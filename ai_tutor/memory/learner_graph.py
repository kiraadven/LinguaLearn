"""
LearnerGraph: personalized intelligence graph built up over all sessions.
Tracks vocabulary mastery, grammar confidence, interests, and learning style.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class LearnerGraph:
    learner_id: str
    # Word → mastery score 0.0–1.0
    vocab_mastery: dict[str, float] = field(default_factory=dict)
    # Grammar point → confidence 0.0–1.0
    grammar_confidence: dict[str, float] = field(default_factory=dict)
    # Free-form interest tags extracted from chat
    interests: list[str] = field(default_factory=list)
    # Learning behavior preferences
    learning_style: dict[str, str] = field(default_factory=dict)
    # Factual info discovered about the user during global chat
    chat_insights: dict[str, str] = field(default_factory=dict)
    # Derived aggregates
    weak_areas: list[str] = field(default_factory=list)
    strong_areas: list[str] = field(default_factory=list)

    # ── Serialization ──────────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps({
            "vocab_mastery": self.vocab_mastery,
            "grammar_confidence": self.grammar_confidence,
            "interests": self.interests,
            "learning_style": self.learning_style,
            "chat_insights": self.chat_insights,
            "weak_areas": self.weak_areas,
            "strong_areas": self.strong_areas,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, learner_id: str, data: dict) -> "LearnerGraph":
        return cls(
            learner_id=learner_id,
            vocab_mastery=data.get("vocab_mastery", {}),
            grammar_confidence=data.get("grammar_confidence", {}),
            interests=data.get("interests", []),
            learning_style=data.get("learning_style", {}),
            chat_insights=data.get("chat_insights", {}),
            weak_areas=data.get("weak_areas", []),
            strong_areas=data.get("strong_areas", []),
        )

    # ── Updates ───────────────────────────────────────────────────────────────

    def update_vocab(self, word: str, mastery_delta: float) -> None:
        current = self.vocab_mastery.get(word, 0.0)
        self.vocab_mastery[word] = max(0.0, min(1.0, current + mastery_delta))
        self._refresh_areas()

    def update_grammar(self, point: str, confidence_delta: float) -> None:
        current = self.grammar_confidence.get(point, 0.0)
        self.grammar_confidence[point] = max(0.0, min(1.0, current + confidence_delta))
        self._refresh_areas()

    def add_interest(self, tag: str) -> None:
        tag = tag.strip()
        if tag and tag not in self.interests:
            self.interests.append(tag)

    def add_chat_insight(self, key: str, value: str) -> None:
        self.chat_insights[key] = value

    def _refresh_areas(self) -> None:
        """Recompute weak/strong areas from current mastery data."""
        all_vocab = [(w, m) for w, m in self.vocab_mastery.items()]
        self.weak_areas = [w for w, m in all_vocab if m < 0.4][:5]
        self.strong_areas = [w for w, m in all_vocab if m >= 0.8][:5]

    # ── Prompt summary ────────────────────────────────────────────────────────

    def to_prompt_summary(self) -> str:
        parts: list[str] = []

        if self.interests:
            parts.append(f"兴趣标签：{', '.join(self.interests[:5])}")

        if self.weak_areas:
            parts.append(f"词汇弱项：{', '.join(self.weak_areas)}")

        if self.strong_areas:
            parts.append(f"词汇强项：{', '.join(self.strong_areas)}")

        weak_grammar = [p for p, c in self.grammar_confidence.items() if c < 0.4]
        if weak_grammar:
            parts.append(f"语法弱项：{', '.join(weak_grammar[:3])}")

        if self.learning_style:
            style_parts = [f"{k}={v}" for k, v in self.learning_style.items()]
            parts.append(f"学习风格：{', '.join(style_parts)}")

        if self.chat_insights:
            insight_parts = [f"{k}: {v}" for k, v in list(self.chat_insights.items())[:3]]
            parts.append(f"个人信息：{'; '.join(insight_parts)}")

        return "\n".join(parts) if parts else "（暂无学习者画像数据）"
