"""
AssessmentEngine - Evaluates student input on the hot path.

Heuristic-based, low-latency assessment. No LLM calls.
Produces a dict with: error_type, focus_skill, confidence, fatigue,
engagement, is_correct, is_silence, is_off_topic, error_severity.
"""

from __future__ import annotations
from typing import Optional

from ..graph.schema import LiveNode
from .memory import HotMemory


class AssessmentEngine:

    def evaluate(
        self,
        student_text: str,
        audio_features: dict,
        current_node: LiveNode,
        hot_memory: HotMemory,
    ) -> dict:
        """Evaluate student input against current node expectations.

        Returns assessment dict.
        """
        text = student_text.strip()

        # Silence detection
        if not text or len(text) < 2:
            return {
                "is_silence": True,
                "is_correct": False,
                "is_off_topic": False,
                "error_type": "",
                "focus_skill": "",
                "confidence": 0.0,
                "fatigue": self._estimate_fatigue(audio_features, hot_memory),
                "engagement": 0.2,
                "error_severity": 0.0,
            }

        # Basic heuristics
        focus_skill = current_node.learning_targets[0] if current_node.learning_targets else ""
        error_type = self._classify_error(text, current_node)
        is_correct = error_type == ""
        is_off_topic = self._detect_off_topic(text, current_node)

        confidence = self._estimate_confidence(text, audio_features)
        fatigue = self._estimate_fatigue(audio_features, hot_memory)
        engagement = self._estimate_engagement(text, audio_features, hot_memory)

        error_severity = 0.0
        if error_type:
            error_severity = 0.7 if "major" in error_type else 0.4

        return {
            "is_silence": False,
            "is_correct": is_correct,
            "is_off_topic": is_off_topic,
            "error_type": error_type,
            "focus_skill": focus_skill,
            "confidence": confidence,
            "fatigue": fatigue,
            "engagement": engagement,
            "error_severity": error_severity,
        }

    # ------------------------------------------------------------------
    # Heuristic classifiers (placeholder logic, to be refined)
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_error(text: str, node: LiveNode) -> str:
        """Simple heuristic error classification.
        Returns error_type string or empty string if correct."""
        text_lower = text.lower()

        # Tense errors
        tense_markers = ["yesterday", "last", "ago", "before"]
        present_verbs = ["go ", "eat ", "do ", "have ", "make "]
        if any(m in text_lower for m in tense_markers):
            if any(v in text_lower for v in present_verbs):
                return "tense_error"

        # Very short response when evidence is expected
        expected = node.expected_student_evidence
        if expected and len(text.split()) < 3:
            return "incomplete_response"

        return ""  # No error detected

    @staticmethod
    def _detect_off_topic(text: str, node: LiveNode) -> bool:
        """Detect if student response is off-topic."""
        # Simple: very long response with no overlap with learning targets
        if len(text.split()) > 30:
            targets = " ".join(node.learning_targets).lower()
            text_lower = text.lower()
            # Check for any keyword overlap
            target_words = set(targets.split())
            text_words = set(text_lower.split())
            if not target_words & text_words:
                return True
        return False

    @staticmethod
    def _estimate_confidence(text: str, audio_features: dict) -> float:
        """Estimate student confidence from text and audio."""
        confidence = 0.5

        # Longer, more detailed responses -> higher confidence
        word_count = len(text.split())
        if word_count > 10:
            confidence += 0.2
        elif word_count < 3:
            confidence -= 0.2

        # Hedging language -> lower confidence
        hedges = ["maybe", "i think", "not sure", "i guess", "probably"]
        if any(h in text.lower() for h in hedges):
            confidence -= 0.15

        # Audio features
        duration = audio_features.get("duration_ms", 0)
        latency = audio_features.get("latency_ms", 0)
        if latency > 3000:  # long pause before answering
            confidence -= 0.1
        if audio_features.get("self_correction_count", 0) > 0:
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _estimate_fatigue(audio_features: dict, hot: HotMemory) -> float:
        """Estimate student fatigue."""
        fatigue = 0.0

        # Turn count contributes to fatigue
        fatigue += hot.turn_number * 0.015

        # Long silence -> fatigue indicator
        silence = audio_features.get("silence_before_ms", 0)
        if silence > 5000:
            fatigue += 0.15

        return min(1.0, fatigue)

    @staticmethod
    def _estimate_engagement(text: str, audio_features: dict,
                             hot: HotMemory) -> float:
        """Estimate student engagement."""
        engagement = 0.5

        word_count = len(text.split())
        if word_count > 15:
            engagement += 0.2
        elif word_count < 3:
            engagement -= 0.2

        # Questions indicate engagement
        if "?" in text:
            engagement += 0.15

        return max(0.0, min(1.0, engagement))
