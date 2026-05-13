"""WhatsApp webhook handler — text-only pipeline per §3d."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request, Response

from app.config import settings
from app.domain.extractor import FNOLExtractor
from app.domain.fsm import ConversationFSM
from app.domain.language import LanguageTracker
from app.domain.prompts.loader import get_prompt
from app.pipeline.metrics import ACTIVE_CALLS, CALLS_TOTAL
from app.pipeline.orchestrator import PipelineOrchestrator

log = structlog.get_logger()
router = APIRouter(tags=["whatsapp"])

# Session management: phone_number → {call_id, fsm, orchestrator, ...}
_sessions: dict[str, dict] = {}
_orchestrator: PipelineOrchestrator | None = None
_extractor: FNOLExtractor | None = None


def _get_pipeline():
    global _orchestrator, _extractor
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
        _extractor = FNOLExtractor(_orchestrator.llm)
    return _orchestrator, _extractor


def _get_or_create_session(from_number: str) -> dict:
    import uuid
    if from_number not in _sessions:
        call_id = str(uuid.uuid4())
        _sessions[from_number] = {
            "call_id": call_id,
            "fsm": ConversationFSM(call_id=call_id, language="hi-IN"),
            "lang_tracker": LanguageTracker(),
            "fnol_data": {},
        }
        ACTIVE_CALLS.labels(channel="whatsapp").inc()
        log.info("whatsapp_session_created", call_id=call_id, from_number=from_number)
    return _sessions[from_number]


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = dict(await request.form())
    body = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "")

    if not body or not from_number:
        return Response(content="", status_code=204)

    orchestrator, extractor = _get_pipeline()
    session = _get_or_create_session(from_number)
    fsm: ConversationFSM = session["fsm"]
    lang_tracker: LanguageTracker = session["lang_tracker"]
    fnol_data: dict = session["fnol_data"]
    call_id: str = session["call_id"]

    try:
        system_prompt = get_prompt(
            fsm.current_prompt_key, settings.ACTIVE_PROMPT_VERSION, fsm.language
        )
        result = await orchestrator.run_turn(
            audio_wav=None,
            text_input=body,
            conversation_history=fsm.history,
            call_id=call_id,
            language=fsm.language,
            system_prompt=system_prompt,
            channel="whatsapp",
        )

        fsm.language = lang_tracker.update(None, body)
        fsm.add_turn("user", body)
        fsm.add_turn("agent", result.response_text)
        fnol_data.update(await extractor.extract(fsm.history, call_id))
        fsm.advance(fnol_data)

        # Send reply via Twilio WhatsApp
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                from twilio.rest import Client as TwilioClient
                client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    from_=settings.TWILIO_WHATSAPP_NUMBER,
                    to=from_number,
                    body=result.response_text,
                )
            except Exception as exc:
                log.error("whatsapp_send_failed", error=str(exc))

        if fsm.is_complete:
            ACTIVE_CALLS.labels(channel="whatsapp").dec()
            CALLS_TOTAL.labels(channel="whatsapp", language=fsm.language, outcome="complete").inc()
            _sessions.pop(from_number, None)

        return Response(content="", status_code=204)

    except Exception as exc:
        log.error("whatsapp_turn_error", call_id=call_id, error=str(exc))
        return Response(content="", status_code=204)
