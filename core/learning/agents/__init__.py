"""
AI Tutor Agents — LinguaLearn

5个独立的Skill代理：
  1. ContentAnalyzer — 分析内容类型、难度、风格
  2. LessonPlanner — 逐句规划讲解策略
  3. LessonWriter — 工具调用驱动生成讲解脚本
  4. QualityValidator — 评估脚本质量
  5. ScriptRepair — 自动修复质量问题

每个Agent独立，但可以组成Skill Chain。
"""

from .base_agent import BaseAgent
from .content_analyzer import ContentAnalyzer
from .lesson_planner import LessonPlanner
from .lesson_writer import LessonWriter
from .quality_validator import QualityValidator
from .script_repair import ScriptRepair
from .skill_chain_orchestrator import SkillChainOrchestrator

__all__ = [
    'BaseAgent',
    'ContentAnalyzer',
    'LessonPlanner',
    'LessonWriter',
    'QualityValidator',
    'ScriptRepair',
    'SkillChainOrchestrator',
]
