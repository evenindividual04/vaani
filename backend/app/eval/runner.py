"""Eval runner — parallel scenario execution + field-level scoring per §14.2."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

from app.eval.scenarios import SCENARIO_MAP, SCENARIOS

log = structlog.get_logger()


@dataclass
class FieldScore:
    field: str
    expected: object
    extracted: object
    score: float
    match_type: str  # "exact" | "alternative" | "partial" | "miss"


@dataclass
class ScenarioScore:
    scenario_id: str
    scenario_name: str
    field_scores: dict[str, float]
    field_details: list[dict]
    overall_accuracy: float
    passed: bool


def score_scenario(
    extracted: dict,
    expected: dict,
    acceptable_alternatives: dict | None = None,
    expected_partial: bool = False,
) -> tuple[dict[str, float], list[dict]]:
    alts = acceptable_alternatives or {}
    field_scores: dict[str, float] = {}
    field_details: list[dict] = []

    for field_name, expected_value in expected.items():
        extracted_value = extracted.get(field_name)

        detail: dict = {
            "field": field_name,
            "expected": expected_value,
            "extracted": extracted_value,
            "score": 0.0,
            "match_type": "miss",
        }

        if extracted_value is None:
            field_scores[field_name] = 0.0
            field_details.append(detail)
            continue

        # Boolean fields
        if isinstance(expected_value, bool):
            if extracted_value == expected_value:
                detail.update(score=1.0, match_type="exact")
            field_scores[field_name] = detail["score"]
            field_details.append(detail)
            continue

        # Exact match (case-insensitive for strings)
        if str(extracted_value).strip().lower() == str(expected_value).strip().lower():
            detail.update(score=1.0, match_type="exact")
            field_scores[field_name] = 1.0
            field_details.append(detail)
            continue

        # Acceptable alternatives
        field_alts = alts.get(field_name, [])
        if any(str(extracted_value).strip().lower() == str(alt).strip().lower() for alt in field_alts):
            detail.update(score=1.0, match_type="alternative")
            field_scores[field_name] = 1.0
            field_details.append(detail)
            continue

        # Partial string match
        if isinstance(expected_value, str) and isinstance(extracted_value, str):
            if expected_value.lower() in extracted_value.lower():
                detail.update(score=0.8, match_type="partial")
                field_scores[field_name] = 0.8
                field_details.append(detail)
                continue
            # Check alternatives for partial
            if any(str(alt).lower() in extracted_value.lower() for alt in field_alts):
                detail.update(score=0.8, match_type="partial_alternative")
                field_scores[field_name] = 0.8
                field_details.append(detail)
                continue

        field_scores[field_name] = 0.0
        field_details.append(detail)

    return field_scores, field_details


async def run_scenario(scenario: dict, extractor) -> ScenarioScore:
    """Run a single scenario through the extractor and score it."""
    expected = scenario.get("expected", {})
    alts = scenario.get("acceptable_alternatives", {})
    expected_partial = scenario.get("expected_partial", False)

    try:
        extracted = await extractor.extract(scenario["transcript"], scenario["id"])
        field_scores, field_details = score_scenario(extracted, expected, alts, expected_partial)
        overall = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
        passed = overall >= 0.8
    except Exception as exc:
        log.error("scenario_run_failed", scenario_id=scenario["id"], error=str(exc))
        field_scores = {f: 0.0 for f in expected}
        field_details = []
        overall = 0.0
        passed = False

    return ScenarioScore(
        scenario_id=scenario["id"],
        scenario_name=scenario["name"],
        field_scores=field_scores,
        field_details=field_details,
        overall_accuracy=round(overall, 4),
        passed=passed,
    )


async def run_eval(
    prompt_version_id: str,
    scenario_ids: list[str] | str = "all",
    baseline_version_id: str | None = None,
) -> tuple[dict, dict]:
    """Run eval scenarios in parallel; return (summary, scenario_results)."""
    from app.domain.extractor import FNOLExtractor
    from app.pipeline.llm import LLMRouter

    llm = LLMRouter()
    extractor = FNOLExtractor(llm)

    if scenario_ids == "all":
        scenarios_to_run = SCENARIOS
    else:
        scenarios_to_run = [SCENARIO_MAP[sid] for sid in scenario_ids if sid in SCENARIO_MAP]

    log.info("eval_starting", count=len(scenarios_to_run), version=prompt_version_id)

    tasks = [run_scenario(s, extractor) for s in scenarios_to_run]
    results: list[ScenarioScore] = await asyncio.gather(*tasks)

    # Aggregate
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    # Per-field accuracy across all scenarios
    all_fields: dict[str, list[float]] = {}
    for result in results:
        for field_name, score in result.field_scores.items():
            all_fields.setdefault(field_name, []).append(score)

    per_field_accuracy = {
        field: round(sum(scores) / len(scores), 4)
        for field, scores in all_fields.items()
    }

    overall_accuracy = round(sum(r.overall_accuracy for r in results) / max(total, 1), 4)

    summary = {
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "overall_accuracy": overall_accuracy,
        "per_field_accuracy": per_field_accuracy,
        "baseline_delta": None,  # computed separately if baseline provided
    }

    scenario_results = {
        r.scenario_id: {
            "name": r.scenario_name,
            "passed": r.passed,
            "overall_accuracy": r.overall_accuracy,
            "field_scores": r.field_scores,
            "field_details": r.field_details,
        }
        for r in results
    }

    log.info(
        "eval_complete",
        version=prompt_version_id,
        passed=passed,
        total=total,
        accuracy=overall_accuracy,
    )
    return summary, scenario_results
