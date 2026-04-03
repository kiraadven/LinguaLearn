from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from .shared import SUPPORTED_LANGS, normalize_lang_code, normalize_lookup_word

def _pick_gloss(sense: dict) -> str:
    for key in ("glosses", "raw_glosses"):
        vals = sense.get(key) or []
        if isinstance(vals, list):
            for v in vals:
                txt = str(v or "").strip()
                if txt:
                    return txt
    return ""

def _pick_example(sense: dict) -> str:
    examples = sense.get("examples") or []
    if not isinstance(examples, list):
        return ""
    for ex in examples:
        if isinstance(ex, str):
            txt = ex.strip()
            if txt:
                return txt
        elif isinstance(ex, dict):
            txt = str(ex.get("text") or "").strip()
            if txt:
                return txt
    return ""

def _pick_synonyms(sense: dict) -> List[str]:
    out: List[str] = []
    syns = sense.get("synonyms") or []
    if not isinstance(syns, list):
        return out
    for s in syns:
        if isinstance(s, str):
            w = s.strip()
        elif isinstance(s, dict):
            w = str(s.get("word") or "").strip()
        else:
            w = ""
        if w and w not in out:
            out.append(w)
        if len(out) >= 6:
            break
    return out

def extract_meanings(record: dict, max_meanings: int = 6) -> List[dict]:
    pos = str(record.get("pos") or "").strip()
    out: List[dict] = []
    senses = record.get("senses") or []
    if not isinstance(senses, list):
        return out

    for sense in senses:
        if not isinstance(sense, dict):
            continue
        definition = _pick_gloss(sense)
        if not definition:
            continue
        item = {
            "pos": pos,
            "definition": definition,
            "example": _pick_example(sense),
            "synonyms": _pick_synonyms(sense),
        }
        out.append(item)
        if len(out) >= max_meanings:
            break
    return out

def _has_tag(tags: Iterable[str], wanted: str) -> bool:
    w = wanted.lower()
    for t in tags:
        if w in str(t or "").lower():
            return True
    return False

def extract_phonetic(record: dict, source_lang: str) -> str:
    src = normalize_lang_code(source_lang)
    sounds = record.get("sounds") or []
    forms = record.get("forms") or []

    def _iter_form_roman() -> Iterator[str]:
        if not isinstance(forms, list):
            return
        for form in forms:
            if not isinstance(form, dict):
                continue
            tags = [str(t) for t in (form.get("tags") or [])]
            txt = str(form.get("form") or "").strip()
            if not txt:
                continue
            if _has_tag(tags, "roman") or _has_tag(tags, "romanization"):
                yield txt

    if src == "ko":
        for v in _iter_form_roman():
            return v

    if src == "zh" and isinstance(sounds, list):
        for s in sounds:
            if not isinstance(s, dict):
                continue
            tags = [str(t) for t in (s.get("tags") or [])]
            zh_pron = str(s.get("zh_pron") or "").strip()
            if zh_pron and _has_tag(tags, "pinyin") and (_has_tag(tags, "mandarin") or _has_tag(tags, "standard-chinese")):
                return zh_pron
        for s in sounds:
            if not isinstance(s, dict):
                continue
            tags = [str(t) for t in (s.get("tags") or [])]
            zh_pron = str(s.get("zh_pron") or "").strip()
            if zh_pron and _has_tag(tags, "pinyin"):
                return zh_pron
        for s in sounds:
            if not isinstance(s, dict):
                continue
            zh_pron = str(s.get("zh_pron") or "").strip()
            if zh_pron:
                return zh_pron

    if src == "ja" and isinstance(sounds, list):
        for s in sounds:
            if not isinstance(s, dict):
                continue
            for key in ("other", "roman", "ipa"):
                value = str(s.get(key) or "").strip()
                if value:
                    return value

    if isinstance(sounds, list):
        for s in sounds:
            if not isinstance(s, dict):
                continue
            for key in ("ipa", "enpr", "roman", "other"):
                value = str(s.get(key) or "").strip()
                if value:
                    return value

    for v in _iter_form_roman():
        return v
    return ""

def extract_audio(record: dict) -> str:
    sounds = record.get("sounds") or []
    if not isinstance(sounds, list):
        return ""

    for s in sounds:
        if not isinstance(s, dict):
            continue
        for key in ("audio", "ogg_url", "mp3_url", "wav_url", "url"):
            v = str(s.get(key) or "").strip()
            if not v:
                continue
            if v.startswith("//"):
                return "https:" + v
            if v.startswith("http://") or v.startswith("https://"):
                return v
    return ""

