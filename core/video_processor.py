import os
import subprocess
import tempfile
import time
from typing import List, Dict, Optional, Callable
from moviepy.editor import (
    VideoFileClip, AudioFileClip, AudioClip, CompositeVideoClip,
    concatenate_videoclips, concatenate_audioclips, ImageClip, TextClip
)
from moviepy.video.fx.all import speedx
from PIL import Image
import numpy as np

import config
from html_renderer import HTMLRenderer

try:
    import proglog

    class _VideoWriteLogger(proglog.ProgressBarLogger):
        def __init__(self, progress_fn: Callable = None):
            super().__init__(min_time_interval=1.0)
            self._fn = progress_fn

        def callback(self, **changes):
            if not self._fn:
                return
            for bar in self.bars.values():
                total = bar.get('total') or 0
                idx = bar.get('index') or 0
                if total > 0:
                    pct = min(100, int(idx / total * 100))
                    self._fn('write', {'pct': pct})
                    break

except ImportError:
    _VideoWriteLogger = None


class VideoProcessor:
    def __init__(self):
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        self.html_renderer = HTMLRenderer()
        self._subtitle_cache = {}
        self._wordbox_cache = {}
        self._exprbox_cache = {}

    def _create_watermark(self, video_width: int, video_height: int, duration: float = None) -> Optional[ImageClip]:
        if not config.WATERMARK_ENABLED:
            return None
        watermark_text = "Made By GetEverybodyLearning"
        font_size = int(min(video_width, video_height) * 0.05)
        for font in ('Arial-Bold', 'Helvetica-Bold', None):
            try:
                kwargs = dict(
                    fontsize=font_size,
                    color=f'gray({config.WATERMARK_GRAY})',
                    stroke_color=f'gray({config.WATERMARK_GRAY})',
                    stroke_width=font_size * 0.08,
                )
                if font:
                    kwargs['font'] = font
                watermark = TextClip(watermark_text, **kwargs)
                break
            except Exception:
                continue
        else:
            return None

        watermark = watermark.set_opacity(config.WATERMARK_OPACITY)
        ww, wh = watermark.size
        watermark = watermark.set_position(((video_width - ww) // 2, (video_height - wh) // 2))
        watermark = watermark.rotate(config.WATERMARK_ANGLE)
        if duration is not None:
            watermark = watermark.set_duration(duration)
        return watermark

    def _slow_audio_with_pitch_preservation(self, audio_clip, speed_factor: float, slow_duration: float):
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp_in = f.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp_out = f.name
        try:
            audio_clip.write_audiofile(tmp_in, verbose=False, logger=None)
            subprocess.run([
                'ffmpeg', '-y', '-i', tmp_in,
                '-filter:a', f'atempo={speed_factor}',
                '-t', str(slow_duration),
                tmp_out
            ], capture_output=True, check=True)
            result = AudioFileClip(tmp_out)
            if result.duration < slow_duration:
                silence = AudioClip(lambda t: 0, duration=slow_duration - result.duration, fps=result.fps)
                result = concatenate_audioclips([result, silence])
            return result
        except Exception as e:
            print(f"Warning: Audio processing failed: {e}")
        return AudioClip(lambda t: 0, duration=slow_duration, fps=44100)

    def create_subtitle_frame(self, english_text: str, chinese_text: str,
                              width: int, height: int, style: dict = None) -> np.ndarray:
        cache_key = (english_text, chinese_text, width, height, str(sorted((style or {}).items())))
        if cache_key in self._subtitle_cache:
            return self._subtitle_cache[cache_key]
        temp_path = os.path.join(config.TEMP_DIR, f'subtitle_{int(time.time() * 1000000)}.png')
        success = self.html_renderer.render_subtitle(english_text, chinese_text, width, height, temp_path, style=style)
        if not success or not os.path.exists(temp_path):
            raise RuntimeError(f"Subtitle render failed: {english_text[:30]}")
        result = np.array(Image.open(temp_path))
        self._subtitle_cache[cache_key] = result
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return result

    def create_word_box_frame(self, words: List[Dict],
                              width: int, height: int, style: dict = None) -> np.ndarray:
        cache_key = (tuple(w.get('word', '') for w in words), width, height, str(sorted((style or {}).items())))
        if cache_key in self._wordbox_cache:
            return self._wordbox_cache[cache_key]
        temp_path = os.path.join(config.TEMP_DIR, f'wordbox_{int(time.time() * 1000000)}.png')
        success = self.html_renderer.render_wordbox(words, width, height, temp_path, style=style)
        if not success or not os.path.exists(temp_path):
            raise RuntimeError("Wordbox render failed")
        result = np.array(Image.open(temp_path))
        self._wordbox_cache[cache_key] = result
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return result

    def create_expression_box_frame(self, expressions: List[Dict],
                                    width: int, height: int, style: dict = None) -> np.ndarray:
        cache_key = (tuple(e.get('english', '') for e in expressions), width, height, str(sorted((style or {}).items())))
        if cache_key in self._exprbox_cache:
            return self._exprbox_cache[cache_key]
        temp_path = os.path.join(config.TEMP_DIR, f'expressionbox_{int(time.time() * 1000000)}.png')
        success = self.html_renderer.render_expressionbox(expressions, width, height, temp_path, style=style)
        if not success or not os.path.exists(temp_path):
            raise RuntimeError("Expressionbox render failed")
        result = np.array(Image.open(temp_path))
        self._exprbox_cache[cache_key] = result
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return result

    def _make_image_clip(self, arr: np.ndarray, duration: float, pos) -> ImageClip:
        if arr.shape[2] == 4:
            clip = ImageClip(arr, duration=duration)
        else:
            clip = ImageClip(arr[:, :, :3], duration=duration)
        return clip.set_position(pos)

    def process_sentence_video(self, video_clip: VideoFileClip,
                               sentence_data: Dict,
                               start_time: float,
                               end_time: float,
                               next_sentence_start: Optional[float] = None,
                               style: dict = None) -> VideoFileClip:
        style = style or {}
        segment_duration = end_time - start_time
        gap_end_time = next_sentence_start if next_sentence_start is not None else end_time
        gap_duration = gap_end_time - start_time

        orig_width, orig_height = video_clip.size

        # Layout from style (percentages of video dimensions)
        sub_w_pct = style.get('subtitle_width_pct', 0.95)
        sub_h_pct = style.get('subtitle_height_pct', 0.22)
        sub_x_pct = style.get('subtitle_x_pct', (1 - sub_w_pct) / 2)
        sub_y_pct = style.get('subtitle_y_pct', 1 - sub_h_pct)

        wb_w_pct = style.get('wordbox_width_pct', 0.245)
        wb_h_pct = style.get('wordbox_height_pct', 0.65)
        wb_x_pct = style.get('wordbox_x_pct', 1 - wb_w_pct - 0.005)
        wb_y_pct = style.get('wordbox_y_pct', 0.005)

        eb_w_pct = style.get('exprbox_width_pct', 0.245)
        eb_h_pct = style.get('exprbox_height_pct', 0.55)
        eb_x_pct = style.get('exprbox_x_pct', 0.005)
        eb_y_pct = style.get('exprbox_y_pct', 0.005)

        sub_w = int(orig_width * sub_w_pct)
        sub_h = int(orig_height * sub_h_pct)
        sub_x = int(orig_width * sub_x_pct)
        sub_y = int(orig_height * sub_y_pct)

        wb_w = int(orig_width * wb_w_pct)
        wb_h = int(orig_height * wb_h_pct)
        wb_x = int(orig_width * wb_x_pct)
        wb_y = int(orig_height * wb_y_pct)

        eb_w = int(orig_width * eb_w_pct)
        eb_h = int(orig_height * eb_h_pct)
        eb_x = int(orig_width * eb_x_pct)
        eb_y = int(orig_height * eb_y_pct)

        subtitle_arr = self.create_subtitle_frame(
            sentence_data['original_text'],
            sentence_data.get('chinese_translation', ''),
            sub_w, sub_h, style=style
        )

        word_box_arr = None
        if sentence_data.get('key_words'):
            word_box_arr = self.create_word_box_frame(
                sentence_data['key_words'], wb_w, wb_h, style=style
            )

        expr_box_arr = None
        if sentence_data.get('useful_expressions'):
            expr_box_arr = self.create_expression_box_frame(
                sentence_data['useful_expressions'], eb_w, eb_h, style=style
            )

        def build_composite(base_clip, duration, show_sub, show_word, show_expr):
            clips = [base_clip]
            if show_sub:
                clips.append(self._make_image_clip(subtitle_arr, duration, (sub_x, sub_y)))
            if show_word and word_box_arr is not None:
                clips.append(self._make_image_clip(word_box_arr, duration, (wb_x, wb_y)))
            if show_expr and expr_box_arr is not None:
                clips.append(self._make_image_clip(expr_box_arr, duration, (eb_x, eb_y)))
            if len(clips) > 1:
                return CompositeVideoClip(clips).set_duration(duration)
            return base_clip

        # Part 1: original speed
        part1_base = video_clip.subclip(start_time, gap_end_time)
        part1 = build_composite(
            part1_base, gap_duration,
            config.PART1_SHOW_SUBTITLE,
            config.PART1_SHOW_WORD_BOX,
            config.PART1_SHOW_EXPRESSION_BOX,
        )

        # Part 2: slow speed
        segment = video_clip.subclip(start_time, end_time)
        slow_video = segment.without_audio().fx(speedx, config.SPEED_SLOW)
        slow_duration = round(slow_video.duration, 2)
        slow_video = slow_video.subclip(0, slow_duration)
        slowed_audio = self._slow_audio_with_pitch_preservation(segment.audio, config.SPEED_SLOW, slow_duration)
        part2 = build_composite(
            slow_video, slow_duration,
            config.PART2_SHOW_SUBTITLE,
            config.PART2_SHOW_WORD_BOX,
            config.PART2_SHOW_EXPRESSION_BOX,
        )
        if slowed_audio:
            part2 = part2.set_audio(slowed_audio)

        # Part 3: normal speed with overlays
        part3_base = video_clip.subclip(start_time, gap_end_time)
        part3 = build_composite(
            part3_base, gap_duration,
            config.PART3_SHOW_SUBTITLE,
            config.PART3_SHOW_WORD_BOX,
            config.PART3_SHOW_EXPRESSION_BOX,
        )

        final_parts = (
            [part1] * config.PART1_REPEAT_COUNT +
            [part2] * config.PART2_REPEAT_COUNT +
            [part3] * config.PART3_REPEAT_COUNT
        )
        return concatenate_videoclips(final_parts, method="compose")

    def process_full_video(self, video_path: str,
                           sentences_data: List[Dict],
                           output_path: str,
                           segments_info: Optional[List[Dict]] = None,
                           progress_callback: Optional[Callable] = None,
                           style: dict = None,
                           cancelled_fn: Optional[Callable] = None) -> dict:
        """
        Process the full video and write the output.

        progress_callback(phase, data):
            phase='clips': data={'current': i, 'total': n, 'pct': 0-100}
            phase='write':  data={'pct': 0-100}
        cancelled_fn(): returns True if job should be cancelled.
        """
        base_path = os.path.splitext(output_path)[0]
        full_output_path = f"{base_path}_full.mp4"

        print("正在加载视频...")
        video = VideoFileClip(video_path)

        print("\n" + "=" * 60)
        print("生成学习版视频...")
        print("=" * 60)

        full_clips = []
        total = len(sentences_data)
        segs = segments_info or []

        for i, sentence_data in enumerate(sentences_data):
            if cancelled_fn and cancelled_fn():
                print("⚠️ 任务已取消")
                video.close()
                return {"cancelled": True}

            seg_info = segs[i] if i < len(segs) else {}
            start_time = seg_info.get('start', 0)
            end_time = seg_info.get('end', video.duration)
            next_start = segs[i + 1].get('start') if i + 1 < len(segs) else None

            processed_clip = self.process_sentence_video(
                video, sentence_data, start_time, end_time, next_start, style=style
            )
            full_clips.append(processed_clip)

            pct = int((i + 1) / total * 100)
            print(f"  片段 {i+1}/{total} ({pct}%)")
            if progress_callback:
                progress_callback('clips', {'current': i + 1, 'total': total, 'pct': pct})

        if cancelled_fn and cancelled_fn():
            video.close()
            return {"cancelled": True}

        print("正在合并视频片段...")
        full_video = concatenate_videoclips(full_clips, method="compose")
        full_video = full_video.set_fps(config.FPS)
        print(f"总时长: {full_video.duration:.1f}s")

        if _VideoWriteLogger is not None and progress_callback:
            logger = _VideoWriteLogger(
                progress_fn=lambda phase, data: progress_callback(phase, data)
            )
        else:
            logger = 'bar'

        print(f"正在导出视频到 {full_output_path}...")
        if progress_callback:
            progress_callback('write', {'pct': 0})

        # 优化编码参数以加快速度
        write_params = {
            'fps': config.FPS,
            'codec': 'libx264',
            'audio_codec': 'aac',
            'audio_fps': config.AUDIO_FPS,
            'preset': 'superfast',  # 超快速预设（比 fast 快 3-4 倍）
            'bitrate': '4000k',      # 降低比特率（1080p 仍有不错画质）
            'verbose': False,        # 关闭冗长输出
            'logger': logger,
        }

        # 根据分辨率调整参数
        if config.VIDEO_RESOLUTION == '720p':
            write_params['bitrate'] = '2500k'

        full_video.write_videofile(full_output_path, **write_params)

        video.close()
        full_video.close()

        if progress_callback:
            progress_callback('write', {'pct': 100})

        print("\n视频处理完成！")
        return {"full": full_output_path}
