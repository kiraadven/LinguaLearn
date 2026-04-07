"""
质量规则 — 脚本评估的具体规则

定义脚本必须满足的7个维度的规则。
"""

from typing import Dict, List, Any


class QualityRules:
    """脚本质量规则检查器"""

    # 及格线
    PASS_SCORE = 80

    @staticmethod
    def check_coverage(script: List[Dict], lesson_plan: List[Dict]) -> Dict[str, Any]:
        """
        检查覆盖率：是否处理了所有句子？

        Args:
            script: 生成的脚本
            lesson_plan: 课程规划

        Returns:
            {
                'passed': bool,
                'coverage_rate': float (0-1),
                'missing_sentences': [list of sentence_ids],
                'issue': str if not passed
            }
        """
        # 获取脚本中提到的所有句子
        mentioned_sentences = set()
        for item in script:
            if item.get('sentence_id') is not None:
                mentioned_sentences.add(item['sentence_id'])

        # 应该处理的句子
        expected_sentences = set(s.get('sentence_id', i) for i, s in enumerate(lesson_plan))

        missing = expected_sentences - mentioned_sentences
        coverage_rate = len(mentioned_sentences) / len(expected_sentences) if expected_sentences else 1.0

        # 至少要覆盖95%
        passed = coverage_rate >= 0.95 and len(missing) == 0

        return {
            'passed': passed,
            'coverage_rate': coverage_rate,
            'missing_sentences': list(missing),
            'issue': f"缺少 {len(missing)} 个句子的讲解" if missing else None
        }

    @staticmethod
    def check_interaction(script: List[Dict]) -> Dict[str, Any]:
        """
        检查互动质量：是否有足够的提问和互动？
        """
        questions = [s for s in script if s.get('type') == 'question']
        summaries = [s for s in script if s.get('subtype') == 'summary']

        # 统计句子数
        sentence_count = len(set(s.get('sentence_id') for s in script if s.get('sentence_id') is not None))

        # 规则：每4-5句应该有1个问题，每4-5句应该有1个总结
        expected_questions = max(1, sentence_count // 4)
        expected_summaries = max(1, sentence_count // 5)

        questions_ok = len(questions) >= expected_questions * 0.8
        summaries_ok = len(summaries) >= expected_summaries * 0.8

        passed = questions_ok and summaries_ok

        issues = []
        if not questions_ok:
            issues.append(f"问题太少：{len(questions)}/{expected_questions}")
        if not summaries_ok:
            issues.append(f"总结太少：{len(summaries)}/{expected_summaries}")

        return {
            'passed': passed,
            'question_count': len(questions),
            'summary_count': len(summaries),
            'expected_questions': expected_questions,
            'expected_summaries': expected_summaries,
            'issue': " | ".join(issues) if issues else None
        }

    @staticmethod
    def check_deep_coverage(script: List[Dict], lesson_plan: List[Dict]) -> Dict[str, Any]:
        """
        检查深度句讲解质量：深度句是否得到充分讲解？
        """
        # 获取所有深度句的ID
        deep_sentence_ids = set(
            s.get('sentence_id', i)
            for i, s in enumerate(lesson_plan)
            if s.get('depth') == 'deep'
        )

        # 统计每个句子的讲解项数
        explanation_counts = {}
        for item in script:
            sid = item.get('sentence_id')
            if sid is not None:
                explanation_counts[sid] = explanation_counts.get(sid, 0) + (
                    1 if item.get('type') in ['speak', 'question'] else 0
                )

        # 深度句应该至少有3个讲解项（explain + grammar/culture + replay等）
        insufficient_deep = [
            sid for sid in deep_sentence_ids
            if explanation_counts.get(sid, 0) < 3
        ]

        passed = len(insufficient_deep) == 0

        return {
            'passed': passed,
            'deep_sentence_count': len(deep_sentence_ids),
            'insufficient_deep': insufficient_deep,
            'issue': f"{len(insufficient_deep)} 个深度句讲解不足" if insufficient_deep else None
        }

    @staticmethod
    def check_structure(script: List[Dict]) -> Dict[str, Any]:
        """
        检查结构：是否有开场和结尾？
        """
        has_intro = any(s.get('subtype') == 'intro' for s in script)
        has_outro = any(s.get('subtype') == 'outro' for s in script)

        passed = has_intro and has_outro

        issues = []
        if not has_intro:
            issues.append("缺少课程开场")
        if not has_outro:
            issues.append("缺少课程结尾")

        return {
            'passed': passed,
            'has_intro': has_intro,
            'has_outro': has_outro,
            'issue': " | ".join(issues) if issues else None
        }

    @staticmethod
    def check_natural_tone(script: List[Dict]) -> Dict[str, Any]:
        """
        检查自然度：讲解是否听起来自然（启发式检查）

        这是一个启发式检查，真正的评估还需要LLM
        """
        # 检查是否过度使用结构化语言
        structured_phrases = ['首先', '其次', '第三', 'first', 'second', 'third']

        speak_items = [s for s in script if s.get('type') == 'speak']
        structured_count = 0

        for item in speak_items:
            text = item.get('text', '').lower()
            if any(phrase in text for phrase in structured_phrases):
                structured_count += 1

        # 不应该超过 20% 的讲话使用结构化短语
        rate = structured_count / len(speak_items) if speak_items else 0
        passed = rate < 0.2

        return {
            'passed': passed,
            'structured_rate': rate,
            'issue': f"过度使用结构化语言 ({rate:.1%})" if not passed else None
        }
