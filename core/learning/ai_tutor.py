"""
AI 讲师模块 — LinguaLearn

═══════════════════════════════════════════════════════════════════════════════
架构：三层 Agent 设计
═══════════════════════════════════════════════════════════════════════════════

  Layer 1 — Content Analyst（内容分析师）
    · 读取 segments + MD，判断内容类型（新闻/vlog/影视/采访/讲座/播客）
    · 分析整体难度、语体风格、目标受众
    · 输出 content_profile（指导后续两层的行为）

  Layer 2 — Lesson Planner（课程规划师）
    · 接收 content_profile，逐句制定讲解策略
    · 决定：讲解深度 / 聚焦点 / 文化背景 / 语法点
    · 输出 lesson_plan（按句子索引的 JSON 数组）

  Layer 3 — Lesson Writer（课程执笔人，工具调用驱动）
    · 接收 lesson_plan，逐句调用工具生成脚本
    · 工具链覆盖：讲解/播音/语法/文化/用法/口音/对比/提问/过渡/阶段小结
    · 输出 lesson_script（前端可直接执行的指令序列）

═══════════════════════════════════════════════════════════════════════════════
内容类型感知：不同类型的讲解策略
═══════════════════════════════════════════════════════════════════════════════

  news（新闻报道）
    → 重点：正式词汇、被动语态、报道语言、引用结构
    → 文化：新闻事件背景、相关人物介绍
    → 风格：严肃、客观

  vlog（网红口播/日常 vlog）
    → 重点：俚语、口语缩略、感叹词、非正式表达
    → 文化：网络文化、地区俚语、年轻人用语
    → 风格：轻松、贴近生活

  drama_movie（影视剧）
    → 重点：情感表达、对话节奏、角色语气、文化典故
    → 文化：剧情背景、社会文化语境
    → 风格：生动、有感情

  interview（采访/对话）
    → 重点：问答结构、礼貌用语、转折语、强调句
    → 文化：采访对象背景、话题社会意义
    → 风格：专业、引导性

  lecture_educational（讲座/教学）
    → 重点：学术词汇、逻辑连接词、概念解释、举例结构
    → 文化：学科背景
    → 风格：系统、严谨

  podcast_talk（播客/脱口秀）
    → 重点：观点表达、幽默语言、话题转换、情感词
    → 文化：话题背景、流行文化
    → 风格：随性、有深度

═══════════════════════════════════════════════════════════════════════════════
lesson_script 指令格式
═══════════════════════════════════════════════════════════════════════════════

  {"type": "speak",      "subtype": "intro|explanation|grammar|culture|usage|pronunciation|comparison|summary",
                         "sentence_id": int|null, "text": str, "tts_audio": null}
  {"type": "play",       "sentence_id": int, "label": str}
  {"type": "question",   "sentence_id": int, "text": str, "answer_hint": str}
  {"type": "transition", "text": str, "tts_audio": null}
  {"type": "summary",    "text": str, "tts_audio": null}

TTS 环境变量：
  TTS_PROVIDER      openai（默认）| elevenlabs | azure
  TTS_API_KEY       TTS 服务的 API Key（OpenAI 必须用官方 key，不走 base_url）
  TTS_MODEL         tts-1 | tts-1-hd
  TTS_VOICE         nova | shimmer | alloy | echo | fable | onyx
  ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID / ELEVENLABS_MODEL_ID
  AZURE_TTS_KEY / AZURE_TTS_REGION / AZURE_TTS_VOICE

Tutor LLM 环境变量：
  TUTOR_LLM_MODEL   用于三层 Agent 的模型（默认 deepseek-chat）
                    推荐换成 claude-3-5-sonnet / gpt-4o 获得更好的讲解质量
"""

import os
import json
import logging
from pathlib import Path
from typing import Iterator, Optional
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# ── 语言名称 ──────────────────────────────────────────────────────────────────
LANG_NAME = {
    'en': 'English', 'zh-Hans': '中文（简体）', 'zh-Hant': '中文（繁體）',
    'ja': '日本語', 'ko': '한국어', 'de': 'Deutsch',
    'fr': 'Français', 'es': 'Español', 'ru': 'Русский',
}

# ──────────────────────────────────────────────────────────────────────────────
# LAYER 1 — CONTENT ANALYST PROMPTS
# ──────────────────────────────────────────────────────────────────────────────

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

