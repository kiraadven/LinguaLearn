"""
Prompt builders for Global Mode (全局复习 / 自由闲聊模式).

Refactored to system prompt + per-turn message, so the model can use actual
chat history as messages while keeping policy/context cleanly separated.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_tutor.content.language_profiles import get_language_profile

if TYPE_CHECKING:
    from ai_tutor.memory.manager import MemoryContext
    from ai_tutor.session.learner_profile import LearnerProfile


def _memory_snapshot(memory_context: "MemoryContext") -> str:
    lines: list[str] = []

    graph_summary = memory_context.learner_graph.to_prompt_summary()
    if graph_summary:
        lines.append(f"[学习者画像]\n{graph_summary}")

    quiz = memory_context.quiz_record
    if quiz.has_data():
        lines.append(f"[Quiz] {quiz.to_prompt_summary()}")

    attn = memory_context.short_term.avg_attention
    attn_label = "高" if attn >= 0.7 else ("中" if attn >= 0.4 else "低")
    lines.append(f"[注意力] {attn_label}（{attn:.1f}）")

    return "\n\n".join(lines)


def build_global_system_prompt(
    profile: "LearnerProfile",
    target_language: str = "en",
    output_style: str = "coach",
) -> str:
    """Build stable system instructions for global chat/review mode."""
    lang_profile = get_language_profile(target_language)
    lang_display = lang_profile.get("display_name", target_language)

    style_hint = {
        "coach": "自然、共情、轻引导",
        "strict": "更聚焦练习与纠错，但语气保持礼貌",
        "friendly": "像朋友聊天，保持学习推进",
    }.get(output_style, "自然、共情、轻引导")

    return "\n\n".join(
        [
            lang_profile["teacher_persona"],
            "【模式】自由复习/闲聊模式。",
            "【目标】让对话自然、有连续性，同时适度复习已学内容。",
            "【互动原则】\n"
            "- 先回应学生真实表达，再轻量引导\n"
            "- 如果学生挫败，先共情再教学\n"
            "- 不要把对话变成考试\n"
            "- 不要每轮都提问；默认用自然讲述推进\n"
            "- 遇到冒犯或负面表达，简短接住并回到内容，不要尬聊或自嘲",
            "【输出约束】\n"
            "- 1-4句\n"
            "- 优先目标语交流，必要时少量母语解释\n"
            "- 如有新洞察，可在末尾附加 JSON："
            "```json {\"insights\": {...}, \"interests\": [...]} ```",
            f"【教学风格】{style_hint}",
            f"【学习者】{profile.name}，{lang_display}水平 {profile.level}，母语 {profile.l1}",
        ]
    )


def build_global_turn_message(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    target_language: str = "en",
) -> str:
    """Build per-turn dynamic context for global mode."""
    parts: list[str] = [
        _memory_snapshot(memory_context),
        f"【上次课摘要】{profile.last_session_summary or '暂无'}",
    ]

    quiz = memory_context.quiz_record
    if quiz.has_data() and quiz.completion_rate < 0.5:
        parts.append(
            f"【提醒机会】该学习者 Quiz 完成率 {quiz.completion_rate:.0%}，"
            "若语境合适可自然提醒巩固，但不要强迫。"
        )

    if student_input:
        parts.append(f"【学生刚说】{student_input}")
        parts.append(
            "【回合任务】自然回应这句话，并尝试推进半步学习目标；"
            "只有在必要时才提问，不要机械追问。"
        )
    else:
        parts.append("【回合任务】你先轻松开场，可结合上次课内容。")

    return "\n\n".join(parts)


# ── Legacy compatibility wrapper ───────────────────────────────────────────────


def build_global_prompt(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    target_language: str = "en",
) -> str:
    """Backward-compatible single-string global prompt."""
    system_prompt = build_global_system_prompt(
        profile=profile,
        target_language=target_language,
    )
    turn_message = build_global_turn_message(
        memory_context=memory_context,
        profile=profile,
        student_input=student_input,
        target_language=target_language,
    )
    return f"{system_prompt}\n\n【回合上下文】\n{turn_message}"
