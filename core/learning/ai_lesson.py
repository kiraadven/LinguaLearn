"""
AI 讲课模块 (AI Lesson) — LinguaLearn

三层 Agent：
  Layer 1 — Content Analyst    分析内容类型、难度、风格
  Layer 2 — Lesson Planner     逐句规划讲解策略
  Layer 3 — Lesson Writer      工具调用驱动生成互动脚本

输出：tutor_script.json（前端步进式播放）+ TTS 音频文件
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

from openai import OpenAI
import requests

import config

logger = logging.getLogger(__name__)

# ── 语言名称 ─────────────────────────────────────────────────────────────────
LANG_NAME = {
    'en': 'English', 'zh-Hans': '中文（简体）', 'zh-Hant': '中文（繁體）',
    'ja': '日本語', 'ko': '한국어', 'de': 'Deutsch',
    'fr': 'Français', 'es': 'Español', 'ru': 'Русский',
}

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — CONTENT ANALYST PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """\
You are a linguistic content analyst specializing in language learning material.
Analyze the provided video transcript and produce a structured content profile.
Output ONLY valid JSON — no markdown fences, no prose outside JSON.
"""

ANALYST_USER_TEMPLATE = """\
## Video Transcript (first 3000 chars)
{md_excerpt}

## Sentence List
{sentences_summary}

## Task
The video language is {source_lang_name}. The learner's native language is {target_lang_name}.

Produce a JSON object with these fields:

"content_type": one of:
  "news" | "vlog" | "drama_movie" | "interview" | "lecture_educational" | "podcast_talk" | "other"
"content_type_confidence": 0.0–1.0
"content_type_reasoning": one sentence explaining your classification
"register": "formal" | "semi_formal" | "casual" | "mixed"
"estimated_cefr": "A1"–"C2"
"dominant_themes": array of up to 4 topic strings
"speaker_profile": short description of who is speaking
"notable_language_features": array of up to 6 strings
"cultural_context": string — background knowledge a non-native speaker would need
"teaching_focus_priority": array of 3–5 focus areas in priority order
"tone_for_teacher": "warm_casual" | "encouraging_professional" | "analytical_academic"

Return ONLY the JSON object.
"""

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — LESSON PLANNER PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """\
You are a language learning curriculum designer. Given a content profile and sentence list,
produce a per-sentence lesson plan. Output ONLY valid JSON — no markdown fences.
"""

PLANNER_USER_TEMPLATE = """\
## Content Profile
{content_profile_json}

## Sentence List
{sentences_summary}

## Task
Produce a JSON array. Each element covers ONE sentence (0-indexed, in order).

Each element:
  "sentence_id": int (0-indexed)
  "sentence_text": the original sentence
  "depth": "light" | "standard" | "deep"
  "focus_items": array of words/phrases to highlight
  "grammar_point": string|null
  "cultural_note": string|null
  "pronunciation_note": string|null
  "register_note": string|null
  "collocation_focus": array
  "replay_after_explain": bool
  "insert_question_after": bool (max 1 per 4 sentences)
  "insert_summary_after": bool (after every 4–5 sentences)

Depth guidelines (content_type: {content_type}):
  {depth_guidelines}

Return ONLY the JSON array.
"""

DEPTH_GUIDELINES_BY_TYPE = {
    "news": "Deep: passive voice, hedging language, idioms, legal/official terms, complex noun phrases. Light: simple transition phrases, pure facts with common vocabulary. Standard: everything else.",
    "vlog": "Deep: slang, internet expressions, cultural references, non-standard grammar used intentionally. Light: filler words, simple connectors. Standard: everything else.",
    "drama_movie": "Deep: emotionally loaded lines, cultural references, idiomatic dialogue, lines with subtext. Light: simple action descriptions. Standard: everything else.",
    "interview": "Deep: rhetorical devices, hedging language, complex opinion structures, deflection phrases. Light: simple factual statements. Standard: everything else.",
    "lecture_educational": "Deep: technical vocabulary, logical connectors, definition structures, cause-effect language. Light: simple examples or transitions. Standard: everything else.",
    "podcast_talk": "Deep: humor, irony, cultural references, complex opinions. Light: filler phrases, simple agreements. Standard: everything else.",
    "other": "Deep: any sentence with 3+ unfamiliar words, idioms, or cultural context. Light: very simple sentences. Standard: everything else.",
}

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — LESSON WRITER SYSTEM PROMPT & TOOLS
# ─────────────────────────────────────────────────────────────────────────────

WRITER_SYSTEM_TEMPLATE = """\
You are an enthusiastic, knowledgeable language teacher delivering a spoken one-on-one lesson.
You speak {target_lang_name}, quoting {source_lang_name} only when necessary.