"estimated_cefr": "A1"–"C2" — overall difficulty level of the source language

"dominant_themes": array of up to 4 topic strings (e.g. ["crime", "celebrity", "law enforcement"])

"speaker_profile": short description of who is speaking (e.g. "news anchor", "lifestyle vlogger",
  "fictional character", "tech CEO being interviewed")

"notable_language_features": array of up to 6 strings describing key linguistic features
  (e.g. ["heavy use of passive voice", "news-style reported speech", "legal terminology",
          "frequent use of hedging language", "idiomatic expressions", "code-switching"])

"cultural_context": string — background knowledge a non-native speaker would need
  (e.g. "Rihanna is a Barbadian pop star and fashion entrepreneur; AR-15 is a semi-automatic rifle
   commonly referenced in US gun control debates")

"teaching_focus_priority": array of 3–5 focus areas in priority order
  (e.g. ["vocabulary_formal", "reported_speech", "passive_voice", "news_idioms"])

"tone_for_teacher": one of "warm_casual" | "encouraging_professional" | "analytical_academic"
  — recommended tone for the AI teacher given this content type

Return ONLY the JSON object.
"""

# ──────────────────────────────────────────────────────────────────────────────
# LAYER 2 — LESSON PLANNER PROMPTS
# ──────────────────────────────────────────────────────────────────────────────

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
    light    → one-liner comment only (simple/filler sentences)
    standard → 1-2 key items + play once
    deep     → full breakdown + replay
  "focus_items": array — specific words/phrases/structures to highlight (empty for light)
  "grammar_point": string|null — core grammar structure if any (e.g. "passive voice: be + past participle")
  "cultural_note": string|null — cultural/historical context worth mentioning
  "pronunciation_note": string|null — notable pronunciation features (stress, connected speech, accent)
  "register_note": string|null — register/formality note (e.g. "formal news register vs casual alternative")
  "collocation_focus": array — collocations worth drilling (e.g. ["open fire on", "fire a weapon"])
  "replay_after_explain": bool — play audio again after explanation
  "insert_question_after": bool — add interactive question after this sentence (max 1 per 4 sentences)
  "insert_summary_after": bool — add comprehension summary after this sentence (use after every 4–5 sentences)

Depth guidelines (adapted to content_type: {content_type}):
  {depth_guidelines}

Return ONLY the JSON array.
"""

DEPTH_GUIDELINES_BY_TYPE = {
    "news": "Deep: sentences with passive voice, hedging language, idioms, legal/official terms, or complex noun phrases. Light: simple transition phrases, pure facts with common vocabulary. Standard: everything else.",
    "vlog": "Deep: slang, internet expressions, cultural references, non-standard grammar used intentionally. Light: filler words, simple connectors. Standard: everything else.",
    "drama_movie": "Deep: emotionally loaded lines, cultural references, idiomatic dialogue, lines with subtext. Light: simple action descriptions. Standard: everything else.",
    "interview": "Deep: rhetorical devices, hedging language, complex opinion structures, deflection phrases. Light: simple factual statements. Standard: everything else.",
    "lecture_educational": "Deep: technical vocabulary, logical connectors, definition structures, cause-effect language. Light: simple examples or transitions. Standard: everything else.",
    "podcast_talk": "Deep: humor, irony, cultural references, complex opinions. Light: filler phrases, simple agreements. Standard: everything else.",
    "other": "Deep: any sentence with 3+ unfamiliar words, idioms, or cultural context. Light: very simple sentences. Standard: everything else.",
}

# ──────────────────────────────────────────────────────────────────────────────
# LAYER 3 — LESSON WRITER SYSTEM PROMPT (content-type aware)
# ──────────────────────────────────────────────────────────────────────────────

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
7. Speak naturally and conversationally — as if talking to a friend, not reading a textbook.
8. Never use bullet points or markdown in spoken text — write as flowing speech.
9. Do not skip sentences.

## Content-Type Specific Guidance
{content_type_guidance}
"""

CONTENT_TYPE_GUIDANCE = {
    "news": """\
- Highlight formal/journalistic vocabulary and explain why reporters choose these words over simpler ones.
- When you see passive voice or reported speech, always name the structure and give the active equivalent.
- Connect vocabulary to real-world context (who is Rihanna? what is an AR-15?).
- Point out hedging language like 'allegedly', 'reportedly', 'according to'.
- Compare news register with everyday equivalents (e.g. 'behind bars' vs 'in jail').""",

    "vlog": """\
- Celebrate informal expressions — explain these are the words real people use daily.
- Decode slang and internet expressions with their origin or context.
- Compare casual grammar to formal alternatives so learners know both registers.
- Point out filler words (like, you know, I mean) and explain their social function.
- Be extra energetic and relatable — match the vlogger's casual energy.""",

    "drama_movie": """\
- Bring scenes to life — describe the emotional tone or situation when helpful.
- Explain subtext: what characters really mean beyond the literal words.
- Highlight cultural or historical references that non-native viewers might miss.
- Discuss how stress and intonation carry emotion in key lines.
- Note when dialogue grammar is intentionally non-standard (character voice).""",

    "interview": """\
- Analyze how the interviewer frames questions and the interviewee structures answers.
- Highlight deflection, hedging, and emphasis techniques used by speakers.
- Explain professional vocabulary in context.
- Point out discourse markers (well, I think, look, the thing is).
- Discuss power dynamics reflected in language choices.""",

    "lecture_educational": """\
- Build vocabulary systematically — introduce technical terms with clear definitions.
- Highlight logical connectors (therefore, however, in contrast, as a result).
- Explain sentence structures used to define concepts and give examples.
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

# ──────────────────────────────────────────────────────────────────────────────
# LAYER 3 — TOOL DEFINITIONS
# ──────────────────────────────────────────────────────────────────────────────

LESSON_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": "Insert a directive to play the original audio clip of a sentence from the video. Always call this before or after explaining a sentence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer", "description": "0-indexed sentence number"},
                    "label": {"type": "string", "description": "Short spoken cue, e.g. '来，先听一遍' or 'Let's listen first'. Keep under 15 words."}
                },
                "required": ["sentence_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_sentence",
            "description": "Add the main explanation for a sentence. Covers overall meaning, key words, and context. The core teaching moment for this sentence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {
                        "type": "string",
                        "description": "Spoken explanation. Natural, conversational. No bullet points, no markdown. Adjust detail level to the sentence depth (light/standard/deep)."
                    }
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grammar_breakdown",
            "description": "Deep-dive into the grammar structure of a sentence or phrase. Explain the structure clearly, name it, and show how it works with examples.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "structure_name": {
                        "type": "string",
                        "description": "Name of the grammar structure, e.g. 'passive voice', 'present perfect', 'relative clause', 'reported speech'"
                    },
                    "text": {
                        "type": "string",
                        "description": "Spoken grammar explanation. Start by naming the structure, show how it's formed, give 1-2 other examples from common speech."
                    }
                },
                "required": ["sentence_id", "structure_name", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cultural_context",
            "description": "Provide cultural, historical, or social background that helps the learner fully understand this sentence. Use for proper nouns, cultural events, social references, or context a native speaker would assume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "context_type": {
                        "type": "string",
                        "enum": ["person", "event", "place", "concept", "media_reference", "social_context", "historical"],
                        "description": "Category of the cultural context"
                    },
                    "text": {
                        "type": "string",
                        "description": "Spoken cultural explanation. Brief and relevant — don't over-explain. Connect it back to why it matters for understanding the language."
                    }
                },
                "required": ["sentence_id", "context_type", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "usage_and_collocation",
            "description": "Explain how a word or phrase is typically used in real life — what it collocates with, what situations it fits, common mistakes learners make.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {
                        "type": "string",
                        "description": "The word or phrase being focused on"
                    },
                    "text": {
                        "type": "string",
                        "description": "Spoken usage explanation. Give 2-3 real-life examples. Mention what it pairs with. Note any common mistakes."
                    }
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_and_style",
            "description": "Explain the formality level, style, or register of a word/phrase/sentence. Compare formal vs informal alternatives. Especially important for content mixing registers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {
                        "type": "string",
                        "description": "Spoken register explanation. Give the formal and casual equivalents. Explain when you'd use each. Keep it practical."
                    }
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pronunciation_tip",
            "description": "Focus on pronunciation — word stress, connected speech, reduction, intonation, or accent-specific features. Use this when the sentence has notable pronunciation points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "focus": {
                        "type": "string",
                        "enum": ["word_stress", "connected_speech", "vowel_reduction", "intonation", "silent_letters", "accent_feature"],
                        "description": "Type of pronunciation feature"
                    },
                    "text": {
                        "type": "string",
                        "description": "Spoken pronunciation tip. Describe it in words (you can't demo it, but you can describe it clearly). Give examples of the pattern."
                    }
                },
                "required": ["sentence_id", "focus", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "synonym_and_variation",
            "description": "Expand learner vocabulary by offering synonyms, antonyms, or natural variations of a key word or phrase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {"type": "string"},
                    "text": {
                        "type": "string",
                        "description": "Spoken explanation of synonyms/variations. For each alternative, briefly note any nuance difference. Keep it to 2-4 alternatives."
                    }
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": "Pose an interactive question to the learner to check comprehension or stimulate thinking. Use sparingly — max once every 4-5 sentences. Prefer meaningful questions over trivial ones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "question_type": {
                        "type": "string",
                        "enum": ["comprehension", "vocabulary_check", "grammar_apply", "cultural_reflection", "personal_connection"],
                        "description": "Type of question"
                    },
                    "text": {"type": "string", "description": "The question, spoken naturally."},
                    "answer_hint": {
                        "type": "string",
                        "description": "Brief hint or model answer for the learner, shown after they've had a moment to think."
                    }
                },
                "required": ["sentence_id", "question_type", "text", "answer_hint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transition_remark",
            "description": "Insert a natural transition between groups of sentences — helps the lesson flow and signals topic shifts. Use when moving to a noticeably different part of the content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer", "description": "Sentence just completed"},
                    "text": {"type": "string", "description": "Short transition remark, 1-2 sentences. Natural, not mechanical."}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stage_summary",
            "description": "After every 4-5 sentences, deliver a brief comprehension summary that reinforces key points. Helps cement memory. Do not recap everything — highlight only the 2-3 most important takeaways.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer", "description": "Last sentence covered in this stage"},
                    "text": {
                        "type": "string",
                        "description": "Spoken summary. Start with 'Good, so far we've seen...' or similar. Mention 2-3 key language points. Encourage the learner."
                    }
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lesson_intro",
            "description": "Call this ONCE at the very beginning, before any sentence. Introduce the video content, set expectations for the lesson, and get the learner excited.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Opening remarks. Mention the content type, what makes this material interesting or useful, and what language skills learners will pick up. 3-5 sentences."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lesson_outro",
            "description": "Call this ONCE at the very end, after all sentences. Wrap up the lesson with a summary of the most important language points and an encouraging closing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Closing remarks. Summarize 3-4 key takeaways from the whole lesson. Encourage continued practice. Mention one tip for using today's vocabulary in real life."
                    }
                },
                "required": ["text"]
            }
        }
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# TOOL EXECUTOR
# ──────────────────────────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, script: list):
    """将工具调用结果追加到 script 列表。"""
    if name == "lesson_intro":
        script.append({
            "type": "speak", "subtype": "intro",
            "sentence_id": None, "text": args["text"], "tts_audio": None,
        })
    elif name == "lesson_outro":
        script.append({
            "type": "speak", "subtype": "outro",
            "sentence_id": None, "text": args["text"], "tts_audio": None,
        })
    elif name == "play_sentence":
        script.append({
            "type": "play",
            "sentence_id": args["sentence_id"],
            "label": args.get("label", "请听原句"),
        })
    elif name == "explain_sentence":
        script.append({
            "type": "speak", "subtype": "explanation",
            "sentence_id": args["sentence_id"],
            "text": args["text"], "tts_audio": None,
        })
    elif name == "grammar_breakdown":
        script.append({
            "type": "speak", "subtype": "grammar",
            "sentence_id": args["sentence_id"],
            "structure_name": args.get("structure_name", ""),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "cultural_context":
        script.append({
            "type": "speak", "subtype": "culture",
            "sentence_id": args["sentence_id"],
            "context_type": args.get("context_type", ""),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "usage_and_collocation":
        script.append({
            "type": "speak", "subtype": "usage",
            "sentence_id": args["sentence_id"],
            "target": args.get("target_word_or_phrase", ""),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "register_and_style":
        script.append({
            "type": "speak", "subtype": "register",
            "sentence_id": args["sentence_id"],
            "text": args["text"], "tts_audio": None,
        })
    elif name == "pronunciation_tip":
        script.append({
            "type": "speak", "subtype": "pronunciation",
            "sentence_id": args["sentence_id"],
            "focus": args.get("focus", ""),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "synonym_and_variation":
        script.append({
            "type": "speak", "subtype": "synonym",
            "sentence_id": args["sentence_id"],
            "target": args.get("target_word_or_phrase", ""),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "ask_question":
        script.append({
            "type": "question",
            "sentence_id": args["sentence_id"],
            "question_type": args.get("question_type", "comprehension"),
            "text": args["text"],
            "answer_hint": args.get("answer_hint", ""),
        })
    elif name == "transition_remark":
        script.append({
            "type": "speak", "subtype": "transition",
            "sentence_id": args.get("after_sentence_id"),
            "text": args["text"], "tts_audio": None,
        })
    elif name == "stage_summary":
        script.append({
            "type": "speak", "subtype": "summary",
            "sentence_id": args.get("after_sentence_id"),
            "text": args["text"], "tts_audio": None,
        })


# ──────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ──────────────────────────────────────────────────────────────────────────────

class AITutor:
    """
    三层 AI 讲师 Agent。

    快速使用：
        tutor = AITutor(source_lang='en', target_lang='zh-Hans')
        script = tutor.generate_lesson_script(md_content, segments, job_output_dir)
        tutor.synthesize_tts(script, job_output_dir / 'tutor')
        tutor.build_podcast(script, job_output_dir, out_path)
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
        tts_elevenlabs_voice_id: str = None,
    ):
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        self.model = model or os.getenv('TUTOR_LLM_MODEL', 'deepseek-chat')
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.source_lang_name = LANG_NAME.get(source_lang, source_lang)
        self.target_lang_name = LANG_NAME.get(target_lang, target_lang)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # TTS
        self.tts_provider = (tts_provider or os.getenv('TTS_PROVIDER', 'openai')).lower()
        self.tts_api_key = tts_api_key or os.getenv('TTS_API_KEY') or os.getenv('OPENAI_API_KEY')
        self.tts_model = tts_model or os.getenv('TTS_MODEL', 'tts-1')
        self.tts_voice = tts_voice or os.getenv('TTS_VOICE', 'nova')
        self.tts_elevenlabs_voice_id = tts_elevenlabs_voice_id or os.getenv('ELEVENLABS_VOICE_ID', '')

    # ── Layer 1: Content Analyst ───────────────────────────────────────────────
    def _analyze_content(self, md_content: str, segments: list) -> dict:
        sentences_summary = "\n".join(
            f"[{i}] {s['text']}" for i, s in enumerate(segments)
        )
        messages = [
            {"role": "system", "content": ANALYST_SYSTEM},
            {"role": "user", "content": ANALYST_USER_TEMPLATE.format(
                md_excerpt=md_content[:3000],
                sentences_summary=sentences_summary[:2000],
                source_lang_name=self.source_lang_name,
                target_lang_name=self.target_lang_name,
            )},
        ]
        logger.info("[AITutor] Layer 1: 分析内容类型...")
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2, max_tokens=1200,
        )
        raw = _clean_json(resp.choices[0].message.content)
        profile = json.loads(raw)
        logger.info(f"[AITutor] 内容类型: {profile.get('content_type')} ({profile.get('register')})")
        return profile

    # ── Layer 2: Lesson Planner ────────────────────────────────────────────────
    def _plan_lesson(self, content_profile: dict, segments: list) -> list:
        content_type = content_profile.get("content_type", "other")
        sentences_summary = "\n".join(
            f"[{i}] {s['text']}" for i, s in enumerate(segments)
        )
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": PLANNER_USER_TEMPLATE.format(
                content_profile_json=json.dumps(content_profile, ensure_ascii=False, indent=2),
                sentences_summary=sentences_summary,
                content_type=content_type,
                depth_guidelines=DEPTH_GUIDELINES_BY_TYPE.get(content_type, DEPTH_GUIDELINES_BY_TYPE["other"]),
            )},
        ]
        logger.info("[AITutor] Layer 2: 规划课程...")
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.3, max_tokens=4096,
        )
        raw = _clean_json(resp.choices[0].message.content)
        plan = json.loads(raw)
        logger.info(f"[AITutor] 课程规划完成，{len(plan)} 句")
        return plan

    # ── Layer 3: Lesson Writer (tool-calling loop) ─────────────────────────────
    def _write_lesson(self, content_profile: dict, lesson_plan: list, audio_files: list) -> list:
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
        user_prompt = f"""\
## Lesson Plan
{json.dumps(lesson_plan, ensure_ascii=False, indent=2)}

## Available sentence audio files
{', '.join(audio_files) or 'None found'}

Begin the lesson now. Start with lesson_intro, then process every sentence in order, end with lesson_outro.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        script = []
        logger.info("[AITutor] Layer 3: 工具调用生成脚本...")

        for round_idx in range(20):  # 长视频需要更多轮次
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=LESSON_WRITER_TOOLS,
                tool_choice="auto",
                temperature=0.6,
                max_tokens=8192,
            )
            msg = resp.choices[0].message
            finish_reason = resp.choices[0].finish_reason

            if not msg.tool_calls:
                logger.info(f"[AITutor] Writer 完成（round {round_idx}），无更多工具调用")
                break

            tool_results = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                logger.debug(f"[AITutor] 工具: {tc.function.name} sid={args.get('sentence_id', args.get('after_sentence_id', '-'))}")
                _execute_tool(tc.function.name, args, script)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "ok",
                })

            messages.append(msg)
            messages.extend(tool_results)

            if finish_reason == "stop":
                break

        logger.info(f"[AITutor] 脚本生成完成，共 {len(script)} 条指令")
        return script

    # ── 公共接口：生成完整脚本 ────────────────────────────────────────────────
    def generate_lesson_script(
        self,
        md_content: str,
        segments: list,
        job_output_dir: Path,
    ) -> list:
        audio_files = sorted(f.name for f in job_output_dir.glob("sq_*.mp3"))

        content_profile = self._analyze_content(md_content, segments)
        lesson_plan = self._plan_lesson(content_profile, segments)
        script = self._write_lesson(content_profile, lesson_plan, audio_files)

        tutor_dir = job_output_dir / "tutor"
        tutor_dir.mkdir(exist_ok=True)
        (tutor_dir / "content_profile.json").write_text(
            json.dumps(content_profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (tutor_dir / "lesson_plan.json").write_text(
            json.dumps(lesson_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (tutor_dir / "tutor_script.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"[AITutor] 脚本已保存: {tutor_dir}")
        return script

    # ── TTS 合成 ──────────────────────────────────────────────────────────────
    def synthesize_tts(self, script: list, tutor_dir: Path) -> list:
        tts_targets = [(i, s) for i, s in enumerate(script) if s.get("tts_audio") is None and s["type"] == "speak"]

        logger.info(f"[AITutor] TTS: 合成 {len(tts_targets)} 条语音...")
        tutor_dir.mkdir(exist_ok=True)

        tts_idx = 0
        for item in script:
            if item["type"] != "speak":
                continue
            out_filename = f"tts_{tts_idx:04d}.mp3"
            out_path = tutor_dir / out_filename
            tts_idx += 1

            if out_path.exists():
                item["tts_audio"] = out_filename
                continue
            try:
                audio_bytes = self._tts_synthesize(item["text"])
                out_path.write_bytes(audio_bytes)
                item["tts_audio"] = out_filename
            except Exception as e:
                logger.error(f"[AITutor] TTS 失败 [{tts_idx}]: {e}")
                item["tts_audio"] = None

        (tutor_dir / "tutor_script.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return script

    def _tts_synthesize(self, text: str) -> bytes:
        if self.tts_provider == 'openai':
            return self._tts_openai(text)
        elif self.tts_provider == 'elevenlabs':
            return self._tts_elevenlabs(text)
        elif self.tts_provider == 'azure':
            return self._tts_azure(text)
        else:
            raise ValueError(f"未知 TTS 供应商: {self.tts_provider}，可选: openai | elevenlabs | azure")

    def _tts_openai(self, text: str) -> bytes:
        """OpenAI TTS — 官方 API，不走 base_url"""
        client = OpenAI(api_key=self.tts_api_key, base_url="https://api.openai.com/v1")
        resp = client.audio.speech.create(
            model=self.tts_model, voice=self.tts_voice,
            input=text, response_format="mp3",
        )
        return resp.content

    def _tts_elevenlabs(self, text: str) -> bytes:
        """ElevenLabs — 高质量真人感语音。pip install elevenlabs"""
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise ImportError("请先安装 ElevenLabs SDK: pip install elevenlabs")
        el = ElevenLabs(api_key=self.tts_api_key)
        gen = el.text_to_speech.convert(
            voice_id=self.tts_elevenlabs_voice_id,
            text=text,
            model_id=os.getenv('ELEVENLABS_MODEL_ID', 'eleven_multilingual_v2'),
            output_format="mp3_44100_128",
        )
        return b"".join(gen)

    def _tts_azure(self, text: str) -> bytes:
        """Azure Cognitive Services TTS. pip install azure-cognitiveservices-speech"""
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            raise ImportError("请先安装 Azure SDK: pip install azure-cognitiveservices-speech")
        import tempfile
        key = os.getenv('AZURE_TTS_KEY', self.tts_api_key)
        region = os.getenv('AZURE_TTS_REGION', 'eastus')
        voice = os.getenv('AZURE_TTS_VOICE', 'en-US-JennyNeural')
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        cfg.speech_synthesis_voice_name = voice
        cfg.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_path = f.name
        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=tmp_path)
        synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)
        result = synth.speak_text_async(text).get()
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise RuntimeError(f"Azure TTS 失败: {result.reason}")
        data = Path(tmp_path).read_bytes()
        Path(tmp_path).unlink(missing_ok=True)
        return data

    # ── Podcast 拼接 ──────────────────────────────────────────────────────────
    def build_podcast(self, script: list, job_output_dir: Path, out_path: Path) -> Path:
        """FFmpeg concat 拼接 TTS + 原句音频 → 完整 podcast MP3"""
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
                    logger.warning(f"[AITutor] 找不到原句音频: {sq}")

        if not entries:
            raise RuntimeError("没有可拼接的音频片段")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for e in entries:
                f.write(f"file '{e}'\n")
            concat_list = f.name

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:a", "libmp3lame", "-q:a", "4",
            str(out_path),
        ]
        logger.info(f"[AITutor] FFmpeg 拼接 {len(entries)} 片段 → {out_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(concat_list)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 拼接失败:\n{result.stderr}")
        logger.info(f"[AITutor] Podcast 完成: {out_path}")
        return out_path

    # ── SSE 流式生成 ──────────────────────────────────────────────────────────
    def stream_lesson_events(
        self, md_content: str, segments: list, job_output_dir: Path
    ) -> Iterator[dict]:
        try:
            audio_files = sorted(f.name for f in job_output_dir.glob("sq_*.mp3"))
            tutor_dir = job_output_dir / "tutor"
            tutor_dir.mkdir(exist_ok=True)

            yield {"event": "status", "data": {"message": "正在分析内容类型..."}}
            profile = self._analyze_content(md_content, segments)
            yield {"event": "profile_ready", "data": profile}

            yield {"event": "status", "data": {"message": "正在规划课程..."}}
            plan = self._plan_lesson(profile, segments)
            yield {"event": "plan_ready", "data": {"total": len(plan)}}

            yield {"event": "status", "data": {"message": "正在生成讲解脚本..."}}
            script = self._write_lesson(profile, plan, audio_files)
            for i, item in enumerate(script):
                yield {"event": "script_item", "data": item, "index": i}

            yield {"event": "status", "data": {"message": "正在合成语音..."}}
            script = self.synthesize_tts(script, tutor_dir)
            for i, item in enumerate(script):
                if item["type"] == "speak" and item.get("tts_audio"):
                    yield {"event": "tts_ready", "data": {"index": i, "audio": item["tts_audio"]}}

            (tutor_dir / "content_profile.json").write_text(
                json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (tutor_dir / "tutor_script.json").write_text(
                json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            yield {"event": "done", "data": {"total": len(script)}}

        except Exception as e:
            logger.exception("[AITutor] stream_lesson_events 异常")
            yield {"event": "error", "data": {"message": str(e)}}


# ──────────────────────────────────────────────────────────────────────────────
# UTILS
# ──────────────────────────────────────────────────────────────────────────────

def _clean_json(raw: str) -> str:
    """去掉 LLM 可能返回的 markdown code fence"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]  # 去掉 ```json 行
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    return raw.strip()
