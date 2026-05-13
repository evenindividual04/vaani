"""Tests for FSM — all state transitions and exit conditions."""
import pytest

from app.domain.fsm import ConversationFSM, FsmState


def make_fsm(**kwargs) -> ConversationFSM:
    return ConversationFSM(call_id="test-123", **kwargs)


def test_initial_state():
    fsm = make_fsm()
    assert fsm.state == FsmState.GREETING
    assert not fsm.is_complete


def test_greeting_to_policy_after_user_turn():
    fsm = make_fsm()
    fsm.add_turn("user", "नमस्ते")
    transition = fsm.advance()
    assert fsm.state == FsmState.POLICY_VERIFY
    assert transition is not None
    assert transition.from_state == "GREETING"
    assert transition.to_state == "POLICY_VERIFY"


def test_no_advance_without_user_turn():
    fsm = make_fsm()
    transition = fsm.advance()
    # Should reprompt (no user turn yet)
    assert transition is None
    assert fsm.state == FsmState.GREETING
    assert fsm.reprompt_count == 1


def test_policy_verify_exits_with_policy_number():
    fsm = make_fsm()
    fsm.add_turn("user", "नमस्ते")
    fsm.advance()  # GREETING → POLICY_VERIFY
    fnol = {"policy_number": "SBI-123"}
    transition = fsm.advance(fnol)
    assert fsm.state == FsmState.INCIDENT_CAPTURE
    assert transition.trigger == "exit_condition_met"


def test_incident_capture_exits_with_type_and_date():
    fsm = make_fsm()
    fsm.add_turn("user", "hi")
    fsm.advance()
    fsm.advance({"policy_number": "P123"})

    fnol = {"incident_type": "accident", "incident_date": "2024-03-15"}
    transition = fsm.advance(fnol)
    assert fsm.state == FsmState.DETAILS_CAPTURE


def test_details_capture_exits_at_high_score():
    fsm = make_fsm()
    fsm.add_turn("user", "hi")
    fsm.advance()
    fsm.advance({"policy_number": "P123"})
    fsm.advance({"incident_type": "accident", "incident_date": "2024-01-01"})

    fnol = {"completeness_score": 0.85}
    transition = fsm.advance(fnol)
    assert fsm.state == FsmState.CONTACT_VERIFY


def test_contact_verify_exits_with_callback_number():
    fsm = make_fsm()
    # Drive to CONTACT_VERIFY manually
    fsm.state = FsmState.CONTACT_VERIFY
    fnol = {"callback_number": "9876543210"}
    fsm.advance(fnol)
    assert fsm.state == FsmState.SUMMARY


def test_complete_state_is_terminal():
    fsm = make_fsm()
    fsm.state = FsmState.COMPLETE
    result = fsm.advance()
    assert result is None
    assert fsm.state == FsmState.COMPLETE
    assert fsm.is_complete


def test_max_reprompts_triggers_fallback():
    fsm = make_fsm()
    # GREETING fallback is ERROR (caller couldn't respond at all)
    fsm.advance()  # reprompt 1
    fsm.advance()  # reprompt 2
    fsm.advance()  # reprompt 3 → triggers fallback (ERROR per STATE_CONFIG)
    assert fsm.state == FsmState.ERROR


def test_turn_count():
    fsm = make_fsm()
    assert fsm.turn_count == 0
    fsm.add_turn("user", "hello")
    fsm.add_turn("agent", "response")
    assert fsm.turn_count == 2


def test_prompt_key_matches_state():
    fsm = make_fsm()
    assert fsm.current_prompt_key == "greeting"
    fsm.state = FsmState.POLICY_VERIFY
    assert fsm.current_prompt_key == "policy_verify"