## Content Context
Content type: {content_type}
Speaker profile: {speaker_profile}
Cultural context: {cultural_context}
Teacher tone: {tone_for_teacher}

## Absolute Rules
1. ONLY produce output by calling tools — never output free text.
2. Process EVERY sentence in the lesson plan, in order.
3. For every sentence, call play_sentence at least once.
4. For "deep" sentences: play → explain → (tip or grammar or culture) → play again.
5. For "standard" sentences: play → explain → (optionally replay).
6. For "light" sentences: explain (one line) → play.
7. Speak naturally and conversationally — as if talking to a friend.
8. Never use bullet points or markdown in spoken text.
9. Do not skip sentences.

## Content-Type Specific Guidance
{content_type_guidance}
"""

CONTENT_TYPE_GUIDANCE = {
    "news": """\
- Highlight formal/journalistic vocabulary and explain why reporters choose these words.
- When you see passive voice or reported speech, name the structure and give the active equivalent.
- Connect vocabulary to real-world context.
- Point out hedging language like 'allegedly', 'reportedly', 'according to'.
- Compare news register with everyday equivalents.""",
    "vlog": """\
- Celebrate informal expressions — these are the words real people use daily.
- Decode slang and internet expressions with their origin or context.
- Compare casual grammar to formal alternatives.
- Point out filler words (like, you know, I mean) and explain their social function.
- Be extra energetic and relatable.""",
    "drama_movie": """\
- Bring scenes to life — describe the emotional tone or situation when helpful.
- Explain subtext: what characters really mean beyond the literal words.
- Highlight cultural or historical references.
- Discuss how stress and intonation carry emotion in key lines.
- Note when dialogue grammar is intentionally non-standard (character voice).""",
    "interview": """\
- Analyze how the interviewer frames questions and the interviewee structures answers.
- Highlight deflection, hedging, and emphasis techniques.
- Explain professional vocabulary in context.
- Point out discourse markers (well, I think, look, the thing is).
- Discuss power dynamics reflected in language choices.""",
    "lecture_educational": """\
- Build vocabulary systematically — introduce technical terms with clear definitions.
- Highlight logical connectors (therefore, however, in contrast, as a result).
- Explain sentence structures used to define concepts.
- Pause periodically to synthesize what has been explained.
- Connect new terms to concepts the learner may already know.""",
    "podcast_talk": """\
- Embrace humor and irony — explain jokes and cultural references.
- Highlight how speakers signal opinion vs fact.
- Note when speakers interrupt or build on each other's points.
- Explain colloquial expressions and informal transitions.
- Discuss how the conversational rhythm differs from formal speech.""",
    "other": """\
- Adapt your teaching style to the content you encounter.
- Prioritize explaining vocabulary that appears unusual or context-specific.
- Always connect words to their broader usage outside this specific context.""",
}

MINIMAX_PAUSE_RULES = """\
For MiniMax TTS text, use explicit pause tags like <#0.25#> where useful.
Pause durations are in seconds; keep most tags between 0.15 and 0.55.
Use short pauses for commas/phrases, longer pauses for sentence boundaries.
Do not chain pause tags back-to-back. Avoid putting pause tags at the beginning or end.
Keep speech natural; prioritize listener comprehension.
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

