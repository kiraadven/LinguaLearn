"""
Lesson plan persistence layer for the AI tutor.

LessonPlan captures the *session-level intent* — what the teacher wants to
accomplish today — as opposed to the per-sentence Curriculum (which is built
dynamically from job content).

Fields are grounded in SLA research:
  - session_goals: CEFR-aligned communicative objectives for this session
  - sla_strategies: which SLA methods to emphasise (e.g. shadowing, output push)
  - cultural_focus: intercultural competence targets (Byram 1997)
  - pragmatics_focus: speech act types to practise (Austin / Searle)
  - shadow_sentences: sentence indices pre-selected for prosodic shadowing
  - review_vocab: vocabulary recycled from previous sessions (spaced retrieval)
  - transfer_risks: known L1 interference patterns to watch for this session
  - teacher_notes: free-form pedagogical notes or session-specific adaptations
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from config import get_settings


@dataclass
class LessonPlan:
    # ── Identity ───────────────────────────────────────────────────────────────
    lesson_id: str
    focus: str                          # One-sentence session theme / focus

    # ── Language context ───────────────────────────────────────────────────────
    target_language: str = "en"         # ISO code of language being learned
    l1_language: str = "zh"            # ISO code of learner's native language
    content_type: str = "unknown"       # news / movie / tv_show / interview / …
    cefr_level: str = "B1"             # Learner's current CEFR level

    # ── Session logistics ──────────────────────────────────────────────────────
    total_minutes: int = 30

    # ── Pedagogical goals (SLA-grounded) ──────────────────────────────────────
    session_goals: list[str] = field(default_factory=list)
    """CEFR-aligned communicative objectives for this session.
    Example: ["Use reported speech to describe news events",
              "Recognise passive voice in journalistic register"]"""

    sla_strategies: list[str] = field(default_factory=list)
    """SLA methods to emphasise this session.
    Example: ["shadowing", "output_push", "recast_correction", "noticing"]"""

    opening_topics: list[str] = field(default_factory=list)
    """Ice-breaker conversation topics to warm up the learner."""

    # ── Vocabulary and grammar ─────────────────────────────────────────────────
    key_vocab: list[str] = field(default_factory=list)
    """Target vocabulary items for this session."""

    review_vocab: list[str] = field(default_factory=list)
    """Vocabulary to recycle from previous sessions (spaced retrieval practice)."""

    # ── Culture and pragmatics (Byram / Austin) ────────────────────────────────
    cultural_focus: list[str] = field(default_factory=list)
    """Cultural knowledge / awareness targets.
    Example: ["Understanding news media conventions in English-speaking countries"]"""

    pragmatics_focus: list[str] = field(default_factory=list)
    """Speech act types to notice and practise.
    Example: ["hedging in academic discourse", "polite disagreement", "requests"]"""

    # ── Prosodic shadowing (Murphey / Field) ──────────────────────────────────
    shadow_sentences: list[int] = field(default_factory=list)
    """Zero-based sentence indices pre-selected for shadowing practice."""

    # ── Error analysis (from learner profile) ─────────────────────────────────
    transfer_risks: list[str] = field(default_factory=list)
    """Known L1 interference patterns to watch for this session.
    Example: ["article omission (zh→en)", "tense conflation (zh→en)"]"""

    # ── Teacher notes ──────────────────────────────────────────────────────────
    teacher_notes: str = ""
    """Free-form pedagogical notes, session-specific adaptations."""

    def to_prompt_summary(self) -> str:
        """Compact summary for injection into course/global prompts."""
        lines = [f"本节课主题：{self.focus}"]
        if self.session_goals:
            lines.append("目标：" + "；".join(self.session_goals))
        if self.sla_strategies:
            lines.append("SLA策略：" + "、".join(self.sla_strategies))
        if self.review_vocab:
            lines.append("待复习词汇：" + "、".join(self.review_vocab))
        if self.transfer_risks:
            lines.append("母语干扰风险：" + "、".join(self.transfer_risks))
        if self.teacher_notes:
            lines.append(f"教师备注：{self.teacher_notes}")
        return "\n".join(lines)


class LessonPlanStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.lesson_plan_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, lesson_id: str) -> Path:
        return self.settings.lesson_plan_dir / f"{lesson_id}.json"

    def load(self, lesson_id: str) -> LessonPlan:
        path = self._path(lesson_id)
        if not path.exists():
            plan = _make_default_plan(lesson_id, self.settings.default_language)
            self.save(plan)
            return plan

        payload = json.loads(path.read_text(encoding="utf-8"))
        return LessonPlan(
            lesson_id=payload.get("lesson_id", lesson_id),
            focus=payload.get("focus", "general conversation"),
            target_language=payload.get("target_language", self.settings.default_language),
            l1_language=payload.get("l1_language", "zh"),
            content_type=payload.get("content_type", "unknown"),
            cefr_level=payload.get("cefr_level", "B1"),
            total_minutes=int(payload.get("total_minutes", 30)),
            session_goals=list(payload.get("session_goals", [])),
            sla_strategies=list(payload.get("sla_strategies", [])),
            opening_topics=list(payload.get("opening_topics", [])),
            key_vocab=list(payload.get("key_vocab", [])),
            review_vocab=list(payload.get("review_vocab", [])),
            cultural_focus=list(payload.get("cultural_focus", [])),
            pragmatics_focus=list(payload.get("pragmatics_focus", [])),
            shadow_sentences=list(payload.get("shadow_sentences", [])),
            transfer_risks=list(payload.get("transfer_risks", [])),
            teacher_notes=payload.get("teacher_notes", ""),
        )

    def save(self, plan: LessonPlan) -> None:
        path = self._path(plan.lesson_id)
        path.write_text(
            json.dumps(asdict(plan), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _make_default_plan(lesson_id: str, target_language: str) -> LessonPlan:
    """Create a sensible default lesson plan for a new lesson."""
    return LessonPlan(
        lesson_id=lesson_id,
        focus="首次课程——了解学习者并熟悉教学内容",
        target_language=target_language,
        l1_language="zh",
        content_type="unknown",
        cefr_level="B1",
        total_minutes=30,
        session_goals=[
            "通过视频内容理解真实语言输入",
            "学习本课核心词汇和表达",
        ],
        sla_strategies=["comprehensible_input", "noticing", "recast_correction"],
        opening_topics=["日常生活", "学习目标", "学习者兴趣"],
        key_vocab=[],
        review_vocab=[],
        cultural_focus=[],
        pragmatics_focus=[],
        shadow_sentences=[],
        transfer_risks=[],
        teacher_notes="",
    )
