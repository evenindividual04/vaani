"""Parallel batch TTS via Sarvam bulbul:v2, per §12.2."""
from __future__ import annotations

import asyncio
import base64
import re
import time
from dataclasses import dataclass

import structlog

from app.config import settings
from app.pipeline.audio import generate_silence_wav
from app.pipeline.circuit_breaker import CircuitBreaker
from app.pipeline.metrics import PROVIDER_ERRORS, TTS_LATENCY, update_provider_health

log = structlog.get_logger()


@dataclass
class TTSResult:
    audio_chunks: list[bytes]
    latency_ms: float
    sentence_count: int


def split_into_sentences(text: str, language: str = "hi-IN") -> list[str]:
    """Split LLM response into sentences for parallel TTS synthesis."""
    if language == "hi-IN":
        # Handle Devanagari danda (।) as well as Latin punctuation
        parts = re.split(r"[।.!?]+", text)
    else:
        parts = re.split(r"[.!?]+", text)

    sentences = [s.strip() for s in parts if s.strip()]

    # Chunk sentences > 200 chars on comma boundaries
    result: list[str] = []
    for s in sentences:
        if len(s) > 200:
            sub = re.split(r"[,،]+", s)
            result.extend(p.strip() for p in sub if p.strip())
        else:
            result.append(s)

    return result if result else [text]


class SarvamTTS:
    def __init__(self) -> None:
        from sarvamai import AsyncSarvamAI, SarvamAI

        self.client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        self.async_client = AsyncSarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        self.circuit_breaker = CircuitBreaker(
            name="sarvam_tts",
            error_threshold=settings.CB_ERROR_THRESHOLD,
            cooldown_seconds=settings.CB_COOLDOWN_SECONDS,
            disable_threshold=settings.CB_DISABLE_THRESHOLD,
            recovery_seconds=settings.CB_RECOVERY_SECONDS,
        )

    async def synthesize_parallel(
        self,
        sentences: list[str],
        language_code: str,
        call_id: str = "",
    ) -> TTSResult:
        """Fire all sentences simultaneously; return audio chunks in order."""
        if not sentences:
            return TTSResult(audio_chunks=[], latency_ms=0.0, sentence_count=0)

        if not self.circuit_breaker.is_available():
            silence = generate_silence_wav(500)
            return TTSResult(
                audio_chunks=[silence] * len(sentences),
                latency_ms=0.0,
                sentence_count=len(sentences),
            )

        start = time.perf_counter()

        async def synthesize_one(text: str, index: int) -> tuple[int, bytes]:
            resp = await self.async_client.text_to_speech.convert(
                text=text,
                target_language_code=language_code,
                speaker=settings.SARVAM_TTS_SPEAKER,
                model=settings.SARVAM_TTS_MODEL,
            )
            audio = base64.b64decode(resp.audios[0])
            return index, audio

        tasks = [synthesize_one(s, i) for i, s in enumerate(sentences)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        silence_chunk = generate_silence_wav(500)
        audio_chunks: list[bytes] = [silence_chunk] * len(sentences)

        success_count = 0
        for result in results:
            if isinstance(result, Exception):
                self.circuit_breaker.record_failure()
                PROVIDER_ERRORS.labels(
                    stage="tts", provider="sarvam", error_type=type(result).__name__
                ).inc()
                log.warning("tts_sentence_failed", error=str(result))
            else:
                idx, audio = result
                audio_chunks[idx] = audio
                success_count += 1

        if success_count > 0:
            self.circuit_breaker.record_success()
            update_provider_health("sarvam", "tts", "healthy")
        else:
            update_provider_health("sarvam", "tts", self.circuit_breaker.state.value)

        latency_ms = (time.perf_counter() - start) * 1000
        TTS_LATENCY.labels(provider="sarvam", language=language_code).observe(latency_ms)

        log.info(
            "tts_complete",
            call_id=call_id,
            sentences=len(sentences),
            success=success_count,
            latency_ms=round(latency_ms, 1),
        )
        return TTSResult(
            audio_chunks=audio_chunks,
            latency_ms=latency_ms,
            sentence_count=len(sentences),
        )

    async def synthesize_one_async(self, text: str, language_code: str) -> bytes:
        """Single-sentence async TTS for streaming pipeline; returns silence on failure."""
        if not self.circuit_breaker.is_available():
            return generate_silence_wav(500)
        try:
            resp = await self.async_client.text_to_speech.convert(
                text=text,
                target_language_code=language_code,
                speaker=settings.SARVAM_TTS_SPEAKER,
                model=settings.SARVAM_TTS_MODEL,
            )
            self.circuit_breaker.record_success()
            update_provider_health("sarvam", "tts", "healthy")
            return base64.b64decode(resp.audios[0])
        except Exception as exc:
            self.circuit_breaker.record_failure()
            PROVIDER_ERRORS.labels(
                stage="tts", provider="sarvam", error_type=type(exc).__name__
            ).inc()
            log.warning("tts_one_failed", error=str(exc))
            return generate_silence_wav(500)

    def synthesize_single(self, text: str, language_code: str) -> bytes:
        """Synchronous single sentence synthesis (for greeting on Twilio connect)."""
        resp = self.client.text_to_speech.convert(
            text=text,
            target_language_code=language_code,
            speaker=settings.SARVAM_TTS_SPEAKER,
            model=settings.SARVAM_TTS_MODEL,
        )
        return base64.b64decode(resp.audios[0])
