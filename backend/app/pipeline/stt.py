"""Sarvam STT wrapper with circuit breaker and Prometheus metrics."""
from __future__ import annotations

import io
import time
from dataclasses import dataclass

import structlog

from app.config import settings
from app.pipeline.circuit_breaker import CircuitBreaker
from app.pipeline.metrics import PROVIDER_ERRORS, STT_LATENCY, update_provider_health

log = structlog.get_logger()


@dataclass
class STTResult:
    transcript: str
    language_code: str
    latency_ms: float


class SarvamSTT:
    def __init__(self) -> None:
        from sarvamai import SarvamAI

        self.client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        self.circuit_breaker = CircuitBreaker(
            name="sarvam_stt",
            error_threshold=settings.CB_ERROR_THRESHOLD,
            cooldown_seconds=settings.CB_COOLDOWN_SECONDS,
            disable_threshold=settings.CB_DISABLE_THRESHOLD,
        )

    async def transcribe(
        self,
        audio_wav: bytes,
        language_code: str = "hi-IN",
        channel: str = "web",
        call_id: str = "",
    ) -> STTResult:
        if not self.circuit_breaker.is_available():
            raise RuntimeError("sarvam_stt circuit breaker is open")

        start = time.perf_counter()
        try:
            audio_io = io.BytesIO(audio_wav)
            audio_io.name = "audio.wav"

            response = self.client.speech_to_text.transcribe(
                file=audio_io,
                model=settings.SARVAM_STT_MODEL,
                language_code=language_code,
                with_timestamps=False,
            )

            latency_ms = (time.perf_counter() - start) * 1000
            self.circuit_breaker.record_success()
            update_provider_health("sarvam", "stt", "healthy")

            detected_lang = getattr(response, "language_code", language_code) or language_code
            transcript = getattr(response, "transcript", "") or ""

            STT_LATENCY.labels(
                provider="sarvam", language=detected_lang, channel=channel
            ).observe(latency_ms)

            log.info(
                "stt_complete",
                call_id=call_id,
                latency_ms=round(latency_ms, 1),
                language=detected_lang,
                transcript_length=len(transcript),
            )
            return STTResult(
                transcript=transcript,
                language_code=detected_lang,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self.circuit_breaker.record_failure()
            cb_state = self.circuit_breaker.state.value
            update_provider_health("sarvam", "stt", cb_state)
            PROVIDER_ERRORS.labels(
                stage="stt", provider="sarvam", error_type=type(exc).__name__
            ).inc()
            log.error("stt_failed", call_id=call_id, error=str(exc), cb_state=cb_state)
            raise
