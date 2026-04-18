"""
Long-term learner memory: cross-session, cross-job knowledge graph.
Persisted in SQLite.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import aiosqlite

from ai_tutor.memory.learner_graph import LearnerGraph

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Reads and writes the learner's long-term knowledge graph."""

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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS learner_long_term (
                learner_id TEXT PRIMARY KEY,
                knowledge_graph TEXT DEFAULT '{}',
                updated_at TEXT
            )
        """)
        await conn.commit()
        await conn.close()
        self._ready = True

    async def get_graph(self, learner_id: str) -> LearnerGraph:
        await self.ensure_tables()
        conn = await self._conn()
        cursor = await conn.execute(
            "SELECT knowledge_graph FROM learner_long_term WHERE learner_id=?",
            (learner_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        await conn.close()

        if row is None:
            return LearnerGraph(learner_id=learner_id)

        try:
            data = json.loads(row["knowledge_graph"] or "{}")
        except Exception:
            data = {}

        return LearnerGraph.from_json(learner_id, data)

    async def save_graph(self, graph: LearnerGraph) -> None:
        await self.ensure_tables()
        conn = await self._conn()
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """
            INSERT INTO learner_long_term (learner_id, knowledge_graph, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(learner_id) DO UPDATE SET
                knowledge_graph = excluded.knowledge_graph,
                updated_at = excluded.updated_at
            """,
            (graph.learner_id, graph.to_json(), now),
        )
        await conn.commit()
        await conn.close()

    async def update_from_session(
        self,
        learner_id: str,
        session_data: dict,
        content_vocab: list[str] | None = None,
    ) -> LearnerGraph:
        """
        Update the long-term graph after a session.

        session_data keys used:
            sentences_covered: list[int]
            errors: list[{type, detail, sentence_index}]
            new_interests: list[str]  (optional, from global chat)
            chat_insights: dict  (optional)
            grammar_gains: dict[str, float]  (optional)
        """
        graph = await self.get_graph(learner_id)

        # Update vocab mastery for covered words
        if content_vocab:
            errors = session_data.get("errors", [])
            error_words = {
                e.get("detail", "").lower()
                for e in errors
                if e.get("type") == "vocabulary"
            }
            for word in content_vocab:
                if word.lower() in error_words:
                    graph.update_vocab(word, -0.05)
                else:
                    graph.update_vocab(word, +0.15)

        # Grammar
        for point, delta in session_data.get("grammar_gains", {}).items():
            graph.update_grammar(point, delta)

        # Interests from global chat
        for tag in session_data.get("new_interests", []):
            graph.add_interest(tag)

        # Chat insights (personal info about user)
        for key, val in session_data.get("chat_insights", {}).items():
            graph.add_chat_insight(key, val)

        await self.save_graph(graph)
        return graph
