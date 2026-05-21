"""Calls API — paginated list, detail, audio, replay, soft delete."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_scope
from app.storage.audit_log import AuditLogger
from app.storage.call_store import CallStore
from app.storage.database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/calls", tags=["calls"])


def _serialize_turn(turn) -> dict:
    return {
        "turn_index": turn.turn_index,
        "speaker": turn.speaker,
        "text": turn.text,
        "language": turn.language,
        "timestamp_ms": turn.timestamp_ms,
        "fsm_state": turn.fsm_state,
    }


def _serialize_fnol(fnol) -> dict | None:
    if fnol is None:
        return None
    return {
        "policy_number": fnol.policy_number,
        "incident_type": fnol.incident_type,
        "incident_date": fnol.incident_date,
        "incident_location": fnol.incident_location,
        "injuries_reported": fnol.injuries_reported,
        "injury_description": fnol.injury_description,
        "vehicle_damage": fnol.vehicle_damage,
        "damage_description": fnol.damage_description,
        "third_party_involved": fnol.third_party_involved,
        "callback_number": fnol.callback_number,
        "preferred_language": fnol.preferred_language,
        "extraction_confidence": fnol.extraction_confidence,
        "completeness_score": fnol.completeness_score,
    }


def _serialize_call_summary(call) -> dict:
    return {
        "call_id": call.call_id,
        "channel": call.channel,
        "language": call.language,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "outcome": call.outcome,
        "prompt_version": call.prompt_version,
    }


@router.get("")
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = None,
    language: str | None = None,
    outcome: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    effective_from = from_date or date_from
    effective_to = to_date or date_to
    store = CallStore(db)
    calls, total = await store.list_calls(
        page=page, page_size=page_size, channel=channel,
        language=language, outcome=outcome, date_from=effective_from, date_to=effective_to,
    )
    return {
        "items": [_serialize_call_summary(c) for c in calls],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{call_id}")
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    store = CallStore(db)
    call = await store.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.storage.models import CallRecord
    result = await db.execute(
        select(CallRecord)
        .options(
            selectinload(CallRecord.turns),
            selectinload(CallRecord.fnol_record),
            selectinload(CallRecord.pipeline_metrics),
            selectinload(CallRecord.audio_artifact),
        )
        .where(CallRecord.call_id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return {
        "call_id": call.call_id,
        "channel": call.channel,
        "language": call.language,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "outcome": call.outcome,
        "transcript": [_serialize_turn(t) for t in sorted(call.turns, key=lambda t: t.turn_index)],
        "fnol_record": _serialize_fnol(call.fnol_record),
        "prompt_version": call.prompt_version,
        "audio_available": call.audio_artifact is not None,
    }


@router.get("/{call_id}/audio")
async def get_call_audio(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.storage.models import CallRecord

    result = await db.execute(
        select(CallRecord)
        .options(selectinload(CallRecord.audio_artifact))
        .where(CallRecord.call_id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not call.audio_artifact:
        raise HTTPException(status_code=404, detail="Audio not available for this call")

    import pathlib
    audio_path = pathlib.Path(call.audio_artifact.file_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    def iter_file():
        with open(audio_path, "rb") as f:
            yield from f

    return StreamingResponse(iter_file(), media_type="audio/wav")


@router.get("/{call_id}/replay")
async def get_call_replay(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.storage.models import CallRecord

    result = await db.execute(
        select(CallRecord)
        .options(
            selectinload(CallRecord.turns),
            selectinload(CallRecord.fnol_record),
            selectinload(CallRecord.pipeline_metrics),
        )
        .where(CallRecord.call_id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    turns = sorted(call.turns, key=lambda t: t.turn_index)
    metrics = sorted(call.pipeline_metrics, key=lambda m: m.turn_index) if call.pipeline_metrics else []

    per_turn_metrics = [
        {
            "turn_index": m.turn_index,
            "stt_ms": m.stt_ms,
            "llm_ms": m.llm_ms,
            "llm_ttft_ms": m.llm_ttft_ms,
            "tts_ms": m.tts_ms,
            "total_ms": m.total_ms,
            "stt_provider": m.stt_provider,
            "llm_provider": m.llm_provider,
            "tts_provider": m.tts_provider,
            "fallback_triggered": m.fallback_triggered,
        }
        for m in metrics
    ]

    return {
        "transcript": [_serialize_turn(t) for t in turns],
        "per_turn_metrics": per_turn_metrics,
        "final_fnol": _serialize_fnol(call.fnol_record),
    }


@router.get("/{call_id}/fnol/export")
async def export_fnol_record(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.storage.models import CallRecord

    result = await db.execute(
        select(CallRecord)
        .options(selectinload(CallRecord.fnol_record))
        .where(CallRecord.call_id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call or not call.fnol_record:
        raise HTTPException(status_code=404, detail="FNOL record not found")

    payload = _serialize_fnol(call.fnol_record)
    headers = {"Content-Disposition": f"attachment; filename=fnol_{call_id}.json"}
    return JSONResponse(content=payload, headers=headers)


@router.delete("/{call_id}", status_code=204)
async def delete_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("write")),
):
    store = CallStore(db)
    call = await store.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    await store.soft_delete_call(call_id)

    audit = AuditLogger(db)
    await audit.log(
        actor=user.get("sub", "unknown"),
        action="call_deleted",
        resource_type="call",
        resource_id=call_id,
        detail={"soft_delete": True},
    )
