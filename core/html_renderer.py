import os
import base64
import tempfile
from typing import Dict, List, Optional
import config

# ===== Font family stacks =====
_FONT_FAMILIES = {
    'system':  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
    'serif':   'Georgia, "Times New Roman", "Noto Serif", "Source Han Serif", serif',
    'rounded': '"Nunito", "Varela Round", "M PLUS Rounded 1c", "Hiragino Maru Gothic Pro", sans-serif',
    'mono':    '"SF Mono", "Fira Code", "JetBrains Mono", Monaco, "Courier New", monospace',
}
_MONO_FONTS = '"SF Mono", Monaco, "Fira Code", "JetBrains Mono", "Courier New", monospace'

# ===== Line height presets =====
_LINE_HEIGHTS = {'compact': 1.15, 'normal': 1.45, 'relaxed': 1.8}

# ===== Subtitle background style presets =====
_SUBTITLE_BG_STYLES = {
    'light':    {'bg': '#ffffff', 'accent': '#6366f1', 'divider': '#e5e7eb', 'tgt_opacity': 0.85},
    'cream':    {'bg': '#fffbeb', 'accent': '#f59e0b', 'divider': '#fde68a', 'tgt_opacity': 0.85},
    'dark':     {'bg': '#1e1e2e', 'accent': '#818cf8', 'divider': '#374151', 'tgt_opacity': 0.80},
    'blue':     {'bg': '#eff6ff', 'accent': '#3b82f6', 'divider': '#bfdbfe', 'tgt_opacity': 0.85},
    'gradient': {'bg': 'linear-gradient(135deg,#f0f4ff 0%,#fdf2ff 100%)', 'accent': '#8b5cf6', 'divider': '#ddd6fe', 'tgt_opacity': 0.85},
    'none':     {'bg': 'transparent', 'accent': 'transparent', 'divider': 'transparent', 'tgt_opacity': 1.0},
}

