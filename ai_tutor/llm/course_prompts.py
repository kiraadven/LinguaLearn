"""
Prompt builder for Course Mode (逐句讲授模式).

Dynamically adapts to:
  - target_language: loads the right teacher persona and language-specific principles
  - content_type: loads content-type pedagogy (movies vs. news vs. daily life etc.)
  - SentencePlan: uses grammar_hint, pronunciation_note, pragmatics_note,
                  l1_transfer_warning, content_type_tip (all from new curriculum.py)

SLA research foundations woven into the prompt structure:
  - Krashen (1982): Comprehensible Input / i+1 / Affective Filter
  - Swain (1985, 1995): Output Hypothesis — pushed output + noticing the gap
  - Long (1996): Interaction Hypothesis — negotiation of meaning, recasts
  - Schmidt (1990): Noticing Hypothesis — explicit attention to form
  - Murphey / Field: Shadowing method for prosody / phonological acquisition
  - Nation (2001): Spaced retrieval, vocabulary load calibration
  - Byram (1997): Intercultural Communicative Competence — culture note rationale
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from content.language_profiles import (
    get_language_profile,
    get_content_type_profile,
)

if TYPE_CHECKING:
    from content.loader import SentenceData
    from content.curriculum import Curriculum, SentencePlan
    from memory.manager import MemoryContext
    from session.learner_profile import LearnerProfile


# ── Static instructional framework (meta-instructions in Chinese to the AI) ───

_SLA_TEACHING_CORE = """【核心教学原则（基于SLA研究）】
1. i+1 原则（Krashen）：输入略高于学生当前水平，不要太难也不要太简单。根据学习者水平灵活调整词汇选择和语法解释深度。
2. 注意（Noticing）原则（Schmidt）：引导学生主动注意关键语法/词汇/语用特征，而非被动接受。可用对比、重复、停顿等方式聚焦注意力。
3. 互动（Interaction）原则（Long）：通过真实提问和语义协商推动理解，出现误解时通过澄清请求帮助学生自我修正。
4. 产出（Output）原则（Swain）：推动学生用目标语言表达，不只理解输入。鼓励造句、复述、改写。
5. Recast 纠错（Long）：把正确形式自然嵌入下一句（"哦，你是说...对吧？"），而不是直接指错。连续3次同类错误才直接纠正。
6. 节奏控制：每次发言不超过3句话；学生发言时间目标 > 60%；提问后默等3–4秒，不要急着填沉默。
7. 避免套话：不说"很好！""我们继续..."，用真实自然的反应。"""

_TOOL_INSTRUCTIONS = """【工具调用规则】
在回复末尾用 ```json {"tool_calls":[...]} ``` 格式附加工具调用，只在确实需要时调用：

- play_sentence(sentence_index, loop_count)
  → 播放句子片段。讲解新句子前必须先调用一次（让学生先听整句）。
- highlight_word(word, sentence_index)
  → 高亮词汇，解释单词含义/用法时调用。每次最多高亮2个词。
- show_note(title, content, note_type)
  → 显示知识卡片。note_type 取值: "grammar" | "culture" | "pronunciation" | "pragmatics"
  → 语法要点复杂时用 grammar；文化背景用 culture；发音/语调要点用 pronunciation；语用功能用 pragmatics
- request_shadow(text, sentence_index)
  → 请学生跟读整句（仅在 should_shadow=true 时使用，不要随意调用）。
- advance_sentence(current_index)
  → 本句讲解完毕，确认学生理解后调用，进入下一句。

