"""
ASS 样式模版定义 — 12 套艺术设计主题
每套模版包含：
  - name / desc / preview_colors（前端画廊展示）
  - animation（默认入场动画类型）
  - subtitle / wordbox / exprbox 的 ASS 颜色参数
  - css（前端画布 CSS 近似预览 + 文字高亮背景 + 艺术特效）
  - text_highlight_color（文字背景高亮色，RGBA）
  - text_glow / text_outline（艺术特效）

ASS 颜色格式：&HAABBGGRR（AA=alpha 0x00=不透明 0xFF=全透明）
"""

def _c(hex_color: str, alpha: int = 0) -> str:
    """将 #RRGGBB 转换为 ASS &HAABBGGRR 格式"""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


STYLE_TEMPLATES = {

    # ─────────────────────────────────────────────────────────────
    "neon_cyberpunk": {
        "name": "赛博霓虹",
        "desc": "黑底荧光青粉，数字朋克科技感，高对比度霓虹发光",
        "preview_colors": {"bg": "#000000", "src": "#00ffff", "tgt": "#ff0080", "box_bg": "#0a0a15"},
        "animation": "pop",
        "subtitle": {
            "PrimaryColour": _c("#00FFFF"), "SecondaryColour": _c("#FF0080"),
            "OutlineColour": _c("#0A0A15", 0x80), "BackColour": _c("#000000", 0xD0),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#0A0A15", 0x80), "word_colour": _c("#00FFFF"),
            "phonetic_colour": _c("#FF00FF"), "trans_colour": _c("#FFFFFF"),
            "accent_colour": _c("#00FFFF"), "header_colour": _c("#FF0080"),
        },
        "exprbox": {
            "bg_colour": _c("#0A0A15", 0x80), "en_colour": _c("#FF0080"),
            "cn_colour": _c("#FFFFFF"), "accent_colour": _c("#FF0080"),
            "header_colour": _c("#00FFFF"),
        },
        "css": {
            "subtitle_bg": "rgba(10,10,21,0.92)", "subtitle_src_color": "#00ffff",
            "subtitle_tgt_color": "#ff0080", "box_bg": "rgba(10,10,21,0.95)",
            "word_color": "#00ffff", "phonetic_color": "#ff00ff", "trans_color": "#ffffff",
            "expr_color": "#ff0080", "font_family": "'Roboto', sans-serif",
            "border_radius": "4px", "text_shadow": "0 0 12px rgba(0,255,255,0.8), 0 0 20px rgba(255,0,128,0.5)",
            "text_highlight_color": "rgba(0,255,255,0.15)", "text_glow": "drop-shadow(0 0 8px #00ffff)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "forest_ink": {
        "name": "森林水墨",
        "desc": "深绿毛笔感，米白文字，东方水墨意蕴",
        "preview_colors": {"bg": "#1b3d2a", "src": "#e8f5e9", "tgt": "#81c784", "box_bg": "#0d261a"},
        "animation": "slide_up",
        "subtitle": {
            "PrimaryColour": _c("#E8F5E9"), "SecondaryColour": _c("#81C784"),
            "OutlineColour": _c("#1B3D2A", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#1B3D2A", 0x80), "word_colour": _c("#FFFFFF"),
            "phonetic_colour": _c("#A5D6A7"), "trans_colour": _c("#E8F5E9"),
            "accent_colour": _c("#81C784"), "header_colour": _c("#A5D6A7"),
        },
        "exprbox": {
            "bg_colour": _c("#0D261A", 0x80), "en_colour": _c("#FFEB3B"),
            "cn_colour": _c("#E8F5E9"), "accent_colour": _c("#FFEB3B"),
            "header_colour": _c("#81C784"),
        },
        "css": {
            "subtitle_bg": "rgba(27,61,42,0.88)", "subtitle_src_color": "#e8f5e9",
            "subtitle_tgt_color": "#81c784", "box_bg": "rgba(13,38,26,0.92)",
            "word_color": "#ffffff", "phonetic_color": "#a5d6a7", "trans_color": "#e8f5e9",
            "expr_color": "#ffeb3b", "font_family": "'Source Han Serif CN', serif",
            "border_radius": "6px", "text_shadow": "0 1px 3px rgba(0,0,0,0.7), 0 0 4px rgba(129,199,132,0.2)",
            "text_highlight_color": "rgba(129,199,132,0.2)", "text_outline": "0.5px rgba(129,199,132,0.4)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "sunset_gradient": {
        "name": "日落渐变",
        "desc": "橙红渐变背景，温暖高饱和，傍晚学习氛围",
        "preview_colors": {"bg": "#5a2d1f", "src": "#ffb74d", "tgt": "#ff8a65", "box_bg": "#6d3d2f"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#FFB74D"), "SecondaryColour": _c("#FF8A65"),
            "OutlineColour": _c("#5A2D1F", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#6D3D2F", 0x80), "word_colour": _c("#FFB74D"),
            "phonetic_colour": _c("#FF8A65"), "trans_colour": _c("#FFEBCD"),
            "accent_colour": _c("#FFB74D"), "header_colour": _c("#FF8A65"),
        },
        "exprbox": {
            "bg_colour": _c("#5A2D1F", 0x80), "en_colour": _c("#FF6F00"),
            "cn_colour": _c("#FFEBCD"), "accent_colour": _c("#FF6F00"),
            "header_colour": _c("#FFB74D"),
        },
        "css": {
            "subtitle_bg": "rgba(90,45,31,0.88)", "subtitle_src_color": "#ffb74d",
            "subtitle_tgt_color": "#ff8a65", "box_bg": "rgba(109,61,47,0.92)",
            "word_color": "#ffb74d", "phonetic_color": "#ff8a65", "trans_color": "#ffebcd",
            "expr_color": "#ff6f00", "font_family": "'Source Han Sans CN', sans-serif",
            "border_radius": "8px", "text_shadow": "0 0 8px rgba(255,183,77,0.4), 0 0 16px rgba(255,138,101,0.2)",
            "text_highlight_color": "rgba(255,138,101,0.25)", "text_glow": "drop-shadow(0 0 6px rgba(255,183,77,0.6))",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "arctic_minimal": {
        "name": "极地简约",
        "desc": "纯白冰蓝，极简设计，清冷专注的高效学习",
        "preview_colors": {"bg": "#f0f4ff", "src": "#1976d2", "tgt": "#5c6bc0", "box_bg": "#e8eef7"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#1976D2"), "SecondaryColour": _c("#5C6BC0"),
            "OutlineColour": _c("#E8EEF7", 0x10), "BackColour": _c("#FFFFFF", 0x20),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#E8EEF7", 0x10), "word_colour": _c("#1565C0"),
            "phonetic_colour": _c("#5C6BC0"), "trans_colour": _c("#37474F"),
            "accent_colour": _c("#1976D2"), "header_colour": _c("#5C6BC0"),
        },
        "exprbox": {
            "bg_colour": _c("#E8EEF7", 0x15), "en_colour": _c("#0D47A1"),
            "cn_colour": _c("#37474F"), "accent_colour": _c("#0D47A1"),
            "header_colour": _c("#1976D2"),
        },
        "css": {
            "subtitle_bg": "rgba(232,238,247,0.92)", "subtitle_src_color": "#1976d2",
            "subtitle_tgt_color": "#5c6bc0", "box_bg": "rgba(240,244,255,0.95)",
            "word_color": "#1565c0", "phonetic_color": "#5c6bc0", "trans_color": "#37474f",
            "expr_color": "#0d47a1", "font_family": "'Inter', 'Noto Sans SC', sans-serif",
            "border_radius": "6px", "text_shadow": "0 0.5px 2px rgba(0,0,0,0.1)",
            "text_highlight_color": "rgba(25,118,210,0.1)", "text_glow": "none",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "royal_purple": {
        "name": "皇家紫",
        "desc": "深紫金色，奢华尊贵，精英品质学习体验",
        "preview_colors": {"bg": "#2d1b4e", "src": "#d4a5d4", "tgt": "#ffd700", "box_bg": "#3f2765"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#D4A5D4"), "SecondaryColour": _c("#FFD700"),
            "OutlineColour": _c("#2D1B4E", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#3F2765", 0x80), "word_colour": _c("#D4A5D4"),
            "phonetic_colour": _c("#FFD700"), "trans_colour": _c("#F3E5F5"),
            "accent_colour": _c("#D4A5D4"), "header_colour": _c("#FFD700"),
        },
        "exprbox": {
            "bg_colour": _c("#2D1B4E", 0x80), "en_colour": _c("#FFD700"),
            "cn_colour": _c("#F3E5F5"), "accent_colour": _c("#FFD700"),
            "header_colour": _c("#D4A5D4"),
        },
        "css": {
            "subtitle_bg": "rgba(45,27,78,0.88)", "subtitle_src_color": "#d4a5d4",
            "subtitle_tgt_color": "#ffd700", "box_bg": "rgba(63,39,101,0.92)",
            "word_color": "#d4a5d4", "phonetic_color": "#ffd700", "trans_color": "#f3e5f5",
            "expr_color": "#ffd700", "font_family": "'Source Han Serif CN', serif",
            "border_radius": "8px", "text_shadow": "0 0 12px rgba(255,215,0,0.4), 0 0 8px rgba(212,165,212,0.2)",
            "text_highlight_color": "rgba(212,165,212,0.2)", "text_outline": "0.5px rgba(255,215,0,0.6)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "retro_terminal": {
        "name": "复古终端",
        "desc": "磷光绿CRT风格，扫描线，80年代计算机美学",
        "preview_colors": {"bg": "#001100", "src": "#00ff00", "tgt": "#88ff88", "box_bg": "#0a2a0a"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#00FF00"), "SecondaryColour": _c("#88FF88"),
            "OutlineColour": _c("#001100", 0x80), "BackColour": _c("#000000", 0xD0),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#0A2A0A", 0x80), "word_colour": _c("#00FF00"),
            "phonetic_colour": _c("#88FF88"), "trans_colour": _c("#00FF00"),
            "accent_colour": _c("#00FF00"), "header_colour": _c("#88FF88"),
        },
        "exprbox": {
            "bg_colour": _c("#001100", 0x80), "en_colour": _c("#00FF00"),
            "cn_colour": _c("#00FF00"), "accent_colour": _c("#00FF00"),
            "header_colour": _c("#88FF88"),
        },
        "css": {
            "subtitle_bg": "rgba(0,17,0,0.92)", "subtitle_src_color": "#00ff00",
            "subtitle_tgt_color": "#88ff88", "box_bg": "rgba(10,42,10,0.95)",
            "word_color": "#00ff00", "phonetic_color": "#88ff88", "trans_color": "#00ff00",
            "expr_color": "#00ff00", "font_family": "'Courier New', monospace",
            "border_radius": "0px", "text_shadow": "0 0 10px rgba(0,255,0,0.8), inset 0 0 8px rgba(0,255,0,0.2)",
            "text_highlight_color": "rgba(0,255,0,0.15)", "text_glow": "drop-shadow(0 0 10px #00ff00)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "aurora_night": {
        "name": "极光暗夜",
        "desc": "深紫背景，紫粉渐变高亮，沉浸式暗色学习体验",
        "preview_colors": {
            "bg": "#0f0f1e", "src": "#a78bfa", "tgt": "#94a3b8", "box_bg": "#1a1a2e"
        },
        "animation": "fade",
        "subtitle": {
            "PrimaryColour":   _c("#EEE8FF"),       # 白紫色原文
            "SecondaryColour": _c("#94A3B8"),        # 灰蓝译文
            "OutlineColour":   _c("#1A1A2E", 0x80),  # 半透深色背景
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#1A1A2E", 0x80),
            "word_colour":     _c("#BFA8FF"),
            "phonetic_colour": _c("#94A3B8"),
            "trans_colour":    _c("#F1F5F9"),
            "accent_colour":   _c("#A78BFA"),
            "header_colour":   _c("#94A3B8"),
        },
        "exprbox": {
            "bg_colour":       _c("#0F172A", 0x80),
            "en_colour":       _c("#F472B6"),
            "cn_colour":       _c("#F1F5F9"),
            "accent_colour":   _c("#F472B6"),
            "header_colour":   _c("#94A3B8"),
        },
        "css": {
            "subtitle_bg":        "rgba(26,26,46,0.85)",
            "subtitle_src_color": "#a78bfa",
            "subtitle_tgt_color": "#94a3b8",
            "box_bg":             "rgba(15,15,30,0.9)",
            "word_color":         "#bfa8ff",
            "phonetic_color":     "#94a3b8",
            "trans_color":        "#f1f5f9",
            "expr_color":         "#f472b6",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "10px",
            "text_shadow":        "0 0 12px rgba(167,139,250,0.4)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "cherry_blossom": {
        "name": "樱花物语",
        "desc": "浅粉樱花配色，圆角柔和，日系温柔学习风格",
        "preview_colors": {"bg": "#fff5f9", "src": "#c2185b", "tgt": "#f06292", "box_bg": "#fce4f3"},
        "animation": "pop",
        "subtitle": {
            "PrimaryColour": _c("#C2185B"), "SecondaryColour": _c("#F06292"),
            "OutlineColour": _c("#FCE4F3", 0x20), "BackColour": _c("#FFFFFF", 0x30),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#FCE4F3", 0x20), "word_colour": _c("#C2185B"),
            "phonetic_colour": _c("#F06292"), "trans_colour": _c("#212121"),
            "accent_colour": _c("#EC407A"), "header_colour": _c("#C2185B"),
        },
        "exprbox": {
            "bg_colour": _c("#FCE4F3", 0x20), "en_colour": _c("#EC407A"),
            "cn_colour": _c("#212121"), "accent_colour": _c("#EC407A"),
            "header_colour": _c("#C2185B"),
        },
        "css": {
            "subtitle_bg": "rgba(252,228,243,0.92)", "subtitle_src_color": "#c2185b",
            "subtitle_tgt_color": "#f06292", "box_bg": "rgba(255,245,249,0.95)",
            "word_color": "#c2185b", "phonetic_color": "#f06292", "trans_color": "#212121",
            "expr_color": "#ec407a", "font_family": "'Source Han Sans CN', sans-serif",
            "border_radius": "16px", "text_shadow": "0 0 6px rgba(194,24,91,0.15)",
            "text_highlight_color": "rgba(240,98,146,0.2)", "text_glow": "none",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "midnight_ocean": {
        "name": "深海午夜",
        "desc": "深蓝流光，青色脉动，深邃神秘的海洋意象",
        "preview_colors": {"bg": "#0a1929", "src": "#29b6f6", "tgt": "#80deea", "box_bg": "#0d2d4a"},
        "animation": "slide_up",
        "subtitle": {
            "PrimaryColour": _c("#29B6F6"), "SecondaryColour": _c("#80DEEA"),
            "OutlineColour": _c("#0A1929", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#0D2D4A", 0x80), "word_colour": _c("#29B6F6"),
            "phonetic_colour": _c("#80DEEA"), "trans_colour": _c("#E0F7FF"),
            "accent_colour": _c("#29B6F6"), "header_colour": _c("#80DEEA"),
        },
        "exprbox": {
            "bg_colour": _c("#0A1929", 0x80), "en_colour": _c("#00BCD4"),
            "cn_colour": _c("#E0F7FF"), "accent_colour": _c("#00BCD4"),
            "header_colour": _c("#29B6F6"),
        },
        "css": {
            "subtitle_bg": "rgba(10,25,41,0.88)", "subtitle_src_color": "#29b6f6",
            "subtitle_tgt_color": "#80deea", "box_bg": "rgba(13,45,74,0.92)",
            "word_color": "#29b6f6", "phonetic_color": "#80deea", "trans_color": "#e0f7ff",
            "expr_color": "#00bcd4", "font_family": "'Source Han Sans CN', sans-serif",
            "border_radius": "10px", "text_shadow": "0 0 12px rgba(41,182,246,0.4), 0 0 20px rgba(128,222,234,0.15)",
            "text_highlight_color": "rgba(0,188,212,0.2)", "text_glow": "drop-shadow(0 0 8px rgba(41,182,246,0.5))",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "golden_age": {
        "name": "黄金时代",
        "desc": "深棕金色，复古纸张质感，经典怀旧学习氛围",
        "preview_colors": {"bg": "#3e2723", "src": "#daa520", "tgt": "#cd7f32", "box_bg": "#4e342e"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#DAA520"), "SecondaryColour": _c("#CD7F32"),
            "OutlineColour": _c("#3E2723", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#4E342E", 0x80), "word_colour": _c("#DAA520"),
            "phonetic_colour": _c("#CD7F32"), "trans_colour": _c("#F5DEB3"),
            "accent_colour": _c("#DAA520"), "header_colour": _c("#CD7F32"),
        },
        "exprbox": {
            "bg_colour": _c("#3E2723", 0x80), "en_colour": _c("#FFB923"),
            "cn_colour": _c("#F5DEB3"), "accent_colour": _c("#FFB923"),
            "header_colour": _c("#DAA520"),
        },
        "css": {
            "subtitle_bg": "rgba(62,39,35,0.88)", "subtitle_src_color": "#daa520",
            "subtitle_tgt_color": "#cd7f32", "box_bg": "rgba(78,52,46,0.92)",
            "word_color": "#daa520", "phonetic_color": "#cd7f32", "trans_color": "#f5deb3",
            "expr_color": "#ffb923", "font_family": "'Source Han Serif CN', serif",
            "border_radius": "8px", "text_shadow": "0 1px 3px rgba(0,0,0,0.6), 0 0 8px rgba(218,165,32,0.3)",
            "text_highlight_color": "rgba(218,165,32,0.2)", "text_outline": "0.5px rgba(205,127,50,0.5)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "volcanic_ash": {
        "name": "火山灰烬",
        "desc": "深灰橙红，熔岩质感，炽热激情的能量学习",
        "preview_colors": {"bg": "#2c2416", "src": "#ff6e40", "tgt": "#e64a19", "box_bg": "#3d322a"},
        "animation": "pop",
        "subtitle": {
            "PrimaryColour": _c("#FF6E40"), "SecondaryColour": _c("#E64A19"),
            "OutlineColour": _c("#2C2416", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#3D322A", 0x80), "word_colour": _c("#FF6E40"),
            "phonetic_colour": _c("#E64A19"), "trans_colour": _c("#FFF8E1"),
            "accent_colour": _c("#FF6E40"), "header_colour": _c("#E64A19"),
        },
        "exprbox": {
            "bg_colour": _c("#2C2416", 0x80), "en_colour": _c("#FF5722"),
            "cn_colour": _c("#FFF8E1"), "accent_colour": _c("#FF5722"),
            "header_colour": _c("#FF6E40"),
        },
        "css": {
            "subtitle_bg": "rgba(44,36,22,0.88)", "subtitle_src_color": "#ff6e40",
            "subtitle_tgt_color": "#e64a19", "box_bg": "rgba(61,50,42,0.92)",
            "word_color": "#ff6e40", "phonetic_color": "#e64a19", "trans_color": "#fff8e1",
            "expr_color": "#ff5722", "font_family": "'Source Han Sans CN', sans-serif",
            "border_radius": "6px", "text_shadow": "0 0 10px rgba(255,110,64,0.4), 0 0 16px rgba(230,74,25,0.2)",
            "text_highlight_color": "rgba(255,87,34,0.25)", "text_glow": "drop-shadow(0 0 8px rgba(255,110,64,0.6))",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "spring_meadow": {
        "name": "春日草原",
        "desc": "清新草绿，自然生机，温和舒适的绿色学习空间",
        "preview_colors": {"bg": "#1b5e20", "src": "#7cb342", "tgt": "#c5e1a5", "box_bg": "#2e7d32"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#7CB342"), "SecondaryColour": _c("#C5E1A5"),
            "OutlineColour": _c("#1B5E20", 0x80), "BackColour": _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#2E7D32", 0x80), "word_colour": _c("#9CCC65"),
            "phonetic_colour": _c("#AED581"), "trans_colour": _c("#F1F8E9"),
            "accent_colour": _c("#7CB342"), "header_colour": _c("#AED581"),
        },
        "exprbox": {
            "bg_colour": _c("#1B5E20", 0x80), "en_colour": _c("#689F38"),
            "cn_colour": _c("#F1F8E9"), "accent_colour": _c("#689F38"),
            "header_colour": _c("#7CB342"),
        },
        "css": {
            "subtitle_bg": "rgba(27,94,32,0.88)", "subtitle_src_color": "#7cb342",
            "subtitle_tgt_color": "#c5e1a5", "box_bg": "rgba(46,125,50,0.92)",
            "word_color": "#9ccc65", "phonetic_color": "#aed581", "trans_color": "#f1f8e9",
            "expr_color": "#689f38", "font_family": "'Source Han Sans CN', sans-serif",
            "border_radius": "10px", "text_shadow": "0 0 8px rgba(124,179,66,0.3)",
            "text_highlight_color": "rgba(156,204,101,0.2)", "text_glow": "none",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "ink_wash": {
        "name": "写意水墨",
        "desc": "米色宣纸，墨黑文字，传统水墨书法意蕴",
        "preview_colors": {"bg": "#fffbf0", "src": "#3f3f3f", "tgt": "#5a5a5a", "box_bg": "#f5f1ed"},
        "animation": "fade",
        "subtitle": {
            "PrimaryColour": _c("#3F3F3F"), "SecondaryColour": _c("#5A5A5A"),
            "OutlineColour": _c("#F5F1ED", 0x20), "BackColour": _c("#FFFBF0", 0x30),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour": _c("#F5F1ED", 0x20), "word_colour": _c("#2C2C2C"),
            "phonetic_colour": _c("#5A5A5A"), "trans_colour": _c("#3F3F3F"),
            "accent_colour": _c("#3F3F3F"), "header_colour": _c("#5A5A5A"),
        },
        "exprbox": {
            "bg_colour": _c("#F5F1ED", 0x20), "en_colour": _c("#2C2C2C"),
            "cn_colour": _c("#3F3F3F"), "accent_colour": _c("#2C2C2C"),
            "header_colour": _c("#5A5A5A"),
        },
        "css": {
            "subtitle_bg": "rgba(245,241,237,0.92)", "subtitle_src_color": "#3f3f3f",
            "subtitle_tgt_color": "#5a5a5a", "box_bg": "rgba(255,251,240,0.95)",
            "word_color": "#2c2c2c", "phonetic_color": "#5a5a5a", "trans_color": "#3f3f3f",
            "expr_color": "#2c2c2c", "font_family": "'Source Han Serif CN', serif",
            "border_radius": "4px", "text_shadow": "0 0.5px 1px rgba(0,0,0,0.2)",
            "text_highlight_color": "rgba(100,100,100,0.1)", "text_outline": "0.3px rgba(0,0,0,0.3)",
        },
    },
}


# 动画标签映射（在 ASSGenerator 中使用）
ANIM_TAGS = {
    "fade":     r"\fad(200,150)",
    "slide_up": None,   # 计算时动态生成 \move 标签
    "pop":      r"\t(0,150,\fscx110\fscy110)\t(150,250,\fscx100\fscy100)",
    "typewriter": None,  # 复杂，用 fade 代替
}

# 默认样式 ID
DEFAULT_STYLE_ID = "neon_cyberpunk"
