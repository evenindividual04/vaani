"""Audio utilities — μ-law ↔ PCM conversion, buffering, WAV handling per §9."""
import audioop
import base64
import io
import struct
import wave

import structlog

log = structlog.get_logger()

_SILENCE_CACHE: dict[int, bytes] = {}


def convert_twilio_chunk(b64_payload: str) -> bytes:
    """Convert a single Twilio μ-law chunk to 16-bit PCM at 8 kHz."""
    mulaw_bytes = base64.b64decode(b64_payload)
    return audioop.ulaw2lin(mulaw_bytes, 2)  # 2 = 16-bit


def upsample_to_16k(pcm_8k: bytes, state=None) -> tuple[bytes, object]:
    """Upsample 8 kHz PCM to 16 kHz; returns (pcm_16k, new_state)."""
    return audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, state)


def build_wav_bytes(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM in a WAV container for Sarvam STT."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit = 2 bytes
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data)
    return buf.getvalue()


def strip_wav_header(wav_bytes: bytes) -> bytes:
    """Extract raw PCM from a WAV container."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wav:
        return wav.readframes(wav.getnframes())


def generate_silence_wav(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """Generate a WAV file of silence — used for failed TTS sentence substitution."""
    if duration_ms in _SILENCE_CACHE:
        return _SILENCE_CACHE[duration_ms]
    num_samples = int(sample_rate * duration_ms / 1000)
    pcm_data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    result = build_wav_bytes(pcm_data, sample_rate)
    _SILENCE_CACHE[duration_ms] = result
    return result


async def send_audio_to_twilio(ws, stream_sid: str, wav_bytes: bytes) -> None:
    """Convert WAV back to μ-law and send to Twilio over WebSocket."""
    pcm_16k = strip_wav_header(wav_bytes)
    pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)
    mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)
    audio_b64 = base64.b64encode(mulaw_bytes).decode("utf-8")
    await ws.send_json(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": audio_b64},
        }
    )


class AudioBuffer:
    """Accumulates Twilio 20 ms PCM chunks; flushes on VAD silence or thresholds."""

    CHUNK_MS = 20
    FLUSH_MS = 300
    MAX_MS = 10000

    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.total_ms: int = 0
        self._upsample_state = None

    def add_twilio_chunk(self, b64_payload: str) -> bytes | None:
        """Accept a raw Twilio base64 μ-law payload; returns flushed WAV or None."""
        pcm_8k = convert_twilio_chunk(b64_payload)
        pcm_16k, self._upsample_state = upsample_to_16k(pcm_8k, self._upsample_state)
        return self._add_pcm(pcm_16k)

    def add_pcm(self, pcm_16k: bytes) -> bytes | None:
        """Accept 16 kHz PCM directly (browser channel)."""
        return self._add_pcm(pcm_16k)

    def _add_pcm(self, pcm_16k: bytes) -> bytes | None:
        self.chunks.append(pcm_16k)
        self.total_ms += self.CHUNK_MS
        if self.total_ms >= self.MAX_MS:
            return self.flush()
        return None

    def flush(self) -> bytes:
        audio = b"".join(self.chunks)
        self.chunks = []
        self.total_ms = 0
        return build_wav_bytes(audio)

    def should_flush_on_silence(self) -> bool:
        return self.total_ms >= self.FLUSH_MS

    def has_audio(self) -> bool:
        return len(self.chunks) > 0