不要过度使用工具；一次回复最多附加1–2个工具调用。"""

_RESPONSE_FORMAT = """【回复格式要求】
- 用目标语言与学习者互动（A1/A2 学习者可适度混入其母语做简短解释）
- 高级学习者（B2+）尽量坚持全目标语言互动，只在真正卡住时才切换母语
- 如需工具，在文字之后追加一个 ```json {"tool_calls":[...]} ``` 块
- 不要包含其他格式标记或多余分隔符
- 控制总长度：正文不超过3句话"""


# ── Public API ─────────────────────────────────────────────────────────────────

def build_course_prompt(
    sentence: "SentenceData | None",
    plan: "SentencePlan | None",
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    student_input: str,
    attention_label: str,
    should_advance: bool = False,
    force_question: bool = False,
    target_language: str = "en",
    content_type: str = "unknown",
) -> str:
    """
    Build the full system prompt for one teacher turn in course mode.

    Args:
        sentence:        Current SentenceData (None if between sentences)
        plan:            SentencePlan from CurriculumBuilder for this sentence
        memory_context:  MemoryContext from MemoryManager (quiz + graph)
        profile:         LearnerProfile (level, l1, frequent_errors …)
        student_input:   What the student just said (empty → teacher initiates)
        attention_label: Human-readable attention level label
        should_advance:  If True, instruct teacher to call advance_sentence
        force_question:  If True, instruct teacher to re-engage with a question
        target_language: ISO code of the language being learned (en/zh/ja/ko/de/fr/es/ru)
        content_type:    Type of source material (news/movie/tv_show/interview/…)
    """
    # Load language + content-type knowledge
    lang_profile = get_language_profile(target_language)
    ct_profile = get_content_type_profile(content_type)

    lang_display = lang_profile.get("display_name", target_language)
    parts: list[str] = []

    # ── 1. Teacher persona (language-specific) ─────────────────────────────────
    parts.append(lang_profile["teacher_persona"])

    # ── 2. Core SLA principles ─────────────────────────────────────────────────
    parts.append(_SLA_TEACHING_CORE)

    # ── 3. Language-specific teaching principles ───────────────────────────────
    lang_principles: list[str] = lang_profile.get("teaching_principles", [])
    if lang_principles:
        principles_text = "\n".join(
            f"{i + 1}. {p}" for i, p in enumerate(lang_principles)
        )
        parts.append(f"【{lang_display}专项教学要点】\n{principles_text}")

    # ── 4. Content-type teaching approach ─────────────────────────────────────
    ct_label = ct_profile.get("label", "")
    ct_approach = ct_profile.get("teaching_approach", "")
    ct_foci: list[str] = ct_profile.get("key_pedagogical_foci", [])
    ct_pragmatics = ct_profile.get("pragmatics_focus", "")
    ct_shadow_ok: bool = ct_profile.get("shadow_suitable", True)
    ct_culture_tips: list[str] = ct_profile.get("culture_tips", [])

    if ct_label or ct_approach:
        ct_block = f"【内容类型：{ct_label or content_type}】"
        if ct_approach:
            ct_block += f"\n教学策略：{ct_approach}"
        if ct_foci:
            ct_block += f"\n核心教学焦点：{'、'.join(ct_foci)}"
        if ct_pragmatics:
            ct_block += f"\n语用重点：{ct_pragmatics}"
        if not ct_shadow_ok:
            ct_block += "\n注意：此类型内容节奏快/非自然口语，不适合强制跟读。"
        if ct_culture_tips:
            ct_block += "\n文化提示：" + "；".join(ct_culture_tips[:2])
        parts.append(ct_block)

    # ── 5. Tool instructions ───────────────────────────────────────────────────
    parts.append(_TOOL_INSTRUCTIONS)

    # ── 6. Sentence content ────────────────────────────────────────────────────
    if sentence:
        parts.append(sentence.to_prompt_block())
    else:
        parts.append("（当前无句子内容——可能处于句间过渡或课程开始阶段）")

    # ── 7. Sentence plan (with all new SentencePlan fields) ───────────────────
    if plan:
        focus_str = "、".join(plan.focus_areas) if plan.focus_areas else "综合理解"
        plan_lines = [f"【本句教学重点】{focus_str}"]

        if plan.grammar_point:
            plan_lines.append(f"语法要点：{plan.grammar_point}")
        if plan.grammar_hint:
            plan_lines.append(f"  └ 如何讲解：{plan.grammar_hint}")
        if plan.key_vocab:
            plan_lines.append(f"重点词汇：{', '.join(plan.key_vocab)}")
        if plan.culture_note:
            plan_lines.append(f"文化背景：{plan.culture_note}")
        if plan.pronunciation_note:
            plan_lines.append(f"发音要点：{plan.pronunciation_note}")
        if plan.pragmatics_note:
            plan_lines.append(f"语用功能：{plan.pragmatics_note}")
        if plan.l1_transfer_warning:
            plan_lines.append(f"⚠ 母语干扰风险：{plan.l1_transfer_warning}")
        if plan.content_type_tip:
            plan_lines.append(f"内容类型提示：{plan.content_type_tip}")
        plan_lines.append(
            "✓ 安排跟读练习" if plan.should_shadow else "✗ 本句无需跟读"
        )
        plan_lines.append(plan.difficulty_note)

        parts.append("\n".join(plan_lines))

    # ── 8. Learner context ─────────────────────────────────────────────────────
    frequent_errors = profile.frequent_errors or ["暂无记录"]
    learner_block = (
        f"【学习者】{profile.name}，{lang_display}水平 {profile.level}，母语 {profile.l1}\n"
        f"高频错误类型：{frequent_errors}\n"
        f"注意力状态：{attention_label}"
    )
    parts.append(learner_block)

    # ── 9. Memory context ──────────────────────────────────────────────────────
    mem_block = memory_context.to_prompt_block(mode="course")
    if mem_block:
        parts.append(f"【记忆上下文】\n{mem_block}")

    # ── 10. Special phase instructions ─────────────────────────────────────────
    instructions: list[str] = []
    if not student_input:
        instructions.append(
            "请主动开始讲解这句话：先调用 play_sentence 让学生听一遍，然后简短导入讲解。"
        )
    if should_advance:
        instructions.append(
            "本句讲解已完毕（学生已理解），请调用 advance_sentence 进入下一句。"
        )
    if force_question:
        instructions.append(
            "学生注意力极低！请立即提一个简单、具体、有趣的问题来重新吸引注意力，不超过1句，"
            "不要继续讲语法。"
        )
    if instructions:
        parts.append("【当前指令】" + " ".join(instructions))

    # ── 11. Student input ──────────────────────────────────────────────────────
    if student_input:
        parts.append(f"【学生说】{student_input}")
    else:
        parts.append("【学生】（等待老师开口）")

    # ── 12. Response format ────────────────────────────────────────────────────
    parts.append(_RESPONSE_FORMAT)

    return "\n\n".join(parts)


def build_review_prompt(
    memory_context: "MemoryContext",
    profile: "LearnerProfile",
    curriculum: "Curriculum",
    target_language: str = "en",
) -> str:
    """
    Prompt for the review/closing phase of a course session.

    Uses the Curriculum's `review_note` (which CurriculumBuilder populates with
    a detailed, language-specific summary of key teaching points from the session).
    """
    lang_profile = get_language_profile(target_language)
    lang_display = lang_profile.get("display_name", target_language)

    parts: list[str] = [
        lang_profile["teacher_persona"],
        "【当前阶段】课程结束，进入总结复习阶段。",
    ]

    # Curriculum summary and review note
    curriculum_summary = curriculum.to_summary()
    review_note = getattr(curriculum, "review_note", "")
    teaching_approach = getattr(curriculum, "teaching_approach_note", "")

    curriculum_block = f"【课程摘要】\n{curriculum_summary}"
    if review_note:
        curriculum_block += f"\n\n【复习重点（教学建议）】\n{review_note}"
    if teaching_approach:
        curriculum_block += f"\n\n【本课整体教学策略回顾】\n{teaching_approach}"
    parts.append(curriculum_block)

    # Review phase pedagogy
    parts.append(
        "【复习阶段教学策略】\n"
        "1. 引导学生用目标语言尝试复述/总结视频内容（1–2句即可，不强求完美）\n"
        "2. 自然地检验本课核心词汇/语法——用问答或造句，不要像考试\n"
        "3. 给予真实的、个性化的鼓励（参考学习者进步点）\n"
        "4. 提出一个课后小任务或预告下节课内容\n"
        "5. 全部内容不超过3句话，保持轻松自然"
    )

    # Learner
    parts.append(
        f"【学习者】{profile.name}，{lang_display}水平 {profile.level}，母语 {profile.l1}"
    )

    # Memory
    mem_block = memory_context.to_prompt_block(mode="course")
    if mem_block:
        parts.append(f"【记忆上下文】\n{mem_block}")

    parts.append(_RESPONSE_FORMAT)

    return "\n\n".join(parts)
