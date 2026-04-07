"""
SkillChainOrchestrator — 5个Skill的协调器

将 5 个独立的 Skill 串联成一个完整的课程生成流程：
  1. ContentAnalyzer → 分析内容
  2. LessonPlanner → 规划课程
  3. LessonWriter → 生成脚本
  4. QualityValidator → 评估质量
  5. ScriptRepair (if needed) → 修复缺陷

这个协调器将替代原有 ai_lesson.py 中的 AILesson 类。
"""

import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any

from agents.content_analyzer import ContentAnalyzer
from agents.lesson_planner import LessonPlanner
from agents.lesson_writer import LessonWriter
from agents.quality_validator import QualityValidator
from agents.script_repair import ScriptRepair
from config.skill_chain_config import SKILL_CHAIN_CONFIG

logger = logging.getLogger(__name__)


class SkillChainOrchestrator:
    """协调 5 个 Skill Agent 的完整流程"""

    def __init__(
        self,
        source_lang: str = "en",
        target_lang: str = "zh-Hans",
        model: str = "gpt-4-turbo",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        初始化 Orchestrator

        Args:
            source_lang: 要学习的语言
            target_lang: 学习者的母语
            model: LLM 模型
            api_key: OpenAI API Key
            base_url: OpenAI Base URL
        """
        self.source_lang = source_lang
        self.target_lang = target_lang

        # 初始化 5 个 Skill Agents
        agent_kwargs = {"model": model, "api_key": api_key, "base_url": base_url}

        self.content_analyzer = ContentAnalyzer(**agent_kwargs)
        self.lesson_planner = LessonPlanner(**agent_kwargs)
        self.lesson_writer = LessonWriter(**agent_kwargs)
        self.quality_validator = QualityValidator(**agent_kwargs)
        self.script_repair = ScriptRepair(**agent_kwargs)

        logger.info(f"[SkillChainOrchestrator] 初始化完成，source={source_lang}, target={target_lang}")

    def generate_lesson(
        self,
        md_content: str,
        segments: list,
        audio_files: list = None,
    ) -> Dict[str, Any]:
        """
        完整的课程生成流程。

        Args:
            md_content: 视频稿件内容
            segments: 句子列表 [{"text": "...", ...}, ...]
            audio_files: 可用的音频文件列表

        Returns:
            {
                'content_profile': dict,
                'lesson_plan': list,
                'lesson_script': list,
                'validation_result': dict,
                'success': bool,
                'metadata': {步骤细节}
            }
        """
        logger.info("[SkillChainOrchestrator] 开始完整的课程生成流程")

        audio_files = audio_files or []
        metadata = {}

        # ────────────────────────────────────────────────────────────────────
        # 步骤 1: ContentAnalyzer — 分析内容
        # ────────────────────────────────────────────────────────────────────
        logger.info("[SkillChainOrchestrator] 步骤1/5: ContentAnalyzer")
        try:
            content_profile = self.content_analyzer.analyze(md_content, segments)
            metadata['content_analysis'] = {
                'success': True,
                'content_type': content_profile.get('content_type'),
                'cefr_level': content_profile.get('estimated_cefr'),
            }
            logger.info(f"✓ 内容分析完成: {content_profile.get('content_type')}")
        except Exception as e:
            logger.error(f"✗ 内容分析失败: {e}")
            return {
                'success': False,
                'error': f"ContentAnalyzer 失败: {str(e)}",
                'metadata': metadata,
            }

        # ────────────────────────────────────────────────────────────────────
        # 步骤 2: LessonPlanner — 规划课程
        # ────────────────────────────────────────────────────────────────────
        logger.info("[SkillChainOrchestrator] 步骤2/5: LessonPlanner")
        try:
            lesson_plan = self.lesson_planner.plan(content_profile, segments)
            metadata['lesson_planning'] = {
                'success': True,
                'total_sentences': len(lesson_plan),
                'deep_sentences': sum(1 for s in lesson_plan if s.get('depth') == 'deep'),
                'standard_sentences': sum(1 for s in lesson_plan if s.get('depth') == 'standard'),
                'light_sentences': sum(1 for s in lesson_plan if s.get('depth') == 'light'),
            }
            logger.info(f"✓ 课程规划完成: {len(lesson_plan)} 句")
        except Exception as e:
            logger.error(f"✗ 课程规划失败: {e}")
            return {
                'success': False,
                'error': f"LessonPlanner 失败: {str(e)}",
                'content_profile': content_profile,
                'metadata': metadata,
            }

        # ────────────────────────────────────────────────────────────────────
        # 步骤 3: LessonWriter — 生成脚本
        # ────────────────────────────────────────────────────────────────────
        logger.info("[SkillChainOrchestrator] 步骤3/5: LessonWriter")
        try:
            lesson_script = self.lesson_writer.write(
                content_profile=content_profile,
                lesson_plan=lesson_plan,
                audio_files=audio_files,
                target_lang=self.target_lang,
                source_lang=self.source_lang,
            )
            metadata['script_generation'] = {
                'success': True,
                'total_instructions': len(lesson_script),
                'instruction_types': self._count_instruction_types(lesson_script),
            }
            logger.info(f"✓ 脚本生成完成: {len(lesson_script)} 条指令")
        except Exception as e:
            logger.error(f"✗ 脚本生成失败: {e}")
            return {
                'success': False,
                'error': f"LessonWriter 失败: {str(e)}",
                'content_profile': content_profile,
                'lesson_plan': lesson_plan,
                'metadata': metadata,
            }

        # ────────────────────────────────────────────────────────────────────
        # 步骤 4: QualityValidator — 评估质量
        # ────────────────────────────────────────────────────────────────────
        logger.info("[SkillChainOrchestrator] 步骤4/5: QualityValidator")
        try:
            validation_result = self.quality_validator.validate(
                script=lesson_script,
                lesson_plan=lesson_plan,
            )
            metadata['quality_validation'] = {
                'success': True,
                'passed': validation_result['passed'],
                'score': validation_result['score'],
                'num_issues': len(validation_result.get('issues', [])),
            }
            logger.info(
                f"✓ 质量评估完成: passed={validation_result['passed']}, "
                f"score={validation_result['score']:.1f}/100"
            )
        except Exception as e:
            logger.error(f"✗ 质量评估失败: {e}")
            # 评估失败不应该阻止整个流程，改为使用默认分数
            validation_result = {
                'passed': False,
                'score': 0,
                'issues': ['Quality validation failed'],
                'suggestions': [],
            }
            metadata['quality_validation'] = {
                'success': False,
                'error': str(e),
            }

        # ────────────────────────────────────────────────────────────────────
        # 步骤 5: ScriptRepair (如需要) — 修复缺陷
        # ────────────────────────────────────────────────────────────────────
        if not validation_result['passed']:
            logger.info("[SkillChainOrchestrator] 步骤5/5: ScriptRepair (修复缺陷)")

            # 检查是否已经修复过
            repair_attempts = metadata.get('repairs', [])
            max_repairs = SKILL_CHAIN_CONFIG.get('thresholds', {}).get('max_repair_attempts', 2)

            if len(repair_attempts) < max_repairs:
                try:
                    logger.info(f"修复尝试 {len(repair_attempts) + 1}/{max_repairs}")
                    repaired_script = self.script_repair.repair(
                        script=lesson_script,
                        lesson_plan=lesson_plan,
                        issues=validation_result.get('issues', []),
                        suggestions=validation_result.get('suggestions', []),
                    )

                    # 用修复后的脚本替换原脚本
                    lesson_script = repaired_script

                    # 重新验证
                    validation_result = self.quality_validator.validate(
                        script=lesson_script,
                        lesson_plan=lesson_plan,
                    )

                    repair_record = {
                        'attempt': len(repair_attempts) + 1,
                        'issue_count': len(validation_result.get('issues', [])),
                        'new_score': validation_result['score'],
                        'passed': validation_result['passed'],
                    }
                    repair_attempts.append(repair_record)
                    metadata['repairs'] = repair_attempts

                    logger.info(
                        f"✓ 修复完成 (尝试 {repair_record['attempt']}): "
                        f"新分数={repair_record['new_score']:.1f}, "
                        f"passed={repair_record['passed']}"
                    )
                except Exception as e:
                    logger.error(f"✗ 修复失败: {e}")
                    metadata['repairs'] = repair_attempts + [{
                        'attempt': len(repair_attempts) + 1,
                        'error': str(e),
                    }]
            else:
                logger.warning(
                    f"已达到最大修复次数 ({max_repairs})，停止修复"
                )
                metadata['repairs'] = repair_attempts

        else:
            logger.info("[SkillChainOrchestrator] 脚本已通过质量检查，无需修复")
            metadata['repairs'] = []

        # ────────────────────────────────────────────────────────────────────
        # 完成
        # ────────────────────────────────────────────────────────────────────
        logger.info(
            f"[SkillChainOrchestrator] 完成！"
            f"final_score={validation_result['score']:.1f}, "
            f"passed={validation_result['passed']}"
        )

        return {
            'success': True,
            'content_profile': content_profile,
            'lesson_plan': lesson_plan,
            'lesson_script': lesson_script,
            'validation_result': validation_result,
            'metadata': metadata,
        }

    @staticmethod
    def _count_instruction_types(script: list) -> Dict[str, int]:
        """统计脚本中的指令类型"""
        counts = {}
        for item in script:
            item_type = item.get('type', 'unknown')
            subtype = item.get('subtype', '')

            key = f"{item_type}/{subtype}" if subtype else item_type
            counts[key] = counts.get(key, 0) + 1

        return counts
