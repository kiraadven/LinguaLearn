import os
import sys
import shutil
from sentence_splitter import SentenceSplitter
from word_analyzer import WordAnalyzer
from video_processor import VideoProcessor
from markdown_exporter import MarkdownExporter
from audio_transcriber import AudioTranscriber
import config


class LinguaLearnGenerator:
    def __init__(self):
        src = getattr(config, 'SOURCE_LANGUAGE', 'en')
        tgt = getattr(config, 'TARGET_LANGUAGE', 'zh')
        lang_names = getattr(config, 'LANGUAGE_DISPLAY_NAMES', {})
        src_name = lang_names.get(src, {}).get(tgt, src)
        tgt_native = getattr(config, 'LANGUAGE_NATIVE_NAMES', {}).get(tgt, tgt)
        print("=" * 60)
        print(f"语言学习视频自动化生成系统")
        print(f"学习模式: {src_name} → {tgt_native}")
        print("=" * 60)

        self.splitter = SentenceSplitter(
            max_words=config.MAX_SENTENCE_WORDS,
            min_words=config.MIN_SENTENCE_WORDS,
            source_lang=src
        )
        self.analyzer = WordAnalyzer(source_lang=src, target_lang=tgt)
        self.processor = VideoProcessor()
        self.exporter = MarkdownExporter(source_lang=src, target_lang=tgt)
        self.transcriber = AudioTranscriber(source_lang=src)

        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def generate(self, video_path: str, output_name: str = None) -> dict:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        if output_name is None:
            output_name = os.path.splitext(os.path.basename(video_path))[0]

        print("\n步骤 1/5: 提取音频并转录...")
        print("-" * 60)
        audio_path = self.transcriber.extract_audio_from_video(video_path)
        transcription = self.transcriber.transcribe_once_with_word_timestamps(audio_path)
        text = transcription["text"]

        print("\n步骤 2/5: 分割句子...")
        print("-" * 60)
        sentences = self.splitter.split_text(text)
        print(f"✓ 成功分割为 {len(sentences)} 个句子")
        sentence_timestamps = self.transcriber.align_sentences_to_timestamps(
            audio_path, sentences, output_name
        )

        print("\n步骤 3/5: 分析句子并识别重难点单词...")
        print("-" * 60)
        sentences_data = self.analyzer.batch_analyze(sentences)
        print(f"✓ 完成 {len(sentences_data)} 个句子的分析")

        print("\n步骤 4/5: 生成Markdown文字稿...")
        print("-" * 60)
        markdown_path = self.exporter.export(sentences_data, f"{output_name}.md")
        print(f"✓ Markdown文字稿已保存: {markdown_path}")

        print("\n步骤 5/5: 处理视频...")
        print("-" * 60)
        segments_info = [{"start": ts.get("start", 0), "end": ts.get("end", 0)} for ts in sentence_timestamps]
        video_output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")

        self.processor.process_full_video(
            video_path, sentences_data, video_output_path, segments_info
        )

        output_folder = os.path.join(config.OUTPUT_DIR, output_name)
        os.makedirs(output_folder, exist_ok=True)

        full_video = os.path.join(config.OUTPUT_DIR, f"{output_name}_full.mp4")
        final_video = os.path.join(output_folder, "学习版.mp4")
        md_dst = os.path.join(output_folder, f"{output_name}.md")

        if os.path.exists(full_video):
            shutil.move(full_video, final_video)
        if os.path.exists(markdown_path):
            shutil.move(markdown_path, md_dst)

        import glob
        for f in glob.glob(os.path.join(config.TEMP_DIR, "*.mp3")) + \
                 glob.glob(os.path.join(config.TEMP_DIR, "*.wav")):
            try:
                os.remove(f)
            except Exception:
                pass

        print(f"\n✅ 完成！输出目录: {output_folder}")
        return {
            'video_path': final_video,
            'markdown_path': md_dst,
            'sentences_count': len(sentences_data),
        }


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py <视频路径> [输出名称]")
        print("示例: python main.py video.mp4 my_lesson")
        sys.exit(1)

    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == 'your_api_key_here':
        print("❌ 错误：请先在 .env 文件中设置 OPENAI_API_KEY")
        sys.exit(1)

    video_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        generator = LinguaLearnGenerator()
        result = generator.generate(video_path, output_name)
        print("\n" + "=" * 60)
        print(f"句子数量: {result['sentences_count']}")
        print(f"视频文件: {result['video_path']}")
        print(f"文字稿:   {result['markdown_path']}")
        print("=" * 60)
    except Exception as e:
        import traceback
        print(f"\n❌ 错误：{e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
