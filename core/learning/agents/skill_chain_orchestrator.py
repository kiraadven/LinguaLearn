"""
SkillChainOrchestrator — 完整的Skill Chain流程编排

协调5个独立Agent：
  Skill 1: ContentAnalyzer    - 分析内容类型、难度、风格
  Skill 2: LessonPlanner      - 逐句规划讲解策略
  Skill 3: LessonWriter       - 工具调用驱动生成脚本（核心）
  Skill 4: QualityValidator   - 评估脚本质量
  Skill 5: ScriptRepair       - 自动修复问题（条件执行）

工作流程：
  Content → Plan → Write → Validate → (Repair if needed) → Success
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .content_analyzer import ContentAnalyzer
from .lesson_planner import LessonPlanner
from .lesson_writer import LessonWriter
from .quality_validator import QualityValidator
from .script_repair import ScriptRepair

logger = logging.getLogger(__name__)


class SkillChainOrchestrator:
    """
    协调所有5个Skill的编排器。

    完成端到端的讲课脚本生成流程，包括质量验证和自动修复。
    """

    # 配置参数
    DEFAULT_CONFIG = {
        "max_repair_attempts": 2,
        "quality_pass_threshold": 80,
    }

    def __init__(
        self,
        model: Optional[str] = None,
        config: Optional[Dict] = None,
    ):
        """
        初始化编排器及所有Skill。

        Args:
            model: LLM 模型名称
            config: 自定义配置（覆盖DEFAULT_CONFIG）
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        # 初始化5个Agent（BaseAgent 使用 config.OPENAI_API_KEY）
        self.content_analyzer = ContentAnalyzer(model=model)
        self.lesson_planner = LessonPlanner(model=model)
        self.lesson_writer = LessonWriter(model=model)
        self.quality_validator = QualityValidator(model=model)
        self.script_repair = ScriptRepair(model=model)

        logger.info("[SkillChainOrchestrator] 初始化完成，5个Skill已就绪")

    def generate_lesson(
        self,
        md_content: str,
        segments: List[Dict[str, Any]],
        audio_files: Optional[List[str]] = None,
        source_lang: str = "en",
        target_lang: str = "zh-Hans",
    ) -> Dict[str, Any]:
        """
        生成完整的课程（端到端流程）。

        Args:
            md_content: 视频内容（markdown格式）
            segments: 句子列表（包含 text, start_time, end_time 等）
            audio_files: 可用的句子音频文件列表（可选）
            source_lang: 源语言（要学的语言）
            target_lang: 目标语言（学习者母语）

        Returns:
            {
                'success': bool,
                'content_profile': dict,
                'lesson_plan': list,
                'lesson_script': list,
                'validation_result': dict,
                'metadata': {
                    'total_attempts': int,
                    'repair_attempts': int,
                    'final_score': float,
                    'execution_time': float,
                }
            }
        """
        import time
        start_time = time.time()

        logger.info(
            f"[SkillChainOrchestrator] 开始生成课程: {len(segments)} 句, "
            f"{source_lang}→{target_lang}"
        )

        audio_files = audio_files or []
        repair_attempts = 0

        try:
            # ─────────────────────────────────────────────────────────────────
            # Skill 1: ContentAnalyzer
            # ─────────────────────────────────────────────────────────────────
            logger.info("[SkillChainOrchestrator] [1/5] ContentAnalyzer: 分析内容...")
            content_profile = self.content_analyzer.analyze(md_content, segments)
            logger.info(
                f"  → 内容类型: {content_profile.get('content_type')}, "
                f"难度: {content_profile.get('estimated_cefr')}"
            )

            # ─────────────────────────────────────────────────────────────────
            # Skill 2: LessonPlanner
            # ─────────────────────────────────────────────────────────────────
            logger.info("[SkillChainOrchestrator] [2/5] LessonPlanner: 规划课程...")
            lesson_plan = self.lesson_planner.plan(content_profile, segments)
            deep_count = sum(1 for s in lesson_plan if s.get("depth") == "deep")
            logger.info(f"  → 规划完成: {deep_count} 深度句, {len(lesson_plan)} 总句数")

            # ─────────────────────────────────────────────────────────────────
            # Skill 3: LessonWriter
            # ─────────────────────────────────────────────────────────────────
            logger.info("[SkillChainOrchestrator] [3/5] LessonWriter: 生成脚本...")
            lesson_script = self.lesson_writer.write(
                content_profile=content_profile,
                lesson_plan=lesson_plan,
                audio_files=audio_files,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            logger.info(f"  → 脚本生成: {len(lesson_script)} 条指令")

            # ─────────────────────────────────────────────────────────────────
            # Skill 4: QualityValidator
            # ─────────────────────────────────────────────────────────────────
            logger.info("[SkillChainOrchestrator] [4/5] QualityValidator: 评估质量...")
            validation_result = self.quality_validator.validate(
                lesson_script, lesson_plan
            )
            logger.info(
                f"  → 初始分数: {validation_result['score']}/100, "
                f"通过: {validation_result['passed']}"
            )

            # ─────────────────────────────────────────────────────────────────
            # Skill 5: ScriptRepair (条件执行)
            # ─────────────────────────────────────────────────────────────────
            if not validation_result["passed"]:
                logger.info(
                    f"[SkillChainOrchestrator] [5/5] ScriptRepair: 修复脚本 "
                    f"(最多 {self.config['max_repair_attempts']} 次)..."
                )

                for attempt in range(1, self.config["max_repair_attempts"] + 1):
                    logger.info(
                        f"  → 修复尝试 {attempt}/{self.config['max_repair_attempts']}"
                    )

                    repaired_script = self.script_repair.repair(
                        script=lesson_script,
                        lesson_plan=lesson_plan,
                        issues=validation_result["issues"],
                        suggestions=validation_result["suggestions"],
                    )

                    # 重新评估
                    validation_result = self.quality_validator.validate(
                        repaired_script, lesson_plan
                    )
                    logger.info(
                        f"    → 修复后分数: {validation_result['score']}/100, "
                        f"通过: {validation_result['passed']}"
                    )

                    repair_attempts += 1
                    lesson_script = repaired_script

                    if validation_result["passed"]:
                        logger.info(
                            f"  → 修复成功！（第 {attempt} 次尝试）"
                        )
                        break
                else:
                    logger.warning(
                        f"  → 在 {repair_attempts} 次尝试后仍未达到质量标准"
                    )

            # ─────────────────────────────────────────────────────────────────
            # 汇总结果
            # ─────────────────────────────────────────────────────────────────
            elapsed = time.time() - start_time
            success = validation_result["passed"]

            result = {
                "success": success,
                "content_profile": content_profile,
                "lesson_plan": lesson_plan,
                "lesson_script": lesson_script,
                "validation_result": validation_result,
                "metadata": {
                    "total_attempts": 1 + repair_attempts,
                    "repair_attempts": repair_attempts,
                    "final_score": validation_result["score"],
                    "execution_time": round(elapsed, 2),
                },
            }

            status_msg = "✓ 成功" if success else "✗ 失败"
            logger.info(
                f"[SkillChainOrchestrator] 完成: {status_msg}, "
                f"最终分数 {validation_result['score']}/100, "
                f"耗时 {elapsed:.1f}s"
            )

            return result

        except Exception as e:
            logger.error(f"[SkillChainOrchestrator] 生成失败: {e}", exc_info=True)
            raise

    def generate_lesson_and_save(
        self,
        md_content: str,
        segments: List[Dict[str, Any]],
        output_dir: Path,
        audio_files: Optional[List[str]] = None,
        source_lang: str = "en",
        target_lang: str = "zh-Hans",
    ) -> Dict[str, Any]:
        """
        生成课程并保存中间结果到文件。

        Args:
            md_content: 视频内容
            segments: 句子列表
            output_dir: 输出目录
            audio_files: 音频文件列表
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            生成结果（同 generate_lesson）
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = self.generate_lesson(
            md_content=md_content,
            segments=segments,
            audio_files=audio_files,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # 保存中间结果
        (output_dir / "content_profile.json").write_text(
            json.dumps(result["content_profile"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "lesson_plan.json").write_text(
            json.dumps(result["lesson_plan"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "lesson_script.json").write_text(
            json.dumps(result["lesson_script"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "validation_result.json").write_text(
            json.dumps(result["validation_result"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(result["metadata"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"[SkillChainOrchestrator] 结果已保存到: {output_dir}")

        return result
