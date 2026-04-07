"""
Lesson Tools 定义

定义 LessonWriter Agent 可以使用的所有工具。
这些工具驱动讲解脚本的生成。
"""

# 这些工具定义直接来自原 ai_lesson.py
# 保留原有的结构以确保兼容性

LESSON_WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lesson_intro",
            "description": "课程开始。介绍今天的话题和学习目标。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "开场白（3-5句）"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": "播放原始音频句子",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "label": {"type": "string", "description": "播放前的提示语（不超过15词）"}
                },
                "required": ["sentence_id", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_sentence",
            "description": "讲解句子的意思、关键词和背景",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "text": {"type": "string", "description": "讲解内容（自然、会话式，无列表）"}
                },
                "required": ["sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grammar_breakdown",
            "description": "语法深度讲解",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "structure_name": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "structure_name", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cultural_context",
            "description": "提供文化、历史或社会背景",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "context_type": {
                        "type": "string",
                        "enum": ["person", "event", "place", "concept", "media_reference", "social_context", "historical", "cultural_value"]
                    },
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "context_type", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "usage_and_collocation",
            "description": "讲解词汇/短语的实际用法",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "target_word_or_phrase": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "target_word_or_phrase", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pronunciation_tip",
            "description": "发音技巧（重音、连贯音、变音等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "focus": {
                        "type": "string",
                        "enum": ["word_stress", "connected_speech", "vowel_reduction", "intonation", "silent_letters", "accent_feature"]
                    },
                    "text": {"type": "string"}
                },
                "required": ["sentence_id", "focus", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_question",
            "description": "提问互动（最多4-5句一个）",
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_id": {"type": "integer"},
                    "question_type": {
                        "type": "string",
                        "enum": ["comprehension", "vocabulary_check", "grammar_apply", "cultural_reflection", "personal_connection"]
                    },
                    "text": {"type": "string"},
                    "answer_hint": {"type": "string"}
                },
                "required": ["sentence_id", "question_type", "text", "answer_hint"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transition_remark",
            "description": "句子组之间的自然过渡",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer"},
                    "text": {"type": "string"}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stage_summary",
            "description": "每4-5句后的阶段总结",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_sentence_id": {"type": "integer"},
                    "text": {"type": "string"}
                },
                "required": ["after_sentence_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lesson_outro",
            "description": "课程结束。总结关键要点并鼓励学生。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "结尾语（3-4个关键点）"}
                },
                "required": ["text"]
            }
        }
    },
]
