"""
视频处理模块
使用MoviePy处理视频、添加字幕和单词框
"""
import os
from typing import List, Dict, Tuple
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, 
    TextClip, ColorClip, concatenate_videoclips
)
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import config


class VideoProcessor:
    def __init__(self):
        """初始化视频处理器"""
        # 创建输出目录
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    def create_subtitle_frame(self, english_text: str, chinese_text: str, 
                             width: int, height: int) -> np.ndarray:
        """
        创建美观的字幕框图像
        
        Args:
            english_text: 英文文本
            chinese_text: 中文文本
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 创建图像
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制渐变背景
        for y in range(height):
            alpha = int(230 * (1 - y / height * 0.3))  # 渐变透明度
            color = config.SUBTITLE_BG_COLOR + (alpha,)
            draw.rectangle([(0, y), (width, y + 1)], fill=color)
        
        # 绘制顶部装饰线
        draw.rectangle([(0, 0), (width, 4)], fill=config.COLOR_PRIMARY + (255,))
        
        # 加载字体
        try:
            font_en = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
            font_cn = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 38)
        except:
            font_en = ImageFont.load_default()
            font_cn = ImageFont.load_default()
        
        # 计算文本位置
        padding = 40
        en_y = padding + 20
        cn_y = height // 2 + 10
        
        # 绘制英文文本（带阴影效果）
        # 阴影
        draw.text((padding + 2, en_y + 2), english_text, 
                 font=font_en, fill=(0, 0, 0, 180))
        # 主文本
        draw.text((padding, en_y), english_text, 
                 font=font_en, fill=config.COLOR_PRIMARY + (255,))
        
        # 绘制中文文本（带阴影效果）
        # 阴影
        draw.text((padding + 2, cn_y + 2), chinese_text, 
                 font=font_cn, fill=(0, 0, 0, 180))
        # 主文本
        draw.text((padding, cn_y), chinese_text, 
                 font=font_cn, fill=config.COLOR_SECONDARY + (255,))
        
        # 转换为numpy数组
        return np.array(img)
    
    def create_word_box_frame(self, words: List[Dict], 
                             width: int, height: int) -> np.ndarray:
        """
        创建美观的单词框图像
        
        Args:
            words: 单词信息列表
            width: 宽度
            height: 高度
            
        Returns:
            numpy数组格式的图像
        """
        # 创建图像
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制背景
        bg_color = config.WORD_BOX_BG_COLOR + (230,)
        draw.rounded_rectangle([(10, 10), (width - 10, height - 10)], 
                              radius=20, fill=bg_color)
        
        # 绘制标题栏
        draw.rounded_rectangle([(10, 10), (width - 10, 70)], 
                              radius=20, fill=config.COLOR_ACCENT + (255,))
        
        # 加载字体
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            font_word = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
            font_phonetic = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
            font_trans = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
        except:
            font_title = ImageFont.load_default()
            font_word = ImageFont.load_default()
            font_phonetic = ImageFont.load_default()
            font_trans = ImageFont.load_default()
        
        # 绘制标题
        title = "📚 Key Words"
        draw.text((width // 2 - 80, 25), title, 
                 font=font_title, fill=(255, 255, 255, 255))
        
        # 绘制单词列表
        y_offset = 90
        padding = 25
        line_height = 85
        
        for i, word_info in enumerate(words[:6]):  # 最多显示6个单词
            word = word_info.get('word', '')
            phonetic = word_info.get('phonetic', '')
            translation = word_info.get('translation', '')
            
            # 单词序号背景
            circle_x = padding + 15
            circle_y = y_offset + 15
            draw.ellipse([(circle_x - 15, circle_y - 15), 
                         (circle_x + 15, circle_y + 15)],
                        fill=config.COLOR_PRIMARY + (255,))
            
            # 序号
            draw.text((circle_x - 8, circle_y - 12), str(i + 1), 
                     font=font_phonetic, fill=(0, 0, 0, 255))
            
            # 单词
            draw.text((padding + 45, y_offset), word, 
                     font=font_word, fill=config.COLOR_PRIMARY + (255,))
            
            # 音标
            draw.text((padding + 45, y_offset + 32), phonetic, 
                     font=font_phonetic, fill=config.COLOR_SECONDARY + (255,))
            
            # 中文释义
            draw.text((padding + 45, y_offset + 58), translation, 
                     font=font_trans, fill=config.COLOR_TEXT + (255,))
            
            y_offset += line_height
            
            # 如果空间不够，停止绘制
            if y_offset + line_height > height - 20:
                break
        
        return np.array(img)
    
    def process_sentence_video(self, video_clip: VideoFileClip, 
                               sentence_data: Dict,
                               start_time: float,
                               end_time: float) -> VideoFileClip:
        """
        处理单个句子的视频片段
        
        Args:
            video_clip: 原始视频片段
            sentence_data: 句子数据（包含翻译和单词）
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            处理后的视频片段
        """
        # 提取该句子的视频片段
        segment = video_clip.subclip(start_time, end_time)
        duration = end_time - start_time
        
        # 第一部分：原速无字幕播放
        part1 = segment.copy()
        
        # 第二部分：0.75倍速带字幕播放（播放2次）
        slow_segment = segment.fx(lambda clip: clip.speedx(config.SPEED_SLOW))
        slow_duration = duration / config.SPEED_SLOW
        
        # 创建字幕框
        subtitle_img = self.create_subtitle_frame(
            sentence_data['original_text'],
            sentence_data['chinese_translation'],
            config.VIDEO_WIDTH,
            config.SUBTITLE_HEIGHT
        )
        
        subtitle_clip = (ImageClip(subtitle_img)
                        .set_duration(slow_duration)
                        .set_position(('center', config.VIDEO_HEIGHT - config.SUBTITLE_HEIGHT)))
        
        # 创建单词框
        if sentence_data.get('key_words'):
            word_box_img = self.create_word_box_frame(
                sentence_data['key_words'],
                config.WORD_BOX_WIDTH,
                config.VIDEO_HEIGHT
            )
            
            word_box_clip = (ImageClip(word_box_img)
                           .set_duration(slow_duration)
                           .set_position((config.VIDEO_WIDTH - config.WORD_BOX_WIDTH, 0)))
            
            part2_single = CompositeVideoClip([slow_segment, subtitle_clip, word_box_clip])
        else:
            part2_single = CompositeVideoClip([slow_segment, subtitle_clip])
        
        # 重复两次
        part2 = concatenate_videoclips([part2_single, part2_single])
        
        # 第三部分：正常速度带字幕播放
        normal_subtitle_clip = subtitle_clip.set_duration(duration)
        
        if sentence_data.get('key_words'):
            normal_word_box_clip = word_box_clip.set_duration(duration)
            part3 = CompositeVideoClip([segment, normal_subtitle_clip, normal_word_box_clip])
        else:
            part3 = CompositeVideoClip([segment, normal_subtitle_clip])
        
        # 合并三个部分
        final_clip = concatenate_videoclips([part1, part2, part3])
        
        return final_clip
    
    def process_full_video(self, video_path: str, 
                          sentences_data: List[Dict],
                          output_path: str) -> str:
        """
        处理完整视频
        
        Args:
            video_path: 输入视频路径
            sentences_data: 所有句子的数据
            output_path: 输出视频路径
            
        Returns:
            输出视频路径
        """
        print("正在加载视频...")
        video = VideoFileClip(video_path)
        
        # 计算每个句子的时间段
        total_duration = video.duration
        total_chars = sum(len(s['original_text']) for s in sentences_data)
        
        processed_clips = []
        current_time = 0
        
        for i, sentence_data in enumerate(sentences_data, 1):
            print(f"正在处理句子 {i}/{len(sentences_data)}...")
            
            # 根据字符数比例分配时间
            char_ratio = len(sentence_data['original_text']) / total_chars
            segment_duration = total_duration * char_ratio
            end_time = min(current_time + segment_duration, total_duration)
            
            # 处理该句子
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


if __name__ == "__main__":
    # 测试代码
    processor = VideoProcessor()
    
    # 测试创建字幕框
    subtitle_img = processor.create_subtitle_frame(
        "Climate change is one of the most pressing issues of our time.",
        "气候变化是我们这个时代最紧迫的问题之一。",
        1920, 270
    )
    
    # 保存测试图像
    Image.fromarray(subtitle_img).save('test_subtitle.png')
    print("字幕框测试图像已保存")
    
    # 测试创建单词框
    test_words = [
        {"word": "climate", "phonetic": "/ˈklaɪmət/", "translation": "气候", "difficulty": 3},
        {"word": "pressing", "phonetic": "/ˈpresɪŋ/", "translation": "紧迫的", "difficulty": 4}
    ]
    
    word_box_img = processor.create_word_box_frame(test_words, 360, 1080)
    Image.fromarray(word_box_img).save('test_wordbox.png')
    print("单词框测试图像已保存")

