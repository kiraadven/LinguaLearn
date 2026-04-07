"""
ContentAnalyzer — Skill 1: 内容分析

分析视频内容的类型、难度、风格、文化背景。
输出：content_profile dict

融合教学知识库中的分类方法论。
"""

import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONTENT ANALYZER SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

CONTENT_ANALYZER_SYSTEM = """\
You are a linguistic content analyst specializing in language learning material.
Analyze the provided video transcript and produce a structured content profile.

Your job is to identify:
1. What TYPE of content this is (news, vlog, drama, interview, lecture, podcast, etc.)
2. The DIFFICULTY LEVEL (CEFR A1-C2)
3. The REGISTER (formal, semi-formal, casual, mixed)
4. Key THEMES and CULTURAL CONTEXT
5. TEACHING FOCUS AREAS (what students should learn)
6. TEACHER TONE to use when explaining

This information guides the lesson planner and writer in crafting appropriate lessons.

Output ONLY valid JSON — no markdown fences, no prose outside JSON.
"""

CONTENT_ANALYZER_USER_TEMPLATE = """\
## Video Transcript (first 3000 chars)
{md_excerpt}

## Sentence List
{sentences_summary}

## Task
Analyze this content and produce a JSON object with these fields:

{{
  "content_type": "news" | "vlog" | "drama_movie" | "interview" | "lecture_educational" | "podcast_talk" | "other",
  "content_type_confidence": 0.0-1.0,
  "content_type_reasoning": "one sentence explaining your classification",
  "register": "formal" | "semi_formal" | "casual" | "mixed",
  "estimated_cefr": "A1" | "A2" | "B1" | "B2" | "C1" | "C2",
  "dominant_themes": ["theme1", "theme2", ...],
  "speaker_profile": "description of who is speaking",
  "notable_language_features": ["feature1", "feature2", ...],
  "cultural_context": "background knowledge needed",
  "teaching_focus_priority": ["focus1", "focus2", ...],
  "tone_for_teacher": "warm_casual" | "encouraging_professional" | "analytical_academic"
}}

Return ONLY the JSON object.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONTENT ANALYZER CLASS
# ─────────────────────────────────────────────────────────────────────────────


class ContentAnalyzer(BaseAgent):
    """分析内容类型、难度、风格的Agent"""

    def __init__(self, **kwargs):
        super().__init__(agent_name="ContentAnalyzer", **kwargs)

    def analyze(self, md_content: str, segments: list) -> dict:
        """
        分析视频内容。

        Args:
            md_content: 视频稿件内容（markdown 或纯文本）
            segments: 句子列表 [{"text": "...", ...}, ...]

        Returns:
            content_profile dict
        """
        logger.info(f"[ContentAnalyzer] 分析内容... ({len(segments)} 句)")

        # 1. 加载教学知识库
        teaching_methodology = self.load_reference_file("teaching_methodology.md")

        # 2. 构建系统提示词
        system_prompt = self._build_system_prompt(teaching_methodology)

        # 3. 构建用户提示词
        user_prompt = self._build_user_prompt(md_content, segments)

        # 4. 调用 LLM 分析
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        profile = self._request_json(
            messages=messages,
            temperature=0.2,  # 低温度保证分析准确
            max_tokens=1500,
            scene="content_analysis",
            expected_type=dict,
        )

        logger.info(
            f"[ContentAnalyzer] 完成: type={profile.get('content_type')}, "
            f"cefr={profile.get('estimated_cefr')}, "
            f"register={profile.get('register')}"
        )
        return profile

    def _build_system_prompt(self, teaching_methodology: str) -> str:
        """构建系统提示词"""
        parts = [CONTENT_ANALYZER_SYSTEM]

        if teaching_methodology:
            parts.append("\n## Teaching Methodology Reference\n")
            # 提取前 1500 字
            parts.append(teaching_methodology[:1500])

        return "\n".join(parts)

    @staticmethod
    def _build_user_prompt(md_content: str, segments: list) -> str:
        """构建用户提示词"""
        # 提取前 3000 字作为示例
        md_excerpt = md_content[:3000]

        # 生成句子摘要
        sentences_summary = ContentAnalyzer._sentence_summary(segments)

        return CONTENT_ANALYZER_USER_TEMPLATE.format(
            md_excerpt=md_excerpt,
            sentences_summary=sentences_summary,
        )

    @staticmethod
    def _sentence_summary(segments: list, max_chars: int = 2000) -> str:
        """生成句子列表摘要"""
        rows = [f"[{i}] {s.get('text', '').strip()}" for i, s in enumerate(segments)]
        return "\n".join(rows)[:max_chars]
