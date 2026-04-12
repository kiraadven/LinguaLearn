from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import torch


@dataclass
class VADResult:
    is_speech: bool
    speech_start: bool
    speech_end: bool
    probability: float


_SILERO_MODEL = None
_SILERO_LOAD_FAILED = False


def _get_silero_model():
    global _SILERO_MODEL, _SILERO_LOAD_FAILED
    if _SILERO_MODEL is not None:
        return _SILERO_MODEL
    if _SILERO_LOAD_FAILED:
        return None

    try:
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
        )
        _SILERO_MODEL = model
        return model
    except Exception as exc:
        _SILERO_LOAD_FAILED = True
        logging.warning("Silero VAD unavailable, fallback to energy VAD: %s", exc)
        return None


class SileroVAD:
    """Silero VAD v5 wrapper for 16kHz mono PCM frames."""

    def __init__(self, threshold: float = 0.5, min_silence_ms: int = 300) -> None:
        self.model = _get_silero_model()
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self.sample_rate = 16000

        self._is_speech = False
        self._silence_frames = 0
        self._speech_frames = 0

    def process(self, pcm_frame: bytes) -> VADResult:
        audio = np.frombuffer(pcm_frame, dtype=np.int16).astype(np.float32) / 32768.0
        if self.model is None:
            # Fallback: use simple energy as pseudo probability.
            rms = float(np.sqrt(np.mean(np.square(audio))) if audio.size else 0.0)
            prob = min(1.0, rms * 8.0)
        else:
            tensor = torch.from_numpy(audio)
            prob = float(self.model(tensor, self.sample_rate).item())

        speech_detected = prob > self.threshold
        speech_start = False
        speech_end = False

        if speech_detected:
            self._silence_frames = 0
            self._speech_frames += 1
            if not self._is_speech and self._speech_frames >= 3:
                self._is_speech = True
                speech_start = True
        else:
            self._speech_frames = 0
            self._silence_frames += 1
            silence_ms = self._silence_frames * 32
            if self._is_speech and silence_ms >= self.min_silence_ms:
                self._is_speech = False
                speech_end = True

        return VADResult(
            is_speech=self._is_speech,
            speech_start=speech_start,
            speech_end=speech_end,
            probability=prob,
        )

    def reset(self) -> None:
        if self.model is not None:
            self.model.reset_states()
        self._is_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
