"""
Prompt builders for Course Mode (逐句讲授模式).

Refactored to a two-layer structure inspired by modern agent runtimes:
1) System prompt: stable teacher contract + tool contract + tone style.
2) Turn message: dynamic lesson context for this specific interaction.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_tutor.content.language_profiles import (
    get_content_type_profile,
    get_language_profile,
)

if TYPE_CHECKING:
    from ai_tutor.content.loader import SentenceData
    from ai_tutor.content.curriculum import Curriculum, SentencePlan
    from ai_tutor.memory.manager import MemoryContext
    from ai_tutor.session.learner_profile import LearnerProfile


_TOOL_CONTRACT = """【工具契约】
工具调用优先使用系统提供的原生 tool_calls。
如果你当前环境只能输出文本，再在回复末尾追加一个 JSON 代码块，格式必须是：
```json
{"tool_calls":[{"name":"tool_name","arguments":{...}}]}
```

可用工具：
- play_sentence(sentence_index, loop_count): 播放句子（用于学生要求重听，或老师判断有必要再听）
- highlight_word(word, sentence_index): 高亮词汇（每轮最多2个）
- show_note(title, content, note_type): 显示知识卡片（grammar/culture/pronunciation/pragmatics）
- request_shadow(text, sentence_index): 发起跟读（仅 should_shadow=true 时）
- advance_sentence(current_index): 确认本句完成，进入下一句

