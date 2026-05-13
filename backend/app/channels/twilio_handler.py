"""Twilio Voice + Media Streams handler per §3c, §9."""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.config import settings
from app.domain.extractor import FNOLExtractor
from app.domain.fsm import ConversationFSM
from app.domain.language import LanguageTracker
from app.domain.prompts.loader import get_prompt
from app.pipeline.audio import AudioBuffer, send_audio_to_twilio
from app.pipeline.metrics import ACTIVE_CALLS, CALLS_TOTAL
from app.pipeline.orchestrator import PipelineOrchestrator

log = structlog.get_logger()
router = APIRouter(tags=["twilio"])

# In-memory orchestrators per active Twilio call (keyed by stream_sid)
_active_calls: dict[str, dict] = {}


@router.post("/voice/incoming")
async def twilio_incoming(request: Request):
    """Twilio calls this when a caller dials our number."""
    # Validate Twilio signature in production
    if settings.ENVIRONMENT == "production" and settings.TWILIO_AUTH_TOKEN:
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        form_data = dict(await request.form())
        if not validator.validate(url, form_data, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form_data = dict(await request.form())
    call_sid = form_data.get("CallSid", "")

    # Build WebSocket URL for Media Streams
    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if settings.ENVIRONMENT == "production" else "ws"
    ws_url = f"{protocol}://{host}/voice/stream"

    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=ws_url)
    stream.parameter(name="callSid", value=call_sid)
    response.append(connect)

    log.info("twilio_incoming", call_sid=call_sid)
    return Response(content=str(response), media_type="application/xml")


@router.post("/voice/status")
async def twilio_status(request: Request):
    """Twilio call status callback."""
    form_data = dict(await request.form())
    call_sid = form_data.get("CallSid")
    status = form_data.get("CallStatus")
    log.info("twilio_status_callback", call_sid=call_sid, status=status)
    return Response(content="", status_code=204)


@router.websocket("/voice/stream")
async def twilio_stream(ws: WebSocket):
    """Twilio Media Streams WebSocket."""
    await ws.accept()

    orchestrator = PipelineOrchestrator()
    extractor = FNOLExtractor(orchestrator.llm)
    fsm = ConversationFSM()
    lang_tracker = LanguageTracker()
    audio_buffer = AudioBuffer()

    call_id: str | None = None
    stream_sid: str | None = None
    call_start = time.time()
    turn_index = 0
    fnol_data: dict = {}

    try:
        async for raw_message in ws.iter_text():
            message = json.loads(raw_message)
            event = message.get("event")

            if event == "connected":
                log.info("twilio_stream_connected")

            elif event == "start":
                call_id = str(uuid.uuid4())
                stream_sid = message.get("streamSid")
                params = message.get("customParameters", {})
                twilio_call_sid = params.get("callSid")
                call_start = time.time()

                ACTIVE_CALLS.labels(channel="phone").inc()

                # Persist call record
                from app.storage.database import AsyncSessionFactory
                from app.storage.call_store import CallStore
                async with AsyncSessionFactory() as session:
                    store = CallStore(session)
                    await store.create_call(
                        call_id=call_id,
                        channel="phone",
                        language="hi-IN",
                        prompt_version=settings.ACTIVE_PROMPT_VERSION,
                        twilio_call_sid=twilio_call_sid,
                    )

                # Send greeting audio
                try:
                    greeting_text = get_prompt("greeting", settings.ACTIVE_PROMPT_VERSION, "hi-IN")
                    greeting_wav = orchestrator.tts.synthesize_single(greeting_text, "hi-IN")
                    await send_audio_to_twilio(ws, stream_sid, greeting_wav)
                except Exception as exc:
                    log.warning("greeting_tts_failed", error=str(exc))

                log.info("twilio_stream_started", call_id=call_id, stream_sid=stream_sid)

            elif event == "media" and call_id and stream_sid:
                payload = message.get("media", {}).get("payload", "")
                flushed = audio_buffer.add_twilio_chunk(payload)

                if flushed:
                    try:
                        system_prompt = get_prompt(
                            fsm.current_prompt_key, settings.ACTIVE_PROMPT_VERSION, fsm.language
                        )
                        result = await orchestrator.run_turn(
                            audio_wav=flushed,
                            text_input=None,
                            conversation_history=fsm.history,
                            call_id=call_id,
                            language=fsm.language,
                            system_prompt=system_prompt,
                            channel="phone",
                        )
                        fsm.language = lang_tracker.update(result.language, result.transcript)
                        fsm.add_turn("user", result.transcript)
                        fsm.add_turn("agent", result.response_text)
                        fnol_data.update(await extractor.extract(fsm.history, call_id))
                        fsm.advance(fnol_data)
                        turn_index += 1

                        for wav_chunk in result.audio_chunks:
                            await send_audio_to_twilio(ws, stream_sid, wav_chunk)

                        if fsm.is_complete:
                            break
                    except Exception as exc:
                        log.error("twilio_turn_error", call_id=call_id, error=str(exc))

            elif event == "stop":
                log.info("twilio_stream_stopped", call_id=call_id)
                break

    except WebSocketDisconnect:
        log.info("twilio_ws_disconnected", call_id=call_id)
    except Exception as exc:
        log.error("twilio_stream_error", call_id=call_id, error=str(exc))
    finally:
        ACTIVE_CALLS.labels(channel="phone").dec()
        if call_id:
            outcome = "complete" if fsm.is_complete else "abandoned"
            CALLS_TOTAL.labels(channel="phone", language=fsm.language, outcome=outcome).inc()
            from app.storage.database import AsyncSessionFactory
            from app.storage.call_store import CallStore
            async with AsyncSessionFactory() as session:
                store = CallStore(session)
                await store.upsert_fnol(call_id, fnol_data)
                await store.finalize_call(call_id, outcome)
