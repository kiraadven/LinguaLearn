"""
Voice Schema - Data structures for the self-thinking voice model.

Re-exports VoiceModelInput from graph.schema (single source of truth)
and defines voice-specific types.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# VoiceModelInput is defined in graph.schema to keep the contract
# between graph/runtime and voice in one place.
from ..graph.schema import VoiceModelInput


@dataclass
class AudioOutput:
    """Output from voice model generation."""
    audio_bytes: bytes = b""
    sample_rate: int = 24000
    duration_ms: int = 0
    format: str = "pcm_16"        # pcm_16 | wav | opus
    streaming: bool = False
    chunk_index: int = 0
    total_chunks: int = 1


@dataclass
class VoiceGenerationRequest:
    """Complete request to the voice model or TTS fallback."""
    input: VoiceModelInput = field(default_factory=VoiceModelInput)
    use_fallback: bool = False
    fallback_text: Optional[str] = None
    stream: bool = True
    max_duration_ms: int = 15000
