import os
import re
from typing import List, Dict, Tuple
from moviepy.editor import VideoFileClip
from openai import OpenAI
import config

# 尝试导入 difflib 用于模糊匹配
try:
    from difflib import SequenceMatcher
    HAS_DIFFLIB = True
except ImportError:
    HAS_DIFFLIB = False


class AudioTranscriber:
    def __init__(self, api_key: str = None, base_url: str = None, use_local: bool = False, model_size: str = None):
        """
        初始化音频转文字器
        
        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL
            use_local: 是否使用本地 Whisper 模型
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
        """
        self.use_local = use_local
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        self.model_size = model_size or config.WHISPER_MODEL_SIZE
        
        if not use_local:
            if not self.api_key:
                raise ValueError("请在.env文件中设置OPENAI_API_KEY，或使用本地模式")
            
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            # 使用本地 Whisper 模型
            try:
                import whisper
                print(f"正在加载本地 Whisper 模型 ({self.model_size})...")
                self.whisper_model = whisper.load_model(self.model_size)
                print(f"✓ Whisper 模型 ({self.model_size}) 加载成功")
            except ImportError:
                raise ImportError(
                    "本地模式需要安装 openai-whisper 包。\n"
                    "请运行: pip install openai-whisper"
                )
        
        # 创建临时目录
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        # Whisper API 文件大小限制（25MB）
        self.max_file_size = 25 * 1024 * 1024
    
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
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        使用 Whisper 将音频转换为文字
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        if self.use_local:
            return self._transcribe_local(audio_path)
        else:
            return self._transcribe_api(audio_path)
    
    def transcribe_audio_with_timestamps(self, audio_path: str) -> dict:
        """
        使用 Whisper 将音频转换为文字，并返回每个段落的时间戳
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含 text 和 segments 的字典，segments 包含每个段落的时间戳
        """
        if self.use_local:
            return self._transcribe_local_with_timestamps(audio_path)
        else:
            return self._transcribe_api_with_timestamps(audio_path)
    
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
    
    def _transcribe_local_with_timestamps(self, audio_path: str) -> dict:
        """
        使用本地 Whisper 模型转录并返回时间戳
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含 text 和 segments 的字典
        """
        print("正在使用本地 Whisper 模型转录音频（带时间戳）...")
        
        try:
            # 使用 word_timestamps=True 来获取单词级别的时间戳
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False,
                word_timestamps=True
            )
            
            text = result["text"].strip()
            segments = result.get("segments", [])
            
            print(f"✓ 转录完成，共 {len(text)} 个字符，{len(segments)} 个段落")
            return {
                "text": text,
                "segments": segments
            }
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def transcribe_with_sentence_timestamps(self, audio_path: str, sentences: List[str]) -> List[Dict]:
        """
        使用 Whisper 转录音频，并返回每个句子对应的时间戳
        
        Args:
            audio_path: 音频文件路径
            sentences: 已经分割好的句子列表
            
        Returns:
            句子时间戳列表，每个元素包含 start, end, text
        """
        if self.use_local:
            return self._transcribe_local_sentence_timestamps(audio_path, sentences)
        else:
            return self._transcribe_api_sentence_timestamps(audio_path, sentences)
    
    def _transcribe_local_sentence_timestamps(self, audio_path: str, sentences: List[str]) -> List[Dict]:
        """
        使用本地 Whisper 模型获取句子级别时间戳
        
        Args:
            audio_path: 音频文件路径
            sentences: 句子列表
            
        Returns:
            句子时间戳列表
        """
        print("正在使用本地 Whisper 模型获取句子时间戳...")
        
        try:
            # 转录获取单词级别时间戳
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False,
                word_timestamps=True
            )
            
            # 提取所有单词及其时间戳
            words_with_timestamps = []
            for segment in result.get("segments", []):
                # 检查是否有 words 字段
                words = segment.get("words", [])
                if not words:
                    # 如果没有单词级别，使用整个段落
                    words_with_timestamps.append({
                        "word": segment.get("text", ""),
                        "start": segment.get("start", 0),
                        "end": segment.get("end", 0)
                    })
                else:
                    for word_info in words:
                        words_with_timestamps.append({
                            "word": word_info.get("word", ""),
                            "start": word_info.get("start", 0),
                            "end": word_info.get("end", 0)
                        })
            
            if not words_with_timestamps:
                print("⚠️  无法获取单词时间戳，使用文本匹配方式")
                full_text = result.get("text", "")
                return self._text_based_sentence_timestamps(full_text, sentences)
            
            # 将单词按句子分组
            sentence_timestamps = self._group_words_to_sentences(words_with_timestamps, sentences)
            
            print(f"✓ 获取了 {len(sentence_timestamps)} 个句子的时间戳")
            return sentence_timestamps
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def _transcribe_api_sentence_timestamps(self, audio_path: str, sentences: List[str]) -> List[Dict]:
        """
        使用 Whisper API 获取句子级别时间戳
        
        Args:
            audio_path: 音频文件路径
            sentences: 句子列表
            
        Returns:
            句子时间戳列表
        """
        print("正在使用 Whisper API 获取句子时间戳...")
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(audio_path)
            print(f"音频文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            # Whisper API 需要使用 verbose_json 格式
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="verbose_json"
                )
            
            # 尝试获取单词时间戳
            words_with_timestamps = []
            if hasattr(transcript, 'words') and transcript.words:
                for word_info in transcript.words:
                    words_with_timestamps.append({
                        "word": word_info.get("word", ""),
                        "start": word_info.get("start", 0),
                        "end": word_info.get("end", 0)
                    })
            elif hasattr(transcript, 'segments') and transcript.segments:
                # 如果没有单词级别，使用段落级别
                for seg in transcript.segments:
                    words_with_timestamps.append({
                        "word": seg.get("text", ""),
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0)
                    })
            
            if not words_with_timestamps:
                print("⚠️  无法获取单词时间戳，使用文本匹配方式")
                return self._text_based_sentence_timestamps(transcript.text if hasattr(transcript, 'text') else str(transcript), sentences)
            
            # 将单词按句子分组
            sentence_timestamps = self._group_words_to_sentences(words_with_timestamps, sentences)
            
            print(f"✓ 获取了 {len(sentence_timestamps)} 个句子的时间戳")
            return sentence_timestamps
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def _text_based_sentence_timestamps(self, full_text: str, sentences: List[str]) -> List[Dict]:
        """
        基于文本匹配的方式估算句子时间戳（当无法获取单词时间戳时使用）
        
        Args:
            full_text: 完整文本
            sentences: 句子列表
            
        Returns:
            估算的时间戳列表
        """
        print("使用文本匹配方式估算时间戳...")
        
        if not sentences:
            return []
        
        # 按句子数量平均分配时间
        # 假设总时长约为每秒 2.5 个单词
        total_words = len(full_text.split())
        estimated_duration = total_words / 2.5  # 秒
        avg_duration = estimated_duration / len(sentences)
        
        sentence_timestamps = []
        current_time = 0
        
        for sentence in sentences:
            sentence_timestamps.append({
                "start": current_time,
                "end": current_time + avg_duration,
                "text": sentence
            })
            current_time += avg_duration
        
        return sentence_timestamps
    
    def _group_words_to_sentences(self, words_with_timestamps: List[Dict], 
                                   sentences: List[str]) -> List[Dict]:
        """
        将单词时间戳分组到句子 - 使用更可靠的匹配算法
        
        改进点：
        1. 使用模糊匹配处理转录错误
        2. 使用动态规划找到最佳对齐
        3. 添加置信度评分
        
        Args:
            words_with_timestamps: 单词列表，每个包含 word, start, end
            sentences: 目标句子列表
            
        Returns:
            句子时间戳列表
        """
        if not words_with_timestamps or not sentences:
            return []
        
        # 清理文本用于匹配
        def normalize_text(text):
            import re
            text = re.sub(r'[^\w\s]', '', text)
            return " ".join(text.lower().split())
        
        # 构建完整的whisper转录文本
        whisper_text = " ".join([w["word"] for w in words_with_timestamps])
        normalized_whisper = normalize_text(whisper_text)
        
        sentence_timestamps = []
        
        # 为每个目标句子找到最佳匹配
        for target_sentence in sentences:
            normalized_target = normalize_text(target_sentence)
            
            if not normalized_target:
                continue
            
            # 使用优化的匹配算法
            best_match = self._find_best_word_match(
                words_with_timestamps, 
                normalized_target,
                target_sentence
            )
            
            if best_match:
                sentence_timestamps.append({
                    "start": best_match["start"],
                    "end": best_match["end"],
                    "text": target_sentence
                })
            else:
                # 如果没找到匹配，使用位置估算
                idx = len(sentence_timestamps)
                total_words = len(words_with_timestamps)
                words_per_sentence = total_words / len(sentences)
                start_idx = int(idx * words_per_sentence)
                end_idx = int((idx + 1) * words_per_sentence)
                
                start_time = words_with_timestamps[min(start_idx, total_words-1)]["start"]
                end_time = words_with_timestamps[min(end_idx - 1, total_words-1)]["end"]
                
                sentence_timestamps.append({
                    "start": start_time,
                    "end": end_time,
                    "text": target_sentence
                })
        
        # 确保时间戳连续且不重叠
        sentence_timestamps = self._fix_overlapping_timestamps(sentence_timestamps)
        
        return sentence_timestamps
    
    def _find_best_word_match(self, words_with_timestamps: List[Dict], 
                               normalized_target: str,
                               original_target: str) -> Dict:
        """
        找到单词时间戳与目标句子的最佳匹配
        
        使用滑动窗口 + 模糊匹配算法
        
        Args:
            words_with_timestamps: 单词时间戳列表
            normalized_target: 规范化后的目标句子
            original_target: 原始目标句子
            
        Returns:
            匹配结果，包含 start, end, confidence
        """
        if not words_with_timestamps:
            return None
        
        target_words = normalized_target.split()
        n_target = len(target_words)
        n_words = len(words_with_timestamps)

         # 清理文本用于匹配
        def normalize_text(text):
            import re
            text = re.sub(r'[^\w\s]', '', text)
            return " ".join(text.lower().split())
        
        if n_target == 0 or n_words == 0:
            return None
        
        # 滑动窗口搜索最佳匹配
        best_score = 0
        best_start = -1
        best_end = -1
        
        # 窗口大小从目标句子长度开始，逐步扩大
        for window_size in range(max(1, n_target // 2), min(n_words, n_target * 2) + 1):
            for start_idx in range(n_words - window_size + 1):
                end_idx = start_idx + window_size
                
                # 提取窗口内的单词
                window_words = words_with_timestamps[start_idx:end_idx]
                window_text = " ".join([normalize_text(w["word"]) for w in window_words])
                
                # 计算相似度
                score = self._calculate_similarity(window_text, normalized_target)
                
                if score > best_score:
                    best_score = score
                    best_start = start_idx
                    best_end = end_idx
        
        # 如果最佳匹配分数太低，使用动态规划对齐
        if best_score < 0.3:
            return self._dp_align_sentence(words_with_timestamps, normalized_target)
        
        # 返回匹配结果
        if best_start >= 0:
            return {
                "start": words_with_timestamps[best_start]["start"],
                "end": words_with_timestamps[best_end - 1]["end"],
                "confidence": best_score
            }
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 精确匹配
        if text1 == text2:
            return 1.0
        
        # 子串匹配
        if text1 in text2 or text2 in text1:
            return 0.8
        
        # 使用 difflib 计算相似度
        if HAS_DIFFLIB:
            ratio = SequenceMatcher(None, text1, text2).ratio()
            return ratio
        
        # 简单的词重叠计算
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _dp_align_sentence(self, words_with_timestamps: List[Dict], 
                           normalized_target: str) -> Dict:
        """
        使用动态规划对齐句子和单词时间戳
        
        适用于转录文本与目标句子差异较大的情况
        
        Args:
            words_with_timestamps: 单词时间戳列表
            normalized_target: 规范化后的目标句子
            
        Returns:
            对齐结果
        """
        target_words = normalized_target.split()
        n_target = len(target_words)
        n_words = len(words_with_timestamps)
        
        if n_target == 0 or n_words == 0:
            return None
        
        # 构建相似度矩阵
        # dp[i][j] = 前i个目标词匹配到前j个音频词的最佳分数
        dp = [[0.0] * (n_words + 1) for _ in range(n_target + 1)]
        
        for i in range(1, n_target + 1):
            for j in range(1, n_words + 1):
                target_word = target_words[i-1]
                audio_word = normalize_text(words_with_timestamps[j-1]["word"])
                
                # 当前词的相似度
                word_sim = self._calculate_similarity(target_word, audio_word)
                
                # 三种选择：不匹配当前词、匹配、或者跳过音频词
                dp[i][j] = max(
                    dp[i][j-1],  # 跳过音频词
                    dp[i-1][j-1] + word_sim,  # 匹配
                    dp[i-1][j]  # 跳过目标词
                )
        
        # 回溯找到最佳对齐
        i, j = n_target, n_words
        matched_audio = []
        
        while i > 0 and j > 0:
            target_word = target_words[i-1]
            audio_word = normalize_text(words_with_timestamps[j-1]["word"])
            word_sim = self._calculate_similarity(target_word, audio_word)
            
            if dp[i][j] == dp[i-1][j-1] + word_sim and word_sim > 0.3:
                matched_audio.append(j-1)
                i -= 1
                j -= 1
            elif dp[i][j] == dp[i][j-1]:
                j -= 1
            else:
                i -= 1
        
        if not matched_audio:
            return None
        
        matched_audio.reverse()
        
        return {
            "start": words_with_timestamps[matched_audio[0]]["start"],
            "end": words_with_timestamps[matched_audio[-1]]["end"],
            "confidence": dp[n_target][n_words] / n_target
        }
        
        # 确保时间戳连续且不重叠
        sentence_timestamps = self._fix_overlapping_timestamps(sentence_timestamps)
        
        return sentence_timestamps
    
    def _fix_overlapping_timestamps(self, sentence_timestamps: List[Dict]) -> List[Dict]:
        """
        修复重叠的时间戳，确保每个句子的结束时间等于下一个句子的开始时间
        
        Args:
            sentence_timestamps: 句子时间戳列表
            
        Returns:
            修复后的时间戳列表
        """
        if len(sentence_timestamps) <= 1:
            return sentence_timestamps
        
        fixed = []
        for i, ts in enumerate(sentence_timestamps):
            start = ts["start"]
            end = ts["end"]
            
            # 确保开始时间不小于上一个的结束时间
            if i > 0 and start < fixed[i-1]["end"]:
                start = fixed[i-1]["end"]
            
            # 确保结束时间大于开始时间
            if end <= start:
                end = start + 1.0  # 至少1秒
            
            # 确保结束时间不超过下一个的开始时间（如果存在）
            if i < len(sentence_timestamps) - 1:
                next_ts = sentence_timestamps[i + 1]
                if end > next_ts["start"]:
                    end = next_ts["start"]
            
            fixed.append({
                "start": start,
                "end": end,
                "text": ts["text"]
            })
        
        return fixed
    
    def _transcribe_api(self, audio_path: str) -> str:
        """
        使用 Whisper API 转录
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        print("正在使用 Whisper API 转录音频...")
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(audio_path)
            print(f"音频文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size > self.max_file_size:
                print(f"⚠️  文件超过25MB限制，将进行分段处理...")
                return self._transcribe_large_audio(audio_path)
            
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",  # 指定为英语
                    response_format="text"
                )
            
            text = transcript if isinstance(transcript, str) else transcript.text
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            return text
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            print(f"提示: 请确保音频文件小于25MB，且API Key有效")
            raise
    
    def _transcribe_api_with_timestamps(self, audio_path: str) -> dict:
        """
        使用 Whisper API 转录并返回时间戳
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含 text 和 segments 的字典
        """
        print("正在使用 Whisper API 转录音频（带时间戳）...")
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(audio_path)
            print(f"音频文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size > self.max_file_size:
                print(f"⚠️  文件超过25MB限制，将进行分段处理...")
                return self._transcribe_large_audio_with_timestamps(audio_path)
            
            # 使用 verbose_json 格式来获取详细的时间戳信息
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="verbose_json"
                )
            
            # 转换为兼容格式
            text = transcript.text if hasattr(transcript, 'text') else str(transcript)
            
            # 转换 segments 格式
            segments = []
            if hasattr(transcript, 'segments'):
                for seg in transcript.segments:
                    segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", "")
                    })
            elif hasattr(transcript, 'words'):
                # 如果只有单词级别的时间戳，构建段落
                current_segment = {"start": 0, "end": 0, "text": ""}
                for word in transcript.words:
                    if not current_segment["text"]:
                        current_segment["start"] = word.get("start", 0)
                    current_segment["text"] += " " + word.get("word", "")
                    current_segment["end"] = word.get("end", 0)
                if current_segment["text"]:
                    segments.append(current_segment)
            
            print(f"✓ 转录完成，共 {len(text)} 个字符，{len(segments)} 个段落")
            return {
                "text": text,
                "segments": segments
            }
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            print(f"提示: 请确保音频文件小于25MB，且API Key有效")
            raise
    
    def _transcribe_large_audio(self, audio_path: str) -> str:
        """
        处理大于25MB的音频文件（分段处理）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        from pydub import AudioSegment
        
        print("正在分段处理大文件...")
        audio = AudioSegment.from_file(audio_path)
        
        # 每段10分钟
        segment_length = 10 * 60 * 1000  # 毫秒
        segments = []
        
        for i in range(0, len(audio), segment_length):
            segment = audio[i:i + segment_length]
            segment_path = os.path.join(config.TEMP_DIR, f"segment_{i}.mp3")
            segment.export(segment_path, format="mp3", bitrate="64k")
            
            print(f"正在转录第 {i // segment_length + 1} 段...")
            
            with open(segment_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="text"
                )
            
            text = transcript if isinstance(transcript, str) else transcript.text
            segments.append(text)
            
            # 清理临时文件
            os.remove(segment_path)
        
        full_text = " ".join(segments)
        print(f"✓ 所有段落转录完成，共 {len(full_text)} 个字符")
        return full_text
    
    def _transcribe_large_audio_with_timestamps(self, audio_path: str) -> dict:
        """
        处理大于25MB的音频文件（分段处理，带时间戳）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            包含 text 和 segments 的字典
        """
        from pydub import AudioSegment
        
        print("正在分段处理大文件...")
        audio = AudioSegment.from_file(audio_path)
        
        # 每段10分钟
        segment_length = 10 * 60 * 1000  # 毫秒
        all_segments = []
        full_text_parts = []
        
        for i in range(0, len(audio), segment_length):
            segment = audio[i:i + segment_length]
            segment_path = os.path.join(config.TEMP_DIR, f"segment_{i}.mp3")
            segment.export(segment_path, format="mp3", bitrate="64k")
            
            print(f"正在转录第 {i // segment_length + 1} 段...")
            
            # 调整时间偏移
            time_offset = i / 1000.0  # 转换为秒
            
            with open(segment_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="verbose_json"
                )
            
            text = transcript.text if hasattr(transcript, 'text') else str(transcript)
            full_text_parts.append(text)
            
            # 调整时间戳
            if hasattr(transcript, 'segments'):
                for seg in transcript.segments:
                    all_segments.append({
                        "start": seg.get("start", 0) + time_offset,
                        "end": seg.get("end", 0) + time_offset,
                        "text": seg.get("text", "")
                    })
            
            # 清理临时文件
            os.remove(segment_path)
        
        full_text = " ".join(full_text_parts)
        print(f"✓ 所有段落转录完成，共 {len(full_text)} 个字符，{len(all_segments)} 个段落")
        return {
            "text": full_text,
            "segments": all_segments
        }
    
    def transcribe_video(self, video_path: str) -> str:
        """
        从视频中提取文字（完整流程）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            转录的文字
        """
        # 1. 提取音频
        audio_path = self.extract_audio_from_video(video_path)
        
        # 2. 转录音频
        text = self.transcribe_audio(audio_path)
        
        # 3. 清理临时文件（可选）
        # os.remove(audio_path)
        
        return text
    
    def transcribe_video_with_timestamps(self, video_path: str) -> dict:
        """
        从视频中提取文字（带时间戳）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            包含 text 和 segments 的字典
        """
        # 1. 提取音频
        audio_path = self.extract_audio_from_video(video_path)
        
        # 2. 转录音频（带时间戳）
        result = self.transcribe_audio_with_timestamps(audio_path)
        
        # 3. 清理临时文件（可选）
        # os.remove(audio_path)
        
        return result


if __name__ == "__main__":
    # 测试代码
    transcriber = AudioTranscriber()
    
    # 假设有一个测试视频
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        text = transcriber.transcribe_video(test_video)
        print(f"\n转录结果:\n{text}")
    else:
        print(f"测试视频不存在: {test_video}")
