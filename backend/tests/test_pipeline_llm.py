"""Tests for GroqLLM, GeminiLLM, and LLMRouter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.pipeline.circuit_breaker import CircuitState
from app.pipeline.llm import GroqLLM, GeminiLLM, LLMRouter, LLMResult


# ── GroqLLM ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_groq_complete_success(mock_groq):
    llm = GroqLLM()
    result = await llm.complete([{"role": "user", "content": "Hello"}], call_id="g-1")
    assert isinstance(result, LLMResult)
    assert result.text == "Mock agent response."
    assert result.fallback_used is False
    assert result.provider == "groq"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_groq_tracks_ttft(mock_groq):
    llm = GroqLLM()
    result = await llm.complete([{"role": "user", "content": "Test"}], call_id="ttft-1")
    # TTFT should be set (mock returns content on first chunk)
    assert result.ttft_ms >= 0


@pytest.mark.asyncio
async def test_groq_failure_increments_cb(monkeypatch):
    async def exploding_stream(*args, **kwargs):
        raise RuntimeError("groq down")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=exploding_stream)
    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: mock_client)

    llm = GroqLLM()
    with pytest.raises(RuntimeError):
        await llm.complete([{"role": "user", "content": "hi"}], call_id="err-1")
    assert llm.circuit_breaker.consecutive_errors == 1


@pytest.mark.asyncio
async def test_groq_cb_state_recorded_on_open(monkeypatch):
    async def always_fail(*args, **kwargs):
        raise RuntimeError("fail")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=always_fail)
    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: mock_client)

    llm = GroqLLM()
    llm.circuit_breaker.error_threshold = 1

    with pytest.raises(RuntimeError):
        await llm.complete([{"role": "user", "content": "x"}], call_id="open-1")
    assert llm.circuit_breaker.state == CircuitState.COOLING_DOWN


# ── GeminiLLM ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_complete_success(monkeypatch):
    fake_model = MagicMock()
    fake_model.generate_content_async = AsyncMock(
        return_value=type("R", (), {"text": "Gemini says hello"})()
    )

    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", lambda model: fake_model)

    llm = GeminiLLM()
    result = await llm.complete([{"role": "user", "content": "hi"}], call_id="gem-1")
    assert result.text == "Gemini says hello"
    assert result.fallback_used is True
    assert result.provider == "gemini"


# ── LLMRouter ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_router_uses_primary_when_healthy(mock_groq):
    router = LLMRouter()
    result = await router.complete([{"role": "user", "content": "hello"}], call_id="r-1")
    assert result.provider == "groq"
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_router_falls_back_when_primary_fails(monkeypatch):
    async def always_fail(*args, **kwargs):
        raise RuntimeError("groq down")

    groq_mock = MagicMock()
    groq_mock.chat.completions.create = AsyncMock(side_effect=always_fail)
    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: groq_mock)

    gemini_mock = MagicMock()
    gemini_mock.generate_content_async = AsyncMock(
        return_value=type("R", (), {"text": "fallback response"})()
    )
    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", lambda model: gemini_mock)

    router = LLMRouter()
    result = await router.complete([{"role": "user", "content": "hi"}], call_id="fb-1")
    assert result.provider == "gemini"
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_router_skips_primary_when_cb_open(mock_groq, monkeypatch):
    gemini_mock = MagicMock()
    gemini_mock.generate_content_async = AsyncMock(
        return_value=type("R", (), {"text": "gemini"})()
    )
    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", lambda model: gemini_mock)

    router = LLMRouter()
    # Force primary CB open
    from datetime import datetime, timedelta
    router.primary.circuit_breaker.state = CircuitState.COOLING_DOWN
    router.primary.circuit_breaker.cooling_until = datetime.utcnow() + timedelta(seconds=60)

    result = await router.complete([{"role": "user", "content": "hi"}], call_id="skip-1")
    assert result.provider == "gemini"
