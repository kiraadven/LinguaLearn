"""
AttentionMonitor: detect learner attention level from multiple signals.

Signals:
  - audio_energy: how actively the student is speaking (0.0–1.0)
  - response_latency: time between teacher finishing and student starting to reply (seconds)
  - tab_switch: browser tab switched away (boolean event)
  - mouse_idle: mouse hasn't moved for N seconds (boolean event)
"""
from __future__ import annotations

import time
from enum import Enum


class AttentionLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DISTRACTED = "distracted"


class AttentionMonitor:
    """
    Maintains a rolling attention score from multiple weak signals.
    Score 0.0 = fully distracted, 1.0 = fully engaged.
    """

    def __init__(self) -> None:
        self._score: float = 1.0
        self._last_response_time: float = time.time()
        self._tab_switches: int = 0
        self._mouse_idles: int = 0
        self._total_signals: int = 0

    # ── Signal intake ─────────────────────────────────────────────────────────

    def record_audio_energy(self, energy: float) -> None:
        """energy: 0.0 (silent) – 1.0 (very active). Updates score smoothly."""
        # Low energy (student barely speaking) suggests disengagement
        target = 0.6 + energy * 0.4  # maps 0→0.6, 1→1.0
        self._update_score(target, weight=0.2)
        self._last_response_time = time.time()
        self._total_signals += 1

    def record_response_latency(self, latency_seconds: float) -> None:
        """Long latency before response → lower attention."""
        if latency_seconds < 3:
            target = 1.0
        elif latency_seconds < 8:
            target = 0.7
        elif latency_seconds < 15:
            target = 0.4
        else:
            target = 0.2
        self._update_score(target, weight=0.3)
        self._total_signals += 1

    def record_tab_switch(self) -> None:
        """Learner switched browser tab → strong negative signal."""
        self._tab_switches += 1
        self._update_score(0.1, weight=0.5)
        self._total_signals += 1

    def record_mouse_idle(self, idle_seconds: float) -> None:
        """Mouse idle for a long time → mild negative signal."""
        if idle_seconds > 30:
            self._update_score(0.3, weight=0.2)
            self._mouse_idles += 1
            self._total_signals += 1

    def record_student_response(self, text: str) -> None:
        """Any student text input = active engagement."""
        if text and len(text.strip()) > 2:
            target = 0.9 if len(text) > 20 else 0.75
            self._update_score(target, weight=0.3)
        self._total_signals += 1

    # ── Score management ──────────────────────────────────────────────────────

    def _update_score(self, target: float, weight: float) -> None:
        self._score = self._score * (1 - weight) + target * weight
        self._score = max(0.0, min(1.0, self._score))

    def decay(self, elapsed_seconds: float) -> None:
        """
        Apply passive decay if nothing has happened for a while.
        Call periodically (e.g., every 10s from the session loop).
        """
        if elapsed_seconds > 20:
            decay_amount = min(0.1, elapsed_seconds / 300)
            self._score = max(0.2, self._score - decay_amount)

    # ── Level ─────────────────────────────────────────────────────────────────

    @property
    def score(self) -> float:
        return self._score

    def get_level(self) -> AttentionLevel:
        if self._score >= 0.7:
            return AttentionLevel.HIGH
        elif self._score >= 0.45:
            return AttentionLevel.MEDIUM
        elif self._score >= 0.25:
            return AttentionLevel.LOW
        else:
            return AttentionLevel.DISTRACTED

    def should_intervene(self) -> bool:
        """True when the teacher should proactively re-engage the learner."""
        return self.get_level() in (AttentionLevel.LOW, AttentionLevel.DISTRACTED)

    def get_intervention_type(self) -> str:
        """Returns 'question' or 'culture_note' based on how distracted."""
        level = self.get_level()
        if level == AttentionLevel.DISTRACTED:
            return "culture_note"   # Show something interesting to hook back
        return "question"           # Ask a simple question

    def to_prompt_label(self) -> str:
        level = self.get_level()
        labels = {
            AttentionLevel.HIGH: "高（学习者积极参与）",
            AttentionLevel.MEDIUM: "中（正常状态）",
            AttentionLevel.LOW: "低（可能分心，请适时提问）",
            AttentionLevel.DISTRACTED: "极低（学习者分心，需要立即干预）",
        }
        return labels[level]
