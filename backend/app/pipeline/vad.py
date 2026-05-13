"""Silero VAD wrapper — voice activity detection."""
from __future__ import annotations

import structlog

from app.config import settings

log = structlog.get_logger()

_model = None
_get_speech_timestamps = None


def _load_model():
    global _model, _get_speech_timestamps
    if _model is not None:
        return
    try:
        import torch

        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        _model = model
        _get_speech_timestamps = utils[0]  # get_speech_timestamps
        log.info("silero_vad_loaded")
    except Exception as exc:
        log.warning("silero_vad_load_failed", error=str(exc))
        _model = None


class SileroVAD:
    def __init__(self) -> None:
        _load_model()

    def is_speech(self, audio_chunk_pcm: bytes, sample_rate: int = 16000) -> bool:
        """Return True if the PCM chunk contains speech above VAD_THRESHOLD."""
        if _model is None:
            # Fallback: assume speech if we have audio (graceful degradation)
            return len(audio_chunk_pcm) > 0

        try:
            import torch

            audio_tensor = torch.frombuffer(audio_chunk_pcm, dtype=torch.int16).float() / 32768.0
            if audio_tensor.numel() == 0:
                return False
            confidence = _model(audio_tensor, sample_rate).item()
            return confidence > settings.VAD_THRESHOLD
        except Exception as exc:
            log.warning("vad_inference_failed", error=str(exc))
            return True  # assume speech on error
