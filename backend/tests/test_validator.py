"""Tests for FNOL validator completeness scoring."""
import pytest

from app.domain.validator import (
    compute_completeness,
    get_missing_required_fields,
    REQUIRED_FIELDS,
    OPTIONAL_FIELDS,
)


def test_empty_record_is_zero():
    score = compute_completeness({})
    assert score == 0.0


def test_all_required_fields_with_high_confidence():
    record = {
        "policy_number": "P123",
        "incident_type": "accident",
        "incident_date": "2024-01-01",
        "incident_location": "Mumbai",
        "callback_number": "9876543210",
    }
    confidence = {f: 0.95 for f in REQUIRED_FIELDS}
    score = compute_completeness(record, confidence)
    assert score == pytest.approx(0.75, abs=0.001)


def test_all_fields_gives_1_0():
    record = {
        "policy_number": "P123",
        "incident_type": "accident",
        "incident_date": "2024-01-01",
        "incident_location": "Mumbai",
        "callback_number": "9876543210",
        "injuries_reported": False,
        "vehicle_damage": True,
        "third_party_involved": False,
    }
    confidence = {f: 0.95 for f in REQUIRED_FIELDS + OPTIONAL_FIELDS}
    score = compute_completeness(record, confidence)
    assert score == pytest.approx(0.90, abs=0.001)  # 5*0.15 + 3*0.05 = 0.90


def test_low_confidence_fields_do_not_count():
    record = {
        "policy_number": "P123",
        "incident_type": "accident",
        "incident_date": "2024-01-01",
        "incident_location": "Mumbai",
        "callback_number": "9876543210",
    }
    # All below threshold
    confidence = {f: 0.3 for f in REQUIRED_FIELDS}
    score = compute_completeness(record, confidence)
    assert score == 0.0


def test_no_confidence_defaults_to_included():
    record = {
        "policy_number": "P123",
        "incident_type": "accident",
        "incident_date": "2024-01-01",
        "incident_location": "Mumbai",
        "callback_number": "9876543210",
    }
    # No confidence dict → assume 1.0 for all
    score = compute_completeness(record)
    assert score == pytest.approx(0.75, abs=0.001)


def test_missing_required_fields():
    record = {"policy_number": "P123"}
    missing = get_missing_required_fields(record)
    assert "incident_type" in missing
    assert "incident_date" in missing
    assert "policy_number" not in missing


def test_none_value_is_missing():
    record = {"policy_number": None}
    missing = get_missing_required_fields(record)
    assert "policy_number" in missing
