import os
import re
from typing import List, Dict
from moviepy.editor import VideoFileClip
import config

# 尝试导入 tqdm 用于进度条
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# 尝试导入 difflib 用于模糊匹配
try:
    from difflib import SequenceMatcher
    HAS_DIFFLIB = True
except ImportError:
    HAS_DIFFLIB = False


class AudioTranscriber:
    def __init__(self):
        """
        初始化音频转文字器（仅使用本地 Whisper 模型）
        
        Args:
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
        """
        self.model_size = config.WHISPER_MODEL_SIZE
        
        import whisper
        self.whisper_model = whisper.load_model(self.model_size)
      
        # 创建临时目录
        os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    def extract_audio_from_video(self, video_path: str) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            音频文件路径
        """
        print("正在从视频中提取音频...")
        
        video = VideoFileClip(video_path)
        audio_path = os.path.join(config.TEMP_DIR, "extracted_audio.mp3")
        
        # 提取音频并保存为MP3
        video.audio.write_audiofile(audio_path, codec='mp3', verbose=False, logger=None)
        video.close()
        
        print(f"✓ 音频已提取到: {audio_path}")
        return audio_path
    
  
    
   
    def _transcribe_local(self, audio_path: str) -> str:
        """
        使用本地 Whisper 模型转录
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        print("正在使用本地 Whisper 模型转录音频...")
        
        try:
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False
            )
            
            text = result["text"].strip()
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            return text
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def transcribe_once_with_word_timestamps(self, audio_path: str) -> dict:
        """
        使用 Whisper 一次性转录音频并获取词级时间戳
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含 text 和 word_timestamps 的字典
        """
        print("正在使用 Whisper 转录音频（带词级时间戳）...")
        
        try:
            # 使用 Whisper 的词级时间戳功能
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False,
                word_timestamps=True  # 启用词级时间戳
            )
            
            text = result["text"].strip()
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            
            # 提取词级时间戳
            word_timestamps = []
            if "words" in result:
                for word_info in result["words"]:
                    word_timestamps.append({
                        "word": word_info.get("word", "").strip(),
                        "start": word_info.get("start", 0),
                        "end": word_info.get("end", 0),
                        "probability": word_info.get("probability", 0)
                    })
            
            return {
                "text": text,
                "word_timestamps": word_timestamps
            }
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def _normalize_text(self, text: str) -> str:
        """
        标准化文本用于匹配（转小写、去除标点、多个空格变一个）
        
        Args:
            text: 原始文本
            
        Returns:
            标准化后的文本
        """
        # 转小写
        text = text.lower()
        # 去除标点符号，保留字母、数字和空格
        text = re.sub(r'[^\w\s]', '', text)
        # 多个空格变一个
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _find_word_indices_in_transcription(self, sentence: str, word_timestamps: list) -> tuple:
        """
        在转录的词级时间戳中找到句子对应的词索引范围
        
        使用模糊匹配来找到最佳匹配位置
        
        Args:
            sentence: 要匹配的句子
            word_timestamps: 词级时间戳列表
            
        Returns:
            (start_index, end_index) 或 (None, None)
        """
        # 标准化句子
        sentence_normalized = self._normalize_text(sentence)
        
        if not sentence_normalized or not word_timestamps:
            return None, None
        
        # 构建转录文本的词列表（标准化后）
        transcription_words = [self._normalize_text(w["word"]) for w in word_timestamps]
        sentence_words = sentence_normalized.split()
        
        if not sentence_words:
            return None, None
        
        # 使用滑动窗口寻找最佳匹配
        best_match = None
        best_score = 0
        
        for i in range(len(transcription_words) - len(sentence_words) + 1):
            # 构建窗口内的文本
            window = transcription_words[i:i + len(sentence_words)]
            window_text = ' '.join(window)
            
            # 计算相似度
            if HAS_DIFFLIB:
                score = SequenceMatcher(None, window_text, sentence_normalized).ratio()
            else:
                # 简单的词匹配计数
                matches = sum(1 for w in sentence_words if w in window)
                score = matches / len(sentence_words)
            
            if score > best_score:
                best_score = score
                best_match = i
        
        # 如果匹配度太低，尝试更宽松的匹配
        if best_score < 0.5:
            # 尝试逐词匹配
            for i, tw in enumerate(transcription_words):
                if sentence_words[0] in tw or tw in sentence_words[0]:
                    # 找到第一个可能的词
                    # 检查后续词
                    match_count = 0
                    for j in range(len(sentence_words)):
                        if i + j < len(transcription_words):
                            if sentence_words[j] in transcription_words[i + j]:
                                match_count += 1
                            else:
                                break
                    
                    if match_count >= len(sentence_words) * 0.7:  # 至少70%的词匹配
                        best_match = i
                        best_score = match_count / len(sentence_words)
                        break
        
        if best_match is not None:
            start_idx = best_match
            end_idx = best_match + len(sentence_words) - 1
            # 确保索引在有效范围内
            if end_idx < len(word_timestamps):
                return start_idx, end_index
        
        return None, None
    
    def _find_word_indices_in_transcription(self, sentence: str, word_timestamps: list) -> tuple:
        """
        在转录的词级时间戳中找到句子对应的词索引范围（改进版）
        
        Args:
            sentence: 要匹配的句子
            word_timestamps: 词级时间戳列表
            
        Returns:
            (start_index, end_index) 或 (None, None)
        """
        # 标准化句子
        sentence_normalized = self._normalize_text(sentence)
        
        if not sentence_normalized or not word_timestamps:
            return None, None
        
        # 构建转录文本的词列表（标准化后）
        transcription_words = [self._normalize_text(w["word"]) for w in word_timestamps]
        sentence_words = sentence_normalized.split()
        
        if not sentence_words:
            return None, None
        
        # 方法1: 精确匹配整个句子（去掉空格后）
        # 将句子与转录文本的连续词进行匹配
        best_match = None
        best_score = 0
        
        for i in range(len(transcription_words) - len(sentence_words) + 1):
            # 构建窗口内的文本
            window = transcription_words[i:i + len(sentence_words)]
            window_text = ' '.join(window)
            
            # 计算相似度
            if HAS_DIFFLIB:
                score = SequenceMatcher(None, window_text, sentence_normalized).ratio()
            else:
                # 简单的词匹配计数
                matches = sum(1 for w in sentence_words if w in window)
                score = matches / len(sentence_words)
            
            if score > best_score:
                best_score = score
                best_match = i
        
        # 方法2: 如果方法1匹配度太低，尝试部分匹配
        if best_score < 0.5:
            # 找到第一个词的位置，然后向后扩展
            first_word = sentence_words[0]
            for i, tw in enumerate(transcription_words):
                if first_word == tw:
                    # 尝试匹配更多词
                    match_len = 1
                    for j in range(1, len(sentence_words)):
                        if i + j < len(transcription_words):
                            if sentence_words[j] == transcription_words[i + j]:
                                match_len += 1
                            else:
                                break
                    
                    if match_len >= len(sentence_words) * 0.7:  # 至少70%的词匹配
                        best_match = i
                        best_score = match_len / len(sentence_words)
                        break
        
        if best_match is not None:
            start_idx = best_match
            end_idx = best_match + len(sentence_words) - 1
            # 确保索引在有效范围内
            if end_idx < len(word_timestamps):
                return start_idx, end_idx
        
        return None, None

    def align_sentences_to_timestamps(self, audio_path: str, sentences: List[str]) -> List[Dict]:
        """
        将每个句子对齐到音频中的时间戳（强制对齐）
    
        
        Args:
            audio_path: 音频文件路径
            sentences: 句子列表
            
        Returns:
            句子时间戳列表，格式为 [{"start": float, "end": float, "text": str}, ...]
        """
        print("正在将句子对齐到时间戳...")
        
        # 1. 使用 Whisper 获取词级时间戳
        result = self.whisper_model.transcribe(
            audio_path,
            language="en",
            verbose=False,
            word_timestamps=True
        )
        
        # 提取词级时间戳
        word_timestamps = []
        if "words" in result:
            for word_info in result["words"]:
                word_timestamps.append({
                    "word": word_info.get("word", "").strip(),
                    "start": word_info.get("start", 0),
                    "end": word_info.get("end", 0)
                })
        else:
            # 如果没有词级信息，使用段落级
            print("⚠️  Whisper 未返回词级时间戳，使用段落级时间戳")
            for seg in result.get("segments", []):
                word_timestamps.append({
                    "word": seg.get("text", "").strip(),
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0)
                })
        
        if not word_timestamps:
            print("❌ 无法获取时间戳信息")
            return []
        
        print(f"✓ 获取了 {len(word_timestamps)} 个词的时间戳")
        
        # 2. 对齐每个句子到时间戳
        sentence_timestamps = []
        
        # 构建完整转录文本用于调试
        full_transcription = ' '.join([w["word"] for w in word_timestamps])
        
        # 使用进度条
        iterator = sentences
        if HAS_TQDM:
            iterator = tqdm(sentences, desc="对齐句子")
        
        for sentence in iterator:
            start_idx, end_idx = self._find_word_indices_in_transcription(
                sentence, word_timestamps
            )
            
            if start_idx is not None and end_idx is not None:
                sentence_timestamps.append({
                    "start": word_timestamps[start_idx]["start"],
                    "end": word_timestamps[end_idx]["end"],
                    "text": sentence
                })
            else:
                # 如果找不到匹配，使用估计的时间
                # 根据句子长度比例估计
                if sentence_timestamps:
                    last_end = sentence_timestamps[-1]["end"]
                else:
                    last_end = 0
                
                # 估计每个词约 0.3 秒
                word_count = len(sentence.split())
                estimated_duration = word_count * 0.3
                
                sentence_timestamps.append({
                    "start": last_end,
                    "end": last_end + estimated_duration,
                    "text": sentence
                })
                print(f"⚠️  句子未能精确对齐（匹配度低）: {sentence[:50]}...")
        
        print(f"✓ 成功对齐 {len(sentence_timestamps)} 个句子")
        
        # 3. 调整时间戳确保连续性（修复可能的重叠或间隙）
        sentence_timestamps = self._adjust_timestamps(sentence_timestamps)
        
        return sentence_timestamps
    
    def _adjust_timestamps(self, sentence_timestamps: List[Dict]) -> List[Dict]:
        """
        调整句子时间戳，确保连续性和正确顺序
        
        Args:
            sentence_timestamps: 原始句子时间戳列表
            
        Returns:
            调整后的句子时间戳列表
        """
        if not sentence_timestamps:
            return sentence_timestamps
        
        adjusted = []
        
        for i, ts in enumerate(sentence_timestamps):
            start = ts["start"]
            end = ts["end"]
            
            # 确保 start 不小于前一个 end
            if adjusted:
                prev_end = adjusted[-1]["end"]
                if start < prev_end:
                    start = prev_end
                # 确保 end 不小于 start
                if end < start:
                    end = start + 0.1  # 最小持续时间
            
            # 确保时间戳递增
            if adjusted and start < adjusted[-1]["end"]:
                start = adjusted[-1]["end"]
            
            if end <= start:
                end = start + 0.1  # 最小持续时间
            
            adjusted.append({
                "start": start,
                "end": end,
                "text": ts["text"]
            })
        
        return adjusted
  