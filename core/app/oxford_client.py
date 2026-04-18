"""Oxford Dictionaries API client for word lookup."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import requests


DEFAULT_BASE_URL = "https://od-api-sandbox.oxforddictionaries.com/api/v2"
DEFAULT_EN_DATASET = "en-gb"


class OxfordLookupError(RuntimeError):
    """Raised when Oxford API returns a non-retryable error."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = int(status_code or 0)


def _normalize_source_dataset(source_lang: str, english_dataset: str = DEFAULT_EN_DATASET) -> str:
    raw = str(source_lang or "").strip().lower().replace("_", "-")
    if not raw:
        return english_dataset
    if raw in {"en", "en-gb", "en-us"}:
        return english_dataset if raw == "en" else raw
    if raw in {"zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-sg"}:
        return "zh"
    if raw.startswith("ja"):
        return "ja"
    if raw.startswith("ko"):
        return "ko"
    if raw.startswith("de"):
        return "de"
    if raw.startswith("fr"):
        return "fr"
    if raw.startswith("es"):
        return "es"
    if raw.startswith("ru"):
        return "ru"
    return raw


def _iter_senses(items: Iterable[dict]) -> Iterable[dict]:
    for sense in items or []:
        if not isinstance(sense, dict):
            continue
        yield sense
        for sub in _iter_senses(sense.get("subsenses") or []):
            yield sub


def _pick_pronunciation(nodes: Iterable[dict]) -> Tuple[str, str]:
    phonetic = ""
    audio = ""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for item in node.get("pronunciations") or []:
            if not isinstance(item, dict):
                continue
            if not phonetic:
                phonetic = str(item.get("phoneticSpelling") or "").strip()
            if not audio:
                audio = str(item.get("audioFile") or "").strip()
            if phonetic and audio:
                return phonetic, audio
    return phonetic, audio


def _normalize_pronunciation(item: dict) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    phonetic = str(item.get("phoneticSpelling") or "").strip()
    audio = str(item.get("audioFile") or "").strip()
    if not phonetic and not audio:
        return None

    dialects: List[str] = []
    for key in ("dialects", "regions"):
        values = item.get(key) or []
        if not isinstance(values, list):
            continue
        for v in values:
            text = str(v or "").strip()
            if text and text not in dialects:
                dialects.append(text)

    out = {"phonetic": phonetic, "audio": audio, "dialects": dialects}
    return out


def _collect_pronunciations(nodes: Iterable[dict], sink: List[dict]) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for item in node.get("pronunciations") or []:
            pr = _normalize_pronunciation(item)
            if not pr:
                continue
            key = (pr.get("phonetic", ""), pr.get("audio", ""), tuple(pr.get("dialects") or []))
            if any(
                (x.get("phonetic", ""), x.get("audio", ""), tuple(x.get("dialects") or [])) == key
                for x in sink
            ):
                continue
            sink.append(pr)