LESSON_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": "Insert a directive to play the original audio clip of a sentence from the video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "label": {"type": "string", "description": "Short spoken cue, e.g. '来，先听一遍'. Keep under 15 words."}
                },
                "required": ["sentence_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_sentence",
            "description": "Main explanation for a sentence — meaning, key words, context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {"type": "string", "description": "Spoken explanation. Natural, conversational. No bullet points."}
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grammar_breakdown",
            "description": "Deep-dive into the grammar structure of a sentence or phrase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "structure_name": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "structure_name", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cultural_context",
            "description": "Provide cultural, historical, or social background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "context_type": {
                        "type": "string",
                        "enum": ["person", "event", "place", "concept", "media_reference", "social_context", "historical"]
                    },
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "context_type", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "usage_and_collocation",
            "description": "Explain how a word or phrase is typically used in real life.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_and_style",
            "description": "Explain the formality level, style, or register of a word/phrase/sentence.",
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
            "name": "pronunciation_tip",
            "description": "Focus on pronunciation — word stress, connected speech, intonation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "focus": {
                        "type": "string",
                        "enum": ["word_stress", "connected_speech", "vowel_reduction", "intonation", "silent_letters", "accent_feature"]
                    },
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "focus", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "synonym_and_variation",
            "description": "Offer synonyms, antonyms, or natural variations of a key word or phrase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": "Pose an interactive question to check comprehension. Use sparingly — max once every 4-5 sentences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "question_type": {
                        "type": "string",
                        "enum": ["comprehension", "vocabulary_check", "grammar_apply", "cultural_reflection", "personal_connection"]
                    },
                    "text": {"type": "string"},
                    "answer_hint": {"type": "string"}
                },
                "required": ["sentence_id", "question_type", "text", "answer_hint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transition_remark",
            "description": "Natural transition between groups of sentences.",
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
            "name": "stage_summary",
            "description": "After every 4-5 sentences, deliver a brief comprehension summary.",
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
            "name": "lesson_intro",
            "description": "Call ONCE at the very beginning. Introduce the video content and lesson.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Opening remarks. 3-5 sentences."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lesson_outro",
            "description": "Call ONCE at the very end. Wrap up with key takeaways.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Closing remarks with 3-4 key takeaways."}
                },
                "required": ["text"]
            }
        }
    },
]


