"""Dictionary lookup router and helpers.
Extracted from api.py to keep the main API entry concise.
"""
import asyncio
import html
import os
import re
import time
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException

import config
try:
    from core.app.oxford_client import OxfordLookupError, lookup_word_entry as _lookup_oxford_word_entry
except Exception:
    OxfordLookupError = RuntimeError
    _lookup_oxford_word_entry = None

try:
    from core.wiktextract import (
        lookup_card as _lookup_wiktextract_card,
        upsert_cached_card as _upsert_wiktextract_cached_card,
    )
except Exception:
    _lookup_wiktextract_card = None
    _upsert_wiktextract_cached_card = None

try:
    from pypinyin import lazy_pinyin, pinyin as pinyin_choices, Style as PinyinStyle
except Exception:
    lazy_pinyin = None
    pinyin_choices = None
    PinyinStyle = None

try:
    from opencc import OpenCC
except Exception:
    OpenCC = None

try:
    from pykakasi import kakasi as _pykakasi_factory
except Exception:
    _pykakasi_factory = None

try:
    from wiktionaryparser import WiktionaryParser
except Exception:
    WiktionaryParser = None

router = APIRouter()

_DICT_SUPPORTED_LANGS = {"en", "zh", "zh-Hans", "zh-Hant", "ja", "ko", "de", "fr", "es", "ru"}
_WIKTIONARY_API_ENDPOINTS = {
    "en": "https://en.wiktionary.org/w/api.php",
    "zh": "https://zh.wiktionary.org/w/api.php",
    "ja": "https://ja.wiktionary.org/w/api.php",
    "ko": "https://ko.wiktionary.org/w/api.php",
    "de": "https://de.wiktionary.org/w/api.php",
    "fr": "https://fr.wiktionary.org/w/api.php",
    "es": "https://es.wiktionary.org/w/api.php",
    "ru": "https://ru.wiktionary.org/w/api.php",
}
_WIKTIONARY_LANG_SECTION_TITLES = {
    "en": ["English", "英语", "英語"],
    "zh": ["中文", "汉语", "漢語", "华语", "華語", "普通话", "普通話", "官话", "國語", "Chinese", "Mandarin"],
    "ja": ["日本語", "Japanese", "日语", "日語"],
    "ko": ["한국어", "朝鮮語", "韓國語", "Korean", "韩语", "韓語"],
    "de": ["Deutsch", "German", "德语", "德語"],
    "fr": ["Français", "French", "法语", "法語"],
    "es": ["Español", "Spanish", "西班牙语", "西班牙語"],
    "ru": ["Русский", "Russian", "俄语", "俄語"],
}
_WIKTIONARY_HEADERS = {"User-Agent": "LinguaLearn/2.1 (+MediaWiki lookup)"}
_WIKTIONARYPARSER_LANGUAGE_NAMES = {
    "en": "english",
    "zh": "chinese",
    "ja": "japanese",
    "ko": "korean",
    "de": "german",
    "fr": "french",
    "es": "spanish",
    "ru": "russian",
}
_DICT_LOOKUP_CACHE: dict = {}
_DICT_LOOKUP_CACHE_MAX = 2000
_DICT_REMOTE_LOOKUP_TIMEOUT_SEC = float(getattr(config, "DICT_REMOTE_LOOKUP_TIMEOUT_SEC", 1.2) or 1.2)
_DICT_TRANSLATE_TIMEOUT_SEC = float(getattr(config, "DICT_TRANSLATE_TIMEOUT_SEC", 1.5) or 1.5)
_DICT_ENABLE_REMOTE_FALLBACK = bool(getattr(config, "DICT_ENABLE_REMOTE_FALLBACK", False))
_DICT_ENABLE_LLM_TRANSLATION = bool(getattr(config, "DICT_ENABLE_LLM_TRANSLATION", True))
_DICT_ENABLE_OXFORD = bool(getattr(config, "DICT_ENABLE_OXFORD", True))
_DICT_ONLY_OXFORD = bool(getattr(config, "DICT_ONLY_OXFORD", False))
_DICT_PROVIDER_MODE_RAW = str(getattr(config, "DICT_PROVIDER_MODE", "") or "").strip().lower()
_OXFORD_BASE_URL = str(getattr(config, "OXFORD_BASE_URL", "https://od-api-sandbox.oxforddictionaries.com/api/v2") or "").strip()
_OXFORD_APP_ID = str(getattr(config, "OXFORD_APP_ID", "") or "").strip()
_OXFORD_APP_KEY = str(getattr(config, "OXFORD_APP_KEY", "") or "").strip()
_OXFORD_ENGLISH_DATASET = str(getattr(config, "OXFORD_ENGLISH_DATASET", "en-gb") or "en-gb").strip()
_OXFORD_TIMEOUT_SEC = float(getattr(config, "OXFORD_TIMEOUT_SEC", 3.0) or 3.0)
_LLM_TRANSLATE_FAILURES = 0
_LLM_TRANSLATE_DISABLED_UNTIL = 0.0
_ZH_T2S_CONVERTER = None
if OpenCC is not None:
    try:
        _ZH_T2S_CONVERTER = OpenCC("t2s")
    except Exception:
        _ZH_T2S_CONVERTER = None


