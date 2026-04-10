"""
VoiceDispatcher - Runtime voice generation router.

Routes between:
- Self-thinking voice model (95%+ of turns): context -> audio directly
- LLM + TTS fallback (<5%): text -> TTS audio

Handles persona parameter assembly, model invocation, and persona state updates.
"""

from __future__ import annotations
import logging
from typing import Optional

from ..graph.schema import VoiceModelInput
from .persona import PersonaManager

logger = logging.getLogger(__name__)


class VoiceDispatcher:

    def __init__(
        self,
        voice_model=None,       # SelfThinkingVoiceModel (when available)
        tts_fallback=None,      # TTSAdapter for LLM text fallback
        persona_manager: Optional[PersonaManager] = None,
    ):
        self._voice_model = voice_model
        self._tts_fallback = tts_fallback
        self._persona = persona_manager

    async def dispatch(
        self,
        graph_state: dict,
        policy_action: str,
        delivery_style: str,
        assessment: dict,
        memory_context: dict,
        fallback_text: Optional[str] = None,
    ) -> Optional[str]:
        """Generate audio for this turn.

        Normal flow (self-thinking model):
        1. Assemble persona + delivery params
        2. Build VoiceModelInput
        3. Generate audio
        4. Update persona dynamic state

        Exception fallback (LLM text -> TTS):
        1. If fallback_text provided from LLM supervisor
        2. Synthesize via TTS with persona params

        Returns:
            Audio URL/path string, or None if no voice system configured.
        """
        if self._persona is None:
            return None

        persona_params = self._persona.get_voice_params(delivery_style, assessment)

        # --- Exception fallback path ---
        if fallback_text is not None and self._tts_fallback is not None:
            logger.info(f"Voice fallback: using TTS for text={fallback_text[:50]}...")
            audio_url = await self._tts_fallback.synthesize(fallback_text, persona_params)
            self._persona.update_dynamic_state(
                {"policy_action": policy_action}, assessment,
            )
            return audio_url

        # --- Normal path: self-thinking voice model ---
        if self._voice_model is not None:
            voice_input = self._build_voice_input(
                graph_state, policy_action, delivery_style,
                assessment, memory_context, persona_params,
            )
            audio_url = await self._voice_model.generate(voice_input)
            self._persona.update_dynamic_state(
                {"policy_action": policy_action}, assessment,
            )
            return audio_url

        # No voice model available
        logger.debug("No voice model configured, skipping audio generation")
        return None

    def _build_voice_input(
        self,
        graph_state: dict,
        policy_action: str,
        delivery_style: str,
        assessment: dict,
        memory_context: dict,
        persona_params: dict,
    ) -> VoiceModelInput:
        """Assemble the complete VoiceModelInput from all sources."""
        voice_input = VoiceModelInput(
            # Graph state
            current_node_type=graph_state.get("node_type", ""),
            current_phase=graph_state.get("phase", ""),
            node_visit_count=graph_state.get("visit_count", 0),
            node_success_count=graph_state.get("success_count", 0),
            node_failure_count=graph_state.get("failure_count", 0),
            lesson_progress=graph_state.get("lesson_progress", 0.0),
            is_repair_mode=graph_state.get("is_repair_mode", False),

            # Policy decision
            policy_action=policy_action,
            tool_action=graph_state.get("tool_action"),
            delivery_style=delivery_style,

            # Student state
            student_error_type=assessment.get("error_type", ""),
            student_confidence=assessment.get("confidence", 0.5),
            student_fatigue=assessment.get("fatigue", 0.0),
            student_engagement=assessment.get("engagement", 0.5),
            student_lang_level=memory_context.get("student_lang_level", "B1"),
            consecutive_failures=assessment.get("consecutive_failures", 0),
            student_last_utterance_duration_ms=assessment.get("duration_ms", 0),
            student_silence_duration_ms=assessment.get("silence_before_ms", 0),

            # Persona parameters (from PersonaManager)
            persona_warmth=persona_params.get("persona_warmth", 0.5),
            persona_formality=persona_params.get("persona_formality", 0.5),
            persona_humor=persona_params.get("persona_humor", 0.3),
            persona_patience=persona_params.get("persona_patience", 0.7),
            persona_energy=persona_params.get("persona_energy", 0.6),
            persona_gender=persona_params.get("persona_gender", "female"),
            persona_age_range=persona_params.get("persona_age_range", "young_adult"),

            # Delivery style parameters (from PersonaManager)
            speaking_speed=persona_params.get("speaking_speed", 1.0),
            pause_tendency=persona_params.get("pause_tendency", 0.3),
            emphasis_intensity=persona_params.get("emphasis_intensity", 0.3),
            emotion_amplitude=persona_params.get("emotion_amplitude", 0.3),
            intonation_variability=persona_params.get("intonation_variability", 0.3),
            backchannel_frequency=persona_params.get("backchannel_frequency", 0.2),
            sentence_final_pattern=persona_params.get("sentence_final_pattern", "falling"),
        )
        return voice_input.apply_categorical_encodings()
