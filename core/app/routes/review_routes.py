"""Unified review routes (word/expression/sentence + FSRS-like scheduling)."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query


_WORD_SUMMARY_TOKENS = [
    "词汇汇总表",
    "詞彙彙總表",
    "vocabulary summary",
    "語彙まとめ",
    "어휘 정리",
    "vokabeln zusammenfassung",
    "résumé du vocabulaire",
    "resumen de vocabulario",
    "итоговый словарь",
]

_EXPR_SUMMARY_TOKENS = [
    "表达汇总表",
    "表達彙總表",
    "expressions summary",
    "表現まとめ",
    "표현 정리",
    "ausdrücke zusammenfassung",
    "résumé des expressions",
    "resumen de expresiones",
    "итоговые выражения",
]

_WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*"
    r"|[\u4e00-\u9fff]+"
    r"|[\u3040-\u30ff]+"
    r"|[\uac00-\ud7af]+",
    re.UNICODE,
)


def _parse_result_json(job: Dict[str, Any]) -> Dict[str, Any]:
    result = job.get("result")
    if isinstance(result, dict):
        return result
    result_json = job.get("result_json")
    if isinstance(result_json, str):
        try:
            return json.loads(result_json) if result_json else {}
        except Exception:
            return {}
    if isinstance(result, str):
        try:
            return json.loads(result) if result else {}
        except Exception:
            return {}
    return {}


def _normalize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(job)
    out["result"] = _parse_result_json(job)
    return out


def _owner_email(job: Dict[str, Any]) -> str:
    return str(job.get("email") or job.get("created_by") or "").strip().lower()


def _assert_job_owner(job: Dict[str, Any], email: str) -> None:
    owner = _owner_email(job)
    if owner and owner != email.lower():
        raise HTTPException(403, "无权访问该视频")


def _strip_md_emphasis(v: str) -> str:
    s = str(v or "").strip()
    s = re.sub(r"^\*\*(.*?)\*\*$", r"\1", s)
    s = s.replace("`", "")
    return s.strip()


def _clean_space(v: str) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _normalize_text_key(v: str) -> str:
    s = str(v or "").strip().lower().replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    return s


def _make_content_key(item_type: str, value: str) -> str:
    return f"{item_type}:{_normalize_text_key(value)}"


def _word_tokens(sentence: str) -> List[Dict[str, Any]]:
    tokens: List[Dict[str, Any]] = []
    for m in _WORD_RE.finditer(sentence or ""):
        tokens.append({"text": m.group(0), "start": m.start(), "end": m.end()})
    return tokens


def _normalize_answer_text(v: str) -> str:
    s = str(v or "").strip().lower().replace("’", "'")
    s = re.sub(r"[^\w\u00C0-\u024F\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af'\- ]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_md_words_and_expressions(md_text: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    words: List[Dict[str, str]] = []
    expressions: List[Dict[str, str]] = []

    mode = ""
    seen_word = set()
    seen_expr = set()

    for raw_line in (md_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if any(tok in heading for tok in _WORD_SUMMARY_TOKENS):
                mode = "word"
            elif any(tok in heading for tok in _EXPR_SUMMARY_TOKENS):
                mode = "expression"
            else:
                mode = ""
            continue

        if mode not in {"word", "expression"}:
            continue

        if not line.startswith("|"):
            continue
        if re.match(r"^\|\s*[-: ]+\|", line):
            continue

        cols = [c.strip() for c in line.strip("|").split("|")]
        if mode == "word":
            if len(cols) < 3:
                continue
            word = _clean_space(_strip_md_emphasis(cols[0]))
            meaning = _clean_space(_strip_md_emphasis(cols[2]))
            if not word or not meaning:
                continue
            key = _normalize_text_key(word)
            if key in seen_word:
                continue
            seen_word.add(key)
            words.append({"word": word, "meaning": meaning})
        else:
            if len(cols) < 2:
                continue
            expr = _clean_space(_strip_md_emphasis(cols[0]))
            meaning = _clean_space(_strip_md_emphasis(cols[1]))
            if not expr or not meaning:
                continue
            key = _normalize_text_key(expr)
            if key in seen_expr:
                continue
            seen_expr.add(key)
            expressions.append({"expression": expr, "meaning": meaning})

    return words, expressions


def _find_markdown_file(job_out: Path, result: Dict[str, Any]) -> Optional[Path]:
    md_name = str(result.get("markdown") or "").strip()
    if md_name:
        p = job_out / md_name
        if p.exists():
            return p
    matches = sorted(job_out.glob("*.md"))
    return matches[0] if matches else None


def _load_sentence_manifest(job_out: Path, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    sq_name = str(result.get("sentence_quiz") or "sentence_quiz.json").strip() or "sentence_quiz.json"
    sq_path = job_out / sq_name
    if sq_path.exists():
        try:
            data = json.loads(sq_path.read_text(encoding="utf-8"))
            rows = data.get("sentences") if isinstance(data, dict) else []
            if isinstance(rows, list):
                return rows
        except Exception:
            pass

    seg_path = job_out / "segments.json"
    if seg_path.exists():
        try:
            segs = json.loads(seg_path.read_text(encoding="utf-8"))
            out = []
            for i, seg in enumerate(segs or []):
                txt = _clean_space(seg.get("text") or "")
                if not txt:
                    continue
                audio_file = f"sq_{i + 1:04d}.mp3"
                if not (job_out / audio_file).exists():
                    audio_file = ""
                out.append(
                    {
                        "sentence_index": i,
                        "text": txt,
                        "audio_file": audio_file,
                        "start": seg.get("start"),
                        "end": seg.get("end"),
                        "duration": None,
                        "has_audio": bool(audio_file),
                    }
                )
            return out
        except Exception:
            return []
    return []


def _build_job_review_items(job: Dict[str, Any], output_dir: Path) -> List[Dict[str, Any]]:
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        return []

    job_out = output_dir / job_id
    if not job_out.exists():
        return []

    result = _parse_result_json(job)
    source_lang = str(job.get("source_lang") or result.get("source_lang") or "").strip()
    target_lang = str(job.get("target_lang") or result.get("target_lang") or "").strip()

    items: List[Dict[str, Any]] = []
    seen = set()

    md_path = _find_markdown_file(job_out, result)
    if md_path and md_path.exists():
        try:
            md_text = md_path.read_text(encoding="utf-8")
            words, expressions = _parse_md_words_and_expressions(md_text)
            for row in words:
                answer = row["word"]
                key = ("word", _make_content_key("word", answer))
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "item_type": "word",
                        "content_key": key[1],
                        "display_text": answer,
                        "prompt_text": row["meaning"],
                        "answer_text": answer,
                        "audio_file": "",
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                    }
                )
            for row in expressions:
                answer = row["expression"]
                key = ("expression", _make_content_key("expression", answer))
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "item_type": "expression",
                        "content_key": key[1],
                        "display_text": answer,
                        "prompt_text": row["meaning"],
                        "answer_text": answer,
                        "audio_file": "",
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                    }
                )
        except Exception:
            pass

    for row in _load_sentence_manifest(job_out, result):
        text = _clean_space(row.get("text") or "")
        if not text:
            continue
        audio_file = _clean_space(row.get("audio_file") or "")
        if audio_file and not (job_out / audio_file).exists():
            audio_file = ""

        key = ("sentence", _make_content_key("sentence", text))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "item_type": "sentence",
                "content_key": key[1],
                "display_text": text,
                "prompt_text": "",
                "answer_text": text,
                "audio_file": audio_file,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
        )

    return items


def _ensure_review_bank_for_job(database, email: str, job: Dict[str, Any], output_dir: Path) -> Dict[str, int]:
    items = _build_job_review_items(job, output_dir)
    if not items:
        return {"inserted_items": 0, "linked_jobs": 0}
    return database.upsert_review_items(email, str(job.get("id") or ""), items)


def _parse_due_at(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return None


def _pick_mask_indices(text: str) -> Tuple[List[Dict[str, Any]], List[int]]:
    tokens = _word_tokens(text)
    if not tokens:
        return [], []

    candidates = []
    for i, tok in enumerate(tokens):
        tv = tok.get("text") or ""
        if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", tv):
            if len(tv) >= 2:
                candidates.append(i)
        else:
            if len(tv) >= 1:
                candidates.append(i)

    if not candidates:
        return tokens, []

    n = len(candidates)
    if n <= 1:
        k = 1
    elif n <= 3:
        k = 2
    else:
        k = max(2, int(round(n * 0.42)))
    k = max(1, min(k, n, 8))

    return tokens, sorted(random.sample(candidates, k=k))


def _blank_placeholder(token: str) -> str:
    n = len(str(token or ""))
    n = max(2, min(n, 10))
    return "•" * n


def _build_masked_segments(text: str, tokens: List[Dict[str, Any]], mask_indices: List[int]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if not tokens:
        return [{"type": "text", "text": text}]

    mask_set = set(mask_indices)
    cursor = 0
    blank_order = 0

    for i, tok in enumerate(tokens):
        start = int(tok["start"])
        end = int(tok["end"])

        if start > cursor:
            seg_text = text[cursor:start]
            if seg_text:
                segments.append({"type": "text", "text": seg_text})

        tok_text = text[start:end]
        if i in mask_set:
            segments.append(
                {
                    "type": "blank",
                    "blank_order": blank_order,
                    "placeholder": _blank_placeholder(tok_text),
                }
            )
            blank_order += 1
        else:
            segments.append({"type": "text", "text": tok_text})

        cursor = end

    if cursor < len(text):
        segments.append({"type": "text", "text": text[cursor:]})

    return segments


def _find_audio_job_id(
    database,
    *,
    email: str,
    item_id: int,
    preferred_job_id: Optional[str],
    audio_file: str,
    output_dir: Path,
) -> Optional[str]:
    if not audio_file:
        return preferred_job_id

    job_ids: List[str] = []
    if preferred_job_id:
        job_ids.append(preferred_job_id)

    try:
        conn = database.get_db()
        c = conn.cursor()
        c.execute(
            """
            SELECT job_id FROM review_item_jobs
            WHERE review_item_id = ? AND email = ?
            ORDER BY id DESC
            """,
            (item_id, email),
        )
        for row in c.fetchall():
            jid = str(row["job_id"])
            if jid and jid not in job_ids:
                job_ids.append(jid)
        conn.close()
    except Exception:
        pass

    for jid in job_ids:
        if (output_dir / jid / audio_file).exists():
            return jid

    return preferred_job_id or (job_ids[0] if job_ids else None)


def _build_question_payload(database, row: Dict[str, Any], *, email: str, output_dir: Path, job_name_cache: Dict[str, str]) -> Dict[str, Any]:
    item_type = str(row.get("item_type") or "")
    pick_job_id = str(row.get("pick_job_id") or "") or None
    data = {
        "id": int(row.get("id") or 0),
        "item_type": item_type,
        "content_key": str(row.get("content_key") or ""),
        "display_text": str(row.get("display_text") or ""),
        "prompt_text": str(row.get("prompt_text") or ""),
        "source_lang": str(row.get("source_lang") or ""),
        "target_lang": str(row.get("target_lang") or ""),
        "job_id": pick_job_id,
        "state": str(row.get("state") or "new"),
        "due_at": row.get("due_at"),
    }

    if item_type != "sentence":
        return data

    sentence_text = data["display_text"]
    tokens, mask_indices = _pick_mask_indices(sentence_text)
    data["sentence_text"] = sentence_text
    data["mask_indices"] = mask_indices
    data["blank_count"] = len(mask_indices)
    data["masked_segments"] = _build_masked_segments(sentence_text, tokens, mask_indices)

    audio_file = str(row.get("audio_file") or "").strip()
    if audio_file:
        audio_job_id = _find_audio_job_id(
            database,
            email=email,
            item_id=data["id"],
            preferred_job_id=pick_job_id,
            audio_file=audio_file,
            output_dir=output_dir,
        )
        if audio_job_id:
            data["job_id"] = audio_job_id
            data["audio_url"] = f"/api/jobs/{audio_job_id}/preview/{audio_file}"
            if audio_job_id not in job_name_cache:
                try:
                    j = database.get_job(audio_job_id)
                    job_name_cache[audio_job_id] = str(
                        (j or {}).get("name") or (j or {}).get("video_filename") or audio_job_id[:12]
                    )
                except Exception:
                    job_name_cache[audio_job_id] = audio_job_id[:12]
            data["job_name"] = job_name_cache.get(audio_job_id, "")

    return data


def _expected_blanks(sentence_text: str, mask_indices: List[int]) -> Tuple[List[str], int, int]:
    tokens = _word_tokens(sentence_text)
    if not tokens:
        return [], 0, 0

    valid_idx = sorted({int(i) for i in (mask_indices or []) if isinstance(i, int) and 0 <= int(i) < len(tokens)})
    expected = [tokens[i]["text"] for i in valid_idx]
    return expected, len(tokens), len(valid_idx)


def _grade_word_like(expected: str, answer: str) -> Dict[str, float]:
    exp = _normalize_answer_text(expected)
    got = _normalize_answer_text(answer)
    if not exp:
        return {"score": 0.0, "accuracy": 0.0, "coverage": 0.0, "passed": 0}

    coverage = 1.0 if got else 0.0
    ratio = 0.0
    if got:
        ratio = SequenceMatcher(a=exp, b=got).ratio()
    score = round((ratio * 0.9 + coverage * 0.1) * 100, 2)
    passed = 1 if score >= 60 else 0
    return {
        "score": float(score),
        "accuracy": float(ratio),
        "coverage": float(coverage),
        "passed": passed,
    }


def _grade_sentence(expected_blanks: List[str], user_blanks: List[str]) -> Dict[str, Any]:
    mask_count = len(expected_blanks)
    if mask_count <= 0:
        return {
            "score": 0.0,
            "accuracy": 0.0,
            "coverage": 0.0,
            "passed": 0,
            "correct_count": 0,
            "mask_count": 0,
            "expected_blanks": [],
        }

    user_blanks = list(user_blanks or [])
    if len(user_blanks) < mask_count:
        user_blanks += [""] * (mask_count - len(user_blanks))

    correct_count = 0
    filled_count = 0

    for i in range(mask_count):
        exp = _normalize_answer_text(expected_blanks[i])
        got_raw = user_blanks[i] if i < len(user_blanks) else ""
        got = _normalize_answer_text(got_raw)
        if got:
            filled_count += 1
        if got and got == exp:
            correct_count += 1

    accuracy = correct_count / mask_count
    coverage = filled_count / mask_count
    score = round((accuracy * 0.85 + coverage * 0.15) * 100, 2)
    passed = 1 if score >= 60 else 0

    return {
        "score": float(score),
        "accuracy": float(accuracy),
        "coverage": float(coverage),
        "passed": passed,
        "correct_count": int(correct_count),
        "mask_count": int(mask_count),
        "expected_blanks": expected_blanks,
    }


def _resolve_include_types(payload: Dict[str, Any]) -> List[str]:
    include = payload.get("include_types") or {}
    allowed = ["word", "expression", "sentence"]
    picked = [t for t in allowed if bool(include.get(t))]
    if not picked:
        return []
    return picked


def build_review_router(
    *,
    database,
    config,
    require_user: Callable,
    get_job_or_404: Callable,
    output_dir: Path,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/review/session")
    async def create_review_session(
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        email = str(current_user["email"])
        scope = str(payload.get("scope") or "job").strip().lower()
        if scope not in {"job", "global"}:
            raise HTTPException(400, "scope must be 'job' or 'global'")

        include_types = _resolve_include_types(payload)
        if not include_types:
            raise HTTPException(400, "至少选择一种题型")

        requested_count = int(payload.get("requested_count") or 40)
        requested_count = max(1, min(requested_count, 500))

        job_id = None
        if scope == "job":
            job_id = str(payload.get("job_id") or "").strip()
            if not job_id:
                raise HTTPException(400, "job scope requires job_id")
            job = _normalize_job(get_job_or_404(job_id))
            _assert_job_owner(job, email)
            _ensure_review_bank_for_job(database, email, job, output_dir)
        else:
            # Lazy bootstrap: each global session refreshes bank from all completed jobs.
            jobs = database.get_user_jobs(email, limit=500)
            for raw_job in jobs:
                j = _normalize_job(raw_job)
                if str(j.get("status") or "") != "done":
                    continue
                try:
                    _ensure_review_bank_for_job(database, email, j, output_dir)
                except Exception:
                    continue

        settings = database.get_review_settings(email)
        reviewed_today = database.get_today_review_count(email)
        daily_max = int(settings.get("daily_global_max") or 100)
        remaining_today = max(0, daily_max - reviewed_today)

        actual_limit = requested_count
        if scope == "global":
            actual_limit = min(requested_count, remaining_today)

        if actual_limit <= 0:
            return {
                "items": [],
                "meta": {
                    "requested_count": requested_count,
                    "actual_count": 0,
                    "daily_global_max": daily_max,
                    "reviewed_today": reviewed_today,
                    "remaining_today": remaining_today,
                },
            }

        rows = database.list_candidate_review_items(
            email,
            include_types,
            scope=scope,
            job_id=job_id,
        )

        now = datetime.now()
        due_rows = []
        upcoming_rows = []

        for row in rows:
            due_at = _parse_due_at(row.get("due_at"))
            if due_at is None or due_at <= now:
                due_rows.append(row)
            else:
                upcoming_rows.append(row)

        random.shuffle(due_rows)
        random.shuffle(upcoming_rows)
        picked_rows = (due_rows + upcoming_rows)[:actual_limit]

        job_name_cache: Dict[str, str] = {}
        items = [
            _build_question_payload(
                database,
                row,
                email=email,
                output_dir=output_dir,
                job_name_cache=job_name_cache,
            )
            for row in picked_rows
        ]

        return {
            "items": items,
            "meta": {
                "requested_count": requested_count,
                "actual_count": len(items),
                "daily_global_max": daily_max,
                "reviewed_today": reviewed_today,
                "remaining_today": remaining_today,
            },
        }

    @router.post("/api/review/grade")
    async def grade_review_item(
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        email = str(current_user["email"])
        item_id = int(payload.get("item_id") or 0)
        if item_id <= 0:
            raise HTTPException(400, "item_id is required")

        item = database.get_review_item(item_id, email)
        if not item:
            raise HTTPException(404, "review item not found")

        if int(item.get("mastered") or 0) == 1:
            raise HTTPException(409, "该条目已在熟词本中")

        item_type = str(payload.get("item_type") or item.get("item_type") or "").strip()
        if item_type != item.get("item_type"):
            item_type = str(item.get("item_type") or "")

        elapsed_ms = int(payload.get("elapsed_ms") or 0)
        job_id = str(payload.get("job_id") or "").strip() or None

        if item_type in {"word", "expression"}:
            expected = str(item.get("answer_text") or item.get("display_text") or "")
            answer = str(payload.get("answer_text") or "")
            grade = _grade_word_like(expected, answer)

            sched = database.record_review_item_result(
                item_id,
                email,
                score=float(grade["score"]),
                accuracy=float(grade["accuracy"]),
                coverage=float(grade["coverage"]),
                elapsed_ms=elapsed_ms,
                mask_count=0,
                correct_count=0,
                job_id=job_id,
            )
            if not sched:
                raise HTTPException(500, "评分保存失败")

            return {
                "score": grade["score"],
                "passed": bool(grade["passed"]),
                "accuracy": grade["accuracy"],
                "coverage": grade["coverage"],
                "next_due_at": sched["due_at"],
                "interval_days": sched["interval_days"],
                "stability": sched["stability"],
                "difficulty": sched["difficulty"],
                "state": sched["state"],
                "expected_text": expected,
            }

        if item_type != "sentence":
            raise HTTPException(400, "invalid item_type")

        sentence_text = str(item.get("display_text") or "")
        mask_indices_payload = payload.get("mask_indices") or []
        user_blanks = payload.get("user_blanks") or []

        # Keep same order as question payload to evaluate specific blanks.
        try:
            mask_indices = [int(x) for x in mask_indices_payload]
        except Exception:
            mask_indices = []

        expected_blanks, _token_total, mask_count = _expected_blanks(sentence_text, mask_indices)
        grade = _grade_sentence(expected_blanks, list(user_blanks or []))

        sched = database.record_review_item_result(
            item_id,
            email,
            score=float(grade["score"]),
            accuracy=float(grade["accuracy"]),
            coverage=float(grade["coverage"]),
            elapsed_ms=elapsed_ms,
            mask_count=mask_count,
            correct_count=int(grade["correct_count"]),
            job_id=job_id,
        )
        if not sched:
            raise HTTPException(500, "评分保存失败")

        return {
            "score": grade["score"],
            "passed": bool(grade["passed"]),
            "accuracy": grade["accuracy"],
            "coverage": grade["coverage"],
            "next_due_at": sched["due_at"],
            "interval_days": sched["interval_days"],
            "stability": sched["stability"],
            "difficulty": sched["difficulty"],
            "state": sched["state"],
            "expected_blanks": grade["expected_blanks"],
            "correct_count": int(grade["correct_count"]),
            "mask_count": int(grade["mask_count"]),
        }

    @router.patch("/api/review/items/{item_id}/mastered")
    async def patch_review_item_mastered(
        item_id: int,
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        email = str(current_user["email"])
        target = database.get_review_item(item_id, email)
        if not target:
            raise HTTPException(404, "review item not found")

        mastered = 1 if int(payload.get("mastered") or 0) else 0
        context = str(payload.get("context") or "").strip()
        job_id = str(payload.get("job_id") or "").strip() or None

        prev_mastered = int(target.get("mastered") or 0)
        ok = database.set_review_item_mastered(item_id, email, mastered)
        if not ok:
            raise HTTPException(500, "update failed")

        if context == "exam" and prev_mastered == 0 and mastered == 1:
            database.log_mastered_skip(
                item_id,
                email,
                job_id=job_id,
                item_type=str(target.get("item_type") or ""),
            )

        return {"ok": True}

    @router.get("/api/review/mastered")
    async def list_mastered_items(
        item_type: str = Query(default="", description="word/expression/sentence"),
        q: str = Query(default=""),
        limit: int = Query(default=300, ge=1, le=1000),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        email = str(current_user["email"])
        rows = database.list_mastered_review_items(
            email,
            item_type=item_type.strip() or None,
            q=q.strip() or None,
            limit=limit,
        )
        return {"items": rows}

    @router.get("/api/review/settings")
    async def get_review_settings(current_user: Dict[str, Any] = Depends(require_user)):
        email = str(current_user["email"])
        settings = database.get_review_settings(email)
        reviewed_today = database.get_today_review_count(email)
        daily_max = int(settings.get("daily_global_max") or 100)
        remaining_today = max(0, daily_max - reviewed_today)
        return {
            "daily_global_max": daily_max,
            "reviewed_today": reviewed_today,
            "remaining_today": remaining_today,
        }

    @router.patch("/api/review/settings")
    async def patch_review_settings(
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        email = str(current_user["email"])
        if "daily_global_max" not in payload:
            raise HTTPException(400, "daily_global_max is required")
        value = int(payload.get("daily_global_max") or 100)
        settings = database.update_review_settings(email, daily_global_max=value)
        reviewed_today = database.get_today_review_count(email)
        daily_max = int(settings.get("daily_global_max") or 100)
        remaining_today = max(0, daily_max - reviewed_today)
        return {
            "daily_global_max": daily_max,
            "reviewed_today": reviewed_today,
            "remaining_today": remaining_today,
        }

    # ------------------------------------------------------------------
    # Compatibility endpoints (legacy callers)
    # ------------------------------------------------------------------

    @router.get("/api/jobs/{job_id}/quiz-data")
    async def get_job_quiz_data(job_id: str, current_user: Dict[str, Any] = Depends(require_user)):
        email = str(current_user["email"])
        job = _normalize_job(get_job_or_404(job_id))
        _assert_job_owner(job, email)
        _ensure_review_bank_for_job(database, email, job, output_dir)

        rows = database.list_candidate_review_items(
            email,
            ["word", "expression"],
            scope="job",
            job_id=job_id,
        )
        words = []
        expressions = []
        for row in rows:
            out = {
                "word": row.get("display_text") or "",
                "meaning": row.get("prompt_text") or "",
            }
            if row.get("item_type") == "word":
                words.append(out)
            elif row.get("item_type") == "expression":
                expressions.append(out)

        result = _parse_result_json(job)
        return {
            "job_id": job_id,
            "job_name": job.get("name") or job.get("video_filename") or job_id[:12],
            "source_lang": job.get("source_lang") or result.get("source_lang") or "",
            "target_lang": job.get("target_lang") or result.get("target_lang") or "",
            "words": words,
            "expressions": expressions,
        }

    @router.get("/api/review-words")
    async def get_review_words_legacy(
        job_id: str = Query(default=""),
        mastered: Optional[int] = Query(default=None),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        rows = database.get_review_words(
            current_user["email"],
            job_id=(job_id.strip() or None),
            mastered=mastered,
        )
        return {"words": rows}

    @router.post("/api/review-words")
    async def add_review_words_legacy(
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        job_id = str(payload.get("job_id") or "").strip()
        words = payload.get("words") or []
        if not job_id:
            raise HTTPException(400, "job_id is required")
        if not isinstance(words, list):
            raise HTTPException(400, "words must be a list")
        added = database.add_review_words(current_user["email"], job_id, words)
        return {"ok": True, "added": added}

    @router.patch("/api/review-words/{word_id}")
    async def patch_review_words_legacy(
        word_id: int,
        payload: Dict[str, Any] = Body(default={}),
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        mastered = 1 if int(payload.get("mastered") or 0) else 0
        ok = database.update_review_word(word_id, current_user["email"], mastered)
        if not ok:
            raise HTTPException(404, "word not found")
        return {"ok": True}

    @router.delete("/api/review-words/{word_id}")
    async def delete_review_words_legacy(
        word_id: int,
        current_user: Dict[str, Any] = Depends(require_user),
    ):
        ok = database.delete_review_word(word_id, current_user["email"])
        if not ok:
            raise HTTPException(404, "word not found")
        return {"ok": True}

    return router