def _resolve_dict_provider_mode() -> str:
    # Supported modes:
    # - oxford: only Oxford API
    # - wiktextract: only local wiktextract DB
    if _DICT_PROVIDER_MODE_RAW in {"oxford", "wiktextract"}:
        return _DICT_PROVIDER_MODE_RAW
    # Backward compatibility with old boolean flags
    if _DICT_ONLY_OXFORD:
        return "oxford"
    if not _DICT_ENABLE_OXFORD:
        return "wiktextract"
    return "oxford"


_DICT_PROVIDER_MODE = _resolve_dict_provider_mode()


def _normalize_translated_meanings(values, max_len: int) -> list:
    if not isinstance(values, list):
        return []
    out = []
    has_non_empty = False
    for v in values[:max(0, int(max_len or 0))]:
        text = str(v or "").strip()
        if text:
            has_non_empty = True
        out.append(text)
    if not has_non_empty:
        return []
    return out


def _align_translated_meanings(meanings: list, translated: list) -> list:
    total = len(meanings or [])
    if total <= 0:
        return []
    tr = _normalize_translated_meanings(translated, total)
    if not tr:
        return []
    return tr[:total]


_TRANS_TOKEN_SPLIT_RE = re.compile(r"[;/|,，；、]+")


def _extract_translation_tokens(translated_meanings: list) -> list:
    tokens = []
    for line in (translated_meanings or []):
        text = str(line or "").strip()
        if not text:
            continue
        parts = _TRANS_TOKEN_SPLIT_RE.split(text)
        if len(parts) <= 1:
            parts = [text]
        for p in parts:
            t = str(p or "").strip()
            if t:
                tokens.append(t)
    return tokens


def _is_low_quality_translations(translated_meanings: list, target_lang_norm: str) -> bool:
    tokens = _extract_translation_tokens(translated_meanings)
    if not tokens:
        return True

    # For Chinese output, reject character-level noisy pivots like: 虫; 太; 到; 页
    if target_lang_norm == "zh":
        zh_tokens = [t for t in tokens if re.search(r"[\u3400-\u9FFF]", t)]
        if len(zh_tokens) < max(1, len(tokens) // 2):
            return True
        one_char_zh = [t for t in zh_tokens if len(t) == 1]
        multi_char_zh = [t for t in zh_tokens if len(t) >= 2]
        if len(multi_char_zh) == 0 and len(one_char_zh) >= 3:
            return True
        if len(one_char_zh) >= 4 and len(multi_char_zh) <= 1:
            return True

    # Generic guard: mostly single-character fragments are usually low quality.
    if sum(1 for t in tokens if len(t) == 1) >= max(3, int(len(tokens) * 0.8)):
        return True
    return False


def _needs_translation_refresh(result: dict, src_norm: str, tgt_norm: str) -> bool:
    if src_norm == tgt_norm:
        return False
    meanings = (result or {}).get("meanings") or []
    if not meanings:
        return False
    if not _should_translate_meanings(meanings, tgt_norm):
        return False
    translated = (result or {}).get("translated_meanings") or []
    if not translated:
        return True
    return _is_low_quality_translations(translated, tgt_norm)


def _resolve_wiktextract_db_path() -> str:
    return str(getattr(config, "WIKTEXTRACT_DB_PATH", "data/wiktextract_trans.sqlite3") or "").strip()


def _should_use_remote_fallback() -> bool:
    if _DICT_ENABLE_REMOTE_FALLBACK:
        return True
    db_path = _resolve_wiktextract_db_path()
    return not (db_path and os.path.exists(db_path))


def _should_use_oxford() -> bool:
    return (
        _DICT_ENABLE_OXFORD and
        bool(_OXFORD_APP_ID) and
        bool(_OXFORD_APP_KEY) and
        _lookup_oxford_word_entry is not None
    )


def _should_use_wiktextract() -> bool:
    if _lookup_wiktextract_card is None:
        return False
    db_path = _resolve_wiktextract_db_path()
    return bool(db_path and os.path.exists(db_path))


def _validate_provider_ready() -> None:
    if _DICT_PROVIDER_MODE == "oxford" and not _should_use_oxford():
        raise HTTPException(503, "词典模式=oxford，但 Oxford 凭证未配置或服务不可用")
    if _DICT_PROVIDER_MODE == "wiktextract" and not _should_use_wiktextract():
        raise HTTPException(503, "词典模式=wiktextract，但本地词典库不可用（请先构建数据库）")


def _resolve_zh_script(source_lang: str, target_lang: str) -> str:
    src_low = str(source_lang or "").lower()
    tgt_low = str(target_lang or "").lower()
    if src_low.startswith("zh-hant") or tgt_low.startswith("zh-hant"):
        return "hant"
    return "hans"


def _lookup_local_wiktextract_sync(word: str, source_lang: str, target_lang: str) -> Optional[dict]:
    if _lookup_wiktextract_card is None:
        return None
    db_path = _resolve_wiktextract_db_path()
    if not db_path or not os.path.exists(db_path):
        return None
    try:
        return _lookup_wiktextract_card(
            db_path=db_path,
            word=word,
            source_lang=source_lang,
            target_lang=target_lang,
            zh_script=_resolve_zh_script(source_lang, target_lang),
            use_cache=True,
        )
    except Exception as e:
        print(f"⚠️ 本地词典查询失败: {e}")
        return None


async def _lookup_local_wiktextract_entry(word: str, source_lang: str, target_lang: str) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _lookup_local_wiktextract_sync, word, source_lang, target_lang)


