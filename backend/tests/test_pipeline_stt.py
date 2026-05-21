"""Tests for SarvamSTT — success, CB trigger, error handling."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.pipeline.circuit_breaker import CircuitState
from app.pipeline.stt import SarvamSTT, STTResult


@pytest.mark.asyncio
async def test_transcribe_success(mock_sarvam_stt):
    stt = SarvamSTT()
    result = await stt.transcribe(b"fake_wav", language_code="hi-IN", call_id="test-1")
    assert isinstance(result, STTResult)
    assert result.transcript == "यह एक टेस्ट ट्रांसक्रिप्ट है"
    assert result.language_code == "hi-IN"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_transcribe_records_success_in_cb(mock_sarvam_stt):
    stt = SarvamSTT()
    await stt.transcribe(b"fake_wav", call_id="test-2")
    assert stt.circuit_breaker.state == CircuitState.HEALTHY
    assert stt.circuit_breaker.consecutive_errors == 0


@pytest.mark.asyncio
async def test_transcribe_failure_increments_cb(monkeypatch):
    from unittest.mock import AsyncMock
    mock_client = MagicMock()
    mock_client.speech_to_text.transcribe = AsyncMock(side_effect=RuntimeError("api timeout"))
    monkeypatch.setattr("sarvamai.AsyncSarvamAI", lambda **kwargs: mock_client)

    stt = SarvamSTT()
    with pytest.raises(Exception):
        await stt.transcribe(b"fake_wav", call_id="fail-1")
    assert stt.circuit_breaker.consecutive_errors == 1


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open(mock_sarvam_stt):
    stt = SarvamSTT()
    stt.circuit_breaker.state = CircuitState.COOLING_DOWN
    from datetime import datetime, timedelta
    stt.circuit_breaker.cooling_until = datetime.utcnow() + timedelta(seconds=60)

    with pytest.raises(RuntimeError, match="circuit breaker is open"):
        await stt.transcribe(b"fake_wav", call_id="blocked-1")


@pytest.mark.asyncio
async def test_language_fallback_uses_request_language(monkeypatch):
    """If STT response has no language_code, fall back to requested language."""
    fake_response = MagicMock()
    fake_response.transcript = "hello"
    fake_response.language_code = None
    fake_response.time_taken = 0.05

    from unittest.mock import AsyncMock
    mock_client = MagicMock()
    mock_client.speech_to_text.transcribe = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("sarvamai.AsyncSarvamAI", lambda **kwargs: mock_client)

    stt = SarvamSTT()
    result = await stt.transcribe(b"fake_wav", language_code="en-IN", call_id="lang-test")
    assert result.language_code == "en-IN"
