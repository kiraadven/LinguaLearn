"""
Prompt builder for Global Mode (全局复习 / 自由闲聊模式).

In global mode the AI tutor:
  - Takes on the language-specific teacher persona (no longer hardcoded to English)
  - Uses the learner's long-term graph for personalized conversation
  - Can review vocabulary / grammar from any past session in any of the 8 languages
  - Engages in natural conversation to understand the learner better
  - Extracts insights (interests, personal info) that enrich the learner graph
  - Gently reminds the learner to do quizzes if completion rate is low

SLA rationale:
  - Krashen: Low-affective-filter free conversation maximises acquisition
  - Long: Unstructured interaction still promotes negotiation of meaning
  - Nation: Recycling known vocabulary in new contexts strengthens retention
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from content.language_profiles import get_language_profile

if TYPE_CHECKING:
    from memory.manager import MemoryContext
    from session.learner_profile import LearnerProfile


_GLOBAL_PRINCIPLES = """【全局模式原则】
1. 以自然对话为主，不要结构化教学，不要给学生压力。
2. 如果觉察到学习者的兴趣、职业、生活信息等，在回复末尾用 JSON 记录：
   ```json {"insights": {"key": "value"}, "interests": ["tag1", "tag2"]} ```
   只在有确实获得新信息时才附加 JSON，不要每次都加。
3. 如果学习者 Quiz 完成率 < 50%，适时（不强迫）提醒做题。
4. 可以自然地复习之前学过的词汇或语法，但要像朋友聊天一样带出，不要像考试。
5. 如果学习者想学特定内容，积极配合，立即切换话题。
6. 控制回复长度：3句话以内。
7. 情绪优先：如果学习者表现出挫败感，先共情再教学。"""


def build_global_prompt(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    target_language: str = "en",
) -> str:
    """
    Build the full system prompt for a global-mode (free chat / review) turn.

    Args:
        memory_context:  MemoryContext from MemoryManager (quiz + graph)
        profile:         LearnerProfile (level, l1, last_session_summary …)
        student_input:   What the student just said (empty → teacher opens)
        target_language: ISO code of the language being studied
    """
    lang_profile = get_language_profile(target_language)
    lang_display = lang_profile.get("display_name", target_language)

    parts: list[str] = []

    # ── 1. Teacher persona (language-specific) ─────────────────────────────────
    parts.append(lang_profile["teacher_persona"])

    # ── 2. Global mode principles ──────────────────────────────────────────────
    parts.append(_GLOBAL_PRINCIPLES)

    # ── 3. Language-specific tips relevant to chat / review (top 3) ───────────
    lang_principles: list[str] = lang_profile.get("teaching_principles", [])
    if lang_principles:
        # In global mode we focus on communication, so take the first 3
        chat_principles = lang_principles[:3]
        principles_text = "\n".join(f"- {p}" for p in chat_principles)
        parts.append(
            f"【{lang_display}闲聊/复习模式教学要点】\n{principles_text}"
        )

    # ── 4. Learner info ────────────────────────────────────────────────────────
    learner_block = (
        f"【学习者】{profile.name}，{lang_display}水平 {profile.level}，母语 {profile.l1}\n"
        f"上次课摘要：{profile.last_session_summary or '暂无'}"
    )
    parts.append(learner_block)

    # ── 5. Long-term memory context ────────────────────────────────────────────
    mem_block = memory_context.to_prompt_block(mode="global")
    if mem_block:
        parts.append(f"【学习者长期记忆】\n{mem_block}")

    # ── 6. Quiz reminder (if completion rate is low) ───────────────────────────
    quiz = memory_context.quiz_record
    if quiz.has_data() and quiz.completion_rate < 0.5:
        parts.append(
            f"【Quiz 提醒】该学习者 Quiz 完成率仅 {quiz.completion_rate:.0%}，"
            "可以在对话合适时机（不强迫）自然地提醒他/她做练习来巩固记忆。"
        )

    # ── 7. Student input ───────────────────────────────────────────────────────
    if student_input:
        parts.append(f"【学生说】{student_input}")
    else:
        parts.append("【学生】（等待老师开场——请用轻松自然的方式打招呼或提起上次课内容）")

    # ── 8. Response instructions ───────────────────────────────────────────────
    parts.append(
        "请自然地回应（用目标语言为主，必要时可加母语解释）。\n"
        "如有洞察到学习者新信息，在末尾附加 JSON 块；否则直接回复即可，不要附加空 JSON。"
    )

    return "\n\n".join(parts)
