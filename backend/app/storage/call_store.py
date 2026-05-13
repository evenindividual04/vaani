"""Storage layer — CallStore for async CRUD of all call-related tables."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import (
    AudioArtifact,
    CallRecord,
    ConversationTurn,
    EvalRun,
    FNOLRecord,
    TurnMetrics,
)

log = structlog.get_logger()


class CallStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── CallRecord ────────────────────────────────────────────────────────────

    async def create_call(
        self,
        call_id: str,
        channel: str,
        language: str,
        prompt_version: str,
        twilio_call_sid: str | None = None,
    ) -> CallRecord:
        record = CallRecord(
            call_id=call_id,
            channel=channel,
            language=language,
            started_at=datetime.utcnow(),
            outcome="active",
            prompt_version=prompt_version,
            twilio_call_sid=twilio_call_sid,
        )
        self.session.add(record)
        await self.session.commit()
        return record

    async def get_call(self, call_id: str) -> CallRecord | None:
        result = await self.session.execute(
            select(CallRecord).where(
                CallRecord.call_id == call_id, CallRecord.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_calls(
        self,
        page: int = 1,
        page_size: int = 20,
        channel: str | None = None,
        language: str | None = None,
        outcome: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[CallRecord], int]:
        query = select(CallRecord).where(CallRecord.is_deleted == False)
        if channel:
            query = query.where(CallRecord.channel == channel)
        if language:
            query = query.where(CallRecord.language == language)
        if outcome:
            query = query.where(CallRecord.outcome == outcome)
        if date_from:
            query = query.where(CallRecord.started_at >= date_from)
        if date_to:
            query = query.where(CallRecord.started_at <= date_to)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        query = query.order_by(CallRecord.started_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def finalize_call(
        self,
        call_id: str,
        outcome: str,
        ended_at: datetime | None = None,
    ) -> None:
        ended = ended_at or datetime.utcnow()
        await self.session.execute(
            update(CallRecord)
            .where(CallRecord.call_id == call_id)
            .values(outcome=outcome, ended_at=ended)
        )
        await self.session.commit()

    async def soft_delete_call(self, call_id: str) -> None:
        await self.session.execute(
            update(CallRecord)
            .where(CallRecord.call_id == call_id)
            .values(is_deleted=True)
        )
        await self.session.commit()

    # ── ConversationTurn ──────────────────────────────────────────────────────

    async def add_turn(
        self,
        call_id: str,
        turn_index: int,
        speaker: str,
        text: str,
        language: str,
        timestamp_ms: int,
        fsm_state: str,
    ) -> ConversationTurn:
        turn = ConversationTurn(
            call_id=call_id,
            turn_index=turn_index,
            speaker=speaker,
            text=text,
            language=language,
            timestamp_ms=timestamp_ms,
            fsm_state=fsm_state,
        )
        self.session.add(turn)
        await self.session.commit()
        return turn

    # ── FNOLRecord ────────────────────────────────────────────────────────────

    async def upsert_fnol(self, call_id: str, fnol_data: dict[str, Any]) -> FNOLRecord:
        result = await self.session.execute(
            select(FNOLRecord).where(FNOLRecord.call_id == call_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in fnol_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.extracted_at = datetime.utcnow()
            await self.session.commit()
            return existing
        else:
            record = FNOLRecord(
                call_id=call_id,
                extracted_at=datetime.utcnow(),
                **{k: v for k, v in fnol_data.items() if hasattr(FNOLRecord, k)},
            )
            self.session.add(record)
            await self.session.commit()
            return record

    # ── TurnMetrics ───────────────────────────────────────────────────────────

    async def record_turn_metrics(
        self,
        call_id: str,
        turn_index: int,
        stt_ms: float,
        llm_ms: float,
        llm_ttft_ms: float,
        tts_ms: float,
        total_ms: float,
        stt_provider: str,
        llm_provider: str,
        tts_provider: str,
        fallback_triggered: bool,
    ) -> TurnMetrics:
        metrics = TurnMetrics(
            call_id=call_id,
            turn_index=turn_index,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            llm_ttft_ms=llm_ttft_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
            stt_provider=stt_provider,
            llm_provider=llm_provider,
            tts_provider=tts_provider,
            fallback_triggered=fallback_triggered,
        )
        self.session.add(metrics)
        await self.session.commit()
        return metrics

    # ── EvalRun ───────────────────────────────────────────────────────────────

    async def create_eval_run(
        self, prompt_version_id: str, baseline_version_id: str | None = None
    ) -> EvalRun:
        run = EvalRun(
            prompt_version_id=prompt_version_id,
            baseline_version_id=baseline_version_id,
            status="queued",
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        await self.session.commit()
        return run

    async def update_eval_run(self, run_id: str, **kwargs) -> None:
        await self.session.execute(
            update(EvalRun).where(EvalRun.run_id == run_id).values(**kwargs)
        )
        await self.session.commit()

    async def get_eval_run(self, run_id: str) -> EvalRun | None:
        result = await self.session.execute(
            select(EvalRun).where(EvalRun.run_id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_eval_runs(self) -> list[EvalRun]:
        result = await self.session.execute(
            select(EvalRun).order_by(EvalRun.started_at.desc())
        )
        return list(result.scalars().all())
