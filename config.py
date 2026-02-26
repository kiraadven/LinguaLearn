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
WHISPER_MODEL_SIZE = 'small'  # 可选: tiny, base, small, medium, large

# 视频配置
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

# 字幕框配置
SUBTITLE_HEIGHT = int(VIDEO_HEIGHT * 0.25)  # 占画面下方1/4
SUBTITLE_BG_COLOR = (20, 20, 40)  # 深蓝色背景
SUBTITLE_OPACITY = 0.9

# 单词框配置
WORD_BOX_WIDTH = int(VIDEO_WIDTH * 3 / 16)  # 占画面右侧3/16
WORD_BOX_BG_COLOR = (30, 30, 50)  # 深色背景
WORD_BOX_OPACITY = 0.9

# 字体配置
FONT_PATH_EN = None  # 使用系统默认字体
FONT_PATH_CN = None  # 使用系统默认字体
FONT_SIZE_LARGE = 48
FONT_SIZE_MEDIUM = 36
FONT_SIZE_SMALL = 28

# 颜色配置
COLOR_PRIMARY = (255, 215, 0)  # 金色
COLOR_SECONDARY = (100, 200, 255)  # 浅蓝色
COLOR_TEXT = (255, 255, 255)  # 白色
COLOR_ACCENT = (255, 100, 150)  # 粉红色

# 播放速度配置
SPEED_NORMAL = 1.0
SPEED_SLOW = 0.75
SLOW_REPEAT_TIMES = 2

# 新视频合成器配置 - 现代极简风格
# 启用新合成器（替代旧版）
USE_NEW_COMPOSER = True

# 字幕配置
SUBTITLE_HEIGHT_RATIO = 0.10  # 字幕条高度占视频比例（10%）
SUBTITLE_FADE_DURATION = 0.3  # 淡入淡出时长（秒）
SUBTITLE_BG_OPACITY = 0.75  # 背景透明度 (0-1)

# 单词卡配置
WORD_CARD_WIDTH_RATIO = 0.18  # 单词卡宽度比例
WORD_CARD_SHOW_KEYWORD = True  # 是否在字幕中高亮关键词
WORD_CARD_ANIMATION = True  # 是否启用动画效果
WORD_CARD_HIDE_AFTER = 3.0  # 单词卡自动隐藏时间（秒），0表示不隐藏

# 慢速重复功能配置
ENABLE_SLOW_REPEAT = True  # 是否启用慢速重复功能
SLOW_REPEAT_COUNT = 2  # 慢速重复次数
SLOW_PORTION_START = 0.0  # 慢速部分开始时间（句子开始）
SLOW_PORTION_RATIO = 0.6  # 句子中慢速播放部分的比例

# 关键词高亮配置
KEYWORD_HIGHLIGHT_COLOR = (255, 200, 100)  # 关键词高亮颜色 (金色)
KEYWORD_TEXT_COLOR = (255, 255, 255)  # 普通文本颜色
KEYWORD_BG_COLOR = (255, 180, 0, 30)  # 关键词背景色 (带透明度)

# 输出配置
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp'

# 输入视频配置
INPUT_VIDEO_PATH = 'input_videos/ABC_news_min.mp4'  # 在这里设置你的输入视频路径
