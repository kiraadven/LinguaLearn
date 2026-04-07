"""
Skill Chain 配置

定义5个Skill的执行顺序、超参数、依赖关系。
"""

SKILL_CHAIN_CONFIG = {
    "agents": [
        {
            "name": "ContentAnalyzer",
            "description": "分析内容类型、难度、风格",
            "temperature": 0.2,  # 低温度，保证分析准确
            "max_tokens": 1500,
            "knowledge_base_files": [
                "teaching_methodology.md",
            ],
        },
        {
            "name": "LessonPlanner",
            "description": "规划每句讲解策略（深度、重放、提问等）",
            "temperature": 0.3,  # 较低温度，保证规划一致性
            "max_tokens": 4096,
            "knowledge_base_files": [
                "pedagogical_frameworks/lesson_pacing.md",
                "teacher_principles.md",
            ],
        },
        {
            "name": "LessonWriter",
            "description": "生成讲解脚本（核心Agent，融合所有教学知识库）",
            "temperature": 0.6,  # 中等温度，保证创意和一致性的平衡
            "max_tokens": 8192,
            "knowledge_base_files": [
                "teaching_methodology.md",
                "teacher_principles.md",
                "pedagogical_frameworks/clt_principles.md",
                "pedagogical_frameworks/scaffolding_guide.md",
                "pedagogical_frameworks/questioning_strategies.md",
                "pedagogical_frameworks/lesson_pacing.md",
            ],
            "tools": ["play_sentence", "explain_sentence", "grammar_breakdown", 
                     "cultural_context", "usage_and_collocation", "interaction_and_replay",
                     "lesson_intro", "lesson_outro"],
        },
        {
            "name": "QualityValidator",
            "description": "评估脚本是否达到优秀教师水平",
            "temperature": 0.1,  # 非常低温度，保证评估一致
            "max_tokens": 2000,
            "knowledge_base_files": [
                "quality_checklist.md",
                "teacher_principles.md",
            ],
        },
        {
            "name": "ScriptRepair",
            "description": "自动修复质量问题（如需要）",
            "temperature": 0.5,  # 中等温度
            "max_tokens": 4096,
            "knowledge_base_files": [
                "teaching_methodology.md",
                "quality_checklist.md",
            ],
            "conditional": True,  # 只在需要时执行
        },
    ],
    
    "execution_flow": {
        "1_analyze": "ContentAnalyzer",
        "2_plan": "LessonPlanner",
        "3_write": "LessonWriter",
        "4_validate": "QualityValidator",
        "5_repair_if_needed": "ScriptRepair (conditional)",
    },
    
    "thresholds": {
        "quality_score_pass": 80,  # 80分以上算通过
        "max_repair_attempts": 2,  # 最多修复2次
    }
}
