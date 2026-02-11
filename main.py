"""
英语学习视频自动化生成系统 - 主程序
"""
import os
import sys
from datetime import datetime
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
        self.transcriber = AudioTranscriber()
        
        # 创建必要的目录
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
    
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
        
        print("\n步骤 1/4: 分割句子...")
        print("-" * 60)
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        for i, sentence in enumerate(sentences, 1):
            print(f"  {i}. {sentence[:50]}{'...' if len(sentence) > 50 else ''}")
        
        print("\n步骤 2/4: 分析句子并识别重难点单词...")
        print("-" * 60)
        sentences_data = self.analyzer.batch_analyze(sentences)
        print(f"✓ 完成 {len(sentences_data)} 个句子的分析")
        
        print("\n步骤 3/4: 生成Markdown文字稿...")
        print("-" * 60)
        markdown_path = self.exporter.export(
            sentences_data, 
            f"{output_name}.md"
        )
        print(f"✓ Markdown文字稿已保存: {markdown_path}")
        
        print("\n步骤 4/4: 处理视频...")
        print("-" * 60)
        video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
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
            'sentences_count': len(sentences_data)
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
        
        print("\n步骤 0/4: 从视频中提取文字...")
        print("-" * 60)
        text = self.transcriber.transcribe_video(video_path)
        print(f"✓ 提取的文字内容:\n{text[:200]}{'...' if len(text) > 200 else ''}\n")
        
        return self.generate_from_text_and_video(text, video_path, output_name)
    
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
    
    # 生成视频
    try:
        generator = EnglishLearningVideoGenerator()
        
        # 从视频中自动提取文字并处理
        result = generator.generate_from_video_only(video_path)
        
        print("\n" + "=" * 60)
        print("📊 生成结果统计")
        print("=" * 60)
        print(f"句子数量: {result['sentences_count']}")
        print(f"视频文件: {result['video_path']}")
        print(f"文字稿: {result['markdown_path']}")
        print("=" * 60)
        print("\n✅ 全部完成！您可以开始学习了！")
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