# ===== Preview example data per source language =====
_PREVIEW_EXAMPLES = {
    'en': {
        'sentence': "The acquisition of language is a remarkable phenomenon that reveals the incredible cognitive capabilities of the human mind.",
        'translations': {
            'zh': "语言习得是一种非凡的现象，揭示了人类心智令人难以置信的认知能力。",
            'ja': "言語習得は、人間の心の驚くべき認知能力を明らかにする注目すべき現象です。",
            'ko': "언어 습득은 인간 마음의 놀라운 인지 능력을 드러내는 주목할 만한 현상입니다。",
            'de': "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitiven Fähigkeiten des menschlichen Geistes offenbart.",
            'fr': "L'acquisition du langage révèle les incroyables capacités cognitives de l'esprit humain.",
            'es': "La adquisición del lenguaje revela las increíbles capacidades cognitivas de la mente humana.",
        },
        'words': [
            {"word": "acquisition", "phonetic": "/ˌækwɪˈzɪʃən/", "translation": "习得；获取", "difficulty": 4},
            {"word": "remarkable",  "phonetic": "/rɪˈmɑːrkəbl/",  "translation": "非凡的；显著的", "difficulty": 3},
            {"word": "phenomenon",  "phonetic": "/fɪˈnɒmɪnən/",   "translation": "现象；奇迹", "difficulty": 4},
            {"word": "cognitive",   "phonetic": "/ˈkɒɡnɪtɪv/",    "translation": "认知的", "difficulty": 3},
            {"word": "capability",  "phonetic": "/ˌkeɪpəˈbɪlɪti/","translation": "能力；才能", "difficulty": 3},
            {"word": "incredible",  "phonetic": "/ɪnˈkredɪbl/",   "translation": "难以置信的", "difficulty": 2},
        ],
        'expressions': [
            {"english": "in the long run",    "chinese": "从长远来看", "difficulty": 3},
            {"english": "on the other hand",  "chinese": "另一方面",   "difficulty": 2},
            {"english": "as a result of",     "chinese": "由于…的结果", "difficulty": 2},
        ],
    },
    'zh': {
        'sentence': "人类语言的习得是一种非凡的认知现象，展示了大脑令人难以置信的神经可塑性和学习能力。",
        'translations': {
            'en': "The acquisition of human language is an extraordinary cognitive phenomenon demonstrating the brain's incredible neuroplasticity.",
            'ja': "人間の言語習得は脳の神経可塑性と学習能力を示す認知現象です。",
            'ko': "인간 언어의 습득은 뇌의 신경 가소성과 학습 능력을 보여주는 인지 현상입니다.",
        },
        'words': [
            {"word": "认知",  "phonetic": "rèn zhī",    "translation": "cognition",    "difficulty": 3},
            {"word": "非凡",  "phonetic": "fēi fán",    "translation": "extraordinary","difficulty": 3},
            {"word": "可塑性","phonetic": "kě sù xìng", "translation": "plasticity",   "difficulty": 4},
            {"word": "习得",  "phonetic": "xí dé",      "translation": "acquisition",  "difficulty": 3},
            {"word": "展示",  "phonetic": "zhǎn shì",   "translation": "demonstrate",  "difficulty": 2},
            {"word": "现象",  "phonetic": "xiàn xiàng", "translation": "phenomenon",   "difficulty": 2},
        ],
        'expressions': [
            {"english": "令人难以置信", "chinese": "incredibly hard to believe", "difficulty": 3},
            {"english": "展示了…能力", "chinese": "demonstrates the ability",    "difficulty": 3},
            {"english": "一种…现象",   "chinese": "a kind of phenomenon",        "difficulty": 2},
        ],
    },
    'ja': {
        'sentence': "言語習得は人間の認知能力の驚くべき側面であり、脳の信じられないほどの適応力と可塑性を示しています。",
        'translations': {
            'en': "Language acquisition is a remarkable aspect of human cognitive ability, demonstrating the brain's plasticity.",
            'zh': "语言习得是人类认知能力的显著方面，展示了大脑的适应性和可塑性。",
        },
        'words': [
            {"word": "習得",    "phonetic": "しゅうとく",    "translation": "acquisition",  "difficulty": 3},
            {"word": "認知",    "phonetic": "にんち",        "translation": "cognition",    "difficulty": 3},
            {"word": "驚くべき","phonetic": "おどろくべき",  "translation": "remarkable",   "difficulty": 3},
            {"word": "適応力",  "phonetic": "てきおうりょく","translation": "adaptability", "difficulty": 4},
            {"word": "可塑性",  "phonetic": "かそせい",      "translation": "plasticity",   "difficulty": 5},
            {"word": "側面",    "phonetic": "そくめん",      "translation": "aspect",       "difficulty": 2},
        ],
        'expressions': [
            {"english": "〜を示している", "chinese": "demonstrates ~",  "difficulty": 3},
            {"english": "驚くべき〜",     "chinese": "remarkable ~",     "difficulty": 2},
            {"english": "〜の側面",       "chinese": "aspect of ~",      "difficulty": 2},
        ],
    },
    'ko': {
        'sentence': "언어 습득은 인간 인지 능력의 놀라운 측면으로, 뇌의 적응력과 가소성을 보여줍니다.",
        'translations': {
            'en': "Language acquisition is a remarkable aspect of human cognitive ability.",
            'zh': "语言习得是人类认知能力的显著方面。",
        },
        'words': [
            {"word": "습득",   "phonetic": "seub-deug",        "translation": "acquisition", "difficulty": 3},
            {"word": "인지",   "phonetic": "in-ji",            "translation": "cognition",   "difficulty": 3},
            {"word": "놀라운", "phonetic": "nol-la-un",        "translation": "remarkable",  "difficulty": 2},
            {"word": "적응력", "phonetic": "jeog-eung-lyeog",  "translation": "adaptability","difficulty": 4},
            {"word": "가소성", "phonetic": "ga-so-seong",      "translation": "plasticity",  "difficulty": 5},
            {"word": "측면",   "phonetic": "cheug-myeon",      "translation": "aspect",      "difficulty": 2},
        ],
        'expressions': [
            {"english": "보여줍니다",   "chinese": "demonstrates",       "difficulty": 2},
            {"english": "놀라운 측면", "chinese": "remarkable aspect",   "difficulty": 2},
            {"english": "믿기 어려운", "chinese": "hard to believe",     "difficulty": 3},
        ],
    },
    'de': {
        'sentence': "Der Spracherwerb ist ein bemerkenswertes Phänomen, das die kognitive Anpassungsfähigkeit und neuronale Plastizität des menschlichen Gehirns demonstriert.",
        'translations': {
            'en': "Language acquisition is a remarkable phenomenon demonstrating the cognitive adaptability of the human brain.",
            'zh': "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
        },
        'words': [
            {"word": "Spracherwerb",  "phonetic": "/ˈʃpraːxɛɐ̯ˌvɛrp/", "translation": "language acquisition", "difficulty": 3},
            {"word": "bemerkenswert", "phonetic": "/bəˈmɛrkənsvɛrt/",   "translation": "remarkable",           "difficulty": 3},
            {"word": "Plastizität",   "phonetic": "/plastiˈtsɪtɛːt/",   "translation": "plasticity",           "difficulty": 5},
            {"word": "demonstriert",  "phonetic": "/demoːnˈstriːrt/",   "translation": "demonstrates",         "difficulty": 3},
            {"word": "kognitiv",      "phonetic": "/kɔɡniˈtiːf/",       "translation": "cognitive",            "difficulty": 4},
            {"word": "unglaublich",   "phonetic": "/ʊnˈɡlaʊ̯plɪç/",     "translation": "incredible",           "difficulty": 2},
        ],
        'expressions': [
            {"english": "das...demonstriert", "chinese": "which demonstrates", "difficulty": 3},
            {"english": "ein...Phänomen",     "chinese": "a phenomenon",        "difficulty": 2},
            {"english": "des menschlichen",   "chinese": "of the human",        "difficulty": 2},
        ],
    },
    'fr': {
        'sentence': "L'acquisition du langage est un phénomène remarquable qui démontre l'adaptabilité cognitive et la plasticité neuronale du cerveau humain.",
        'translations': {
            'en': "Language acquisition demonstrates the incredible cognitive adaptability and neural plasticity of the human brain.",
            'zh': "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
        },
        'words': [
            {"word": "acquisition",   "phonetic": "/akizisjɔ̃/",  "translation": "acquisition",  "difficulty": 3},
            {"word": "remarquable",   "phonetic": "/ʁəmaʁkabl/",  "translation": "remarkable",   "difficulty": 3},
            {"word": "plasticité",    "phonetic": "/plastisite/",  "translation": "plasticity",   "difficulty": 5},
            {"word": "adaptabilité",  "phonetic": "/adaptabilite/","translation": "adaptability", "difficulty": 4},
            {"word": "démontre",      "phonetic": "/demɔ̃tʁ/",     "translation": "demonstrates", "difficulty": 3},
            {"word": "incroyable",    "phonetic": "/ɛ̃kʁwajabl/",  "translation": "incredible",   "difficulty": 2},
        ],
        'expressions': [
            {"english": "qui démontre",            "chinese": "which demonstrates",   "difficulty": 2},
            {"english": "un phénomène remarquable","chinese": "a remarkable phenomenon","difficulty": 3},
            {"english": "du cerveau humain",       "chinese": "of the human brain",   "difficulty": 2},
        ],
    },
    'es': {
        'sentence': "La adquisición del lenguaje es un fenómeno notable que demuestra la adaptabilidad cognitiva y la plasticidad neuronal del cerebro humano.",
        'translations': {
            'en': "Language acquisition demonstrates the incredible cognitive adaptability and neural plasticity of the human brain.",
            'zh': "语言习得展示了人类大脑令人难以置信的认知适应性和神经可塑性。",
        },
        'words': [
            {"word": "adquisición",  "phonetic": "/adkiˈsjon/",      "translation": "acquisition",  "difficulty": 3},
            {"word": "notable",      "phonetic": "/noˈtaβle/",        "translation": "remarkable",   "difficulty": 3},
            {"word": "plasticidad",  "phonetic": "/plastiθiˈðað/",    "translation": "plasticity",   "difficulty": 5},
            {"word": "adaptabilidad","phonetic": "/adaptaβiliˈðað/",  "translation": "adaptability", "difficulty": 4},
            {"word": "demuestra",    "phonetic": "/deˈmwestra/",      "translation": "demonstrates", "difficulty": 3},
            {"word": "increíble",    "phonetic": "/iŋkɾeˈiβle/",     "translation": "incredible",   "difficulty": 2},
        ],
        'expressions': [
            {"english": "que demuestra",       "chinese": "which demonstrates",    "difficulty": 2},
            {"english": "un fenómeno notable", "chinese": "a remarkable phenomenon","difficulty": 3},
            {"english": "del cerebro humano",  "chinese": "of the human brain",    "difficulty": 2},
        ],
    },
    'ru': {
        'sentence': "Освоение языка — это замечательный феномен, который демонстрирует когнитивную адаптивность и нейропластичность человеческого мозга.",
        'translations': {
            'en': "Language acquisition is a remarkable phenomenon that demonstrates cognitive adaptability and neural plasticity of the human brain.",
            'zh': "语言习得是一种非凡的现象，展示了人类大脑的认知适应性和神经可塑性。",
        },
        'words': [
            {"word": "освоение",      "phonetic": "/əsˈvoːɪnɪjə/", "translation": "acquisition",   "difficulty": 3},
            {"word": "замечательный", "phonetic": "/zəmɪˈtʃætəlnɪj/", "translation": "remarkable",   "difficulty": 3},
            {"word": "феномен",       "phonetic": "/fɪˈnɔːmɪn/",    "translation": "phenomenon",    "difficulty": 4},
            {"word": "демонстрирует", "phonetic": "/dɪˈmɒnstreɪts/", "translation": "demonstrates",  "difficulty": 3},
            {"word": "адаптивность",  "phonetic": "/ədˈæptɪvnəs/",  "translation": "adaptability",  "difficulty": 4},
            {"word": "нейропластичность", "phonetic": "/ˈnjʊroʊˈplæstɪsɪti/", "translation": "neural plasticity", "difficulty": 5},
        ],
        'expressions': [
            {"english": "замечательный феномен", "chinese": "remarkable phenomenon",      "difficulty": 3},
            {"english": "демонстрирует способность", "chinese": "demonstrates ability", "difficulty": 3},
            {"english": "человеческого мозга",     "chinese": "of the human brain",     "difficulty": 2},
        ],
    },
}


