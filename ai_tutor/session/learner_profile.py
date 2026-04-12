from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from database import get_db


@dataclass
class LearnerProfile:
    learner_id: str
    name: str = "Learner"
    level: str = "A2"
    l1: str = "zh"
    target_language: str = "en"
    frequent_errors: list[str] = field(default_factory=list)
    mastery: dict[str, float] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    total_sessions: int = 0
    last_session_summary: str = ""
    last_session_date: str = ""

    def to_prompt_context(self) -> str:
        return (
            f"- 姓名：{self.name}\n"
            f"- 水平：{self.level}\n"
            f"- 母语：{self.l1}\n"
            f"- 高频错误：{self.frequent_errors or ['暂无']}\n"
            f"- 学习偏好：{self.preferences or {'pace': 'normal'}}\n"
            f"- 上次课内容：{self.last_session_summary or '暂无'}"
        )


class LearnerProfileStore:
    def __init__(self) -> None:
        self._ready = False

    async def ensure_table(self) -> None:
        if self._ready:
            return
        conn = await get_db()
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learner_profiles (
                learner_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                l1 TEXT NOT NULL,
                target_language TEXT NOT NULL,
                frequent_errors TEXT NOT NULL,
                mastery TEXT NOT NULL,
                preferences TEXT NOT NULL,
                total_sessions INTEGER NOT NULL,
                last_session_summary TEXT NOT NULL,
                last_session_date TEXT NOT NULL
            )
            """
        )
        await conn.commit()
        await conn.close()
        self._ready = True

    async def load(self, learner_id: str) -> LearnerProfile:
        await self.ensure_table()
        conn = await get_db()
        cursor = await conn.execute(
            "SELECT * FROM learner_profiles WHERE learner_id = ?",
            (learner_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        await conn.close()

        if row is None:
            return LearnerProfile(learner_id=learner_id)

        return LearnerProfile(
            learner_id=row["learner_id"],
            name=row["name"],
            level=row["level"],
            l1=row["l1"],
            target_language=row["target_language"],
            frequent_errors=json.loads(row["frequent_errors"]),
            mastery=json.loads(row["mastery"]),
            preferences=json.loads(row["preferences"]),
            total_sessions=row["total_sessions"],
            last_session_summary=row["last_session_summary"],
            last_session_date=row["last_session_date"],
        )

    async def save(self, profile: LearnerProfile) -> None:
        await self.ensure_table()
        conn = await get_db()
        await conn.execute(
            """
            INSERT INTO learner_profiles (
                learner_id, name, level, l1, target_language,
                frequent_errors, mastery, preferences,
                total_sessions, last_session_summary, last_session_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id) DO UPDATE SET
                name=excluded.name,
                level=excluded.level,
                l1=excluded.l1,
                target_language=excluded.target_language,
                frequent_errors=excluded.frequent_errors,
                mastery=excluded.mastery,
                preferences=excluded.preferences,
                total_sessions=excluded.total_sessions,
                last_session_summary=excluded.last_session_summary,
                last_session_date=excluded.last_session_date
            """,
            (
                profile.learner_id,
                profile.name,
                profile.level,
                profile.l1,
                profile.target_language,
                json.dumps(profile.frequent_errors, ensure_ascii=False),
                json.dumps(profile.mastery, ensure_ascii=False),
                json.dumps(profile.preferences, ensure_ascii=False),
                profile.total_sessions,
                profile.last_session_summary,
                profile.last_session_date,
            ),
        )
        await conn.commit()
        await conn.close()

    async def update_after_session(
        self,
        profile: LearnerProfile,
        summary: str,
        covered_topics: list[str],
        errors_this_session: list[dict],
        topic_correct_rate: dict[str, float],
    ) -> LearnerProfile:
        profile.last_session_summary = summary
        profile.total_sessions += 1
        profile.last_session_date = datetime.utcnow().strftime("%Y-%m-%d")

        for err in errors_this_session:
            pattern = err.get("error") or err.get("pattern") or "unknown"
            if pattern not in profile.frequent_errors:
                profile.frequent_errors.append(pattern)

        for topic in covered_topics:
            old = float(profile.mastery.get(topic, 0.0))
            correct_rate = float(topic_correct_rate.get(topic, 0.0))
            profile.mastery[topic] = old * 0.7 + correct_rate * 0.3

        await self.save(profile)
        return profile