def _execute_tool(name: str, args: dict, script: list):
    """将工具调用追加到 lesson script。"""
    if name == "lesson_intro":
        script.append({"type": "speak", "subtype": "intro", "sentence_id": None, "text": args["text"], "tts_audio": None})
    elif name == "lesson_outro":
        script.append({"type": "speak", "subtype": "outro", "sentence_id": None, "text": args["text"], "tts_audio": None})
    elif name == "play_sentence":
        script.append({"type": "play", "sentence_id": args["sentence_id"], "label": args.get("label", "请听原句")})
    elif name == "explain_sentence":
        script.append({"type": "speak", "subtype": "explanation", "sentence_id": args["sentence_id"], "text": args["text"], "tts_audio": None})
    elif name == "grammar_breakdown":
        script.append({"type": "speak", "subtype": "grammar", "sentence_id": args["sentence_id"], "structure_name": args.get("structure_name", ""), "text": args["text"], "tts_audio": None})
    elif name == "cultural_context":
        script.append({"type": "speak", "subtype": "culture", "sentence_id": args["sentence_id"], "context_type": args.get("context_type", ""), "text": args["text"], "tts_audio": None})
    elif name == "usage_and_collocation":
        script.append({"type": "speak", "subtype": "usage", "sentence_id": args["sentence_id"], "target": args.get("target_word_or_phrase", ""), "text": args["text"], "tts_audio": None})
    elif name == "register_and_style":
        script.append({"type": "speak", "subtype": "register", "sentence_id": args["sentence_id"], "text": args["text"], "tts_audio": None})
    elif name == "pronunciation_tip":
        script.append({"type": "speak", "subtype": "pronunciation", "sentence_id": args["sentence_id"], "focus": args.get("focus", ""), "text": args["text"], "tts_audio": None})
    elif name == "synonym_and_variation":
        script.append({"type": "speak", "subtype": "synonym", "sentence_id": args["sentence_id"], "target": args.get("target_word_or_phrase", ""), "text": args["text"], "tts_audio": None})
    elif name == "ask_question":
        script.append({"type": "question", "sentence_id": args["sentence_id"], "question_type": args.get("question_type", "comprehension"), "text": args["text"], "answer_hint": args.get("answer_hint", "")})
    elif name == "transition_remark":
        script.append({"type": "speak", "subtype": "transition", "sentence_id": args.get("after_sentence_id"), "text": args["text"], "tts_audio": None})
    elif name == "stage_summary":
        script.append({"type": "speak", "subtype": "summary", "sentence_id": args.get("after_sentence_id"), "text": args["text"], "tts_audio": None})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class AILesson:
    """
    AI 讲课三层 Agent。

    用法：
        lesson = AILesson(source_lang='en', target_lang='zh-Hans')
        result = lesson.generate(md_content, segments, job_output_dir)
        lesson.synthesize_tts(result['lesson_script'], job_output_dir / 'tutor')
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
        logger.info(f"[AILesson] provider={self.llm_provider}, model={self.model}")

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

    # ── JSON 请求工具 ──────────────────────────────────────────────────────────
    def _request_json(self, *, messages: list, temperature: float, max_tokens: int, scene: str, expected_type: Optional[type] = None):
        """请求 LLM 并解析 JSON，类型错误时自动修复或重试。"""
        nudge_for_type = {
            dict: "Your response must be a JSON object (starting with {), not an array. Return ONLY a JSON object now.",
            list: "Your response must be a JSON array (starting with [), not an object. Return ONLY a JSON array now.",
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
                    model=self.model,
                    messages=req_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                resp_text = _extract_response_text(resp)
                raw = _clean_json(resp_text)
                data = json.loads(raw)

                # Auto-coerce common type mismatches before raising
                if expected_type and not isinstance(data, expected_type):
                    if expected_type == dict and isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
                        data = data[0]
                    elif expected_type == list and isinstance(data, dict):
                        # Wrapped list case: {"items": [...]}
                        for v in data.values():
                            if isinstance(v, list):
                                data = v
                                break

                if expected_type and not isinstance(data, expected_type):
                    type_nudge = nudge_for_type.get(expected_type, "")
                    raise ValueError(
                        f"{scene} 返回类型错误，期望 {expected_type.__name__}，实际 {type(data).__name__}. {type_nudge}"
                    )
                return data

            except Exception as e:
                last_err = e
                try:
                    preview = str(locals().get("raw") or locals().get("resp_text") or "")[:300].replace("\n", "\\n")
                except Exception:
                    preview = ""
                logger.warning(f"[AILesson] {scene} 解析失败 attempt {idx}/{max_attempts}: {e}; preview={preview}")

        raise last_err or ValueError(f"{scene} 解析失败")

    def _sentence_summary(self, segments: list, max_chars: int = 5000) -> str:
        rows = [f"[{i}] {s.get('text', '').strip()}" for i, s in enumerate(segments)]
        return "\n".join(rows)[:max_chars]

    # ── Layer 1: Content Analyst ───────────────────────────────────────────────
    def analyze_content(self, md_content: str, segments: list) -> dict:
        """分析内容类型、难度、文化背景。返回 content_profile dict。"""
        messages = [
            {"role": "system", "content": ANALYST_SYSTEM},
            {"role": "user", "content": ANALYST_USER_TEMPLATE.format(
                md_excerpt=md_content[:3000],
                sentences_summary=self._sentence_summary(segments, 2000),
                source_lang_name=self.source_lang_name,
                target_lang_name=self.target_lang_name,
            )},
        ]
        logger.info("[AILesson] Layer 1: 分析内容类型...")
        profile = self._request_json(messages=messages, temperature=0.2, max_tokens=1200, scene="analyze_content", expected_type=dict)
        logger.info(f"[AILesson] 内容类型: {profile.get('content_type')} ({profile.get('register')})")
        return profile

    # ── Layer 2: Lesson Planner ────────────────────────────────────────────────
    def plan_lesson(self, content_profile: dict, segments: list) -> list:
        """逐句规划讲解策略。返回 lesson_plan list。"""
        content_type = content_profile.get("content_type", "other")
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": PLANNER_USER_TEMPLATE.format(
                content_profile_json=json.dumps(content_profile, ensure_ascii=False, indent=2),
                sentences_summary=self._sentence_summary(segments),
                content_type=content_type,
                depth_guidelines=DEPTH_GUIDELINES_BY_TYPE.get(content_type, DEPTH_GUIDELINES_BY_TYPE["other"]),
            )},
        ]
        logger.info("[AILesson] Layer 2: 规划课程...")
        plan = self._request_json(messages=messages, temperature=0.3, max_tokens=4096, scene="plan_lesson", expected_type=list)
        logger.info(f"[AILesson] 课程规划完成，{len(plan)} 句")
        return plan

    # ── Layer 3: Lesson Writer ─────────────────────────────────────────────────
    def write_lesson(self, content_profile: dict, lesson_plan: list, audio_files: list) -> list:
        """工具调用驱动生成互动课程脚本。"""
        content_type = content_profile.get("content_type", "other")
        system_prompt = WRITER_SYSTEM_TEMPLATE.format(
            target_lang_name=self.target_lang_name,
            source_lang_name=self.source_lang_name,
            content_type=content_type,
            speaker_profile=content_profile.get("speaker_profile", "unknown speaker"),
            cultural_context=content_profile.get("cultural_context", ""),
            tone_for_teacher=content_profile.get("tone_for_teacher", "warm_casual"),
            content_type_guidance=CONTENT_TYPE_GUIDANCE.get(content_type, CONTENT_TYPE_GUIDANCE["other"]),
        )
        system_prompt += f"\n\n## TTS Text Rules\n{self._provider_tts_prompt_rules()}"
        user_prompt = (
            f"## Lesson Plan\n{json.dumps(lesson_plan, ensure_ascii=False, indent=2)}\n\n"
            f"## Available sentence audio files\n{', '.join(audio_files) or 'None'}\n\n"
            "Begin the lesson now. Start with lesson_intro, process every sentence in order, end with lesson_outro."
        )
        return self._run_writer_loop(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tools=LESSON_WRITER_TOOLS,
            tool_executor=_execute_tool,
            log_tag="Lesson Writer",
        )

    def _run_writer_loop(self, *, system_prompt: str, user_prompt: str, tools: list, tool_executor: Callable, log_tag: str, max_rounds: int = 24) -> list:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        script = []
        logger.info(f"[AILesson] {log_tag}: 工具调用生成脚本...")

        for round_idx in range(max_rounds):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.6,
                max_tokens=8192,
            )
            msg = resp.choices[0].message
            finish_reason = resp.choices[0].finish_reason

            if not msg.tool_calls:
                logger.info(f"[AILesson] {log_tag} 完成（round {round_idx}），无更多工具调用")
                break

            tool_results = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                logger.debug(f"[AILesson] {log_tag} 工具: {tc.function.name} sid={args.get('sentence_id', args.get('after_sentence_id', '-'))}")
                tool_executor(tc.function.name, args, script)
                tool_results.append({"role": "tool", "tool_call_id": tc.id, "content": "ok"})

            messages.append(msg)
            messages.extend(tool_results)
            if finish_reason == "stop":
                break

        logger.info(f"[AILesson] {log_tag} 完成，共 {len(script)} 条指令")
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
                    mode="lesson",
                    pause_rules=MINIMAX_PAUSE_RULES,
                    items_json=json.dumps(targets, ensure_ascii=False, indent=2),
                )},
            ]
            rows = self._request_json(messages=messages, temperature=0.1, max_tokens=4096, scene="TTS rewrite (lesson)", expected_type=list)
            by_idx = {int(x["index"]): str(x["tts_text"]) for x in rows if "index" in x and "tts_text" in x}
            for idx, item in enumerate(script):
                if item.get("type") != "speak":
                    continue
                candidate = by_idx.get(idx, item.get("text", ""))
                item["tts_text"] = _sanitize_minimax_text(candidate or item.get("text", ""))
        except Exception as e:
            logger.warning(f"[AILesson] TTS 重写失败，回退规则化: {e}")
            for item in script:
                if item.get("type") == "speak":
                    item["tts_text"] = _sanitize_minimax_text(item.get("text", ""))
        return script

    # ── TTS 合成 ──────────────────────────────────────────────────────────────
    def synthesize_tts(self, script: list, tutor_dir: Path, *, script_filename: str = "tutor_script.json", filename_prefix: str = "tts", flush_each: bool = False) -> list:
        speaks = [(i, s) for i, s in enumerate(script) if s.get("tts_audio") is None and s["type"] == "speak"]
        logger.info(f"[AILesson] TTS: 合成 {len(speaks)} 条语音...")
        tutor_dir.mkdir(exist_ok=True)

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
                logger.error(f"[AILesson] TTS 失败 [{tts_idx}]: {e}")
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
            "text": text,
            "stream": False,
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
                raise RuntimeError(f"MiniMax TTS 返回缺少 audio(hex)")
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
        lines = ["# lesson manuscript", ""]
        tts_lines = ["# lesson tts manuscript", ""]
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
            elif typ == "question":
                sid = item.get("sentence_id")
                sid_txt = f"s{sid + 1}" if isinstance(sid, int) else "-"
                lines.append(f"[{i + 1:04d}] QUESTION [{sid_txt}] {item.get('text', '')}")
        mp = tutor_dir / "lesson_manuscript.txt"
        tp = tutor_dir / "lesson_tts_manuscript.txt"
        mp.write_text("\n".join(lines), encoding="utf-8")
        tp.write_text("\n".join(tts_lines), encoding="utf-8")
        return {"manuscript": str(mp), "tts_manuscript": str(tp)}

    # ── 主入口 ────────────────────────────────────────────────────────────────
    def generate(self, md_content: str, segments: list, job_output_dir: Path, content_profile: dict = None) -> dict:
        """生成完整 AI 讲课资产（脚本 + 中间文件）。不含 TTS 合成（需额外调用 synthesize_tts）。"""
        audio_files = sorted(f.name for f in job_output_dir.glob("sq_*.mp3"))
        tutor_dir = job_output_dir / "tutor"
        tutor_dir.mkdir(exist_ok=True)

        if content_profile is None:
            content_profile = self.analyze_content(md_content, segments)
        lesson_plan = self.plan_lesson(content_profile, segments)
        lesson_script = self.write_lesson(content_profile, lesson_plan, audio_files)
        lesson_script = self.rewrite_tts(lesson_script)

        (tutor_dir / "content_profile.json").write_text(json.dumps(content_profile, ensure_ascii=False, indent=2), encoding="utf-8")
        (tutor_dir / "lesson_plan.json").write_text(json.dumps(lesson_plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (tutor_dir / "tutor_script.json").write_text(json.dumps(lesson_script, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_manuscript(lesson_script, tutor_dir)
        logger.info(f"[AILesson] 脚本已保存: {tutor_dir}")
        return {"content_profile": content_profile, "lesson_plan": lesson_plan, "lesson_script": lesson_script}


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _extract_response_text(resp: Any) -> str:
    """从 OpenAI 风格响应中提取文本，兼容各种 provider 特殊字段。"""
    try:
        msg = resp.choices[0].message
    except Exception:
        return ""

    content = getattr(msg, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            txt = (part.get("text") or part.get("content") or "") if isinstance(part, dict) else (getattr(part, "text", "") or getattr(part, "content", ""))
            if txt:
                parts.append(str(txt))
        merged = "\n".join(parts).strip()
        if merged:
            return merged

    for key in ("reasoning_content", "output_text", "reasoning"):
        val = getattr(msg, key, None)
        if isinstance(val, str) and val.strip():
            logger.warning(f"[AILesson] message.content 为空，回退使用 {key}")
            return val

    try:
        dump = msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)
        if isinstance(dump, dict):
            for key in ("content", "reasoning_content", "output_text", "reasoning"):
                val = dump.get(key)
                if isinstance(val, str) and val.strip():
                    return val
    except Exception:
        pass
    return ""


def _clean_json(raw: str) -> str:
    """清理 LLM 响应，提取纯 JSON 主体。"""
    raw = (raw or "").strip()
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
        if m:
            raw = m.group(1)
    raw = raw.strip()
    if not raw:
        raise ValueError("LLM 返回为空，无法解析 JSON")

    first_obj = raw.find("{")
    first_arr = raw.find("[")
    starts = [x for x in (first_obj, first_arr) if x >= 0]
    if not starts:
        return raw

    candidate = raw[min(starts):].strip()
    if not candidate:
        raise ValueError("LLM 返回为空，无法解析 JSON")

    decoder = json.JSONDecoder()
    try:
        _, end = decoder.raw_decode(candidate)
        return candidate[:end].strip()
    except Exception:
        return candidate


def _sanitize_minimax_text(text: str) -> str:
    """规范化 MiniMax TTS 文本中的 pause tag。"""
    s = (text or "").strip()
    if not s:
        return s
    s = re.sub(r"\s*\n+\s*", "<#0.35#>", s)
    if "<#" not in s:
        s = re.sub(r"([，,])\s*", r"\1<#0.20#>", s)
        s = re.sub(r"([；;:：])\s*", r"\1<#0.28#>", s)
        s = re.sub(r"([。！？!?])\s*", r"\1<#0.42#>", s)
    s = re.sub(r"(?:\s*<#\d+(?:\.\d+)?#>\s*){2,}", " <#0.30#> ", s)
    s = re.sub(r"^(?:\s*<#\d+(?:\.\d+)?#>\s*)+", "", s)
    s = re.sub(r"(?:\s*<#\d+(?:\.\d+)?#>\s*)+$", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()
