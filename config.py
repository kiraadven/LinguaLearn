"""
配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')

# Whisper 配置
USE_LOCAL_WHISPER = os.getenv('USE_LOCAL_WHISPER', 'true').lower() == 'true'  # 默认使用本地 Whisper
WHISPER_MODEL_SIZE = 'medium'  # 可选: tiny, base, small, medium, large

# 视频帧率
FPS = 30
SPEED_SLOW = 0.75

# ===== 颜色配置 =====
# 单词框颜色
WORD_BOX_BG_COLOR = "#fef9c3"   # 奶油黄
WORD_BOX_WORD_COLOR = "#0284c7"  # 湖蓝
WORD_BOX_PHONETIC_COLOR = "#6b7280"
WORD_BOX_TRANS_COLOR = "#111827"

# 表达框颜色
EXPR_BOX_BG_COLOR = "#e0f2fe"  # 淡蓝
EXPR_BOX_ENGLISH_COLOR = "#0369a1"
EXPR_BOX_CHINESE_COLOR = "#111827"

# 字幕框颜色
SUBTITLE_BOX_BG_COLOR = "#ffffff"
SUBTITLE_BOX_ENGLISH_COLOR = "#111827"
SUBTITLE_BOX_CHINESE_COLOR = "#374151"


# ===== 水印配置 =====
WATERMARK_ENABLED = True  # 是否启用水印
WATERMARK_GRAY = 128  # 灰色值 (0-255)
WATERMARK_OPACITY = 0.38  # 透明度 (0-1)
WATERMARK_ANGLE = -30  # 旋转角度


# ===== 视频处理模式配置 =====
# 模式选择: "full" (完整模式) 或 "quick" (迅速模式)
# - 完整模式: 3个part (原速+慢速+正常) + markdown文件
# - 迅速模式: 只保留原速视频 + 带翻译的字幕框，无markdown文件
PROCESSING_MODE = "full"  # 可选: "full", "quick"

# ===== 句子分割配置 =====
MAX_SENTENCE_LENGTH = 130  # 句子最大字符数，超过则智能分割
MIN_SENTENCE_LENGTH = 20   # 句子最小字符数

# ===== 视频处理各部分配置 =====
# Part 1: 原速播放部分（从句子开始到下一句开始，无字幕无单词框）
PART1_REPEAT_COUNT = 1  # 播放几遍
PART1_SHOW_SUBTITLE = False  # 是否显示字幕框
PART1_SHOW_WORD_BOX = False  # 是否显示单词框
PART1_SHOW_EXPRESSION_BOX = False  # 是否显示表达框

# Part 2: 慢速播放部分（0.75倍速，有字幕有单词框）
PART2_REPEAT_COUNT = 2  # 播放几遍（默认2遍）
PART2_SHOW_SUBTITLE = True  # 是否显示字幕框
PART2_SHOW_WORD_BOX = True  # 是否显示单词框
PART2_SHOW_EXPRESSION_BOX = True  # 是否显示表达框

# Part 3: 正常速度有字幕部分（1.0倍速）
PART3_REPEAT_COUNT = 1  # 播放几遍
PART3_SHOW_SUBTITLE = True  # 是否显示字幕框
PART3_SHOW_WORD_BOX = True  # 是否显示单词框
PART3_SHOW_EXPRESSION_BOX = True  # 是否显示表达框

# 输出配置
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp'

# 输入视频配置
INPUT_VIDEO_PATH = 'input_videos/Inside President Trump’s recorded message on Iran strikes.mp4'  # 在这里设置你的输入视频路径
