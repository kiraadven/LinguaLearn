"""UI i18n utility routes."""

import asyncio
import hashlib
import json
import re

from fastapi import APIRouter, HTTPException, Request

_ui_i18n_translation_cache: dict[str, dict] = {}


def build_i18n_router(*, config) -> APIRouter:
    router = APIRouter()

    @router.post("/api/i18n/ui-translate")
    async def ui_translate_batch(request: Request):
        """
        批量翻译前端 UI 文案（用于补全非中英语言缺失 key）。
        """
        body = await request.json()
        target_lang = str(body.get("target_lang") or "").strip()
        entries = body.get("entries") or {}

        allowed_langs = {"ja", "ko", "de", "fr", "es", "ru"}
        if target_lang not in allowed_langs:
            raise HTTPException(400, "target_lang 不支持")
        if not isinstance(entries, dict):
            raise HTTPException(400, "entries 必须是对象")

        cleaned = {}
        for k, v in entries.items():
            key = str(k or "").strip()
            if not key or not re.fullmatch(r"[a-zA-Z0-9_]{1,80}", key):
                continue
            txt = str(v or "").strip()
            if not txt:
                continue
            cleaned[key] = txt[:300]
            if len(cleaned) >= 260:
                break

        if not cleaned:
            return {"translations": {}}

        cache_payload = json.dumps(
            {"target_lang": target_lang, "entries": cleaned},
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_key = hashlib.sha1(cache_payload.encode("utf-8")).hexdigest()
        if cache_key in _ui_i18n_translation_cache:
            return {"translations": _ui_i18n_translation_cache[cache_key]}

        api_key = getattr(config, "OPENAI_API_KEY", "")
        base_url = getattr(config, "OPENAI_BASE_URL", "")
        if not api_key:
            return {"translations": {}}

        lang_names = {
            "ja": "日本語",
            "ko": "한국어",
            "de": "Deutsch",
            "fr": "Français",
            "es": "Español",
            "ru": "Русский",
        }
        tgt_name = lang_names.get(target_lang, target_lang)

        from openai import OpenAI

        def _do_translate_ui() -> dict:
            client = OpenAI(api_key=api_key, base_url=base_url)
            prompt = (
                "You are a professional software UI localizer.\n"
                f"Translate the following JSON values from English into {tgt_name}.\n"
                "Rules:\n"
                "1) Keep keys unchanged.\n"
                "2) Keep placeholders/symbols/emoji unchanged (e.g. {x}, %s, →, ✓, 1080p).\n"
                "3) Use concise, natural UI wording.\n"
                "4) Return ONLY a valid JSON object.\n\n"
                f"Input JSON:\n{json.dumps(cleaned, ensure_ascii=False)}"
            )
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000,
            )
            raw = (resp.choices[0].message.content or "").strip()

            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                raw = raw[start : end + 1]
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {}

            out = {}
            for k in cleaned.keys():
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    out[k] = v.strip()
            return out

        try:
            translated = await asyncio.get_event_loop().run_in_executor(None, _do_translate_ui)
        except Exception as e:
            print(f"⚠️ UI 文案翻译失败: {e}")
            translated = {}

        _ui_i18n_translation_cache[cache_key] = translated
        return {"translations": translated}

    return router

