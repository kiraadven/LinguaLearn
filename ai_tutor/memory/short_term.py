"""
Short-term in-session memory.
Lives only for the duration of one WebSocket session.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

MAX_TURNS = 20


@dataclass
class ConversationTurn:
    role: str          # "teacher" or "student"
    text: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)  # action, tool_calls, etc.


class ShortTermMemory:
    """
    In-session context: conversation history, teaching progress, errors, notes.
    Cleared when the session ends (data is flushed to CourseMemory).
    """

    def __init__(self) -> None:
        self._turns: list[ConversationTurn] = []
        self.current_sentence_index: int = -1   # -1 = intro phase
        self.phase: str = "intro"               # intro | teach | review | end
        self.sentences_covered: list[int] = []
        self.errors_this_session: list[dict[str, Any]] = []
        self.attention_signals: list[float] = []  # 0.0 (distracted) – 1.0 (focused)
        self.shadow_requests: int = 0
        self.session_notes: list[str] = []

    # ── Conversation ──────────────────────────────────────────────────────────

    def add_turn(self, role: str, text: str, metadata: dict | None = None) -> None:
        self._turns.append(
            ConversationTurn(role=role, text=text, metadata=metadata or {})
        )
        if len(self._turns) > MAX_TURNS:
            self._turns = self._turns[-MAX_TURNS:]

    def recent_turns(self, n: int = 6) -> list[ConversationTurn]:
        return self._turns[-n:]

    def format_for_prompt(self, n: int = 6) -> str:
        lines: list[str] = []
        for t in self.recent_turns(n):
            speaker = "老师" if t.role == "teacher" else "学生"
            lines.append(f"{speaker}：{t.text}")
        return "\n".join(lines)

    # ── Progress ──────────────────────────────────────────────────────────────

    def mark_sentence_done(self, index: int) -> None:
        if index not in self.sentences_covered:
            self.sentences_covered.append(index)
        self.current_sentence_index = index

    # ── Errors ────────────────────────────────────────────────────────────────

    def record_error(self, error_type: str, detail: str, sentence_index: int) -> None:
        self.errors_this_session.append({
            "type": error_type,
            "detail": detail,
            "sentence_index": sentence_index,
            "turn": len(self._turns),
        })

    # ── Attention ─────────────────────────────────────────────────────────────

    def record_attention(self, level: float) -> None:
        """Record attention signal 0.0–1.0."""
        self.attention_signals.append(max(0.0, min(1.0, level)))

    @property
    def avg_attention(self) -> float:
        if not self.attention_signals:
            return 1.0
        return sum(self.attention_signals) / len(self.attention_signals)

    # ── Dump for persistence ──────────────────────────────────────────────────

    def to_session_data(self) -> dict:
        return {
            "sentences_covered": self.sentences_covered,
            "errors": self.errors_this_session,
            "attention_avg": self.avg_attention,
            "shadow_requests": self.shadow_requests,
            "turn_count": len(self._turns),
            "notes": self.session_notes,
        }