约束：
- 工具只在必要时调用，不要为了“看起来专业”而乱用
- 一轮最多 1-2 个工具调用
- 如果不需要工具，不要输出任何 JSON 块"""


_STYLE_LIBRARY = {
    "coach": "默认风格：温暖、自然、有互动感；先回应学生真实表达，再进入教学点。",
    "strict": "严格风格：更聚焦错误纠正与结构操练，语气仍需礼貌。",
    "friendly": "轻松风格：对话更口语化，优先降低学习焦虑。",
}


def _style_note(output_style: str) -> str:
    return _STYLE_LIBRARY.get(output_style, _STYLE_LIBRARY["coach"])


def _interaction_mode_note(interaction_mode: str) -> str:
    if interaction_mode == "lecture":
        return (
            "讲授主导：以老师讲解为主，不强制学生每句回复。"
            "默认不用连续追问；只有在关键理解断点才做简短确认。"
        )
    return "互动均衡：可互动，但提问要稀疏且有目的，避免“每句都问”。"


def _memory_snapshot(memory_context: "MemoryContext", mode: str = "course") -> str:
    lines: list[str] = []

    graph_summary = memory_context.learner_graph.to_prompt_summary()
    if graph_summary:
        lines.append(f"[学习者画像]\n{graph_summary}")

    if mode == "course":
        prog = memory_context.course_progress
        covered = prog.get("sentences_covered", 0)
        total = prog.get("total_sentences", 0)
        avg = prog.get("avg_mastery", 0.0)
        lines.append(f"[本课进度] 已学 {covered}/{total} 句，平均掌握度 {avg:.0%}")
        lines.append(f"[Quiz] {memory_context.quiz_record.to_prompt_summary()}")

    attn = memory_context.short_term.avg_attention
    attn_label = "高" if attn >= 0.7 else ("中" if attn >= 0.4 else "低")
    lines.append(f"[注意力] {attn_label}（{attn:.1f}）")

    return "\n\n".join(lines)


def _content_type_brief(target_language: str, content_type: str) -> str:
    lang_profile = get_language_profile(target_language)
    ct_profile = get_content_type_profile(content_type)

    lang_display = lang_profile.get("display_name", target_language)
    ct_label = ct_profile.get("label", content_type)
    ct_approach = ct_profile.get("teaching_approach", "")
    foci: list[str] = ct_profile.get("key_pedagogical_foci", [])

    lines = [f"目标语：{lang_display}", f"内容类型：{ct_label}"]
    if ct_approach:
        lines.append(f"教学取向：{ct_approach}")
    if foci:
        lines.append("本类内容建议重点：" + "、".join(foci[:4]))
    return "\n".join(lines)


def _plan_block(plan: "SentencePlan | None") -> str:
    if not plan:
        return "【本句教学计划】暂无明确计划，先做简短理解确认。"

    focus_str = "、".join(plan.focus_areas) if plan.focus_areas else "综合理解"
    lines = [f"【本句教学计划】重点：{focus_str}"]

    if plan.grammar_point:
        lines.append(f"语法：{plan.grammar_point}")
    if plan.grammar_hint:
        lines.append(f"语法讲法建议：{plan.grammar_hint}")
    if plan.key_vocab:
        lines.append(f"词汇：{', '.join(plan.key_vocab)}")
    if plan.pronunciation_note:
        lines.append(f"发音：{plan.pronunciation_note}")
    if plan.pragmatics_note:
        lines.append(f"语用：{plan.pragmatics_note}")
    if plan.culture_note:
        lines.append(f"文化：{plan.culture_note}")
    if plan.l1_transfer_warning:
        lines.append(f"母语干扰风险：{plan.l1_transfer_warning}")
    if plan.content_type_tip:
        lines.append(f"内容类型提示：{plan.content_type_tip}")

    lines.append("should_shadow=true" if plan.should_shadow else "should_shadow=false")
    if getattr(plan, "difficulty_note", ""):
        lines.append(f"难度备注：{plan.difficulty_note}")

    return "\n".join(lines)


def build_course_system_prompt(
    profile: "LearnerProfile",
    target_language: str = "en",
    content_type: str = "unknown",
    output_style: str = "coach",
) -> str:
    """Build stable system instructions for course turns."""
    lang_profile = get_language_profile(target_language)

    return "\n\n".join(
        [
            lang_profile["teacher_persona"],
            "【角色定位】你是一个真人感很强的外语老师。你的首要目标是让学生愿意继续开口，而不是展示术语。",
            "【互动原则】\n"
            "- 优先回应学生刚说的内容，再推进教学目标\n"
            "- 避免固定套话，尽量使用自然口语\n"
            "- 纠错以 recast 为主；除非学生反复同类错误，否则少用生硬直纠\n"
            "- 不要一次塞太多知识点，保持一个小目标推进\n"
            "- 不要每轮都说满，留出学生接话空间\n"
            "- 当学生情绪化/攻击性表达时，简短接住情绪并回到学习，不要尬聊、自嘲或讨好",
            "【课堂节奏】\n"
            "- 默认采用“讲解块 + 轻确认”节奏，不要每轮都提问\n"
            "- 提问只在关键理解节点出现，且必须短、可回答、与本句目标直接相关\n"
            "- 当学生明确要求‘你多讲我少答’时，切换讲授主导模式",
            "【输出约束】\n"
            "- 正文建议 1-4 句，优先短句\n"
            "- 不要输出 markdown 标题、编号列表或额外格式\n"
            "- 如需调用工具，只在正文后追加一个 JSON 代码块",
            _content_type_brief(target_language, content_type),
            f"【教学风格】{_style_note(output_style)}",
            f"【学习者】{profile.name}，水平 {profile.level}，母语 {profile.l1}",
            _TOOL_CONTRACT,
        ]
    )


def build_course_turn_message(
    sentence: "SentenceData | None",
    plan: "SentencePlan | None",
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    attention_label: str,
    should_advance: bool = False,
    force_question: bool = False,
    turn_kind: str = "student_followup",
    interaction_mode: str = "adaptive",
    planning_stage: str = "execute",
    execution_plan: str = "",
    allow_question: bool | None = None,
    current_sentence_index: int | None = None,
    target_language: str = "en",
    content_type: str = "unknown",
) -> str:
    """Build dynamic user turn context for course turns."""
    parts: list[str] = []

    parts.append(f"【当前注意力状态】{attention_label}")
    parts.append(_memory_snapshot(memory_context, mode="course"))

    if sentence:
        parts.append("【当前句子素材】\n" + sentence.to_prompt_block())
    else:
        parts.append("【当前句子素材】暂无（句间过渡）")
    if current_sentence_index is not None:
        parts.append(
            f"【当前句子索引】{current_sentence_index}（0-based，给工具参数用）"
        )

    parts.append(_plan_block(plan))
    if execution_plan:
        parts.append("【本轮执行计划】\n" + execution_plan)
    parts.append(f"【规划阶段】{planning_stage}")
    if allow_question is not None:
        parts.append("【提问策略】本轮可提问" if allow_question else "【提问策略】本轮不提问，专注讲解")
    parts.append(f"【语言与内容】目标语={target_language}；内容类型={content_type}")
    parts.append(f"【互动模式】{_interaction_mode_note(interaction_mode)}")
    parts.append(
        "【学习者背景】"
        f"常见错误类型={profile.frequent_errors or ['暂无记录']}"
    )

    if force_question or turn_kind == "attention_reengage":
        parts.append(
            "【回合任务】学生注意力很低。请立即提出一个简单、具体、有趣的问题，"
            "只做重新吸引，不要继续大段讲解。"
        )
    elif turn_kind == "opening_explain":
        if interaction_mode == "lecture":
            parts.append(
                "【回合任务】当前句子的音频已经由系统播放完。"
                "你现在直接做讲解开场：先给一句白话总义，再讲 1-2 个关键点。"
                "本轮不要提问，避免打断节奏。"
            )
        else:
            parts.append(
                "【回合任务】当前句子的音频已经由系统播放完。"
                "你现在做“讲解开场”：先给一句白话总义，再讲 1 个关键点；"
                "是否提问由你判断，不要机械每轮都问。"
            )
        parts.append(
            "【工具提醒】此时一般不需要再次调用 play_sentence；只有学生明确要求重听时才调用。"
        )
    elif student_input:
        if interaction_mode == "lecture":
            parts.append(
                "【回合任务】先简短回应学生，再连续讲解一个关键点。"
                "除非学生主动提问，否则不抛测验题；若本句已讲清可调用 advance_sentence。"
            )
        else:
            parts.append(
                "【回合任务】先自然回应学生这句话，再推进一个最关键教学点；"
                "若判断本句掌握充分，可调用 advance_sentence。"
            )
        parts.append(f"【学生刚说】{student_input}")
    else:
        parts.append("【回合任务】你先开口引导本句，做简短导入讲解。")

    if should_advance:
        idx_hint = current_sentence_index if current_sentence_index is not None else 0
        parts.append(
            f"【额外指令】当前应进入下一句，请调用 advance_sentence(current_index={idx_hint})。"
        )

    parts.append(
        "【提醒】请输出自然教学话语；只有在确实需要工具时，才在末尾追加 JSON 工具块。"
    )

    return "\n\n".join(parts)


def build_review_system_prompt(
    profile: "LearnerProfile",
    target_language: str = "en",
    output_style: str = "coach",
) -> str:
    """System prompt for review/closing phase."""
    lang_profile = get_language_profile(target_language)
    lang_display = lang_profile.get("display_name", target_language)

    return "\n\n".join(
        [
            lang_profile["teacher_persona"],
            "【阶段】课程总结复习。",
            "【目标】帮助学生低压力回顾 + 给出下次可执行建议。",
            "【输出约束】\n- 2-5句\n- 先肯定真实进步，再给一个具体可执行下一步\n- 语气自然，不要像考试评分",
            f"【教学风格】{_style_note(output_style)}",
            f"【学习者】{profile.name}，{lang_display}水平 {profile.level}，母语 {profile.l1}",
        ]
    )


def build_review_turn_message(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    curriculum: "Curriculum",
    student_input: str = "",
    target_language: str = "en",
) -> str:
    """Dynamic user message for review/closing phase."""
    curriculum_summary = curriculum.to_summary()
    review_note = getattr(curriculum, "review_note", "")
    teaching_approach = getattr(curriculum, "teaching_approach_note", "")

    parts = [
        "【课程摘要】\n" + curriculum_summary,
        _memory_snapshot(memory_context, mode="course"),
        f"【学习者】{profile.name}，目标语={target_language}",
    ]

    if review_note:
        parts.append("【建议复习重点】\n" + review_note)
    if teaching_approach:
        parts.append("【本课教学策略回顾】\n" + teaching_approach)

    if student_input:
        parts.append(f"【学生刚说】{student_input}")
        parts.append("【回合任务】自然回应学生输入，并把话题收束到复盘与下一步。")
    else:
        parts.append("【回合任务】你先发起课程总结，鼓励学生做一个简短复述。")

    return "\n\n".join(parts)


# ── Legacy compatibility wrappers ──────────────────────────────────────────────


def build_course_prompt(
    sentence: "SentenceData | None",
    plan: "SentencePlan | None",
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    attention_label: str,
    should_advance: bool = False,
    force_question: bool = False,
    turn_kind: str = "student_followup",
    interaction_mode: str = "adaptive",
    planning_stage: str = "execute",
    execution_plan: str = "",
    allow_question: bool | None = None,
    current_sentence_index: int | None = None,
    target_language: str = "en",
    content_type: str = "unknown",
) -> str:
    """Backward-compatible single-string prompt (legacy call sites)."""
    system_prompt = build_course_system_prompt(
        profile=profile,
        target_language=target_language,
        content_type=content_type,
    )
    turn_message = build_course_turn_message(
        sentence=sentence,
        plan=plan,
        memory_context=memory_context,
        profile=profile,
        student_input=student_input,
        attention_label=attention_label,
        should_advance=should_advance,
        force_question=force_question,
        turn_kind=turn_kind,
        interaction_mode=interaction_mode,
        planning_stage=planning_stage,
        execution_plan=execution_plan,
        allow_question=allow_question,
        current_sentence_index=current_sentence_index,
        target_language=target_language,
        content_type=content_type,
    )
    return f"{system_prompt}\n\n【回合上下文】\n{turn_message}"


def build_review_prompt(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    curriculum: "Curriculum",
    target_language: str = "en",
) -> str:
    """Backward-compatible single-string review prompt."""
    system_prompt = build_review_system_prompt(
        profile=profile,
        target_language=target_language,
    )
    turn_message = build_review_turn_message(
        memory_context=memory_context,
        profile=profile,
        curriculum=curriculum,
        student_input="",
        target_language=target_language,
    )
    return f"{system_prompt}\n\n【回合上下文】\n{turn_message}"
