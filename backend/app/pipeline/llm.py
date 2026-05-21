"""LLM clients: GroqLLM (primary) + GeminiLLM (fallback) + LLMRouter, per §1d."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"[।.!?]+\s*")

import structlog

from app.config import settings
from app.pipeline.circuit_breaker import CircuitBreaker
from app.pipeline.metrics import (
    CIRCUIT_BREAKER_OPENS,
    FALLBACKS_TRIGGERED,
    LLM_LATENCY,
    LLM_TTFT,
    PROVIDER_ERRORS,
    update_provider_health,
)

log = structlog.get_logger()


@dataclass
class LLMResult:
    text: str
    latency_ms: float
    ttft_ms: float
    fallback_used: bool
    provider: str
    model: str


class GroqLLM:
    """Primary LLM — Groq Llama 3.3 70B."""

    def __init__(self) -> None:
        from groq import AsyncGroq

        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.circuit_breaker = CircuitBreaker(
            name="groq",
            error_threshold=settings.CB_ERROR_THRESHOLD,
            cooldown_seconds=settings.CB_COOLDOWN_SECONDS,
            disable_threshold=settings.CB_DISABLE_THRESHOLD,
            recovery_seconds=settings.CB_RECOVERY_SECONDS,
        )

    async def complete(
        self,
        messages: list[dict],
        call_id: str = "",
        purpose: str = "conversation",
    ) -> LLMResult:
        start = time.perf_counter()
        ttft_ms = 0.0

        try:
            # Use streaming to capture TTFT
            stream = await self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                stream=True,
                temperature=0.3,
                max_tokens=512,
            )

            chunks: list[str] = []
            first_token = True
            async for chunk in stream:
                if first_token and chunk.choices[0].delta.content:
                    ttft_ms = (time.perf_counter() - start) * 1000
                    first_token = False
                content = chunk.choices[0].delta.content or ""
                chunks.append(content)

            text = "".join(chunks)
            latency_ms = (time.perf_counter() - start) * 1000

            self.circuit_breaker.record_success()
            update_provider_health("groq", "llm", "healthy")

            LLM_LATENCY.labels(provider="groq", model=settings.GROQ_MODEL).observe(latency_ms)
            LLM_TTFT.labels(provider="groq", model=settings.GROQ_MODEL).observe(ttft_ms)

            log.info(
                "llm_complete",
                call_id=call_id,
                provider="groq",
                latency_ms=round(latency_ms, 1),
                ttft_ms=round(ttft_ms, 1),
                purpose=purpose,
            )
            return LLMResult(
                text=text,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                fallback_used=False,
                provider="groq",
                model=settings.GROQ_MODEL,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self.circuit_breaker.record_failure()
            if self.circuit_breaker.state.value != "healthy":
                CIRCUIT_BREAKER_OPENS.labels(provider="groq").inc()
            update_provider_health("groq", "llm", self.circuit_breaker.state.value)
            PROVIDER_ERRORS.labels(
                stage="llm", provider="groq", error_type=type(exc).__name__
            ).inc()
            log.error("llm_groq_failed", call_id=call_id, error=str(exc))
            raise

    async def stream_sentences(self, messages: list[dict], call_id: str = ""):
        """Yield complete sentences from the streaming token output."""
        if not self.circuit_breaker.is_available():
            raise RuntimeError("groq circuit breaker is open")

        start = time.perf_counter()
        buffer = ""

        try:
            stream = await self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                stream=True,
                temperature=0.3,
                max_tokens=512,
            )

            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                buffer += token
                while True:
                    m = _SENTENCE_END.search(buffer)
                    if not m:
                        break
                    sentence = buffer[: m.end()].strip()
                    buffer = buffer[m.end() :]
                    if sentence:
                        yield sentence

            if buffer.strip():
                yield buffer.strip()

            latency_ms = (time.perf_counter() - start) * 1000
            self.circuit_breaker.record_success()
            update_provider_health("groq", "llm", "healthy")
            LLM_LATENCY.labels(provider="groq", model=settings.GROQ_MODEL).observe(latency_ms)
            log.info("llm_stream_complete", call_id=call_id, latency_ms=round(latency_ms, 1))

        except Exception as exc:
            self.circuit_breaker.record_failure()
            update_provider_health("groq", "llm", self.circuit_breaker.state.value)
            PROVIDER_ERRORS.labels(
                stage="llm", provider="groq", error_type=type(exc).__name__
            ).inc()
            log.error("llm_groq_stream_failed", call_id=call_id, error=str(exc))
            raise


class GeminiLLM:
    """Fallback LLM — Google Gemini Flash."""

    def __init__(self) -> None:
        import google.generativeai as genai

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self.circuit_breaker = CircuitBreaker(
            name="gemini",
            error_threshold=settings.CB_ERROR_THRESHOLD,
            cooldown_seconds=settings.CB_COOLDOWN_SECONDS,
            disable_threshold=settings.CB_DISABLE_THRESHOLD,
            recovery_seconds=settings.CB_RECOVERY_SECONDS,
        )

    async def complete(
        self,
        messages: list[dict],
        call_id: str = "",
        purpose: str = "conversation",
    ) -> LLMResult:
        start = time.perf_counter()
        try:
            # Convert OpenAI-style messages to Gemini format
            prompt = "\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in messages
                if m.get("content")
            )
            response = await self.model.generate_content_async(prompt)
            text = response.text or ""
            latency_ms = (time.perf_counter() - start) * 1000
            ttft_ms = latency_ms  # Gemini doesn't support streaming TTFT easily

            self.circuit_breaker.record_success()
            update_provider_health("gemini", "llm", "healthy")

            LLM_LATENCY.labels(provider="gemini", model=settings.GEMINI_MODEL).observe(latency_ms)
            LLM_TTFT.labels(provider="gemini", model=settings.GEMINI_MODEL).observe(ttft_ms)

            log.info(
                "llm_complete",
                call_id=call_id,
                provider="gemini",
                latency_ms=round(latency_ms, 1),
                purpose=purpose,
            )
            return LLMResult(
                text=text,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                fallback_used=True,
                provider="gemini",
                model=settings.GEMINI_MODEL,
            )

        except Exception as exc:
            self.circuit_breaker.record_failure()
            update_provider_health("gemini", "llm", self.circuit_breaker.state.value)
            PROVIDER_ERRORS.labels(
                stage="llm", provider="gemini", error_type=type(exc).__name__
            ).inc()
            log.error("llm_gemini_failed", call_id=call_id, error=str(exc))
            raise


class LLMRouter:
    """Routes LLM requests: Groq primary → Gemini fallback."""

    def __init__(self) -> None:
        self.primary = GroqLLM()
        self.fallback = GeminiLLM()

    async def complete(
        self,
        messages: list[dict],
        call_id: str = "",
        purpose: str = "conversation",
    ) -> LLMResult:
        if self.primary.circuit_breaker.is_available():
            try:
                return await self.primary.complete(messages, call_id, purpose)
            except Exception as exc:
                log.warning("llm_primary_failed_using_fallback", error=str(exc))

        FALLBACKS_TRIGGERED.labels(stage="llm", from_provider="groq", to_provider="gemini").inc()
        return await self.fallback.complete(messages, call_id, purpose)

    async def stream_sentences(self, messages: list[dict], call_id: str = ""):
        """Yield sentences: Groq streaming primary, Gemini complete() fallback."""
        if self.primary.circuit_breaker.is_available():
            try:
                async for sentence in self.primary.stream_sentences(messages, call_id):
                    yield sentence
                return
            except Exception as exc:
                log.warning("llm_primary_stream_failed_using_fallback", error=str(exc))

        FALLBACKS_TRIGGERED.labels(stage="llm", from_provider="groq", to_provider="gemini").inc()
        result = await self.fallback.complete(messages, call_id)
        from app.pipeline.tts import split_into_sentences
        for sentence in split_into_sentences(result.text):
            yield sentence

    @property
    def groq_cb(self) -> CircuitBreaker:
        return self.primary.circuit_breaker

    @property
    def gemini_cb(self) -> CircuitBreaker:
        return self.fallback.circuit_breaker
