from __future__ import annotations

import aiosqlite

from ai_tutor.config import get_settings


async def get_db() -> aiosqlite.Connection:
    settings = get_settings()
    settings.profile_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(settings.profile_db_path.as_posix())
    conn.row_factory = aiosqlite.Row
    return conn