def _lookup_oxford_sync(word: str, source_lang: str) -> Optional[dict]:
    if not _should_use_oxford():
        return None
    try:
        return _lookup_oxford_word_entry(
            word=word,
            source_lang=source_lang,
            app_id=_OXFORD_APP_ID,
            app_key=_OXFORD_APP_KEY,
            base_url=_OXFORD_BASE_URL,
            english_dataset=_OXFORD_ENGLISH_DATASET,
            timeout_sec=_OXFORD_TIMEOUT_SEC,
            strict_match=True,
        )
    except OxfordLookupError as e:
        if int(getattr(e, "status_code", 0) or 0) not in {404}:
            print(f"⚠️ Oxford 查询失败: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Oxford 查询异常: {e}")
        return None


async def _lookup_oxford_entry(word: str, source_lang: str) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _lookup_oxford_sync, word, source_lang)


def _persist_local_wiktextract_cache_sync(lookup_word: str, source_lang: str, target_lang: str, result: dict) -> bool:
    if _upsert_wiktextract_cached_card is None or not isinstance(result, dict):
        return False
    db_path = _resolve_wiktextract_db_path()
    if not db_path or not os.path.exists(db_path):
        return False
    try:
        payload = {
            "word": result.get("word", lookup_word),
            "phonetic": result.get("phonetic", ""),
            "audio": result.get("audio", ""),
            "meanings": result.get("meanings", []),
            "translated_meanings": result.get("translated_meanings", []),
        }
        return bool(_upsert_wiktextract_cached_card(
            db_path=db_path,
            word=lookup_word,
            source_lang=source_lang,
            target_lang=target_lang,
            card=payload,
            zh_script=_resolve_zh_script(source_lang, target_lang),
            max_meanings=max(1, len(payload.get("meanings") or [])),
            translation_limit=max(6, len(payload.get("translated_meanings") or [])),
        ))
    except Exception as e:
        print(f"⚠️ 本地词典缓存写回失败: {e}")
        return False


async def _persist_local_wiktextract_cache(lookup_word: str, source_lang: str, target_lang: str, result: dict) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _persist_local_wiktextract_cache_sync, lookup_word, source_lang, target_lang, result)


def _normalize_lang_for_dict(lang: str) -> str:
    raw = (lang or "").strip()
    if not raw:
        return "en"
    low = raw.lower()
    if low.startswith("zh"):
        return "zh"
    aliases = getattr(config, "LANGUAGE_CODE_ALIASES", {})
    if raw in aliases:
        return aliases[raw]
    if low in aliases:
        return aliases[low]
    return low


def _normalize_section_title(title: str) -> str:
    return re.sub(r"[\s\-\(\)\[\]\{\}（）【】《》·•.,，。:：;；!！?？\"'`]+", "", str(title or "")).lower()


def _dict_cache_get(cache_key: str):
    if cache_key not in _DICT_LOOKUP_CACHE:
        return False, None
    return True, _DICT_LOOKUP_CACHE.get(cache_key)


def _dict_cache_set(cache_key: str, value):
    if cache_key in _DICT_LOOKUP_CACHE:
        _DICT_LOOKUP_CACHE[cache_key] = value
        return
    if len(_DICT_LOOKUP_CACHE) >= _DICT_LOOKUP_CACHE_MAX:
        try:
            _DICT_LOOKUP_CACHE.pop(next(iter(_DICT_LOOKUP_CACHE)))
        except Exception:
            _DICT_LOOKUP_CACHE.clear()
    _DICT_LOOKUP_CACHE[cache_key] = value


def _iter_wiktionary_sites(source_lang_norm: str) -> list:
    src = source_lang_norm if source_lang_norm in _WIKTIONARY_API_ENDPOINTS else "en"
    sites = [src]
    if src != "en":
        sites.append("en")
    return sites


def _clean_lookup_word(word: str, source_lang_norm: str) -> str:
    raw = html.unescape(str(word or "")).strip()
    if not raw:
        return ""
    raw = re.sub(
        r"^[\s\"'“”‘’`~!@#$%^&*()_+\-=\[\]{};:,.<>/?，。！？；：（）【】《》、]+|[\s\"'“”‘’`~!@#$%^&*()_+\-=\[\]{};:,.<>/?，。！？；：（）【】《》、]+$",
        "",
        raw,
    )
    if source_lang_norm == "zh":
        raw = raw.replace(" ", "")
    return raw.strip()


