"""Browser WebSocket channel + Live Monitor WebSocket per §3a, §3b."""
from __future__ import annotations

import asyncio
import base64
import time
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.domain.extractor import FNOLExtractor
from app.domain.fsm import ConversationFSM
from app.domain.language import LanguageTracker
from app.domain.prompts.loader import get_prompt
from app.domain.validator import get_missing_required_fields
from app.pipeline.audio import AudioBuffer
from app.pipeline.metrics import ACTIVE_CALLS, CALLS_TOTAL, FNOL_COMPLETENESS
from app.pipeline.orchestrator import PipelineOrchestrator
from app.pipeline.vad import SileroVAD

log = structlog.get_logger()
router = APIRouter(tags=["websocket"])

# ── Live Monitor broadcast manager ───────────────────────────────────────────

class LiveMonitorManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


live_manager = LiveMonitorManager()

# ── Shared pipeline singletons ────────────────────────────────────────────────
_orchestrator: PipelineOrchestrator | None = None
_extractor: FNOLExtractor | None = None
_vad: SileroVAD | None = None


def _get_pipeline():
    global _orchestrator, _extractor, _vad
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
        _extractor = FNOLExtractor(_orchestrator.llm)
        try:
            _vad = SileroVAD()
        except Exception:
            _vad = None
    return _orchestrator, _extractor, _vad


# ── JWT validation helper ─────────────────────────────────────────────────────

def _validate_ws_token(token: str) -> dict | None:
    from app.api.auth import _decode_token
    try:
        return _decode_token(token)
    except Exception:
        return None


# ── Browser call WebSocket ────────────────────────────────────────────────────

@router.websocket("/ws/call")
async def websocket_call_endpoint(ws: WebSocket, token: str = Query(...)):
    user = _validate_ws_token(token)
    if not user:
        await ws.close(code=4001)
        return

    await ws.accept()
    orchestrator, extractor, vad = _get_pipeline()

    call_id = str(uuid.uuid4())
    call_start = time.time()
    fsm = ConversationFSM(call_id=call_id, language="hi-IN")
    lang_tracker = LanguageTracker()
    audio_buffer = AudioBuffer()
    turn_index = 0
    fnol_data: dict = {}

    ACTIVE_CALLS.labels(channel="web").inc()

    # Persist call record
    from app.storage.database import AsyncSessionFactory
    from app.storage.call_store import CallStore
    async with AsyncSessionFactory() as session:
        store = CallStore(session)
        await store.create_call(
            call_id=call_id,
            channel="web",
            language="hi-IN",
            prompt_version=settings.ACTIVE_PROMPT_VERSION,
        )

    try:
        await ws.send_json({"type": "call_ready", "call_id": call_id})
        await live_manager.broadcast({
            "type": "call_started",
            "call_id": call_id,
            "channel": "web",
            "language": "hi-IN",
            "started_at": datetime.utcnow().isoformat(),
        })

        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "audio_chunk":
                pcm = base64.b64decode(data["audio_b64"])
                flushed = audio_buffer.add_pcm(pcm)

                # VAD check on each chunk
                if vad and audio_buffer.should_flush_on_silence():
                    if not vad.is_speech(pcm):
                        flushed = audio_buffer.flush()

                if flushed:
                    await _process_voice_turn(
                        ws, orchestrator, extractor, fsm, lang_tracker,
                        flushed, call_id, call_start, turn_index, fnol_data, "web",
                    )
                    turn_index += 1
                    if fsm.is_complete:
                        break

            elif msg_type == "text_input":
                text = data.get("text", "")
                await _process_text_turn(
                    ws, orchestrator, extractor, fsm, lang_tracker,
                    text, call_id, call_start, turn_index, fnol_data, "web",
                )
                turn_index += 1
                if fsm.is_complete:
                    break

            elif msg_type == "end_call":
                break

    except WebSocketDisconnect:
        log.info("websocket_disconnected", call_id=call_id)
    except Exception as exc:
        log.error("websocket_error", call_id=call_id, error=str(exc))
        try:
            await ws.send_json({"type": "error", "call_id": call_id, "code": "PIPELINE_ERROR", "message": str(exc)})
        except Exception:
            pass
    finally:
        ACTIVE_CALLS.labels(channel="web").dec()
        duration = time.time() - call_start
        outcome = "complete" if fsm.is_complete else "abandoned"
        CALLS_TOTAL.labels(channel="web", language=fsm.language, outcome=outcome).inc()
        if fnol_data.get("completeness_score") is not None:
            FNOL_COMPLETENESS.observe(fnol_data["completeness_score"])

        async with AsyncSessionFactory() as session:
            store = CallStore(session)
            await store.finalize_call(call_id, outcome)

        await live_manager.broadcast({
            "type": "call_ended",
            "call_id": call_id,
            "outcome": outcome,
            "duration_seconds": round(duration, 2),
            "fnol_complete": fnol_data.get("completeness_score", 0) >= 0.8,
        })


