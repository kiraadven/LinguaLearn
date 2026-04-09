"""
Persona Maintenance System.

Maintains teacher persona consistency across an entire classroom session.
Combines fixed identity traits with dynamic emotional state and per-turn
delivery style modifiers to produce final voice model parameters.

Key components:
- PersonaState:   Fixed identity + personality + dynamic emotion
- PersonaManager: Assembles voice params, tracks consistency
- DELIVERY_STYLE_MAP: 10 styles -> numeric parameter modifiers
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import copy


# ---------------------------------------------------------------------------
# Delivery Style -> Voice Parameter Modifiers
# ---------------------------------------------------------------------------

DELIVERY_STYLE_MAP: dict[str, dict[str, float | str]] = {
    "neutral_teach": {
        "speed_modifier": 1.0,
        "pause_tendency_modifier": 0.0,
        "emphasis_modifier": 0.0,
        "emotion_amplitude_modifier": 0.0,
        "intonation_variability_modifier": 0.0,
        "backchannel_frequency_modifier": 0.0,
        "sentence_final_pattern": "falling",
    },
    "warm_encourage": {
        "speed_modifier": 0.95,
        "pause_tendency_modifier": +0.1,
        "emphasis_modifier": +0.15,
        "emotion_amplitude_modifier": +0.2,
        "intonation_variability_modifier": +0.15,
        "backchannel_frequency_modifier": +0.1,
        "sentence_final_pattern": "rising",
    },
    "gentle_corrective": {
        "speed_modifier": 0.9,
        "pause_tendency_modifier": +0.15,
        "emphasis_modifier": +0.1,
        "emotion_amplitude_modifier": +0.1,
        "intonation_variability_modifier": +0.05,
        "backchannel_frequency_modifier": -0.05,
        "sentence_final_pattern": "falling",
    },
    "firm_corrective": {
        "speed_modifier": 0.85,
        "pause_tendency_modifier": +0.2,
        "emphasis_modifier": +0.25,
        "emotion_amplitude_modifier": +0.05,
        "intonation_variability_modifier": -0.1,
        "backchannel_frequency_modifier": -0.1,
        "sentence_final_pattern": "falling",
    },
    "slow_repair": {
        "speed_modifier": 0.75,
        "pause_tendency_modifier": +0.3,
        "emphasis_modifier": +0.2,
        "emotion_amplitude_modifier": 0.0,
        "intonation_variability_modifier": -0.05,
        "backchannel_frequency_modifier": 0.0,
        "sentence_final_pattern": "sustained",
    },
    "energetic_advance": {
        "speed_modifier": 1.1,
        "pause_tendency_modifier": -0.1,
        "emphasis_modifier": +0.1,
        "emotion_amplitude_modifier": +0.15,
        "intonation_variability_modifier": +0.2,
        "backchannel_frequency_modifier": +0.05,
        "sentence_final_pattern": "rising",
    },
    "curious_probe": {
        "speed_modifier": 0.95,
        "pause_tendency_modifier": +0.2,
        "emphasis_modifier": +0.05,
        "emotion_amplitude_modifier": +0.1,
        "intonation_variability_modifier": +0.25,
        "backchannel_frequency_modifier": 0.0,
        "sentence_final_pattern": "rising",
    },
    "surprised_react": {
        "speed_modifier": 1.05,
        "pause_tendency_modifier": 0.0,
        "emphasis_modifier": +0.3,
        "emotion_amplitude_modifier": +0.35,
        "intonation_variability_modifier": +0.3,
        "backchannel_frequency_modifier": +0.15,
        "sentence_final_pattern": "rising",
    },
    "celebrate_success": {
        "speed_modifier": 1.05,
        "pause_tendency_modifier": -0.05,
        "emphasis_modifier": +0.2,
        "emotion_amplitude_modifier": +0.3,
        "intonation_variability_modifier": +0.2,
        "backchannel_frequency_modifier": +0.1,
        "sentence_final_pattern": "falling",
    },
    "calm_reset": {
        "speed_modifier": 0.85,
        "pause_tendency_modifier": +0.25,
        "emphasis_modifier": -0.1,
        "emotion_amplitude_modifier": -0.1,
        "intonation_variability_modifier": -0.15,
        "backchannel_frequency_modifier": 0.0,
        "sentence_final_pattern": "falling",
    },
}


# ---------------------------------------------------------------------------
# Persona State
# ---------------------------------------------------------------------------

@dataclass
class PersonaState:
    """Maintained across the entire session. Updated slowly."""

    persona_id: str = ""

    # --- Core voice identity (fixed within session) ---
    voice_identity_embedding: list[float] = field(default_factory=list)
    gender: str = "female"
    age_range: str = "young_adult"      # young_adult | middle_aged | mature
    accent: str = "neutral"
    base_speaking_rate: float = 1.0

    # --- Personality traits (fixed within session) ---
    warmth: float = 0.6
    formality: float = 0.4
    humor: float = 0.3
    patience: float = 0.7
    energy: float = 0.6

    # --- Dynamic state (updated every few turns) ---
    current_emotion: str = "neutral"
    # neutral | encouraging | concerned | excited | thoughtful | firm
    emotion_intensity: float = 0.3
    energy_level: float = 0.6           # degrades slightly over long sessions
    rapport_level: float = 0.3          # increases as session progresses

    # --- Consistency tracking ---
    phrases_used_this_session: list[str] = field(default_factory=list)
    last_backchannel_type: str = ""
    turns_since_last_humor: int = 0
    total_turns: int = 0


# ---------------------------------------------------------------------------
# Persona Manager
# ---------------------------------------------------------------------------

class PersonaManager:
    """Maintains persona consistency across a session."""

    def __init__(self, persona_config: dict):
        self._state = self._init_from_config(persona_config)

    @property
    def state(self) -> PersonaState:
        return self._state

    def get_voice_params(self, delivery_style: str, assessment: dict) -> dict:
        """Combine fixed persona with dynamic delivery style to produce
        final voice model parameters for this turn.

        Returns dict of all VoiceModelInput persona/delivery fields.
        """
        s = self._state

        # Start from persona base traits
        params = {
            "persona_warmth": s.warmth,
            "persona_formality": s.formality,
            "persona_humor": s.humor,
            "persona_patience": s.patience,
            "persona_energy": s.energy_level,  # use dynamic, not base
            "persona_gender": s.gender,
            "persona_age_range": s.age_range,
        }

        # Apply delivery style modifiers
        style_mods = DELIVERY_STYLE_MAP.get(delivery_style, DELIVERY_STYLE_MAP["neutral_teach"])

        params["speaking_speed"] = s.base_speaking_rate * style_mods["speed_modifier"]
        params["pause_tendency"] = self._clamp(0.3 + style_mods["pause_tendency_modifier"])
        params["emphasis_intensity"] = self._clamp(0.3 + style_mods["emphasis_modifier"])
        params["emotion_amplitude"] = self._clamp(
            s.emotion_intensity + style_mods["emotion_amplitude_modifier"]
        )
        params["intonation_variability"] = self._clamp(
            0.3 + style_mods["intonation_variability_modifier"]
        )
        params["backchannel_frequency"] = self._clamp(
            0.2 + style_mods["backchannel_frequency_modifier"]
        )
        params["sentence_final_pattern"] = style_mods["sentence_final_pattern"]

        # Dynamic adjustments based on student state
        fatigue = assessment.get("fatigue", 0.0)
        engagement = assessment.get("engagement", 0.5)

        if fatigue > 0.6:
            # Slow down, more pauses, calmer
            params["speaking_speed"] *= 0.9
            params["pause_tendency"] = min(1.0, params["pause_tendency"] + 0.1)

        if engagement < 0.3:
            # More energy, more intonation variety
            params["persona_energy"] = min(1.0, params["persona_energy"] + 0.15)
            params["intonation_variability"] = min(1.0, params["intonation_variability"] + 0.1)

        # Rapport adjustment: higher rapport -> slightly warmer
        if s.rapport_level > 0.5:
            params["persona_warmth"] = min(1.0, params["persona_warmth"] + 0.1)
            params["backchannel_frequency"] = min(1.0, params["backchannel_frequency"] + 0.05)

        return params

    def update_dynamic_state(self, turn_result: dict, assessment: dict) -> None:
        """Update emotion, energy, rapport after each turn."""
        s = self._state
        s.total_turns += 1

        # Energy degrades over time
        s.energy_level = max(0.3, s.energy_level - 0.005)

        # Rapport increases with successful interactions
        if assessment.get("is_correct"):
            s.rapport_level = min(1.0, s.rapport_level + 0.03)

        # Update emotion based on context
        action = turn_result.get("policy_action", "")
        if action in ("encourage", "celebrate_success"):
            s.current_emotion = "encouraging"
            s.emotion_intensity = min(1.0, s.emotion_intensity + 0.1)
        elif action in ("direct_correct", "re_explain_simplify"):
            s.current_emotion = "concerned"
            s.emotion_intensity = 0.4
        elif action == "advance":
            s.current_emotion = "excited"
            s.emotion_intensity = 0.5
        else:
            # Decay toward neutral
            s.emotion_intensity = max(0.2, s.emotion_intensity - 0.05)
            if s.emotion_intensity < 0.25:
                s.current_emotion = "neutral"

        # Humor tracking
        s.turns_since_last_humor += 1

    def get_cross_session_identity(self) -> dict:
        """Return fixed identity for cross-session persona consistency.
        Stored in LearnerMemory so same student always hears same teacher voice."""
        s = self._state
        return {
            "persona_id": s.persona_id,
            "voice_identity_embedding": s.voice_identity_embedding,
            "gender": s.gender,
            "age_range": s.age_range,
            "accent": s.accent,
            "base_speaking_rate": s.base_speaking_rate,
            "warmth": s.warmth,
            "formality": s.formality,
            "humor": s.humor,
            "patience": s.patience,
            "energy": s.energy,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _init_from_config(config: dict) -> PersonaState:
        return PersonaState(
            persona_id=config.get("persona_id", "default_teacher"),
            voice_identity_embedding=config.get("voice_identity_embedding", []),
            gender=config.get("gender", "female"),
            age_range=config.get("age_range", "young_adult"),
            accent=config.get("accent", "neutral"),
            base_speaking_rate=config.get("base_speaking_rate", 1.0),
            warmth=config.get("warmth", 0.6),
            formality=config.get("formality", 0.4),
            humor=config.get("humor", 0.3),
            patience=config.get("patience", 0.7),
            energy=config.get("energy", 0.6),
            energy_level=config.get("energy", 0.6),
        )

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))
