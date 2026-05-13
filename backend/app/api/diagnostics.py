"""Diagnostics API — circuit breaker state + recent metrics aggregation."""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_scope
from app.storage.database import get_db
from app.storage.models import CallRecord, FNOLRecord, TurnMetrics

log = structlog.get_logger()
router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# Module-level references — populated when pipeline is first used
_stt_cb = None
_groq_cb = None
_gemini_cb = None
_tts_cb = None


def register_circuit_breakers(stt_cb, groq_cb, gemini_cb, tts_cb) -> None:
    global _stt_cb, _groq_cb, _gemini_cb, _tts_cb
    _stt_cb = stt_cb
    _groq_cb = groq_cb
    _gemini_cb = gemini_cb
    _tts_cb = tts_cb


def _cb_to_stage_health(cb, provider: str) -> dict:
    if cb is None:
        return {
            "provider": provider,
            "status": "unknown",
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "error_rate_1h": 0.0,
            "last_error": None,
        }
    return {
        "provider": provider,
        "status": cb.state.value,
        "consecutive_errors": cb.consecutive_errors,
        "last_error": cb.last_error_at.isoformat() if cb.last_error_at else None,
    }


@router.get("")
async def get_diagnostics(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    # Active calls (outcome == "active")
    active_result = await db.execute(
        select(func.count(CallRecord.call_id)).where(CallRecord.outcome == "active")
    )
    active_calls = active_result.scalar_one() or 0

    # Calls last 1h
    result_1h = await db.execute(
        select(func.count(CallRecord.call_id)).where(CallRecord.started_at >= one_hour_ago)
    )
    calls_1h = result_1h.scalar_one() or 0

    # Calls last 24h
    result_24h = await db.execute(
        select(func.count(CallRecord.call_id)).where(CallRecord.started_at >= one_day_ago)
    )
    calls_24h = result_24h.scalar_one() or 0

    # FNOL completion rate 1h (calls with FNOL completeness >= 0.8)
    total_ended_1h = await db.execute(
        select(func.count(CallRecord.call_id)).where(
            CallRecord.started_at >= one_hour_ago,
            CallRecord.outcome.in_(["complete", "abandoned", "error"]),
        )
    )
    total_ended = total_ended_1h.scalar_one() or 0

    complete_1h = await db.execute(
        select(func.count(FNOLRecord.id))
        .join(CallRecord, FNOLRecord.call_id == CallRecord.call_id)
        .where(
            CallRecord.started_at >= one_hour_ago,
            FNOLRecord.completeness_score >= 0.8,
        )
    )
    complete_count = complete_1h.scalar_one() or 0
    fnol_completion_rate = complete_count / max(total_ended, 1)

    # Avg call duration 1h
    avg_dur = await db.execute(
        select(func.avg(CallRecord.duration_seconds)).where(
            CallRecord.started_at >= one_hour_ago,
            CallRecord.duration_seconds.isnot(None),
        )
    )
    avg_call_duration = float(avg_dur.scalar_one() or 0.0)

    # Fallback rate 1h (turns with fallback / total turns)
    total_turns = await db.execute(
        select(func.count(TurnMetrics.id))
        .join(CallRecord, TurnMetrics.call_id == CallRecord.call_id)
        .where(CallRecord.started_at >= one_hour_ago)
    )
    total_t = total_turns.scalar_one() or 0

    fallback_turns = await db.execute(
        select(func.count(TurnMetrics.id))
        .join(CallRecord, TurnMetrics.call_id == CallRecord.call_id)
        .where(
            CallRecord.started_at >= one_hour_ago,
            TurnMetrics.fallback_triggered == True,
        )
    )
    fallback_t = fallback_turns.scalar_one() or 0
    fallback_rate = fallback_t / max(total_t, 1)

    return {
        "timestamp": now.isoformat(),
        "pipeline": {
            "stt": _cb_to_stage_health(_stt_cb, "sarvam"),
            "llm": _cb_to_stage_health(_groq_cb, "groq"),
            "tts": _cb_to_stage_health(_tts_cb, "sarvam"),
        },
        "active_calls": active_calls,
        "calls_last_1h": calls_1h,
        "calls_last_24h": calls_24h,
        "fnol_completion_rate_1h": round(fnol_completion_rate, 4),
        "avg_call_duration_1h": round(avg_call_duration, 2),
        "fallback_rate_1h": round(fallback_rate, 4),
        "providers": {
            "groq": {
                "status": _groq_cb.state.value if _groq_cb else "unknown",
                "consecutive_errors": _groq_cb.consecutive_errors if _groq_cb else 0,
            },
            "gemini": {
                "status": _gemini_cb.state.value if _gemini_cb else "unknown",
                "consecutive_errors": _gemini_cb.consecutive_errors if _gemini_cb else 0,
            },
            "sarvam_stt": {
                "status": _stt_cb.state.value if _stt_cb else "unknown",
                "consecutive_errors": _stt_cb.consecutive_errors if _stt_cb else 0,
            },
            "sarvam_tts": {
                "status": _tts_cb.state.value if _tts_cb else "unknown",
                "consecutive_errors": _tts_cb.consecutive_errors if _tts_cb else 0,
            },
        },
    }
