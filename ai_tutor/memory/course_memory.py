"""
Course-level memory: per-learner, per-job learning records.
Persisted in SQLite across sessions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiosqlite


@dataclass
class SentenceRecord:
    learner_id: str
    job_id: str
    sentence_index: int
    mastery: float = 0.0            # 0.0–1.0
    times_reviewed: int = 0
    pronunciation_score: float | None = None
    errors: list[dict] = field(default_factory=list)
    last_studied: str = ""


class CourseMemory:
    """
    Reads and writes sentence-level learning records.
    One record per (learner_id, job_id, sentence_index).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ready = False

    async def _conn(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def ensure_tables(self) -> None:
        if self._ready:
            return
        conn = await self._conn()
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS course_learning_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                sentence_index INTEGER NOT NULL,
                mastery REAL DEFAULT 0.0,
                times_reviewed INTEGER DEFAULT 0,
                pronunciation_score REAL,
                errors TEXT DEFAULT '[]',
                last_studied TEXT,
                UNIQUE(learner_id, job_id, sentence_index)
            );

            CREATE TABLE IF NOT EXISTS course_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                sentences_covered TEXT DEFAULT '[]',
                session_summary TEXT DEFAULT '',
                attention_avg REAL DEFAULT 1.0
            );
        """)
        await conn.commit()
        await conn.close()
        self._ready = True

    async def get_sentence_status(
        self, learner_id: str, job_id: str
    ) -> dict[int, SentenceRecord]:
        await self.ensure_tables()
        conn = await self._conn()
        cursor = await conn.execute(
            "SELECT * FROM course_learning_records WHERE learner_id=? AND job_id=?",
            (learner_id, job_id),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        await conn.close()

        result: dict[int, SentenceRecord] = {}
        for row in rows:
            idx = row["sentence_index"]
            result[idx] = SentenceRecord(
                learner_id=learner_id,
                job_id=job_id,
                sentence_index=idx,
                mastery=float(row["mastery"]),
                times_reviewed=int(row["times_reviewed"]),
                pronunciation_score=row["pronunciation_score"],
                errors=json.loads(row["errors"] or "[]"),
                last_studied=row["last_studied"] or "",
            )
        return result

    async def update_after_session(
        self,
        learner_id: str,
        job_id: str,
        session_data: dict,
    ) -> None:
        """
        session_data keys:
            sentences_covered: list[int]
            errors: list[{type, detail, sentence_index}]
            attention_avg: float
            shadow_requests: int
        """
        await self.ensure_tables()
        conn = await self._conn()
        now = datetime.now(timezone.utc).isoformat()

        sentences_covered: list[int] = session_data.get("sentences_covered", [])
        errors: list[dict] = session_data.get("errors", [])

        # Group errors by sentence index
        errors_by_sentence: dict[int, list[dict]] = {}
        for err in errors:
            idx = err.get("sentence_index", -1)
            errors_by_sentence.setdefault(idx, []).append(err)

        for sentence_index in sentences_covered:
            sentence_errors = errors_by_sentence.get(sentence_index, [])
            # Mastery update: fewer errors → higher mastery gain
            error_penalty = min(len(sentence_errors) * 0.1, 0.3)
            mastery_gain = max(0.1, 0.3 - error_penalty)

            await conn.execute(
                """
                INSERT INTO course_learning_records
                    (learner_id, job_id, sentence_index, mastery, times_reviewed, errors, last_studied)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(learner_id, job_id, sentence_index) DO UPDATE SET
                    mastery = MIN(1.0, mastery + ?),
                    times_reviewed = times_reviewed + 1,
                    errors = ?,
                    last_studied = ?
                """,
                (
                    learner_id, job_id, sentence_index,
                    mastery_gain,
                    json.dumps(sentence_errors, ensure_ascii=False),
                    now,
                    # UPDATE values
                    mastery_gain,
                    json.dumps(sentence_errors, ensure_ascii=False),
                    now,
                ),
            )

        # Log the session
        await conn.execute(
            """
            INSERT INTO course_sessions
                (learner_id, job_id, mode, started_at, ended_at,
                 sentences_covered, attention_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                learner_id, job_id,
                session_data.get("mode", "course"),
                session_data.get("started_at", now),
                now,
                json.dumps(sentences_covered),
                session_data.get("attention_avg", 1.0),
            ),
        )

        await conn.commit()
        await conn.close()

    async def get_job_progress(
        self, learner_id: str, job_id: str, total_sentences: int
    ) -> dict:
        """Return a summary dict for the frontend memory panel."""
        status = await self.get_sentence_status(learner_id, job_id)
        covered = len(status)
        avg_mastery = (
            sum(r.mastery for r in status.values()) / covered if covered else 0.0
        )
        return {
            "total_sentences": total_sentences,
            "sentences_covered": covered,
            "avg_mastery": round(avg_mastery, 2),
            "per_sentence": {
                idx: {"mastery": rec.mastery, "times": rec.times_reviewed}
                for idx, rec in status.items()
            },
        }
