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
        
        self.splitter = SentenceSplitter(
            max_words=config.MAX_SENTENCE_WORDS,
            min_words=config.MIN_SENTENCE_WORDS
        )
        self.analyzer = WordAnalyzer()
        self.processor = VideoProcessor()
        self.exporter = MarkdownExporter()
        # 使用本地 Whisper 模型（支持单词级别时间戳）
        self.transcriber = AudioTranscriber()
        
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
    
    def _cleanup_temp_files(self):
        """清理临时音频文件"""
        import glob
        
        temp_dir = config.TEMP_DIR
        if not os.path.exists(temp_dir):
            return
        
        # 删除临时音频文件
        audio_files = glob.glob(os.path.join(temp_dir, "*.mp3")) + \
                      glob.glob(os.path.join(temp_dir, "*.wav"))
        
        for audio_file in audio_files:
            try:
                os.remove(audio_file)
                print(f"🗑️ 已删除临时文件: {os.path.basename(audio_file)}")
            except Exception as e:
                print(f"⚠️ 删除临时文件失败: {audio_file}, {e}")
    
    def _organize_output_files(self, output_name: str):
        """
        整理输出文件：创建视频名文件夹，移动并重命名文件
        
        - 创建以视频名字命名的文件夹
        - 将生成的mp4和md文件移动到该文件夹
        - 重命名规则：
          - *_full.mp4 -> 逐句精听.mp4
          - *_quick.mp4 -> 翻译速览.mp4
          - *.md -> 保持原名
        """
        import glob
        import shutil
        
        output_dir = config.OUTPUT_DIR
        if not os.path.exists(output_dir):
            print(f"⚠️ 输出目录不存在: {output_dir}")
            return
        
        # 创建以视频名字命名的文件夹
        video_folder = os.path.join(output_dir, output_name)
        os.makedirs(video_folder, exist_ok=True)
        # print(f"📂 已创建输出文件夹: {output_name}")
        
        # 查找需要移动的文件
        # mp4 文件 (full 和 quick 版本)
        full_video = os.path.join(output_dir, f"{output_name}_full.mp4")
        quick_video = os.path.join(output_dir, f"{output_name}_quick.mp4")
        
        # md 文件
        md_file = os.path.join(output_dir, f"{output_name}.md")
        
        # 移动并重命名文件
        # 1. 移动 full 视频 -> 逐句精听.mp4
        if os.path.exists(full_video):
            target_full = os.path.join(video_folder, "逐句精听.mp4")
            shutil.move(full_video, target_full)
            # print(f"✓ 已移动: {output_name}_full.mp4 -> 逐句精听.mp4")
        
        # 2. 移动 quick 视频 -> 翻译速览.mp4
        if os.path.exists(quick_video):
            target_quick = os.path.join(video_folder, "翻译速览.mp4")
            shutil.move(quick_video, target_quick)
            # print(f"✓ 已移动: {output_name}_quick.mp4 -> 翻译速览.mp4")
        
        # 3. 移动 md 文件 (保持原名)
        if os.path.exists(md_file):
            target_md = os.path.join(video_folder, f"{output_name}.md")
            shutil.move(md_file, target_md)
            # print(f"✓ 已移动: {output_name}.md")
        
        print(f"✅ 文件整理完成，所有文件已保存到: {video_folder}")
    
    def _cleanup_intermediate_files(self, output_name: str):
        """删除中间结果文件（txt, segments.json, analysis.json）"""
        import glob
        
        # 删除句子 txt 文件
        txt_pattern = os.path.join(config.OUTPUT_DIR, f"{output_name}_*.txt")
        for f in glob.glob(txt_pattern):
            try:
                os.remove(f)
                print(f"🗑️ 已删除中间文件: {os.path.basename(f)}")
            except Exception as e:
                print(f"⚠️ 删除中间文件失败: {f}, {e}")
        
        # 删除 segments.json
        segments_file = os.path.join(config.OUTPUT_DIR, f"{output_name}_segments.json")
        if os.path.exists(segments_file):
            try:
                os.remove(segments_file)
                print(f"🗑️ 已删除中间文件: {os.path.basename(segments_file)}")
            except Exception as e:
                print(f"⚠️ 删除中间文件失败: {segments_file}, {e}")
        
        # 删除 analysis.json
        analysis_file = os.path.join(config.OUTPUT_DIR, f"{output_name}_2_analysis.json")
        if os.path.exists(analysis_file):
            try:
                os.remove(analysis_file)
                print(f"🗑️ 已删除中间文件: {os.path.basename(analysis_file)}")
            except Exception as e:
                print(f"⚠️ 删除中间文件失败: {analysis_file}, {e}")
    
    
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
                video_paths = self.composer.process_full_video(
                    video_path, sentences_data, video_output_path
                )
            else:
                print("使用旧版视频合成器")
                video_paths = self.processor.process_full_video(
                    video_path, sentences_data, video_output_path
                )
            
            # 删除中间文件
            self._cleanup_intermediate_files(output_name)
            
            print(f"✓ 缩略版视频已保存: {video_paths['quick']}")
            print(f"✓ 学习版视频已保存: {video_paths['full']}")
            
            # 清理临时音频文件
            self._cleanup_temp_files()
            
            # 整理输出文件：创建文件夹并重命名
            self._organize_output_files(output_name)
            
            # 构建新的文件路径（在新文件夹中）
            new_video_folder = os.path.join(config.OUTPUT_DIR, output_name)
            
            return {
                'video_path': os.path.join(new_video_folder, "逐句精听.mp4"),
                'video_paths': {
                    'full': os.path.join(new_video_folder, "逐句精听.mp4"),
                    'quick': os.path.join(new_video_folder, "翻译速览.mp4")
                },
                'markdown_path': os.path.join(new_video_folder, f"{output_name}.md"),
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
            
            video_paths = self.processor.process_full_video(
                video_path, sentences_data, video_output_path, segments_info
            )
            
            # 删除中间文件
            self._cleanup_intermediate_files(output_name)
            
            print(f"✓ 缩略版视频已保存: {video_paths['quick']}")
            print(f"✓ 学习版视频已保存: {video_paths['full']}")
            
            # 清理临时音频文件
            self._cleanup_temp_files()
            
            # 整理输出文件：创建文件夹并重命名
            self._organize_output_files(output_name)
            
            # 构建新的文件路径（在新文件夹中）
            new_video_folder = os.path.join(config.OUTPUT_DIR, output_name)
            
            return {
                'video_path': os.path.join(new_video_folder, "逐句精听.mp4"),
                'video_paths': {
                    'full': os.path.join(new_video_folder, "逐句精听.mp4"),
                    'quick': os.path.join(new_video_folder, "翻译速览.mp4")
                },
                'markdown_path': os.path.join(new_video_folder, f"{output_name}.md"),
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
            
            video_paths = self.processor.process_full_video(
                video_path, sentences_data, video_output_path, segments_info
            )
            
            # 删除中间文件
            self._cleanup_intermediate_files(output_name)
            
            print(f"✓ 缩略版视频已保存: {video_paths['quick']}")
            print(f"✓ 学习版视频已保存: {video_paths['full']}")
            
            # 清理临时音频文件
            self._cleanup_temp_files()
            
            # 整理输出文件：创建文件夹并重命名
            self._organize_output_files(output_name)
            
            # 构建新的文件路径（在新文件夹中）
            new_video_folder = os.path.join(config.OUTPUT_DIR, output_name)
            
            return {
                'video_path': os.path.join(new_video_folder, "逐句精听.mp4"),
                'video_paths': {
                    'full': os.path.join(new_video_folder, "逐句精听.mp4"),
                    'quick': os.path.join(new_video_folder, "翻译速览.mp4")
                },
                'sentences_count': len(sentences_data)
            }
        
        else:
            raise ValueError("start_step 必须是 1, 2 或 3")
    
   
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
        
        # 从视频路径提取文件名作为基础名（去掉扩展名）
        video_filename = os.path.splitext(os.path.basename(video_path))[0]
        
        if output_name is None:
            output_name = video_filename
        
        print("\n步骤 0/5: 从视频中提取音频...")
        print("-" * 60)
        
        # 1. 提取音频
        audio_path = self.transcriber.extract_audio_from_video(video_path)
        
        # 2. 使用本地 Whisper 模型一次性转录（带单词时间戳）
        print("\n步骤 1/5: 转录音频并获取时间戳...")
        print("-" * 60)
        
        # 一次性转录获取文本和单词时间戳（带进度条）
        transcription = self.transcriber.transcribe_once_with_word_timestamps(audio_path)
        text = transcription["text"]
        
        # print(f"✓ 提取的文字内容:\n{text}\n")
        
        # 3. 分割句子
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        
        # 4. 对齐句子时间戳
        # 直接用用户分割的句子列表和单词时间戳对齐
        print("正在获取每个句子的时间戳...")
        
        sentence_timestamps = self.transcriber.align_sentences_to_timestamps(
            audio_path, 
            sentences,
            output_name
        )
        
        # 继续处理
        return self._generate_with_segments(audio_path, video_path, output_name, sentence_timestamps, sentences)
    
    def _generate_with_segments(self, audio_path: str, video_path: str, 
                               output_name: str, sentence_timestamps: List[Dict] = None,
                               sentences: List[str] = None) -> dict:
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
        print("\n步骤 2/5: 分割句子...")
        print("-" * 60)
        
        # 如果已经分割好了句子（从 generate_from_video 传入），就直接使用
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        
        # 保存分割后的句子
        sentences_content = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])
        sentences_path = self._save_intermediate_result(sentences_content, f"{output_name}_1_sentences.txt")
        print(f"✓ 句子已保存: {sentences_path}")
        
        # ===== 步骤 2: 分析句子 ====
        print("\n步骤 3/5: 分析句子并识别重难点单词...")
        print("-" * 60)
        sentences_data = self.analyzer.batch_analyze(sentences)
        print(f"✓ 完成 {len(sentences_data)} 个句子的分析")
        
        # 保存分析结果为JSON
        analysis_path = self._save_json_result(sentences_data, f"{output_name}_2_analysis.json")
        print(f"✓ 分析结果已保存: {analysis_path}")
        
        # ===== 步骤 3: 生成Markdown =====
        print("\n步骤 4/5: 生成Markdown文字稿...")
        print("-" * 60)
        markdown_path = self.exporter.export(
            sentences_data, 
            f"{output_name}.md"
        )
        print(f"✓ Markdown文字稿已保存: {markdown_path}")
        
        # ===== 步骤 4: 处理视频 =====
        print("\n步骤 5/5: 处理视频...")
        print("-" * 60)
        
        # 使用句子时间戳
        segments_info = None
        if sentence_timestamps:
            # 直接使用句子时间戳
            segments_info = [{"start": ts.get("start", 0), "end": ts.get("end", 0)} for ts in sentence_timestamps]
        
        video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
    
        video_paths = self.processor.process_full_video(
            video_path,
            sentences_data,
            video_output_path,
            segments_info
        )
        
        # 删除中间文件
        self._cleanup_intermediate_files(output_name)
        
        print(f"✓ 缩略版视频已保存: {video_paths['quick']}")
        print(f"✓ 学习版视频已保存: {video_paths['full']}")
        
        # 清理临时音频文件
        self._cleanup_temp_files()
        
        # 整理输出文件：创建文件夹并重命名
        self._organize_output_files(output_name)
        
        print("\n" + "=" * 60)
        print("✓ 所有任务完成！")
        print("=" * 60)
        
        # 构建新的文件路径（在新文件夹中）
        new_video_folder = os.path.join(config.OUTPUT_DIR, output_name)
        
        return {
            'video_path': os.path.join(new_video_folder, "逐句精听.mp4"),  # 主要返回学习版
            'video_paths': {
                'full': os.path.join(new_video_folder, "逐句精听.mp4"),
                'quick': os.path.join(new_video_folder, "翻译速览.mp4")
            },
            'markdown_path': os.path.join(new_video_folder, f"{output_name}.md"),
            'sentences_count': len(sentences_data)
        }
    
  

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

    print("\n开始处理...\n")
    
    # ===== 测试模式配置 =====
    # 设置为 True 启用测试模式，从中间结果加载
    TEST_MODE = True
    TEST_OUTPUT_NAME = "How Anthropic Became The First U.S. Company To Be Designated As A Supply Chain Risk"  # 使用哪个输出的中间结果
    TEST_START_STEP =3  # 从第几步开始: 1=从句子, 2=从分析结果, 3=直接生成视频
    
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
        if 'video_paths' in result:
            print(f"缩略版视频: {result['video_paths']['quick']}")
            print(f"学习版视频: {result['video_paths']['full']}")
        else:
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