def _extract_meanings(payload: dict, fallback_word: str) -> Optional[dict]:
    results = payload.get("results") or []
    if not isinstance(results, list):
        return None

    meanings: List[dict] = []
    seen = set()
    word_out = str(fallback_word or "").strip()
    phonetic = ""
    audio = ""
    pronunciations: List[dict] = []

    for result in results:
        if not isinstance(result, dict):
            continue
        if not word_out:
            word_out = str(result.get("word") or result.get("id") or fallback_word or "").strip()

        lexical_entries = result.get("lexicalEntries") or []
        if not isinstance(lexical_entries, list):
            continue

        for lex in lexical_entries:
            if not isinstance(lex, dict):
                continue
            if not word_out:
                word_out = str(lex.get("text") or result.get("word") or fallback_word or "").strip()

            lexical_category = lex.get("lexicalCategory")
            if isinstance(lexical_category, dict):
                pos = str(lexical_category.get("text") or lexical_category.get("id") or "").strip()
            else:
                pos = str(lexical_category or "").strip()

            entries = lex.get("entries") or []
            if not isinstance(entries, list):
                entries = []

            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                _collect_pronunciations((lex, entry), pronunciations)
                p, a = _pick_pronunciation((lex, entry))
                if p and not phonetic:
                    phonetic = p
                if a and not audio:
                    audio = a

                senses = entry.get("senses") or []
                for sense in _iter_senses(senses):
                    _collect_pronunciations((sense,), pronunciations)
                    p2, a2 = _pick_pronunciation((sense,))
                    if p2 and not phonetic:
                        phonetic = p2
                    if a2 and not audio:
                        audio = a2

                    defs = sense.get("definitions") or sense.get("shortDefinitions") or []
                    if not isinstance(defs, list):
                        defs = [defs]

                    example = ""
                    for ex in sense.get("examples") or []:
                        if isinstance(ex, dict):
                            example = str(ex.get("text") or "").strip()
                        else:
                            example = str(ex or "").strip()
                        if example:
                            break

                    for d in defs:
                        definition = str(d or "").strip()
                        if not definition:
                            continue
                        key = definition.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        meanings.append(
                            {
                                "pos": pos,
                                "definition": definition,
                                "example": example,
                                "synonyms": [],
                            }
                        )
                        if len(meanings) >= 12:
                            break
                    if len(meanings) >= 12:
                        break
                if len(meanings) >= 12:
                    break
            if len(meanings) >= 12:
                break
        if len(meanings) >= 12:
            break

    if not meanings:
        return None

    return {
        "word": word_out or fallback_word,
        "phonetic": phonetic,
        "audio": audio,
        "pronunciations": pronunciations,
        "meanings": meanings,
    }


def lookup_word_entry(
    *,
    word: str,
    source_lang: str,
    app_id: str,
    app_key: str,
    base_url: str = DEFAULT_BASE_URL,
    english_dataset: str = DEFAULT_EN_DATASET,
    timeout_sec: float = 3.0,
    strict_match: bool = True,
) -> Optional[dict]:
    cleaned_word = str(word or "").strip()
    if not cleaned_word:
        return None
    app_id = str(app_id or "").strip()
    app_key = str(app_key or "").strip()
    if not app_id or not app_key:
        raise OxfordLookupError("Oxford credentials are required", 401)

    dataset = _normalize_source_dataset(source_lang, english_dataset=english_dataset)
    endpoint = f"{str(base_url or DEFAULT_BASE_URL).rstrip('/')}/entries/{dataset}/{cleaned_word.lower()}"
    headers = {"app_id": app_id, "app_key": app_key}
    params = {
        "fields": "definitions,examples,pronunciations",
        "strictMatch": "true" if strict_match else "false",
    }

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=max(1.0, float(timeout_sec or 3.0)))
    except Exception as e:
        raise OxfordLookupError(f"Oxford request failed: {e}") from e

    if resp.status_code == 404:
        return None
    if resp.status_code in {401, 403}:
        raise OxfordLookupError(f"Oxford auth failed (HTTP {resp.status_code})", resp.status_code)
    if resp.status_code == 429:
        raise OxfordLookupError("Oxford rate limited (HTTP 429)", 429)
    if resp.status_code >= 500:
        raise OxfordLookupError(f"Oxford server error (HTTP {resp.status_code})", resp.status_code)
    if resp.status_code != 200:
        snippet = str(resp.text or "").strip().replace("\n", " ")[:220]
        raise OxfordLookupError(f"Oxford lookup failed (HTTP {resp.status_code}): {snippet}", resp.status_code)

    try:
        payload = resp.json()
    except Exception as e:
        raise OxfordLookupError(f"Oxford response is not valid JSON: {e}") from e

    parsed = _extract_meanings(payload, cleaned_word)
    if not parsed:
        return None
    parsed["provider"] = "oxford"
    parsed["dataset"] = dataset
    return parsed
