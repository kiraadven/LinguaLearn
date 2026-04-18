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

# ===== 小工具 =====
def _env_first(*keys: str, default=None):
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return v
    return default

# ===== LLM API 配置 =====
# 主要 LLM 用于词汇分析和翻译
LLM_PROVIDER = _env_first('LLM_PROVIDER', default='deepseek')
OPENAI_API_KEY = _env_first('LLM_API_KEY', 'OPENAI_API_KEY')
OPENAI_BASE_URL = _env_first('LLM_BASE_URL', 'OPENAI_BASE_URL', default='https://api.deepseek.com/v1')

# 分句专用 API（可与上面相同，也可用更快的模型）
SPLITTER_PROVIDER = _env_first('SPLITTER_PROVIDER', default='inherit').strip().lower()
SPLITTER_API_KEY = _env_first('SPLITTER_API_KEY')
SPLITTER_BASE_URL = _env_first('SPLITTER_BASE_URL')
if SPLITTER_PROVIDER in {'inherit', 'same', 'default'} or not SPLITTER_API_KEY:
    SPLITTER_API_KEY = SPLITTER_API_KEY or OPENAI_API_KEY
if SPLITTER_PROVIDER in {'inherit', 'same', 'default'} or not SPLITTER_BASE_URL:
    SPLITTER_BASE_URL = SPLITTER_BASE_URL or OPENAI_BASE_URL
SPLITTER_MODEL = _env_first('SPLITTER_MODEL', default='deepseek-reasoner')

# ===== 语音识别配置 =====
# Whisper 模型大小: tiny / base / small（推荐）/ medium / large
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'small')

# Whisper 支持的语言映射
WHISPER_LANGUAGE_MAP = {
    'en': 'en', 'zh-Hans': 'zh', 'zh-Hant': 'zh', 'ja': 'ja',
    'ko': 'ko', 'de': 'de', 'fr': 'fr', 'es': 'es', 'ru': 'ru',
}

# CJK 语言集合（用于文本断行和音标系统判断）
CJK_LANGUAGES = {'zh-Hans', 'zh-Hant', 'ja', 'ko'}

# 语言规范化：用于把变体语言码归一到主语言码
LANGUAGE_CODE_ALIASES = {
    # 仅保留两种中文语言码，旧值 zh 会自动归一到 zh-Hans
    'zh': 'zh-Hans',
    'zh-Hans': 'zh-Hans',
    'zh-Hant': 'zh-Hant',
}

# 中文脚本偏好：用于控制转录输出简体/繁体
ZH_SCRIPT_PREFERENCE = {
    'zh-Hans': 'hans',
    'zh-Hant': 'hant',
}

# 支持的语言及其本地名称（供 API 和前端语言选择器使用）
LANGUAGE_NATIVE_NAMES = {
    'en': 'English',
    'zh-Hans': '中文（简体）',
    'zh-Hant': '中文（繁體）',
    'ja': '日本語',
    'ko': '한국어',
    'de': 'Deutsch',
    'fr': 'Français',
    'es': 'Español',
    'ru': 'Русский',
}

# 语言对应的国旗 emoji
LANGUAGE_FLAGS = {
    'en': '🇺🇸',
    'zh-Hans': '🇨🇳',
    'zh-Hant': '🇭🇰',
    'ja': '🇯🇵',
    'ko': '🇰🇷',
    'de': '🇩🇪',
    'fr': '🇫🇷',
    'es': '🇪🇸',
    'ru': '🇷🇺',
}

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
OUTPUT_DIR = 'data/output'
TEMP_DIR = 'data/temp'
VIDEO_RESOLUTION = os.getenv('VIDEO_RESOLUTION', '1080p')  # 1080p 或 720p
WIKTEXTRACT_DB_PATH = _env_first('DICT_DB_PATH', 'WIKTEXTRACT_DB_PATH', default='data/wiktextract_trans.sqlite3')
DICT_REMOTE_LOOKUP_TIMEOUT_SEC = float(os.getenv('DICT_REMOTE_LOOKUP_TIMEOUT_SEC', '1.2'))
DICT_TRANSLATE_TIMEOUT_SEC = float(os.getenv('DICT_TRANSLATE_TIMEOUT_SEC', '1.5'))
DICT_PROVIDER_MODE = _env_first('DICT_MODE', 'DICT_PROVIDER_MODE', default='').strip().lower()  # oxford / wiktextract
DICT_ENABLE_REMOTE_FALLBACK = os.getenv('DICT_ENABLE_REMOTE_FALLBACK', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
DICT_ENABLE_LLM_TRANSLATION = os.getenv('DICT_ENABLE_LLM_TRANSLATION', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
DICT_ENABLE_OXFORD = os.getenv('DICT_ENABLE_OXFORD', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
DICT_ONLY_OXFORD = os.getenv('DICT_ONLY_OXFORD', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
OXFORD_BASE_URL = _env_first('DICT_OXFORD_BASE_URL', 'OXFORD_BASE_URL', default='https://od-api-sandbox.oxforddictionaries.com/api/v2')
OXFORD_APP_ID = _env_first('DICT_OXFORD_APP_ID', 'OXFORD_APP_ID')
OXFORD_APP_KEY = _env_first('DICT_OXFORD_APP_KEY', 'OXFORD_APP_KEY', default='e5716115a3d7aeea0940dc6a9ca8880e')
OXFORD_ENGLISH_DATASET = _env_first('DICT_OXFORD_DATASET', 'OXFORD_ENGLISH_DATASET', default='en-gb')
OXFORD_TIMEOUT_SEC = float(_env_first('DICT_OXFORD_TIMEOUT_SEC', 'OXFORD_TIMEOUT_SEC', default='8.0'))

# ===== 邮件配置 =====
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')

# ===== 会员支付配置 =====
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:8080')

# Stripe
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_CN_DAY = os.getenv('STRIPE_PRICE_CN_DAY', '')
STRIPE_PRICE_CN_WEEK = os.getenv('STRIPE_PRICE_CN_WEEK', '')
STRIPE_PRICE_CN_MONTH = os.getenv('STRIPE_PRICE_CN_MONTH', '')
STRIPE_PRICE_CN_YEAR = os.getenv('STRIPE_PRICE_CN_YEAR', '')
STRIPE_PRICE_INTL_DAY = os.getenv('STRIPE_PRICE_INTL_DAY', '')
STRIPE_PRICE_INTL_WEEK = os.getenv('STRIPE_PRICE_INTL_WEEK', '')
STRIPE_PRICE_INTL_MONTH = os.getenv('STRIPE_PRICE_INTL_MONTH', '')
STRIPE_PRICE_INTL_YEAR = os.getenv('STRIPE_PRICE_INTL_YEAR', '')

# 支付宝（签约代扣）
ALIPAY_APP_ID = os.getenv('ALIPAY_APP_ID', '')
ALIPAY_PRIVATE_KEY = os.getenv('ALIPAY_PRIVATE_KEY', '')
ALIPAY_PUBLIC_KEY = os.getenv('ALIPAY_PUBLIC_KEY', '')
ALIPAY_GATEWAY = os.getenv('ALIPAY_GATEWAY', 'https://openapi.alipay.com/gateway.do')
ALIPAY_RETURN_URL = os.getenv('ALIPAY_RETURN_URL', '')
ALIPAY_NOTIFY_URL = os.getenv('ALIPAY_NOTIFY_URL', '')

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
