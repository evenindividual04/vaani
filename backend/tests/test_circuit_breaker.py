"""Tests for CircuitBreaker — 100% coverage target."""
from datetime import datetime, timedelta

import pytest

from app.pipeline.circuit_breaker import CircuitBreaker, CircuitState


def make_cb(**kwargs) -> CircuitBreaker:
    defaults = {"name": "test", "error_threshold": 3, "cooldown_seconds": 60, "disable_threshold": 3}
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_state_is_healthy():
    cb = make_cb()
    assert cb.state == CircuitState.HEALTHY
    assert cb.is_available() is True


# ── HEALTHY → COOLING_DOWN ────────────────────────────────────────────────────

def test_does_not_open_before_threshold():
    cb = make_cb(error_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.HEALTHY
    assert cb.is_available() is True


def test_opens_on_threshold():
    cb = make_cb(error_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    assert cb.is_available() is False


def test_cooldown_until_is_set():
    cb = make_cb(error_threshold=1, cooldown_seconds=60)
    cb.record_failure()
    assert cb.cooling_until is not None
    assert cb.cooling_until > datetime.utcnow()


# ── COOLING_DOWN → HEALTHY ────────────────────────────────────────────────────

def test_recovers_after_cooldown_expires():
    cb = make_cb(error_threshold=2, cooldown_seconds=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    # Fake expiry
    cb.cooling_until = datetime.utcnow() - timedelta(seconds=2)
    assert cb.is_available() is True
    assert cb.state == CircuitState.HEALTHY


def test_success_resets_errors_in_cooling():
    cb = make_cb(error_threshold=2)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    cb.record_success()
    assert cb.state == CircuitState.HEALTHY
    assert cb.consecutive_errors == 0


# ── COOLING_DOWN → DISABLED ───────────────────────────────────────────────────

def test_disables_after_disable_threshold_cycles():
    cb = make_cb(error_threshold=2, disable_threshold=3)
    # Cycle 1
    cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    # Simulate recovering enough to accumulate more failures
    cb.state = CircuitState.HEALTHY
    # Cycle 2
    cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.COOLING_DOWN
    cb.state = CircuitState.HEALTHY
    # Cycle 3 — should disable
    cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.DISABLED
    assert cb.is_available() is False


# ── DISABLED ──────────────────────────────────────────────────────────────────

def test_disabled_is_never_available():
    cb = make_cb()
    cb.state = CircuitState.DISABLED
    assert cb.is_available() is False
    # Even after success call
    cb.record_success()
    assert cb.state == CircuitState.DISABLED


def test_cooldown_does_not_expire_when_disabled():
    cb = make_cb(error_threshold=2, disable_threshold=2)
    # Force to disabled
    cb.record_failure(); cb.record_failure()
    cb.state = CircuitState.HEALTHY
    cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.DISABLED
    # Fake past cooling time
    cb.cooling_until = datetime.utcnow() - timedelta(seconds=999)
    # Still not available — disabled takes precedence
    assert cb.is_available() is False


# ── status_dict ───────────────────────────────────────────────────────────────

def test_status_dict_keys():
    cb = make_cb()
    d = cb.status_dict()
    assert set(d.keys()) == {
        "name", "state", "consecutive_errors",
        "cooldown_cycles", "last_error_at", "cooling_until",
    }
    assert d["state"] == "healthy"
