"""
MemoryManager: unified entry point for all memory layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_tutor.memory.course_memory import CourseMemory
from ai_tutor.memory.learner_graph import LearnerGraph
from ai_tutor.memory.long_term import LongTermMemory
from ai_tutor.memory.quiz_bridge import QuizBridge, QuizRecord
from ai_tutor.memory.short_term import ShortTermMemory

if TYPE_CHECKING:
    from ai_tutor.content.loader import LinguaLearnContent


@dataclass
class MemoryContext:
    """All memory layers assembled for prompt injection."""
    short_term: ShortTermMemory
    course_progress: dict               # from CourseMemory.get_job_progress()
    quiz_record: QuizRecord
    learner_graph: LearnerGraph

    def to_prompt_block(self, mode: str = "course") -> str:
        lines: list[str] = []

        # Learner graph
        graph_summary = self.learner_graph.to_prompt_summary()
        if graph_summary:
            lines.append(f"[学习者画像]\n{graph_summary}")

        if mode == "course":
            # Course progress
            prog = self.course_progress
            covered = prog.get("sentences_covered", 0)
            total = prog.get("total_sentences", 0)
            avg = prog.get("avg_mastery", 0.0)
            lines.append(
                f"[本课学习进度] 已学 {covered}/{total} 句，平均掌握度 {avg:.0%}"
            )

            # Quiz record
            lines.append(f"[Quiz 记录] {self.quiz_record.to_prompt_summary()}")

        # Recent conversation
        recent = self.short_term.format_for_prompt(6)
        if recent:
            lines.append(f"[最近对话]\n{recent}")

        # Current attention
        attn = self.short_term.avg_attention
        attn_label = "高" if attn >= 0.7 else ("中" if attn >= 0.4 else "低")
        lines.append(f"[注意力] {attn_label}（{attn:.1f}）")

        return "\n\n".join(lines)


class MemoryManager:
    """
    Creates and orchestrates all memory layers for a learner session.
    Call initialize() once at session start, then use the properties.
    """

    def __init__(
        self,
        ai_tutor_db_path: str,
        lingualearn_db_path: str | None = None,
    ) -> None:
        self.course_memory = CourseMemory(ai_tutor_db_path)
        self.long_term = LongTermMemory(ai_tutor_db_path)
        self.quiz_bridge = QuizBridge(lingualearn_db_path)
        self._short: ShortTermMemory | None = None
        self._graph: LearnerGraph | None = None
        self._quiz: QuizRecord | None = None
        self._progress: dict = {}

    async def initialize(
        self,
        learner_id: str,
        job_id: str,
        total_sentences: int,
    ) -> ShortTermMemory:
        """Load all persistent memory and return a fresh ShortTermMemory."""
        await self.course_memory.ensure_tables()
        await self.long_term.ensure_tables()

        self._graph = await self.long_term.get_graph(learner_id)
        self._quiz = await self.quiz_bridge.load_quiz_records(learner_id, job_id)
        self._progress = await self.course_memory.get_job_progress(
            learner_id, job_id, total_sentences
        )
        self._short = ShortTermMemory()
        self._learner_id = learner_id
        self._job_id = job_id
        return self._short

    @property
    def short_term(self) -> ShortTermMemory:
        assert self._short is not None, "Call initialize() first"
        return self._short

    def get_context(self, mode: str = "course") -> MemoryContext:
        assert self._short is not None, "Call initialize() first"
        return MemoryContext(
            short_term=self._short,
            course_progress=self._progress,
            quiz_record=self._quiz or QuizRecord(job_id="", learner_id=""),
            learner_graph=self._graph or LearnerGraph(learner_id=self._learner_id),
        )

    async def save_session(
        self,
        learner_id: str,
        job_id: str,
        mode: str,
        content: "LinguaLearnContent | None" = None,
        started_at: str = "",
    ) -> None:
        """Persist short-term session data to all relevant stores."""
        assert self._short is not None
        session_data = self._short.to_session_data()
        session_data["mode"] = mode
        session_data["started_at"] = started_at

        await self.course_memory.update_after_session(learner_id, job_id, session_data)

        # Extract all vocab words from covered sentences for graph update
        content_vocab: list[str] = []
        if content:
            for idx in session_data.get("sentences_covered", []):
                s = content.get_sentence(idx)
                if s:
                    content_vocab.extend(v.word for v in s.vocab)

        await self.long_term.update_from_session(
            learner_id, session_data, content_vocab=content_vocab
        )
