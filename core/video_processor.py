"""
视频处理器 — 纯 FFmpeg subprocess 流水线
彻底移除 MoviePy，使用 FFmpeg 进行：
  - 片段提取（-c copy，毫秒级）
  - 变速保音调（setpts + atempo）
  - ASS 字幕烧录（-vf ass=）
  - 片段拼接（concat filter）
  - 水印叠加（drawtext）
"""

import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Callable

import config

# ffmpeg-full includes libass (for ASS subtitle burning); fallback to plain ffmpeg
_FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"
from ass_generator import ASSGenerator
from ass_styles import DEFAULT_STYLE_ID
from html_renderer import HTMLRenderer

# 默认布局（0-1 小数）
_DEFAULT_LAYOUT = {
    "subtitle": {"x_pct": 0.05, "y_pct": 0.76, "w_pct": 0.90, "h_pct": 0.14, "font_scale": 1.0},
    "wordbox":  {"x_pct": 0.75, "y_pct": 0.005, "w_pct": 0.245, "h_pct": 0.65, "font_scale": 1.0},
    "exprbox":  {"x_pct": 0.005, "y_pct": 0.005, "w_pct": 0.245, "h_pct": 0.55, "font_scale": 1.0},
}


class VideoProcessor:

    def __init__(self):
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def process_full_video(
        self,
        video_path: str,
        sentences_data: List[Dict],
        output_path: str,
        segments_info: Optional[List[Dict]] = None,
        progress_callback: Optional[Callable] = None,
        style_id: str = DEFAULT_STYLE_ID,
        layout: Optional[Dict] = None,
        parts_config: Optional[List[Dict]] = None,
        animation: Optional[str] = None,
        cancelled_fn: Optional[Callable] = None,
        # 旧式兼容参数（style dict 已废弃，忽略）
        style: Optional[Dict] = None,
    ) -> dict:
        """
        处理完整视频，输出学习版 MP4。

        当 style 不为 None 时，使用 html_renderer.py（Chrome Headless PNG）合成 3 个框，
        与布局编辑器预览完全一致。style 为 None 时降级到 ASS 字幕（CLI 批处理兼容）。

        parts_config 格式：
          [
            {"repeat":1, "slow":False, "speed":1.0,
             "show_subtitle":False, "show_wordbox":False, "show_exprbox":False},
            {"repeat":2, "slow":True,  "speed":0.75,
             "show_subtitle":True,  "show_wordbox":True,  "show_exprbox":True},
          ]

        layout 格式（嵌套百分比 0-1）：
          {
            "subtitle": {"x_pct":0.05, "y_pct":0.76, "w_pct":0.90, "h_pct":0.14, "font_scale":1.0},
            "wordbox":  {"x_pct":0.75, "y_pct":0.005,"w_pct":0.245,"h_pct":0.65, "font_scale":1.0},
            "exprbox":  {"x_pct":0.005,"y_pct":0.005,"w_pct":0.245,"h_pct":0.55, "font_scale":1.0},
          }

        progress_callback(phase, data):
            phase='clips': data={'current': i, 'total': n, 'pct': 0-100}
            phase='write':  data={'pct': 0-100}
        """
        # ── 初始化 ──
        base_path        = os.path.splitext(output_path)[0]
        full_output_path = f"{base_path}_full.mp4"

        resolution = config.VIDEO_RESOLUTION or "1080p"
        frame_w    = 1920 if resolution == "1080p" else 1280
        frame_h    = 1080 if resolution == "1080p" else 720

        ass_gen    = ASSGenerator(style_id, resolution)
        segs       = segments_info or []

        # 决定使用 PNG overlay 模式还是 ASS 降级模式
        use_png_overlay = bool(style)
        renderer = HTMLRenderer() if use_png_overlay else None

        # 合并 layout 默认值
        merged_layout = {}
        for key, defaults in _DEFAULT_LAYOUT.items():
            if layout and key in layout:
                merged_layout[key] = {**defaults, **layout[key]}
            else:
                merged_layout[key] = dict(defaults)

        # 若未提供 parts_config，从旧式 config 常量构建（向后兼容）
        if not parts_config:
            parts_config = self._legacy_parts_config()

        # 计算总 clip 数（用于进度）
        total_clips = len(sentences_data) * sum(p.get("repeat", 1) for p in parts_config)
        done_clips  = 0

        # 临时目录
        job_tmp = Path(config.TEMP_DIR) / f"vp_{uuid.uuid4().hex[:8]}"
        job_tmp.mkdir(parents=True, exist_ok=True)
        all_clip_paths = []  # 最终拼接用的有序 clip 路径列表

        print(f"[VideoProcessor] 🎬 开始处理 {len(sentences_data)} 句话，"
              f"{len(parts_config)} 个 Part，共约 {total_clips} 个片段，"
              f"渲染模式={'PNG overlay' if use_png_overlay else 'ASS字幕'}")

        try:
            for i, sent in enumerate(sentences_data):
                if cancelled_fn and cancelled_fn():
                    print("⚠️ 任务已取消")
                    return {"cancelled": True}

                seg      = segs[i] if i < len(segs) else {}
                start    = seg.get("start", 0.0)
                end      = seg.get("end",   start + 5.0)
                next_start = segs[i + 1].get("start", end) if i + 1 < len(segs) else end

                # ── 提前为本句生成 PNG（每句只生成一次，多个 Part 复用）──
                sent_pngs: Dict[str, tuple] = {}  # key → (png_path, x_px, y_px)

                if use_png_overlay:
                    # 判断整个句子里哪些框至少在一个 Part 中显示
                    needs_sub = any(p.get("show_subtitle", False) for p in parts_config)
                    needs_wb  = any(p.get("show_wordbox",  False) for p in parts_config)
                    needs_eb  = any(p.get("show_exprbox",  False) for p in parts_config)

                    src_text  = sent.get("original_text", "")
                    tgt_text  = sent.get("chinese_translation", sent.get("translated_text", ""))
                    words     = sent.get("key_words", [])
                    exprs     = sent.get("useful_expressions", [])

                    if needs_sub and 'subtitle' in merged_layout:
                        lay = merged_layout['subtitle']
                        w_px = max(80, int(lay['w_pct'] * frame_w))
                        h_px = max(40, int(lay['h_pct'] * frame_h))
                        x_px = int(lay['x_pct'] * frame_w)
                        y_px = int(lay['y_pct'] * frame_h)
                        sub_style = {**style, 'font_size_scale': lay.get('font_scale', 1.0)}
                        png_path  = str(job_tmp / f"s{i:04d}_sub.png")
                        ok = renderer.render_subtitle(src_text, tgt_text, w_px, h_px, png_path, style=sub_style)
                        if ok:
                            sent_pngs['subtitle'] = (png_path, x_px, y_px)

                    if needs_wb and 'wordbox' in merged_layout and words:
                        lay = merged_layout['wordbox']
                        w_px = max(80, int(lay['w_pct'] * frame_w))
                        h_px = max(40, int(lay['h_pct'] * frame_h))
                        x_px = int(lay['x_pct'] * frame_w)
                        y_px = int(lay['y_pct'] * frame_h)
                        wb_style = {**style, 'font_size_scale': lay.get('font_scale', 1.0)}
                        png_path = str(job_tmp / f"s{i:04d}_wb.png")
                        ok = renderer.render_wordbox(words, w_px, h_px, png_path, style=wb_style)
                        if ok:
                            sent_pngs['wordbox'] = (png_path, x_px, y_px)

                    if needs_eb and 'exprbox' in merged_layout and exprs:
                        lay = merged_layout['exprbox']
                        w_px = max(80, int(lay['w_pct'] * frame_w))
                        h_px = max(40, int(lay['h_pct'] * frame_h))
                        x_px = int(lay['x_pct'] * frame_w)
                        y_px = int(lay['y_pct'] * frame_h)
                        eb_style = {**style, 'font_size_scale': lay.get('font_scale', 1.0)}
                        png_path = str(job_tmp / f"s{i:04d}_eb.png")
                        ok = renderer.render_expressionbox(exprs, w_px, h_px, png_path, style=eb_style)
                        if ok:
                            sent_pngs['exprbox'] = (png_path, x_px, y_px)

                # ASS 模式缓存（降级路径）
                ass_cache: Dict[tuple, str] = {}

                for part in parts_config:
                    if cancelled_fn and cancelled_fn():
                        return {"cancelled": True}

                    speed     = float(part.get("speed", 1.0))
                    # slow 字段兼容旧格式；新格式直接用 speed < 1.0 判断
                    is_slow   = (speed != 1.0) or part.get("slow", False)
                    if part.get("slow", False) and speed == 1.0:
                        speed = float(getattr(config, "SPEED_SLOW", 0.75))
                    repeat    = max(1, int(part.get("repeat", 1)))
                    show_sub  = part.get("show_subtitle", False)
                    show_wb   = part.get("show_wordbox", False)
                    show_eb   = part.get("show_exprbox", False)

                    # Part 使用的时间段
                    seg_end  = end if is_slow else next_start
                    raw_dur  = seg_end - start

                    # ── 1. 提取原始片段（-c copy 快速模式）──
                    raw_path = str(job_tmp / f"s{i:04d}_p{parts_config.index(part)}_raw.mp4")
                    self._extract_segment(video_path, start, seg_end, raw_path)

                    # ── 2. 变速（如需）──
                    if is_slow:
                        slow_path = str(job_tmp / f"s{i:04d}_p{parts_config.index(part)}_slow.mp4")
                        self._apply_slowdown(raw_path, speed, slow_path)
                        base_clip = slow_path
                        clip_dur  = raw_dur / speed
                    else:
                        base_clip = raw_path
                        clip_dur  = raw_dur

                    need_overlay = show_sub or show_wb or show_eb

                    if use_png_overlay:
                        # ── 3a. PNG overlay 模式 ──
                        overlays = []
                        if show_sub and 'subtitle' in sent_pngs:
                            overlays.append(sent_pngs['subtitle'])
                        if show_wb and 'wordbox' in sent_pngs:
                            overlays.append(sent_pngs['wordbox'])
                        if show_eb and 'exprbox' in sent_pngs:
                            overlays.append(sent_pngs['exprbox'])

                        if overlays:
                            burned_path = str(job_tmp / f"s{i:04d}_p{parts_config.index(part)}_burned.mp4")
                            self._render_with_overlays(base_clip, overlays, burned_path)
                            final_clip = burned_path
                        else:
                            final_clip = base_clip
                    else:
                        # ── 3b. ASS 降级模式（style=None 时，CLI 批处理）──
                        show_key = (show_sub, show_wb, show_eb)

                        if need_overlay and show_key not in ass_cache:
                            ass_content = ass_gen.generate(
                                duration         = clip_dur,
                                original_text    = sent.get("original_text", ""),
                                translated_text  = sent.get("chinese_translation",
                                                   sent.get("translated_text", "")),
                                key_words        = sent.get("key_words", []),
                                expressions      = sent.get("useful_expressions", []),
                                layout           = layout,
                                show_subtitle    = show_sub,
                                show_wordbox     = show_wb,
                                show_exprbox     = show_eb,
                                animation        = animation,
                            )
                            ass_path = str(job_tmp / f"s{i:04d}_p{parts_config.index(part)}.ass")
                            ass_gen.write_to_file(ass_content, ass_path)
                            ass_cache[show_key] = ass_path

                        if need_overlay:
                            burned_path = str(job_tmp / f"s{i:04d}_p{parts_config.index(part)}_burned.mp4")
                            self._burn_ass(base_clip, ass_cache[show_key], burned_path)
                            final_clip = burned_path
                        else:
                            final_clip = base_clip

                    # ── 4. 按 repeat 次数加入拼接列表 ──
                    for _ in range(repeat):
                        all_clip_paths.append(final_clip)

                    done_clips += repeat
                    if progress_callback:
                        pct = int(done_clips / total_clips * 100)
                        progress_callback("clips", {
                            "current": i + 1, "total": len(sentences_data), "pct": pct
                        })

                print(f"  ✓ 句子 {i+1}/{len(sentences_data)}")

            if cancelled_fn and cancelled_fn():
                return {"cancelled": True}

            # ── 6. 拼接所有片段 + 水印 ──
            print(f"[VideoProcessor] 🔗 拼接 {len(all_clip_paths)} 个片段...")
            if progress_callback:
                progress_callback("write", {"pct": 0})

            self._concat_with_watermark(
                all_clip_paths, full_output_path, frame_w, frame_h,
                progress_callback
            )

            if progress_callback:
                progress_callback("write", {"pct": 100})

            print("[VideoProcessor] ✅ 视频处理完成")
            return {"full": full_output_path}

        finally:
            # 清理临时文件
            self._cleanup(job_tmp)

    # ──────────────────────────────────────────────────────────────
    # FFmpeg 命令
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_segment(src: str, start: float, end: float, out: str) -> None:
        """提取片段（-c copy，毫秒级，无重编码）"""
        duration = max(0.1, end - start)
        subprocess.run([
            _FFMPEG, "-y",
            "-ss", f"{start:.3f}",
            "-t",  f"{duration:.3f}",
            "-i",  src,
            "-c",  "copy",
            "-avoid_negative_ts", "make_zero",
            out,
        ], check=True, capture_output=True)

    @staticmethod
    def _apply_slowdown(src: str, speed: float, out: str) -> None:
        """变速保音调（setpts + atempo 链式）"""
        atempo = VideoProcessor._build_atempo_chain(speed)
        pts    = f"{1.0/speed:.6f}*PTS"
        subprocess.run([
            _FFMPEG, "-y", "-i", src,
            "-filter_complex",
            f"[0:v]setpts={pts}[v];[0:a]{atempo}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100",
            out,
        ], check=True, capture_output=True)

    @staticmethod
    def _burn_ass(src: str, ass_path: str, out: str) -> None:
        """将 ASS 字幕烧录到视频"""
        # 转换为绝对路径，避免相对路径问题
        abs_path = os.path.abspath(ass_path)
        # FFmpeg filter 字符串转义：反斜杠 → \\，冒号 → \:
        # 注意：subprocess 不走 shell，所以不需要 shell 级别的引号
        safe_ass = abs_path.replace("\\", "/").replace(":", "\\:")
        result = subprocess.run([
            _FFMPEG, "-y", "-i", src,
            "-vf", f"ass=filename={safe_ass}",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "copy",
            out,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[FFmpeg ASS] stderr: {result.stderr[-2000:]}")
            raise subprocess.CalledProcessError(result.returncode, result.args)

    @staticmethod
    def _render_with_overlays(src: str, overlays: list, out: str) -> None:
        """
        将多张 PNG 叠加到视频上（与布局编辑器预览一致的 Chrome Headless 渲染）。
        overlays: [(png_path, x_px, y_px), ...]
        """
        if not overlays:
            import shutil
            shutil.copy2(src, out)
            return

        cmd = [_FFMPEG, "-y", "-i", src]
        for png_path, _x, _y in overlays:
            cmd += ["-i", png_path]

        filter_parts = []
        prev = "0:v"
        for idx, (_png, x, y) in enumerate(overlays):
            nxt = f"v{idx}"
            filter_parts.append(f"[{prev}][{idx+1}:v]overlay={x}:{y}[{nxt}]")
            prev = nxt

        cmd += [
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{prev}]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "copy", out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[FFmpeg overlay] stderr: {result.stderr[-2000:]}")
            raise subprocess.CalledProcessError(result.returncode, result.args)


        """构建 atempo 过滤链（atempo 范围 0.5–2.0，链式处理极端速度）"""
        filters = []
        s = speed
        # 低速链式（< 0.5 每次乘以 0.5）
        while s < 0.5:
            filters.append("atempo=0.5")
            s /= 0.5
        # 高速链式（> 2.0 每次乘以 2.0）
        while s > 2.0:
            filters.append("atempo=2.0")
            s /= 2.0
        filters.append(f"atempo={s:.6f}")
        return ",".join(filters)

    def _concat_with_watermark(
        self,
        clip_paths: List[str],
        out: str,
        frame_w: int,
        frame_h: int,
        progress_callback: Optional[Callable],
    ) -> None:
        """使用 concat filter 拼接所有片段并叠加水印，一次 pass 完成"""
        n = len(clip_paths)
        inputs = []
        for p in clip_paths:
            inputs += ["-i", p]

        # 构建 filter_complex
        in_refs   = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        concat_f  = f"{in_refs}concat=n={n}:v=1:a=1[vc][aout]"

        # 水印（居中 -30° 半透灰字）
        wm_text   = "Made By LinguaLearn"
        wm_size   = max(16, int(min(frame_w, frame_h) * 0.04))
        wm_filter = (
            f"[vc]drawtext="
            f"text='{wm_text}':"
            f"fontsize={wm_size}:"
            f"fontcolor=gray@0.15:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2"
            f"[vout]"
        )
        filter_complex = f"{concat_f};{wm_filter}"

        # 文件大小进度线程
        _stop = threading.Event()
        if progress_callback:
            def _size_progress():
                bitrate_kbps = 2500 if config.VIDEO_RESOLUTION == "720p" else 4000
                # 粗估总时长（每个 clip 约 3 秒）
                est_dur = n * 3.0
                expected = max(1, est_dur * bitrate_kbps * 1000 / 8)
                last = 0
                while not _stop.is_set():
                    try:
                        if os.path.exists(out):
                            sz  = os.path.getsize(out)
                            pct = min(95, int(sz / expected * 100))
                            if pct > last:
                                last = pct
                                progress_callback("write", {"pct": pct})
                    except Exception:
                        pass
                    _stop.wait(timeout=2.0)
            t = threading.Thread(target=_size_progress, daemon=True)
            t.start()

        try:
            subprocess.run([
                _FFPMEG, "-y", *inputs,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-ar", "44100",
                out,
            ], check=True)
        finally:
            _stop.set()
            if progress_callback:
                t.join(timeout=3)

    # ──────────────────────────────────────────────────────────────
    # 向后兼容
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _legacy_parts_config() -> List[Dict]:
        """从旧式 config 常量构建 parts_config（向后兼容）"""
        parts = []
        if getattr(config, "PART1_REPEAT_COUNT", 0) > 0:
            parts.append({
                "repeat": config.PART1_REPEAT_COUNT,
                "slow": False, "speed": 1.0,
                "show_subtitle": getattr(config, "PART1_SHOW_SUBTITLE", False),
                "show_wordbox":  getattr(config, "PART1_SHOW_WORD_BOX", False),
                "show_exprbox":  getattr(config, "PART1_SHOW_EXPRESSION_BOX", False),
            })
        if getattr(config, "PART2_REPEAT_COUNT", 0) > 0:
            parts.append({
                "repeat": config.PART2_REPEAT_COUNT,
                "slow": True, "speed": getattr(config, "SPEED_SLOW", 0.75),
                "show_subtitle": getattr(config, "PART2_SHOW_SUBTITLE", True),
                "show_wordbox":  getattr(config, "PART2_SHOW_WORD_BOX", True),
                "show_exprbox":  getattr(config, "PART2_SHOW_EXPRESSION_BOX", True),
            })
        if getattr(config, "PART3_REPEAT_COUNT", 0) > 0:
            parts.append({
                "repeat": config.PART3_REPEAT_COUNT,
                "slow": False, "speed": 1.0,
                "show_subtitle": getattr(config, "PART3_SHOW_SUBTITLE", True),
                "show_wordbox":  getattr(config, "PART3_SHOW_WORD_BOX", True),
                "show_exprbox":  getattr(config, "PART3_SHOW_EXPRESSION_BOX", True),
            })
        if not parts:
            # 最终兜底：2 个 Part，1x 原速 + 2x 慢速带字幕
            parts = [
                {"repeat": 1, "slow": False, "speed": 1.0,
                 "show_subtitle": False, "show_wordbox": False, "show_exprbox": False},
                {"repeat": 2, "slow": True,  "speed": 0.75,
                 "show_subtitle": True,  "show_wordbox": True,  "show_exprbox": True},
            ]
        return parts

    @staticmethod
    def _cleanup(tmp_dir: Path) -> None:
        """删除临时目录"""


        try:
            import shutil
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        except Exception:
            pass
