from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import requests
try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

from .extractors import (
    _upsert_lexeme,
    collect_lookup_aliases,
    compute_rank,
    extract_audio,
    extract_meanings,
    extract_phonetic,
    extract_translations,
)
from .shared import (
    BuildStats,
    SUPPORTED_LANGS,
    WIKTEXTRACT_FILES,
    connect_db,
    init_schema,
    iter_wiktextract_records,
    normalize_lang_code,
    normalize_lookup_word,
    reset_schema,
)

def download_wiktextract_archives(
    data_dir: str,
    langs: Optional[Iterable[str]] = None,
    overwrite: bool = False,
    chunk_size: int = 1024 * 1024,
    show_progress: bool = True,
) -> List[str]:
    os.makedirs(data_dir, exist_ok=True)
    selected = set(normalize_lang_code(x) for x in (langs or SUPPORTED_LANGS))
    downloaded: List[str] = []

    for item in WIKTEXTRACT_FILES:
        code = item["code"]
        if code not in selected:
            continue
        dest = os.path.join(data_dir, item["filename"])
        if os.path.exists(dest) and os.path.getsize(dest) > 0 and not overwrite:
            downloaded.append(dest)
            continue

        resp = requests.get(item["url"], stream=True, timeout=(15, 600))
        resp.raise_for_status()
        total_bytes = int(resp.headers.get("content-length") or 0)
        bar = None
        if show_progress and tqdm is not None:
            bar = tqdm(
                total=total_bytes if total_bytes > 0 else None,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                dynamic_ncols=True,
                desc=f"download[{code}]",
            )
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    if bar is not None:
                        bar.update(len(chunk))
        if bar is not None:
            bar.close()
        downloaded.append(dest)

    return downloaded

def build_wiktextract_index(
    data_dir: str,
    db_path: str,
    langs: Optional[Iterable[str]] = None,
    reset: bool = False,
    show_progress: bool = True,
) -> BuildStats:
    selected = set(normalize_lang_code(x) for x in (langs or SUPPORTED_LANGS))
    files = [item for item in WIKTEXTRACT_FILES if item["code"] in selected]

    conn = connect_db(db_path)
    init_schema(conn)
    if reset:
        reset_schema(conn)

    stats = BuildStats()
    cur = conn.cursor()

    for item in files:
        src_lang = item["code"]
        file_path = os.path.join(data_dir, item["filename"])
        if not os.path.exists(file_path):
            continue

        stats.files += 1
        line_in_file = 0
        file_bar = None
        if show_progress and tqdm is not None:
            file_bar = tqdm(
                total=None,
                unit="rec",
                dynamic_ncols=True,
                desc=f"build[{src_lang}]",
            )
        for rec in iter_wiktextract_records(file_path):
            stats.lines += 1
            line_in_file += 1
            if file_bar is not None:
                file_bar.update(1)

            if rec.get("redirect") or rec.get("title") and rec.get("pos") == "hard-redirect":
                continue

            lang_code = normalize_lang_code(str(rec.get("lang_code") or ""))
            if lang_code != src_lang:
                continue

            word = str(rec.get("word") or "").strip()
            if not word:
                continue

            pos = str(rec.get("pos") or "").strip()
            if pos in {"hard-redirect", "soft-redirect"}:
                continue

            norm_word = normalize_lookup_word(word, src_lang)
            if not norm_word:
                continue

            stats.parsed += 1
            meanings = extract_meanings(rec)
            translations = extract_translations(rec, src_lang)
            if not meanings and not translations:
                continue

            phonetic = extract_phonetic(rec, src_lang)
            audio = extract_audio(rec)
            rank_score = compute_rank(meanings, translations, phonetic, audio)

            lexeme_id = _upsert_lexeme(
                cur,
                src_lang,
                word,
                norm_word,
                pos,
                phonetic,
                audio,
                meanings,
                rank_score,
            )
            stats.inserted_lexemes += 1
            stats.kept += 1

            for alias_norm, pr in collect_lookup_aliases(rec, src_lang):
                cur.execute(
                    """
                    INSERT OR IGNORE INTO lookup_index (src_lang, norm_word, lexeme_id, priority)
                    VALUES (?, ?, ?, ?)
                    """,
                    (src_lang, alias_norm, lexeme_id, pr),
                )
                if cur.rowcount > 0:
                    stats.inserted_index_rows += 1

            for tgt_lang, rows in translations.items():
                for tr in rows:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO translations
                        (lexeme_id, tgt_lang, translated_word, roman, sense, weight)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            lexeme_id,
                            tgt_lang,
                            tr["word"],
                            tr.get("roman", ""),
                            tr.get("sense", ""),
                            tr.get("weight", 0.0),
                        ),
                    )
                    if cur.rowcount > 0:
                        stats.inserted_translations += 1

            if line_in_file % 2000 == 0:
                conn.commit()
                if file_bar is not None:
                    file_bar.set_postfix(
                        parsed=stats.parsed,
                        kept=stats.kept,
                        idx=stats.inserted_index_rows,
                        tr=stats.inserted_translations,
                    )

        conn.commit()
        if file_bar is not None:
            file_bar.set_postfix(
                parsed=stats.parsed,
                kept=stats.kept,
                idx=stats.inserted_index_rows,
                tr=stats.inserted_translations,
            )
            file_bar.close()

    cur.execute(
        "INSERT OR REPLACE INTO build_meta(k, v) VALUES(?, ?)",
        (
            "last_build_at",
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        ),
    )
    conn.commit()
    conn.close()
    return stats
