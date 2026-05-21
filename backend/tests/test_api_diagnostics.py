"""Tests for /diagnostics endpoint."""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import CallRecord, FNOLRecord, TurnMetrics


@pytest.mark.asyncio
async def test_diagnostics_shape(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/diagnostics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert "timestamp" in body
    assert "pipeline" in body
    assert "active_calls" in body
    assert "calls_last_1h" in body
    assert "calls_last_24h" in body
    assert "fnol_completion_rate_1h" in body
    assert "avg_call_duration_1h" in body
    assert "fallback_rate_1h" in body
    assert "providers" in body


@pytest.mark.asyncio
async def test_diagnostics_pipeline_stages(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/diagnostics", headers=auth_headers)
    body = resp.json()
    pipeline = body["pipeline"]
    assert "stt" in pipeline
    assert "llm" in pipeline
    assert "tts" in pipeline


@pytest.mark.asyncio
async def test_diagnostics_providers_shape(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/diagnostics", headers=auth_headers)
    body = resp.json()
    providers = body["providers"]
    assert "groq" in providers
    assert "gemini" in providers
    assert "sarvam_stt" in providers
    assert "sarvam_tts" in providers


@pytest.mark.asyncio
async def test_diagnostics_counts_active_calls(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    active_call = CallRecord(
        call_id="diag-active-1",
        channel="web",
        language="hi-IN",
        started_at=datetime.utcnow(),
        outcome="active",
        prompt_version="v1",
    )
    db_session.add(active_call)
    await db_session.commit()

    resp = await test_client.get("/diagnostics", headers=auth_headers)
    body = resp.json()
    assert body["active_calls"] >= 1


@pytest.mark.asyncio
async def test_diagnostics_requires_auth(test_client: AsyncClient):
    resp = await test_client.get("/diagnostics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_diagnostics_zero_values_on_empty_db(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/diagnostics", headers=auth_headers)
    body = resp.json()
    assert body["active_calls"] == 0
    assert body["calls_last_1h"] == 0
    assert body["calls_last_24h"] == 0
    assert body["avg_call_duration_1h"] == 0.0