def _mediawiki_get_json(api_url: str, params: dict) -> dict:
    timeout = max(0.5, min(8.0, float(_DICT_REMOTE_LOOKUP_TIMEOUT_SEC)))
    resp = requests.get(api_url, params=params, headers=_WIKTIONARY_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _mediawiki_parse_page(api_url: str, page_title: str, section: Optional[str] = None) -> Optional[dict]:
    params = {
        "action": "parse",
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
        "prop": "sections|wikitext",
        "page": page_title,
    }
    if section is not None:
        params["section"] = str(section)
    try:
        data = _mediawiki_get_json(api_url, params)
    except Exception:
        return None
    if data.get("error"):
        return None
    return data.get("parse")


def _mediawiki_search_title(api_url: str, query_word: str) -> Optional[str]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srlimit": 5,
        "srsearch": query_word,
    }
    try:
        data = _mediawiki_get_json(api_url, params)
    except Exception:
        return None
    items = (data.get("query") or {}).get("search") or []
    if not items:
        return None
    needle = query_word.strip().lower()
    for item in items:
        title = (item or {}).get("title", "")
        if title.strip().lower() == needle:
            return title
    return (items[0] or {}).get("title")


def _strip_html_tags(text: str) -> str:
    cleaned = re.sub(r"<ref[^>]*>.*?</ref>", " ", str(text or ""), flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\[[0-9]+\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _strip_wiki_markup(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"<ref[^>]*>.*?</ref>", " ", s, flags=re.I | re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", " ", s)
    s = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"''+", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ;,")


def _is_level2_heading(line: str) -> bool:
    s = str(line or "").strip()
    return s.startswith("==") and s.endswith("==") and not s.startswith("===") and not s.endswith("===")


def _is_level3_heading(line: str) -> bool:
    s = str(line or "").strip()
    return s.startswith("===") and s.endswith("===") and not s.startswith("====") and not s.endswith("====")


def _extract_language_wikitext_block(wikitext: str, source_lang_norm: str, site_lang: str) -> str:
    if not wikitext:
        return ""
    lines = str(wikitext).splitlines()
    wanted = _WIKTIONARY_LANG_SECTION_TITLES.get(source_lang_norm) or _WIKTIONARY_LANG_SECTION_TITLES.get("en", [])
    wanted_norm = {_normalize_section_title(x) for x in wanted}

    sections = []
    for idx, line in enumerate(lines):
        if not _is_level2_heading(line):
            continue
        title = _normalize_section_title(line.strip().strip("=").strip())
        sections.append((idx, title))

    if not sections:
        return wikitext if site_lang == source_lang_norm else ""

    for i, (start_idx, title_norm) in enumerate(sections):
        if title_norm not in wanted_norm:
            continue
        end_idx = sections[i + 1][0] if i + 1 < len(sections) else len(lines)
        return "\n".join(lines[start_idx:end_idx]).strip()

    return wikitext if site_lang == source_lang_norm else ""


def _clean_definition_text(text: str, source_lang_norm: str) -> str:
    s = _strip_wiki_markup(text)
    if not s:
        return ""
    s = re.sub(r"\[[^\]]{0,120}\]", " ", s)
    s = re.sub(r"\([^)]{0,120}(?:trad\.|simp\.|pinyin|literal|translation|lyrics)[^)]*\)", " ", s, flags=re.I)
    s = re.sub(r"(?:\[?\s*Pinyin\s*\]?|Original English lyrics|Literal English translation|MSC\s*,\s*(?:trad|simp)\.)[\s\S]*$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ;,，。；：")
    if source_lang_norm == "zh":
        s = s.replace(" / ", "；").replace("/", "；")
    if len(s) > 120:
        s = s[:120].rstrip(" ;,，。；：")
    return s


def _clean_example_text(text: str, source_lang_norm: str) -> str:
    s = _strip_wiki_markup(text)
    if not s:
        return ""
    s = re.sub(r"\[[^\]]{0,120}\]", " ", s)
    s = re.sub(r"\([^)]{0,120}(?:trad\.|simp\.|pinyin|literal|translation|lyrics)[^)]*\)", " ", s, flags=re.I)
    s = re.sub(r"(?:\[?\s*Pinyin\s*\]?|Original English lyrics|Literal English translation|MSC\s*,\s*(?:trad|simp)\.)[\s\S]*$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ;,，。；：\"'")
    if len(s) > 70:
        s = s[:70].rstrip(" ;,，。；：\"'")
    return s


def _is_definition_noise(definition: str, source_lang_norm: str) -> bool:
    d = str(definition or "").strip()
    if len(d) < 2:
        return True
    if len(d) > 140:
        return True
    if re.search(r"https?://", d, flags=re.I):
        return True
    if d.count("[") + d.count("]") + d.count("{") + d.count("}") >= 3:
        return True
    if source_lang_norm == "zh":
        ascii_chars = sum(1 for ch in d if ord(ch) < 128)
        if len(d) > 70 and ascii_chars > len(d) * 0.6:
            return True
    return False


def _is_example_noise(example: str, source_lang_norm: str) -> bool:
    e = str(example or "").strip()
    if len(e) < 2:
        return True
    if len(e) > 72:
        return True
    if re.search(r"https?://", e, flags=re.I):
        return True
    if e.count("[") + e.count("]") + e.count("{") + e.count("}") >= 2:
        return True
    if source_lang_norm == "zh":
        ascii_chars = sum(1 for ch in e if ord(ch) < 128)
        if len(e) > 36 and ascii_chars > len(e) * 0.62:
            return True
    return False


def _normalize_definition_key(definition: str) -> str:
    return re.sub(r"[\s\.,;:!?\-_/，。；：！？、（）\[\]{}\"'`]+", "", str(definition or "").lower())


def _merge_meanings_for_display(meanings: list, source_lang_norm: str) -> list:
    deduped = []
    seen_idx = {}
    for m in meanings:
        definition = (m or {}).get("definition", "").strip()
        example = (m or {}).get("example", "").strip()
        key = _normalize_definition_key(definition)
        if not definition or not key:
            continue
        if key in seen_idx:
            idx = seen_idx[key]
            if example and not deduped[idx].get("example"):
                deduped[idx]["example"] = example
            continue
        seen_idx[key] = len(deduped)
        deduped.append({
            "pos": (m or {}).get("pos", "").strip(),
            "definition": definition,
            "example": example,
            "synonyms": [],
        })

    if source_lang_norm == "zh":
        defs = [m["definition"] for m in deduped][:8]
        if not defs:
            return []
        exs = []
        ex_seen = set()
        for m in deduped:
            ex = (m.get("example") or "").strip()
            if not ex:
                continue
            k = _normalize_definition_key(ex)
            if not k or k in ex_seen:
                continue
            ex_seen.add(k)
            exs.append(ex)
            if len(exs) >= 2:
                break
        return [{"pos": "", "definition": "；".join(defs), "example": "；".join(exs), "synonyms": []}]

    trimmed = deduped[:4]
    ex_count = 0
    for item in trimmed:
        ex = (item.get("example") or "").strip()
        if ex and ex_count < 2:
            ex_count += 1
        else:
            item["example"] = ""
    return trimmed


def _extract_meanings_from_wikitext(wikitext: str, source_lang_norm: str, max_items: int = 12) -> list:
    if not wikitext:
        return []
    meanings = []
    current_pos = ""
    for line in str(wikitext).splitlines():
        s = line.strip()
        if not s:
            continue
        if _is_level3_heading(s):
            current_pos = s.strip("=").strip()
            continue
        if s.startswith("#:") or s.startswith("#*"):
            if not meanings:
                continue
            example = _clean_example_text(s[2:].strip(), source_lang_norm)
            if not example or _is_example_noise(example, source_lang_norm):
                continue
            if not meanings[-1].get("example"):
                meanings[-1]["example"] = example
            continue
        if not s.startswith("#") or s.startswith("##"):
            continue
        if len(s) > 1 and s[1] in {":", "*"}:
            continue
        definition = _clean_definition_text(s.lstrip("#").strip(), source_lang_norm)
        if not definition or _is_definition_noise(definition, source_lang_norm):
            continue
        meanings.append({
            "pos": current_pos,
            "definition": definition,
            "example": "",
            "synonyms": [],
        })
        if len(meanings) >= max_items:
            break
    return _merge_meanings_for_display(meanings, source_lang_norm)


def _extract_phonetic_from_wikitext(wikitext: str) -> str:
    if not wikitext:
        return ""
    text = str(wikitext)
    zh_pron_match = re.search(r"\{\{(?:zh-pron|cmn-pron|zh-pinyin)\|([^{}]+)\}\}", text, flags=re.I)
    if zh_pron_match:
        payload = zh_pron_match.group(1)
        parts = [p.strip() for p in payload.split("|") if p.strip()]
        preferred_keys = {"m", "ma", "mandarin", "pinyin", "py", "pin"}
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            if key.strip().lower() in preferred_keys:
                value = value.strip()
                value = re.sub(r"\[[^\]]+\]", "", value).strip()
                if re.search(r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüêńňḿ]", value):
                    return value
        for part in parts:
            candidate = part.split("=", 1)[-1].strip()
            candidate = re.sub(r"\[[^\]]+\]", "", candidate).strip()
            if re.search(r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüêńňḿ]", candidate):
                return candidate

    patterns = [
        r"\{\{IPA\|([^{}]+)\}\}",
        r"\{\{pron\|([^{}]+)\}\}",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if not m:
            continue
        parts = [p.strip() for p in m.group(1).split("|") if p.strip() and "=" not in p]
        if parts:
            return parts[0]
    return ""


def _extract_audio_from_wiktionaryparser(pronunciations) -> str:
    if not isinstance(pronunciations, dict):
        return ""
    audio_items = pronunciations.get("audio") or []
    if not isinstance(audio_items, list):
        audio_items = [audio_items]
    for item in audio_items:
        if isinstance(item, str):
            url = item.strip()
        elif isinstance(item, dict):
            url = str(item.get("url") or item.get("audio") or "").strip()
        else:
            url = ""
        if not url:
            continue
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return "https://en.wiktionary.org" + url
        if url.startswith("http://") or url.startswith("https://"):
            return url
    return ""


def _extract_phonetic_from_wiktionaryparser(pronunciations, source_lang_norm: str) -> str:
    if not isinstance(pronunciations, dict):
        return ""
    text_items = pronunciations.get("text") or []
    if not isinstance(text_items, list):
        text_items = [text_items]

    if source_lang_norm == "zh":
        for item in text_items:
            text = _strip_wiki_markup(str(item or ""))
            m = re.search(r"(?:Pinyin|拼音)[\s:：\-]*([A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüêńňḿ0-9\s·/'-]+)", text, flags=re.I)
            if m:
                return m.group(1).strip(" -:：")

    for item in text_items:
        text = str(item or "")
        m = re.search(r"/[^/]{1,80}/", text)
        if m:
            return m.group(0)

    for item in text_items:
        text = _strip_wiki_markup(str(item or ""))
        text = re.sub(r"^[A-Za-z\s\(\)\[\]\-]+:\s*", "", text).strip()
        if text and len(text) <= 60:
            return text
    return ""


def _extract_meanings_from_wiktionaryparser_entries(entries: list, source_lang_norm: str, fallback_word: str) -> Optional[dict]:
    if not isinstance(entries, list) or not entries:
        return None

    meanings = []
    word_out = fallback_word
    phonetic = ""
    audio = ""

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not word_out:
            word_out = str(entry.get("word") or fallback_word or "").strip()

        pronunciations = entry.get("pronunciations") or {}
        if not phonetic:
            phonetic = _extract_phonetic_from_wiktionaryparser(pronunciations, source_lang_norm)
        if not audio:
            audio = _extract_audio_from_wiktionaryparser(pronunciations)

        definitions = entry.get("definitions") or []
        if not isinstance(definitions, list):
            continue

        for block in definitions:
            if not isinstance(block, dict):
                continue
            pos = str(block.get("partOfSpeech") or "").strip()
            text_lines = block.get("text") or []
            if not isinstance(text_lines, list):
                text_lines = [text_lines]

            example_pool = []
            for ex in (block.get("examples") or []):
                cleaned_ex = _clean_example_text(str(ex or ""), source_lang_norm)
                if cleaned_ex and not _is_example_noise(cleaned_ex, source_lang_norm):
                    example_pool.append(cleaned_ex)

            ex_idx = 0
            for idx, line in enumerate(text_lines):
                line_text = str(line or "").strip()
                if not line_text:
                    continue

                if idx == 0:
                    low = line_text.lower()
                    if re.search(r"\b(?:plural|past|participle|comparative|superlative)\b", low):
                        continue
                    if word_out and low.startswith(str(word_out).lower()):
                        continue

                cleaned = _clean_definition_text(line_text, source_lang_norm)
                if not cleaned or _is_definition_noise(cleaned, source_lang_norm):
                    continue

                ex_val = ""
                while ex_idx < len(example_pool):
                    cand = example_pool[ex_idx]
                    ex_idx += 1
                    if _normalize_definition_key(cand) != _normalize_definition_key(cleaned):
                        ex_val = cand
                        break

                meanings.append({
                    "pos": pos,
                    "definition": cleaned,
                    "example": ex_val,
                    "synonyms": [],
                })
                if len(meanings) >= 12:
                    break
            if len(meanings) >= 12:
                break
        if len(meanings) >= 12:
            break

    merged = _merge_meanings_for_display(meanings, source_lang_norm)
    if not merged:
        return None
    return {
        "word": word_out or fallback_word,
        "phonetic": phonetic,
        "audio": audio,
        "meanings": merged,
    }


def _lookup_wiktionaryparser_sync(word: str, source_lang_norm: str) -> Optional[dict]:
    if WiktionaryParser is None:
        return None

    parser_language = _WIKTIONARYPARSER_LANGUAGE_NAMES.get(source_lang_norm, "english")
    parser = WiktionaryParser()
    try:
        parser.set_default_language(parser_language)
    except Exception:
        pass

    entries = None
    try:
        entries = parser.fetch(word, language=parser_language)
    except TypeError:
        try:
            entries = parser.fetch(word, parser_language)
        except Exception:
            entries = None
    except Exception:
        entries = None

    if not entries:
        try:
            entries = parser.fetch(word)
        except Exception:
            entries = None

    return _extract_meanings_from_wiktionaryparser_entries(entries or [], source_lang_norm, word)


async def _lookup_wiktionaryparser_entry(word: str, source_lang_norm: str) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _lookup_wiktionaryparser_sync, word, source_lang_norm)


def _lookup_on_single_wiki(api_url: str, site_lang: str, word: str, source_lang_norm: str) -> Optional[dict]:
    parse_data = _mediawiki_parse_page(api_url, word)
    if not parse_data:
        title = _mediawiki_search_title(api_url, word)
        if not title:
            return None
        parse_data = _mediawiki_parse_page(api_url, title)
        if not parse_data:
            return None

    page_title = parse_data.get("title") or word
    wikitext = parse_data.get("wikitext") or ""
    lang_block = _extract_language_wikitext_block(wikitext, source_lang_norm, site_lang)
    if not lang_block:
        return None

    meanings = _extract_meanings_from_wikitext(lang_block, source_lang_norm, max_items=12)
    if not meanings:
        return None

    phonetic = _extract_phonetic_from_wikitext(lang_block)
    return {
        "word": page_title,
        "phonetic": phonetic,
        "audio": "",
        "meanings": meanings,
    }


def _lookup_mediawiki_sync(word: str, source_lang_norm: str) -> Optional[dict]:
    for site_lang in _iter_wiktionary_sites(source_lang_norm):
        api_url = _WIKTIONARY_API_ENDPOINTS.get(site_lang)
        if not api_url:
            continue
        result = _lookup_on_single_wiki(api_url, site_lang, word, source_lang_norm)
        if result and result.get("meanings"):
            return result
    return None


async def _lookup_mediawiki_entry(word: str, source_lang_norm: str) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _lookup_mediawiki_sync, word, source_lang_norm)


def _to_chinese_pinyin(word: str) -> str:
    if not word or lazy_pinyin is None:
        return ""
    try:
        base_word = word
        if _ZH_T2S_CONVERTER is not None:
            try:
                base_word = _ZH_T2S_CONVERTER.convert(word) or word
            except Exception:
                base_word = word

        if PinyinStyle is not None and pinyin_choices is not None:
            arr = pinyin_choices(base_word, style=PinyinStyle.TONE, heteronym=True)
            tokens = []
            for item in arr:
                opts = []
                for py in (item or [])[:3]:
                    py = (py or "").strip()
                    if not py or re.search(r"[\u3400-\u9FFF]", py):
                        continue
                    if py not in opts:
                        opts.append(py)
                if opts:
                    tokens.append("/".join(opts))
            if tokens:
                return " ".join(tokens).strip()
        if PinyinStyle is not None:
            arr = lazy_pinyin(base_word, style=PinyinStyle.TONE)
        else:
            arr = lazy_pinyin(base_word)
        cleaned = [x for x in arr if x and not re.search(r"[\u3400-\u9FFF]", x)]
        return " ".join(cleaned).strip()
    except Exception:
        return ""


def _to_japanese_reading(word: str) -> str:
    if not word or _pykakasi_factory is None:
        return ""
    try:
        conv = _pykakasi_factory()
        items = conv.convert(word)
        hira = "".join((it.get("hira") or it.get("kana") or it.get("orig") or "") for it in items).strip()
        roma = " ".join((it.get("hepburn") or it.get("kunrei") or it.get("orig") or "") for it in items).strip()
        if hira and roma:
            return f"{hira} / {roma}"
        return hira or roma
    except Exception:
        return ""


def _should_translate_meanings(meanings: list, target_lang_norm: str) -> bool:
    text = " ".join((m or {}).get("definition", "") for m in (meanings or [])).strip()
    if not text:
        return False

    latin = len(re.findall(r"[A-Za-z]", text))
    hanzi = len(re.findall(r"[\u3400-\u9FFF]", text))
    kana = len(re.findall(r"[\u3040-\u30ff]", text))
    hangul = len(re.findall(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]", text))
    cyr = len(re.findall(r"[А-Яа-яЁёЀ-ӿ]", text))

    if target_lang_norm == "en":
        return latin < 20 or (hanzi + kana + hangul + cyr) > latin
    if target_lang_norm == "zh":
        return hanzi < 12
    if target_lang_norm == "ja":
        return (kana + hanzi) < 12
    if target_lang_norm == "ko":
        return hangul < 8
    if target_lang_norm == "ru":
        return cyr < 8
    return True


@router.get("/api/dictionary/{word}")
async def lookup_dictionary(word: str, source_lang: str = "en", target_lang: str = "zh"):
    """按配置的词典模式查词（oxford / wiktextract）；按 source_lang 查词，按 target_lang 翻译释义。"""
    src_lang = (source_lang or "en").strip() or "en"
    tgt_lang = (target_lang or "zh").strip() or "zh"
    src_norm = _normalize_lang_for_dict(src_lang)
    tgt_norm = _normalize_lang_for_dict(tgt_lang)

    if src_lang not in _DICT_SUPPORTED_LANGS and src_norm not in _DICT_SUPPORTED_LANGS:
        raise HTTPException(400, f"暂不支持该源语言：{source_lang}")
    if tgt_lang not in _DICT_SUPPORTED_LANGS and tgt_norm not in _DICT_SUPPORTED_LANGS:
        raise HTTPException(400, f"暂不支持该目标语言：{target_lang}")

    lookup_word = _clean_lookup_word(word, src_norm)
    if not lookup_word:
        raise HTTPException(400, "无效词条")

    _validate_provider_ready()

    cache_key = f"{_DICT_PROVIDER_MODE}|{src_norm}|{tgt_lang}|{lookup_word}"
    cache_hit, cached_result = _dict_cache_get(cache_key)
    if cache_hit:
        if not cached_result:
            raise HTTPException(404, "词条不存在")
        if not _needs_translation_refresh(cached_result, src_norm, tgt_norm):
            return cached_result

    if _DICT_PROVIDER_MODE == "oxford":
        entry = await _lookup_oxford_entry(lookup_word, src_lang)
    else:
        entry = await _lookup_local_wiktextract_entry(lookup_word, src_lang, tgt_lang)

    if not entry or not entry.get("meanings"):
        _dict_cache_set(cache_key, None)
        raise HTTPException(404, "词条不存在")

    result = {
        "word": entry.get("word", lookup_word),
        "phonetic": entry.get("phonetic", ""),
        "audio": entry.get("audio", ""),
        "provider": str(entry.get("provider") or _DICT_PROVIDER_MODE).strip(),
        "dataset": str(entry.get("dataset") or "").strip(),
        "pronunciations": entry.get("pronunciations") if isinstance(entry.get("pronunciations"), list) else [],
        "meanings": entry.get("meanings", []),
    }
    translated_meanings = _align_translated_meanings(result["meanings"], entry.get("translated_meanings"))
    if translated_meanings:
        result["translated_meanings"] = translated_meanings
    if result.get("translated_meanings") and _is_low_quality_translations(result["translated_meanings"], tgt_norm):
        result.pop("translated_meanings", None)

    if src_norm == "zh":
        result["word"] = lookup_word
        zh_pinyin = _to_chinese_pinyin(lookup_word)
        if zh_pinyin:
            result["phonetic"] = zh_pinyin
    elif src_norm == "ja":
        jp_reading = _to_japanese_reading(lookup_word)
        if jp_reading:
            result["phonetic"] = jp_reading

    if (
        _DICT_ENABLE_LLM_TRANSLATION and
        tgt_norm != src_norm and
        result["meanings"] and
        _needs_translation_refresh(result, src_norm, tgt_norm) and
        _should_translate_meanings(result["meanings"], tgt_norm)
    ):
        try:
            translated = await _translate_definitions(result["word"], result["meanings"], src_lang, tgt_lang)
            if translated:
                aligned = _align_translated_meanings(result["meanings"], translated)
                if aligned and not _is_low_quality_translations(aligned, tgt_norm):
                    result["translated_meanings"] = aligned
                    try:
                        await _persist_local_wiktextract_cache(lookup_word, src_lang, tgt_lang, result)
                    except Exception:
                        pass
        except asyncio.TimeoutError:
            pass
        except Exception as te:
            print(f"⚠️ 翻译释义失败: {te}")

    _dict_cache_set(cache_key, result)
    return result


# 释义翻译缓存
_translation_cache: dict = {}

async def _translate_definitions(word: str, meanings: list, source_lang: str, target_lang: str) -> list:
    """使用 DeepSeek/OpenAI 将词典释义翻译成目标语言"""
    global _LLM_TRANSLATE_FAILURES, _LLM_TRANSLATE_DISABLED_UNTIL
    cache_key = f"{word}_{source_lang}_{target_lang}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]
    if time.time() < _LLM_TRANSLATE_DISABLED_UNTIL:
        _translation_cache[cache_key] = []
        return []

    lang_names = {
        "zh": "中文", "zh-Hans": "简体中文", "zh-Hant": "繁體中文",
        "ja": "日本語", "ko": "한국어", "en": "English",
        "de": "Deutsch", "fr": "français", "es": "español", "ru": "русский",
    }
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)

    # 构建翻译请求
    defs_text = "\n".join(
        f"{i+1}. [{m['pos']}] {m['definition']}"
        for i, m in enumerate(meanings) if m.get('definition')
    )
    if not defs_text.strip():
        return []

    from openai import OpenAI
    api_key = getattr(config, 'OPENAI_API_KEY', '')
    base_url = getattr(config, 'OPENAI_BASE_URL', '')
    if not api_key:
        return []

    def _do_translate():
        client = None
        try:
            try:
                import httpx
                http_client = httpx.Client(trust_env=False, timeout=float(_DICT_TRANSLATE_TIMEOUT_SEC))
                client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
            except Exception:
                client = OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"你是一个精准的词典翻译助手。把{src_name}释义翻译成{tgt_name}，保持简洁准确。每行一个翻译，格式为数字序号开头，只返回翻译内容。"},
                    {"role": "user", "content": f"翻译以下「{word}」的{src_name}释义为{tgt_name}：\n{defs_text}"}
                ],
                temperature=0.2,
                max_tokens=200,
            )
            return (resp.choices[0].message.content or "").strip()
        finally:
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass

    try:
        raw = await asyncio.get_event_loop().run_in_executor(None, _do_translate)
    except Exception:
        _LLM_TRANSLATE_FAILURES += 1
        if _LLM_TRANSLATE_FAILURES >= 3:
            _LLM_TRANSLATE_DISABLED_UNTIL = time.time() + 600
        _translation_cache[cache_key] = []
        return []

    # 解析翻译结果
    translated = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 去除序号前缀 "1. " / "1、" / "1) "
        cleaned = re.sub(r'^\d+[\.\、\)\]\s]+', '', line).strip()
        # 去除可能的 [pos] 前缀
        cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned).strip()
        if cleaned:
            translated.append(cleaned)

    if translated:
        _LLM_TRANSLATE_FAILURES = 0
        _LLM_TRANSLATE_DISABLED_UNTIL = 0.0
    _translation_cache[cache_key] = translated
    return translated
