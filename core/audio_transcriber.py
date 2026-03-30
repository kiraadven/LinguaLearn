import os
import re
import json
import unicodedata
from typing import List, Dict, Optional, Tuple
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

def _is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF or   # CJK Unified Ideographs
        0x3040 <= code <= 0x30FF or   # Hiragana/Katakana
        0xAC00 <= code <= 0xD7AF      # Hangul
    )


def _normalize_token(token: str, is_cjk: bool = False) -> str:
    """归一化 token（支持多语种 Unicode 文本）"""
    text = (token or "").strip().lower()
    if not text:
        return ""

    out = []
    for ch in text:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if is_cjk:
            if _is_cjk_char(ch) or cat.startswith("L") or cat.startswith("N"):
                out.append(ch)
        else:
            if cat.startswith("L") or cat.startswith("N") or ch in {"'", "’"}:
                out.append("'" if ch == "’" else ch)

    normalized = "".join(out).strip("'")
    return normalized

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
            raw_tokens = re.findall(r"[^\s]+", sentence or "")
            tokens = []
            for t in raw_tokens:
                norm = _normalize_token(t)
                if norm:
                    tokens.append(norm)
            return tokens

    def _iter_with_progress(self, sentences: List[str]):
        """在 tqdm 不可用时自动降级为普通迭代"""
        iterator = enumerate(sentences)
        if HAS_TQDM:
            return tqdm(iterator, total=len(sentences), desc="对齐句子")
        return iterator

    def _similarity(self, a: str, b: str) -> float:
        """字符串相似度（difflib 不可用时退化为集合重叠）"""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        if HAS_DIFFLIB:
            return SequenceMatcher(None, a, b).ratio()

        a_set = set(a.split())
        b_set = set(b.split())
        if not a_set or not b_set:
            return 0.0
        return len(a_set & b_set) / max(len(a_set), len(b_set))

    def _token_match(self, stream_token: str, target_token: str, threshold: float = 0.84) -> bool:
        if not stream_token or not target_token:
            return False
        if stream_token == target_token:
            return True
        if self.is_cjk:
            return stream_token == target_token
        return self._similarity(stream_token, target_token) >= threshold

    def _sequential_sentence_match(
        self,
        word_stream: List[Dict],
        sent_tokens: List[str],
        search_start_idx: int,
        lookahead: int = 220,
        end_limit_idx: Optional[int] = None,
    ) -> Optional[Tuple[int, int, float]]:
        """
        按时间顺序做单调匹配，避免全局跳跃导致越对越偏。
        返回 (start_idx, end_idx, match_ratio)。
        """
        if not sent_tokens:
            return None

        n = len(word_stream)
        if n == 0:
            return None

        start_scan = max(0, min(search_start_idx, n - 1))
        hard_end = n if end_limit_idx is None else min(n, end_limit_idx + 1)
        end_scan = min(hard_end, start_scan + lookahead)
        if start_scan >= end_scan:
            return None

        # 先在局部窗口找一个更可靠的起点（优先命中前两个 token）
        first_tok = sent_tokens[0]
        second_tok = sent_tokens[1] if len(sent_tokens) > 1 else None
        candidate_start = None

        for i in range(start_scan, end_scan):
            if not self._token_match(word_stream[i]["norm"], first_tok):
                continue
            if second_tok:
                second_hit = False
                for j in range(i + 1, min(i + 8, end_scan)):
                    if self._token_match(word_stream[j]["norm"], second_tok):
                        second_hit = True
                        break
                if second_hit:
                    candidate_start = i
                    break
            else:
                candidate_start = i
                break

        if candidate_start is None:
            candidate_start = start_scan

        # 从 candidate_start 开始顺序吃 token
        max_span = min(n, candidate_start + max(18, len(sent_tokens) * 5))
        token_ptr = 0
        matched_positions: List[int] = []

        for idx in range(candidate_start, max_span):
            if token_ptr >= len(sent_tokens):
                break
            if self._token_match(word_stream[idx]["norm"], sent_tokens[token_ptr]):
                matched_positions.append(idx)
                token_ptr += 1

        if not matched_positions:
            return None

        match_ratio = token_ptr / max(len(sent_tokens), 1)
        if match_ratio < 0.52:
            return None

        return matched_positions[0], matched_positions[-1], match_ratio

    def _local_fuzzy_window_match(
        self,
        word_stream: List[Dict],
        sent_tokens: List[str],
        search_start_idx: int,
        lookahead: int = 240,
        end_limit_idx: Optional[int] = None,
    ) -> Optional[Tuple[int, int, float]]:
        """当顺序匹配失败时，仅在局部窗口做模糊匹配兜底。"""
        if not sent_tokens:
            return None

        n = len(word_stream)
        if n == 0:
            return None

        target = " ".join(sent_tokens)
        base = max(0, min(search_start_idx, n - 1))
        scan_start = base
        hard_end = n if end_limit_idx is None else min(n, end_limit_idx + 1)
        scan_end = min(hard_end, base + lookahead)
        if scan_start >= scan_end:
            return None

        min_w = max(1, len(sent_tokens) - 3)
        max_w = min(scan_end - scan_start, len(sent_tokens) + 10)
        if min_w > max_w:
            min_w = max_w

        best: Optional[Tuple[int, int, float]] = None
        for s in range(scan_start, scan_end):
            for wlen in range(min_w, max_w + 1):
                e = s + wlen - 1
                if e >= scan_end:
                    break
                window = " ".join(w["norm"] for w in word_stream[s:e + 1])
                score = self._similarity(target, window)
                if not best or score > best[2]:
                    best = (s, e, score)

        if best and best[2] >= 0.46:
            return best
        return None

    def _mapping_value(self, split_mapping: Optional[Dict], idx: int) -> int:
        if not split_mapping:
            return idx
        if idx in split_mapping:
            return split_mapping[idx]
        s = str(idx)
        if s in split_mapping:
            return split_mapping[s]
        return idx

    def _build_split_groups(self, sentences: List[str], split_mapping: Optional[Dict]) -> List[List[int]]:
        """按 splitter 的原句映射把输出句子分组（同组来自同一个长句）。"""
        if not sentences:
            return []
        groups: List[List[int]] = []
        current = [0]
        current_key = self._mapping_value(split_mapping, 0)
        for i in range(1, len(sentences)):
            key = self._mapping_value(split_mapping, i)
            if key == current_key:
                current.append(i)
            else:
                groups.append(current)
                current = [i]
                current_key = key
        groups.append(current)
        return groups

    def align_sentences_to_timestamps(self, audio_path: str, sentences: List[str], 
                                       output_name: str = None, split_mapping: Optional[Dict] = None) -> List[Dict]:
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

        # 1) 获取单词时间戳（优先使用同一音频的缓存）
        same_audio_cached = (self._last_audio_path == audio_path and self._last_word_items)
        word_items = self._last_word_items if same_audio_cached else []

        if not word_items:
            print("  重新获取单词时间戳...")
            transcribed = self.transcribe_once_with_word_timestamps(audio_path)
            word_items = transcribed.get("words", []) or []

        if not word_items:
            print("  ⚠️ 无法获取单词时间戳，使用平均分配")
            return self._average_align(sentences, 0.0)

        # 2) 获取音频总时长
        full_duration = float(word_items[-1]["end"]) if word_items else 0.0
        print(f"  音频总时长: {full_duration:.2f}s")

        # 3) 构建归一化单词流
        word_stream = self._prepare_normalized_word_stream()
        if not word_stream:
            print("  ⚠️ 单词流为空，使用平均分配")
            return self._average_align(sentences, full_duration)

        print(f"  单词流长度: {len(word_stream)}")

        # 4) 分层对齐：
        #    先定位“长句整体”时间段，再在该段内顺序匹配其拆分出来的短句。
        groups = self._build_split_groups(sentences, split_mapping)
        split_group_count = sum(1 for g in groups if len(g) > 1)
        print(f"  分层对齐分组: {len(groups)} 组（长句拆分组: {split_group_count}）")
        results: List[Optional[Dict]] = [None] * len(sentences)
        group_cursor = 0

        for group in self._iter_with_progress(groups):
            # tqdm 包装的是 enumerate(sentences)，这里手动兼容
            if isinstance(group, tuple):
                _, group_indices = group
            else:
                group_indices = group

            merged_tokens: List[str] = []
            for idx in group_indices:
                merged_tokens.extend(self._tokenize_sentence(sentences[idx]))

            if not merged_tokens:
                s = min(group_cursor, len(word_stream) - 1)
                e = s
            else:
                whole_match = self._sequential_sentence_match(
                    word_stream=word_stream,
                    sent_tokens=merged_tokens,
                    search_start_idx=group_cursor,
                    lookahead=max(280, len(merged_tokens) * 7),
                )
                if not whole_match:
                    whole_match = self._local_fuzzy_window_match(
                        word_stream=word_stream,
                        sent_tokens=merged_tokens,
                        search_start_idx=group_cursor,
                        lookahead=max(320, len(merged_tokens) * 8),
                    )
                if whole_match:
                    s, e, _ = whole_match
                    if s < group_cursor:
                        s = group_cursor
                else:
                    s = min(group_cursor, len(word_stream) - 1)
                    e = min(len(word_stream) - 1, s + max(1, len(merged_tokens)) - 1)

            # 在 [s, e] 区间内部对每个短句做顺序匹配
            inner_cursor = s
            for pos, sent_idx in enumerate(group_indices):
                sentence = sentences[sent_idx]
                sent_tokens = self._tokenize_sentence(sentence)

                if not sent_tokens:
                    st_idx = min(inner_cursor, e)
                    ed_idx = st_idx
                else:
                    sub_match = self._sequential_sentence_match(
                        word_stream=word_stream,
                        sent_tokens=sent_tokens,
                        search_start_idx=inner_cursor,
                        lookahead=max(140, len(sent_tokens) * 7),
                        end_limit_idx=e,
                    )
                    if not sub_match:
                        sub_match = self._local_fuzzy_window_match(
                            word_stream=word_stream,
                            sent_tokens=sent_tokens,
                            search_start_idx=inner_cursor,
                            lookahead=max(180, len(sent_tokens) * 8),
                            end_limit_idx=e,
                        )

                    if sub_match:
                        st_idx, ed_idx, _ = sub_match
                        st_idx = max(st_idx, inner_cursor)
                        ed_idx = min(ed_idx, e)
                        if ed_idx < st_idx:
                            ed_idx = st_idx
                    else:
                        st_idx = min(inner_cursor, e)
                        ed_idx = st_idx

                start_time = float(word_stream[st_idx]["start"])
                end_time = float(word_stream[ed_idx]["end"])

                # 该长句最后一个短句：强制覆盖到长句末尾，避免词落到下一句
                if pos == len(group_indices) - 1:
                    end_time = max(end_time, float(word_stream[e]["end"]))

                prev_idx = sent_idx - 1
                prev_end = results[prev_idx]["end"] if prev_idx >= 0 and results[prev_idx] else 0.0
                if start_time < prev_end:
                    start_time = prev_end
                    end_time = max(end_time, start_time + 0.1)

                results[sent_idx] = {
                    "sentence": sentence,
                    "start": start_time,
                    "end": end_time,
                }

                inner_cursor = min(e, ed_idx + 1)

            group_cursor = min(len(word_stream) - 1, e + 1)

        # 类型收敛：None 理论上不会出现，这里做兜底
        finalized: List[Dict] = []
        last_end_fallback = 0.0
        for i, sentence in enumerate(sentences):
            item = results[i]
            if item is None:
                item = {"sentence": sentence, "start": last_end_fallback, "end": last_end_fallback + 0.5}
            finalized.append(item)
            last_end_fallback = item["end"]
        results = finalized

        # 5) 最终修正：确保连续、非重叠、且最后一句收口到音频尾部
        for i in range(len(results)):
            if i > 0 and results[i]["start"] < results[i-1]["end"]:
                results[i]["start"] = results[i-1]["end"]
            if results[i]["end"] < results[i]["start"]:
                results[i]["end"] = results[i]["start"] + 0.5
            if full_duration > 0:
                results[i]["end"] = min(results[i]["end"], full_duration)

        if results and full_duration > 0 and results[-1]["end"] < full_duration:
            results[-1]["end"] = full_duration

        # 6) 保存到 JSON 文件
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
    
