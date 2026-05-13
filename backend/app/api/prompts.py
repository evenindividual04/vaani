"""Prompts API — CRUD, deploy, rollback, diff per §6."""
from __future__ import annotations

import difflib
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_scope
from app.storage.audit_log import AuditLogger
from app.storage.database import get_db
from app.storage.models import PromptVersion

log = structlog.get_logger()
router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptCreateRequest(BaseModel):
    version_id: str
    description: str
    templates: dict[str, str]


class DeployRequest(BaseModel):
    confirm: bool


def _serialize_version(pv: PromptVersion, include_templates: bool = False) -> dict:
    d = {
        "version_id": pv.version_id,
        "description": pv.description,
        "created_at": pv.created_at.isoformat() if pv.created_at else None,
        "is_active": pv.is_active,
        "eval_score": pv.eval_score,
    }
    if include_templates:
        d["templates"] = pv.templates
    return d


@router.get("")
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    result = await db.execute(select(PromptVersion).order_by(PromptVersion.created_at.desc()))
    versions = result.scalars().all()
    active = next((v.version_id for v in versions if v.is_active), None)
    return {
        "versions": [_serialize_version(v) for v in versions],
        "active_version": active,
    }


@router.post("", status_code=201)
async def create_prompt(
    body: PromptCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("write")),
):
    existing = await db.get(PromptVersion, body.version_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Version '{body.version_id}' already exists")
    pv = PromptVersion(
        version_id=body.version_id,
        description=body.description,
        templates=body.templates,
        created_at=datetime.utcnow(),
        is_active=False,
    )
    db.add(pv)
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        actor=user.get("sub", "unknown"),
        action="prompt_created",
        resource_type="prompt_version",
        resource_id=body.version_id,
    )
    return _serialize_version(pv, include_templates=True)


@router.get("/diff/{version_a}/{version_b}")
async def diff_prompts(
    version_a: str,
    version_b: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    pv_a = await db.get(PromptVersion, version_a)
    pv_b = await db.get(PromptVersion, version_b)
    if not pv_a:
        raise HTTPException(status_code=404, detail=f"Version '{version_a}' not found")
    if not pv_b:
        raise HTTPException(status_code=404, detail=f"Version '{version_b}' not found")

    templates_a = pv_a.templates or {}
    templates_b = pv_b.templates or {}
    all_keys = set(templates_a) | set(templates_b)

    diffs = {}
    for key in all_keys:
        a_text = templates_a.get(key, "")
        b_text = templates_b.get(key, "")
        if a_text != b_text:
            unified = "\n".join(
                difflib.unified_diff(
                    a_text.splitlines(),
                    b_text.splitlines(),
                    fromfile=f"{version_a}/{key}",
                    tofile=f"{version_b}/{key}",
                    lineterm="",
                )
            )
            diffs[key] = {"a": a_text, "b": b_text, "unified_diff": unified}

    return {"diffs": diffs}


@router.get("/{version_id}")
async def get_prompt(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    pv = await db.get(PromptVersion, version_id)
    if not pv:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return _serialize_version(pv, include_templates=True)


@router.post("/{version_id}/deploy")
async def deploy_prompt(
    version_id: str,
    body: DeployRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("admin")),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true")
    pv = await db.get(PromptVersion, version_id)
    if not pv:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

    # Deactivate all, then activate this one
    await db.execute(update(PromptVersion).values(is_active=False))
    pv.is_active = True
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        actor=user.get("sub", "unknown"),
        action="prompt_deployed",
        resource_type="prompt_version",
        resource_id=version_id,
    )
    log.info("prompt_deployed", version=version_id, actor=user.get("sub"))
    return {"active_version": version_id, "deployed_at": datetime.utcnow().isoformat()}


@router.post("/{version_id}/rollback")
async def rollback_prompt(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("admin")),
):
    # Find the currently active version
    result = await db.execute(select(PromptVersion).where(PromptVersion.is_active == True))
    current = result.scalar_one_or_none()
    current_id = current.version_id if current else None

    target = await db.get(PromptVersion, version_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

    await db.execute(update(PromptVersion).values(is_active=False))
    target.is_active = True
    await db.commit()

    audit = AuditLogger(db)
    await audit.log(
        actor=user.get("sub", "unknown"),
        action="prompt_rolled_back",
        resource_type="prompt_version",
        resource_id=version_id,
        detail={"rolled_back_from": current_id},
    )
    return {"active_version": version_id, "rolled_back_from": current_id}
