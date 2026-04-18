"""Unified review item bank operations (word/expression/sentence)."""

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


def ensure_review_settings(email: str) -> Dict:
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    c.execute(
        """
        INSERT OR IGNORE INTO review_settings (email, daily_global_max, created_at, updated_at)
        VALUES (?, 100, ?, ?)
        """,
        (email, now, now),
    )
    conn.commit()
    c.execute("SELECT * FROM review_settings WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"email": email, "daily_global_max": 100}


def get_review_settings(email: str) -> Dict:
    return ensure_review_settings(email)


def update_review_settings(email: str, *, daily_global_max: int) -> Dict:
    rec = ensure_review_settings(email)
    now = _now_iso()
    value = int(max(1, min(1000, int(daily_global_max))))
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        UPDATE review_settings
        SET daily_global_max = ?, updated_at = ?
        WHERE email = ?
        """,
        (value, now, email),
    )
    conn.commit()
    conn.close()
    rec["daily_global_max"] = value
    return rec


def upsert_review_items(email: str, job_id: str, items: List[Dict]) -> Dict:
    """
    Upsert review items and bind them to job.
    items fields:
      item_type, content_key, display_text, prompt_text, answer_text, audio_file,
      source_lang, target_lang
    """
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    inserted_items = 0
    linked_jobs = 0

    for item in items:
        item_type = str(item.get("item_type") or "").strip()
        content_key = str(item.get("content_key") or "").strip()
        display_text = str(item.get("display_text") or "").strip()
        if not item_type or not content_key or not display_text:
            continue

        prompt_text = str(item.get("prompt_text") or "").strip()
        answer_text = str(item.get("answer_text") or "").strip()
        audio_file = str(item.get("audio_file") or "").strip()
        source_lang = str(item.get("source_lang") or "").strip()
        target_lang = str(item.get("target_lang") or "").strip()

        c.execute(
            """
            INSERT OR IGNORE INTO review_items
            (email, item_type, content_key, display_text, prompt_text, answer_text, audio_file,
             source_lang, target_lang, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email, item_type, content_key, display_text, prompt_text, answer_text, audio_file,
                source_lang, target_lang, now, now,
            ),
        )
        if c.rowcount > 0:
            inserted_items += 1
        else:
            c.execute(
                """
                UPDATE review_items
                SET display_text = ?,
                    prompt_text = CASE WHEN prompt_text IS NULL OR prompt_text = '' THEN ? ELSE prompt_text END,
                    answer_text = CASE WHEN answer_text IS NULL OR answer_text = '' THEN ? ELSE answer_text END,
                    audio_file = CASE WHEN audio_file IS NULL OR audio_file = '' THEN ? ELSE audio_file END,
                    source_lang = CASE WHEN source_lang IS NULL OR source_lang = '' THEN ? ELSE source_lang END,
                    target_lang = CASE WHEN target_lang IS NULL OR target_lang = '' THEN ? ELSE target_lang END,
                    updated_at = ?
                WHERE email = ? AND item_type = ? AND content_key = ?
                """,
                (
                    display_text, prompt_text, answer_text, audio_file, source_lang, target_lang, now,
                    email, item_type, content_key,
                ),
            )

        c.execute(
            """
            SELECT id FROM review_items
            WHERE email = ? AND item_type = ? AND content_key = ?
            """,
            (email, item_type, content_key),
        )
        row = c.fetchone()
        if not row:
            continue
        rid = int(row["id"])

        c.execute(
            """
            INSERT OR IGNORE INTO review_item_jobs
            (review_item_id, email, job_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rid, email, job_id, now, now),
        )
        if c.rowcount > 0:
            linked_jobs += 1

    conn.commit()
    conn.close()
    return {"inserted_items": inserted_items, "linked_jobs": linked_jobs}


def list_candidate_review_items(
    email: str,
    item_types: List[str],
    *,
    scope: str,
    job_id: Optional[str] = None,
) -> List[Dict]:
    if not item_types:
        return []

    conn = get_db()
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(item_types))
    params: List = [email] + item_types

    if scope == "job":
        if not job_id:
            conn.close()
            return []
        sql = f"""
            SELECT ri.*, rij.job_id AS pick_job_id
            FROM review_items ri
            JOIN review_item_jobs rij
              ON rij.review_item_id = ri.id
             AND rij.email = ri.email
            WHERE ri.email = ?
              AND ri.mastered = 0
              AND ri.item_type IN ({placeholders})
              AND rij.job_id = ?
            ORDER BY datetime(COALESCE(ri.due_at, ri.created_at)) ASC, ri.reps ASC, ri.id ASC
        """
        params.append(job_id)
    else:
        sql = f"""
            SELECT ri.*, MIN(rij.job_id) AS pick_job_id
            FROM review_items ri
            LEFT JOIN review_item_jobs rij
              ON rij.review_item_id = ri.id
             AND rij.email = ri.email
            WHERE ri.email = ?
              AND ri.mastered = 0
              AND ri.item_type IN ({placeholders})
            GROUP BY ri.id
            ORDER BY datetime(COALESCE(ri.due_at, ri.created_at)) ASC, ri.reps ASC, ri.id ASC
        """

    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_review_item(item_id: int, email: str) -> Optional[Dict]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM review_items WHERE id = ? AND email = ?", (item_id, email))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def set_review_item_mastered(item_id: int, email: str, mastered: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    c.execute(
        """
        UPDATE review_items
        SET mastered = ?, updated_at = ?
        WHERE id = ? AND email = ?
        """,
        (1 if int(mastered) else 0, now, item_id, email),
    )
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def list_mastered_review_items(
    email: str,
    *,
    item_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
) -> List[Dict]:
    conn = get_db()
    c = conn.cursor()
    sql = """
        SELECT ri.*,
               GROUP_CONCAT(DISTINCT rij.job_id) AS job_ids_csv
        FROM review_items ri
        LEFT JOIN review_item_jobs rij
          ON rij.review_item_id = ri.id
         AND rij.email = ri.email
        WHERE ri.email = ?
          AND ri.mastered = 1
    """
    params: List = [email]
    if item_type:
        sql += " AND ri.item_type = ?"
        params.append(item_type)
    if q:
        like_q = f"%{q.strip()}%"
        sql += " AND (ri.display_text LIKE ? OR ri.prompt_text LIKE ?)"
        params.extend([like_q, like_q])
    sql += """
        GROUP BY ri.id
        ORDER BY datetime(ri.updated_at) DESC
        LIMIT ?
    """
    params.append(max(1, min(int(limit), 1000)))
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        csv = r.pop("job_ids_csv", "") or ""
        r["job_ids"] = [x for x in csv.split(",") if x]
    return rows


def _schedule_after_answer(row: Dict, score: float, now: datetime) -> Dict:
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
            interval_days = max(0.04, stability * 0.35)
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


def record_review_item_result(
    item_id: int,
    email: str,
    *,
    score: float,
    accuracy: float,
    coverage: float,
    elapsed_ms: int = 0,
    mask_count: int = 0,
    correct_count: int = 0,
    job_id: Optional[str] = None,
) -> Optional[Dict]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM review_items WHERE id = ? AND email = ?", (item_id, email))
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
        UPDATE review_items
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
            item_id, email,
        ),
    )

    c.execute(
        """
        INSERT INTO review_item_logs
        (review_item_id, email, job_id, item_type, outcome, score, accuracy, coverage, passed,
         elapsed_ms, mask_count, correct_count, interval_days, stability, difficulty, reviewed_at)
        VALUES (?, ?, ?, ?, 'graded', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id, email, job_id, rowd.get("item_type"),
            float(score), float(accuracy), float(coverage), int(sched["passed"]),
            int(elapsed_ms or 0), int(mask_count or 0), int(correct_count or 0),
            float(sched["interval_days"]), float(sched["stability"]), float(sched["difficulty"]), now,
        ),
    )

    conn.commit()
    conn.close()
    return {
        **sched,
        "item_id": item_id,
        "score": float(score),
        "accuracy": float(accuracy),
        "coverage": float(coverage),
    }


def log_mastered_skip(item_id: int, email: str, *, job_id: Optional[str], item_type: str) -> None:
    conn = get_db()
    c = conn.cursor()
    now = _now_iso()
    c.execute(
        """
        INSERT INTO review_item_logs
        (review_item_id, email, job_id, item_type, outcome, score, accuracy, coverage, passed,
         elapsed_ms, mask_count, correct_count, interval_days, stability, difficulty, reviewed_at)
        VALUES (?, ?, ?, ?, 'mastered_skip', 100, 1, 1, 1, 0, 0, 0, 0, 0.6, 5.0, ?)
        """,
        (item_id, email, job_id, item_type, now),
    )
    conn.commit()
    conn.close()


def get_today_review_count(email: str) -> int:
    conn = get_db()
    c = conn.cursor()
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    c.execute(
        """
        SELECT COUNT(*) AS n
        FROM review_item_logs
        WHERE email = ? AND reviewed_at >= ?
        """,
        (email, day_start),
    )
    row = c.fetchone()
    conn.close()
    return int((row or {"n": 0})["n"])

