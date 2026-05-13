"""Append-only audit log — never updates or deletes."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import AuditLog

log = structlog.get_logger()


class AuditLogger:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        entry = AuditLog(
            timestamp=datetime.utcnow(),
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
        )
        self.session.add(entry)
        await self.session.commit()
        log.info(
            "audit",
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
        )
