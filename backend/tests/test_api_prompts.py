"""Tests for /prompts API — CRUD, deploy, rollback, diff."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import PromptVersion
from datetime import datetime


async def _seed_version(db: AsyncSession, version_id: str, is_active: bool = False) -> PromptVersion:
    pv = PromptVersion(
        version_id=version_id,
        description=f"Version {version_id}",
        templates={"greeting_hi": f"नमस्ते from {version_id}", "greeting_en": f"Hello from {version_id}"},
        created_at=datetime.utcnow(),
        is_active=is_active,
    )
    db.add(pv)
    await db.commit()
    return pv


@pytest.mark.asyncio
async def test_list_prompts_empty(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/prompts", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "versions" in body
    assert "active_version" in body


@pytest.mark.asyncio
async def test_create_prompt(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.post("/prompts", headers=auth_headers, json={
        "version_id": "v2",
        "description": "Second version",
        "templates": {"greeting_hi": "नमस्ते", "greeting_en": "Hello"},
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["version_id"] == "v2"
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_create_duplicate_returns_409(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-dup")
    resp = await test_client.post("/prompts", headers=auth_headers, json={
        "version_id": "v-dup",
        "description": "duplicate",
        "templates": {},
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_prompt_by_id(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-get")
    resp = await test_client.get("/prompts/v-get", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_id"] == "v-get"
    assert "templates" in body


@pytest.mark.asyncio
async def test_get_prompt_not_found(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/prompts/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deploy_prompt(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-deploy")
    resp = await test_client.post("/prompts/v-deploy/deploy", headers=auth_headers, json={"confirm": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_version"] == "v-deploy"


@pytest.mark.asyncio
async def test_deploy_without_confirm_returns_400(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-noconfirm")
    resp = await test_client.post("/prompts/v-noconfirm/deploy", headers=auth_headers, json={"confirm": False})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_deploy_deactivates_previous(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-old", is_active=True)
    await _seed_version(db_session, "v-new")

    resp = await test_client.post("/prompts/v-new/deploy", headers=auth_headers, json={"confirm": True})
    assert resp.status_code == 200

    # v-old should now be inactive
    from sqlalchemy import select
    result = await db_session.execute(select(PromptVersion).where(PromptVersion.version_id == "v-old"))
    old = result.scalar_one_or_none()
    await db_session.refresh(old)
    assert old.is_active is False


@pytest.mark.asyncio
async def test_rollback_prompt(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-rb-current", is_active=True)
    await _seed_version(db_session, "v-rb-target")

    resp = await test_client.post("/prompts/v-rb-target/rollback", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_version"] == "v-rb-target"
    assert body["rolled_back_from"] == "v-rb-current"


@pytest.mark.asyncio
async def test_diff_prompts(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_version(db_session, "v-diff-a")
    pv_b = PromptVersion(
        version_id="v-diff-b",
        description="Version B",
        templates={"greeting_hi": "नमस्ते UPDATED", "greeting_en": "Hello from v-diff-a"},
        created_at=datetime.utcnow(),
        is_active=False,
    )
    db_session.add(pv_b)
    await db_session.commit()

    resp = await test_client.get("/prompts/diff/v-diff-a/v-diff-b", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "diffs" in body
    # greeting_hi differs, greeting_en is the same
    assert "greeting_hi" in body["diffs"]
    assert "greeting_en" not in body["diffs"]
