"""
QualityValidator — Skill 4: 质量评估

评估生成的脚本是否达到"经验丰富教师"的水平。
使用quality_checklist.md中的标准。

输出：validation_result dict
"""

import json
import logging
from typing import Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY EVALUATION SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

QUALITY_VALIDATOR_SYSTEM = """\
You are an experienced language teaching expert evaluating lesson scripts for quality.
Your role is to ensure scripts reflect the work of an experienced, knowledgeable teacher—not a machine.

## Evaluation Criteria (from quality_checklist.md)

Evaluate these 7 dimensions on 0-100 scale:

### 1. Overall Structure (intro/outline/outro)
- Does it have a clear lesson_intro that sets context?
- Is there logical progression from simple to complex?
- Does it have a strong lesson_outro with key takeaways?
- Is there a narrative flow, not just list processing?

### 2. Explanation Quality (Meaning/Form/Use/Contrast/Connection)
- Does each explanation show MEANING (what it means and why)?
- Does it explain FORM (how it's structured)?
- Does it show USAGE (when and how to use in real life)?
- Does it provide CONTRAST (comparison with similar expressions)?
- Does it CONNECT to student knowledge and experience?

### 3. Interaction & Engagement (questions/feedback/application)
- Are there enough questions (proportional to content)?
- Are questions meaningful (not just filler)?
- Are there application opportunities (let students try)?
- Does it invite student participation throughout?

### 4. Natural Tone & Authenticity
- Does it sound like a real person, not a template?
- Are there natural pauses and thinking moments shown?
- Does it show genuine enthusiasm without being artificial?
- Is there variety in sentence structure and pacing?
- Avoid: "首先...其次...最后..." (overly structured)

### 5. Accuracy & Completeness
- Are language explanations factually correct?
- Are examples valid and from real usage?
- Is cultural information accurate and respectful?
- Does it cover all key points from lesson_plan?
- Are there any "deep" sentences that were skipped?

### 6. CLT & Scaffolding Principles
- Does it focus on meaning, not just form?
- Are explanations in authentic contexts?
- Does it use scaffolding (reducing support gradually)?
- Are there examples of modeling → guided practice → independence?

### 7. Pacing & Depth Distribution
- Is depth distributed appropriately (Light/Standard/Deep)?
- Are Deep sentences explained in depth?
- Are Light sentences explained briefly?
- Does energy vary to maintain engagement?

## Scoring

- **80-100**: Excellent, passes quality standards
- **60-79**: Good, needs minor improvements
- **40-59**: Fair, needs significant improvements
- **<40**: Poor, requires major revision

## Output Format

Return ONLY valid JSON:
{
  "passed": true/false,
  "score": 0-100,
  "dimension_scores": {
    "structure": 0-100,
    "explanation_quality": 0-100,
    "interaction": 0-100,
    "natural_tone": 0-100,
    "accuracy": 0-100,
    "clt_scaffolding": 0-100,
    "pacing": 0-100
  },
  "issues": ["specific issue 1", "specific issue 2", ...],
  "suggestions": ["actionable suggestion 1", "suggestion 2", ...]
}

Be fair but rigorous. The goal is to ensure students have excellent learning experiences.
"""

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY VALIDATOR CLASS
# ─────────────────────────────────────────────────────────────────────────────


