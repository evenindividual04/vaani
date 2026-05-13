"""FNOL extractor — JSON-constrained LLM extraction from transcript."""
from __future__ import annotations

import json
from typing import Any

import structlog

from app.domain.validator import compute_completeness

log = structlog.get_logger()

EXTRACTOR_SYSTEM_PROMPT = """You are an FNOL (First Notice of Loss) extraction system for an Indian insurance company.
Given a conversation transcript between a caller and an insurance agent, extract structured claim information.

Extract the following fields:
- policy_number: The policy/contract number (any format)
- incident_type: One of: accident, theft, fire, flood, natural_disaster, medical, other
- incident_date: Date of the incident (normalize to YYYY-MM-DD if possible, else return as spoken)
- incident_location: Where the incident occurred (city, address, landmark)
- injuries_reported: boolean — were any injuries mentioned?
- injury_description: Details of injuries if mentioned
- vehicle_damage: boolean — was vehicle damage mentioned?
- damage_description: Description of damage if mentioned
- third_party_involved: boolean — was any third party involved?
- callback_number: Phone number for follow-up
- preferred_language: "hi-IN" if conversation was Hindi/Hinglish, "en-IN" if English

For each field also provide a confidence score 0.0-1.0.
0.9-1.0: explicitly stated and unambiguous
0.6-0.8: inferred from context, likely correct
0.3-0.5: guessed, uncertain
0.0: not mentioned, null

IMPORTANT:
- Handle Hindi text and Hinglish (mixed Hindi/English) correctly
- Indian date formats: "15 March ko", "teen tarikh ko" = March 3rd
- Indian number formats: "nine eight seven six" spoken as individual digits
- Return ONLY valid JSON. No preamble, no explanation.

Output format:
{
  "policy_number": string | null,
  "incident_type": string | null,
  "incident_date": string | null,
  "incident_location": string | null,
  "injuries_reported": boolean | null,
  "injury_description": string | null,
  "vehicle_damage": boolean | null,
  "damage_description": string | null,
  "third_party_involved": boolean | null,
  "callback_number": string | null,
  "preferred_language": "hi-IN" | "en-IN",
  "confidence": {
    "policy_number": float,
    "incident_type": float,
    "incident_date": float,
    "incident_location": float,
    "injuries_reported": float,
    "vehicle_damage": float,
    "third_party_involved": float,
    "callback_number": float
  }
}"""

EMPTY_FNOL: dict[str, Any] = {
    "policy_number": None,
    "incident_type": None,
    "incident_date": None,
    "incident_location": None,
    "injuries_reported": None,
    "injury_description": None,
    "vehicle_damage": None,
    "damage_description": None,
    "third_party_involved": None,
    "callback_number": None,
    "preferred_language": "hi-IN",
    "confidence": {},
    "completeness_score": 0.0,
}

VALID_INCIDENT_TYPES = {
    "accident", "theft", "fire", "flood",
    "natural_disaster", "medical", "other",
}


def _format_transcript(history: list[dict]) -> str:
    lines = []
    for turn in history:
        speaker = "Caller" if turn.get("speaker") == "user" else "Agent"
        lines.append(f"{speaker}: {turn.get('text', '')}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict | None:
    try:
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def _validate_and_clean(raw: dict) -> dict[str, Any]:
    """Validate field values and normalize."""
    record = dict(EMPTY_FNOL)
    record.update({
        "policy_number": raw.get("policy_number"),
        "incident_type": raw.get("incident_type"),
        "incident_date": raw.get("incident_date"),
        "incident_location": raw.get("incident_location"),
        "injuries_reported": raw.get("injuries_reported"),
        "injury_description": raw.get("injury_description"),
        "vehicle_damage": raw.get("vehicle_damage"),
        "damage_description": raw.get("damage_description"),
        "third_party_involved": raw.get("third_party_involved"),
        "callback_number": raw.get("callback_number"),
        "preferred_language": raw.get("preferred_language", "hi-IN"),
        "confidence": raw.get("confidence", {}),
    })
    # Validate incident_type
    if record["incident_type"] and record["incident_type"] not in VALID_INCIDENT_TYPES:
        record["incident_type"] = "other"
    # Validate language
    if record["preferred_language"] not in ("hi-IN", "en-IN"):
        record["preferred_language"] = "hi-IN"
    # Compute completeness
    record["completeness_score"] = compute_completeness(record, record["confidence"])
    return record


class FNOLExtractor:
    """LLM-based structured FNOL extraction with JSON retry."""

    def __init__(self, llm_router=None) -> None:
        self._llm_router = llm_router  # injected; lazy-loaded if None

    def _get_router(self):
        if self._llm_router is None:
            from app.pipeline.llm import LLMRouter
            self._llm_router = LLMRouter()
        return self._llm_router

    async def extract(
        self,
        conversation_history: list[dict],
        call_id: str = "",
    ) -> dict[str, Any]:
        """Extract FNOL record from conversation history."""
        transcript_text = _format_transcript(conversation_history)
        if not transcript_text.strip():
            return dict(EMPTY_FNOL)

        messages = [
            {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract FNOL data from this conversation:\n\n{transcript_text}",
            },
        ]

        router = self._get_router()

        # First attempt
        try:
            result = await router.complete(messages, call_id, "extraction")
            parsed = _parse_json(result.text)
            if parsed:
                log.info("fnol_extraction_success", call_id=call_id, attempt=1)
                return _validate_and_clean(parsed)
        except Exception as exc:
            log.warning("fnol_extraction_attempt1_failed", call_id=call_id, error=str(exc))

        # Retry with explicit JSON instruction
        messages[1]["content"] += "\n\nRESPOND ONLY WITH JSON. NO EXPLANATIONS."
        try:
            result = await router.complete(messages, call_id, "extraction")
            parsed = _parse_json(result.text)
            if parsed:
                log.info("fnol_extraction_success", call_id=call_id, attempt=2)
                return _validate_and_clean(parsed)
        except Exception as exc:
            log.error("fnol_extraction_failed", call_id=call_id, error=str(exc))

        log.warning("fnol_extraction_returning_empty", call_id=call_id)
        return dict(EMPTY_FNOL)
