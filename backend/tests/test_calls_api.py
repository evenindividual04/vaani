from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.storage.models import CallRecord, FNOLRecord


@pytest.mark.asyncio
async def test_list_calls_date_range_filters(test_client, auth_headers, db_session):
    now = datetime.utcnow()
    in_range = CallRecord(
        call_id="call-in-range",
        channel="web",
        language="hi-IN",
        started_at=now - timedelta(hours=2),
        outcome="complete",
        prompt_version="v1",
    )
    out_of_range = CallRecord(
        call_id="call-out-range",
        channel="web",
        language="hi-IN",
        started_at=now - timedelta(days=3),
        outcome="complete",
        prompt_version="v1",
    )
    db_session.add_all([in_range, out_of_range])
    await db_session.commit()

    from_date = (now - timedelta(hours=4)).isoformat()
    to_date = (now - timedelta(hours=1)).isoformat()

    resp = await test_client.get(
        f"/calls?from_date={from_date}&to_date={to_date}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    ids = {item["call_id"] for item in payload["items"]}
    assert "call-in-range" in ids
    assert "call-out-range" not in ids


@pytest.mark.asyncio
async def test_fnol_export_returns_attachment(test_client, auth_headers, db_session):
    call = CallRecord(
        call_id="call-export",
        channel="phone",
        language="en-IN",
        started_at=datetime.utcnow(),
        outcome="complete",
        prompt_version="v1",
    )
    fnol = FNOLRecord(
        call_id="call-export",
        policy_number="POL-123",
        incident_type="accident",
        incident_date="2024-01-01",
        incident_location="Mumbai",
        injuries_reported=False,
        vehicle_damage=True,
        third_party_involved=False,
        callback_number="9999999999",
        preferred_language="en-IN",
        extraction_confidence={},
        completeness_score=0.95,
        extracted_at=datetime.utcnow(),
    )
    db_session.add_all([call, fnol])
    await db_session.commit()

    resp = await test_client.get("/calls/call-export/fnol/export", headers=auth_headers)
    assert resp.status_code == 200
    assert "attachment;" in resp.headers.get("content-disposition", "")
    body = resp.json()
    assert body["policy_number"] == "POL-123"
    assert body["incident_type"] == "accident"
