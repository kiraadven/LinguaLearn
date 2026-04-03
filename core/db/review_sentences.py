"""Sentence review scheduling operations (FSRS-inspired)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .connection import get_db


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_float(v, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _parse_iso(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return None


def upsert_review_sentences(
    email: str,
    job_id: str,
    sentences: List[Dict],
    source_lang: str = "",
    target_lang: str = "",
) -> int:
    """
    Upsert sentence review records for one job.
    Returns number of newly inserted rows.
    """
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    inserted = 0
    for item in sentences:
        idx = int(item.get("sentence_index", 0))
        text = (item.get("text") or "").strip()
        if not text:
            continue
        audio_file = (item.get("audio_file") or "").strip()

        c.execute(
            """
            INSERT OR IGNORE INTO review_sentences
            (email, job_id, sentence_index, sentence_text, audio_file,
             source_lang, target_lang, due_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email, job_id, idx, text, audio_file,
                source_lang or "", target_lang or "",
                now, now, now,
            ),
        )
        if c.rowcount > 0:
            inserted += 1
        else:
            c.execute(
                """
                UPDATE review_sentences
                SET sentence_text = ?,
                    audio_file = CASE WHEN (audio_file IS NULL OR audio_file = '')
                                      THEN ? ELSE audio_file END,
                    source_lang = CASE WHEN (source_lang IS NULL OR source_lang = '')
                                       THEN ? ELSE source_lang END,
                    target_lang = CASE WHEN (target_lang IS NULL OR target_lang = '')
                                       THEN ? ELSE target_lang END,
                    updated_at = ?
                WHERE email = ? AND job_id = ? AND sentence_index = ?
                """,
                (
                    text, audio_file, source_lang or "", target_lang or "", now,
                    email, job_id, idx,
                ),
            )
    conn.commit()
    conn.close()
    return inserted


