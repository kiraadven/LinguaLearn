from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Iterable, List, Optional

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

from .shared import (
    SUPPORTED_LANGS,
    WIKTEXTRACT_FILES,
    connect_db,
    convert_zh_script,
    normalize_lang_code,
    normalize_lookup_word,
)

_TEXT_KEY_RE = re.compile(r"[\s\.,;:!?\-_/，。；：！？、（）\[\]{}\"'`]+")
_TRANS_SPLIT_RE = re.compile(r"[;/|,，；、]+")
_TRANS_EDGE_RE = re.compile(r"^[\s\.,;:!?\-_/，。；：！？、（）\[\]{}\"'`]+|[\s\.,;:!?\-_/，。；：！？、（）\[\]{}\"'`]+$")
_WORD_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")
_ZH_CHAR_RE = re.compile(r"[\u3400-\u9FFF]")
_JA_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9FFF]")
_KO_CHAR_RE = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
_RU_CHAR_RE = re.compile(r"[А-Яа-яЁёЀ-ӿ]")
_LATIN_EXT_CHAR_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]")


def _norm_text_key(text: str) -> str:
    return _TEXT_KEY_RE.sub("", str(text or "").lower())


def _clean_synonyms(values) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen = set()
    for v in values:
        s = str(v or "").strip()
        if not s:
            continue
        k = _norm_text_key(s)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _dedupe_meanings(meanings, max_meanings: int) -> List[dict]:
    if not isinstance(meanings, list):
        return []
    out: List[dict] = []
    seen = {}
    for m in meanings:
        if not isinstance(m, dict):
            continue
        pos = str(m.get("pos") or "").strip()
        definition = str(m.get("definition") or "").strip()
        example = str(m.get("example") or "").strip()
        synonyms = _clean_synonyms(m.get("synonyms"))
        if not definition:
            continue
        key = (_norm_text_key(pos), _norm_text_key(definition))
        if key in seen:
            existing = out[seen[key]]
            if example and not existing.get("example"):
                existing["example"] = example
            if synonyms:
                existing["synonyms"] = _clean_synonyms((existing.get("synonyms") or []) + synonyms)
            continue
        seen[key] = len(out)
        out.append({
            "pos": pos,
            "definition": definition,
            "example": example,
            "synonyms": synonyms,
        })
    return out[:max(1, int(max_meanings or 4))]


