"""Tests for SarvamTTS and split_into_sentences."""
from __future__ import annotations

import pytest

from app.pipeline.tts import SarvamTTS, TTSResult, split_into_sentences
from app.pipeline.circuit_breaker import CircuitState


# ── split_into_sentences ──────────────────────────────────────────────────────

def test_split_hindi_danda():
    text = "नमस्ते। आपका क्लेम दर्ज हो गया। धन्यवाद।"
    sentences = split_into_sentences(text, "hi-IN")
    assert len(sentences) == 3
    assert "नमस्ते" in sentences[0]


def test_split_english_punctuation():
    sentences = split_into_sentences("Hello. How are you? I'm fine!", "en-IN")
    assert len(sentences) == 3


def test_split_long_sentence_on_comma():
    long_text = "A" * 210 + ", " + "B" * 50
    sentences = split_into_sentences(long_text, "en-IN")
    assert all(len(s) <= 210 for s in sentences)


def test_split_empty_returns_original():
    sentences = split_into_sentences("", "hi-IN")
    assert sentences == [""]


def test_split_no_punctuation_returns_whole():
    text = "No punctuation here at all"
    sentences = split_into_sentences(text, "en-IN")
    assert sentences == [text]


# ── SarvamTTS.synthesize_parallel ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_parallel_success(mock_sarvam_tts):
    tts = SarvamTTS()
    result = await tts.synthesize_parallel(
        ["Hello", "How are you"], language_code="en-IN", call_id="tts-1"
    )
    assert isinstance(result, TTSResult)
    assert result.sentence_count == 2
    assert len(result.audio_chunks) == 2
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_synthesize_parallel_empty_input(mock_sarvam_tts):
    tts = SarvamTTS()
    result = await tts.synthesize_parallel([], language_code="hi-IN", call_id="tts-empty")
    assert result.sentence_count == 0
    assert result.audio_chunks == []


@pytest.mark.asyncio
async def test_synthesize_parallel_cb_open_returns_silence(mock_sarvam_tts):
    from datetime import datetime, timedelta
    tts = SarvamTTS()
    tts.circuit_breaker.state = CircuitState.COOLING_DOWN
    tts.circuit_breaker.cooling_until = datetime.utcnow() + timedelta(seconds=60)

    result = await tts.synthesize_parallel(["Hello", "World"], language_code="en-IN", call_id="cb-test")
    assert len(result.audio_chunks) == 2
    # All chunks should be silence (non-empty bytes)
    assert all(isinstance(c, bytes) and len(c) > 0 for c in result.audio_chunks)


@pytest.mark.asyncio
async def test_synthesize_parallel_partial_failure(mock_sarvam_tts):
    """If one sentence fails, that slot gets silence; others succeed."""
    call_count = 0

    async def sometimes_fail(text, target_language_code, speaker, model):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("network error")
        import base64
        resp = type("R", (), {"audios": [base64.b64encode(b"\x00" * 50).decode()]})()
        return resp

    tts = SarvamTTS()
    tts.async_client.text_to_speech.convert = sometimes_fail  # type: ignore

    result = await tts.synthesize_parallel(
        ["sentence one", "sentence two", "sentence three"],
        language_code="en-IN",
        call_id="partial",
    )
    assert len(result.audio_chunks) == 3