def _translation_lang_code(raw: str) -> Optional[str]:
    code = normalize_lang_code(raw)
    if code in SUPPORTED_LANGS:
        return code
    return None

def extract_translations(record: dict, source_lang: str) -> Dict[str, List[dict]]:
    src = normalize_lang_code(source_lang)
    out: Dict[str, List[dict]] = {}
    items = record.get("translations") or []
    if not isinstance(items, list):
        return out

    seen = set()
    for idx, tr in enumerate(items):
        if not isinstance(tr, dict):
            continue
        tgt = _translation_lang_code(str(tr.get("lang_code") or ""))
        if not tgt or tgt == src:
            continue
        word = str(tr.get("word") or "").strip()
        if not word:
            continue
        key = (tgt, word)
        if key in seen:
            continue
        seen.add(key)

        score = 1000 - idx
        if tr.get("sense"):
            score += 3
        if tr.get("roman"):
            score += 2

        out.setdefault(tgt, []).append(
            {
                "word": word,
                "roman": str(tr.get("roman") or "").strip(),
                "sense": str(tr.get("sense") or "").strip(),
                "weight": float(score),
            }
        )

    for tgt, arr in out.items():
        arr.sort(key=lambda x: x["weight"], reverse=True)
        out[tgt] = arr[:12]
    return out

def collect_lookup_aliases(record: dict, source_lang: str) -> List[Tuple[str, int]]:
    src = normalize_lang_code(source_lang)
    aliases: List[Tuple[str, int]] = []

    def _add(raw: str, priority: int) -> None:
        norm = normalize_lookup_word(raw, src)
        if not norm:
            return
        aliases.append((norm, priority))

    main_word = str(record.get("word") or "").strip()
    if main_word:
        _add(main_word, 100)

    forms = record.get("forms") or []
    if isinstance(forms, list):
        for form in forms:
            if not isinstance(form, dict):
                continue
            txt = str(form.get("form") or "").strip()
            if not txt:
                continue
            tags = [str(t or "") for t in (form.get("tags") or [])]
            low = " ".join(tags).lower()
            pr = 70
            if "canonical" in low or "hangeul" in low:
                pr = 95
            elif "romanization" in low or "roman" in low:
                pr = 60
            elif "simplified" in low or "traditional" in low:
                pr = 85
            _add(txt, pr)

    uniq: Dict[str, int] = {}
    for norm, pr in aliases:
        if pr > uniq.get(norm, -1):
            uniq[norm] = pr
    return sorted(uniq.items(), key=lambda x: (-x[1], x[0]))

def compute_rank(meanings: List[dict], translations: Dict[str, List[dict]], phonetic: str, audio: str) -> float:
    score = 0.0
    score += min(len(meanings), 6) * 5.0
    if phonetic:
        score += 3.0
    if audio:
        score += 4.0
    score += min(len(translations), 8) * 2.5
    ex_count = sum(1 for m in meanings if m.get("example"))
    score += min(ex_count, 3) * 1.5
    return score

def _entry_hash(src_lang: str, word: str, pos: str, meanings: List[dict], phonetic: str, audio: str) -> str:
    first_def = ""
    if meanings:
        first_def = str(meanings[0].get("definition") or "")
    payload = f"{src_lang}\n{word}\n{pos}\n{first_def}\n{phonetic}\n{audio}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()

def _upsert_lexeme(cur: sqlite3.Cursor, src_lang: str, word: str, norm_word: str, pos: str, phonetic: str, audio: str, meanings: List[dict], rank_score: float) -> int:
    ehash = _entry_hash(src_lang, word, pos, meanings, phonetic, audio)
    cur.execute(
        """
        INSERT OR IGNORE INTO lexemes
        (entry_hash, src_lang, word, norm_word, pos, phonetic, audio, meanings_json, rank_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ehash,
            src_lang,
            word,
            norm_word,
            pos,
            phonetic,
            audio,
            json.dumps(meanings, ensure_ascii=False),
            rank_score,
        ),
    )
    # NOTE:
    # Do not use `lastrowid` directly after INSERT OR IGNORE.
    # When a row is ignored, sqlite may keep the previous statement's lastrowid,
    # which can point to a different table and break FK inserts downstream.
    if cur.rowcount == 1 and cur.lastrowid:
        return int(cur.lastrowid)

    row = cur.execute("SELECT id FROM lexemes WHERE entry_hash=?", (ehash,)).fetchone()
    if row:
        return int(row[0])
    raise RuntimeError("failed to resolve lexeme id")

