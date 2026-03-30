"""
视频处理器 — 纯 FFmpeg subprocess 流水线
彻底移除 MoviePy，使用 FFmpeg 进行：
  - 片段提取（-c copy，毫秒级）
  - 变速保音调（setpts + atempo）
  - ASS 字幕烧录（-vf ass=）
  - 片段拼接（concat filter）
  - 水印叠加（drawtext）

渲染模式：
  1. timeline_json 模式（新）：使用 konva-node (Node.js sidecar) 渲染 PNG，与前端 vue-konva 同源
  2. style dict 模式（旧）：使用 html_renderer.py (Chrome Headless) 渲染 PNG
  3. ASS 降级模式（CLI 批处理）：style=None 时使用 ASS 字幕
"""

import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple

import config

# ffmpeg-full includes libass (for ASS subtitle burning); fallback to plain ffmpeg
_FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"
_FFPROBE = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffprobe") else "ffprobe"
from ass_generator import ASSGenerator
from ass_styles import DEFAULT_STYLE_ID
from html_renderer import HTMLRenderer
from konva_renderer import KonvaRenderer

# 默认布局（0-1 小数）
_DEFAULT_LAYOUT = {
    "subtitle": {"x_pct": 0.011, "y_pct": 0.704, "w_pct": 0.961, "h_pct": 0.346, "font_scale": 1.15},
    "wordbox":  {"x_pct": 0.761, "y_pct": 0.008, "w_pct": 0.222, "h_pct": 0.689, "font_scale": 0.90},
    "exprbox":  {"x_pct": 0.002, "y_pct": 0.005, "w_pct": 0.275, "h_pct": 0.483, "font_scale": 1.00},
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
        # 旧式兼容参数
        style: Optional[Dict] = None,
        # 新 Timeline JSON 模式（优先级最高）
        timeline_json: Optional[Dict] = None,
        # 会员能力控制
        membership_tier: str = "free",
        forced_watermark: Optional[Dict] = None,
    ) -> dict:
        """
        处理完整视频，输出学习版 MP4。

        渲染模式优先级：
          1. timeline_json 不为 None → konva-node 渲染（同源）
          2. style 不为 None → html_renderer PNG 渲染（Chrome Headless）
          3. 都为 None → ASS 字幕降级（CLI 批处理）

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

        # Timeline JSON 模式可覆盖分辨率
        if timeline_json:
            tl_res = timeline_json.get("resolution", {})
            if tl_res.get("width"):
                frame_w = tl_res["width"]
                frame_h = tl_res["height"]

        # Ensure the rendered video geometry matches editor canvas resolution.
        src_w, src_h = self._probe_video_resolution(video_path)
        need_rescale = (src_w is None or src_h is None or src_w != frame_w or src_h != frame_h)
        if need_rescale:
            print(f"[VideoProcessor] 📐 将片段统一到编辑器分辨率: {frame_w}x{frame_h} (源视频={src_w}x{src_h})")
        else:
            print(f"[VideoProcessor] 📐 源视频分辨率已匹配编辑器: {frame_w}x{frame_h}")

        ass_gen    = ASSGenerator(style_id, resolution)
        segs       = segments_info or []

        # 决定渲染模式
        use_konva = bool(timeline_json)
        use_png_overlay = bool(style) and not use_konva
        renderer = None
        konva_renderer = None

        if use_konva:
            konva_renderer = KonvaRenderer()
        elif use_png_overlay:
            renderer = HTMLRenderer()

        # ── Timeline JSON 模式：转换 parts 为 parts_config 格式 ──
        if use_konva and timeline_json:
            tl_parts = timeline_json.get("parts", [])
            tl_elements = timeline_json.get("elements", [])
            # 构建 element type lookup
            elem_type_map = {e["id"]: e["type"] for e in tl_elements}

            if not parts_config:
                parts_config = []
                for tp in tl_parts:
                    vis = tp.get("elementVisibility", {})
                    show_sub = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "subtitle")
                    show_wb  = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "wordbox")
                    show_eb  = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "exprbox")
                    speed = float(tp.get("speed", 1.0))
                    parts_config.append({
                        "repeat": tp.get("repeat", 1),
                        "slow": speed != 1.0,
                        "speed": speed,
                        "show_subtitle": show_sub,
                        "show_wordbox": show_wb,
                        "show_exprbox": show_eb,
                        # Store timeline part info for element visibility lookup
                        "_tl_part_id": tp.get("id"),
                        "_tl_visibility": vis,
                    })

        # 合并 layout 默认值（仅非 konva 模式使用）
        merged_layout = {}
        if not use_konva:
            for key, defaults in _DEFAULT_LAYOUT.items():
                if layout and key in layout:
                    merged_layout[key] = {**defaults, **layout[key]}
                else:
                    merged_layout[key] = dict(defaults)

        # 若未提供 parts_config，从旧式 config 常量构建（向后兼容）
        if not parts_config:
            parts_config = self._legacy_parts_config()

        # one-sentence-one-part 模式：每个句子只绑定同索引 part，而不是句子×part 全组合
        sentence_part_mode = False
        if use_konva and timeline_json:
            bind_raw = str(
                timeline_json.get("partBinding")
                or timeline_json.get("part_binding")
                or timeline_json.get("sentencePartMode")
                or ""
            ).strip().lower()
            if bind_raw in {"sentence", "per_sentence", "per-sentence", "one_to_one", "1:1", "one-to-one"}:
                sentence_part_mode = True
            else:
                # 自动判定：part 数量与句子数量一致且 repeat 全为 1，默认按一一绑定处理
                if len(parts_config) == len(sentences_data) and len(parts_config) > 0:
                    all_repeat_once = all(max(1, int(p.get("repeat", 1))) == 1 for p in parts_config)
                    if all_repeat_once:
                        sentence_part_mode = True

        # Part 时间切片策略（固定规则）：
        # - part1：句子结束时间取下一句 start（保证连贯）
        # - 其余 part：句子结束时间取当前句 end（保证精确）

        # 计算总 clip 数（用于进度）
        if sentence_part_mode:
            total_clips = sum(
                max(1, int(parts_config[i].get("repeat", 1)))
                for i in range(min(len(parts_config), len(sentences_data)))
            )
        else:
            total_clips = len(sentences_data) * sum(p.get("repeat", 1) for p in parts_config)
        done_clips  = 0
        timeline_cursor = 0.0
        sentence_timing: List[Dict] = []

        # 临时目录
        job_tmp = Path(config.TEMP_DIR) / f"vp_{uuid.uuid4().hex[:8]}"
        job_tmp.mkdir(parents=True, exist_ok=True)
        all_clip_paths = []  # 最终拼接用的有序 clip 路径列表

        mode_name = 'Konva (konva-node)' if use_konva else ('PNG overlay' if use_png_overlay else 'ASS字幕')
        print(f"[VideoProcessor] 🎬 开始处理 {len(sentences_data)} 句话，"
              f"{len(parts_config)} 个 Part，共约 {total_clips} 个片段，"
              f"渲染模式={mode_name}，sentence_part_mode={sentence_part_mode}")

        try:
            # ── Konva 模式：批量预渲染所有句子的 PNG（一次 Node.js 调用）──
            konva_pngs: Dict = {}
            if use_konva and konva_renderer:
                print("[VideoProcessor] 🎨 正在用 konva-node 批量渲染 PNG...")
                konva_pngs = konva_renderer.render_all_sentences(
                    timeline=timeline_json,
                    sentences_data=sentences_data,
                    output_dir=str(job_tmp / "konva"),
                    resolution={"width": frame_w, "height": frame_h},
                )
                total_pngs = 0
                for by_sentence in konva_pngs.values():
                    if by_sentence and all(isinstance(v, tuple) for v in by_sentence.values()):
                        total_pngs += len(by_sentence)  # legacy
                    else:
                        total_pngs += sum(len(v) for v in by_sentence.values() if isinstance(v, dict))
                print(f"[VideoProcessor] ✅ konva-node 渲染完成，共 {total_pngs} 个 PNG")

            for i, sent in enumerate(sentences_data):
                if cancelled_fn and cancelled_fn():
                    print("⚠️ 任务已取消")
                    return {"cancelled": True}

                seg      = segs[i] if i < len(segs) else {}
                start    = float(seg.get("start", 0.0))
                end      = float(seg.get("end",   start + 5.0))
                next_start = float(segs[i + 1].get("start", end)) if i + 1 < len(segs) else end

                # 边界修正：防止分段异常造成重叠或负时长
                if i > 0 and i - 1 < len(segs):
                    prev_end = float(segs[i - 1].get("end", start))
                    if start < prev_end:
                        start = prev_end
                if next_start < end:
                    end = next_start
                if end <= start:
                    end = start + 0.1

                # ── 提前为本句生成 PNG（每句只生成一次，多个 Part 复用）──
                # Konva new format: {part_id: {element_id: (png_path, x_px, y_px)}}
                # Konva legacy format: {element_id: (png_path, x_px, y_px)}
                sent_pngs: Dict = {}

                if use_konva:
                    # Konva 模式：从预渲染结果获取 PNG
                    if i in konva_pngs:
                        sent_pngs = konva_pngs[i] or {}
                elif use_png_overlay:
                    # 旧 HTML 渲染模式
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
                seg_video_start = timeline_cursor
                first_overlay_start = None

                if sentence_part_mode:
                    if i >= len(parts_config):
                        print(f"[VideoProcessor] ⚠️ 句子 {i+1} 无对应 Part，跳过")
                        continue
                    part_iter = [(i, parts_config[i])]
                else:
                    part_iter = list(enumerate(parts_config))

                for pidx, part in part_iter:
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

                    # Part 使用的时间段：
                    # part1 用下一句 start，其余 part 用当前句 end
                    is_part1 = (pidx == 0)
                    seg_end = next_start if (is_part1 and i + 1 < len(segs)) else end
                    if seg_end <= start:
                        seg_end = end
                    raw_dur = max(0.1, seg_end - start)

                    # ── 1. 提取原始片段（-c copy 快速模式）──
                    raw_path = str(job_tmp / f"s{i:04d}_p{pidx}_raw.mp4")
                    self._extract_segment(video_path, start, seg_end, raw_path)

                    # ── 2. 变速（如需）──
                    if is_slow:
                        slow_path = str(job_tmp / f"s{i:04d}_p{pidx}_slow.mp4")
                        self._apply_slowdown(raw_path, speed, slow_path)
                        base_clip = slow_path
                        clip_dur  = raw_dur / speed
                    else:
                        base_clip = raw_path
                        clip_dur  = raw_dur

                    need_overlay = show_sub or show_wb or show_eb

                    if use_konva:
                        # ── 3a. Konva PNG overlay 模式 ──
                        # Use element-level visibility from timeline parts
                        tl_vis = part.get("_tl_visibility", {})
                        overlays = []

                        # Backward compatibility: legacy flat structure
                        is_legacy_flat = bool(sent_pngs) and all(
                            isinstance(v, tuple) for v in sent_pngs.values()
                        )
                        if is_legacy_flat:
                            for elem_id, png_info in sent_pngs.items():
                                if tl_vis.get(elem_id, False):
                                    overlays.append(png_info)
                        else:
                            part_id = str(part.get("_tl_part_id", ""))
                            if part_id and part_id in sent_pngs:
                                part_pngs = sent_pngs.get(part_id, {})
                            else:
                                # Fallback: align by part order if no explicit timeline part id.
                                part_dict_keys = [k for k, v in sent_pngs.items() if isinstance(v, dict)]
                                fallback_key = part_dict_keys[pidx] if pidx < len(part_dict_keys) else None
                                part_pngs = sent_pngs.get(fallback_key, {}) if fallback_key else {}
                            for elem_id, png_info in part_pngs.items():
                                if tl_vis.get(elem_id, False):
                                    overlays.append(png_info)

                        if overlays:
                            if first_overlay_start is None and (show_sub or show_wb or show_eb):
                                first_overlay_start = timeline_cursor
                            burned_path = str(job_tmp / f"s{i:04d}_p{pidx}_burned.mp4")
                            self._render_with_overlays(
                                base_clip, overlays, burned_path,
                                frame_w if need_rescale else None,
                                frame_h if need_rescale else None,
                            )
                            final_clip = burned_path
                        else:
                            if need_rescale:
                                norm_path = str(job_tmp / f"s{i:04d}_p{pidx}_norm.mp4")
                                self._normalize_resolution(base_clip, frame_w, frame_h, norm_path)
                                final_clip = norm_path
                            else:
                                final_clip = base_clip

                    elif use_png_overlay:
                        # ── 3a. PNG overlay 模式 ──
                        overlays = []
                        if show_sub and 'subtitle' in sent_pngs:
                            overlays.append(sent_pngs['subtitle'])
                        if show_wb and 'wordbox' in sent_pngs:
                            overlays.append(sent_pngs['wordbox'])
                        if show_eb and 'exprbox' in sent_pngs:
                            overlays.append(sent_pngs['exprbox'])

                        if overlays:
                            if first_overlay_start is None and (show_sub or show_wb or show_eb):
                                first_overlay_start = timeline_cursor
                            burned_path = str(job_tmp / f"s{i:04d}_p{pidx}_burned.mp4")
                            self._render_with_overlays(
                                base_clip, overlays, burned_path,
                                frame_w if need_rescale else None,
                                frame_h if need_rescale else None,
                            )
                            final_clip = burned_path
                        else:
                            if need_rescale:
                                norm_path = str(job_tmp / f"s{i:04d}_p{pidx}_norm.mp4")
                                self._normalize_resolution(base_clip, frame_w, frame_h, norm_path)
                                final_clip = norm_path
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
                            ass_path = str(job_tmp / f"s{i:04d}_p{pidx}.ass")
                            ass_gen.write_to_file(ass_content, ass_path)
                            ass_cache[show_key] = ass_path

                        if need_overlay:
                            if first_overlay_start is None and (show_sub or show_wb or show_eb):
                                first_overlay_start = timeline_cursor
                            burned_path = str(job_tmp / f"s{i:04d}_p{pidx}_burned.mp4")
                            self._burn_ass(
                                base_clip, ass_cache[show_key], burned_path,
                                frame_w if need_rescale else None,
                                frame_h if need_rescale else None,
                            )
                            final_clip = burned_path
                        else:
                            if need_rescale:
                                norm_path = str(job_tmp / f"s{i:04d}_p{pidx}_norm.mp4")
                                self._normalize_resolution(base_clip, frame_w, frame_h, norm_path)
                                final_clip = norm_path
                            else:
                                final_clip = base_clip

                    # 使用最终片段真实时长，避免估算累计误差造成跳转滞后
                    actual_clip_dur = self._probe_duration_seconds(final_clip) or clip_dur

                    # ── 4. 按 repeat 次数加入拼接列表 ──
                    for _ in range(repeat):
                        all_clip_paths.append(final_clip)
                    timeline_cursor += actual_clip_dur * repeat

                    done_clips += repeat
                    if progress_callback:
                        pct = int(done_clips / total_clips * 100)
                        progress_callback("clips", {
                            "current": i + 1, "total": len(sentences_data), "pct": pct
                        })

                sentence_timing.append({
                    "seg_start": seg_video_start,
                    "seg_end": timeline_cursor,
                    "first_overlay_start": first_overlay_start,
                })
                print(f"  ✓ 句子 {i+1}/{len(sentences_data)}")

            if cancelled_fn and cancelled_fn():
                return {"cancelled": True}

            # ── 6. 拼接所有片段 + 水印 ──
            print(f"[VideoProcessor] 🔗 拼接 {len(all_clip_paths)} 个片段...")
            if progress_callback:
                progress_callback("write", {"pct": 0})

            # Konva 模式下通常已经通过时间线渲染了水印元素，避免重复叠加
            has_timeline_watermark = False
            if use_konva and timeline_json:
                el_map = {e.get("id"): e.get("type") for e in timeline_json.get("elements", [])}
                wm_ids = {eid for eid, et in el_map.items() if et == "watermark"}
                if wm_ids:
                    for p in timeline_json.get("parts", []):
                        vis = p.get("elementVisibility", {})
                        if any(vis.get(wid) for wid in wm_ids):
                            has_timeline_watermark = True
                            break

            watermark_cfg = None
            if membership_tier != "member":
                if (not use_konva) or (not has_timeline_watermark):
                    watermark_cfg = forced_watermark or {
                        "text": "LinguaLearn",
                        "position": {"x": 0.33, "y": 0.16},
                        "size": {"w": 0.34, "h": 0.12},
                        "rotation": 30,
                        "opacity": 0.35,
                        "font_size": 120,
                    }
            print(
                f"[VideoProcessor] 💧 watermark route: tier={membership_tier}, "
                f"use_konva={use_konva}, has_timeline_watermark={has_timeline_watermark}, "
                f"drawtext_fallback={bool(watermark_cfg)}"
            )
            if watermark_cfg:
                print(
                    f"[VideoProcessor] 💧 drawtext cfg: text={watermark_cfg.get('text')}, "
                    f"pos={watermark_cfg.get('position')}, size={watermark_cfg.get('size')}, "
                    f"rotation={watermark_cfg.get('rotation')}, opacity={watermark_cfg.get('opacity')}, "
                    f"font_size={watermark_cfg.get('font_size')}"
                )

            self._concat_with_watermark(
                all_clip_paths, full_output_path, frame_w, frame_h,
                progress_callback,
                watermark_cfg=watermark_cfg,
            )

            if progress_callback:
                progress_callback("write", {"pct": 100})

            print("[VideoProcessor] ✅ 视频处理完成")
            return {"full": full_output_path, "sentence_timing": sentence_timing}

        finally:
            # 清理临时文件
            self._cleanup(job_tmp)

    # ──────────────────────────────────────────────────────────────
    # FFmpeg 命令
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_segment(src: str, start: float, end: float, out: str) -> None:
        """
        精确提取片段。

        说明：
        - 之前使用 `-ss before -i + -c copy`，会按关键帧切，导致片段起点可能落在更早位置，
          体感就是“下一句开头重复上一句后半段”。
        - 这里改为精确切片（解码后再编码），确保句子边界与时间戳一致。
        """
        duration = max(0.1, end - start)
        subprocess.run([
            _FFMPEG, "-y",
            "-i",  src,
            "-ss", f"{start:.3f}",
            "-t",  f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100",
            "-movflags", "+faststart",
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
    def _burn_ass(
        src: str, ass_path: str, out: str,
        frame_w: Optional[int] = None, frame_h: Optional[int] = None,
    ) -> None:
        """将 ASS 字幕烧录到视频"""
        # 转换为绝对路径，避免相对路径问题
        abs_path = os.path.abspath(ass_path)
        # FFmpeg filter 字符串转义：反斜杠 → \\，冒号 → \:
        # 注意：subprocess 不走 shell，所以不需要 shell 级别的引号
        safe_ass = abs_path.replace("\\", "/").replace(":", "\\:")

        vf_chain = []
        if frame_w and frame_h:
            vf_chain.append(
                f"scale={frame_w}:{frame_h}:force_original_aspect_ratio=decrease,"
                f"pad={frame_w}:{frame_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
            )
        vf_chain.append(f"ass=filename={safe_ass}")

        result = subprocess.run([
            _FFMPEG, "-y", "-i", src,
            "-vf", ",".join(vf_chain),
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "copy",
            out,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[FFmpeg ASS] stderr: {result.stderr[-2000:]}")
            raise subprocess.CalledProcessError(result.returncode, result.args)

    @staticmethod
    def _render_with_overlays(
        src: str, overlays: list, out: str,
        frame_w: Optional[int] = None, frame_h: Optional[int] = None,
    ) -> None:
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
        if frame_w and frame_h:
            filter_parts.append(
                f"[0:v]scale={frame_w}:{frame_h}:force_original_aspect_ratio=decrease,"
                f"pad={frame_w}:{frame_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[vbase]"
            )
            prev = "vbase"
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

    @staticmethod
    def _normalize_resolution(src: str, frame_w: int, frame_h: int, out: str) -> None:
        """统一片段分辨率到编辑器画布尺寸（保留宽高比，黑边补齐）。"""
        vf = (
            f"scale={frame_w}:{frame_h}:force_original_aspect_ratio=decrease,"
            f"pad={frame_w}:{frame_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
        )
        result = subprocess.run([
            _FFMPEG, "-y", "-i", src,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
            "-c:a", "copy",
            out,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[FFmpeg normalize] stderr: {result.stderr[-2000:]}")
            raise subprocess.CalledProcessError(result.returncode, result.args)

    @staticmethod
    def _probe_video_resolution(video_path: str) -> Tuple[Optional[int], Optional[int]]:
        """读取视频首个视频流分辨率。"""
        try:
            result = subprocess.run([
                _FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                video_path,
            ], capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout or "{}")
            streams = data.get("streams", [])
            if not streams:
                return None, None
            width = streams[0].get("width")
            height = streams[0].get("height")
            return int(width) if width else None, int(height) if height else None
        except Exception:
            return None, None

    @staticmethod
    def _probe_duration_seconds(video_path: str) -> Optional[float]:
        """读取媒体时长（秒）。"""
        try:
            result = subprocess.run([
                _FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ], capture_output=True, text=True, check=True)
            v = (result.stdout or "").strip()
            return float(v) if v else None
        except Exception:
            return None

    @staticmethod
    def _build_atempo_chain(speed: float) -> str:
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
        watermark_cfg: Optional[Dict] = None,
    ) -> None:
        """使用 concat filter 拼接所有片段并叠加水印，一次 pass 完成"""
        n = len(clip_paths)
        inputs = []
        for p in clip_paths:
            inputs += ["-i", p]

        # 构建 filter_complex
        in_refs   = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        concat_f  = f"{in_refs}concat=n={n}:v=1:a=1[vc][aout]"
        filter_complex = concat_f
        v_ref = "vc"
        if watermark_cfg:
            wm_text = str(watermark_cfg.get("text", "LinguaLearn")).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            wm_opacity = float(watermark_cfg.get("opacity", 0.35))
            wm_size = int(watermark_cfg.get("font_size", max(16, int(min(frame_w, frame_h) * 0.04))))
            x_pct = float((watermark_cfg.get("position") or {}).get("x", 0.33))
            y_pct = float((watermark_cfg.get("position") or {}).get("y", 0.16))
            wm_x = int(frame_w * x_pct)
            wm_y = int(frame_h * y_pct)
            # drawtext 不支持直接旋转；Konva 模式下默认走时间线水印（支持旋转）
            wm_filter = (
                f"[vc]drawtext="
                f"text='{wm_text}':"
                f"fontsize={wm_size}:"
                f"fontcolor=white@{wm_opacity}:"
                f"x={wm_x}:"
                f"y={wm_y}"
                f"[vout]"
            )
            filter_complex = f"{concat_f};{wm_filter}"
            v_ref = "vout"

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
                _FFMPEG, "-y", *inputs,
                "-filter_complex", filter_complex,
                "-map", f"[{v_ref}]", "-map", "[aout]",
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
