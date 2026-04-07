"""
LessonPlanner — Skill 2: 课程规划

根据内容分析结果，逐句规划讲解策略。
输出：lesson_plan list

融合 lesson_pacing.md 的深度分配和节奏指导。
"""

import json
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LESSON PLANNER SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

LESSON_PLANNER_SYSTEM = """\
You are a language learning curriculum designer.
Given a content profile and sentence list, produce a per-sentence lesson plan.

Your plan should:
1. Assign DEPTH to each sentence (light / standard / deep)
   - Follow the distribution: Light 30%, Standard 50%, Deep 20%
   - Prioritize deep explanations for content_type-specific difficult items

2. Identify KEY TEACHING POINTS for each sentence
   - focus_items: words/phrases that need explanation
   - grammar_point: if relevant
   - cultural_note: if relevant
   - pronunciation_note: if relevant

3. Plan INTERACTION OPPORTUNITIES
   - Questions to check understanding
   - Replays after explanation (especially for deep sentences)
   - Summary points after every 4-5 sentences

4. Ensure all TEACHING PRIORITIES are covered
   - Use the teaching_focus_priority from content profile
   - Deep sentences should address these priorities

Output ONLY valid JSON — no markdown fences, no prose outside JSON.
"""

LESSON_PLANNER_USER_TEMPLATE = """\
## Content Profile
{content_profile_json}

## Sentence List
{sentences_summary}

## Task
Produce a JSON array. Each element covers ONE sentence (0-indexed, in order).

Each element should have:
{{
  "sentence_id": int (0-indexed),
  "sentence_text": "the original sentence",
  "depth": "light" | "standard" | "deep",
  "focus_items": ["word1", "phrase2"],
  "grammar_point": "grammar point or null",
  "cultural_note": "cultural context or null",
  "pronunciation_note": "pronunciation tip or null",
  "register_note": "register/formality note or null",
  "collocation_focus": ["collocation1"],
  "replay_after_explain": bool,
  "insert_question_after": bool,
  "insert_summary_after": bool
}}

Depth guidelines for {content_type}:
{depth_guidelines}

Return ONLY the JSON array.
"""

# Depth guidelines by content type
DEPTH_GUIDELINES_BY_TYPE = {
    "news": "Deep: passive voice, hedging language, idioms, legal/official terms, complex noun phrases. Light: simple transition phrases, pure facts with common vocabulary. Standard: everything else.",
    "vlog": "Deep: slang, internet expressions, cultural references, non-standard grammar. Light: filler words, simple connectors. Standard: everything else.",
    "drama_movie": "Deep: emotionally loaded lines, cultural references, idiomatic dialogue, subtext. Light: simple action descriptions. Standard: everything else.",
    "interview": "Deep: rhetorical devices, hedging language, complex opinion structures. Light: simple factual statements. Standard: everything else.",
    "lecture_educational": "Deep: technical vocabulary, logical connectors, definition structures, cause-effect language. Light: simple examples or transitions. Standard: everything else.",
    "podcast_talk": "Deep: humor, irony, cultural references, complex opinions. Light: filler phrases, simple agreements. Standard: everything else.",
    "other": "Deep: any sentence with 3+ unfamiliar words, idioms, or cultural context. Light: very simple sentences. Standard: everything else.",
}

# ─────────────────────────────────────────────────────────────────────────────
# LESSON PLANNER CLASS
# ─────────────────────────────────────────────────────────────────────────────


class LessonPlanner(BaseAgent):
    """规划课程讲解策略的Agent"""

    def __init__(self, **kwargs):
        super().__init__(agent_name="LessonPlanner", **kwargs)

    def plan(self, content_profile: dict, segments: list) -> list:
        """
        规划课程。

        Args:
            content_profile: ContentAnalyzer 的输出
            segments: 句子列表

        Returns:
            lesson_plan list
        """
        logger.info(f"[LessonPlanner] 规划课程... ({len(segments)} 句)")

        # 1. 加载教学知识库
        lesson_pacing = self.load_reference_file("pedagogical_frameworks/lesson_pacing.md")

        # 2. 构建系统提示词
        system_prompt = self._build_system_prompt(lesson_pacing)

        # 3. 构建用户提示词
        user_prompt = self._build_user_prompt(content_profile, segments)

        # 4. 调用 LLM 规划
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        lesson_plan = self._request_json(
            messages=messages,
            temperature=0.3,  # 较低温度，保证规划一致性
            max_tokens=4096,
            scene="lesson_planning",
            expected_type=list,
        )

        logger.info(
            f"[LessonPlanner] 完成规划: "
            f"deep={sum(1 for s in lesson_plan if s.get('depth')=='deep')}, "
            f"standard={sum(1 for s in lesson_plan if s.get('depth')=='standard')}, "
            f"light={sum(1 for s in lesson_plan if s.get('depth')=='light')}"
        )
        return lesson_plan

    def _build_system_prompt(self, lesson_pacing: str) -> str:
        """构建系统提示词"""
        parts = [LESSON_PLANNER_SYSTEM]

        if lesson_pacing:
            parts.append("\n## Lesson Pacing Reference (from knowledge base)\n")
            parts.append(lesson_pacing[:2000])

        return "\n".join(parts)

    @staticmethod
    def _build_user_prompt(content_profile: dict, segments: list) -> str:
        """构建用户提示词"""
        content_type = content_profile.get("content_type", "other")
        depth_guidelines = DEPTH_GUIDELINES_BY_TYPE.get(
            content_type, DEPTH_GUIDELINES_BY_TYPE["other"]
        )

        # 生成句子摘要
        sentences_summary = LessonPlanner._sentence_summary(segments)

        return LESSON_PLANNER_USER_TEMPLATE.format(
            content_profile_json=json.dumps(content_profile, ensure_ascii=False, indent=2),
            sentences_summary=sentences_summary,
            content_type=content_type,
            depth_guidelines=depth_guidelines,
        )

    @staticmethod
    def _sentence_summary(segments: list, max_chars: int = 3000) -> str:
        """生成句子列表摘要"""
        rows = [f"[{i}] {s.get('text', '').strip()}" for i, s in enumerate(segments)]
        return "\n".join(rows)[:max_chars]
