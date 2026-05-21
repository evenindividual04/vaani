"""Pipeline orchestrator — chains STT → LLM → TTS and records all metrics."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import structlog

from app.config import settings
from app.pipeline.llm import LLMResult, LLMRouter
from app.pipeline.metrics import record_pipeline_turn
from app.pipeline.stt import STTResult, SarvamSTT
from app.pipeline.tts import SarvamTTS, split_into_sentences

log = structlog.get_logger()


@dataclass
class PipelineTurnResult:
    transcript: str
    response_text: str
    audio_chunks: list[bytes]
    stt_ms: float
    llm_ms: float
    llm_ttft_ms: float
    tts_ms: float
    total_ms: float
    fallback_triggered: bool
    stt_provider: str = "sarvam"
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    tts_provider: str = "sarvam"
    language: str = "hi-IN"


def _build_messages(
    conversation_history: list[dict],
    transcript: str,
    system_prompt: str,
) -> list[dict]:
    """Construct OpenAI-compatible messages list."""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for turn in conversation_history:
        role = "user" if turn.get("speaker") == "user" else "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": transcript})
    return messages


class PipelineOrchestrator:
    def __init__(self) -> None:
        self.stt = SarvamSTT()
        self.llm = LLMRouter()
        self.tts = SarvamTTS()

    async def run_turn(
        self,
        audio_wav: bytes | None,
        text_input: str | None,
        conversation_history: list[dict],
        call_id: str,
        language: str,
        system_prompt: str,
        channel: str = "web",
    ) -> PipelineTurnResult:
        """
        Full STT → LLM → TTS pipeline for one conversational turn.

        audio_wav:  WAV bytes for voice channels; None for text-only (WhatsApp)
        text_input: pre-transcribed text for text channels; None for voice
        """
        start = time.perf_counter()

        # ── STT ──────────────────────────────────────────────────────────────
        transcript = text_input or ""
        stt_ms = 0.0
        stt_provider = "none"
        detected_language = language

        if audio_wav is not None:
            stt_result: STTResult = await self.stt.transcribe(
                audio_wav, language, channel, call_id
            )
            transcript = stt_result.transcript
            stt_ms = stt_result.latency_ms
            stt_provider = "sarvam"
            detected_language = stt_result.language_code

        # ── LLM ──────────────────────────────────────────────────────────────
        messages = _build_messages(conversation_history, transcript, system_prompt)
        llm_result: LLMResult = await self.llm.complete(messages, call_id, "conversation")

        # ── TTS ──────────────────────────────────────────────────────────────
        tts_ms = 0.0
        audio_chunks: list[bytes] = []
        tts_provider = "none"

        if audio_wav is not None:  # voice channel — need audio response
            sentences = split_into_sentences(llm_result.text, detected_language)
            tts_result = await self.tts.synthesize_parallel(sentences, detected_language, call_id)
            audio_chunks = tts_result.audio_chunks
            tts_ms = tts_result.latency_ms
            tts_provider = "sarvam"

        total_ms = (time.perf_counter() - start) * 1000

        # ── Metrics ──────────────────────────────────────────────────────────
        record_pipeline_turn(
            channel=channel,
            language=detected_language,
            stt_ms=stt_ms,
            llm_ms=llm_result.latency_ms,
            llm_ttft_ms=llm_result.ttft_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
            stt_provider=stt_provider,
            llm_provider=llm_result.provider,
            llm_model=llm_result.model,
            tts_provider=tts_provider,
            fallback_triggered=llm_result.fallback_used,
        )

        log.info(
            "pipeline_turn_complete",
            call_id=call_id,
            channel=channel,
            stt_ms=round(stt_ms, 1),
            llm_ms=round(llm_result.latency_ms, 1),
            tts_ms=round(tts_ms, 1),
            total_ms=round(total_ms, 1),
            fallback=llm_result.fallback_used,
        )

        return PipelineTurnResult(
            transcript=transcript,
            response_text=llm_result.text,
            audio_chunks=audio_chunks,
            stt_ms=stt_ms,
            llm_ms=llm_result.latency_ms,
            llm_ttft_ms=llm_result.ttft_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
            fallback_triggered=llm_result.fallback_used,
            stt_provider=stt_provider,
            llm_provider=llm_result.provider,
            llm_model=llm_result.model,
            tts_provider=tts_provider,
            language=detected_language,
        )

    async def run_turn_streaming(
        self,
        audio_wav: bytes | None,
        text_input: str | None,
        conversation_history: list[dict],
        call_id: str,
        language: str,
        system_prompt: str,
        channel: str = "web",
    ):
        """
        Streaming STT → LLM → TTS pipeline.

        Yields bytes (audio chunks) as each sentence's TTS completes, then
        yields a final PipelineTurnResult with all metrics. This gets first
        audio to the caller ~(LLM TTFT + one sentence TTS) earlier than batch.
        """
        start = time.perf_counter()

        # STT is inherently batch
        transcript = text_input or ""
        stt_ms = 0.0
        stt_provider = "none"
        detected_language = language

        if audio_wav is not None:
            stt_result: STTResult = await self.stt.transcribe(
                audio_wav, language, channel, call_id
            )
            transcript = stt_result.transcript
            stt_ms = stt_result.latency_ms
            stt_provider = "sarvam"
            detected_language = stt_result.language_code

        messages = _build_messages(conversation_history, transcript, system_prompt)

        sentences: list[str] = []
        audio_chunks: list[bytes] = []
        tts_ms = 0.0
        tts_provider = "none"
        llm_start = time.perf_counter()

        if audio_wav is not None:
            async for sentence in self.llm.stream_sentences(messages, call_id):
                sentences.append(sentence)
                tts_chunk_start = time.perf_counter()
                chunk = await self.tts.synthesize_one_async(sentence, detected_language)
                tts_ms += (time.perf_counter() - tts_chunk_start) * 1000
                audio_chunks.append(chunk)
                tts_provider = "sarvam"
                yield chunk
        else:
            llm_result = await self.llm.complete(messages, call_id, "conversation")
            sentences = [llm_result.text]

        llm_ms = (time.perf_counter() - llm_start) * 1000
        total_ms = (time.perf_counter() - start) * 1000
        response_text = " ".join(sentences)

        record_pipeline_turn(
            channel=channel,
            language=detected_language,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            llm_ttft_ms=0.0,  # not tracked per-token in streaming path
            tts_ms=tts_ms,
            total_ms=total_ms,
            stt_provider=stt_provider,
            llm_provider="groq",
            llm_model=settings.GROQ_MODEL,
            tts_provider=tts_provider,
            fallback_triggered=False,
        )

        log.info(
            "pipeline_streaming_complete",
            call_id=call_id,
            sentences=len(sentences),
            stt_ms=round(stt_ms, 1),
            llm_ms=round(llm_ms, 1),
            tts_ms=round(tts_ms, 1),
            total_ms=round(total_ms, 1),
        )

        yield PipelineTurnResult(
            transcript=transcript,
            response_text=response_text,
            audio_chunks=audio_chunks,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            llm_ttft_ms=0.0,
            tts_ms=tts_ms,
            total_ms=total_ms,
            fallback_triggered=False,
            stt_provider=stt_provider,
            llm_provider="groq",
            llm_model=settings.GROQ_MODEL,
            tts_provider=tts_provider,
            language=detected_language,
        )
