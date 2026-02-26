import os
import subprocess
import tempfile
import time
from typing import List, Dict, Optional
from moviepy.editor import (
    VideoFileClip, AudioFileClip, AudioClip, CompositeVideoClip, 
    concatenate_videoclips, concatenate_audioclips, ImageClip
)
from moviepy.video.fx.all import speedx
from PIL import Image
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
        self._debug_saved = False
    
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
        创建字幕框图像 - 使用 HTML + Chrome 渲染
        
        Args:
            english_text: 英文文本
            chinese_text: 中文文本
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
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
        创建单词框图像 - 使用 HTML + Chrome 渲染
        
        Args:
            words: 单词信息列表
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 创建临时输出路径
        temp_path = os.path.join(config.TEMP_DIR, f'wordbox_{int(time.time() * 1000000)}.png')
        
        # 使用 HTML 渲染器生成单词框图片
        success = self.html_renderer.render_wordbox(
            words, width, height, temp_path
        )
        
        if not success or not os.path.exists(temp_path):
            raise RuntimeError(f"HTML 单词框渲染失败！words: {[w.get('word', '') for w in words[:2]]}")
        
        # 读取渲染好的图片并转换为 numpy 数组
        img = Image.open(temp_path)
        result = np.array(img)
        
        # 保存第一个用于调试
        if not self._debug_saved:
            img.save(os.path.join(config.OUTPUT_DIR, 'debug_wordbox.png'))
            print(f"  ✅ 已保存单词框图片: {os.path.join(config.OUTPUT_DIR, 'debug_wordbox.png')}")
            self._debug_saved = True
        
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
    
    def process_sentence_video(self, video_clip: VideoFileClip, 
                               sentence_data: Dict,
                               start_time: float,
                               end_time: float,
                               next_sentence_start: Optional[float] = None) -> VideoFileClip:
        """
        处理单个句子的视频片段
        
        处理流程：
        1. 原速1.0x无字幕播放（从句子开始到下一句开始或句子结束）
        2. 0.75x速有字幕有单词框（从句子开始到句子结束）
        3. 1.0x速有字幕有单词框（从句子开始到下一句开始或句子结束）
        
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
        end_time += 0.1
        gap_end_time = next_sentence_start + 0.1 if next_sentence_start is not None else end_time
        gap_duration = gap_end_time - start_time
        
        # ===== 第1部分：原速无字幕播放 =====
        part1_segment = video_clip.subclip(start_time, gap_end_time)
        part1 = part1_segment.copy()
        
        # ===== 第2部分：0.75倍速有字幕有单词框 =====
        segment = video_clip.subclip(start_time, end_time)
        
        # 减速视频（去掉原音频）
        slow_video = segment.without_audio().fx(speedx, config.SPEED_SLOW)
        slow_duration = round(slow_video.duration, 2)
        slow_video = slow_video.subclip(0, slow_duration)
        
        # 获取原始视频尺寸
        orig_width, orig_height = slow_video.size
        
        # 使用 FFmpeg atempo 减速音频（保持音调不变）
        original_audio = segment.audio
        slowed_audio = self._slow_audio_with_pitch_preservation(original_audio, config.SPEED_SLOW, slow_duration)
        
        # 字幕框和单词框尺寸
        # 字幕框：占据下1/3，底部留边距
        subtitle_box_height = int(orig_height * 0.33)  # 下1/3
        subtitle_margin = int(orig_height * 0.005)  # 底部边距 1%
        subtitle_box_width = int(orig_width * 0.95)  # 宽度为视频的95%
        
        # 单词框：右上角，不与字幕框重叠
        word_box_width = int(orig_width * 0.25)  # 宽度25%
        word_box_height = int(orig_height * 0.64)  # 高度64%（足够放下6个单词）
        word_box_margin = int(orig_width * 0.005)  # 右边和顶部边距 0.5%
        
        # 创建字幕框
        subtitle_img = self.create_subtitle_frame(
            sentence_data['original_text'],
            sentence_data['chinese_translation'],
            subtitle_box_width,
            subtitle_box_height
        )
        
        # 转换为 ImageClip - 字幕框在底部居中
        # 使用 RGBA 模式保持透明度
        subtitle_arr = np.array(subtitle_img)
        if subtitle_arr.shape[2] == 4:  # 如果有 alpha 通道
            subtitle_clip = (ImageClip(subtitle_arr, duration=slow_duration)
                            .set_position(('center', orig_height - subtitle_box_height - subtitle_margin)))
        else:
            # 没有 alpha 通道则用 RGB
            subtitle_clip = (ImageClip(subtitle_arr[:, :, :3], duration=slow_duration)
                            .set_position(('center', orig_height - subtitle_box_height - subtitle_margin)))
        
        # 创建单词框
        if sentence_data.get('key_words'):
            word_box_img = self.create_word_box_frame(
                sentence_data['key_words'],
                word_box_width,
                word_box_height
            )
            
            # 使用 RGBA 模式保持透明度
            word_box_x = orig_width - word_box_width - word_box_margin
            word_box_y = word_box_margin
            word_box_arr = np.array(word_box_img)
            if word_box_arr.shape[2] == 4:  # 如果有 alpha 通道
                word_box_clip = (ImageClip(word_box_arr, duration=slow_duration)
                               .set_position((word_box_x, word_box_y)))
            else:
                word_box_clip = (ImageClip(word_box_arr[:, :, :3], duration=slow_duration)
                               .set_position((word_box_x, word_box_y)))
            
            part2 = CompositeVideoClip([slow_video, subtitle_clip, word_box_clip])
        else:
            part2 = CompositeVideoClip([slow_video, subtitle_clip])
        
        # 添加减速后的音频
        if slowed_audio:
            part2 = part2.set_audio(slowed_audio)
        
        # ===== 第3部分：正常速度有字幕有单词框 =====
        normal_subtitle_clip = subtitle_clip.set_duration(gap_duration)
        
        if sentence_data.get('key_words'):
            normal_word_box_clip = word_box_clip.set_duration(gap_duration)
            part3 = CompositeVideoClip([part1_segment, normal_subtitle_clip, normal_word_box_clip])
        else:
            part3 = CompositeVideoClip([part1_segment, normal_subtitle_clip])
        
        # 合并三个部分，part2 播放两遍
        final_clip = concatenate_videoclips([part1, part2, part2, part3])
        
        return final_clip
    
    def process_full_video(self, video_path: str, 
                          sentences_data: List[Dict],
                          output_path: str,
                          segments_info: Optional[List[Dict]] = None) -> str:
        """
        处理完整视频
        
        Args:
            video_path: 输入视频路径
            sentences_data: 所有句子的数据
            output_path: 输出视频路径
            segments_info: 片段时间信息列表
            
        Returns:
            输出视频路径
        """
        print("正在加载视频...")
        video = VideoFileClip(video_path)
        
        if segments_info is not None and len(segments_info) == len(sentences_data):
            print("使用提供的时间戳信息分割视频...")
            processed_clips = []
            
            for i, (sentence_data, seg_info) in enumerate(zip(sentences_data, segments_info), 1):
                print(f"正在处理句子 {i}/{len(sentences_data)}...")
                
                start_time = seg_info.get('start', 0)
                end_time = seg_info.get('end', video.duration)
                
                next_sentence_start = None
                if i < len(segments_info):
                    next_sentence_start = segments_info[i].get('start', None)
                
                processed_clip = self.process_sentence_video(
                    video, sentence_data, start_time, end_time, next_sentence_start
                )
                processed_clips.append(processed_clip)
        else:
            print("未提供时间信息，根据视频时长平均分配...")
            total_duration = video.duration
            
            processed_clips = []
            current_time = 0
            
            for i, sentence_data in enumerate(sentences_data, 1):
                print(f"正在处理句子 {i}/{len(sentences_data)}...")
                
                total_chars = sum(len(s['original_text']) for s in sentences_data)
                char_ratio = len(sentence_data['original_text']) / total_chars
                segment_duration = total_duration * char_ratio
                end_time = min(current_time + segment_duration, total_duration)
                
                processed_clip = self.process_sentence_video(
                    video, sentence_data, current_time, end_time
                )
                processed_clips.append(processed_clip)
                
                current_time = end_time
        
        # 合并所有片段
        print("正在合并视频片段...")
        final_video = concatenate_videoclips(processed_clips)
        
        # 导出视频
        print(f"正在导出视频到 {output_path}...")
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=config.FPS,
            preset='medium'
        )
        
        # 清理
        video.close()
        final_video.close()
        
        print("视频处理完成！")
        return output_path
