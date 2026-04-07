"""
EvaluationMetrics — 脚本评估指标聚合

将 QualityRules 的单维度检查结果聚合成综合评分。
"""

from typing import Dict, List, Any
from .quality_rules import QualityRules


class EvaluationMetrics:
    """脚本质量评估指标计算器"""

    # 各维度权重（总和应为 100）
    DIMENSION_WEIGHTS = {
        'structure': 10,           # 开场/结尾结构
        'coverage': 15,            # 句子覆盖率
        'interaction': 20,         # 互动质量（问题/总结频率）
        'deep_coverage': 15,       # 深度句讲解质量
        'natural_tone': 15,        # 自然度（启发式）
        'pacing': 10,              # 节奏感
        'accuracy': 5,             # 准确性（基础检查）
    }

    @staticmethod
    def evaluate(script: List[Dict], lesson_plan: List[Dict]) -> Dict[str, Any]:
        """
        对脚本进行完整评估。

        Args:
            script: 生成的脚本（包含 speak、play、question 等）
            lesson_plan: 课程规划（包含 depth、focus_items 等）

        Returns:
            {
                'passed': bool,  # 是否通过（80分以上）
                'score': float (0-100),
                'dimension_scores': {
                    'structure': float,
                    'coverage': float,
                    ...
                },
                'issues': [list of issue strings],
                'suggestions': [list of suggestion strings]
            }
        """
        dimension_scores = {}
        issues = []
        suggestions = []

        # 1. 结构检查
        struct_result = QualityRules.check_structure(script)
        dimension_scores['structure'] = 100 if struct_result['passed'] else 40
        if struct_result['issue']:
            issues.append(f"[结构] {struct_result['issue']}")
            suggestions.append("确保课程有明确的开场（intro）和结尾（outro）")

        # 2. 覆盖率检查
        coverage_result = QualityRules.check_coverage(script, lesson_plan)
        coverage_score = int(coverage_result['coverage_rate'] * 100)
        dimension_scores['coverage'] = coverage_score
        if not coverage_result['passed']:
            issues.append(f"[覆盖率] {coverage_result['issue']}")
            suggestions.append(f"需要覆盖所有 {len(coverage_result['missing_sentences'])} 个缺失的句子")

        # 3. 互动质量检查
        interact_result = QualityRules.check_interaction(script)
        # 如果问题数和总结数都符合预期，得分为 100
        q_ok = interact_result['question_count'] >= interact_result['expected_questions'] * 0.8
        s_ok = interact_result['summary_count'] >= interact_result['expected_summaries'] * 0.8
        interact_score = 100 if (q_ok and s_ok) else (50 if (q_ok or s_ok) else 30)
        dimension_scores['interaction'] = interact_score
        if interact_result['issue']:
            issues.append(f"[互动] {interact_result['issue']}")
            if not q_ok:
                suggestions.append(
                    f"增加问题数量：目标 {interact_result['expected_questions']} 个，"
                    f"当前 {interact_result['question_count']} 个"
                )
            if not s_ok:
                suggestions.append(
                    f"增加总结数量：目标 {interact_result['expected_summaries']} 个，"
                    f"当前 {interact_result['summary_count']} 个"
                )

        # 4. 深度句讲解检查
        deep_result = QualityRules.check_deep_coverage(script, lesson_plan)
        deep_score = 100 if deep_result['passed'] else max(50, 100 - len(deep_result['insufficient_deep']) * 20)
        dimension_scores['deep_coverage'] = deep_score
        if deep_result['issue']:
            issues.append(f"[深度讲解] {deep_result['issue']}")
            suggestions.append(
                f"深度句（共 {deep_result['deep_sentence_count']} 个）需要至少 3 个讲解项"
            )

        # 5. 自然度检查（启发式）
        tone_result = QualityRules.check_natural_tone(script)
        tone_score = 100 if tone_result['passed'] else int(100 - tone_result['structured_rate'] * 200)
        dimension_scores['natural_tone'] = max(30, tone_score)
        if tone_result['issue']:
            issues.append(f"[自然度] {tone_result['issue']}")
            suggestions.append("避免过度使用结构化语言（'首先'、'其次'等），让讲解听起来更自然")

        # 6. 节奏感（基础检查：speak 项是否过长）
        pacing_score = EvaluationMetrics._evaluate_pacing(script)
        dimension_scores['pacing'] = pacing_score
        if pacing_score < 80:
            issues.append("[节奏] 部分讲解过长，可能影响学生注意力")
            suggestions.append("将长讲解分解成 2-3 个较短的讲话段落")

        # 7. 准确性（基础检查：是否有明显错误）
        accuracy_score = EvaluationMetrics._evaluate_accuracy(script, lesson_plan)
        dimension_scores['accuracy'] = accuracy_score
        if accuracy_score < 80:
            issues.append("[准确性] 检测到可能的讲解不准确或遗漏")

        # 计算加权总分
        total_score = sum(
            dimension_scores.get(dim, 50) * (EvaluationMetrics.DIMENSION_WEIGHTS[dim] / 100)
            for dim in EvaluationMetrics.DIMENSION_WEIGHTS
        )

        passed = total_score >= 80

        return {
            'passed': passed,
            'score': round(total_score, 1),
            'dimension_scores': {k: round(v, 1) for k, v in dimension_scores.items()},
            'issues': issues,
            'suggestions': suggestions
        }

    @staticmethod
    def _evaluate_pacing(script: List[Dict]) -> float:
        """
        评估节奏感：检查 speak 项的长度和频率。

        过长的讲解（>300 字）会降低分数。
        """
        long_items = 0
        for item in script:
            if item.get('type') == 'speak':
                text = item.get('text', '')
                if len(text) > 300:
                    long_items += 1

        total_speaks = len([s for s in script if s.get('type') == 'speak'])
        if total_speaks == 0:
            return 50

        long_ratio = long_items / total_speaks
        # 如果超过 20% 的讲话项都过长，降分
        if long_ratio > 0.2:
            return max(50, 100 - int(long_ratio * 150))
        return 100

    @staticmethod
    def _evaluate_accuracy(script: List[Dict], lesson_plan: List[Dict]) -> float:
        """
        评估准确性：基础检查，通常返回 100（真正的语义检查需要 LLM）。

        这里只做基础的形式检查。
        """
        # 检查是否所有 sentence_id 都在有效范围内
        max_sid = len(lesson_plan) - 1
        for item in script:
            sid = item.get('sentence_id')
            if isinstance(sid, int) and (sid < 0 or sid > max_sid):
                return 60

        # 检查是否有空白的讲话内容
        empty_speaks = sum(1 for s in script if s.get('type') == 'speak' and not s.get('text', '').strip())
        if empty_speaks > 0:
            return 80

        return 100
