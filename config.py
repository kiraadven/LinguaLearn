"""
配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')

# Whisper 配置
USE_LOCAL_WHISPER = os.getenv('USE_LOCAL_WHISPER', 'true').lower() == 'true'  # 默认使用本地 Whisper

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

# 输出配置
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp'

# 输入视频配置
INPUT_VIDEO_PATH = 'input_videos/ABC_news_min.mp4'  # 在这里设置你的输入视频路径