async def _process_voice_turn(
    ws, orchestrator, extractor, fsm, lang_tracker,
    wav_bytes, call_id, call_start, turn_index, fnol_data, channel,
):
    system_prompt = get_prompt(fsm.current_prompt_key, settings.ACTIVE_PROMPT_VERSION, fsm.language)
    result = await orchestrator.run_turn(
        audio_wav=wav_bytes,
        text_input=None,
        conversation_history=fsm.history,
        call_id=call_id,
        language=fsm.language,
        system_prompt=system_prompt,
        channel=channel,
    )

    # Update language
    fsm.language = lang_tracker.update(result.language, result.transcript)

    # Update FSM
    fsm.add_turn("user", result.transcript)
    fsm.add_turn("agent", result.response_text)
    timestamp_ms = int((time.time() - call_start) * 1000)

    # Extract FNOL
    fnol_data.update(await extractor.extract(fsm.history, call_id))
    transition = fsm.advance(fnol_data)

    # Persist to DB
    from app.storage.database import AsyncSessionFactory
    from app.storage.call_store import CallStore
    async with AsyncSessionFactory() as session:
        store = CallStore(session)
        await store.add_turn(call_id, turn_index * 2, "user", result.transcript, fsm.language, timestamp_ms, fsm.state.value)
        await store.add_turn(call_id, turn_index * 2 + 1, "agent", result.response_text, fsm.language, timestamp_ms + 100, fsm.state.value)
        await store.upsert_fnol(call_id, fnol_data)
        await store.record_turn_metrics(
            call_id=call_id, turn_index=turn_index,
            stt_ms=result.stt_ms, llm_ms=result.llm_ms, llm_ttft_ms=result.llm_ttft_ms,
            tts_ms=result.tts_ms, total_ms=result.total_ms,
            stt_provider=result.stt_provider, llm_provider=result.llm_provider,
            tts_provider=result.tts_provider, fallback_triggered=result.fallback_triggered,
        )

    # Send audio chunks back
    for chunk in result.audio_chunks:
        await ws.send_json({
            "type": "agent_audio",
            "call_id": call_id,
            "audio_b64": base64.b64encode(chunk).decode(),
            "turn_index": turn_index,
        })

    await ws.send_json({
        "type": "agent_text",
        "call_id": call_id,
        "text": result.response_text,
        "turn_index": turn_index,
    })

    # Broadcast to live monitors
    missing = get_missing_required_fields(fnol_data, fnol_data.get("confidence", {}))
    await live_manager.broadcast({"type": "transcript_turn", "call_id": call_id, "turn_index": turn_index * 2, "speaker": "user", "text": result.transcript, "language": fsm.language, "timestamp_ms": timestamp_ms})
    await live_manager.broadcast({"type": "pipeline_metrics", "call_id": call_id, "turn_index": turn_index, "stt_ms": result.stt_ms, "llm_ms": result.llm_ms, "llm_ttft_ms": result.llm_ttft_ms, "tts_ms": result.tts_ms, "total_ms": result.total_ms, "fallback_triggered": result.fallback_triggered})
    await live_manager.broadcast({"type": "fnol_update", "call_id": call_id, "fields": fnol_data, "completeness_score": fnol_data.get("completeness_score", 0), "missing_fields": missing})
    if transition:
        await live_manager.broadcast({"type": "fsm_transition", "call_id": call_id, "from_state": transition.from_state, "to_state": transition.to_state, "trigger": transition.trigger})


async def _process_text_turn(
    ws, orchestrator, extractor, fsm, lang_tracker,
    text, call_id, call_start, turn_index, fnol_data, channel,
):
    system_prompt = get_prompt(fsm.current_prompt_key, settings.ACTIVE_PROMPT_VERSION, fsm.language)
    result = await orchestrator.run_turn(
        audio_wav=None,
        text_input=text,
        conversation_history=fsm.history,
        call_id=call_id,
        language=fsm.language,
        system_prompt=system_prompt,
        channel=channel,
    )
    fsm.add_turn("user", text)
    fsm.add_turn("agent", result.response_text)
    fnol_data.update(await extractor.extract(fsm.history, call_id))
    fsm.advance(fnol_data)

    await ws.send_json({
        "type": "agent_text",
        "call_id": call_id,
        "text": result.response_text,
        "turn_index": turn_index,
    })


# ── Live monitor WebSocket ────────────────────────────────────────────────────

@router.websocket("/ws/live")
async def websocket_live_endpoint(ws: WebSocket, token: str = Query(...)):
    user = _validate_ws_token(token)
    if not user:
        await ws.close(code=4001)
        return

    await live_manager.connect(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        live_manager.disconnect(ws)
