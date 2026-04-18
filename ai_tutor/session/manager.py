from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime

from ai_tutor.llm.client import ClaudeClient
from ai_tutor.llm.response_parser import ResponseParser
from ai_tutor.session.learner_profile import LearnerProfile, LearnerProfileStore
from ai_tutor.session.lesson_plan import LessonPlan, LessonPlanStore
from ai_tutor.session.prompt_builder import PromptBuilder


FAST_RESPONSES = {
    "correct_simple": ["Good!", "That's right!", "Exactly!", "很好!"],
    "encourage_retry": ["Almost!", "Try again!", "差一点!"],
    "greeting": ["Hi there!", "Hello!", "你好!"],
}


@dataclass
class Turn:
    student: str
    teacher: str
    action: str = "encourage"
    phase: str = "teach"


@dataclass
class SessionContext:
    lesson_id: str
    learner_id: str
    start_time: datetime
    target_language: str
    lesson_focus: str
    total_minutes: int

    current_phase: str = "opening"
    turns: list[Turn] = field(default_factory=list)
    covered_topics: list[str] = field(default_factory=list)
    vocab_introduced: dict[str, dict] = field(default_factory=dict)
    errors_this_session: list[dict] = field(default_factory=list)
    energy_level: float = 0.5

    def elapsed_minutes(self) -> int:
        return int((datetime.utcnow() - self.start_time).total_seconds() // 60)

    def to_prompt_context(self) -> str:
        return (
            f"phase={self.current_phase}, focus={self.lesson_focus}, "
            f"covered={self.covered_topics}, vocab={self.vocab_introduced}, "
            f"elapsed={self.elapsed_minutes()}/{self.total_minutes}"
        )


class SessionManager:
    def __init__(self, session_config: dict) -> None:
        self.lesson_id = session_config["lesson_id"]
        self.learner_id = session_config["learner_id"]
        self.voice_id = session_config.get("voice_id", "sarah_en")
        self.language = session_config.get("language", "en")

        self.llm = ClaudeClient()
        self.parser = ResponseParser()
        self.prompt_builder = PromptBuilder()
        self.lesson_store = LessonPlanStore()
        self.profile_store = LearnerProfileStore()

        self.lesson_plan: LessonPlan | None = None
        self.profile: LearnerProfile | None = None
        self.context: SessionContext | None = None

        self._ready = False

    async def initialize(self) -> None:
        self.lesson_plan = self.lesson_store.load(self.lesson_id)
        self.profile = await self.profile_store.load(self.learner_id)
        self.context = SessionContext(
            lesson_id=self.lesson_id,
            learner_id=self.learner_id,
            start_time=datetime.utcnow(),
            target_language=self.lesson_plan.target_language,
            lesson_focus=self.lesson_plan.focus,
            total_minutes=self.lesson_plan.total_minutes,
        )
        self._ready = True

    def _ensure_ready(self) -> None:
        if not self._ready or self.lesson_plan is None or self.profile is None or self.context is None:
            raise RuntimeError("SessionManager not initialized")

    def maybe_fast_response(self, student_text: str) -> dict | None:
        self._ensure_ready()
        assert self.context is not None

        text = (student_text or "").strip()
        if not text:
            return {
                "text": random.choice(FAST_RESPONSES["encourage_retry"]),
                "action": "encourage",
                "phase": self.context.current_phase,
                "vocab_used": [],
                "error_noted": None,
            }

        low = text.lower()
        tokens = [t for t in low.replace("?", " ").replace("!", " ").split() if t]

        if any(greet in low for greet in ["hello", "hi", "hey", "你好", "嗨"]):
            return {
                "text": random.choice(FAST_RESPONSES["greeting"]),
                "action": "encourage",
                "phase": self.context.current_phase,
                "vocab_used": [],
                "error_noted": None,
            }

        if len(tokens) <= 2 and any(x in tokens for x in ["yes", "yeah", "right", "correct", "对", "是"]):
            return {
                "text": random.choice(FAST_RESPONSES["correct_simple"]),
                "action": "encourage",
                "phase": self.context.current_phase,
                "vocab_used": [],
                "error_noted": None,
            }

        if len(tokens) <= 2 and any(x in tokens for x in ["no", "wrong", "不会", "不知道"]):
            return {
                "text": random.choice(FAST_RESPONSES["encourage_retry"]),
                "action": "encourage",
                "phase": self.context.current_phase,
                "vocab_used": [],
                "error_noted": None,
            }

        return None

    def build_prompt(self, student_text: str) -> str:
        self._ensure_ready()
        assert self.context is not None
        assert self.profile is not None

        turns = [
            {
                "student": t.student,
                "teacher": t.teacher,
                "action": t.action,
                "phase": t.phase,
            }
            for t in self.context.turns[-8:]
        ]

        energy_hint = self._energy_hint()
        return self.prompt_builder.build(
            phase=self.context.current_phase,
            lesson_focus=self.context.lesson_focus,
            covered_topics=self.context.covered_topics,
            vocab_list_with_usage_count=self.context.vocab_introduced,
            elapsed_minutes=self.context.elapsed_minutes(),
            total_minutes=self.context.total_minutes,
            learner_profile=self.profile,
            last_turns=turns,
            energy_hint=energy_hint,
            student_text=student_text,
        )

    def parse_response(self, full_response: str) -> dict:
        return self.parser.parse(full_response)

    def add_partial_teacher_turn(self, text: str) -> None:
        self._ensure_ready()
        if not text.strip():
            return
        assert self.context is not None
        if self.context.turns:
            self.context.turns[-1].teacher = (self.context.turns[-1].teacher + " " + text).strip()

    def update(self, student_text: str, parsed: dict) -> None:
        self._ensure_ready()
        assert self.context is not None

        turn = Turn(
            student=student_text,
            teacher=parsed.get("text", ""),
            action=parsed.get("action", "encourage"),
            phase=parsed.get("phase", self.context.current_phase),
        )
        self.context.turns.append(turn)
        self.context.turns = self.context.turns[-8:]

        new_phase = parsed.get("phase")
        if new_phase in {"opening", "teach", "practice", "closing"}:
            self.context.current_phase = new_phase

        vocab_used = parsed.get("vocab_used") or []
        for word in vocab_used:
            existing = self.context.vocab_introduced.setdefault(word, {"turn": len(self.context.turns), "uses": 0})
            existing["uses"] += 1

        error_noted = parsed.get("error_noted")
        if error_noted:
            self.context.errors_this_session.append(
                {"error": error_noted, "turn": len(self.context.turns), "corrected": parsed.get("action") == "recast"}
            )

        if parsed.get("action") == "advance":
            topic = parsed.get("error_noted") or self.context.lesson_focus
            if topic not in self.context.covered_topics:
                self.context.covered_topics.append(topic)

        self._update_energy(parsed.get("action", "encourage"))

    def _update_energy(self, action: str) -> None:
        assert self.context is not None
        if action in {"encourage", "recast"}:
            self.context.energy_level = min(1.0, self.context.energy_level + 0.05)
        elif action in {"explain", "check"}:
            self.context.energy_level = max(0.0, self.context.energy_level - 0.02)

    def _energy_hint(self) -> str:
        assert self.context is not None
        elapsed = self.context.elapsed_minutes()
        if elapsed >= max(self.context.total_minutes - 4, 1):
            return "课程接近结束，保持轻松并自然收尾。"
        if self.context.energy_level < 0.35:
            return "学生可能疲劳，降低节奏并给简短成功体验。"
        if self.context.energy_level > 0.75:
            return "学生状态好，可推进一档难度并增加输出任务。"
        return "保持当前节奏，优先让学生多说。"

    async def auto_advance_loop(self) -> None:
        """Simple timer-based phase transition fallback."""
        while True:
            await asyncio.sleep(20)
            self._ensure_ready()
            assert self.context is not None
            elapsed = self.context.elapsed_minutes()
            total = self.context.total_minutes
            if elapsed >= total - 3:
                self.context.current_phase = "closing"
            elif elapsed >= 3 and self.context.current_phase == "opening":
                self.context.current_phase = "teach"
            elif elapsed >= total // 2 and self.context.current_phase == "teach":
                self.context.current_phase = "practice"

    async def end(self) -> None:
        if not self._ready:
            return

        assert self.context is not None
        assert self.profile is not None

        turns_payload = [
            {
                "student": t.student,
                "teacher": t.teacher,
                "action": t.action,
                "phase": t.phase,
            }
            for t in self.context.turns
        ]

        summary = await self.llm.summarize_session(turns_payload, self.context.errors_this_session)
        topic_correct_rate = {topic: 0.7 for topic in self.context.covered_topics}

        await self.profile_store.update_after_session(
            profile=self.profile,
            summary=summary,
            covered_topics=self.context.covered_topics,
            errors_this_session=self.context.errors_this_session,
            topic_correct_rate=topic_correct_rate,
        )
