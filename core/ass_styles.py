"""
ASS 样式模版定义 — 8 套 CapCut 风格美学主题
每套模版包含：
  - name / desc / preview_colors（前端画廊展示）
  - animation（默认入场动画类型）
  - subtitle / wordbox / exprbox 的 ASS 颜色参数
  - css（前端画布 CSS 近似预览，不需要像素级精确）

ASS 颜色格式：&HAABBGGRR（AA=alpha 0x00=不透明 0xFF=全透明）
"""

def _c(hex_color: str, alpha: int = 0) -> str:
    """将 #RRGGBB 转换为 ASS &HAABBGGRR 格式"""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


STYLE_TEMPLATES = {

    # ─────────────────────────────────────────────────────────────
    "aurora_dark": {
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
    "chalk_board": {
        "name": "黑板粉笔",
        "desc": "深绿黑板质感，白色粉笔字，经典课堂复古风格",
        "preview_colors": {
            "bg": "#1b3a2b", "src": "#e8f5e9", "tgt": "#a5d6a7", "box_bg": "#143022"
        },
        "animation": "slide_up",
        "subtitle": {
            "PrimaryColour":   _c("#E8F5E9"),
            "SecondaryColour": _c("#A5D6A7"),
            "OutlineColour":   _c("#1B3A2B", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#1B3A2B", 0x80),
            "word_colour":     _c("#FFFFFF"),
            "phonetic_colour": _c("#81C784"),
            "trans_colour":    _c("#E8F5E9"),
            "accent_colour":   _c("#A5D6A7"),
            "header_colour":   _c("#81C784"),
        },
        "exprbox": {
            "bg_colour":       _c("#143022", 0x80),
            "en_colour":       _c("#FFEB3B"),
            "cn_colour":       _c("#E8F5E9"),
            "accent_colour":   _c("#FFEB3B"),
            "header_colour":   _c("#81C784"),
        },
        "css": {
            "subtitle_bg":        "rgba(27,58,43,0.85)",
            "subtitle_src_color": "#e8f5e9",
            "subtitle_tgt_color": "#a5d6a7",
            "box_bg":             "rgba(20,48,34,0.9)",
            "word_color":         "#ffffff",
            "phonetic_color":     "#81c784",
            "trans_color":        "#e8f5e9",
            "expr_color":         "#ffeb3b",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "6px",
            "text_shadow":        "0 1px 3px rgba(0,0,0,0.6)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "neon_city": {
        "name": "霓虹都市",
        "desc": "纯黑背景，电光青与玫瑰霓虹高亮，赛博朋克科技感",
        "preview_colors": {
            "bg": "#000000", "src": "#00ffff", "tgt": "#888888", "box_bg": "#050510"
        },
        "animation": "pop",
        "subtitle": {
            "PrimaryColour":   _c("#00FFFF"),
            "SecondaryColour": _c("#888888"),
            "OutlineColour":   _c("#050510", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#050510", 0x80),
            "word_colour":     _c("#00FFFF"),
            "phonetic_colour": _c("#888888"),
            "trans_colour":    _c("#FFFFFF"),
            "accent_colour":   _c("#00FFFF"),
            "header_colour":   _c("#FF0080"),
        },
        "exprbox": {
            "bg_colour":       _c("#050510", 0x80),
            "en_colour":       _c("#FF0080"),
            "cn_colour":       _c("#FFFFFF"),
            "accent_colour":   _c("#FF0080"),
            "header_colour":   _c("#00FFFF"),
        },
        "css": {
            "subtitle_bg":        "rgba(5,5,16,0.85)",
            "subtitle_src_color": "#00ffff",
            "subtitle_tgt_color": "#888888",
            "box_bg":             "rgba(5,5,16,0.9)",
            "word_color":         "#00ffff",
            "phonetic_color":     "#888888",
            "trans_color":        "#ffffff",
            "expr_color":         "#ff0080",
            "font_family":        "'Roboto', 'Source Han Sans CN', sans-serif",
            "border_radius":      "4px",
            "text_shadow":        "0 0 10px rgba(0,255,255,0.6)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "warm_paper": {
        "name": "暖光羊皮",
        "desc": "米黄纸质感，棕色手写风，温暖舒适的阅读体验",
        "preview_colors": {
            "bg": "#2d1b0e", "src": "#f4a460", "tgt": "#d2b48c", "box_bg": "#3d2515"
        },
        "animation": "fade",
        "subtitle": {
            "PrimaryColour":   _c("#F4A460"),
            "SecondaryColour": _c("#D2B48C"),
            "OutlineColour":   _c("#2D1B0E", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#3D2515", 0x80),
            "word_colour":     _c("#F4A460"),
            "phonetic_colour": _c("#D2B48C"),
            "trans_colour":    _c("#FFF8DC"),
            "accent_colour":   _c("#F4A460"),
            "header_colour":   _c("#D2B48C"),
        },
        "exprbox": {
            "bg_colour":       _c("#4A3728", 0x80),
            "en_colour":       _c("#FF9562"),
            "cn_colour":       _c("#FFF8DC"),
            "accent_colour":   _c("#FF9562"),
            "header_colour":   _c("#D2B48C"),
        },
        "css": {
            "subtitle_bg":        "rgba(45,27,14,0.85)",
            "subtitle_src_color": "#f4a460",
            "subtitle_tgt_color": "#d2b48c",
            "box_bg":             "rgba(61,37,21,0.9)",
            "word_color":         "#f4a460",
            "phonetic_color":     "#d2b48c",
            "trans_color":        "#fff8dc",
            "expr_color":         "#ff9562",
            "font_family":        "'Source Han Serif CN', serif",
            "border_radius":      "8px",
            "text_shadow":        "0 1px 4px rgba(0,0,0,0.5)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "ocean_deep": {
        "name": "深海蔚蓝",
        "desc": "深海蓝背景，青白文字，清澈通透的海洋学习氛围",
        "preview_colors": {
            "bg": "#0a2040", "src": "#4db8ff", "tgt": "#80c4e9", "box_bg": "#0d2b4a"
        },
        "animation": "slide_up",
        "subtitle": {
            "PrimaryColour":   _c("#4DB8FF"),
            "SecondaryColour": _c("#80C4E9"),
            "OutlineColour":   _c("#0A2040", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#0D2B4A", 0x80),
            "word_colour":     _c("#4DB8FF"),
            "phonetic_colour": _c("#80C4E9"),
            "trans_colour":    _c("#E8F4FD"),
            "accent_colour":   _c("#4DB8FF"),
            "header_colour":   _c("#80C4E9"),
        },
        "exprbox": {
            "bg_colour":       _c("#0A1A30", 0x80),
            "en_colour":       _c("#40DFB8"),
            "cn_colour":       _c("#E8F4FD"),
            "accent_colour":   _c("#40DFB8"),
            "header_colour":   _c("#80C4E9"),
        },
        "css": {
            "subtitle_bg":        "rgba(10,32,64,0.85)",
            "subtitle_src_color": "#4db8ff",
            "subtitle_tgt_color": "#80c4e9",
            "box_bg":             "rgba(13,43,74,0.9)",
            "word_color":         "#4db8ff",
            "phonetic_color":     "#80c4e9",
            "trans_color":        "#e8f4fd",
            "expr_color":         "#40dfb8",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "10px",
            "text_shadow":        "0 0 8px rgba(77,184,255,0.4)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "academic": {
        "name": "学院经典",
        "desc": "白色背景，靛蓝标题字，简洁学术风格，适合正式学习",
        "preview_colors": {
            "bg": "#f8f9fa", "src": "#4f46e5", "tgt": "#374151", "box_bg": "#f1f5f9"
        },
        "animation": "fade",
        "subtitle": {
            "PrimaryColour":   _c("#4F46E5"),
            "SecondaryColour": _c("#374151"),
            "OutlineColour":   _c("#F1F5F9", 0x20),
            "BackColour":      _c("#FFFFFF", 0x30),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#F1F5F9", 0x20),
            "word_colour":     _c("#6366F1"),
            "phonetic_colour": _c("#6B7280"),
            "trans_colour":    _c("#1F2937"),
            "accent_colour":   _c("#4F46E5"),
            "header_colour":   _c("#6B7280"),
        },
        "exprbox": {
            "bg_colour":       _c("#FDF2F8", 0x20),
            "en_colour":       _c("#DB2777"),
            "cn_colour":       _c("#1F2937"),
            "accent_colour":   _c("#DB2777"),
            "header_colour":   _c("#6B7280"),
        },
        "css": {
            "subtitle_bg":        "rgba(241,245,249,0.92)",
            "subtitle_src_color": "#4f46e5",
            "subtitle_tgt_color": "#374151",
            "box_bg":             "rgba(248,249,250,0.95)",
            "word_color":         "#6366f1",
            "phonetic_color":     "#6b7280",
            "trans_color":        "#1f2937",
            "expr_color":         "#db2777",
            "font_family":        "'Noto Sans SC', 'Source Han Sans CN', sans-serif",
            "border_radius":      "8px",
            "text_shadow":        "none",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "sakura": {
        "name": "樱花粉",
        "desc": "浅粉主题，深玫瑰色文字，温柔甜美的日系学习风格",
        "preview_colors": {
            "bg": "#fff0f6", "src": "#be185d", "tgt": "#831843", "box_bg": "#fce7f3"
        },
        "animation": "pop",
        "subtitle": {
            "PrimaryColour":   _c("#BE185D"),
            "SecondaryColour": _c("#831843"),
            "OutlineColour":   _c("#FDF2F8", 0x20),
            "BackColour":      _c("#FFFFFF", 0x30),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#FDF2F8", 0x20),
            "word_colour":     _c("#DB2777"),
            "phonetic_colour": _c("#BE185D"),
            "trans_colour":    _c("#1F2937"),
            "accent_colour":   _c("#9D174D"),
            "header_colour":   _c("#BE185D"),
        },
        "exprbox": {
            "bg_colour":       _c("#FDF2F8", 0x20),
            "en_colour":       _c("#9D174D"),
            "cn_colour":       _c("#1F2937"),
            "accent_colour":   _c("#9D174D"),
            "header_colour":   _c("#BE185D"),
        },
        "css": {
            "subtitle_bg":        "rgba(253,242,248,0.92)",
            "subtitle_src_color": "#be185d",
            "subtitle_tgt_color": "#831843",
            "box_bg":             "rgba(252,231,243,0.95)",
            "word_color":         "#db2777",
            "phonetic_color":     "#be185d",
            "trans_color":        "#1f2937",
            "expr_color":         "#9d174d",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "12px",
            "text_shadow":        "0 0 6px rgba(190,24,93,0.2)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "midnight_gold": {
        "name": "午夜金",
        "desc": "深蓝黑底，金色高亮文字，奢华精致的夜间学习体验",
        "preview_colors": {
            "bg": "#0a1628", "src": "#ffd700", "tgt": "#b8a361", "box_bg": "#0e1f3a"
        },
        "animation": "fade",
        "subtitle": {
            "PrimaryColour":   _c("#FFD700"),
            "SecondaryColour": _c("#B8A361"),
            "OutlineColour":   _c("#0A1628", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#0E1F3A", 0x80),
            "word_colour":     _c("#FFD700"),
            "phonetic_colour": _c("#B8A361"),
            "trans_colour":    _c("#E8E0D0"),
            "accent_colour":   _c("#FFD700"),
            "header_colour":   _c("#B8A361"),
        },
        "exprbox": {
            "bg_colour":       _c("#080F1E", 0x80),
            "en_colour":       _c("#FFD700"),
            "cn_colour":       _c("#E8E0D0"),
            "accent_colour":   _c("#FFD700"),
            "header_colour":   _c("#B8A361"),
        },
        "css": {
            "subtitle_bg":        "rgba(10,22,40,0.88)",
            "subtitle_src_color": "#ffd700",
            "subtitle_tgt_color": "#b8a361",
            "box_bg":             "rgba(14,31,58,0.92)",
            "word_color":         "#ffd700",
            "phonetic_color":     "#b8a361",
            "trans_color":        "#e8e0d0",
            "expr_color":         "#ffd700",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "8px",
            "text_shadow":        "0 0 12px rgba(255,215,0,0.4)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "forest_zen": {
        "name": "禅意森林",
        "desc": "深绿禅意背景，柔和金色文字，宁静专注的自然学习氛围",
        "preview_colors": {
            "bg": "#0d2010", "src": "#c8a84b", "tgt": "#8fbc6a", "box_bg": "#112a14"
        },
        "animation": "slide_up",
        "subtitle": {
            "PrimaryColour":   _c("#C8A84B"),
            "SecondaryColour": _c("#8FBC6A"),
            "OutlineColour":   _c("#0D2010", 0x80),
            "BackColour":      _c("#000000", 0xC8),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#112A14", 0x80),
            "word_colour":     _c("#C8A84B"),
            "phonetic_colour": _c("#8FBC6A"),
            "trans_colour":    _c("#E8F5E9"),
            "accent_colour":   _c("#C8A84B"),
            "header_colour":   _c("#8FBC6A"),
        },
        "exprbox": {
            "bg_colour":       _c("#0A1E0C", 0x80),
            "en_colour":       _c("#A8D572"),
            "cn_colour":       _c("#E8F5E9"),
            "accent_colour":   _c("#A8D572"),
            "header_colour":   _c("#8FBC6A"),
        },
        "css": {
            "subtitle_bg":        "rgba(13,32,16,0.88)",
            "subtitle_src_color": "#c8a84b",
            "subtitle_tgt_color": "#8fbc6a",
            "box_bg":             "rgba(17,42,20,0.92)",
            "word_color":         "#c8a84b",
            "phonetic_color":     "#8fbc6a",
            "trans_color":        "#e8f5e9",
            "expr_color":         "#a8d572",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "10px",
            "text_shadow":        "0 0 8px rgba(200,168,75,0.3)",
        },
    },

    # ─────────────────────────────────────────────────────────────
    "cotton_candy": {
        "name": "棉花糖",
        "desc": "浅粉薄荷配色，明亮活泼，适合轻松愉快的日常学习",
        "preview_colors": {
            "bg": "#fff0f8", "src": "#e91e8c", "tgt": "#00bfa5", "box_bg": "#fce4f4"
        },
        "animation": "pop",
        "subtitle": {
            "PrimaryColour":   _c("#E91E8C"),
            "SecondaryColour": _c("#00BFA5"),
            "OutlineColour":   _c("#FFF0F8", 0x20),
            "BackColour":      _c("#FFFFFF", 0x30),
            "Bold": 1, "FontSize": 50,
        },
        "wordbox": {
            "bg_colour":       _c("#FCE4F4", 0x20),
            "word_colour":     _c("#C2185B"),
            "phonetic_colour": _c("#00897B"),
            "trans_colour":    _c("#212121"),
            "accent_colour":   _c("#E91E8C"),
            "header_colour":   _c("#00BFA5"),
        },
        "exprbox": {
            "bg_colour":       _c("#E0F7F4", 0x20),
            "en_colour":       _c("#E91E8C"),
            "cn_colour":       _c("#212121"),
            "accent_colour":   _c("#E91E8C"),
            "header_colour":   _c("#00BFA5"),
        },
        "css": {
            "subtitle_bg":        "rgba(252,228,244,0.92)",
            "subtitle_src_color": "#e91e8c",
            "subtitle_tgt_color": "#00bfa5",
            "box_bg":             "rgba(255,240,248,0.95)",
            "word_color":         "#c2185b",
            "phonetic_color":     "#00897b",
            "trans_color":        "#212121",
            "expr_color":         "#e91e8c",
            "font_family":        "'Source Han Sans CN', sans-serif",
            "border_radius":      "14px",
            "text_shadow":        "0 0 6px rgba(233,30,140,0.15)",
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
DEFAULT_STYLE_ID = "aurora_dark"
