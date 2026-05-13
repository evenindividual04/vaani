"""FNOL completeness validator — per §2e scoring formula."""
from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = [
    "policy_number",
    "incident_type",
    "incident_date",
    "incident_location",
    "callback_number",
]

OPTIONAL_FIELDS = [
    "injuries_reported",
    "vehicle_damage",
    "third_party_involved",
    "injury_description",
]

REQUIRED_WEIGHT = 0.15   # 5 fields × 0.15 = 0.75 total
OPTIONAL_WEIGHT = 0.05   # 4 fields × 0.05 = 0.25 total
CONFIDENCE_THRESHOLD = 0.5


def compute_completeness(
    record: dict[str, Any],
    confidence: dict[str, float] | None = None,
) -> float:
    """
    Compute FNOL completeness score 0.0–1.0.

    Required fields contribute 0.15 each; optional 0.05 each.
    A field only counts if value is not None AND confidence > 0.5.
    """
    conf = confidence or {}
    score = 0.0

    for field in REQUIRED_FIELDS:
        value = record.get(field)
        field_conf = conf.get(field, 1.0)  # assume high conf if not provided
        if value is not None and field_conf > CONFIDENCE_THRESHOLD:
            score += REQUIRED_WEIGHT

    for field in OPTIONAL_FIELDS:
        value = record.get(field)
        field_conf = conf.get(field, 1.0)
        if value is not None and field_conf > CONFIDENCE_THRESHOLD:
            score += OPTIONAL_WEIGHT

    return min(round(score, 4), 1.0)


def get_missing_required_fields(
    record: dict[str, Any],
    confidence: dict[str, float] | None = None,
) -> list[str]:
    """Return list of required fields that are still missing or low-confidence."""
    conf = confidence or {}
    missing = []
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        field_conf = conf.get(field, 1.0)
        if value is None or field_conf <= CONFIDENCE_THRESHOLD:
            missing.append(field)
    return missing
