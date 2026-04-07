"""
AI 随身听模块 (AI Podcast) — LinguaLearn

三层 Agent：
  Layer 2B — Podcast Planner   纯音频视角逐句规划
  Layer 3B — Podcast Writer    工具调用驱动生成随身听脚本

输出：podcast_script.json + TTS 音频 + podcast.mp3（FFmpeg 拼接）
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI
import requests

import config
from core.learning.ai_lesson import (
    LANG_NAME,
    _extract_response_text,
    _clean_json,
    _sanitize_minimax_text,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2B — PODCAST PLANNER PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

PODCAST_PLANNER_SYSTEM = """\
You design premium, audio-only language lessons for commuters.
Given content profile and sentence list, create a podcast teaching plan.
Output ONLY valid JSON — no markdown fences.
"""

PODCAST_PLANNER_USER_TEMPLATE = """\
## Content Profile
{content_profile_json}

## Sentence List
{sentences_summary}

## Task
Create a JSON array (one object per sentence, in order). Each object must include:

"sentence_id": int
"sentence_text": string
"audio_objective": string (what the learner should understand/retain)
"context_bridge": string|null (extra context needed without video)
"key_terms": array of strings (0-3 terms)
"spell_terms": array of strings (0-2 terms that should be spelled letter-by-letter)
"must_replay_original": bool
"insert_check_question": bool
"insert_recap_after": bool (true every 3-4 sentences)

Rules:
1. Prioritize listenability — listener cannot see the screen.
2. Avoid visual references; convert context to spoken description.
3. Use spell_terms only for high-value easily-mishearable terms.

Return ONLY the JSON array.
"""

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3B — PODCAST WRITER SYSTEM PROMPT & TOOLS
# ─────────────────────────────────────────────────────────────────────────────

PODCAST_WRITER_SYSTEM_TEMPLATE = """\
You are a premium audio-only language coach for commuters.
The listener cannot see subtitles or video — everything must be understood by ear alone.
You speak {target_lang_name}, quoting {source_lang_name} only when needed.

## Content Context
Content type: {content_type}
Speaker profile: {speaker_profile}
Cultural context: {cultural_context}
Teacher tone: {tone_for_teacher}

## Absolute Rules
1. ONLY output tool calls. Never output free text.
2. Process ALL sentences in order; do not skip.
3. No visual references like "as you can see on screen".
4. For each sentence, provide at least one spoken explanation.
5. If a term is easy to mishear, call spell_term to spell it out.
6. Check questions and recaps must be spoken clearly.
7. Keep pacing natural for commuting listeners.
"""

MINIMAX_PAUSE_RULES = """\
For MiniMax TTS text, use explicit pause tags like <#0.25#> where useful.
Pause durations are in seconds; keep most tags between 0.15 and 0.55.
Do not chain pause tags back-to-back. Avoid putting pause tags at the beginning or end.
Keep speech natural.
"""

MINIMAX_TTS_REWRITE_SYSTEM = """\
You are an audio narration editor for language-learning TTS.
Rewrite each line into a TTS-friendly text with MiniMax pause tags.
Return ONLY valid JSON array.
"""

MINIMAX_TTS_REWRITE_USER_TEMPLATE = """\
## Role mode
{mode}

## MiniMax pause rules
{pause_rules}

## Input lines (JSON array)
{items_json}