class HTMLRenderer:
    """使用 Playwright (Chromium) 渲染 HTML 模板为 PNG"""

    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            templates_dir = os.path.join(current_dir, 'templates')
        self.templates_dir = templates_dir
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()

    def __del__(self):
        try:
            self._browser.close()
            self._pw.stop()
        except Exception:
            pass

    def _read_template(self, template_name: str) -> str:
        path = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"模板文件不存在: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _render_html_to_png(self, html_content: str, output_path: str, width: int, height: int) -> bool:
        try:
            page = self._browser.new_page(viewport={'width': width, 'height': height})
            page.set_content(html_content, wait_until='domcontentloaded')
            page.screenshot(path=output_path, clip={'x': 0, 'y': 0, 'width': width, 'height': height}, omit_background=True)
            page.close()
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Playwright 渲染异常: {e}")
            return False

    # ------------------------------------------------------------------ helpers

    def _font_family(self, style: dict) -> str:
        key = style.get('font_family', 'system')
        return _FONT_FAMILIES.get(key, _FONT_FAMILIES['system'])

    def _line_height(self, style: dict) -> float:
        key = style.get('line_height', 'normal')
        return _LINE_HEIGHTS.get(key, 1.45)

    def _scale(self, style: dict, box_type: str = '') -> float:
        """Return font size scale for a box. Checks box-specific key first (e.g. subtitle_font_size_scale)."""
        if box_type:
            v = style.get(f'{box_type}_font_size_scale')
            if v is not None:
                return float(v)
        return float(style.get('font_size_scale', 1.0))

    # ------------------------------------------------------------------ subtitle

    def render_subtitle(self, english_text: str, chinese_text: str,
                        width: int, height: int, output_path: str,
                        style: dict = None) -> bool:
        style = style or {}
        is_1080p = getattr(config, 'VIDEO_RESOLUTION', '1080p') == "1080p"
        scale = self._scale(style, 'subtitle')
        lh = self._line_height(style)

        if is_1080p:
            base_src = height * 0.28
            base_tgt = height * 0.25
        else:
            base_src = height * 0.15
            base_tgt = height * 0.13

        en_len = len(english_text)
        char_scale = (1.0 if en_len <= 20 else 0.95 if en_len <= 30 else
                      0.85 if en_len <= 40 else 0.75 if en_len <= 50 else
                      0.65 if en_len <= 60 else 0.55 if en_len <= 80 else 0.45)

        if is_1080p:
            font_src = max(24, min(62, int(base_src * char_scale * scale)))
            font_tgt = max(20, min(54, int(base_tgt * char_scale * scale)))
        else:
            font_src = max(14, min(38, int(base_src * char_scale * scale)))
            font_tgt = max(12, min(30, int(base_tgt * char_scale * scale)))

        # Background style — support 'none' (transparent)
        bg_style_key = style.get('subtitle_bg_style', 'light')
        bg_preset = _SUBTITLE_BG_STYLES.get(bg_style_key, _SUBTITLE_BG_STYLES['light'])
        # Accept both subtitle_bg_color (frontend key) and subtitle_bg (legacy key)
        bg_color = style.get('subtitle_bg_color') or style.get('subtitle_bg') or bg_preset['bg']
        # Accept subtitle_text_color (frontend key) or subtitle_en_color (legacy key)
        en_color = style.get('subtitle_text_color') or style.get('subtitle_en_color', config.SUBTITLE_BOX_ENGLISH_COLOR)
        cn_color = style.get('subtitle_cn_color', config.SUBTITLE_BOX_CHINESE_COLOR)
        accent = bg_preset['accent']
        divider_color = bg_preset['divider']
        tgt_opacity = bg_preset['tgt_opacity']
        text_highlight_color = style.get('text_highlight_color', 'rgba(200,200,200,0.1)')

        padding = max(8, int(height * 0.06))
        padding_h = max(12, int(width * 0.03))
        divider_margin = max(4, int(font_src * 0.25))
        divider_h = max(1, int(height * 0.008))
        divider_w = 40

        template = self._read_template('subtitle_template.html')

        # 检测是否是 CJK 语言，用于自动换行（只对目标语言）
        target_lang = style.get('target_lang', 'zh')
        cjk_break = "word-break: break-all;" if target_lang in config.CJK_LANGUAGES else ""

        html = (template
            .replace('{{width}}',              str(width))
            .replace('{{height}}',             str(height))
            .replace('{{font_family}}',        self._font_family(style))
            .replace('{{bg_color}}',           bg_color)
            .replace('{{font_size_src}}',      str(font_src))
            .replace('{{font_size_tgt}}',      str(font_tgt))
            .replace('{{english_text}}',       english_text)
            .replace('{{chinese_text}}',       chinese_text)
            .replace('{{en_color}}',           en_color)
            .replace('{{cn_color}}',           cn_color)
            .replace('{{line_height_src}}',    str(round(lh, 2)))
            .replace('{{line_height_tgt}}',    str(round(lh * 0.95, 2)))
            .replace('{{letter_spacing_src}}', '0.2')
            .replace('{{letter_spacing_tgt}}', '0.1')
            .replace('{{src_weight}}',         '700')
            .replace('{{tgt_weight}}',         '400')
            .replace('{{tgt_opacity}}',        str(tgt_opacity))
            .replace('{{padding}}',            str(padding))
            .replace('{{padding_h}}',          str(padding_h))
            .replace('{{divider_w}}',          str(divider_w))
            .replace('{{divider_h}}',          str(divider_h))
            .replace('{{divider_color}}',      divider_color)
            .replace('{{divider_margin}}',     str(divider_margin))
            .replace('{{divider_opacity}}',    '0.6')
            .replace('{{accent_color}}',       accent)
            .replace('{{accent_bar_w}}',       str(max(3, int(width * 0.004))))
            .replace('{{accent_opacity}}',     '0.7')
            .replace('{{cjk_break}}',          cjk_break)
            .replace('{{text_highlight_color}}', text_highlight_color)
        )
        return self._render_html_to_png(html, output_path, width, height)

    # ------------------------------------------------------------------ wordbox

    def render_wordbox(self, words: List[Dict],
                       width: int, height: int, output_path: str,
                       style: dict = None) -> bool:
        style = style or {}
        is_1080p = getattr(config, 'VIDEO_RESOLUTION', '1080p') == "1080p"
        scale = self._scale(style, 'wordbox')
        lh = self._line_height(style)

        if is_1080p:
            base_word = height * 0.11
            base_ph   = height * 0.08
            base_tr   = height * 0.09
        else:
            base_word = height * 0.06
            base_ph   = height * 0.04
            base_tr   = height * 0.05

        hf = 0.54
        if is_1080p:
            fw = max(22, min(52, int(base_word * hf * scale)))
            fp = max(16, min(40, int(base_ph   * hf * scale)))
            ft = max(18, min(44, int(base_tr   * hf * scale)))
        else:
            fw = max(12, min(36, int(base_word * hf * scale)))
            fp = max(9,  min(26, int(base_ph   * hf * scale)))
            ft = max(10, min(30, int(base_tr   * hf * scale)))

        bg       = style.get('wordbox_bg',            config.WORD_BOX_BG_COLOR)
        wc       = style.get('wordbox_word_color',    config.WORD_BOX_WORD_COLOR)
        pc       = style.get('wordbox_phonetic_color',config.WORD_BOX_PHONETIC_COLOR)
        tc       = style.get('wordbox_trans_color',   config.WORD_BOX_TRANS_COLOR)
        accent   = style.get('wordbox_accent_color',  wc)
        text_highlight_color = style.get('text_highlight_color', 'rgba(200,200,200,0.1)')

        padding     = max(6, int(height * 0.025))
        label_size  = max(10, int(fw * 0.48))
        label_margin= max(3, int(height * 0.012))
        item_gap    = max(2, int(height * 0.012))
        item_pad_v  = max(3, int(height * 0.014))
        item_pad_h  = max(6, int(width  * 0.018))
        item_inner  = max(4, int(width  * 0.015))
        item_radius = max(4, int(height * 0.012))
        accent_w    = max(2, int(width  * 0.006))

        # Slightly lighter item background
        item_bg = _lighten_or_darken(bg, 0.05)

        words_html = ""
        for w in words[:6]:
            words_html += (
                f'<div class="word-item">'
                f'  <div class="word-left">'
                f'    <div class="word">{w.get("word","")}</div>'
                f'    <div class="phonetic">{w.get("phonetic","")}</div>'
                f'  </div>'
                f'  <div class="word-right">'
                f'    <div class="translation">{w.get("translation","")}</div>'
                f'  </div>'
                f'</div>'
            )

        label_text = style.get('wordbox_label', 'Key Words')

        template = self._read_template('wordbox_template.html')

        # 检测是否是 CJK 语言，用于自动换行
        source_lang = style.get('source_lang', 'en')
        cjk_break = "word-break: break-all;" if source_lang in config.CJK_LANGUAGES else ""

        html = (template
            .replace('{{width}}',          str(width))
            .replace('{{h}}',              str(height))
            .replace('{{font_family}}',    self._font_family(style))
            .replace('{{mono_font}}',      _MONO_FONTS)
            .replace('{{bg_color}}',       bg)
            .replace('{{item_bg}}',        item_bg)
            .replace('{{word_color}}',     wc)
            .replace('{{phonetic_color}}', pc)
            .replace('{{trans_color}}',    tc)
            .replace('{{accent_color}}',   accent)
            .replace('{{font_size_word}}', str(fw))
            .replace('{{font_size_phonetic}}', str(fp))
            .replace('{{font_size_trans}}', str(ft))
            .replace('{{label_size}}',     str(label_size))
            .replace('{{label_color}}',    wc)
            .replace('{{label_margin}}',   str(label_margin))
            .replace('{{label_text}}',     label_text)
            .replace('{{line_height_src}}',str(round(lh, 2)))
            .replace('{{line_height_tgt}}',str(round(lh * 0.92, 2)))
            .replace('{{item_gap}}',       str(item_gap))
            .replace('{{item_inner_gap}}', str(item_inner))
            .replace('{{item_pad_v}}',     str(item_pad_v))
            .replace('{{item_pad_h}}',     str(item_pad_h))
            .replace('{{item_radius}}',    str(item_radius))
            .replace('{{accent_w}}',       str(accent_w))
            .replace('{{padding}}',        str(padding))
            .replace('{{cjk_break}}',      cjk_break)
            .replace('{{text_highlight_color}}', text_highlight_color)
            .replace('{{words_html}}',     words_html)
        )
        return self._render_html_to_png(html, output_path, width, height)

    # ------------------------------------------------------------------ exprbox

    def render_expressionbox(self, expressions: List[Dict],
                              width: int, height: int, output_path: str,
                              style: dict = None) -> bool:
        style = style or {}
        is_1080p = getattr(config, 'VIDEO_RESOLUTION', '1080p') == "1080p"
        scale = self._scale(style, 'exprbox')
        lh = self._line_height(style)

        if is_1080p:
            base_en = height * 0.13
            base_cn = height * 0.10
        else:
            base_en = height * 0.07
            base_cn = height * 0.055

        hf = 0.82
        if is_1080p:
            fen = max(22, min(52, int(base_en * hf * scale)))
            fcn = max(18, min(44, int(base_cn * hf * scale)))
        else:
            fen = max(12, min(36, int(base_en * hf * scale)))
            fcn = max(10, min(28, int(base_cn * hf * scale)))

        bg     = style.get('exprbox_bg',       config.EXPR_BOX_BG_COLOR)
        enc    = style.get('exprbox_en_color',  config.EXPR_BOX_ENGLISH_COLOR)
        cnc    = style.get('exprbox_cn_color',  config.EXPR_BOX_CHINESE_COLOR)
        accent = style.get('exprbox_accent_color', enc)
        text_highlight_color = style.get('text_highlight_color', 'rgba(200,200,200,0.1)')

        padding      = max(6, int(height * 0.025))
        label_size   = max(10, int(fen * 0.48))
        label_margin = max(3,  int(height * 0.012))
        item_gap     = max(3,  int(height * 0.015))
        item_pad_v   = max(4,  int(height * 0.016))
        item_pad_h   = max(6,  int(width  * 0.018))
        item_radius  = max(4,  int(height * 0.012))
        accent_w     = max(2,  int(width  * 0.006))
        inner_gap    = max(2,  int(height * 0.008))
        arrow_gap    = max(4,  int(fen * 0.3))
        f_arrow      = max(12, int(fen * 0.7))
        cn_indent    = arrow_gap + f_arrow

        item_bg = _lighten_or_darken(bg, 0.05)
        label_text = style.get('exprbox_label', 'Expressions')

        expressions_html = ""
        for expr in expressions[:3]:
            expressions_html += (
                f'<div class="expr-item">'
                f'  <div class="expr-src-row">'
                f'    <span class="expr-arrow">›</span>'
                f'    <div class="expr-english">{expr.get("english","")}</div>'
                f'  </div>'
                f'  <div class="expr-chinese">{expr.get("chinese","")}</div>'
                f'</div>'
            )

        template = self._read_template('expressionbox_template.html')

        # 检测是否是 CJK 语言，用于自动换行
        source_lang = style.get('source_lang', 'en')
        cjk_break = "word-break: break-all;" if source_lang in config.CJK_LANGUAGES else ""

        html = (template
            .replace('{{width}}',          str(width))
            .replace('{{h}}',              str(height))
            .replace('{{font_family}}',    self._font_family(style))
            .replace('{{bg_color}}',       bg)
            .replace('{{item_bg}}',        item_bg)
            .replace('{{en_color}}',       enc)
            .replace('{{cn_color}}',       cnc)
            .replace('{{accent_color}}',   accent)
            .replace('{{font_size_en}}',   str(fen))
            .replace('{{font_size_cn}}',   str(fcn))
            .replace('{{font_size_arrow}}',str(f_arrow))
            .replace('{{label_size}}',     str(label_size))
            .replace('{{label_color}}',    enc)
            .replace('{{label_margin}}',   str(label_margin))
            .replace('{{label_text}}',     label_text)
            .replace('{{line_height_src}}',str(round(lh, 2)))
            .replace('{{line_height_tgt}}',str(round(lh * 0.92, 2)))
            .replace('{{item_gap}}',       str(item_gap))
            .replace('{{item_pad_v}}',     str(item_pad_v))
            .replace('{{item_pad_h}}',     str(item_pad_h))
            .replace('{{item_radius}}',    str(item_radius))
            .replace('{{accent_w}}',       str(accent_w))
            .replace('{{inner_gap}}',      str(inner_gap))
            .replace('{{arrow_gap}}',      str(arrow_gap))
            .replace('{{cn_indent}}',      str(cn_indent))
            .replace('{{padding}}',        str(padding))
            .replace('{{cjk_break}}',      cjk_break)
            .replace('{{text_highlight_color}}', text_highlight_color)
            .replace('{{expressions_html}}', expressions_html)
        )
        return self._render_html_to_png(html, output_path, width, height)

    # ------------------------------------------------------------------ preview

    def generate_preview_images(
        self,
        num_words: int,
        num_expressions: int,
        source_lang: str,
        target_lang: str,
        resolution: str,
        output_dir: str,
        style: dict = None,
        layout: dict = None,
    ) -> dict:
        """Render preview box images for the layout editor.
        Returns base64-encoded PNGs + default layout percentages."""
        style = style or {}
        example = _PREVIEW_EXAMPLES.get(source_lang, _PREVIEW_EXAMPLES['en'])
        sentence   = example['sentence']
        translation = (
            example['translations'].get(target_lang)
            or example['translations'].get('en')
            or list(example['translations'].values())[0]
        )
        words       = example['words'][:max(1, min(num_words, 6))]
        expressions = example['expressions'][:max(1, min(num_expressions, 3))]

        is_1080p = resolution == "1080p"
        frame_w  = 1920 if is_1080p else 1280
        frame_h  = 1080 if is_1080p else 720

        layout = layout or {}
        sub_w_pct = layout.get('subtitle_width_pct',  0.95)
        sub_h_pct = layout.get('subtitle_height_pct', 0.22)
        wb_w_pct  = layout.get('wordbox_width_pct',   0.245)
        wb_h_pct  = layout.get('wordbox_height_pct',  0.65)
        eb_w_pct  = layout.get('exprbox_width_pct',   0.245)
        eb_h_pct  = layout.get('exprbox_height_pct',  0.55)

        sub_w = int(frame_w * sub_w_pct)
        sub_h = int(frame_h * sub_h_pct)
        wb_w  = int(frame_w * wb_w_pct)
        wb_h  = int(frame_h * wb_h_pct)
        eb_w  = int(frame_w * eb_w_pct)
        eb_h  = int(frame_h * eb_h_pct)

        os.makedirs(output_dir, exist_ok=True)
        results = {}
        ts = int(time.time() * 1000)

        def _to_b64(path: str) -> Optional[str]:
            with open(path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode()

        sub_path = os.path.join(output_dir, f'prev_sub_{ts}.png')
        if self.render_subtitle(sentence, translation, sub_w, sub_h, sub_path, style=style):
            results['subtitle'] = _to_b64(sub_path)
            os.unlink(sub_path)

        wb_path = os.path.join(output_dir, f'prev_wb_{ts}.png')
        if self.render_wordbox(words, wb_w, wb_h, wb_path, style=style):
            results['wordbox'] = _to_b64(wb_path)
            os.unlink(wb_path)

        eb_path = os.path.join(output_dir, f'prev_eb_{ts}.png')
        if self.render_expressionbox(expressions, eb_w, eb_h, eb_path, style=style):
            results['exprbox'] = _to_b64(eb_path)
            os.unlink(eb_path)

        results['layout'] = {
            'frame_w': frame_w,
            'frame_h': frame_h,
            'subtitle': {
                'x_pct': (1 - sub_w_pct) / 2,
                'y_pct': 1 - sub_h_pct,
                'width_pct': sub_w_pct,
                'height_pct': sub_h_pct,
            },
            'wordbox': {
                'x_pct': 1 - wb_w_pct - 0.005,
                'y_pct': 0.005,
                'width_pct': wb_w_pct,
                'height_pct': wb_h_pct,
            },
            'exprbox': {
                'x_pct': 0.005,
                'y_pct': 0.005,
                'width_pct': eb_w_pct,
                'height_pct': eb_h_pct,
            },
        }
        return results


def _lighten_or_darken(hex_color: str, amount: float) -> str:
    """Slightly lighten a hex color for item backgrounds."""
    try:
        h = hex_color.lstrip('#')
        if len(h) != 6:
            return hex_color
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return hex_color
