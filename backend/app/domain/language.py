"""Language detection — Sarvam STT primary, Devanagari heuristic fallback, per §11.3."""
from __future__ import annotations

import structlog

from app.config import settings

log = structlog.get_logger()

_DEVANAGARI_RANGE = ("\u0900", "\u097F")


def is_devanagari_char(c: str) -> bool:
    return _DEVANAGARI_RANGE[0] <= c <= _DEVANAGARI_RANGE[1]


def detect_hinglish(text: str) -> bool:
    """Return True if text is Hinglish (mixed script)."""
    devanagari_count = sum(1 for c in text if is_devanagari_char(c))
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return False
    ratio = devanagari_count / total_alpha
    return 0.1 < ratio < 0.9


def infer_language_from_text(text: str) -> str:
    """
    Heuristic language detection from transcript text.
    Returns 'hi-IN' for Hindi/Hinglish, 'en-IN' for English.
    """
    if not text:
        return "hi-IN"
    devanagari_count = sum(1 for c in text if is_devanagari_char(c))
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return "hi-IN"
    ratio = devanagari_count / total_alpha
    # >10% Devanagari → treat as Hindi/Hinglish
    return "hi-IN" if ratio > 0.1 else "en-IN"


class LanguageTracker:
    """Tracks and locks language for a call."""

    def __init__(self) -> None:
        self.language: str = "hi-IN"
        self._locked: bool = False
        self._turns_since_detection: int = 0

    def update(self, stt_language_code: str | None, transcript: str = "") -> str:
        """Update language from STT result; lock after LANGUAGE_DETECTION_TURNS turns."""
        if self._locked:
            return self.language

        if stt_language_code and stt_language_code in ("hi-IN", "en-IN"):
            detected = stt_language_code
        else:
            detected = infer_language_from_text(transcript)

        self.language = detected
        self._turns_since_detection += 1

        if self._turns_since_detection >= settings.LANGUAGE_DETECTION_TURNS:
            self._locked = True
            log.info("language_locked", language=self.language)

        return self.language

    @property
    def is_locked(self) -> bool:
        return self._locked
