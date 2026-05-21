"""Tests for FNOLExtractor — JSON extraction, retry, validation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.extractor import (
    FNOLExtractor,
    _format_transcript,
    _parse_json,
    _validate_and_clean,
    EMPTY_FNOL,
)
from app.pipeline.llm import LLMResult


def make_llm_result(text: str) -> LLMResult:
    return LLMResult(text=text, latency_ms=100.0, ttft_ms=50.0, fallback_used=False, provider="groq", model="llama")


def make_mock_router(response_text: str) -> MagicMock:
    router = MagicMock()
    router.complete = AsyncMock(return_value=make_llm_result(response_text))
    return router


# ── _format_transcript ────────────────────────────────────────────────────────

def test_format_transcript_labels():
    history = [
        {"speaker": "agent", "text": "Hello"},
        {"speaker": "user", "text": "My policy is SBI-123"},
    ]
    result = _format_transcript(history)
    assert "Agent: Hello" in result
    assert "Caller: My policy is SBI-123" in result


# ── _parse_json ───────────────────────────────────────────────────────────────

def test_parse_json_valid():
    data = {"policy_number": "ABC-123", "incident_type": "accident"}
    assert _parse_json(json.dumps(data)) == data


def test_parse_json_with_code_fence():
    data = {"policy_number": "ABC-123"}
    text = "```json\n" + json.dumps(data) + "\n```"
    assert _parse_json(text) == data


def test_parse_json_invalid_returns_none():
    assert _parse_json("Not JSON at all") is None
    assert _parse_json("{'bad': 'quotes'}") is None


# ── _validate_and_clean ───────────────────────────────────────────────────────

def test_validate_cleans_invalid_incident_type():
    raw = {"incident_type": "earthquake", "preferred_language": "hi-IN", "confidence": {}}
    result = _validate_and_clean(raw)
    assert result["incident_type"] == "other"


def test_validate_cleans_invalid_language():
    raw = {"preferred_language": "fr-FR", "confidence": {}}
    result = _validate_and_clean(raw)
    assert result["preferred_language"] == "hi-IN"


def test_validate_sets_completeness_score():
    raw = {
        "policy_number": "SBI-123",
        "incident_type": "accident",
        "incident_date": "2024-03-15",
        "incident_location": "Mumbai",
        "injuries_reported": False,
        "vehicle_damage": True,
        "third_party_involved": True,
        "callback_number": "9876543210",
        "preferred_language": "hi-IN",
        "confidence": {k: 0.9 for k in ["policy_number", "incident_type", "incident_date", "incident_location", "injuries_reported", "vehicle_damage", "third_party_involved", "callback_number"]},
    }
    result = _validate_and_clean(raw)
    assert result["completeness_score"] > 0.5


# ── FNOLExtractor.extract ─────────────────────────────────────────────────────

FULL_HINDI_TRANSCRIPT = [
    {"speaker": "agent", "text": "नमस्ते, पॉलिसी नंबर बताएं।"},
    {"speaker": "user", "text": "SBI-2024-789456"},
    {"speaker": "agent", "text": "क्या हुआ?"},
    {"speaker": "user", "text": "कल रात कार एक्सीडेंट हो गई मुंबई हाईवे पर।"},
    {"speaker": "user", "text": "9876543210"},
]

GOOD_FNOL_JSON = json.dumps({
    "policy_number": "SBI-2024-789456",
    "incident_type": "accident",
    "incident_date": "2024-03-15",
    "incident_location": "Mumbai Highway",
    "injuries_reported": False,
    "injury_description": None,
    "vehicle_damage": True,
    "damage_description": None,
    "third_party_involved": False,
    "callback_number": "9876543210",
    "preferred_language": "hi-IN",
    "confidence": {
        "policy_number": 0.95,
        "incident_type": 0.9,
        "incident_date": 0.6,
        "incident_location": 0.85,
        "injuries_reported": 0.8,
        "vehicle_damage": 0.9,
        "third_party_involved": 0.5,
        "callback_number": 0.99,
    },
})


@pytest.mark.asyncio
async def test_extract_full_fnol():
    router = make_mock_router(GOOD_FNOL_JSON)
    extractor = FNOLExtractor(llm_router=router)
    result = await extractor.extract(FULL_HINDI_TRANSCRIPT, call_id="e-1")
    assert result["policy_number"] == "SBI-2024-789456"
    assert result["incident_type"] == "accident"
    assert result["callback_number"] == "9876543210"
    assert result["completeness_score"] > 0


@pytest.mark.asyncio
async def test_extract_partial_fnol():
    partial_json = json.dumps({
        "policy_number": None,
        "incident_type": "theft",
        "incident_date": None,
        "incident_location": "Chennai",
        "injuries_reported": None,
        "injury_description": None,
        "vehicle_damage": None,
        "damage_description": None,
        "third_party_involved": None,
        "callback_number": None,
        "preferred_language": "en-IN",
        "confidence": {"incident_type": 0.9, "incident_location": 0.7},
    })
    router = make_mock_router(partial_json)
    extractor = FNOLExtractor(llm_router=router)
    result = await extractor.extract([{"speaker": "user", "text": "theft in Chennai"}], "partial-1")
    assert result["incident_type"] == "theft"
    assert result["policy_number"] is None


@pytest.mark.asyncio
async def test_extract_empty_history_returns_empty():
    router = make_mock_router(GOOD_FNOL_JSON)
    extractor = FNOLExtractor(llm_router=router)
    result = await extractor.extract([], call_id="empty-1")
    assert result == dict(EMPTY_FNOL)


@pytest.mark.asyncio
async def test_extract_retries_on_json_failure():
    """First call returns garbage, second returns valid JSON."""
    call_count = 0

    async def side_effect(messages, call_id, purpose):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_llm_result("Sorry, I cannot help with that.")
        return make_llm_result(GOOD_FNOL_JSON)

    router = MagicMock()
    router.complete = AsyncMock(side_effect=side_effect)

    extractor = FNOLExtractor(llm_router=router)
    result = await extractor.extract(FULL_HINDI_TRANSCRIPT, call_id="retry-1")
    assert call_count == 2
    assert result["policy_number"] == "SBI-2024-789456"


@pytest.mark.asyncio
async def test_extract_returns_empty_on_double_failure():
    router = MagicMock()
    router.complete = AsyncMock(return_value=make_llm_result("Not JSON"))

    extractor = FNOLExtractor(llm_router=router)
    result = await extractor.extract(FULL_HINDI_TRANSCRIPT, call_id="fail-2")
    assert result == dict(EMPTY_FNOL)
