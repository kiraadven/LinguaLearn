import os
import re
import json
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


def _normalize_token(token: str) -> str:
    """归一化单词，用于模糊匹配"""
    return re.sub(r"[^a-zA-Z']", "", token).lower()


class AudioTranscriber:
    def __init__(self):
        """初始化音频转文字器（仅使用本地 Whisper 模型）"""
        self.model_size = config.WHISPER_MODEL_SIZE

        import whisper
        self.whisper_model = whisper.load_model(self.model_size)

        # 创建临时目录
        os.makedirs(config.TEMP_DIR, exist_ok=True)

        # 缓存最近一次转录结果
        self._last_audio_path: str = None
        self._last_text: str = None
        self._last_word_items: List[Dict] = None

    def extract_audio_from_video(self, video_path: str) -> str:
        """从视频中提取音频"""
        print("正在从视频中提取音频...")

        video = VideoFileClip(video_path)
        audio_path = os.path.join(config.TEMP_DIR, "extracted_audio.mp3")

        video.audio.write_audiofile(audio_path, codec='mp3', verbose=False, logger=None)
        video.close()

        print(f"✓ 音频已提取到: {audio_path}")
        return audio_path

    def _transcribe_local(self, audio_path: str) -> str:
        """使用本地 Whisper 模型转录"""
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

    def transcribe_once_with_word_timestamps(self, audio_path: str) -> Dict:
        """
        使用本地 Whisper 模型一次性转录，获取单词级时间戳

        Args:
            audio_path: 音频文件路径

        Returns:
            包含 "text", "words", "segments" 的字典
        """
        # 如果已经转录过，直接返回缓存
        if self._last_audio_path == audio_path and self._last_text and self._last_word_items:
            return {
                "text": self._last_text,
                "words": self._last_word_items,
                "segments": []
            }

        print("正在使用本地 Whisper 模型转录音频（单词级时间戳）...")

        try:
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False,
                task="transcribe",
                word_timestamps=True
            )

            text = result.get("text", "").strip()
            segments = result.get("segments", []) or []

            word_items: List[Dict] = []

            for seg in segments:
                for w in seg.get("words", []) or []:
                    word = (w.get("word") or "").strip()
                    if not word:
                        continue
                    word_items.append({
                        "word": word,
                        "start": float(w.get("start", 0.0)),
                        "end": float(w.get("end", 0.0))
                    })

            print(f"✓ 转录完成：{len(text)} 个字符，{len(segments)} 个片段，{len(word_items)} 个单词时间戳")

            # 缓存结果
            self._last_audio_path = audio_path
            self._last_text = text
            self._last_word_items = word_items

            return {
                "text": text,
                "words": word_items,
                "segments": segments
            }

        except Exception as e:
            print(f"❌ 带时间戳转录失败: {e}")
            raise

    def _prepare_normalized_word_stream(self) -> List[Dict]:
        """将缓存的单词时间戳转为归一化序列"""
        if not self._last_word_items:
            return []

        normalized_stream = []
        for w in self._last_word_items:
            norm = _normalize_token(w.get("word", ""))
            if norm:
                normalized_stream.append({
                    "word": w.get("word", ""),  # 保留原始单词
                    "norm": norm,
                    "start": w["start"],
                    "end": w["end"]
                })
        return normalized_stream

    def _tokenize_sentence(self, sentence: str) -> List[str]:
        """将句子拆分成归一化后的 token 列表"""
        raw_tokens = re.findall(r"\b\w+'\w+|\b\w+\b", sentence)
        tokens = []
        for t in raw_tokens:
            norm = _normalize_token(t)
            if norm:
                tokens.append(norm)
        return tokens

    def get_sentences_from_original_transcript(self) -> List[str]:
        """
        从 Whisper 原始转录文本中分割句子
        
        关键：使用原始转录文本分割，确保与单词时间戳完全匹配
        这样可以避免外部分割器重写文本导致的对齐失败
        """
        if not self._last_text:
            return []
        
        text = re.sub(r'\s+', ' ', self._last_text)
        
        # 按句末标点分割
        parts = re.split(r'(?<=[.!?])\s+', text)
        
        sentences = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 5:
                sentences.append(part)
        
        return sentences

    def align_with_original_transcript(self, audio_path: str, output_name: str = None) -> List[Dict]:
        """
        使用原始转录文本分割句子并对齐时间戳
        
        这是最准确的方法：直接使用 Whisper 转录的原始文本分割句子，
        然后将每个句子与单词时间戳对齐。
        
        Args:
            audio_path: 音频文件路径
            output_name: 输出文件名
            
        Returns:
            每个元素为 {"sentence": str, "start": float, "end": float}
        """
        # 确保已有单词时间戳
        if self._last_audio_path != audio_path or not self._last_word_items or not self._last_text:
            self.transcribe_once_with_word_timestamps(audio_path)
        
        # 关键：使用原始转录文本分割的句子，而不是外部分割器的结果
        sentences = self.get_sentences_from_original_transcript()
        
        if not sentences:
            print("⚠️ 无法从原始转录文本分割句子")
            return []
        
        print(f"  从原始转录文本分割出 {len(sentences)} 个句子")
        
        # 使用标准对齐算法
        return self._align_sentences_by_tokens(audio_path, sentences, output_name)

    def _align_sentences_by_tokens(self, audio_path: str, sentences: List[str], output_name: str = None) -> List[Dict]:
        """
        基于 token 序列对齐句子到时间戳
        
        改进版：扩大搜索范围，确保每个句子都能匹配到
        """
        word_stream = self._prepare_normalized_word_stream()
        if not word_stream:
            print("⚠️ 未能获取单词时间戳")
            return []

        full_duration = word_stream[-1]["end"] if word_stream else 0.0
        
        print(f"  单词数: {len(word_stream)}, 句子数: {len(sentences)}")

        if not HAS_DIFFLIB:
            return self._average_align(sentences, full_duration)

        results = []
        cursor = 0
        total_words = len(word_stream)
        
        avg_duration = full_duration / max(len(sentences), 1)
        
        # 暴力搜索：极大的搜索窗口
        max_lookahead = min(300, total_words - 1)
        window_expand = 15

        for idx, sentence in enumerate(sentences):
            sent_tokens = self._tokenize_sentence(sentence)
            num_tokens = len(sent_tokens)

            if not sent_tokens:
                last_end = results[-1]["end"] if results else 0.0
                results.append({
                    "sentence": sentence, 
                    "start": float(last_end), 
                    "end": float(last_end + 0.5)
                })
                continue

            target_str = " ".join(sent_tokens)
            
            # 如果 cursor 已经到达末尾
            if cursor >= total_words - 1:
                last_end = results[-1]["end"] if results else 0.0
                results.append({
                    "sentence": sentence,
                    "start": last_end,
                    "end": min(last_end + avg_duration, full_duration)
                })
                continue

            # 估算窗口大小
            remaining = len(sentences) - idx - 1
            if remaining > 0:
                estimated_words = int((total_words - cursor) / (remaining + 1))
                estimated_words = max(estimated_words, num_tokens)
            else:
                estimated_words = total_words - cursor
            
            # 扩展搜索窗口
            min_window = max(1, estimated_words - window_expand)
            max_window = estimated_words + window_expand + 10
            
            search_start = max(0, cursor)
            search_end = min(total_words, cursor + max_lookahead)

            best_score = -1.0
            best_start_idx = cursor
            best_end_idx = cursor

            # 暴力搜索
            for start_idx in range(search_start, search_end):
                for window_size in range(min_window, max_window + 1):
                    end_idx = start_idx + window_size
                    if end_idx > total_words:
                        break

                    window_tokens = [w["norm"] for w in word_stream[start_idx:end_idx]]
                    window_str = " ".join(window_tokens)
                    
                    if not window_str or len(window_tokens) < num_tokens * 0.3:
                        continue

                    # 计算相似度
                    ratio = SequenceMatcher(None, target_str, window_str).ratio()
                    
                    # 计算覆盖率
                    coverage = sum(1 for t in sent_tokens if t in window_tokens) / num_tokens if num_tokens > 0 else 0
                    
                    # 综合评分
                    score = ratio * 0.4 + coverage * 0.6

                    if score > best_score:
                        best_score = score
                        best_start_idx = start_idx
                        best_end_idx = end_idx - 1

            # 防御越界
            best_start_idx = max(0, min(best_start_idx, total_words - 1))
            best_end_idx = max(best_start_idx, min(best_end_idx, total_words - 1))

            # 获取时间戳
            start_time = float(word_stream[best_start_idx]["start"])
            end_time = float(word_stream[best_end_idx]["end"])
            
            # 确保不重叠
            if results and start_time < results[-1]["end"]:
                overlap = results[-1]["end"] - start_time
                if overlap > 0.3:
                    start_time = results[-1]["end"]
                    end_time = max(end_time, start_time)

            end_time = max(end_time, start_time + 0.1)

            results.append({
                "sentence": sentence,
                "start": start_time,
                "end": end_time
            })

            cursor = best_end_idx + 1
            if cursor >= total_words:
                cursor = total_words - 1

        # 最终修正
        for i in range(len(results)):
            if i > 0 and results[i]["start"] < results[i-1]["end"]:
                results[i]["start"] = results[i-1]["end"]
            if results[i]["end"] < results[i]["start"]:
                results[i]["end"] = results[i]["start"] + 0.5
            if full_duration > 0:
                results[i]["end"] = min(results[i]["end"], full_duration)

        # 保存
        if output_name:
            segments_data = [
                {"start": item["start"], "end": item["end"], "text": item["sentence"]}
                for item in results
            ]
            segments_path = os.path.join(config.OUTPUT_DIR, f"{output_name}_segments.json")
            with open(segments_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, ensure_ascii=False, indent=2)
            print(f"✓ 时间戳已保存: {segments_path}")

        return results

    # 保留原有的对齐方法，但默认使用新的方法
    def align_sentences_to_timestamps(self, audio_path: str, sentences: List[str], output_name: str = None) -> List[Dict]:
        """
        将句子对齐到时间戳 - 使用原始转录文本方法
        
        这个方法现在会自动使用原始转录文本来对齐，
        以避免外部分割器重写文本导致的问题
        """
        # 优先使用原始转录文本方法
        return self.align_with_original_transcript(audio_path, output_name)
    
    def _average_align(self, sentences: List[str], full_duration: float) -> List[Dict]:
        """平均分配时间戳"""
        n = max(len(sentences), 1)
        results = []
        for i, s in enumerate(sentences):
            start = full_duration * i / n
            end = full_duration * (i + 1) / n
            results.append({"sentence": s, "start": float(start), "end": float(end)})
        return results
    
    def fix_timestamps_count(self, timestamps: List[Dict], sentences: List[str], full_duration: float) -> List[Dict]:
        """
        根据用户的句子分割调整时间戳
        
        场景：原始用 Whisper 句子对齐得到 timestamps，但用户用 sentence splitter
        重新分割了句子（比如长句分成短句）。这个函数根据用户的句子分割，
        在原始对齐的单词流中找分界点，调整时间戳。
        
        Args:
            timestamps: 原始 Whisper 句子对齐后的时间戳
            sentences: 用户 sentence splitter 分割后的句子
            full_duration: 音频总时长
            
        Returns:
            调整后的时间戳列表
        """
        if not timestamps or not sentences:
            return self._average_align(sentences, full_duration)
        
        if len(timestamps) == len(sentences):
            return timestamps
        
        print(f"  调整时间戳: {len(timestamps)} 个原始 -> {len(sentences)} 个用户句子")
        
        # 获取原始单词流
        word_stream = self._prepare_normalized_word_stream()
        if not word_stream:
            return self._average_align(sentences, full_duration)
        
        results = []
        
        # 遍历用户的句子，找到对应的时间戳
        for i, sentence in tqdm(enumerate(sentences), total=len(sentences), desc="调整时间戳"):
            sent_tokens = self._tokenize_sentence(sentence)
            
            if not sent_tokens:
                # 空句子，使用前一个结束时间
                last_end = results[-1]["end"] if results else 0.0
                results.append({
                    "sentence": sentence,
                    "start": last_end,
                    "end": last_end + 0.5
                })
                continue
            
            # 在原始单词流中找到这些 token 的位置
            target_str = " ".join(sent_tokens)
            
            best_start_idx = 0
            best_end_idx = len(word_stream) - 1
            
            # 搜索最佳匹配位置
            best_score = -1.0
            for start_idx in range(len(word_stream)):
                for end_idx in range(start_idx, len(word_stream)):
                    window_tokens = [w["norm"] for w in word_stream[start_idx:end_idx+1]]
                    window_str = " ".join(window_tokens)
                    
                    if not window_str:
                        continue
                    
                    ratio = SequenceMatcher(None, target_str, window_str).ratio()
                    if ratio > best_score:
                        best_score = ratio
                        best_start_idx = start_idx
                        best_end_idx = end_idx
            
            # 获取时间戳
            start_time = float(word_stream[best_start_idx]["start"])
            end_time = float(word_stream[best_end_idx]["end"])
            
            # 确保不与前一句重叠
            if results and start_time < results[-1]["end"]:
                start_time = results[-1]["end"]
                end_time = max(end_time, start_time)
            
            results.append({
                "sentence": sentence,
                "start": start_time,
                "end": end_time
            })
        
        # 最终修正
        for i in range(len(results)):
            if i > 0 and results[i]["start"] < results[i-1]["end"]:
                results[i]["start"] = results[i-1]["end"]
            if results[i]["end"] < results[i]["start"]:
                results[i]["end"] = results[i]["start"] + 0.5
            if full_duration > 0:
                results[i]["end"] = min(results[i]["end"], full_duration)
        
        return results

    def fix_timestamps_by_mapping(self, timestamps: List[Dict], sentences: List[str], 
                                  split_mapping: dict, full_duration: float) -> List[Dict]:
        """
        根据分割映射调整时间戳
        
        核心思路：
        1. 原始 timestamps 是用 Whisper 句子（19个）对齐的
        2. 用户的 sentences 是经过分割的（22个）
        3. split_mapping 记录了每个用户句子对应哪个原始句子
        4. 对于同一个原始句子的多个用户句子，需要：
           - 找到原始句子在 word_stream 中的位置
           - 在原始句子文本中找到分割点的位置（用单词索引）
           - 根据单词索引找到对应的起始/结束时间
        
        Args:
            timestamps: 原始 Whisper 句子对齐后的时间戳 (19个)
            sentences: 用户 sentence splitter 分割后的句子 (22个)
            split_mapping: 分割映射 {输出索引: 原始句子索引}
            full_duration: 音频总时长
            
        Returns:
            调整后的时间戳列表 (22个)
        """
        if not timestamps or not sentences or not split_mapping:
            return self._average_align(sentences, full_duration)
        
        if len(timestamps) == len(sentences):
            return timestamps
        
        print(f"  根据分割映射调整: {len(timestamps)} -> {len(sentences)}")
        
        # 获取原始单词流
        word_stream = self._prepare_normalized_word_stream()
        if not word_stream:
            return self._average_align(sentences, full_duration)
        
        # 先计算每个原始句子在 word_stream 中的范围
        print("  计算原始句子在单词流中的位置...")
        original_word_ranges = self._find_original_sentence_ranges(timestamps, word_stream)
        
        # 按原始句子索引分组用户句子
        grouped_by_original = {}
        for i, sentence in enumerate(sentences):
            orig_idx = split_mapping.get(i, i)
            if orig_idx not in grouped_by_original:
                grouped_by_original[orig_idx] = []
            grouped_by_original[orig_idx].append((i, sentence))
        
        # 构建结果
        results = [None] * len(sentences)
        
        # 遍历每个原始句子
        for orig_idx, group in grouped_by_original.items():
            if len(group) == 1:
                # 只有一个用户句子，直接用原始时间戳
                user_idx, sentence = group[0]
                if orig_idx < len(timestamps):
                    results[user_idx] = {
                        "sentence": sentence,
                        "start": timestamps[orig_idx]["start"],
                        "end": timestamps[orig_idx]["end"]
                    }
                else:
                    results[user_idx] = {
                        "sentence": sentence,
                        "start": full_duration - 5.0,
                        "end": full_duration
                    }
            else:
                # 多个用户句子，需要在原始句子的单词范围内找分割点
                if orig_idx < len(timestamps):
                    orig_ts = timestamps[orig_idx]
                    orig_start_time = orig_ts["start"]
                    orig_end_time = orig_ts["end"]
                    
                    word_start, word_end = original_word_ranges.get(orig_idx, (0, len(word_stream)-1))
                else:
                    orig_start_time = timestamps[-1]["end"] if timestamps else 0.0
                    orig_end_time = full_duration
                    word_start = 0
                    word_end = len(word_stream) - 1
                
                # 获取原始句子对应的单词文本
                orig_words = word_stream[word_start:word_end+1]
                orig_text = " ".join([w["word"] for w in orig_words])
                
                # 分割这个原始文本
                sub_ranges = self._split_original_text_by_user_sentences(
                    orig_text, [s for _, s in group], orig_words
                )
                
                # 为每个用户句子分配时间戳
                for j, (user_idx, sentence) in enumerate(group):
                    if j < len(sub_ranges):
                        sub_start_idx, sub_end_idx = sub_ranges[j]
                        start_time = float(word_stream[word_start + sub_start_idx]["start"])
                        end_time = float(word_stream[word_start + sub_end_idx]["end"])
                    else:
                        # 备用：平均分配
                        duration = (orig_end_time - orig_start_time) / len(group)
                        start_time = orig_start_time + j * duration
                        end_time = start_time + duration
                    
                    # 确保不与前一句重叠
                    if user_idx > 0 and results[user_idx-1] is not None:
                        if start_time < results[user_idx-1]["end"]:
                            start_time = results[user_idx-1]["end"]
                    
                    results[user_idx] = {
                        "sentence": sentence,
                        "start": start_time,
                        "end": end_time
                    }
        
        # 填充 None（如果有的话）
        for i, r in enumerate(results):
            if r is None:
                last_end = results[i-1]["end"] if i > 0 and results[i-1] else 0.0
                results[i] = {
                    "sentence": sentences[i],
                    "start": last_end,
                    "end": last_end + 1.0
                }
        
        # 最终修正
        for i in range(len(results)):
            if i > 0 and results[i]["start"] < results[i-1]["end"]:
                results[i]["start"] = results[i-1]["end"]
            if results[i]["end"] < results[i]["start"]:
                results[i]["end"] = results[i]["start"] + 0.5
            if full_duration > 0:
                results[i]["end"] = min(results[i]["end"], full_duration)
        
        return results
    
    def _find_original_sentence_ranges(self, timestamps: List[Dict], word_stream: List[Dict]) -> dict:
        """找到每个原始句子在 word_stream 中的范围"""
        original_word_ranges = {}
        
        for orig_idx, ts in enumerate(timestamps):
            orig_tokens = self._tokenize_sentence(ts["sentence"])
            target_str = " ".join(orig_tokens)
            
            best_start = 0
            best_end = len(word_stream) - 1
            best_score = -1.0
            
            for start_idx in range(len(word_stream)):
                for end_idx in range(start_idx, min(start_idx + len(orig_tokens) + 30, len(word_stream))):
                    window_tokens = [w["norm"] for w in word_stream[start_idx:end_idx+1]]
                    window_str = " ".join(window_tokens)
                    
                    if not window_str:
                        continue
                    
                    ratio = SequenceMatcher(None, target_str, window_str).ratio()
                    if ratio > best_score:
                        best_score = ratio
                        best_start = start_idx
                        best_end = end_idx
            
            original_word_ranges[orig_idx] = (best_start, best_end)
        
        return original_word_ranges
    
    def _split_original_text_by_user_sentences(self, orig_text: str, user_sentences: List[str], 
                                               orig_words: List[Dict]) -> List[tuple]:
        """
        在原始文本中找到用户句子对应的单词索引范围
        
        Returns:
            List of (start_idx, end_idx) tuples for each user sentence
        """
        if not orig_text or not user_sentences or not orig_words:
            return [(0, len(orig_words)-1)] * len(user_sentences)
        
        # 用 SequenceMatcher 找每个用户句子在原始文本中的位置
        results = []
        
        for user_sent in user_sentences:
            user_tokens = self._tokenize_sentence(user_sent)
            user_str = " ".join(user_tokens)
            
            best_start = 0
            best_end = len(orig_words) - 1
            best_score = -1.0
            
            # 在原始单词中搜索最佳匹配
            for start_idx in range(len(orig_words)):
                for end_idx in range(start_idx, min(start_idx + len(user_tokens) + 20, len(orig_words))):
                    window_tokens = [w["norm"] for w in orig_words[start_idx:end_idx+1]]
                    window_str = " ".join(window_tokens)
                    
                    if not window_str:
                        continue
                    
                    ratio = SequenceMatcher(None, user_str, window_str).ratio()
                    if ratio > best_score:
                        best_score = ratio
                        best_start = start_idx
                        best_end = end_idx
            
            results.append((best_start, best_end))
        
        # 如果结果数量不匹配，用平均分配
        if len(results) != len(user_sentences):
            total_words = len(orig_words)
            per_sentence = total_words // len(user_sentences)
            results = []
            for i in range(len(user_sentences)):
                start = i * per_sentence
                end = start + per_sentence - 1 if i < len(user_sentences) - 1 else total_words - 1
                results.append((start, end))
        
        return results