class QualityValidator(BaseAgent):
    """评估脚本质量的Agent"""

    def __init__(self, **kwargs):
        super().__init__(agent_name="QualityValidator", **kwargs)

    def validate(self, script: list, lesson_plan: list) -> dict:
        """
        验证脚本质量。

        Args:
            script: LessonWriter 生成的脚本
            lesson_plan: 课程规划（包含深度信息）

        Returns:
            {
                'passed': bool,
                'score': float (0-100),
                'dimension_scores': {各维度分数},
                'issues': [问题列表],
                'suggestions': [改进建议列表]
            }
        """
        logger.info(f"[QualityValidator] 评估脚本质量 ({len(script)} 条指令)")

        # 1. 加载质量评估指南
        quality_checklist = self.load_reference_file("quality_checklist.md")
        teacher_principles = self.load_reference_file("teacher_principles.md")

        # 2. 构建评估提示词
        system_prompt = self._build_evaluation_prompt(
            quality_checklist,
            teacher_principles
        )

        # 3. 构建用户提示词
        user_prompt = self._build_evaluation_user_prompt(
            script,
            lesson_plan
        )

        # 4. 调用LLM进行评估
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        evaluation_result = self._request_json(
            messages=messages,
            temperature=0.1,  # 低温度保证评估一致性
            max_tokens=2000,
            scene="quality_validation",
            expected_type=dict,
        )

        # 5. 验证并标准化结果
        result = self._normalize_evaluation_result(evaluation_result)
        logger.info(
            f"[QualityValidator] 完成评估: passed={result['passed']}, "
            f"score={result['score']}, issues={len(result['issues'])}"
        )

        return result

    def _build_evaluation_prompt(
        self,
        quality_checklist: str,
        teacher_principles: str,
    ) -> str:
        """构建系统提示词"""
        parts = [
            QUALITY_VALIDATOR_SYSTEM,
            "\n## Quality Standards from Knowledge Base\n",
        ]

        if quality_checklist:
            parts.append("### Quality Checklist:")
            # 提取前3000字
            parts.append(quality_checklist[:3000])

        if teacher_principles:
            parts.append("\n### Teacher Principles:")
            # 提取前2000字
            parts.append(teacher_principles[:2000])

        parts.append("\n## Your Task\n")
        parts.append("""\
Evaluate the provided lesson script against the criteria above.
Be rigorous but fair. Focus on whether it represents expert teaching.

Criteria for PASSING (80+):
- Clear structure with intro/content/outro
- Explanations show meaning, form, usage, contrast, and connection
- Frequent student engagement
- Natural, authentic tone (not templated)
- Factually accurate
- Appropriate depth distribution
- Evidence of CLT and scaffolding principles
        """)

        return "\n".join(parts)

    def _build_evaluation_user_prompt(
        self,
        script: list,
        lesson_plan: list,
    ) -> str:
        """构建用户提示词"""
        parts = [
            "## Script to Evaluate\n",
            json.dumps(script, ensure_ascii=False, indent=2),
            "",
            "## Lesson Plan (for reference)\n",
            json.dumps(lesson_plan, ensure_ascii=False, indent=2),
            "",
            "## Evaluation Task\n",
            "1. Read the script and lesson plan carefully",
            "2. Evaluate on each of the 7 dimensions",
            "3. Identify specific issues (point to where in script)",
            "4. Provide actionable suggestions for improvement",
            "5. Calculate overall score and pass/fail",
            "",
            "Remember: A passing script (80+) should feel like a real teacher explaining, "
            "not a machine going through checklist.",
        ]

        return "\n".join(parts)

    @staticmethod
    def _normalize_evaluation_result(raw_result: dict) -> dict:
        """
        标准化评估结果，确保格式正确。
        """
        # 确保必需的字段存在
        if "score" not in raw_result:
            raw_result["score"] = sum(
                raw_result.get("dimension_scores", {}).values()
            ) / max(len(raw_result.get("dimension_scores", {})), 1)

        if "passed" not in raw_result:
            raw_result["passed"] = raw_result.get("score", 0) >= 80

        # 确保列表字段存在
        if "issues" not in raw_result:
            raw_result["issues"] = []
        if "suggestions" not in raw_result:
            raw_result["suggestions"] = []

        # 标准化分数范围
        raw_result["score"] = max(0, min(100, raw_result["score"]))
        for key in raw_result.get("dimension_scores", {}):
            raw_result["dimension_scores"][key] = max(
                0, min(100, raw_result["dimension_scores"][key])
            )

        return raw_result
