from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover
    OpenCC = None

SUPPORTED_LANGS: Tuple[str, ...] = ("en", "zh", "ja", "ko", "de", "fr", "es", "ru")

WIKTEXTRACT_FILES: Tuple[dict, ...] = (
    {
        "code": "en",
        "name": "English",
        "filename": "raw-wiktextract-data.jsonl.gz",
        "url": "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz",
    },
    {
        "code": "zh",
        "name": "Chinese",
        "filename": "zh-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/zh/zh-extract.jsonl.gz",
    },
    {
        "code": "ja",
        "name": "Japanese",
        "filename": "ja-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/ja/ja-extract.jsonl.gz",
    },
    {
        "code": "ko",
        "name": "Korean",
        "filename": "ko-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/ko/ko-extract.jsonl.gz",
    },
    {
        "code": "de",
        "name": "German",
        "filename": "de-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/de/de-extract.jsonl.gz",
    },
    {
        "code": "fr",
        "name": "French",
        "filename": "fr-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/fr/fr-extract.jsonl.gz",
    },
    {
        "code": "es",
        "name": "Spanish",
        "filename": "es-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/es/es-extract.jsonl.gz",
    },
    {
        "code": "ru",
        "name": "Russian",
        "filename": "ru-extract.jsonl.gz",
        "url": "https://kaikki.org/dictionary/downloads/ru/ru-extract.jsonl.gz",
    },
)

_ZH_T2S = OpenCC("t2s") if OpenCC is not None else None
_ZH_S2T = OpenCC("s2t") if OpenCC is not None else None

_STRIP_EDGE_RE = re.compile(r"^[\s\"'“”‘’`~!@#$%^&*()_+\-=\[\]{};:,.<>/?，。！？；：（）【】《》、]+|[\s\"'“”‘’`~!@#$%^&*()_+\-=\[\]{};:,.<>/?，。！？；：（）【】《》、]+$")
_BASIC_T2S_MAP = {
    "學": "学", "習": "习", "體": "体", "這": "这", "個": "个", "語": "语", "轉": "转", "錄": "录",
    "視": "视", "頻": "频", "標": "标", "題": "题", "詞": "词", "彙": "汇", "總": "总", "結": "结",
    "時": "时", "間": "间", "點": "点", "對": "对", "齊": "齐", "與": "与", "為": "为", "後": "后",
    "開": "开", "發": "发", "現": "现", "測": "测", "試": "试", "請": "请", "將": "将", "寫": "写",
    "讀": "读", "聽": "听", "說": "说", "還": "还", "麼": "么", "們": "们", "從": "从", "於": "于",
    "網": "网", "頁": "页", "數": "数", "據": "据", "類": "类", "變": "变", "長": "长", "門": "门",
    "國": "国", "電": "电", "腦": "脑", "臺": "台", "灣": "湾", "華": "华", "畫": "画", "進": "进",
    "優": "优", "質": "质", "聲": "声", "處": "处", "檔": "档", "簡": "简", "貓": "猫", "龍": "龙",
}
_BASIC_S2T_MAP = {v: k for k, v in _BASIC_T2S_MAP.items()}


@dataclass

class BuildStats:
    files: int = 0
    lines: int = 0
    parsed: int = 0
    kept: int = 0
    inserted_lexemes: int = 0
    inserted_index_rows: int = 0
    inserted_translations: int = 0

def normalize_lang_code(lang: str) -> str:
    raw = str(lang or "").strip()
    if not raw:
        return "en"
    low = raw.lower()
    if low in {"zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-sg"}:
        return "zh"
    if low.startswith("ja"):
        return "ja"
    if low.startswith("ko"):
        return "ko"
    if low.startswith("de"):
        return "de"
    if low.startswith("fr"):
        return "fr"
    if low.startswith("es"):
        return "es"
    if low.startswith("ru"):
        return "ru"
    if low.startswith("en"):
        return "en"
    return low

def normalize_lookup_word(word: str, source_lang: str) -> str:
    src = normalize_lang_code(source_lang)
    text = str(word or "").replace("’", "'").strip()
    if not text:
        return ""
    text = _STRIP_EDGE_RE.sub("", text)
    text = text.strip()
    if not text:
        return ""
    if src in {"zh", "ja", "ko"}:
        return text
    return text.lower()

def convert_zh_script(text: str, script: str = "hans") -> str:
    value = str(text or "")
    if not value:
        return value
    sc = str(script or "").lower()
    if sc.startswith("hant") and _ZH_S2T is not None:
        try:
            return _ZH_S2T.convert(value)
        except Exception:
            pass
    if sc.startswith("hans") and _ZH_T2S is not None:
        try:
            return _ZH_T2S.convert(value)
        except Exception:
            pass
    if sc.startswith("hant"):
        return "".join(_BASIC_S2T_MAP.get(ch, ch) for ch in value)
    if sc.startswith("hans"):
        return "".join(_BASIC_T2S_MAP.get(ch, ch) for ch in value)
    return value

def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-200000")
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lexemes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          entry_hash TEXT NOT NULL UNIQUE,
          src_lang TEXT NOT NULL,
          word TEXT NOT NULL,
          norm_word TEXT NOT NULL,
          pos TEXT,
          phonetic TEXT,
          audio TEXT,
          meanings_json TEXT NOT NULL,
          rank_score REAL NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_lex_src_norm_rank
          ON lexemes(src_lang, norm_word, rank_score DESC, id ASC);

        CREATE TABLE IF NOT EXISTS lookup_index (
          src_lang TEXT NOT NULL,
          norm_word TEXT NOT NULL,
          lexeme_id INTEGER NOT NULL,
          priority INTEGER NOT NULL DEFAULT 0,
          UNIQUE(src_lang, norm_word, lexeme_id),
          FOREIGN KEY(lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_lookup_src_norm_priority
          ON lookup_index(src_lang, norm_word, priority DESC, lexeme_id ASC);

        CREATE TABLE IF NOT EXISTS translations (
          lexeme_id INTEGER NOT NULL,
          tgt_lang TEXT NOT NULL,
          translated_word TEXT NOT NULL,
          roman TEXT,
          sense TEXT,
          weight REAL NOT NULL DEFAULT 0,
          UNIQUE(lexeme_id, tgt_lang, translated_word),
          FOREIGN KEY(lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_trans_lex_tgt_weight
          ON translations(lexeme_id, tgt_lang, weight DESC, translated_word ASC);

        CREATE TABLE IF NOT EXISTS card_cache (
          src_lang TEXT NOT NULL,
          norm_word TEXT NOT NULL,
          tgt_lang TEXT NOT NULL,
          card_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(src_lang, norm_word, tgt_lang)
        );

        CREATE TABLE IF NOT EXISTS build_meta (
          k TEXT PRIMARY KEY,
          v TEXT NOT NULL
        );
        """
    )
    conn.commit()

def reset_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM card_cache;
        DELETE FROM translations;
        DELETE FROM lookup_index;
        DELETE FROM lexemes;
        DELETE FROM build_meta;
        """
    )
    conn.commit()

def iter_wiktextract_records(path: str) -> Iterator[dict]:
    open_func = gzip.open if path.endswith(".gz") else open
    with open_func(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj

