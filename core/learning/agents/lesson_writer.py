"""
LessonWriter — Skill 3: 脚本生成（核心）

工具调用驱动生成互动讲解脚本。
这是最重要的Agent，融合所有教学知识库。

输出：tutor_script list（包含play_sentence, explain_sentence等指令）
"""

import json
import logging
from typing import Callable, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LESSON WRITER SYSTEM PROMPT COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

LESSON_WRITER_BASE_SYSTEM = """\
You are an enthusiastic, knowledgeable language teacher delivering a spoken one-on-one lesson.
You speak the target language, quoting the source language only when necessary.

## Core Teaching Principles (Integrated from Knowledge Base)

Your goal is NOT just to explain content, but to create a LEARNING experience where students:
1. Understand MEANING (what it means and why it matters)
2. Grasp FORM (how it's structured)
3. Learn USAGE (when and how to use it in real life)
4. See CONTRAST (how it differs from similar expressions)
5. Make CONNECTIONS (link to their existing knowledge and experience)

## Key Rules for This Lesson

1. **ONLY produce output by calling tools** — never output free text.
2. **Process EVERY sentence** in the lesson plan, in order.
3. **Follow the lesson plan's depth instructions**:
   - For DEEP sentences: play → explain → (grammar/culture/usage tips) → play again
   - For STANDARD sentences: play → explain → (optional replay)
   - For LIGHT sentences: brief explain → play

4. **Speak naturally and conversationally**:
   - Like talking to a friend, not reading a script
   - Allow natural pauses and thinking moments
   - Show genuine enthusiasm for interesting points
   - Use personal anecdotes when relevant

5. **Apply CLT (Communicative Language Teaching)**:
   - Focus on MEANING over mechanical rules
   - Create authentic learning contexts
   - Use real examples from real language use
   - Invite student participation frequently

6. **Use Scaffolding strategically**:
   - Model complex explanations, then reduce support
   - Ask guiding questions to help students discover answers
   - Progress from simple to complex gradually

7. **Question effectively**:
   - Use questions to CHECK understanding, not just fill time
   - Give students 3-5 seconds to think before expecting answers
   - Provide feedback that builds on their responses
   - Vary question types: from recall to analysis

8. **Never use bullet points or markdown in spoken text**.
   - Explain naturally, as continuous speech
   - Use transitions: "So...", "Here's the thing...", "Notice how..."

9. **Pace and energy**:
   - Mix deep explanations with quick/light sentences to maintain energy
   - Don't explain EVERYTHING deeply (that's exhausting)
   - Deep explanations for vocabulary/grammar/culture; light for transitions/simple points
"""

# Content-specific teaching guidance
CONTENT_TYPE_GUIDANCE = {
    "news": """\
- Highlight formal/journalistic vocabulary and explain why reporters choose these words
- When you see passive voice or reported speech, name the structure and give the active equivalent
- Connect vocabulary to real-world context and news purposes
- Point out hedging language like 'allegedly', 'reportedly', 'according to'
- Explain register: compare journalistic language with everyday equivalents
- Help students understand journalistic ethics and precision requirements""",

    "vlog": """\
- Celebrate informal expressions — these are the words real people use daily
- Decode slang and internet expressions with their origin or cultural context
- Compare casual grammar to formal alternatives (and when each is appropriate)
- Point out filler words (like, you know, um) and explain their social function
- Be extra energetic and relatable — match the vlog's tone
- Show how personality comes through in language choices""",

    "drama_movie": """\
- Bring scenes to life — describe the emotional tone or situation when helpful
- Explain subtext: what characters really mean beyond the literal words
- Highlight cultural or historical references and their significance
- Discuss how stress, intonation, and emotion carry meaning
- Note when dialogue grammar is intentionally non-standard (character voice)
- Use lines as windows into character motivation and relationships""",

    "interview": """\
- Analyze how the interviewer frames questions and the interviewee structures answers
- Highlight deflection, hedging, and emphasis techniques professionals use
- Explain professional vocabulary in context
- Point out discourse markers that structure arguments (well, I think, look, the thing is)
- Discuss power dynamics reflected in language choices
- Show how people navigate difficult questions strategically""",

    "lecture_educational": """\
- Build vocabulary systematically — introduce technical terms with clear definitions
- Highlight logical connectors (therefore, however, in contrast, as a result)
- Explain sentence structures used to define concepts and build arguments
- Pause periodically to synthesize what has been explained
- Connect new terms to concepts the learner may already know
- Show the internal logic of complex academic explanations""",

    "podcast_talk": """\
- Embrace humor and irony — explain jokes and cultural references
- Highlight how speakers signal opinion versus fact
- Note when speakers interrupt or build on each other's points
- Explain colloquial expressions and informal transitions
- Discuss how the conversational rhythm and energy differ from formal speech
- Show camaraderie and personality in language choices""",

    "other": """\
- Adapt your teaching style to the content you encounter
- Prioritize explaining vocabulary that appears unusual or context-specific
- Always connect words to their broader usage outside this specific context
- Maintain flexibility in what you emphasize based on learning value""",
}

# ─────────────────────────────────────────────────────────────────────────────
# LESSON WRITER TOOLS DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

LESSON_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lesson_intro",
            "description": "Call ONCE at the very beginning. Introduce the lesson topic, why it's interesting, and what students will learn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Opening remarks (3-5 sentences). Set context, build curiosity, establish the lesson's goal."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": "Play the original audio clip of a sentence from the video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "label": {"type": "string", "description": "Natural spoken cue before playing (e.g., 'Here's the sentence' or 'Listen carefully'). Keep under 15 words."}
                },
                "required": ["sentence_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_sentence",
            "description": "Main explanation for a sentence — meaning, key words, context. Use CLT principles: connect to student experience, show real usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {"type": "string", "description": "Spoken explanation in natural, conversational style. No bullet points. Show meaning, usage context, and why it matters."}
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grammar_breakdown",
            "description": "Deep-dive into grammar structure. Don't just explain the rule—explain WHY and WHEN to use it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "structure_name": {"type": "string", "description": "Name of the grammar point (e.g., 'passive voice', 'present perfect')"},
                    "text": {"type": "string", "description": "Explanation that shows: what it is, how it's formed, why speakers use it, and how it differs from alternatives."}
                },
                "required": ["sentence_id", "structure_name", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cultural_context",
            "description": "Provide cultural, historical, or social background. Help students understand not just WHAT to say, but WHY English speakers say it that way.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "context_type": {
                        "type": "string",
                        "enum": ["person", "event", "place", "concept", "media_reference", "social_context", "historical", "cultural_value"]
                    },
                    "text": {"type": "string", "description": "Explain the cultural background and what it reveals about English-speaking culture."}
                },
                "required": ["sentence_id", "context_type", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "usage_and_collocation",
            "description": "Show how a word/phrase is actually used in real life. Give multiple real-world examples.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {"type": "string"},
                    "text": {"type": "string", "description": "Explain typical usage patterns, common collocations, and real examples. Show how this differs from formal/textbook usage."}
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pronunciation_tip",
            "description": "Focus on pronunciation features that students often struggle with.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "focus": {
                        "type": "string",
                        "enum": ["word_stress", "connected_speech", "vowel_reduction", "intonation", "silent_letters", "accent_feature"]
                    },
                    "text": {"type": "string", "description": "Clear explanation with contrasts and practice tips."}
                },
                "required": ["sentence_id", "focus", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": "Ask a question to engage students and check understanding. Use sparingly — max once every 4-5 sentences. Always give wait time!",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "question_type": {
                        "type": "string",
                        "enum": ["comprehension", "vocabulary_check", "grammar_apply", "cultural_reflection", "personal_connection"]
                    },
                    "text": {"type": "string", "description": "The actual question. Make it clear, interesting, and answerable."},
                    "answer_hint": {"type": "string", "description": "A helpful hint if students struggle (to guide them toward the answer)."}
                },
                "required": ["sentence_id", "question_type", "text", "answer_hint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transition_remark",
            "description": "Natural transition between groups of sentences. Keep the lesson flowing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer"},
                    "text": {"type": "string", "description": "Short, natural remark to connect ideas or move to the next section."}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stage_summary",
            "description": "After every 4-5 sentences, deliver a brief summary to help students consolidate learning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer"},
                    "text": {"type": "string", "description": "Brief summary (2-3 sentences) highlighting key points covered so far."}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lesson_outro",
            "description": "Call ONCE at the very end. Wrap up with key takeaways, encourage continued learning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Closing remarks with 3-4 key takeaways. Celebrate what students learned, encourage confidence."}
                },
                "required": ["text"]
            }
        }
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LESSON WRITER CLASS
# ─────────────────────────────────────────────────────────────────────────────


class LessonWriter(BaseAgent):
    """生成讲解脚本的核心Agent，融合所有教学知识库"""

    def __init__(self, **kwargs):
        super().__init__(agent_name="LessonWriter", **kwargs)

    def write(
        self,
        content_profile: dict,
        lesson_plan: list,
        audio_files: list,
        target_lang: str = "en",
        source_lang: str = "zh-Hans",
    ) -> list:
        """
        生成讲解脚本。

        Args:
            content_profile: ContentAnalyzer 的输出
            lesson_plan: LessonPlanner 的输出
            audio_files: 可用的音频文件列表
            target_lang: 学习者母语
            source_lang: 要学的语言

        Returns:
            tutor_script 列表（包含play/speak/question指令）
        """
        logger.info(f"[LessonWriter] 生成讲解脚本，共 {len(lesson_plan)} 句")

        # 1. 加载所有教学知识库文件
        knowledge_base = self.load_reference_files([
            "teaching_methodology.md",
            "teacher_principles.md",
            "pedagogical_frameworks/clt_principles.md",
            "pedagogical_frameworks/scaffolding_guide.md",
            "pedagogical_frameworks/questioning_strategies.md",
            "pedagogical_frameworks/lesson_pacing.md",
        ])

        logger.debug(f"[LessonWriter] 加载了 {len(knowledge_base)} 个知识库文件")

        # 2. 构建融合知识库的系统提示词
        system_prompt = self._build_system_prompt(
            content_profile,
            knowledge_base,
            target_lang,
            source_lang,
        )

        # 3. 构建用户提示词（lesson plan + context）
        user_prompt = self._build_user_prompt(
            lesson_plan,
            content_profile,
            audio_files,
        )

        # 4. 调用 writer loop（工具调用驱动生成）
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        script = self._run_writer_loop(
            messages=messages,
            tools=LESSON_WRITER_TOOLS,
            max_rounds=30,  # 防止无限循环
        )

        logger.info(f"[LessonWriter] 完成，生成 {len(script)} 条指令")
        return script

    def _build_system_prompt(
        self,
        content_profile: dict,
        knowledge_base: dict,
        target_lang: str,
        source_lang: str,
    ) -> str:
        """构建融合知识库的系统提示词"""

        content_type = content_profile.get("content_type", "other")
        tone = content_profile.get("tone_for_teacher", "warm_casual")
        speaker_profile = content_profile.get("speaker_profile", "unknown")
        cultural_context = content_profile.get("cultural_context", "")

        # 基础系统提示词
        parts = [LESSON_WRITER_BASE_SYSTEM]

        # 加入内容类型特定指导
        parts.append("\n## Content-Type Specific Teaching Approach\n")
        parts.append(CONTENT_TYPE_GUIDANCE.get(content_type, CONTENT_TYPE_GUIDANCE["other"]))

        # 加入本课程的上下文
        parts.append(f"\n## This Lesson's Context\n")
        parts.append(f"- Content type: {content_type}")
        parts.append(f"- Speaker profile: {speaker_profile}")
        parts.append(f"- Cultural context: {cultural_context}")
        parts.append(f"- Teacher tone: {tone} (warm/encouraging, not robotic)")
        parts.append(f"- Learner's native language: {target_lang}")
        parts.append(f"- Language being taught: {source_lang}")

        # 加入关键的教学知识库内容
        parts.append("\n## Teaching Principles from Knowledge Base\n")
        parts.append("### CLT (Communicative Language Teaching) Principles:")
        if "clt_principles.md" in knowledge_base:
            # 提取关键部分（前2000字左右）
            clt_content = knowledge_base["clt_principles.md"][:2000]
            parts.append(clt_content)

        parts.append("\n### Scaffolding (Support Reduction Strategy):")
        if "scaffolding_guide.md" in knowledge_base:
            scaff_content = knowledge_base["scaffolding_guide.md"][:1500]
            parts.append(scaff_content)

        parts.append("\n### Effective Questioning:")
        if "questioning_strategies.md" in knowledge_base:
            q_content = knowledge_base["questioning_strategies.md"][:1500]
            parts.append(q_content)

        parts.append("\n### Pacing and Depth Distribution:")
        if "lesson_pacing.md" in knowledge_base:
            pace_content = knowledge_base["lesson_pacing.md"][:1200]
            parts.append(pace_content)

        parts.append("\n## Your Task\n")
        parts.append("""\
Generate a lesson script by calling tools for each sentence in the lesson plan.
The script should feel like a real teacher explaining, not a machine:
- Natural language with occasional pauses
- Genuine interest in the topic
- Mix of deep and light explanations (don't explain EVERYTHING equally)
- Frequent student engagement through questions and applications
- Support that gradually reduces as students learn
        """)

        return "\n".join(parts)

    def _build_user_prompt(
        self,
        lesson_plan: list,
        content_profile: dict,
        audio_files: list,
    ) -> str:
        """构建用户提示词"""

        parts = [
            "## Lesson Plan",
            json.dumps(lesson_plan, ensure_ascii=False, indent=2),
            "",
            "## Available Sentence Audio Files",
            ", ".join(audio_files) if audio_files else "None",
            "",
            "## Key Notes from Content Analysis",
            f"- CEFR Level: {content_profile.get('estimated_cefr', 'B1')}",
            f"- Register: {content_profile.get('register', 'mixed')}",
            f"- Teaching focus areas: {', '.join(content_profile.get('teaching_focus_priority', []))}",
            "",
            "## Instructions",
            "1. Start with lesson_intro",
            "2. Process EVERY sentence in the lesson plan, in order",
            "3. For DEEP sentences: play → explain (detailed) → grammar/culture/usage tips → optional replay",
            "4. For STANDARD sentences: play → explain (moderate) → optional replay",
            "5. For LIGHT sentences: explain (brief) → play",
            "6. Ask questions sparingly (max 1 per 4-5 sentences)",
            "7. Add stage summaries after every 4-5 sentences",
            "8. End with lesson_outro",
            "9. Speak naturally, like a real teacher—show genuine enthusiasm!",
            "",
            "Now begin the lesson.",
        ]

        return "\n".join(parts)

    def _run_writer_loop(
        self,
        messages: list,
        tools: list,
        max_rounds: int = 30,
    ) -> list:
        """
        工具调用循环，生成脚本。

        这个方法与 ai_lesson.py 中的 _run_writer_loop 类似，
        但集成到了 Agent 中。
        """
        script = []
        logger.info(f"[LessonWriter] 开始工具调用循环 (max {max_rounds} 轮)")

        for round_idx in range(max_rounds):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            msg = resp.choices[0].message
            finish_reason = resp.choices[0].finish_reason

            # 如果没有工具调用，说明生成完成
            if not msg.tool_calls:
                logger.info(f"[LessonWriter] 轮 {round_idx}: 无更多工具调用，生成完成")
                break

            # 处理每个工具调用
            tool_results = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    logger.debug(f"[LessonWriter] 工具: {tc.function.name}")

                    # 执行工具（追加到脚本）
                    self._execute_tool(tc.function.name, args, script)

                    # 反馈给模型（告诉它执行成功）
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "Done."
                    })
                except Exception as e:
                    logger.warning(f"[LessonWriter] 工具执行错误: {tc.function.name}: {e}")
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"Error: {str(e)}"
                    })

            # 更新消息历史
            messages.append(msg)
            messages.extend(tool_results)

            if finish_reason == "stop":
                logger.info(f"[LessonWriter] 轮 {round_idx}: 模型停止生成")
                break

        return script

    @staticmethod
    def _execute_tool(name: str, args: dict, script: list):
        """执行工具调用，追加到脚本"""

        if name == "lesson_intro":
            script.append({
                "type": "speak",
                "subtype": "intro",
                "sentence_id": None,
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "lesson_outro":
            script.append({
                "type": "speak",
                "subtype": "outro",
                "sentence_id": None,
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "play_sentence":
            script.append({
                "type": "play",
                "sentence_id": args["sentence_id"],
                "label": args.get("label", "Listen")
            })
        elif name == "explain_sentence":
            script.append({
                "type": "speak",
                "subtype": "explanation",
                "sentence_id": args["sentence_id"],
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "grammar_breakdown":
            script.append({
                "type": "speak",
                "subtype": "grammar",
                "sentence_id": args["sentence_id"],
                "structure_name": args.get("structure_name", ""),
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "cultural_context":
            script.append({
                "type": "speak",
                "subtype": "culture",
                "sentence_id": args["sentence_id"],
                "context_type": args.get("context_type", ""),
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "usage_and_collocation":
            script.append({
                "type": "speak",
                "subtype": "usage",
                "sentence_id": args["sentence_id"],
                "target": args.get("target_word_or_phrase", ""),
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "pronunciation_tip":
            script.append({
                "type": "speak",
                "subtype": "pronunciation",
                "sentence_id": args["sentence_id"],
                "focus": args.get("focus", ""),
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "ask_question":
            script.append({
                "type": "question",
                "sentence_id": args["sentence_id"],
                "question_type": args.get("question_type", "comprehension"),
                "text": args["text"],
                "answer_hint": args.get("answer_hint", "")
            })
        elif name == "transition_remark":
            script.append({
                "type": "speak",
                "subtype": "transition",
                "sentence_id": args.get("after_sentence_id"),
                "text": args["text"],
                "tts_audio": None
            })
        elif name == "stage_summary":
            script.append({
                "type": "speak",
                "subtype": "summary",
                "sentence_id": args.get("after_sentence_id"),
                "text": args["text"],
                "tts_audio": None
            })
