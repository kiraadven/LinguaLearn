from __future__ import annotations

from pathlib import Path

from ai_tutor.session.learner_profile import LearnerProfile

PROMPT_DIR = Path("llm/prompts")


def _read_prompt_file(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8").strip()


class PromptBuilder:
    def __init__(self) -> None:
        self.persona_sarah = _read_prompt_file("persona_sarah.md")
        self.teaching_rules = _read_prompt_file("teaching_rules.md")
        self.phase_rules = _read_prompt_file("phase_rules.md")

    def build(
        self,
        phase: str,
        lesson_focus: str,
        covered_topics: list[str],
        vocab_list_with_usage_count: dict[str, dict],
        elapsed_minutes: int,
        total_minutes: int,
        learner_profile: LearnerProfile,
        last_turns: list[dict],
        energy_hint: str,
        student_text: str,
    ) -> str:
        recent = "\n".join(
            f"- student: {t['student']}\n  teacher: {t['teacher']}"
            for t in last_turns[-8:]
        ) or "- 无历史对话"

        return f"""
{self.persona_sarah}

{self.teaching_rules}

# [CURRENT LESSON]
- 阶段：{phase}
- 本节重点：{lesson_focus}
- 已覆盖内容：{covered_topics or ['暂无']}
- 本节已引入词汇：{vocab_list_with_usage_count or {}}
- 课程已进行：{elapsed_minutes} 分钟 / 共 {total_minutes} 分钟

# [STUDENT PROFILE]
{learner_profile.to_prompt_context()}

# [RECENT CONVERSATION]
{recent}

# [ENERGY ARC]
{energy_hint}

{self.phase_rules}

# [RULES]
- 每次回复必须包含一个 JSON 标记（放在回复最后，用 ```json 包裹）：
  {{"action":"...","phase":"...","vocab_used":[...],"error_noted":"..."}}
- action 必须是以下之一：recast|explain|encourage|check|practice_prompt|advance|closing
- 如果你认为应该切换阶段，在 phase 字段中写新阶段名
- 不要输出你的思考过程，只输出老师会说的话

# [CURRENT STUDENT INPUT]
{student_text}
        """.strip()