Task:
Return a JSON array with the same length and same indexes:
[
  {{"index": 0, "tts_text": "..."}},
  ...
]
Keep wording as close as possible to input text; only improve oral clarity and insert pause tags.
"""

PODCAST_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "podcast_intro",
            "description": "Opening for the audio-only podcast lesson. Set expectation and listening strategy.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": "Play the original sentence audio from source video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "label": {"type": "string"}
                },
                "required": ["sentence_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "audio_explain",
            "description": "Audio-first explanation with explicit context so listener can understand without video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spell_term",
            "description": "Spell out an important term letter-by-letter and explain why it matters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "term": {"type": "string"},
                    "spelling": {"type": "string", "description": "Letter-by-letter, e.g. A-R-15"},
                    "meaning_tip": {"type": "string"}
                },
                "required": ["sentence_id", "term", "spelling", "meaning_tip"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pronunciation_drill",
            "description": "Give a pronunciation coaching tip for a key term.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "term": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "term", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "audio_check_question",
            "description": "Ask a spoken comprehension check and include spoken hint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {"type": "string"},
                    "answer_hint": {"type": "string"}
                },
                "required": ["sentence_id", "text", "answer_hint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "audio_recap",
            "description": "Short spoken recap every few sentences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer"},
                    "text": {"type": "string"}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "podcast_outro",
            "description": "Closing remarks with actionable review suggestions.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }
    },
]


def _execute_podcast_tool(name: str, args: dict, script: list):
    """将 Podcast 工具调用追加到脚本。"""
    if name == "podcast_intro":
        script.append({"type": "speak", "subtype": "podcast_intro", "sentence_id": None, "text": args["text"], "tts_audio": None})
    elif name == "podcast_outro":
        script.append({"type": "speak", "subtype": "podcast_outro", "sentence_id": None, "text": args["text"], "tts_audio": None})
    elif name == "play_sentence":
        script.append({"type": "play", "sentence_id": args["sentence_id"], "label": args.get("label", "我们先听原句")})
    elif name == "audio_explain":
        script.append({"type": "speak", "subtype": "audio_explain", "sentence_id": args["sentence_id"], "text": args["text"], "tts_audio": None})
    elif name == "spell_term":
        term = args.get("term", "")
        spelling = args.get("spelling", "")
        tip = args.get("meaning_tip", "")
        script.append({"type": "speak", "subtype": "spelling", "sentence_id": args["sentence_id"], "term": term, "text": f"这个重点词是 {term}，拼写是 {spelling}。{tip}", "tts_audio": None})
    elif name == "pronunciation_drill":
        script.append({"type": "speak", "subtype": "podcast_pronunciation", "sentence_id": args["sentence_id"], "term": args.get("term", ""), "text": args["text"], "tts_audio": None})
    elif name == "audio_check_question":
        script.append({"type": "speak", "subtype": "audio_question", "sentence_id": args["sentence_id"], "answer_hint": args.get("answer_hint", ""), "text": f"{args['text']}。提示是：{args.get('answer_hint', '')}", "tts_audio": None})
    elif name == "audio_recap":
        script.append({"type": "speak", "subtype": "audio_recap", "sentence_id": args.get("after_sentence_id"), "text": args["text"], "tts_audio": None})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class AIPodcast:
    """
    AI 随身听三层 Agent + FFmpeg 拼接。

    用法：
        podcast = AIPodcast(source_lang='en', target_lang='zh-Hans')
        result = podcast.generate(md_content, segments, job_output_dir, content_profile=profile)
        podcast.synthesize_tts(result['podcast_script'], job_output_dir / 'tutor')
        podcast.build_podcast(result['podcast_script'], job_output_dir, out_path)
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        source_lang: str = 'en',
        target_lang: str = 'zh-Hans',
        tts_provider: str = None,
        tts_api_key: str = None,
        tts_model: str = None,
        tts_voice: str = None,
    ):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.source_lang_name = LANG_NAME.get(source_lang, source_lang)
        self.target_lang_name = LANG_NAME.get(target_lang, target_lang)

        # LLM setup
        self.llm_provider = (os.getenv('TUTOR_PROVIDER') or os.getenv('TUTOR_LLM_PROVIDER') or 'inherit').strip().lower()
        self.model = model or os.getenv('TUTOR_MODEL') or os.getenv('TUTOR_LLM_MODEL') or 'deepseek-reasoner'
        self.api_key, self.base_url = self._resolve_llm_config(self.llm_provider, api_key, base_url)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info(f"[AIPodcast] provider={self.llm_provider}, model={self.model}")

        # TTS setup
        self.tts_provider = (tts_provider or os.getenv('TTS_PROVIDER', 'minimax')).lower()
        self.tts_api_key = self._resolve_tts_api_key(tts_api_key)
        self.tts_model = tts_model or os.getenv('TTS_MODEL', self._default_tts_model())
        self.tts_voice = tts_voice or os.getenv('TTS_VOICE', 'nova')
        self.tts_minimax_endpoint = os.getenv('TTS_ENDPOINT') or os.getenv('MINIMAX_TTS_ENDPOINT', 'https://api.minimax.io/v1/t2a_v2')
        self.tts_minimax_voice_id = os.getenv('MINIMAX_VOICE_ID', self.tts_voice or 'male-qn-qingse')
        self.tts_minimax_output_format = os.getenv('TTS_OUTPUT_FORMAT') or os.getenv('MINIMAX_TTS_OUTPUT_FORMAT', 'hex')
        self.tts_minimax_language_boost = os.getenv('TTS_LANGUAGE_BOOST') or os.getenv('MINIMAX_TTS_LANGUAGE_BOOST', 'auto')
        self.tts_minimax_sample_rate = int(os.getenv('TTS_SAMPLE_RATE') or os.getenv('MINIMAX_TTS_SAMPLE_RATE', '32000'))
        self.tts_minimax_bitrate = int(os.getenv('TTS_BITRATE') or os.getenv('MINIMAX_TTS_BITRATE', '128000'))
        self.tts_minimax_channel = int(os.getenv('TTS_CHANNEL') or os.getenv('MINIMAX_TTS_CHANNEL', '1'))

    def _resolve_llm_config(self, provider: str, api_key_override: Optional[str], base_url_override: Optional[str]) -> tuple:
        p = (provider or "inherit").lower()
        if p == "inherit":
            p = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()

        if p == "deepseek":
            key = api_key_override or os.getenv("TUTOR_API_KEY") or os.getenv("TUTOR_LLM_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or config.OPENAI_API_KEY
            url = base_url_override or os.getenv("TUTOR_BASE_URL") or os.getenv("TUTOR_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or config.OPENAI_BASE_URL or "https://api.deepseek.com/v1"
        elif p in {"openai", "gpt"}:
            key = api_key_override or os.getenv("TUTOR_API_KEY") or os.getenv("TUTOR_LLM_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            url = base_url_override or os.getenv("TUTOR_BASE_URL") or os.getenv("TUTOR_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
        elif p == "gemini":
            key = api_key_override or os.getenv("TUTOR_API_KEY") or os.getenv("TUTOR_LLM_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
            url = base_url_override or os.getenv("TUTOR_BASE_URL") or os.getenv("TUTOR_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
        else:
            key = api_key_override or os.getenv("TUTOR_API_KEY") or os.getenv("TUTOR_LLM_API_KEY") or os.getenv("LLM_API_KEY") or config.OPENAI_API_KEY
            url = base_url_override or os.getenv("TUTOR_BASE_URL") or os.getenv("TUTOR_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or config.OPENAI_BASE_URL

        if not key:
            raise ValueError(f"LLM provider={p} 缺少 API Key")
        if not url:
            raise ValueError(f"LLM provider={p} 缺少 Base URL")
        return key, url

    def _default_tts_model(self) -> str:
        return "speech-2.8-turbo" if self.tts_provider == "minimax" else "tts-1"

    def _resolve_tts_api_key(self, override: Optional[str]) -> str:
        if override:
            return override
        if self.tts_provider == "minimax":
            return os.getenv("MINIMAX_API_KEY", "") or os.getenv("TTS_API_KEY", "")
        if self.tts_provider == "elevenlabs":
            return os.getenv("ELEVENLABS_API_KEY", "") or os.getenv("TTS_API_KEY", "")
        if self.tts_provider == "azure":
            return os.getenv("AZURE_TTS_KEY", "") or os.getenv("TTS_API_KEY", "")
        return os.getenv("TTS_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")

    def _provider_tts_prompt_rules(self) -> str:
        return MINIMAX_PAUSE_RULES if self.tts_provider == "minimax" else "Use clean, natural spoken text suitable for TTS."

    def _sentence_summary(self, segments: list, max_chars: int = 5000) -> str:
        rows = [f"[{i}] {s.get('text', '').strip()}" for i, s in enumerate(segments)]
        return "\n".join(rows)[:max_chars]

    # ── JSON 请求工具 ──────────────────────────────────────────────────────────
    def _request_json(self, *, messages: list, temperature: float, max_tokens: int, scene: str, expected_type: Optional[type] = None):
        nudge_for_type = {
            dict: "Your response must be a JSON object (starting with {), not an array.",
            list: "Your response must be a JSON array (starting with [), not an object.",
        }
        max_attempts = 3
        invalid_json_nudge = "Your previous response was empty or not valid JSON. Return ONLY valid JSON now — no markdown, no prose."
        last_err: Optional[Exception] = None

        for idx in range(1, max_attempts + 1):
            req_messages = list(messages)
            nudge: Optional[str] = None
            if idx > 1:
                type_nudge = nudge_for_type.get(expected_type, "")
                if isinstance(last_err, ValueError) and "返回类型错误" in str(last_err):
                    nudge = type_nudge or invalid_json_nudge
                else:
                    nudge = invalid_json_nudge
                    if type_nudge:
                        nudge = f"{nudge} {type_nudge}"
            if nudge:
                req_messages.append({"role": "user", "content": nudge})
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, messages=req_messages,
                    temperature=temperature, max_tokens=max_tokens,
                )
                resp_text = _extract_response_text(resp)
                raw = _clean_json(resp_text)
                data = json.loads(raw)

                if expected_type and not isinstance(data, expected_type):
                    if expected_type == dict and isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
                        data = data[0]
                    elif expected_type == list and isinstance(data, dict):
                        for v in data.values():
                            if isinstance(v, list):
                                data = v
                                break

                if expected_type and not isinstance(data, expected_type):
                    raise ValueError(f"{scene} 返回类型错误，期望 {expected_type.__name__}，实际 {type(data).__name__}. {nudge_for_type.get(expected_type, '')}")
                return data

            except Exception as e:
                last_err = e
                try:
                    preview = str(locals().get("raw") or locals().get("resp_text") or "")[:300].replace("\n", "\\n")
                except Exception:
                    preview = ""
                logger.warning(f"[AIPodcast] {scene} 解析失败 attempt {idx}/{max_attempts}: {e}; preview={preview}")

        raise last_err or ValueError(f"{scene} 解析失败")

    # ── Layer 2B: Podcast Planner ──────────────────────────────────────────────
    def plan_podcast(self, content_profile: dict, segments: list) -> list:
        """逐句规划随身听策略。返回 podcast_plan list。"""
        messages = [
            {"role": "system", "content": PODCAST_PLANNER_SYSTEM},
            {"role": "user", "content": PODCAST_PLANNER_USER_TEMPLATE.format(
                content_profile_json=json.dumps(content_profile, ensure_ascii=False, indent=2),
                sentences_summary=self._sentence_summary(segments),
            )},
        ]
        logger.info("[AIPodcast] Layer 2B: 规划随身听课程...")
        plan = self._request_json(messages=messages, temperature=0.3, max_tokens=4096, scene="plan_podcast", expected_type=list)
        logger.info(f"[AIPodcast] 随身听规划完成，{len(plan)} 句")
        return plan

    # ── Layer 3B: Podcast Writer ───────────────────────────────────────────────
    def write_podcast(self, content_profile: dict, podcast_plan: list, audio_files: list) -> list:
        """工具调用驱动生成随身听脚本。"""
        content_type = content_profile.get("content_type", "other")
        system_prompt = PODCAST_WRITER_SYSTEM_TEMPLATE.format(
            target_lang_name=self.target_lang_name,
            source_lang_name=self.source_lang_name,
            content_type=content_type,
            speaker_profile=content_profile.get("speaker_profile", "unknown speaker"),
            cultural_context=content_profile.get("cultural_context", ""),
            tone_for_teacher=content_profile.get("tone_for_teacher", "warm_casual"),
        )
        system_prompt += f"\n\n## TTS Text Rules\n{self._provider_tts_prompt_rules()}"
        user_prompt = (
            f"## Podcast Plan\n{json.dumps(podcast_plan, ensure_ascii=False, indent=2)}\n\n"
            f"## Available sentence audio files\n{', '.join(audio_files) or 'None'}\n\n"
            "Start now. Call podcast_intro first. Process every sentence in order. "
            "For difficult terms, call spell_term and pronunciation_drill. Finish with podcast_outro."
        )

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        script = []
        logger.info("[AIPodcast] Podcast Writer: 工具调用生成脚本...")

        for round_idx in range(28):
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=PODCAST_WRITER_TOOLS, tool_choice="auto",
                temperature=0.6, max_tokens=8192,
            )
            msg = resp.choices[0].message
            finish_reason = resp.choices[0].finish_reason

            if not msg.tool_calls:
                logger.info(f"[AIPodcast] Podcast Writer 完成（round {round_idx}），无更多工具调用")
                break

            tool_results = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                _execute_podcast_tool(tc.function.name, args, script)
                tool_results.append({"role": "tool", "tool_call_id": tc.id, "content": "ok"})

            messages.append(msg)
            messages.extend(tool_results)
            if finish_reason == "stop":
                break

        logger.info(f"[AIPodcast] Podcast Writer 完成，共 {len(script)} 条指令")
        return script

    # ── TTS 重写 ──────────────────────────────────────────────────────────────
    def rewrite_tts(self, script: list) -> list:
        """为 speak 文本生成 provider-specific 的 tts_text。"""
        if self.tts_provider != "minimax":
            return script

        targets = [{"index": idx, "text": item.get("text", "")} for idx, item in enumerate(script) if item.get("type") == "speak" and item.get("text")]
        if not targets:
            return script

        try:
            messages = [
                {"role": "system", "content": MINIMAX_TTS_REWRITE_SYSTEM},
                {"role": "user", "content": MINIMAX_TTS_REWRITE_USER_TEMPLATE.format(
                    mode="podcast",
                    pause_rules=MINIMAX_PAUSE_RULES,
                    items_json=json.dumps(targets, ensure_ascii=False, indent=2),
                )},
            ]
            rows = self._request_json(messages=messages, temperature=0.1, max_tokens=4096, scene="TTS rewrite (podcast)", expected_type=list)
            by_idx = {int(x["index"]): str(x["tts_text"]) for x in rows if "index" in x and "tts_text" in x}
            for idx, item in enumerate(script):
                if item.get("type") != "speak":
                    continue
                candidate = by_idx.get(idx, item.get("text", ""))
                item["tts_text"] = _sanitize_minimax_text(candidate or item.get("text", ""))
        except Exception as e:
            logger.warning(f"[AIPodcast] TTS 重写失败，回退规则化: {e}")
            for item in script:
                if item.get("type") == "speak":
                    item["tts_text"] = _sanitize_minimax_text(item.get("text", ""))
        return script

    # ── TTS 合成 ──────────────────────────────────────────────────────────────
    def synthesize_tts(self, script: list, tutor_dir: Path, *, filename_prefix: str = "pod_tts", flush_each: bool = False) -> list:
        speaks = [(i, s) for i, s in enumerate(script) if s.get("tts_audio") is None and s["type"] == "speak"]
        logger.info(f"[AIPodcast] TTS: 合成 {len(speaks)} 条语音...")
        tutor_dir.mkdir(exist_ok=True)
        script_filename = "podcast_script.json"

        tts_idx = 0
        for item in script:
            if item["type"] != "speak":
                continue
            out_filename = f"{filename_prefix}_{tts_idx:04d}.mp3"
            out_path = tutor_dir / out_filename
            tts_idx += 1

            if out_path.exists():
                item["tts_audio"] = out_filename
                continue
            try:
                tts_text = item.get("tts_text") or item.get("text", "")
                if self.tts_provider == "minimax":
                    tts_text = _sanitize_minimax_text(tts_text)
                    item["tts_text"] = tts_text
                audio_bytes = self._tts_synthesize(tts_text)
                out_path.write_bytes(audio_bytes)
                item["tts_audio"] = out_filename
            except Exception as e:
                logger.error(f"[AIPodcast] TTS 失败 [{tts_idx}]: {e}")
                item["tts_audio"] = None
            finally:
                if flush_each:
                    (tutor_dir / script_filename).write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        (tutor_dir / script_filename).write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_manuscript(script, tutor_dir)
        return script

    def _tts_synthesize(self, text: str) -> bytes:
        if self.tts_provider == 'openai':
            return self._tts_openai(text)
        elif self.tts_provider == 'minimax':
            return self._tts_minimax(text)
        elif self.tts_provider == 'elevenlabs':
            return self._tts_elevenlabs(text)
        elif self.tts_provider == 'azure':
            return self._tts_azure(text)
        raise ValueError(f"未知 TTS 供应商: {self.tts_provider}")

    def _tts_openai(self, text: str) -> bytes:
        client = OpenAI(api_key=self.tts_api_key, base_url="https://api.openai.com/v1")
        resp = client.audio.speech.create(model=self.tts_model, voice=self.tts_voice, input=text, response_format="mp3")
        return resp.content

    def _tts_minimax(self, text: str) -> bytes:
        key = self.tts_api_key or os.getenv("MINIMAX_API_KEY", "")
        if not key:
            raise ValueError("MiniMax TTS 缺少 API Key")
        payload = {
            "model": self.tts_model or "speech-2.8-turbo",
            "text": text, "stream": False,
            "language_boost": self.tts_minimax_language_boost,
            "output_format": self.tts_minimax_output_format,
            "voice_setting": {"voice_id": self.tts_minimax_voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
            "audio_setting": {"sample_rate": self.tts_minimax_sample_rate, "bitrate": self.tts_minimax_bitrate, "format": "mp3", "channel": self.tts_minimax_channel},
        }
        resp = requests.post(self.tts_minimax_endpoint, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"MiniMax TTS HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        base = data.get("base_resp", {})
        if base.get("status_code", 0) != 0:
            raise RuntimeError(f"MiniMax TTS 失败: {base.get('status_msg', '')} | {data}")
        if payload["output_format"] == "hex":
            audio_hex = data.get("data", {}).get("audio")
            if not audio_hex:
                raise RuntimeError("MiniMax TTS 返回缺少 audio(hex)")
            return bytes.fromhex(audio_hex)
        if payload["output_format"] == "url":
            audio_url = data.get("data", {}).get("audio")
            if not audio_url:
                raise RuntimeError("MiniMax TTS 返回缺少 audio(url)")
            r = requests.get(audio_url, timeout=60)
            r.raise_for_status()
            return r.content
        raise RuntimeError(f"MiniMax TTS 不支持的 output_format: {payload['output_format']}")

    def _tts_elevenlabs(self, text: str) -> bytes:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise ImportError("请安装: pip install elevenlabs")
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', '')
        api_key = os.getenv('ELEVENLABS_API_KEY', '') or self.tts_api_key
        if not voice_id:
            raise ValueError("ElevenLabs TTS 缺少 ELEVENLABS_VOICE_ID")
        el = ElevenLabs(api_key=api_key)
        gen = el.text_to_speech.convert(voice_id=voice_id, text=text, model_id=os.getenv('ELEVENLABS_MODEL_ID', 'eleven_multilingual_v2'), output_format="mp3_44100_128")
        return b"".join(gen)

    def _tts_azure(self, text: str) -> bytes:
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            raise ImportError("请安装: pip install azure-cognitiveservices-speech")
        import tempfile
        cfg = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_TTS_KEY', self.tts_api_key), region=os.getenv('AZURE_TTS_REGION', 'eastus'))
        cfg.speech_synthesis_voice_name = os.getenv('AZURE_TTS_VOICE', 'en-US-JennyNeural')
        cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_path = f.name
        synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=speechsdk.audio.AudioOutputConfig(filename=tmp_path))
        result = synth.speak_text_async(text).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise RuntimeError(f"Azure TTS 失败: {result.reason}")
        data = Path(tmp_path).read_bytes()
        Path(tmp_path).unlink(missing_ok=True)
        return data

    # ── 文稿输出 ──────────────────────────────────────────────────────────────
    def write_manuscript(self, script: list, tutor_dir: Path) -> dict:
        tutor_dir.mkdir(exist_ok=True)
        lines = ["# podcast manuscript", ""]
        tts_lines = ["# podcast tts manuscript", ""]
        for i, item in enumerate(script):
            typ = item.get("type", "")
            if typ == "speak":
                txt = item.get("text", "")
                tts_txt = item.get("tts_text") or txt
                sub = item.get("subtype", "")
                sid = item.get("sentence_id")
                sid_txt = f"s{sid + 1}" if isinstance(sid, int) else "-"
                if txt:
                    lines.append(f"[{i + 1:04d}] SPEAK/{sub} [{sid_txt}] {txt}")
                if tts_txt:
                    tts_lines.append(f"[{i + 1:04d}] SPEAK/{sub} [{sid_txt}] {tts_txt}")
            elif typ == "play":
                sid = item.get("sentence_id")
                sid_txt = f"s{sid + 1}" if isinstance(sid, int) else "-"
                lines.append(f"[{i + 1:04d}] PLAY [{sid_txt}] {item.get('label', '')}")
        mp = tutor_dir / "podcast_manuscript.txt"
        tp = tutor_dir / "podcast_tts_manuscript.txt"
        mp.write_text("\n".join(lines), encoding="utf-8")
        tp.write_text("\n".join(tts_lines), encoding="utf-8")
        return {"manuscript": str(mp), "tts_manuscript": str(tp)}

    # ── FFmpeg 拼接 ───────────────────────────────────────────────────────────
    def build_podcast(self, script: list, job_output_dir: Path, out_path: Path) -> Path:
        """FFmpeg concat 拼接 TTS 音频 + 原句音频 → 完整 podcast MP3。"""
        import subprocess
        import tempfile

        tutor_dir = job_output_dir / "tutor"
        entries = []

        for item in script:
            if item["type"] == "speak" and item.get("tts_audio"):
                p = tutor_dir / item["tts_audio"]
                if p.exists():
                    entries.append(str(p.resolve()))
            elif item["type"] == "play":
                sid = item["sentence_id"]
                sq = job_output_dir / f"sq_{sid + 1:04d}.mp3"
                if sq.exists():
                    entries.append(str(sq.resolve()))
                else:
                    logger.warning(f"[AIPodcast] 找不到原句音频: {sq}")

        if not entries:
            raise RuntimeError("没有可拼接的音频片段")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for e in entries:
                f.write(f"file '{e}'\n")
            concat_list = f.name

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c:a", "libmp3lame", "-q:a", "4", str(out_path)]
        logger.info(f"[AIPodcast] FFmpeg 拼接 {len(entries)} 片段 → {out_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(concat_list)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 拼接失败:\n{result.stderr}")
        logger.info(f"[AIPodcast] Podcast 完成: {out_path}")
        return out_path

    # ── 主入口 ────────────────────────────────────────────────────────────────
    def generate(self, md_content: str, segments: list, job_output_dir: Path, content_profile: dict = None) -> dict:
        """生成完整 AI 随身听资产。content_profile 可从 AILesson 共用，避免重复 Layer 1 调用。"""
        audio_files = sorted(f.name for f in job_output_dir.glob("sq_*.mp3"))
        tutor_dir = job_output_dir / "tutor"
        tutor_dir.mkdir(exist_ok=True)

        podcast_plan = self.plan_podcast(content_profile, segments)
        podcast_script = self.write_podcast(content_profile, podcast_plan, audio_files)
        podcast_script = self.rewrite_tts(podcast_script)

        (tutor_dir / "podcast_plan.json").write_text(json.dumps(podcast_plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (tutor_dir / "podcast_script.json").write_text(json.dumps(podcast_script, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_manuscript(podcast_script, tutor_dir)
        logger.info(f"[AIPodcast] 脚本已保存: {tutor_dir}")
        return {"podcast_plan": podcast_plan, "podcast_script": podcast_script}
