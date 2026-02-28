import os
import sys
import json
from datetime import datetime
from typing import List, Dict
from sentence_splitter import SentenceSplitter
from word_analyzer import WordAnalyzer
from video_processor import VideoProcessor
from markdown_exporter import MarkdownExporter
from audio_transcriber import AudioTranscriber
import config


class EnglishLearningVideoGenerator:
    def __init__(self):
        """初始化视频生成器"""
        print("=" * 60)
        print("英语学习视频自动化生成系统")
        print("=" * 60)
        
        self.splitter = SentenceSplitter()
        self.analyzer = WordAnalyzer()
        self.processor = VideoProcessor()
        self.exporter = MarkdownExporter()
        self.transcriber = AudioTranscriber(use_local=config.USE_LOCAL_WHISPER)
        
        # 创建必要的目录
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def _save_intermediate_result(self, content: str, filename: str) -> str:
        """保存中间结果到文件"""
        output_path = os.path.join(config.OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return output_path
    
    def _save_json_result(self, data: dict, filename: str) -> str:
        """保存JSON格式的中间结果"""
        output_path = os.path.join(config.OUTPUT_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path
    
    def _load_intermediate_result(self, filename: str) -> str:
        """加载中间结果文件"""
        output_path = os.path.join(config.OUTPUT_DIR, filename)
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"中间结果文件不存在: {output_path}")
        with open(output_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _load_json_result(self, filename: str) -> dict:
        """加载JSON格式的中间结果"""
        output_path = os.path.join(config.OUTPUT_DIR, filename)
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"中间结果文件不存在: {output_path}")
        with open(output_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_from_step(self, output_name: str, start_step: int, video_path: str) -> dict:
        """
        从指定步骤开始加载并处理
        
        Args:
            output_name: 输出文件名（与保存时一致）
            start_step: 起始步骤 (1=从句子加载, 2=从分析结果加载, 3=从markdown加载)
            video_path: 视频路径
            
        Returns:
            处理结果字典
        """
        if start_step == 1:
            # 加载步骤1的结果（分割后的句子）
            print(f"\n📂 从步骤1加载: {output_name}_1_sentences.txt")
            sentences_content = self._load_intermediate_result(f"{output_name}_1_sentences.txt")
            # 解析句子
            sentences = []
            for line in sentences_content.strip().split('\n'):
                if '. ' in line:
                    sentences.append(line.split('. ', 1)[1])
            
            print(f"✓ 加载了 {len(sentences)} 个句子")
            
            # 继续步骤2
            print("\n步骤 2/4: 分析句子并识别重难点单词...")
            print("-" * 60)
            sentences_data = self.analyzer.batch_analyze(sentences)
            print(f"✓ 完成 {len(sentences_data)} 个句子的分析")
            
            # 保存分析结果
            analysis_path = self._save_json_result(sentences_data, f"{output_name}_2_analysis.json")
            print(f"✓ 分析结果已保存: {analysis_path}")
            
            # 继续步骤3
            print("\n步骤 3/4: 生成Markdown文字稿...")
            print("-" * 60)
            markdown_path = self.exporter.export(sentences_data, f"{output_name}.md")
            print(f"✓ Markdown文字稿已保存: {markdown_path}")
            
            # 继续步骤4
            print("\n步骤 4/4: 处理视频...")
            print("-" * 60)
            video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
            
            # 根据配置选择使用新版或旧版视频合成器
            if config.USE_NEW_COMPOSER:
                print("使用新版现代风格视频合成器")
                final_video_path = self.composer.process_full_video(
                    video_path, sentences_data, video_output_path
                )
            else:
                print("使用旧版视频合成器")
                final_video_path = self.processor.process_full_video(
                    video_path, sentences_data, video_output_path
                )
            print(f"✓ 视频已保存: {final_video_path}")
            
            return {
                'video_path': final_video_path,
                'markdown_path': markdown_path,
                'sentences_count': len(sentences_data)
            }
        
        elif start_step == 2:
            # 加载步骤2的结果（分析结果JSON）
            print(f"\n📂 从步骤2加载: {output_name}_2_analysis.json")
            sentences_data = self._load_json_result(f"{output_name}_2_analysis.json")
            print(f"✓ 加载了 {len(sentences_data)} 个句子的分析结果")
            
            # 尝试加载时间戳信息
            segments_info = None
            segments_path = os.path.join(config.OUTPUT_DIR, f"{output_name}_segments.json")
            if os.path.exists(segments_path):
                print("✓ 发现时间戳信息")
                segments_info = self._load_json_result(f"{output_name}_segments.json")
            else:
                print("⚠️  未发现时间戳信息，将根据视频时长平均分配")
            
            # 继续步骤3
            print("\n步骤 3/4: 生成Markdown文字稿...")
            print("-" * 60)
            markdown_path = self.exporter.export(sentences_data, f"{output_name}.md")
            print(f"✓ Markdown文字稿已保存: {markdown_path}")
            
            # 继续步骤4
            print("\n步骤 4/4: 处理视频...")
            print("-" * 60)
            video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
            
            final_video_path = self.processor.process_full_video(
                video_path, sentences_data, video_output_path, segments_info
            )
            print(f"✓ 视频已保存: {final_video_path}")
            
            return {
                'video_path': final_video_path,
                'markdown_path': markdown_path,
                'sentences_count': len(sentences_data)
            }
        
        elif start_step == 3:
            # 加载步骤2的结果来生成视频
            print(f"\n📂 从步骤3加载: {output_name}_2_analysis.json")
            sentences_data = self._load_json_result(f"{output_name}_2_analysis.json")
            print(f"✓ 加载了 {len(sentences_data)} 个句子的分析结果")
            
            # 尝试加载时间戳信息
            segments_info = None
            segments_path = os.path.join(config.OUTPUT_DIR, f"{output_name}_segments.json")
            if os.path.exists(segments_path):
                print("✓ 发现时间戳信息")
                segments_info = self._load_json_result(f"{output_name}_segments.json")
            else:
                print("⚠️  未发现时间戳信息，将根据视频时长平均分配")
            
            # 直接步骤4
            print("\n步骤 4/4: 处理视频...")
            print("-" * 60)
            video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
            
            # 根据配置选择使用新版或旧版视频合成器
            if config.USE_NEW_COMPOSER:
                print("使用新版现代风格视频合成器")
                final_video_path = self.composer.process_full_video(
                    video_path, sentences_data, video_output_path, segments_info
                )
            else:
                print("使用旧版视频合成器")
                final_video_path = self.processor.process_full_video(
                    video_path, sentences_data, video_output_path, segments_info
                )
            print(f"✓ 视频已保存: {final_video_path}")
            
            return {
                'video_path': final_video_path,
                'sentences_count': len(sentences_data)
            }
        
        else:
            raise ValueError("start_step 必须是 1, 2 或 3")
    
    def generate_from_text_and_video(self, text: str, video_path: str, 
                                    output_name: str = None) -> dict:
        """
        从文本和视频生成学习视频
        
        Args:
            text: 英文新闻文本
            video_path: 原始视频路径
            output_name: 输出文件名（不含扩展名）
            
        Returns:
            包含输出路径的字典
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"learning_video_{timestamp}"
        
        # ===== 步骤 0: 保存原始文本 =====
        print("\n步骤 0/4: 保存原始文本...")
        print("-" * 60)
        raw_text_path = self._save_intermediate_result(text, f"{output_name}_0_raw_text.txt")
        print(f"✓ 原始文本已保存: {raw_text_path}")
        
        # ===== 步骤 1: 分割句子 =====
        print("\n步骤 1/4: 分割句子...")
        print("-" * 60)
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        
        # 保存分割后的句子
        sentences_content = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])
        sentences_path = self._save_intermediate_result(sentences_content, f"{output_name}_1_sentences.txt")
        print(f"✓ 句子已保存: {sentences_path}")
        
        for i, sentence in enumerate(sentences, 1):
            print(f"  {i}. {sentence[:50]}{'...' if len(sentence) > 50 else ''}")
        
        # ===== 步骤 2: 分析句子 =====
        print("\n步骤 2/4: 分析句子并识别重难点单词...")
        print("-" * 60)
        sentences_data = self.analyzer.batch_analyze(sentences)
        print(f"✓ 完成 {len(sentences_data)} 个句子的分析")
        
        # 保存分析结果为JSON
        analysis_path = self._save_json_result(sentences_data, f"{output_name}_2_analysis.json")
        print(f"✓ 分析结果已保存: {analysis_path}")
        
        # ===== 步骤 3: 生成Markdown =====
        print("\n步骤 3/4: 生成Markdown文字稿...")
        print("-" * 60)
        markdown_path = self.exporter.export(
            sentences_data, 
            f"{output_name}.md"
        )
        print(f"✓ Markdown文字稿已保存: {markdown_path}")
        
        # ===== 步骤 4: 处理视频 =====
        print("\n步骤 4/4: 处理视频...")
        print("-" * 60)
        video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
        
        # 根据配置选择使用新版或旧版视频合成器
        if config.USE_NEW_COMPOSER:
            print("使用新版现代风格视频合成器")
            final_video_path = self.composer.process_full_video(
                video_path,
                sentences_data,
                video_output_path
            )
        else:
            print("使用旧版视频合成器")
            final_video_path = self.processor.process_full_video(
                video_path,
                sentences_data,
                video_output_path
            )
        print(f"✓ 视频已保存: {final_video_path}")
        
        print("\n" + "=" * 60)
        print("✓ 所有任务完成！")
        print("=" * 60)
        
        return {
            'video_path': final_video_path,
            'markdown_path': markdown_path,
            'sentences_count': len(sentences_data),
            'intermediate_files': {
                'raw_text': raw_text_path,
                'sentences': sentences_path,
                'analysis': analysis_path
            }
        }
    
    def generate_from_video_only(self, video_path: str, output_name: str = None) -> dict:
        """
        仅从视频生成学习视频（自动提取音频并转录）
        
        Args:
            video_path: 原始视频路径
            output_name: 输出文件名（不含扩展名）
            
        Returns:
            包含输出路径的字典
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"learning_video_{timestamp}"
        
        print("\n步骤 0/4: 从视频中提取文字...")
        print("-" * 60)
        
        # 1. 提取音频
        audio_path = self.transcriber.extract_audio_from_video(video_path)
        
        # 2. 使用带时间戳的转录（只加载一次模型）
        print("正在使用 Whisper 转录音频（带时间戳）...")
        transcription_result = self.transcriber.transcribe_audio_with_timestamps(audio_path)
        text = transcription_result["text"]
        segments = transcription_result.get("segments", [])
        
        print(f"✓ 提取的文字内容:\n{text[:200]}{'...' if len(text) > 200 else ''}\n")
        
        # 3. 分割句子
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        
        # 4. 从 segments 中提取单词级别时间戳
        print("正在解析每个句子的时间戳...")
        
        # 提取单词时间戳
        words_with_timestamps = []
        for segment in segments:
            words = segment.get("words", [])
            if words:
                # 有单词级别时间戳
                for word_info in words:
                    words_with_timestamps.append({
                        "word": word_info.get("word", ""),
                        "start": word_info.get("start", 0),
                        "end": word_info.get("end", 0)
                    })
            else:
                # 没有单词级别，使用段落级别
                words_with_timestamps.append({
                    "word": segment.get("text", ""),
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0)
                })
        
        if words_with_timestamps:
            sentence_timestamps = self.transcriber._group_words_to_sentences(words_with_timestamps, sentences)
        else:
            # 无法获取时间戳，使用平均分配
            sentence_timestamps = []
        
        if sentence_timestamps:
            print(f"✓ 获取了 {len(sentence_timestamps)} 个句子的时间戳")
            for i, ts in enumerate(sentence_timestamps[:5]):
                print(f"  句子 {i+1}: {ts['start']:.2f}s - {ts['end']:.2f}s")
            if len(sentence_timestamps) > 5:
                print(f"  ...")
        else:
            print("⚠️  无法获取时间戳，将使用平均分配")
        
        # 保存时间戳信息
        if sentence_timestamps:
            segments_path = self._save_json_result(sentence_timestamps, f"{output_name}_segments.json")
            print(f"✓ 时间戳信息已保存: {segments_path}")
        
        # 继续处理
        return self._generate_with_segments(text, video_path, output_name, sentence_timestamps)
    
    def _generate_with_segments(self, text: str, video_path: str, 
                               output_name: str, sentence_timestamps: List[Dict] = None) -> dict:
        """
        内部方法：带时间戳信息生成学习视频
        
        Args:
            text: 英文文本
            video_path: 视频路径
            output_name: 输出文件名
            sentence_timestamps: 句子时间戳列表
            
        Returns:
            处理结果字典
        """
        # ===== 步骤 1: 分割句子 =====
        print("\n步骤 1/4: 分割句子...")
        print("-" * 60)
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        
        # 保存分割后的句子
        sentences_content = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])
        sentences_path = self._save_intermediate_result(sentences_content, f"{output_name}_1_sentences.txt")
        print(f"✓ 句子已保存: {sentences_path}")
        
        for i, sentence in enumerate(sentences, 1):
            print(f"  {i}. {sentence[:50]}{'...' if len(sentence) > 50 else ''}")
        
        # ===== 步骤 2: 分析句子 =====
        print("\n步骤 2/4: 分析句子并识别重难点单词...")
        print("-" * 60)
        sentences_data = self.analyzer.batch_analyze(sentences)
        print(f"✓ 完成 {len(sentences_data)} 个句子的分析")
        
        # 保存分析结果为JSON
        analysis_path = self._save_json_result(sentences_data, f"{output_name}_2_analysis.json")
        print(f"✓ 分析结果已保存: {analysis_path}")
        
        # ===== 步骤 3: 生成Markdown =====
        print("\n步骤 3/4: 生成Markdown文字稿...")
        print("-" * 60)
        markdown_path = self.exporter.export(
            sentences_data, 
            f"{output_name}.md"
        )
        print(f"✓ Markdown文字稿已保存: {markdown_path}")
        
        # ===== 步骤 4: 处理视频 =====
        print("\n步骤 4/4: 处理视频...")
        print("-" * 60)
        
        # 使用句子时间戳
        segments_info = None
        if sentence_timestamps:
            # 直接使用句子时间戳
            segments_info = [{"start": ts.get("start", 0), "end": ts.get("end", 0)} for ts in sentence_timestamps]
        
        video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
    
        final_video_path = self.processor.process_full_video(
            video_path,
            sentences_data,
            video_output_path,
            segments_info
        )
        print(f"✓ 视频已保存: {final_video_path}")
        
        print("\n" + "=" * 60)
        print("✓ 所有任务完成！")
        print("=" * 60)
        
        return {
            'video_path': final_video_path,
            'markdown_path': markdown_path,
            'sentences_count': len(sentences_data)
        }
    
    def generate_from_text_file(self, text_file: str, video_path: str,
                               output_name: str = None) -> dict:
        """
        从文本文件和视频生成学习视频
        
        Args:
            text_file: 文本文件路径
            video_path: 原始视频路径
            output_name: 输出文件名（不含扩展名）
            
        Returns:
            包含输出路径的字典
        """
        if not os.path.exists(text_file):
            raise FileNotFoundError(f"文本文件不存在: {text_file}")
        
        print(f"正在读取文本文件: {text_file}")
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return self.generate_from_text_and_video(text, video_path, output_name)


