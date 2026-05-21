"""Tests for eval runner — field scoring, scenario execution, aggregation."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.eval.runner import FieldScore, ScenarioScore, score_scenario, run_scenario, run_eval
from app.pipeline.llm import LLMResult


def make_mock_router(json_response: str) -> MagicMock:
    router = MagicMock()
    router.complete = AsyncMock(
        return_value=LLMResult(
            text=json_response,
            latency_ms=100.0,
            ttft_ms=50.0,
            fallback_used=False,
            provider="groq",
            model="llama",
        )
    )
    return router


# ── score_scenario ────────────────────────────────────────────────────────────

def test_exact_match_scores_1():
    extracted = {"incident_type": "accident", "policy_number": "SBI-123"}
    expected = {"incident_type": "accident", "policy_number": "SBI-123"}
    field_scores, details = score_scenario(extracted, expected)
    assert field_scores["incident_type"] == 1.0
    assert field_scores["policy_number"] == 1.0


def test_case_insensitive_match():
    extracted = {"incident_type": "ACCIDENT"}
    expected = {"incident_type": "accident"}
    field_scores, _ = score_scenario(extracted, expected)
    assert field_scores["incident_type"] == 1.0


def test_alternative_match_scores_1():
    extracted = {"incident_date": "March 15"}
    expected = {"incident_date": "2024-03-15"}
    alts = {"incident_date": ["March 15", "15 March"]}
    field_scores, _ = score_scenario(extracted, expected, acceptable_alternatives=alts)
    assert field_scores["incident_date"] == 1.0


def test_partial_match_scores_08():
    extracted = {"incident_location": "Bandra Kurla Complex BKC"}
    expected = {"incident_location": "BKC"}
    field_scores, _ = score_scenario(extracted, expected)
    assert field_scores["incident_location"] == 0.8


def test_miss_scores_0():
    extracted = {"incident_type": None}
    expected = {"incident_type": "accident"}
    field_scores, _ = score_scenario(extracted, expected)
    assert field_scores["incident_type"] == 0.0


def test_boolean_exact_match():
    extracted = {"injuries_reported": True, "vehicle_damage": False}
    expected = {"injuries_reported": True, "vehicle_damage": False}
    field_scores, _ = score_scenario(extracted, expected)
    assert field_scores["injuries_reported"] == 1.0
    assert field_scores["vehicle_damage"] == 1.0


def test_boolean_mismatch_scores_0():
    extracted = {"injuries_reported": False}
    expected = {"injuries_reported": True}
    field_scores, _ = score_scenario(extracted, expected)
    assert field_scores["injuries_reported"] == 0.0


# ── run_scenario ──────────────────────────────────────────────────────────────

GOOD_EXTRACTION = json.dumps({
    "policy_number": "SBI-2024-789456",
    "incident_type": "accident",
    "incident_date": "2024-03-15",
    "incident_location": "Mumbai Highway",
    "injuries_reported": False,
    "injury_description": None,
    "vehicle_damage": True,
    "damage_description": None,
    "third_party_involved": True,
    "callback_number": "9876543210",
    "preferred_language": "hi-IN",
    "confidence": {k: 0.9 for k in ["policy_number", "incident_type", "incident_date", "incident_location", "injuries_reported", "vehicle_damage", "third_party_involved", "callback_number"]},
})

H1_SCENARIO = {
    "id": "H1",
    "name": "Clean complete FNOL in Hindi",
    "language": "hi-IN",
    "transcript": [
        {"speaker": "user", "text": "SBI-2024-789456"},
        {"speaker": "user", "text": "कल रात कार एक्सीडेंट, मुंबई हाईवे"},
        {"speaker": "user", "text": "9876543210"},
    ],
    "expected": {
        "policy_number": "SBI-2024-789456",
        "incident_type": "accident",
        "callback_number": "9876543210",
    },
}


@pytest.mark.asyncio
async def test_run_scenario_passing(monkeypatch):
    from app.domain.extractor import FNOLExtractor
    router = make_mock_router(GOOD_EXTRACTION)
    extractor = FNOLExtractor(llm_router=router)
    score = await run_scenario(H1_SCENARIO, extractor)
    assert isinstance(score, ScenarioScore)
    assert score.scenario_id == "H1"
    assert score.overall_accuracy > 0.5
    assert score.passed is True


@pytest.mark.asyncio
async def test_run_scenario_extractor_exception():
    from app.domain.extractor import FNOLExtractor
    router = MagicMock()
    router.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
    extractor = FNOLExtractor(llm_router=router)

    score = await run_scenario(H1_SCENARIO, extractor)
    assert score.passed is False
    assert score.overall_accuracy == 0.0


# ── run_eval ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_eval_returns_summary(monkeypatch):
    from app.domain import extractor as ext_module
    from app.domain.extractor import FNOLExtractor

    # Patch LLMRouter inside eval.runner
    router = make_mock_router(GOOD_EXTRACTION)
    monkeypatch.setattr("app.pipeline.llm.LLMRouter", lambda: router)
    monkeypatch.setattr("app.domain.extractor.FNOLExtractor", lambda llm: FNOLExtractor(llm_router=router))

    summary, scenario_results = await run_eval("v1", scenario_ids=["H1"])
    assert "total_scenarios" in summary
    assert summary["total_scenarios"] == 1
    assert "H1" in scenario_results


@pytest.mark.asyncio
async def test_run_eval_all_scenarios(monkeypatch):
    from app.domain.extractor import FNOLExtractor

    router = make_mock_router(GOOD_EXTRACTION)
    monkeypatch.setattr("app.pipeline.llm.LLMRouter", lambda: router)
    monkeypatch.setattr("app.domain.extractor.FNOLExtractor", lambda llm: FNOLExtractor(llm_router=router))

    summary, scenario_results = await run_eval("v1", scenario_ids="all")
    assert summary["total_scenarios"] == 15
    assert len(scenario_results) == 15
