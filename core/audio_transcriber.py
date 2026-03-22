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

def _normalize_token(token: str, is_cjk: bool = False) -> str:
    """归一化单词，用于模糊匹配"""
    if is_cjk:
        return re.sub(r'\s+', '', token).lower()
    return re.sub(r"[^a-zA-Z']", "", token).lower()

class AudioTranscriber:
    def __init__(self, source_lang: str = None):
        """初始化音频转文字器（仅使用本地 Whisper 模型）"""
        self.model_size = config.WHISPER_MODEL_SIZE
        self.source_lang = source_lang or getattr(config, 'SOURCE_LANGUAGE', 'en')
        # 映射到 Whisper 支持的语言代码
        whisper_map = getattr(config, 'WHISPER_LANGUAGE_MAP', {})
        self.whisper_lang = whisper_map.get(self.source_lang, self.source_lang)
        self.is_cjk = self.source_lang in getattr(config, 'CJK_LANGUAGES', {'zh', 'ja', 'ko'})

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
        
        filename = os.path.basename(video_path)
        name_without_ext = os.path.splitext(filename)[0]
        audio_filename = name_without_ext + ".mp3"
        audio_path = os.path.join(config.TEMP_DIR, audio_filename)

        video.audio.write_audiofile(audio_path, codec='mp3', verbose=False, logger=None)
        video.close()

        print(f"✓ 音频已提取到: {audio_path}")
        return audio_path

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
                language=self.whisper_lang,
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
            norm = _normalize_token(w.get("word", ""), self.is_cjk)
            if norm:
                normalized_stream.append({
                    "word": w.get("word", ""),
                    "norm": norm,
                    "start": w["start"],
                    "end": w["end"]
                })
        return normalized_stream

    def _tokenize_sentence(self, sentence: str) -> List[str]:
        """将句子拆分成归一化后的 token 列表"""
        if self.is_cjk:
            # CJK语言：按字符分割
            tokens = []
            for char in sentence:
                norm = _normalize_token(char, True)
                if norm:
                    tokens.append(norm)
            return tokens
        else:
            raw_tokens = re.findall(r"\b\w+'\w+|\b\w+\b", sentence)
            tokens = []
            for t in raw_tokens:
                norm = _normalize_token(t)
                if norm:
                    tokens.append(norm)
            return tokens

    def align_sentences_to_timestamps(self, audio_path: str, sentences: List[str], 
                                       output_name: str = None) -> List[Dict]:
        """
        将用户分割的句子对齐到时间戳
        
        核心算法：
        1. 获取音频的单词时间戳列表
        2. 对每个句子，在单词流中找到最佳匹配的起止位置
        3. 使用该位置的起始/结束时间作为句子时间戳
        4. 保存结果到 JSON 文件
        
        Args:
            audio_path: 音频文件路径
            sentences: 用户 sentence splitter 分割后的句子列表
            output_name: 输出文件名（用于保存 JSON）
            
        Returns:
            每个句子的时间戳列表 [{"sentence": str, "start": float, "end": float}, ...]
        """
        print(f"  开始对齐 {len(sentences)} 个句子到时间戳...")
        
        # 1. 获取单词时间戳
        # 使用之前转录的结果（如果有缓存的话）
        word_items = self._last_word_items if hasattr(self, '_last_word_items') and self._last_word_items else []
        
        if not word_items:
            # 如果没有缓存，重新转录获取单词时间戳
            print("  重新获取单词时间戳...")
            result = self.model.transcribe(audio_path, word_timestamps=True)
            word_items = result.get("words", []) or []
            # 缓存起来供后续使用
            self._last_word_items = word_items
        
        if not word_items:
            print("  ⚠️ 无法获取单词时间戳，使用平均分配")
            return self._average_align(sentences, 0.0)
        
        # 获取音频总时长
        full_duration = word_items[-1]["end"] if word_items else 0.0
        print(f"  音频总时长: {full_duration:.2f}s")
        
        # 2. 构建归一化单词流
        word_stream = self._prepare_normalized_word_stream()
        if not word_stream:
            print("  ⚠️ 单词流为空，使用平均分配")
            return self._average_align(sentences, full_duration)
        
        print(f"  单词流长度: {len(word_stream)}")
        
        # 3. 对每个句子在单词流中找最佳匹配
        results = []
        
        for i, sentence in tqdm(enumerate(sentences), total=len(sentences), desc="对齐句子"):
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
            
            # 在单词流中找到这些 token 的最佳位置
            target_str = " ".join(sent_tokens)
            
            best_start_idx = 0
            best_end_idx = len(word_stream) - 1
            best_score = -1.0
            
            # 搜索最佳匹配位置
            # 优化：只搜索从上一个句子结束位置开始的范围
            search_start = 0
            if results:
                # 找到上一个句子结束时间对应的单词位置
                last_end_time = results[-1]["end"]
                for idx, w in enumerate(word_stream):
                    if w["start"] >= last_end_time:
                        search_start = max(0, idx - 1)  # 稍微往回一点，避免漏掉
                        break
            
            for start_idx in range(search_start, len(word_stream)):
                # 限制搜索窗口大小，避免太慢
                max_end = min(start_idx + len(sent_tokens) + 30, len(word_stream))
                for end_idx in range(start_idx, max_end):
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
                end_time = max(end_time, start_time + 0.1)
            
            # 最后一个句子延伸到音频结束
            if i == len(sentences) - 1:
                end_time = full_duration
            
            results.append({
                "sentence": sentence,
                "start": start_time,
                "end": end_time
            })
        
        # 4. 最终修正：确保时间戳连续且不重叠
        for i in range(len(results)):
            if i > 0 and results[i]["start"] < results[i-1]["end"]:
                results[i]["start"] = results[i-1]["end"]
            if results[i]["end"] < results[i]["start"]:
                results[i]["end"] = results[i]["start"] + 0.5
            if full_duration > 0:
                results[i]["end"] = min(results[i]["end"], full_duration)
        
        # 5. 保存到 JSON 文件
        if output_name:
            import config
            segments_path = os.path.join(config.OUTPUT_DIR, f"{output_name}_segments.json")
            
            # 转换为输出格式
            segments_data = [
                {"start": ts["start"], "end": ts["end"], "text": ts["sentence"]}
                for ts in results
            ]
            
            with open(segments_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, ensure_ascii=False, indent=2)
            print(f"  ✓ 句子时间戳已保存: {segments_path}")
        
        print(f"  ✓ 完成！共 {len(results)} 个句子时间戳")
        
        return results
    
    def _average_align(self, sentences: List[str], full_duration: float) -> List[Dict]:
        """平均分配时间戳"""
        n = max(len(sentences), 1)
        results = []
        for i, s in enumerate(sentences):
            start = full_duration * i / n
            end = full_duration * (i + 1) / n
            results.append({"sentence": s, "start": float(start), "end": float(end)})
        return results
    
