"""Tests for /calls API — list, detail, replay, soft delete."""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import CallRecord, ConversationTurn, FNOLRecord


async def _seed_call(db: AsyncSession, call_id: str = "call-abc", outcome: str = "complete") -> CallRecord:
    call = CallRecord(
        call_id=call_id,
        channel="web",
        language="hi-IN",
        started_at=datetime.utcnow(),
        outcome=outcome,
        prompt_version="v1",
    )
    db.add(call)
    await db.commit()
    return call


@pytest.mark.asyncio
async def test_list_calls_empty(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/calls", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_calls_returns_seeded(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_call(db_session, "call-1")
    await _seed_call(db_session, "call-2")

    resp = await test_client.get("/calls", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_calls_pagination(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    for i in range(5):
        await _seed_call(db_session, f"call-p{i}")

    resp = await test_client.get("/calls?page=1&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2


@pytest.mark.asyncio
async def test_list_calls_filter_channel(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    call_web = CallRecord(call_id="web-1", channel="web", language="hi-IN",
                          started_at=datetime.utcnow(), outcome="complete", prompt_version="v1")
    call_phone = CallRecord(call_id="phone-1", channel="phone", language="hi-IN",
                            started_at=datetime.utcnow(), outcome="complete", prompt_version="v1")
    db_session.add_all([call_web, call_phone])
    await db_session.commit()

    resp = await test_client.get("/calls?channel=phone", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["channel"] == "phone"


@pytest.mark.asyncio
async def test_get_call_success(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_call(db_session, "detail-1")
    resp = await test_client.get("/calls/detail-1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == "detail-1"
    assert body["channel"] == "web"
    assert "transcript" in body


@pytest.mark.asyncio
async def test_get_call_not_found(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/calls/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_call_replay(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    call = await _seed_call(db_session, "replay-1")
    turn = ConversationTurn(
        call_id="replay-1",
        turn_index=0,
        speaker="user",
        text="Hello",
        language="en-IN",
        timestamp_ms=100,
        fsm_state="GREETING",
    )
    db_session.add(turn)
    await db_session.commit()

    resp = await test_client.get("/calls/replay-1/replay", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "transcript" in body
    assert len(body["transcript"]) == 1


@pytest.mark.asyncio
async def test_delete_call_soft_deletes(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_call(db_session, "del-1")

    resp = await test_client.delete("/calls/del-1", headers=auth_headers)
    assert resp.status_code == 204

    # Call should still exist in DB but marked deleted
    from sqlalchemy import select
    result = await db_session.execute(select(CallRecord).where(CallRecord.call_id == "del-1"))
    call = result.scalar_one_or_none()
    assert call is not None
    assert call.is_deleted is True


@pytest.mark.asyncio
async def test_delete_call_not_found(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.delete("/calls/no-such-call", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_audio_no_artifact(test_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    await _seed_call(db_session, "audio-1")
    resp = await test_client.get("/calls/audio-1/audio", headers=auth_headers)
    assert resp.status_code == 404