def _split_translation_candidate(raw: str) -> List[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    parts = _TRANS_SPLIT_RE.split(text)
    if len(parts) <= 1:
        parts = [text]
    out: List[str] = []
    for p in parts:
        s = _TRANS_EDGE_RE.sub("", str(p or "").strip())
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            out.append(s)
    return out


def _dedupe_translation_words(words, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    max_items = max(1, int(limit or 6))
    for w in (words or []):
        for token in _split_translation_candidate(w):
            key = _norm_text_key(token)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(token)
            if len(out) >= max_items:
                return out
    return out


def _sanitize_card_payload(card: dict, max_meanings: int, translation_limit: int) -> dict:
    if not isinstance(card, dict):
        return {}
    out = dict(card)
    meanings = _dedupe_meanings(out.get("meanings"), max_meanings)
    out["meanings"] = meanings

    translated = out.get("translated_meanings")
    if not isinstance(translated, list):
        out["translated_meanings"] = []
        return out

    cleaned_lines: List[str] = []
    has_non_empty = False
    for line in translated:
        words = _dedupe_translation_words([line], translation_limit)
        text = "; ".join(words) if words else ""
        if text:
            has_non_empty = True
        cleaned_lines.append(text)
    if not meanings or not has_non_empty:
        out["translated_meanings"] = []
        return out
    if len(cleaned_lines) < len(meanings):
        cleaned_lines.extend([""] * (len(meanings) - len(cleaned_lines)))
    out["translated_meanings"] = cleaned_lines[:len(meanings)]
    return out


def _has_stale_repeated_translations(card: dict) -> bool:
    if not isinstance(card, dict):
        return False
    meanings = card.get("meanings") or []
    translated = card.get("translated_meanings") or []
    if not isinstance(meanings, list) or not isinstance(translated, list):
        return False
    if len(meanings) <= 1:
        return False
    non_empty = [str(x or "").strip() for x in translated if str(x or "").strip()]
    if len(non_empty) <= 1:
        return False
    return len(set(non_empty)) == 1


def _word_matches_target_lang(word: str, target_lang: str) -> bool:
    text = str(word or "").strip()
    if not text:
        return False
    tgt = normalize_lang_code(target_lang)
    if tgt == "zh":
        return bool(_ZH_CHAR_RE.search(text))
    if tgt == "ja":
        return bool(_JA_CHAR_RE.search(text))
    if tgt == "ko":
        return bool(_KO_CHAR_RE.search(text))
    if tgt == "ru":
        return bool(_RU_CHAR_RE.search(text))
    if tgt in {"en", "de", "fr", "es"}:
        return bool(_LATIN_EXT_CHAR_RE.search(text))
    return True


def _sense_tokens(text: str) -> set:
    return {x.lower() for x in _WORD_TOKEN_RE.findall(str(text or ""))}


def _sense_match_score(definition: str, sense: str) -> float:
    d = str(definition or "").strip()
    s = str(sense or "").strip()
    if not d or not s:
        return 0.0
    d_key = _norm_text_key(d)
    s_key = _norm_text_key(s)
    if not d_key or not s_key:
        return 0.0
    if d_key == s_key:
        return 1000.0
    d_tokens = _sense_tokens(d)
    s_tokens = _sense_tokens(s)
    if not d_tokens or not s_tokens:
        return 0.0
    overlap = len(d_tokens & s_tokens)
    if overlap <= 0:
        return 0.0
    return float(overlap) / max(1.0, float(len(s_tokens)))


def _build_translated_meanings_from_rows(meanings: List[dict], rows: List[sqlite3.Row], target_lang: str, translation_limit: int) -> List[str]:
    if not meanings:
        return []

    m_count = len(meanings)
    by_meaning: List[List[tuple]] = [[] for _ in range(m_count)]
    generic: List[tuple] = []

    for row in rows:
        word = str(row["translated_word"] or "").strip()
        if not word or not _word_matches_target_lang(word, target_lang):
            continue
        sense = str(row["sense"] or "").strip()
        weight = float(row["weight"] or 0.0)

        if sense:
            best_idx = -1
            best_score = 0.0
            for idx, m in enumerate(meanings):
                score = _sense_match_score(str(m.get("definition") or ""), sense)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0 and best_score > 0:
                by_meaning[best_idx].append((word, best_score, weight))
                continue
        generic.append((word, 0.0, weight))

    for idx in range(m_count):
        by_meaning[idx].sort(key=lambda x: (x[1], x[2], _norm_text_key(x[0])), reverse=True)
    generic.sort(key=lambda x: (x[2], _norm_text_key(x[0])), reverse=True)

    lines: List[str] = []
    used_global = set()
    generic_unique: List[str] = []
    generic_seen = set()

    # For multi-meaning entries, keep only one primary translation per meaning and
    # spill the rest into a shared fallback pool for other meanings.
    overflow_pool: List[str] = []
    if m_count > 1:
        for bucket in by_meaning:
            for item in bucket[1:]:
                overflow_pool.append(str(item[0] or "").strip())

    for word in overflow_pool:
        key = _norm_text_key(word)
        if not key or key in generic_seen:
            continue
        generic_seen.add(key)
        generic_unique.append(word)

    for word, _, _ in generic:
        key = _norm_text_key(word)
        if not key or key in generic_seen:
            continue
        generic_seen.add(key)
        generic_unique.append(word)
    generic_idx = 0
    max_items = max(1, int(translation_limit or 6))
    for idx in range(m_count):
        selected: List[str] = []
        seen_local = set()
        primary_take = max_items if m_count == 1 else 1
        for word, _, _ in by_meaning[idx]:
            key = _norm_text_key(word)
            if not key or key in seen_local:
                continue
            selected.append(word)
            seen_local.add(key)
            used_global.add(key)
            if len(selected) >= primary_take:
                break
        if not selected:
            fallback_take = max_items if m_count == 1 else 1
            while generic_idx < len(generic_unique) and len(selected) < fallback_take:
                word = generic_unique[generic_idx]
                generic_idx += 1
                key = _norm_text_key(word)
                if not key or key in seen_local or key in used_global:
                    continue
                selected.append(word)
                seen_local.add(key)
                used_global.add(key)
        lines.append("; ".join(selected) if selected else "")
    return lines

def _pick_best_candidate(cur: sqlite3.Cursor, src_lang: str, norm_word: str, tgt_lang: str) -> Optional[sqlite3.Row]:
    rows = cur.execute(
        """
        SELECT l.*, li.priority
          FROM lookup_index li
          JOIN lexemes l ON l.id = li.lexeme_id
         WHERE li.src_lang = ? AND li.norm_word = ?
         ORDER BY li.priority DESC, l.rank_score DESC, l.id ASC
         LIMIT 12
        """,
        (src_lang, norm_word),
    ).fetchall()
    if not rows:
        return None

    best_row = None
    best_score = None
    for r in rows:
        tr_count = cur.execute(
            "SELECT COUNT(1) FROM translations WHERE lexeme_id=? AND tgt_lang=?",
            (r["id"], tgt_lang),
        ).fetchone()[0]
        score = (int(tr_count) > 0, tr_count, float(r["rank_score"]))
        if best_score is None or score > best_score:
            best_score = score
            best_row = r
    return best_row

def _apply_zh_script_to_card(card: dict, src_lang: str, tgt_lang: str, zh_script: str) -> dict:
    sc = str(zh_script or "").lower()
    if not sc.startswith("hans") and not sc.startswith("hant"):
        return card

    out = dict(card)
    if src_lang == "zh":
        out["word"] = convert_zh_script(out.get("word", ""), sc)
        converted_meanings = []
        for m in out.get("meanings", []):
            mm = dict(m)
            mm["definition"] = convert_zh_script(mm.get("definition", ""), sc)
            mm["example"] = convert_zh_script(mm.get("example", ""), sc)
            mm["synonyms"] = [convert_zh_script(s, sc) for s in (mm.get("synonyms") or [])]
            converted_meanings.append(mm)
        out["meanings"] = converted_meanings

    if tgt_lang == "zh":
        out["translated_meanings"] = [convert_zh_script(v, sc) for v in (out.get("translated_meanings") or [])]

    return out

def _pivot_translate_via_english(
    cur: sqlite3.Cursor,
    src_lexeme_id: int,
    target_lang: str,
    limit: int = 6,
) -> List[str]:
    tgt = normalize_lang_code(target_lang)
    if tgt == "en":
        return []

    seed_rows = cur.execute(
        """
        SELECT translated_word
          FROM translations
         WHERE lexeme_id=? AND tgt_lang='en'
         ORDER BY weight DESC, translated_word ASC
         LIMIT 12
        """,
        (src_lexeme_id,),
    ).fetchall()
    seeds = [str(r[0]) for r in seed_rows if str(r[0] or "").strip()]
    if not seeds:
        return []

    out: List[str] = []
    seen = set()
    for seed in seeds:
        norm = normalize_lookup_word(seed, "en")
        if not norm:
            continue
        en_row = _pick_best_candidate(cur, "en", norm, tgt)
        if not en_row:
            continue
        rows = cur.execute(
            """
            SELECT translated_word
              FROM translations
             WHERE lexeme_id=? AND tgt_lang=?
             ORDER BY weight DESC, translated_word ASC
             LIMIT ?
            """,
            (en_row["id"], tgt, limit),
        ).fetchall()
        for r in rows:
            w = str(r[0] or "").strip()
            if not w or w in seen:
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                return out
    return out


def _bridge_language_order(src_lang: str, target_lang: str) -> List[str]:
    src = normalize_lang_code(src_lang)
    tgt = normalize_lang_code(target_lang)
    preferred = ["en", "fr", "es", "de", "ru", "ja", "ko", "zh"]
    out = []
    for lang in preferred:
        if lang in {src, tgt}:
            continue
        if lang in SUPPORTED_LANGS:
            out.append(lang)
    for lang in SUPPORTED_LANGS:
        if lang in {src, tgt} or lang in out:
            continue
        out.append(lang)
    return out


def _pivot_translate_multi_hop(
    cur: sqlite3.Cursor,
    src_lexeme_id: int,
    src_lang: str,
    target_lang: str,
    limit: int = 6,
) -> List[str]:
    src = normalize_lang_code(src_lang)
    tgt = normalize_lang_code(target_lang)
    if src == tgt:
        return []

    bridges = _bridge_language_order(src, tgt)
    if not bridges:
        return []

    placeholders = ",".join("?" for _ in bridges)
    seed_rows = cur.execute(
        f"""
        SELECT tgt_lang, translated_word, weight
          FROM translations
         WHERE lexeme_id=? AND tgt_lang IN ({placeholders})
         ORDER BY weight DESC, translated_word ASC
         LIMIT 60
        """,
        (src_lexeme_id, *bridges),
    ).fetchall()
    if not seed_rows:
        return []

    out: List[str] = []
    seen = set()
    for seed in seed_rows:
        bridge_lang = str(seed["tgt_lang"] or "").strip()
        bridge_word = str(seed["translated_word"] or "").strip()
        if not bridge_lang or not bridge_word:
            continue
        norm = normalize_lookup_word(bridge_word, bridge_lang)
        if not norm:
            continue
        bridge_row = _pick_best_candidate(cur, bridge_lang, norm, tgt)
        if not bridge_row:
            continue
        rows = cur.execute(
            """
            SELECT translated_word
              FROM translations
             WHERE lexeme_id=? AND tgt_lang=?
             ORDER BY weight DESC, translated_word ASC
             LIMIT ?
            """,
            (bridge_row["id"], tgt, limit),
        ).fetchall()
        for r in rows:
            w = str(r[0] or "").strip()
            if not w or w in seen:
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                return out
    return out

def _cache_tgt_key(src_lang: str, tgt_lang: str, zh_script: str) -> str:
    src = normalize_lang_code(src_lang)
    tgt = normalize_lang_code(tgt_lang)
    if src != "zh" and tgt != "zh":
        return tgt
    sc = str(zh_script or "").lower()
    sc = "hant" if sc.startswith("hant") else "hans"
    return f"{tgt}#{sc}"

def lookup_card(
    db_path: str,
    word: str,
    source_lang: str,
    target_lang: str,
    zh_script: str = "hans",
    max_meanings: int = 4,
    translation_limit: int = 6,
    use_cache: bool = True,
) -> Optional[dict]:
    src = normalize_lang_code(source_lang)
    tgt = normalize_lang_code(target_lang)
    if src not in SUPPORTED_LANGS or tgt not in SUPPORTED_LANGS:
        return None

    norm_word = normalize_lookup_word(word, src)
    if not norm_word:
        return None

    conn = connect_db(db_path)
    cur = conn.cursor()
    cache_tgt = _cache_tgt_key(src, tgt, zh_script)

    if use_cache:
        row = cur.execute(
            "SELECT card_json FROM card_cache WHERE src_lang=? AND norm_word=? AND tgt_lang=?",
            (src, norm_word, cache_tgt),
        ).fetchone()
        if row:
            try:
                cached_card = json.loads(row[0])
                cached_card = _sanitize_card_payload(
                    cached_card,
                    max_meanings=max_meanings,
                    translation_limit=translation_limit,
                )
                if _has_stale_repeated_translations(cached_card):
                    raise ValueError("stale repeated translations in cache")
                cached_trans = cached_card.get("translated_meanings") if isinstance(cached_card, dict) else None
                if src == tgt or (isinstance(cached_trans, list) and any(str(x or "").strip() for x in cached_trans)):
                    try:
                        cur.execute(
                            """
                            INSERT OR REPLACE INTO card_cache(src_lang, norm_word, tgt_lang, card_json, updated_at)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """,
                            (src, norm_word, cache_tgt, json.dumps(cached_card, ensure_ascii=False)),
                        )
                        conn.commit()
                    except Exception:
                        pass
                    conn.close()
                    return cached_card
            except Exception:
                pass

    candidate = _pick_best_candidate(cur, src, norm_word, tgt)
    if not candidate:
        conn.close()
        return None

    meanings = []
    try:
        meanings = json.loads(candidate["meanings_json"] or "[]")
    except Exception:
        meanings = []
    meanings = _dedupe_meanings(meanings, max_meanings=max_meanings)

    tr_rows = cur.execute(
        """
        SELECT translated_word, sense, weight
          FROM translations
         WHERE lexeme_id=? AND tgt_lang=?
         ORDER BY weight DESC, translated_word ASC
         LIMIT ?
        """,
        (candidate["id"], tgt, max(24, int(translation_limit or 6) * 6)),
    ).fetchall()
    translated_words = [str(r["translated_word"] or "").strip() for r in tr_rows if str(r["translated_word"] or "").strip()]
    if not translated_words and src != tgt:
        translated_words = _pivot_translate_via_english(
            cur=cur,
            src_lexeme_id=int(candidate["id"]),
            target_lang=tgt,
            limit=translation_limit,
        )
    if not translated_words and src != tgt:
        translated_words = _pivot_translate_multi_hop(
            cur=cur,
            src_lexeme_id=int(candidate["id"]),
            src_lang=src,
            target_lang=tgt,
            limit=translation_limit,
        )
    translated_words = _dedupe_translation_words(translated_words, translation_limit)

    translated_meanings = _build_translated_meanings_from_rows(
        meanings=meanings,
        rows=tr_rows,
        target_lang=tgt,
        translation_limit=translation_limit,
    )
    if not any(str(x or "").strip() for x in translated_meanings) and translated_words:
        translated_line = "; ".join(translated_words[:translation_limit])
        translated_meanings = [translated_line] + [""] * max(0, len(meanings) - 1)
    elif src == tgt and not any(str(x or "").strip() for x in translated_meanings):
        translated_meanings = [str(m.get("definition") or "") for m in meanings]

    card = {
        "word": candidate["word"],
        "phonetic": candidate["phonetic"] or "",
        "audio": candidate["audio"] or "",
        "meanings": meanings,
        "translated_meanings": translated_meanings,
    }
    card = _sanitize_card_payload(card, max_meanings=max_meanings, translation_limit=translation_limit)
    card = _apply_zh_script_to_card(card, src, tgt, zh_script)
    card = _sanitize_card_payload(card, max_meanings=max_meanings, translation_limit=translation_limit)

    if use_cache:
        cur.execute(
            """
            INSERT OR REPLACE INTO card_cache(src_lang, norm_word, tgt_lang, card_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (src, norm_word, cache_tgt, json.dumps(card, ensure_ascii=False)),
        )
        conn.commit()

    conn.close()
    return card


def upsert_cached_card(
    db_path: str,
    word: str,
    source_lang: str,
    target_lang: str,
    card: dict,
    zh_script: str = "hans",
    max_meanings: int = 4,
    translation_limit: int = 6,
) -> bool:
    if not db_path or not isinstance(card, dict):
        return False
    src = normalize_lang_code(source_lang)
    tgt = normalize_lang_code(target_lang)
    if src not in SUPPORTED_LANGS or tgt not in SUPPORTED_LANGS:
        return False

    norm_word = normalize_lookup_word(word, src)
    if not norm_word:
        return False

    cache_tgt = _cache_tgt_key(src, tgt, zh_script)
    payload = _sanitize_card_payload(card, max_meanings=max_meanings, translation_limit=translation_limit)
    payload = _apply_zh_script_to_card(payload, src, tgt, zh_script)
    payload = _sanitize_card_payload(payload, max_meanings=max_meanings, translation_limit=translation_limit)
    if not payload.get("meanings"):
        return False

    conn = connect_db(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO card_cache(src_lang, norm_word, tgt_lang, card_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (src, norm_word, cache_tgt, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def precompute_cache(
    db_path: str,
    src_langs: Optional[Iterable[str]] = None,
    tgt_langs: Optional[Iterable[str]] = None,
    limit_per_src: int = 20000,
    zh_script: str = "hans",
    show_progress: bool = True,
) -> int:
    src_set = [normalize_lang_code(x) for x in (src_langs or SUPPORTED_LANGS) if normalize_lang_code(x) in SUPPORTED_LANGS]
    tgt_set = [normalize_lang_code(x) for x in (tgt_langs or SUPPORTED_LANGS) if normalize_lang_code(x) in SUPPORTED_LANGS]

    conn = connect_db(db_path)
    cur = conn.cursor()
    total = 0

    scan_rows = cur.execute(
        """
        SELECT src_lang, COUNT(DISTINCT norm_word) AS cnt
          FROM lookup_index
         WHERE src_lang IN ({})
         GROUP BY src_lang
        """.format(",".join("?" for _ in src_set)),
        tuple(src_set),
    ).fetchall() if src_set else []
    src_word_counts = {str(r[0]): int(r[1] or 0) for r in scan_rows}
    total_steps = sum(min(limit_per_src, src_word_counts.get(src, 0)) * len(tgt_set) for src in src_set)
    bar = None
    if show_progress and tqdm is not None:
        bar = tqdm(
            total=total_steps if total_steps > 0 else None,
            unit="card",
            dynamic_ncols=True,
            desc="precompute",
        )

    for src in src_set:
        norms = cur.execute(
            """
            SELECT norm_word
              FROM lookup_index
             WHERE src_lang=?
             GROUP BY norm_word
             ORDER BY MIN(rowid)
             LIMIT ?
            """,
            (src, limit_per_src),
        ).fetchall()
        words = [r[0] for r in norms]
        for norm_word in words:
            for tgt in tgt_set:
                cache_tgt = _cache_tgt_key(src, tgt, zh_script)
                row = cur.execute(
                    "SELECT card_json FROM card_cache WHERE src_lang=? AND norm_word=? AND tgt_lang=?",
                    (src, norm_word, cache_tgt),
                ).fetchone()
                if row:
                    if bar is not None:
                        bar.update(1)
                    continue
                # Use norm_word as lookup token; for indexed languages this is already normalized.
                card = lookup_card(
                    db_path=db_path,
                    word=norm_word,
                    source_lang=src,
                    target_lang=tgt,
                    zh_script=zh_script,
                    use_cache=True,
                )
                if card:
                    total += 1
                if bar is not None:
                    bar.update(1)
                    bar.set_postfix(created=total)

    if bar is not None:
        bar.close()
    conn.close()
    return total

def resolve_data_files(data_dir: str, langs: Optional[Iterable[str]] = None) -> List[str]:
    selected = set(normalize_lang_code(x) for x in (langs or SUPPORTED_LANGS))
    paths = []
    for item in WIKTEXTRACT_FILES:
        if item["code"] not in selected:
            continue
        p = os.path.join(data_dir, item["filename"])
        if os.path.exists(p):
            paths.append(p)
    return paths