def list_review_sentences(email: str, limit: int = 200, job_id: Optional[str] = None) -> List[Dict]:
    """List sentence review records sorted by due time."""
    conn = get_db()
    c = conn.cursor()
    sql = """
        SELECT *
        FROM review_sentences
        WHERE email = ?
    """
    params = [email]
    if job_id:
        sql += " AND job_id = ?"
        params.append(job_id)
    sql += """
        ORDER BY datetime(COALESCE(due_at, created_at)) ASC, reps ASC, created_at ASC
        LIMIT ?
    """
    params.append(int(limit))
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_review_sentence_item(review_id: int, email: str) -> Optional[Dict]:
    """Get one sentence review record by id/email."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM review_sentences WHERE id = ? AND email = ?", (review_id, email))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def _schedule_after_answer(row: Dict, score: float, now: datetime) -> Dict:
    """
    FSRS-inspired but lightweight schedule update.
    We keep:
      - stability (days)
      - difficulty (1-10)
      - due_at
    """
    q = _clamp(_safe_float(score, 0.0) / 100.0, 0.0, 1.0)
    passed = q >= 0.60

    reps = int(row.get("reps") or 0)
    lapses = int(row.get("lapses") or 0)
    stability = max(_safe_float(row.get("stability"), 0.6), 0.2)
    difficulty = _clamp(_safe_float(row.get("difficulty"), 5.0), 1.0, 10.0)

    last_reviewed = _parse_iso(row.get("last_reviewed_at"))
    if last_reviewed:
        elapsed_days = max((now - last_reviewed).total_seconds() / 86400.0, 0.0)
        retrievability = math.exp(-elapsed_days / max(stability, 0.1))
    else:
        elapsed_days = 0.0
        retrievability = 1.0

    if reps == 0:
        difficulty = _clamp(7.2 - q * 4.8, 1.0, 10.0)
        if passed:
            stability = 0.8 + q * 2.2
            interval_days = 0.4 + q * 1.8
            state = "learning"
        else:
            stability = 0.35 + q * 0.30
            interval_days = 0.08 + q * 0.15
            state = "relearning"
            lapses += 1
    else:
        if passed:
            difficulty = _clamp(
                difficulty - (q - 0.6) * 1.2 + (1.0 - retrievability) * 0.35,
                1.0,
                10.0,
            )
            growth = (
                1.0
                + (11.0 - difficulty) * 0.10
                + (q - 0.6) * 1.25
                + (1.0 - retrievability) * 0.55
            )
            stability = max(0.4, stability * max(1.08, growth))
            interval_days = stability * (0.78 + q * 0.72)
            if reps >= 2:
                interval_days *= 1.12
            state = "review"
        else:
            difficulty = _clamp(
                difficulty + (1.0 - q) * 2.0 + (1.0 - retrievability) * 0.6,
                1.0,
                10.0,
            )
            stability = max(0.25, stability * (0.42 + q * 0.15))
            interval_days = max(0.04, stability * 0.35)  # at least ~1 hour
            state = "relearning"
            lapses += 1

    interval_days = _clamp(interval_days, 0.03, 120.0)
    due_at = (now + timedelta(days=interval_days)).isoformat()
    return {
        "passed": 1 if passed else 0,
        "state": state,
        "reps": reps + 1,
        "lapses": lapses,
        "stability": float(stability),
        "difficulty": float(difficulty),
        "interval_days": float(interval_days),
        "due_at": due_at,
        "elapsed_days": float(elapsed_days),
        "retrievability": float(retrievability),
    }


def record_review_sentence_result(
    review_id: int,
    email: str,
    *,
    score: float,
    accuracy: float,
    coverage: float,
    elapsed_ms: int = 0,
    mask_count: int = 0,
    correct_count: int = 0,
) -> Optional[Dict]:
    """Persist one review event and update schedule state."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM review_sentences WHERE id = ? AND email = ?", (review_id, email))
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    rowd = dict(row)
    now_dt = datetime.now()
    now = now_dt.isoformat()
    sched = _schedule_after_answer(rowd, score=score, now=now_dt)

    c.execute(
        """
        UPDATE review_sentences
        SET due_at = ?,
            last_reviewed_at = ?,
            reps = ?,
            lapses = ?,
            state = ?,
            stability = ?,
            difficulty = ?,
            last_score = ?,
            updated_at = ?
        WHERE id = ? AND email = ?
        """,
        (
            sched["due_at"], now, sched["reps"], sched["lapses"], sched["state"],
            sched["stability"], sched["difficulty"], float(score), now,
            review_id, email,
        ),
    )

    c.execute(
        """
        INSERT INTO review_sentence_logs
        (review_id, email, job_id, sentence_index, score, accuracy, coverage, passed,
         elapsed_ms, mask_count, correct_count, interval_days, stability, difficulty, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id, email, rowd.get("job_id"), int(rowd.get("sentence_index") or 0),
            float(score), float(accuracy), float(coverage), int(sched["passed"]),
            int(elapsed_ms or 0), int(mask_count or 0), int(correct_count or 0),
            float(sched["interval_days"]), float(sched["stability"]), float(sched["difficulty"]), now,
        ),
    )

    conn.commit()
    conn.close()

    return {
        **sched,
        "review_id": review_id,
        "score": float(score),
        "accuracy": float(accuracy),
        "coverage": float(coverage),
    }


def get_review_sentence_stats(email: str) -> Dict:
    """Aggregate stats for sentence review dashboard."""
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    c.execute("SELECT COUNT(*) AS n FROM review_sentences WHERE email = ?", (email,))
    total = int((c.fetchone() or {"n": 0})["n"])

    c.execute(
        """
        SELECT COUNT(*) AS n
        FROM review_sentences
        WHERE email = ? AND (due_at IS NULL OR due_at <= ?)
        """,
        (email, now),
    )
    due = int((c.fetchone() or {"n": 0})["n"])

    c.execute(
        """
        SELECT COUNT(*) AS n
        FROM review_sentences
        WHERE email = ? AND reps = 0
        """,
        (email,),
    )
    new_items = int((c.fetchone() or {"n": 0})["n"])

    c.execute(
        """
        SELECT COUNT(*) AS n
        FROM review_sentence_logs
        WHERE email = ? AND reviewed_at >= ?
        """,
        (email, day_start),
    )
    reviewed_today = int((c.fetchone() or {"n": 0})["n"])

    conn.close()
    return {
        "total": total,
        "due": due,
        "new": new_items,
        "reviewed_today": reviewed_today,
    }

