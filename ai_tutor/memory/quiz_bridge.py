"""
Quiz Bridge: read quiz performance data from the LinguaLearn main system.

LinguaLearn stores quiz results in its SQLite DB.
We read them here to give the AI tutor context about the learner's quiz history.
Falls back gracefully if the DB is unavailable or quiz table doesn't exist.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class QuizRecord:
    job_id: str
    learner_id: str
    completion_rate: float = 0.0        # 0.0–1.0
    error_sentences: list[int] = field(default_factory=list)   # 0-based indices
    error_words: list[str] = field(default_factory=list)
    last_quiz_date: str = ""
    total_attempts: int = 0

    def has_data(self) -> bool:
        return self.total_attempts > 0

    def to_prompt_summary(self) -> str:
        if not self.has_data():
            return "（暂无 quiz 做题记录）"
        parts = [f"完成率 {self.completion_rate:.0%}，共 {self.total_attempts} 次"]
        if self.error_sentences:
            parts.append(f"错误句子：第 {[i+1 for i in self.error_sentences]} 句")
        if self.error_words:
            parts.append(f"高频错误词：{', '.join(self.error_words[:5])}")
        return "；".join(parts)


class QuizBridge:
    """
    Reads quiz performance from LinguaLearn's database.

    LinguaLearn quiz table schema (expected):
        quiz_attempts(id, job_id, user_id, sentence_index, word, is_correct, attempted_at)

    Falls back silently if the table or DB doesn't exist.
    """

    def __init__(self, lingualearn_db_path: str | Path | None = None) -> None:
        self._db_path = str(lingualearn_db_path) if lingualearn_db_path else None

    async def load_quiz_records(
        self, learner_id: str, job_id: str
    ) -> QuizRecord:
        record = QuizRecord(job_id=job_id, learner_id=learner_id)

        if not self._db_path or not Path(self._db_path).exists():
            return record

        try:
            conn = await aiosqlite.connect(self._db_path)
            conn.row_factory = aiosqlite.Row

            # Check if table exists
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_attempts'"
            )
            if not await cursor.fetchone():
                await cursor.close()
                await conn.close()
                return record

            # Total attempts
            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt FROM quiz_attempts WHERE job_id=? AND user_id=?",
                (job_id, learner_id),
            )
            row = await cursor.fetchone()
            record.total_attempts = int(row["cnt"]) if row else 0

            if record.total_attempts == 0:
                await cursor.close()
                await conn.close()
                return record

            # Correct attempts
            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt FROM quiz_attempts WHERE job_id=? AND user_id=? AND is_correct=1",
                (job_id, learner_id),
            )
            row = await cursor.fetchone()
            correct = int(row["cnt"]) if row else 0
            record.completion_rate = correct / record.total_attempts

            # Error sentences (sentences with ≥1 wrong answer)
            cursor = await conn.execute(
                """SELECT DISTINCT sentence_index FROM quiz_attempts
                   WHERE job_id=? AND user_id=? AND is_correct=0
                   ORDER BY sentence_index""",
                (job_id, learner_id),
            )
            rows = await cursor.fetchall()
            record.error_sentences = [int(r["sentence_index"]) for r in rows]

            # Error words (most frequent wrong words)
            cursor = await conn.execute(
                """SELECT word, COUNT(*) as cnt FROM quiz_attempts
                   WHERE job_id=? AND user_id=? AND is_correct=0 AND word IS NOT NULL
                   GROUP BY word ORDER BY cnt DESC LIMIT 10""",
                (job_id, learner_id),
            )
            rows = await cursor.fetchall()
            record.error_words = [r["word"] for r in rows]

            # Last quiz date
            cursor = await conn.execute(
                "SELECT MAX(attempted_at) as last FROM quiz_attempts WHERE job_id=? AND user_id=?",
                (job_id, learner_id),
            )
            row = await cursor.fetchone()
            record.last_quiz_date = (row["last"] or "")[:10] if row else ""

            await cursor.close()
            await conn.close()

        except Exception as exc:
            logger.warning("QuizBridge: failed to load quiz records: %s", exc)

        return record
