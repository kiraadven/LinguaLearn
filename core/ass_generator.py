"""
ASS 文件生成器
替代 html_renderer.py，使用纯 ASS 格式生成字幕/单词框/表达框叠加层
供 FFmpeg -vf ass=file.ass 烧录到视频
"""

import os
from typing import List, Dict, Optional

from ass_styles import STYLE_TEMPLATES, ANIM_TAGS, DEFAULT_STYLE_ID


class ASSGenerator:
    """
    ASS 文件生成器

    使用说明：
        gen = ASSGenerator("aurora_dark", "1080p")
        content = gen.generate(
            duration=8.0,
            original_text="...",
            translated_text="...",
            key_words=[...],
            expressions=[...],
            layout={...},
            show_subtitle=True,
            show_wordbox=True,
            show_exprbox=True,
        )
        gen.write_to_file(content, "/tmp/sub.ass")
    """

    # 默认布局（百分比 0-1）
    DEFAULT_LAYOUT = {
        "subtitle": {"x_pct": 0.05, "y_pct": 0.76, "w_pct": 0.90, "h_pct": 0.14},
        "wordbox":  {"x_pct": 0.75, "y_pct": 0.005, "w_pct": 0.245, "h_pct": 0.65},
        "exprbox":  {"x_pct": 0.005, "y_pct": 0.005, "w_pct": 0.245, "h_pct": 0.55},
    }

    def __init__(self, style_id: str = DEFAULT_STYLE_ID, resolution: str = "1080p"):
        if style_id not in STYLE_TEMPLATES:
            style_id = DEFAULT_STYLE_ID
        self.style = STYLE_TEMPLATES[style_id]
        self.style_id = style_id
        self.resolution = resolution
        self.frame_w = 1920 if resolution == "1080p" else 1280
        self.frame_h = 1080 if resolution == "1080p" else 720
        # 720p 时字体缩小到 0.667x
        self._font_scale = 1.0 if resolution == "1080p" else 0.667

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def generate(
        self,
        duration: float,
        original_text: str,
        translated_text: str,
        key_words: List[Dict],
        expressions: List[Dict],
        layout: Optional[Dict] = None,
        show_subtitle: bool = True,
        show_wordbox: bool = True,
        show_exprbox: bool = True,
        animation: Optional[str] = None,
    ) -> str:
        """生成 .ass 文件内容字符串"""
        layout = self._merge_layout(layout or {})
        anim = animation or self.style.get("animation", "fade")

        t_start = "0:00:00.00"
        t_end   = self._fmt_time(duration)

        lines = []
        lines.append(self._script_info())
        lines.append(self._v4_styles())
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

        if show_subtitle:
            sub_lay = layout["subtitle"]
            lines += self._subtitle_events(
                t_start, t_end, original_text, translated_text, sub_lay, anim
            )

        if show_wordbox and key_words:
            wb_lay = layout["wordbox"]
            lines += self._wordbox_events(
                t_start, t_end, key_words, wb_lay, anim
            )

        if show_exprbox and expressions:
            eb_lay = layout["exprbox"]
            lines += self._exprbox_events(
                t_start, t_end, expressions, eb_lay, anim
            )

        return "\n".join(lines) + "\n"

    def write_to_file(self, content: str, path: str) -> None:
        """写入 .ass 文件（UTF-8 with BOM，FFmpeg 要求）"""
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(content)

    # ──────────────────────────────────────────────────────────────
    # ASS Script Info
    # ──────────────────────────────────────────────────────────────

    def _script_info(self) -> str:
        return (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "Collisions: Normal\n"
            "WrapStyle: 1\n"
            f"PlayResX: {self.frame_w}\n"
            f"PlayResY: {self.frame_h}\n"
            "ScaledBorderAndShadow: yes\n"
        )

    def _v4_styles(self) -> str:
        """生成 [V4+ Styles] 段，包含 Subtitle / Word / Expr / Draw 四个样式"""
        fmt = (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )
        styles = []

        # ── Subtitle 样式 ──
        sub = self.style["subtitle"]
        styles.append(self._make_style(
            name="Subtitle",
            fontsize=self._fs(sub.get("FontSize", 50)),
            primary=sub["PrimaryColour"],
            secondary=sub["SecondaryColour"],
            outline=sub["OutlineColour"],
            back=sub["BackColour"],
            bold=sub.get("Bold", 1),
            border_style=4,    # 4 = opaque box
            outline_w=0, shadow=0,
            alignment=5,       # middle-center（用 \pos 覆盖）
        ))

        # ── Word 样式（单词框文字基础样式）──
        wb = self.style["wordbox"]
        styles.append(self._make_style(
            name="Word",
            fontsize=self._fs(26),
            primary=wb["word_colour"],
            secondary=wb["phonetic_colour"],
            outline="&H00000000",
            back="&H00000000",
            bold=0,
            border_style=1,
            outline_w=0, shadow=0,
            alignment=7,       # top-left
        ))

        # ── Expr 样式（表达框文字基础样式）──
        eb = self.style["exprbox"]
        styles.append(self._make_style(
            name="Expr",
            fontsize=self._fs(26),
            primary=eb["en_colour"],
            secondary=eb["cn_colour"],
            outline="&H00000000",
            back="&H00000000",
            bold=0,
            border_style=1,
            outline_w=0, shadow=0,
            alignment=7,
        ))

        # ── Draw 样式（背景矩形专用）──
        styles.append(self._make_style(
            name="Draw",
            fontsize=self._fs(1),
            primary="&H00FFFFFF",
            secondary="&H00FFFFFF",
            outline="&H00000000",
            back="&H00000000",
            bold=0,
            border_style=1,
            outline_w=0, shadow=0,
            alignment=7,
        ))

        return "[V4+ Styles]\n" + fmt + "".join(styles)

    def _make_style(
        self, name: str, fontsize: int, primary: str, secondary: str,
        outline: str, back: str, bold: int, border_style: int,
        outline_w: int, shadow: int, alignment: int,
        fontname: str = "Source Han Sans CN",
    ) -> str:
        return (
            f"Style: {name},{fontname},{fontsize},"
            f"{primary},{secondary},{outline},{back},"
            f"{bold},0,0,0,"           # Bold,Italic,Underline,StrikeOut
            f"100,100,0,0,"            # ScaleX,ScaleY,Spacing,Angle
            f"{border_style},{outline_w},{shadow},"
            f"{alignment},0,0,0,1\n"  # Alignment,MarginL,R,V,Encoding
        )

    # ──────────────────────────────────────────────────────────────
    # Subtitle Events
    # ──────────────────────────────────────────────────────────────

    def _subtitle_events(
        self, t0: str, t1: str,
        original: str, translated: str,
        lay: Dict, anim: str,
    ) -> List[str]:
        x = int(lay["x_pct"] * self.frame_w)
        y = int(lay["y_pct"] * self.frame_h)
        w = int(lay["w_pct"] * self.frame_w)
        h = int(lay["h_pct"] * self.frame_h)

        cx = x + w // 2   # 水平中点
        src_y = y + int(h * 0.35)
        tgt_y = y + int(h * 0.72)

        sub_c = self.style["subtitle"]
        bg_colour = sub_c["OutlineColour"]
        src_colour = sub_c["PrimaryColour"]
        tgt_colour = sub_c["SecondaryColour"]

        at = self._anim_tag(anim, cx, src_y)

        events = []
        # 背景矩形
        events.append(self._dialogue(0, t0, t1, "Draw", "", [
            self._draw_rect(x, y, w, h, bg_colour)
        ]))
        # 原文（上方）
        fs_src = self._fs(46)
        events.append(self._dialogue(1, t0, t1, "Subtitle", "", [
            f"\\pos({cx},{src_y})\\an5\\fs{fs_src}\\c{src_colour}\\bord0\\shad0{at}",
            self._escape_text(original)
        ]))
        # 译文（下方）
        fs_tgt = self._fs(32)
        events.append(self._dialogue(1, t0, t1, "Subtitle", "", [
            f"\\pos({cx},{tgt_y})\\an5\\fs{fs_tgt}\\c{tgt_colour}\\bord0\\shad0{at}",
            self._escape_text(translated)
        ]))
        return events

    # ──────────────────────────────────────────────────────────────
    # Wordbox Events
    # ──────────────────────────────────────────────────────────────

    def _wordbox_events(
        self, t0: str, t1: str,
        key_words: List[Dict],
        lay: Dict, anim: str,
    ) -> List[str]:
        x = int(lay["x_pct"] * self.frame_w)
        y = int(lay["y_pct"] * self.frame_h)
        w = int(lay["w_pct"] * self.frame_w)
        h = int(lay["h_pct"] * self.frame_h)

        wb = self.style["wordbox"]
        bg_col    = wb["bg_colour"]
        word_col  = wb["word_colour"]
        phon_col  = wb["phonetic_colour"]
        trans_col = wb["trans_colour"]
        hdr_col   = wb["header_colour"]

        pad_x = max(8, int(w * 0.04))
        pad_y = max(8, int(h * 0.02))

        fs_hdr  = self._fs(20)
        fs_word = self._fs(30)
        fs_phon = self._fs(20)
        fs_tran = self._fs(22)

        lh_hdr  = fs_hdr + 10
        lh_word = fs_word + 8
        lh_phon = fs_phon + 10

        at = self._anim_tag(anim, x + pad_x, y + pad_y)

        events = []
        # 背景矩形
        events.append(self._dialogue(0, t0, t1, "Draw", "", [
            self._draw_rect(x, y, w, h, bg_col)
        ]))
        # 标题
        hdr_y = y + pad_y
        events.append(self._dialogue(2, t0, t1, "Word", "", [
            f"\\pos({x+pad_x},{hdr_y})\\an7\\fs{fs_hdr}\\c{hdr_col}{at}",
            "KEY WORDS"
        ]))

        cur_y = hdr_y + lh_hdr + 4
        for word_item in key_words:
            word  = word_item.get("word", "")
            phon  = word_item.get("phonetic", "")
            trans = word_item.get("translation", "")

            if cur_y + lh_word + lh_phon > y + h - pad_y:
                break  # 超出框高度则截断

            # 单词（左对齐，加粗）
            events.append(self._dialogue(2, t0, t1, "Word", "", [
                f"\\pos({x+pad_x},{cur_y})\\an7\\fs{fs_word}\\c{word_col}\\b1{at}",
                self._escape_text(word)
            ]))
            # 释义（右对齐）
            if trans:
                events.append(self._dialogue(2, t0, t1, "Word", "", [
                    f"\\pos({x+w-pad_x},{cur_y})\\an9\\fs{fs_tran}\\c{trans_col}{at}",
                    self._escape_text(trans)
                ]))
            cur_y += lh_word

            # 音标（左对齐，小字）
            if phon:
                events.append(self._dialogue(2, t0, t1, "Word", "", [
                    f"\\pos({x+pad_x},{cur_y})\\an7\\fs{fs_phon}\\c{phon_col}{at}",
                    self._escape_text(phon)
                ]))
            cur_y += lh_phon + 4  # 小间距

        return events

    # ──────────────────────────────────────────────────────────────
    # Exprbox Events
    # ──────────────────────────────────────────────────────────────

    def _exprbox_events(
        self, t0: str, t1: str,
        expressions: List[Dict],
        lay: Dict, anim: str,
    ) -> List[str]:
        x = int(lay["x_pct"] * self.frame_w)
        y = int(lay["y_pct"] * self.frame_h)
        w = int(lay["w_pct"] * self.frame_w)
        h = int(lay["h_pct"] * self.frame_h)

        eb = self.style["exprbox"]
        bg_col  = eb["bg_colour"]
        en_col  = eb["en_colour"]
        cn_col  = eb["cn_colour"]
        hdr_col = eb["header_colour"]

        pad_x = max(8, int(w * 0.04))
        pad_y = max(8, int(h * 0.02))

        fs_hdr = self._fs(20)
        fs_en  = self._fs(26)
        fs_cn  = self._fs(20)

        lh_hdr = fs_hdr + 10
        lh_en  = fs_en + 6
        lh_cn  = fs_cn + 10

        at = self._anim_tag(anim, x + pad_x, y + pad_y)

        events = []
        # 背景矩形
        events.append(self._dialogue(0, t0, t1, "Draw", "", [
            self._draw_rect(x, y, w, h, bg_col)
        ]))
        # 标题
        hdr_y = y + pad_y
        events.append(self._dialogue(2, t0, t1, "Expr", "", [
            f"\\pos({x+pad_x},{hdr_y})\\an7\\fs{fs_hdr}\\c{hdr_col}{at}",
            "EXPRESSIONS"
        ]))

        cur_y = hdr_y + lh_hdr + 4
        for expr in expressions:
            english = expr.get("english", "")
            chinese = expr.get("chinese", expr.get("translation", ""))

            if cur_y + lh_en + lh_cn > y + h - pad_y:
                break

            # 英文表达
            events.append(self._dialogue(2, t0, t1, "Expr", "", [
                f"\\pos({x+pad_x},{cur_y})\\an7\\fs{fs_en}\\c{en_col}\\b1{at}",
                self._escape_text(english)
            ]))
            cur_y += lh_en

            # 中文翻译
            if chinese:
                events.append(self._dialogue(2, t0, t1, "Expr", "", [
                    f"\\pos({x+pad_x},{cur_y})\\an7\\fs{fs_cn}\\c{cn_col}{at}",
                    self._escape_text(chinese)
                ]))
            cur_y += lh_cn + 6

        return events

    # ──────────────────────────────────────────────────────────────
    # Helper methods
    # ──────────────────────────────────────────────────────────────

    def _fs(self, base_px: int) -> int:
        """缩放字体大小（720p 时乘以 0.667）"""
        return max(12, int(base_px * self._font_scale))

    @staticmethod
    def _fmt_time(secs: float) -> str:
        """浮点秒数转 ASS 时间格式 H:MM:SS.cc"""
        secs = max(0.0, secs)
        h  = int(secs // 3600)
        m  = int((secs % 3600) // 60)
        s  = int(secs % 60)
        cs = int(round((secs - int(secs)) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _escape_text(text: str) -> str:
        """转义 ASS 文本中的特殊字符"""
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    def _draw_rect(self, x: int, y: int, w: int, h: int, colour: str) -> str:
        """生成 ASS Drawing 背景矩形（\\p1 模式）"""
        return f"{{\\an7\\p1\\c{colour}\\pos({x},{y})}}" \
               f"m 0 0 l {w} 0 {w} {h} 0 {h}"

    def _anim_tag(self, anim: str, ref_x: int, ref_y: int) -> str:
        """根据动画类型生成 ASS Override Tag"""
        if anim == "fade":
            return r"\fad(200,150)"
        elif anim == "slide_up":
            # 从下 20px 向上滑入
            y_end   = ref_y
            y_start = ref_y + self._fs(20)
            return f"\\move({ref_x},{y_start},{ref_x},{y_end},0,300)"
        elif anim == "pop":
            return r"\fad(80,80)\t(0,150,\fscx110\fscy110)\t(150,250,\fscx100\fscy100)"
        else:
            # typewriter 或未知 → 用 fade
            return r"\fad(200,150)"

    def _dialogue(
        self,
        layer: int, t0: str, t1: str,
        style: str, name: str,
        parts: List[str],
    ) -> str:
        """生成一行 ASS Dialogue 事件"""
        tags = ""
        text = ""
        if len(parts) == 1:
            # 纯 drawing 命令，无文字标签
            text = parts[0]
        elif len(parts) == 2:
            tags = "{" + parts[0] + "}"
            text = parts[1]
        else:
            text = "".join(parts)

        return (
            f"Dialogue: {layer},{t0},{t1},{style},{name},"
            f"0,0,0,,{tags}{text}"
        )

    def _merge_layout(self, user_layout: Dict) -> Dict:
        """将用户布局（可能缺少某些框）与默认布局合并"""
        merged = {}
        for key, default in self.DEFAULT_LAYOUT.items():
            if key in user_layout:
                merged[key] = {**default, **user_layout[key]}
            else:
                merged[key] = dict(default)
        return merged
