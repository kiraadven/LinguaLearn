"""
配置文件 - LinguaLearn 多语言学习视频生成系统

此文件管理应用级配置，包括：
- LLM API 密钥和地址
- 语言和渲染相关的常量
- 视频处理参数默认值
- 目录和输出配置

大部分参数通过环境变量 (.env) 加载，或使用合理的默认值。
前端编辑器配置（主题、字体、布局）在前端状态中管理，
不在此处定义。
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== LLM API 配置 =====
# 主要 LLM 用于词汇分析和翻译
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')

# 分句专用 API（可与上面相同，也可用更快的模型）
SPLITTER_API_KEY = os.getenv('SPLITTER_API_KEY') or os.getenv('OPENAI_API_KEY')
SPLITTER_BASE_URL = os.getenv('SPLITTER_BASE_URL') or os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')
SPLITTER_MODEL = os.getenv('SPLITTER_MODEL', 'deepseek-chat')

# ===== 语音识别配置 =====
# Whisper 模型大小: tiny / base / small（推荐）/ medium / large
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'small')

# Whisper 支持的语言映射
WHISPER_LANGUAGE_MAP = {
    'en': 'en', 'zh': 'zh', 'ja': 'ja',
    'ko': 'ko', 'de': 'de', 'fr': 'fr', 'es': 'es', 'ru': 'ru',
}

# CJK 语言集合（用于文本断行和音标系统判断）
CJK_LANGUAGES = {'zh', 'ja', 'ko'}

# ===== 句子分割配置 =====
MAX_SENTENCE_WORDS = 30
MIN_SENTENCE_WORDS = 5

# ===== 视频处理配置 =====
# Part1（原速，无字幕）
PART1_REPEAT_COUNT = 1
PART1_SHOW_SUBTITLE = False
PART1_SHOW_WORD_BOX = False
PART1_SHOW_EXPRESSION_BOX = False

# Part2（慢速，有字幕）
PART2_REPEAT_COUNT = 2
PART2_SHOW_SUBTITLE = True
PART2_SHOW_WORD_BOX = True
PART2_SHOW_EXPRESSION_BOX = True

# Part3（原速，有字幕）
PART3_REPEAT_COUNT = 1
PART3_SHOW_SUBTITLE = True
PART3_SHOW_WORD_BOX = True
PART3_SHOW_EXPRESSION_BOX = True

# 慢速倍率（Part2 使用）
SPEED_SLOW = 0.75

# ===== 输出配置 =====
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp'
VIDEO_RESOLUTION = os.getenv('VIDEO_RESOLUTION', '1080p')  # 1080p 或 720p

# ===== 邮件配置 =====
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')

# ===== HTML 渲染默认颜色（Chrome Headless 降级模式）=====
# 这些值用于 HTMLRenderer，当 style dict 未提供相应键时使用
SUBTITLE_BOX_ENGLISH_COLOR = '#ffffff'
SUBTITLE_BOX_CHINESE_COLOR  = '#94a3b8'
WORD_BOX_BG_COLOR           = '#1e1e2e'
WORD_BOX_WORD_COLOR         = '#ffffff'
WORD_BOX_PHONETIC_COLOR     = '#888888'
WORD_BOX_TRANS_COLOR        = '#cccccc'
EXPR_BOX_BG_COLOR           = '#1e1e2e'
EXPR_BOX_ENGLISH_COLOR      = '#f43f5e'
EXPR_BOX_CHINESE_COLOR      = '#94a3b8'