def main():
    """主函数 - 自动处理配置文件中指定的视频"""
    print("\n欢迎使用英语学习视频自动化生成系统！\n")
    
    # 检查API密钥
    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == 'your_api_key_here':
        print("❌ 错误：请先在 .env 文件中设置 OPENAI_API_KEY")
        print("   1. 复制 .env.example 为 .env")
        print("   2. 在 .env 中填入你的 API Key")
        return
    
    # 从配置文件读取视频路径
    video_path = config.INPUT_VIDEO_PATH
    
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"❌ 错误：视频文件不存在: {video_path}")
        print(f"   请在 config.py 中设置正确的 INPUT_VIDEO_PATH")
        return
    
    print(f"📹 输入视频: {video_path}")
    print(f"📁 输出目录: {config.OUTPUT_DIR}")
    print("\n开始处理...\n")
    
    # ===== 测试模式配置 =====
    # 设置为 True 启用测试模式，从中间结果加载
    TEST_MODE = False
    TEST_OUTPUT_NAME = "learning_video_20260227_000130"  # 使用哪个输出的中间结果
    TEST_START_STEP = 2  # 从第几步开始: 1=从句子, 2=从分析结果, 3=直接生成视频
    
    # 生成视频
    try:
        generator = EnglishLearningVideoGenerator()
        
        if TEST_MODE:
            # 测试模式：从中间结果加载
            print("🔧 测试模式：从中间结果加载")
            print("=" * 60)
            result = generator.load_from_step(TEST_OUTPUT_NAME, TEST_START_STEP, video_path)
        else:
            # 正常模式：从视频提取文字
            result = generator.generate_from_video_only(video_path)
        
        print("\n" + "=" * 60)
        print("📊 生成结果统计")
        print("=" * 60)
        print(f"句子数量: {result['sentences_count']}")
        print(f"视频文件: {result['video_path']}")
        if 'markdown_path' in result:
            print(f"文字稿: {result['markdown_path']}")
        print("=" * 60)
        print("\n✅ 全部完成！您可以开始学习了！")
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

