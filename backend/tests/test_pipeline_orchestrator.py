"""Tests for PipelineOrchestrator.run_turn()."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline.orchestrator import PipelineOrchestrator, PipelineTurnResult


HISTORY = [
    {"speaker": "agent", "text": "Hello, please provide your policy number."},
]

SYSTEM_PROMPT = "You are a helpful insurance agent."


@pytest.mark.asyncio
async def test_full_pipeline_voice_turn(monkeypatch, mock_groq):
    """Full voice turn: STT → LLM → TTS. Patch STT and TTS at orchestrator call site
    to avoid sarvamai.SarvamAI being overwritten by two competing fixtures."""
    from unittest.mock import AsyncMock, MagicMock
    from app.pipeline.stt import STTResult
    from app.pipeline.tts import TTSResult

    stt_instance = MagicMock()
    stt_instance.transcribe = AsyncMock(
        return_value=STTResult(
            transcript="यह एक टेस्ट ट्रांसक्रिप्ट है",
            language_code="hi-IN",
            latency_ms=10.0,
        )
    )
    monkeypatch.setattr("app.pipeline.orchestrator.SarvamSTT", lambda: stt_instance)

    from app.pipeline.tts import TTSResult
    tts_instance = MagicMock()
    tts_instance.synthesize_parallel = AsyncMock(
        return_value=TTSResult(audio_chunks=[b"\x00" * 100], latency_ms=5.0, sentence_count=1)
    )
    monkeypatch.setattr("app.pipeline.orchestrator.SarvamTTS", lambda: tts_instance)

    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_turn(
        audio_wav=b"fake_wav_data",
        text_input=None,
        conversation_history=HISTORY,
        call_id="orch-1",
        language="hi-IN",
        system_prompt=SYSTEM_PROMPT,
        channel="web",
    )
    assert isinstance(result, PipelineTurnResult)
    assert result.transcript == "यह एक टेस्ट ट्रांसक्रिप्ट है"
    assert result.response_text == "Mock agent response."
    assert len(result.audio_chunks) > 0
    assert result.stt_ms >= 0
    assert result.llm_ms >= 0
    assert result.tts_ms >= 0
    assert result.total_ms >= 0
    assert result.stt_provider == "sarvam"
    assert result.tts_provider == "sarvam"


@pytest.mark.asyncio
async def test_text_only_skips_stt_and_tts(mock_groq):
    """WhatsApp / text channel: no STT, no TTS, just LLM."""
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_turn(
        audio_wav=None,
        text_input="Mera policy number SBI-1234 hai",
        conversation_history=HISTORY,
        call_id="text-1",
        language="hi-IN",
        system_prompt=SYSTEM_PROMPT,
        channel="whatsapp",
    )
    assert result.transcript == "Mera policy number SBI-1234 hai"
    assert result.stt_ms == 0.0
    assert result.tts_ms == 0.0
    assert result.audio_chunks == []
    assert result.stt_provider == "none"
    assert result.tts_provider == "none"


@pytest.mark.asyncio
async def test_stt_error_propagates(mock_groq, mock_sarvam_tts, monkeypatch):
    """If STT fails, the whole turn should raise."""
    def bad_transcribe(**kwargs):
        raise RuntimeError("STT service unavailable")

    mock_client = type("C", (), {
        "speech_to_text": type("S", (), {"transcribe": lambda self, **kw: (_ for _ in ()).throw(RuntimeError("STT service unavailable"))})()
    })()
    monkeypatch.setattr("sarvamai.SarvamAI", lambda **kwargs: mock_client)

    orchestrator = PipelineOrchestrator()
    with pytest.raises(Exception):
        await orchestrator.run_turn(
            audio_wav=b"bad_audio",
            text_input=None,
            conversation_history=[],
            call_id="err-stt",
            language="en-IN",
            system_prompt=SYSTEM_PROMPT,
        )


@pytest.mark.asyncio
async def test_fallback_recorded_in_result(monkeypatch, mock_sarvam_tts):
    """Verify fallback_triggered is True when LLMRouter uses Gemini."""
    from unittest.mock import AsyncMock
    from app.pipeline.stt import STTResult

    # Patch STT at orchestrator level to avoid sarvamai.AsyncSarvamAI conflict with mock_sarvam_tts
    stt_instance = MagicMock()
    stt_instance.transcribe = AsyncMock(
        return_value=STTResult(transcript="test audio", language_code="en-IN", latency_ms=10.0)
    )
    monkeypatch.setattr("app.pipeline.orchestrator.SarvamSTT", lambda: stt_instance)

    async def always_fail(*args, **kwargs):
        raise RuntimeError("groq down")

    groq_mock = MagicMock()
    groq_mock.chat.completions.create = AsyncMock(side_effect=always_fail)
    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: groq_mock)

    gemini_mock = MagicMock()
    gemini_mock.generate_content_async = AsyncMock(
        return_value=type("R", (), {"text": "Gemini fallback"})()
    )
    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", lambda model: gemini_mock)

    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_turn(
        audio_wav=b"fake_wav",
        text_input=None,
        conversation_history=[],
        call_id="fallback-1",
        language="en-IN",
        system_prompt=SYSTEM_PROMPT,
    )
    assert result.fallback_triggered is True
    assert result.llm_provider == "gemini"
