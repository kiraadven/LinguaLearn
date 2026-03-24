"""
配置文件 - 多语言学习视频生成系统
支持任意语言对之间的相互学习
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== API配置 =====
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')

SPLITTER_API_KEY = os.getenv('SPLITTER_API_KEY') or os.getenv('OPENAI_API_KEY')
SPLITTER_BASE_URL = os.getenv('SPLITTER_BASE_URL') or os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')
SPLITTER_MODEL = os.getenv('SPLITTER_MODEL', 'gpt-4-ca')

WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'small')

# ===== 多语言配置 =====
SOURCE_LANGUAGE = os.getenv('SOURCE_LANGUAGE', 'en')
TARGET_LANGUAGE = os.getenv('TARGET_LANGUAGE', 'zh')

WHISPER_LANGUAGE_MAP = {
    'en': 'en', 'zh': 'zh', 'ja': 'ja',
    'ko': 'ko', 'de': 'de', 'fr': 'fr', 'es': 'es', 'ru': 'ru',
}

LANGUAGE_NATIVE_NAMES = {
    'en': 'English', 'zh': '中文', 'ja': '日本語',
    'ko': '한국어', 'de': 'Deutsch', 'fr': 'Français', 'es': 'Español', 'ru': 'Русский',
}

LANGUAGE_FLAGS = {
    'en': '🇺🇸', 'zh': '🇨🇳', 'ja': '🇯🇵',
    'ko': '🇰🇷', 'de': '🇩🇪', 'fr': '🇫🇷', 'es': '🇪🇸', 'ru': '🇷🇺',
}

LANGUAGE_DISPLAY_NAMES = {
    'en': {'zh': '英语', 'en': 'English', 'ja': '英語', 'ko': '영어', 'de': 'Englisch', 'fr': 'Anglais', 'es': 'Inglés', 'ru': 'Английский'},
    'zh': {'zh': '中文', 'en': 'Chinese', 'ja': '中国語', 'ko': '중국어', 'de': 'Chinesisch', 'fr': 'Chinois', 'es': 'Chino', 'ru': 'Китайский'},
    'ja': {'zh': '日语', 'en': 'Japanese', 'ja': '日本語', 'ko': '일본어', 'de': 'Japanisch', 'fr': 'Japonais', 'es': 'Japonés', 'ru': 'Японский'},
    'ko': {'zh': '韩语', 'en': 'Korean', 'ja': '韓国語', 'ko': '한국어', 'de': 'Koreanisch', 'fr': 'Coréen', 'es': 'Coreano', 'ru': 'Корейский'},
    'de': {'zh': '德语', 'en': 'German', 'ja': 'ドイツ語', 'ko': '독일어', 'de': 'Deutsch', 'fr': 'Allemand', 'es': 'Alemán', 'ru': 'Немецкий'},
    'fr': {'zh': '法语', 'en': 'French', 'ja': 'フランス語', 'ko': '프랑스어', 'de': 'Französisch', 'fr': 'Français', 'es': 'Francés', 'ru': 'Французский'},
    'es': {'zh': '西班牙语', 'en': 'Spanish', 'ja': 'スペイン語', 'ko': '스페인어', 'de': 'Spanisch', 'fr': 'Espagnol', 'es': 'Español', 'ru': 'Испанский'},
    'ru': {'zh': '俄语', 'en': 'Russian', 'ja': 'ロシア語', 'ko': '러시아어', 'de': 'Russisch', 'fr': 'Russe', 'es': 'Ruso', 'ru': 'Русский'},
}

PHONETIC_SYSTEM_NAMES = {
    'en': {'zh': 'IPA国际音标（如 /ˈwɜːrd/）', 'en': 'IPA (e.g. /ˈwɜːrd/)', 'default': 'IPA'},
    'zh': {'zh': '汉语拼音（如 pīn yīn）', 'en': 'Pinyin (e.g. pīn yīn)', 'default': 'Pinyin'},
    'ja': {'zh': '假名读音（如 にほんご）', 'en': 'Kana reading (e.g. にほんご)', 'default': 'Kana'},
    'ko': {'zh': '罗马字标音（如 han-guk-eo）', 'en': 'Romanization (e.g. han-guk-eo)', 'default': 'Romanization'},
    'de': {'zh': 'IPA国际音标', 'en': 'IPA', 'default': 'IPA'},
    'fr': {'zh': 'IPA国际音标', 'en': 'IPA', 'default': 'IPA'},
    'es': {'zh': 'IPA国际音标', 'en': 'IPA', 'default': 'IPA'},
    'ru': {'zh': 'IPA国际音标', 'en': 'IPA', 'default': 'IPA'},
}

CJK_LANGUAGES = {'zh', 'ja', 'ko'}

# ===== 视频帧率 =====
FPS = 30
AUDIO_FPS = 44100
SPEED_SLOW = 0.75

# ===== 水印配置 =====
WATERMARK_ENABLED = True
WATERMARK_GRAY = 200
WATERMARK_OPACITY = 0.15
WATERMARK_ANGLE = -30

# ===== ASS 样式配置（颜色由 ass_styles.py 管理）=====
ASS_DEFAULT_STYLE = "aurora_dark"   # 默认样式模版 ID
ASS_FONT_CJK      = "Source Han Sans CN"   # CJK 字体
ASS_FONT_LATIN    = "Arial"                # Latin 回退字体

# ===== 句子分割配置 =====
MAX_SENTENCE_WORDS = 30
MIN_SENTENCE_WORDS = 5

# ===== 视频处理各部分配置 =====
PART1_REPEAT_COUNT = 1
PART1_SHOW_SUBTITLE = False
PART1_SHOW_WORD_BOX = False
PART1_SHOW_EXPRESSION_BOX = False

PART2_REPEAT_COUNT = 2
PART2_SHOW_SUBTITLE = True
PART2_SHOW_WORD_BOX = True
PART2_SHOW_EXPRESSION_BOX = True

PART3_REPEAT_COUNT = 1
PART3_SHOW_SUBTITLE = True
PART3_SHOW_WORD_BOX = True
PART3_SHOW_EXPRESSION_BOX = True

# ===== 输出配置 =====
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp'
UPLOAD_DIR = 'uploads'

# ===== 视频分辨率配置 =====
VIDEO_RESOLUTION = "1080p"

# ===== 邮件配置 =====
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
