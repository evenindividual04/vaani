"""Conversation FSM — 7 states per §11.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger()


class FsmState(str, Enum):
    GREETING = "GREETING"
    POLICY_VERIFY = "POLICY_VERIFY"
    INCIDENT_CAPTURE = "INCIDENT_CAPTURE"
    DETAILS_CAPTURE = "DETAILS_CAPTURE"
    CONTACT_VERIFY = "CONTACT_VERIFY"
    SUMMARY = "SUMMARY"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


@dataclass
class FsmTransition:
    from_state: str
    to_state: str
    trigger: str


STATE_CONFIG: dict[FsmState, dict[str, Any]] = {
    FsmState.GREETING: {
        "entry_prompt": "greeting",
        "max_reprompts": 2,
        "next": FsmState.POLICY_VERIFY,
        "fallback": FsmState.ERROR,
    },
    FsmState.POLICY_VERIFY: {
        "entry_prompt": "policy_verify",
        "max_reprompts": 3,
        "next": FsmState.INCIDENT_CAPTURE,
        "fallback": FsmState.INCIDENT_CAPTURE,
    },
    FsmState.INCIDENT_CAPTURE: {
        "entry_prompt": "incident_capture",
        "max_reprompts": 3,
        "next": FsmState.DETAILS_CAPTURE,
        "fallback": FsmState.DETAILS_CAPTURE,
    },
    FsmState.DETAILS_CAPTURE: {
        "entry_prompt": "details_capture",
        "max_reprompts": 5,
        "next": FsmState.CONTACT_VERIFY,
        "fallback": FsmState.CONTACT_VERIFY,
    },
    FsmState.CONTACT_VERIFY: {
        "entry_prompt": "contact_verify",
        "max_reprompts": 2,
        "next": FsmState.SUMMARY,
        "fallback": FsmState.SUMMARY,
    },
    FsmState.SUMMARY: {
        "entry_prompt": "summary",
        "max_reprompts": 2,
        "next": FsmState.COMPLETE,
        "fallback": FsmState.COMPLETE,
    },
    FsmState.COMPLETE: {
        "entry_prompt": "closing",
        "max_reprompts": 0,
        "next": None,
        "fallback": None,
    },
    FsmState.ERROR: {
        "entry_prompt": "error",
        "max_reprompts": 0,
        "next": None,
        "fallback": None,
    },
}


class ConversationFSM:
    def __init__(self, call_id: str = "", language: str = "hi-IN") -> None:
        self.state = FsmState.GREETING
        self.language = language
        self.call_id = call_id
        self.reprompt_count: int = 0
        self.history: list[dict] = []
        self.transitions: list[FsmTransition] = []

    def add_turn(self, speaker: str, text: str) -> None:
        self.history.append({"speaker": speaker, "text": text})

    def advance(self, fnol_record: Any | None = None) -> FsmTransition | None:
        """Evaluate exit conditions and advance state if met."""
        if self.state in (FsmState.COMPLETE, FsmState.ERROR):
            return None

        config = STATE_CONFIG[self.state]
        should_advance = self._check_exit_condition(fnol_record)

        if should_advance:
            return self._transition_to(config["next"], trigger="exit_condition_met")
        elif self.reprompt_count >= config["max_reprompts"]:
            return self._transition_to(config["fallback"], trigger="max_reprompts_exceeded")
        else:
            self.reprompt_count += 1
            return None

    def _check_exit_condition(self, fnol_record: Any | None) -> bool:
        """State-specific exit conditions."""
        if self.state == FsmState.GREETING:
            # Exit after any user response
            return any(t["speaker"] == "user" for t in self.history)

        if self.state == FsmState.POLICY_VERIFY:
            return bool(fnol_record and fnol_record.get("policy_number"))

        if self.state == FsmState.INCIDENT_CAPTURE:
            return bool(
                fnol_record
                and fnol_record.get("incident_type")
                and fnol_record.get("incident_date")
            )

        if self.state == FsmState.DETAILS_CAPTURE:
            score = fnol_record.get("completeness_score", 0.0) if fnol_record else 0.0
            return score >= 0.8

        if self.state == FsmState.CONTACT_VERIFY:
            return bool(fnol_record and fnol_record.get("callback_number"))

        if self.state == FsmState.SUMMARY:
            # Exit after summary is presented (always advance after one reprompt)
            return self.reprompt_count >= 1

        return False

    def _transition_to(self, target: FsmState | None, trigger: str) -> FsmTransition | None:
        if target is None:
            return None
        from_state = self.state
        self.state = target
        self.reprompt_count = 0
        transition = FsmTransition(
            from_state=from_state.value,
            to_state=target.value,
            trigger=trigger,
        )
        self.transitions.append(transition)
        log.info(
            "fsm_transition",
            call_id=self.call_id,
            from_state=from_state.value,
            to_state=target.value,
            trigger=trigger,
        )
        return transition

    @property
    def current_prompt_key(self) -> str:
        return STATE_CONFIG[self.state]["entry_prompt"]

    @property
    def is_complete(self) -> bool:
        return self.state == FsmState.COMPLETE

    @property
    def turn_count(self) -> int:
        return len(self.history)
