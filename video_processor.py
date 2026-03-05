import os
import subprocess
import tempfile
import time
from typing import List, Dict, Optional
from tqdm import tqdm
from moviepy.editor import (
    VideoFileClip, AudioFileClip, AudioClip, CompositeVideoClip, 
    concatenate_videoclips, concatenate_audioclips, ImageClip, TextClip
)
from moviepy.video.fx.all import speedx
from PIL import Image, ImageDraw, ImageFont
import numpy as np

import config
from html_renderer import HTMLRenderer


class VideoProcessor:
    def __init__(self):
        """初始化视频处理器"""
        # 创建输出目录
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        # 初始化 HTML 渲染器
        self.html_renderer = HTMLRenderer()
        
        # 标记是否已保存调试图片
        self._debug_saved = True
        
        # 缓存已渲染的帧（避免重复调用 Chrome）
        self._subtitle_cache = {}  # (english_text, chinese_text, width, height) -> np.ndarray
        self._wordbox_cache = {}    # (words tuple, width, height) -> np.ndarray
        self._exprbox_cache = {}   # (expressions tuple, width, height) -> np.ndarray
    
    def _create_watermark(self, video_width: int, video_height: int, duration: float = None) -> Optional[ImageClip]:
        """
        创建斜着的半透明灰色水印
        
        Args:
            video_width: 视频宽度
            video_height: video_height
            duration: 视频时长（秒），如果不提供则不设置
            
        Returns:
            水印 ImageClip，如果禁用水印则返回 None
        """
        # 如果禁用水印，直接返回 None
        if not config.WATERMARK_ENABLED:
            return None
        
        # 水印文字
        watermark_text = "Made By GetEverybodyLearning"
        
        # 计算合适的字体大小（基于视频尺寸）
        font_size = int(min(video_width, video_height) * 0.05)
        
        # 创建 TextClip，使用粗体字体
        try:
            watermark = TextClip(
                watermark_text,
                fontsize=font_size,
                color=f'gray({config.WATERMARK_GRAY})',
                font='Arial-Bold',
                stroke_color=f'gray({config.WATERMARK_GRAY})',
                stroke_width=font_size * 0.08,
            )
        except Exception:
            try:
                watermark = TextClip(
                    watermark_text,
                    fontsize=font_size,
                    color=f'gray({config.WATERMARK_GRAY})',
                    font='Helvetica-Bold',
                    stroke_color=f'gray({config.WATERMARK_GRAY})',
                    stroke_width=font_size * 0.08,
                )
            except Exception:
                watermark = TextClip(
                    watermark_text,
                    fontsize=font_size,
                    color=f'gray({config.WATERMARK_GRAY})',
                    stroke_color=f'gray({config.WATERMARK_GRAY})',
                    stroke_width=font_size * 0.08,
                )
        
        # 设置透明度
        watermark = watermark.set_opacity(config.WATERMARK_OPACITY)
        
        # 计算水印位置（居中）
        watermark_w, watermark_h = watermark.size
        x_pos = (video_width - watermark_w) // 2
        y_pos = (video_height - watermark_h) // 2
        
        # 设置位置
        watermark = watermark.set_position((x_pos, y_pos))
        
        # 旋转角度
        watermark = watermark.rotate(config.WATERMARK_ANGLE)
        
        # 如果提供了视频时长则设置
        if duration is not None:
            watermark = watermark.set_duration(duration)
        
        return watermark
      
    
    def _slow_audio_with_pitch_preservation(self, audio_clip: AudioFileClip, speed_factor: float, slow_duration: float) -> AudioFileClip:
        """
        使用 FFmpeg 的 atempo 滤镜减速音频，保持音调不变
        
        Args:
            audio_clip: 原始音频
            speed_factor: 速度因子 (如 0.75 表示减速)
            slow_duration: 最终需要的时长
            
        Returns:
            减速并调整后的音频
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_input:
            tmp_input_path = tmp_input.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_output:
            tmp_output_path = tmp_output.name
        
        try:
            # 将原始音频写入临时文件
            audio_clip.write_audiofile(tmp_input_path, verbose=False, logger=None)
            
            # 变速 + 调整时长一步完成
            subprocess.run([
                'ffmpeg', '-y', '-i', tmp_input_path,
                '-filter:a', f'atempo={speed_factor}',
                '-t', str(slow_duration),
                tmp_output_path
            ], capture_output=True, check=True)
            
            # 加载处理后的音频
            result = AudioFileClip(tmp_output_path)
            
            # 如果音频比目标时长短，用静音填充
            if result.duration < slow_duration:
                silence = AudioClip(lambda t: 0, duration=slow_duration - result.duration, fps=result.fps)
                result = concatenate_audioclips([result, silence])
            
            return result
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: FFmpeg failed: {e.stderr.decode() if e.stderr else e}")
        except Exception as e:
            print(f"Warning: Audio processing failed: {e}")
        
        # 出错时返回静音
        return AudioClip(lambda t: 0, duration=slow_duration, fps=44100)
    
    def create_subtitle_frame(self, english_text: str, chinese_text: str, 
                             width: int, height: int) -> np.ndarray:
        """
        创建字幕框图像 - 使用 HTML + Chrome 渲染（带缓存）
        
        Args:
            english_text: 英文文本
            chinese_text: 中文文本
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 生成缓存 key
        cache_key = (english_text, chinese_text, width, height)
        
        # 检查缓存
        if cache_key in self._subtitle_cache:
            return self._subtitle_cache[cache_key]
        
        # 创建临时输出路径
        temp_path = os.path.join(config.TEMP_DIR, f'subtitle_{int(time.time() * 1000000)}.png')
        
        # 使用 HTML 渲染器生成字幕图片
        success = self.html_renderer.render_subtitle(
            english_text, chinese_text, width, height, temp_path
        )
        
        if not success or not os.path.exists(temp_path):
            raise RuntimeError(f"HTML 字幕渲染失败！english: {english_text[:30]}...")
        
        # 读取渲染好的图片并转换为 numpy 数组
        img = Image.open(temp_path)
        result = np.array(img)
        
        # 缓存结果
        self._subtitle_cache[cache_key] = result
        
        # 保存第一个用于调试
        if not self._debug_saved:
            img.save(os.path.join(config.OUTPUT_DIR, 'debug_subtitle.png'))
            print(f"  ✅ 已保存字幕框图片: {os.path.join(config.OUTPUT_DIR, 'debug_subtitle.png')}")
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
    
    def create_word_box_frame(self, words: List[Dict], 
                             width: int, height: int) -> np.ndarray:
        """
        创建单词框图像 - 使用 HTML + Chrome 渲染（带缓存）
        
        Args:
            words: 单词信息列表
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 生成缓存 key（使用单词文本的 tuple）
        words_key = tuple(w.get('word', '') for w in words)
        cache_key = (words_key, width, height)
        
        # 检查缓存
        if cache_key in self._wordbox_cache:
            return self._wordbox_cache[cache_key]
        
        # 创建临时输出路径
        temp_path = os.path.join(config.TEMP_DIR, f'wordbox_{int(time.time() * 1000000)}.png')
        
        # 使用 HTML 渲染器生成单词框图片
        success = self.html_renderer.render_wordbox(
            words, width, height, temp_path
        )
        
        if not success:
            raise RuntimeError(f"HTML 单词框渲染失败！words: {[w.get('word', '') for w in words[:2]]}")
        if not os.path.exists(temp_path):
            raise RuntimeError(f"单词框图片不存在！temp_path: {temp_path}")
        
        # 读取渲染好的图片并转换为 numpy 数组
        img = Image.open(temp_path)
        result = np.array(img)
        
        # 缓存结果
        self._wordbox_cache[cache_key] = result
        
        # 保存第一个用于调试
        if not self._debug_saved:
            img.save(os.path.join(config.OUTPUT_DIR, 'debug_wordbox.png'))
            print(f"  ✅ 已保存单词框图片: {os.path.join(config.OUTPUT_DIR, 'debug_wordbox.png')}")
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
    
    def create_expression_box_frame(self, expressions: List[Dict], 
                                   width: int, height: int) -> np.ndarray:
        """
        创建表达框图像 - 使用 HTML + Chrome 渲染（带缓存）
        
        Args:
            expressions: 表达信息列表
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 生成缓存 key（使用表达文本的 tuple）
        expr_key = tuple(e.get('english', '') for e in expressions)
        cache_key = (expr_key, width, height)
        
        # 检查缓存
        if cache_key in self._exprbox_cache:
            return self._exprbox_cache[cache_key]
        
        # 创建临时输出路径
        temp_path = os.path.join(config.TEMP_DIR, f'expressionbox_{int(time.time() * 1000000)}.png')
        
        # 使用 HTML 渲染器生成表达框图片
        success = self.html_renderer.render_expressionbox(
            expressions, width, height, temp_path
        )
        
        if not success or not os.path.exists(temp_path):
            raise RuntimeError(f"HTML 表达框渲染失败！expressions: {[e.get('english', '') for e in expressions[:2]]}")
        
        # 读取渲染好的图片并转换为 numpy 数组
        img = Image.open(temp_path)
        result = np.array(img)
        
        # 缓存结果
        self._exprbox_cache[cache_key] = result
        
        # 保存第一个用于调试
        if not self._debug_saved:
            img.save(os.path.join(config.OUTPUT_DIR, 'debug_expressionbox.png'))
            print(f"  ✅ 已保存表达框图片: {os.path.join(config.OUTPUT_DIR, 'debug_expressionbox.png')}")
            self._debug_saved = True
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
    
    def process_sentence_video_quick(self, video_clip: VideoFileClip, 
                                       sentence_data: Dict,
                                       start_time: float,
                                       end_time: float) -> VideoFileClip:
        """
        快速模式：处理单个句子的视频片段（原速 + 带翻译的字幕框）
        
        Args:
            video_clip: 原始视频
            sentence_data: 句子数据（包含翻译）
            start_time: 句子开始时间
            end_time: 句子结束时间
            
        Returns:
            处理后的视频片段
        """
        # 时间处理 - 确保不超过视频总时长
        video_duration = video_clip.duration
        end_time = min(end_time + 0.1, video_duration)
        
        # 计算正确的 duration
        duration = end_time - start_time
        
        # 获取原始视频尺寸
        orig_width, orig_height = video_clip.size
        
        # 字幕框尺寸
        subtitle_box_height = int(orig_height * 0.33)
        subtitle_margin = int(orig_height * 0.005)
        subtitle_box_width = int(orig_width * 0.95)
        
        # 创建字幕框（带翻译）
        subtitle_img = self.create_subtitle_frame(
            sentence_data['original_text'],
            sentence_data['chinese_translation'],
            subtitle_box_width,
            subtitle_box_height
        )
        subtitle_arr = np.array(subtitle_img)
        
        # 提取原速视频片段
        segment = video_clip.subclip(start_time, end_time)
        
        # 创建字幕 clip
        if subtitle_arr.shape[2] == 4:
            subtitle_clip = ImageClip(subtitle_arr, duration=duration).set_position(
                ('center', orig_height - subtitle_box_height - subtitle_margin)
            )
        else:
            subtitle_clip = ImageClip(subtitle_arr[:, :, :3], duration=duration).set_position(
                ('center', orig_height - subtitle_box_height - subtitle_margin)
            )
        
        # 合成视频和字幕
        final_clip = CompositeVideoClip([segment, subtitle_clip])
        
        # 显式设置 duration，防止 moviepy 计算错误
        final_clip = final_clip.set_duration(duration)

        return final_clip
    
    def process_sentence_video(self, video_clip: VideoFileClip, 
                               sentence_data: Dict,
                               start_time: float,
                               end_time: float,
                               next_sentence_start: Optional[float] = None) -> VideoFileClip:
        """
        处理单个句子的视频片段
        
        处理流程（可配置）：
        1. Part 1: 原速播放（可配置是否显示字幕框、单词框、播放遍数）
        2. Part 2: 慢速播放（可配置是否显示字幕框、单词框、播放遍数）
        3. Part 3: 正常速度播放（可配置是否显示字幕框、单词框、播放遍数）
        
        Args:
            video_clip: 原始视频
            sentence_data: 句子数据（包含翻译和单词）
            start_time: 句子开始时间
            end_time: 句子结束时间
            next_sentence_start: 下一句的开始时间
            
        Returns:
            处理后的视频片段
        """
        # 时间处理
        # 使用句子的实际结束时间，而不是下一个句子的开始时间
        segment_duration = end_time - start_time
        gap_end_time = next_sentence_start if next_sentence_start is not None else end_time
        gap_duration = gap_end_time - start_time
        
        # 获取原始视频尺寸
        orig_width, orig_height = video_clip.size
        
        # ===== 准备字幕框和单词框 =====
        # 字幕框尺寸
        subtitle_box_height = int(orig_height * 0.33)
        subtitle_margin = int(orig_height * 0.005)
        subtitle_box_width = int(orig_width * 0.95)
        
        # 单词框尺寸 (放在右上角)
        word_box_width = int(orig_width * 0.25)
        word_box_height = int(orig_height * 0.65)
        word_box_margin = int(orig_width * 0.005)
        
        # 表达框尺寸（放在左上角）
        expr_box_width = int(orig_width * 0.25)
        expr_box_height = int(orig_height * 0.45)
        expr_box_margin = int(orig_width * 0.005)
        
        # 创建字幕框（用于Part2和Part3）
        subtitle_img = self.create_subtitle_frame(
            sentence_data['original_text'],
            sentence_data['chinese_translation'],
            subtitle_box_width,
            subtitle_box_height
        )
        subtitle_arr = np.array(subtitle_img)
        
        # 创建单词框（用于Part2和Part3）
        word_box_clip = None
        if sentence_data.get('key_words'):
            word_box_img = self.create_word_box_frame(
                sentence_data['key_words'],
                word_box_width,
                word_box_height
            )
            word_box_arr = np.array(word_box_img)
            
            if word_box_arr.shape[2] == 4:
                word_box_clip = ImageClip(word_box_arr).set_position(
                    (orig_width - word_box_width - word_box_margin, word_box_margin)
                )
            else:
                word_box_clip = ImageClip(word_box_arr[:, :, :3]).set_position(
                    (orig_width - word_box_width - word_box_margin, word_box_margin)
                )
        
        # 创建表达框（用于Part2和Part3）
        expr_box_clip = None
        if sentence_data.get('useful_expressions'):
            expr_box_img = self.create_expression_box_frame(
                sentence_data['useful_expressions'],
                expr_box_width,
                expr_box_height
            )
            expr_box_arr = np.array(expr_box_img)
            
            if expr_box_arr.shape[2] == 4:
                expr_box_clip = ImageClip(expr_box_arr).set_position(
                    (expr_box_margin, expr_box_margin)
                )
            else:
                expr_box_clip = ImageClip(expr_box_arr[:, :, :3]).set_position(
                    (expr_box_margin, expr_box_margin)
                )
        
        # ===== 第1部分：原速播放 =====
        part1_segment = video_clip.subclip(t_start=start_time, t_end=gap_end_time)
        # print(f"part1_segment.duration={part1_segment.duration:.2f}")
        
        # 根据配置决定是否添加字幕框、单词框和表达框
        part1_clips = [part1_segment]
        if config.PART1_SHOW_SUBTITLE:
            if subtitle_arr.shape[2] == 4:
                subtitle_clip = ImageClip(subtitle_arr, duration=gap_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            else:
                subtitle_clip = ImageClip(subtitle_arr[:, :, :3], duration=gap_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            part1_clips.append(subtitle_clip)
        
        if config.PART1_SHOW_WORD_BOX and word_box_clip:
            part1_clips.append(word_box_clip.set_duration(gap_duration))
        
        if config.PART1_SHOW_EXPRESSION_BOX and expr_box_clip:
            part1_clips.append(expr_box_clip.set_duration(gap_duration))
        
        if len(part1_clips) > 1:
            part1 = CompositeVideoClip(part1_clips).set_duration(gap_duration)
        else:
            part1 = part1_segment
        
        # ===== 第2部分：慢速播放 =====
        segment = video_clip.subclip(start_time, end_time)
        
        # 减速视频
        slow_video = segment.without_audio().fx(speedx, config.SPEED_SLOW)
        slow_duration = round(slow_video.duration, 2)
        slow_video = slow_video.subclip(0, slow_duration)
        
        # 减速音频
        original_audio = segment.audio
        slowed_audio = self._slow_audio_with_pitch_preservation(original_audio, config.SPEED_SLOW, slow_duration)
        
        # 根据配置决定是否添加字幕框、单词框和表达框
        part2_clips = [slow_video]
        if config.PART2_SHOW_SUBTITLE:
            if subtitle_arr.shape[2] == 4:
                subtitle_clip = ImageClip(subtitle_arr, duration=slow_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            else:
                subtitle_clip = ImageClip(subtitle_arr[:, :, :3], duration=slow_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            part2_clips.append(subtitle_clip)
        
        if config.PART2_SHOW_WORD_BOX and word_box_clip:
            part2_clips.append(word_box_clip.set_duration(slow_duration))
        
        if config.PART2_SHOW_EXPRESSION_BOX and expr_box_clip:
            part2_clips.append(expr_box_clip.set_duration(slow_duration))
        
        if len(part2_clips) > 1:
            part2 = CompositeVideoClip(part2_clips).set_duration(slow_duration)
        else:
            part2 = slow_video

        # 添加减速后的音频
        if slowed_audio:
            part2 = part2.set_audio(slowed_audio)
        
        # ===== 第3部分：正常速度播放 =====
        # 重新截取视频片段，使用正确的结束时间
        part3_segment = video_clip.subclip(start_time, gap_end_time)
        
        # 根据配置决定是否添加字幕框、单词框和表达框
        part3_clips = [part3_segment]
        if config.PART3_SHOW_SUBTITLE:
            if subtitle_arr.shape[2] == 4:
                subtitle_clip = ImageClip(subtitle_arr, duration=gap_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            else:
                subtitle_clip = ImageClip(subtitle_arr[:, :, :3], duration=gap_duration).set_position(
                    ('center', orig_height - subtitle_box_height - subtitle_margin)
                )
            part3_clips.append(subtitle_clip)
        
        if config.PART3_SHOW_WORD_BOX and word_box_clip:
            part3_clips.append(word_box_clip.set_duration(gap_duration))
        
        if config.PART3_SHOW_EXPRESSION_BOX and expr_box_clip:
            part3_clips.append(expr_box_clip.set_duration(gap_duration))
        
        if len(part3_clips) > 1:
            part3 = CompositeVideoClip(part3_clips).set_duration(gap_duration)
        else:
            part3 = part3_segment
        
        # ===== 合并三个部分（根据配置的播放遍数） =====
        final_parts = []
        
        # Part 1 播放 N 遍
        for _ in range(config.PART1_REPEAT_COUNT):
            final_parts.append(part1)
        
        # Part 2 播放 N 遍
        for _ in range(config.PART2_REPEAT_COUNT):
            final_parts.append(part2)
        
        # Part 3 播放 N 遍
        for _ in range(config.PART3_REPEAT_COUNT):
            final_parts.append(part3)
        
        # 使用 compose 方法确保视频正确连接
        final_clip = concatenate_videoclips(final_parts, method="compose")

        return final_clip
    
    def process_full_video(self, video_path: str, 
                          sentences_data: List[Dict],
                          output_path: str,
                          segments_info: Optional[List[Dict]] = None) -> str:
        """
        处理完整视频 - 同时生成缩略版和学习版
        
        Args:
            video_path: 输入视频路径
            sentences_data: 所有句子的数据
            output_path: 输出视频路径（基础路径，会自动添加 _quick 和 _full 后缀）
            segments_info: 片段时间信息列表
            
        Returns:
            包含两个视频路径的字典 {"quick": quick_path, "full": full_path}
        """
        import os
        
        # 获取基础路径（去掉扩展名）
        base_path = os.path.splitext(output_path)[0]
        quick_output_path = f"{base_path}_quick.mp4"
        full_output_path = f"{base_path}_full.mp4"
        
        print("正在加载视频...")
        video = VideoFileClip(video_path)
    
        
        # ===== 生成缩略版 (Quick) =====
        print("\n" + "=" * 60)
        print("生成缩略版视频...")
        print("=" * 60)
        print("缩略版模式：仅处理原速视频 + 字幕框")
        
        quick_clips = []
        for i, sentence_data in tqdm(enumerate(sentences_data, 1), 
                                      total=len(sentences_data), 
                                      desc="渲染缩略版视频"):
            # 第一个句子从视频开头开始
            if i == 1:
                start_time = 0.0
            else:
                start_time = segments_info[i-1].get('start', 0)
            
            # 最后一个句子到视频结尾
            if i == len(sentences_data):
                end_time = video.duration
            else:
                # 其他句子使用下一个句子的开始时间
                end_time = segments_info[i].get('start', video.duration)
           
            processed_clip = self.process_sentence_video_quick(
                video, sentence_data, start_time, end_time
            )
            quick_clips.append(processed_clip)
        
        # 合并缩略版
        print("正在合并缩略版视频片段...")
        quick_video = concatenate_videoclips(quick_clips, method="compose")
        quick_video = quick_video.set_fps(config.FPS)
        
        # 导出缩略版（降低 FPS 加速）
        print(f"正在导出缩略版视频到 {quick_output_path}...")
        quick_video.write_videofile(
            quick_output_path,
            fps=config.FPS,
            codec='libx264',
            audio_codec='aac',
            audio_fps=config.AUDIO_FPS,
            preset='fast',
            bitrate='3000k'
        )
        quick_video.close()
        
        # ===== 生成学习版 (Full) =====
        print("\n" + "=" * 60)
        print("生成学习版视频...")
        print("=" * 60)
        
        print("学习版模式：使用提供的时间戳信息...")
        full_clips = []
        
        for i, (sentence_data, seg_info) in tqdm(enumerate(zip(sentences_data, segments_info)), total=len(sentences_data), desc="渲染学习版视频"):
            start_time = seg_info.get('start', 0)
            end_time = seg_info.get('end', video.duration)
            
            # 获取下一个句子的开始时间（用于确定当前句子的结束点）
            next_sentence_start = None
            if i + 1 < len(segments_info):
                next_sentence_start = segments_info[i + 1].get('start', None)
            
            processed_clip = self.process_sentence_video(
                video, sentence_data, start_time, end_time, next_sentence_start
            )
            # 调试信息
            # print(f"句子 {i+1}: start={start_time:.2f}, end={end_time:.2f}, next_start={next_sentence_start}, clip_duration={processed_clip.duration:.2f}")
            full_clips.append(processed_clip)
        
        # 合并学习版
        print("正在合并学习版视频片段...")
        full_video = concatenate_videoclips(full_clips, method="compose")
        full_video = full_video.set_fps(config.FPS)
        print("full_video duration:", full_video.duration)
        # 导出学习版（降低 FPS 加速）
        print(f"正在导出学习版视频到 {full_output_path}...")
        full_video.write_videofile(
            full_output_path,
            fps=config.FPS,
            codec='libx264',
            audio_codec='aac', 
            audio_fps=config.AUDIO_FPS,
            preset='fast',
            bitrate='3000k'
        )
        
        # 清理
        video.close()
        full_video.close()
        
        print("\n视频处理完成！")
        print(f"  缩略版: {quick_output_path}")
        print(f"  学习版: {full_output_path}")
        
        return {
            "quick": quick_output_path,
            "full": full_output_path
        }
