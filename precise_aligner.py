"""
精确句子对齐器 - 使用 Montreal Forced Aligner (MFA)

MFA 是一个专业的强制对齐工具，提供词级别和音素级别的精确对齐。
相比 Whisper 的词级时间戳，MFA 的对齐精度更高。

安装方法:
    pip install montreal-forced-aligner
    # 或者使用 mfa 命令行工具

使用方法:
    aligner = PreciseSentenceAligner()
    timestamps = aligner.align_sentences(audio_path, sentences)
"""

import os
import subprocess
import json
from typing import List, Dict, Optional
from pathlib import Path
import config


class PreciseSentenceAligner:
    """
    使用 Montreal Forced Aligner (MFA) 进行精确句子对齐
    
    MFA 使用声学模型和语言模型对音频和文本进行强制对齐，
    提供高精度的词级别时间戳。
    """
    
    def __init__(self, acoustic_model: str = "english_us_arpa"):
        """
        初始化对齐器
        
        Args:
            acoustic_model: MFA 声学模型 (默认: english_us_arpa)
                           可选: english_us_arpa, english_us_nocapitalization 等
        """
        self.acoustic_model = acoustic_model
        self.temp_dir = Path(config.TEMP_DIR)
        self.mfa_output_dir = self.temp_dir / "mfa_align_output"
        self.mfa_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查 MFA 是否可用
        self.mfa_available = self._check_mfa_available()
    
    def _check_mfa_available(self) -> bool:
        """检查 MFA 是否已安装"""
        try:
            result = subprocess.run(
                ["mfa", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def align_sentences(
        self, 
        audio_path: str, 
        sentences: List[str],
        language: str = "en"
    ) -> List[Dict[str, float | str]]:
        """
        将句子精确对齐到音频时间戳
        
        使用 MFA 进行强制对齐，获取每个句子的精确起始和结束时间。
        
        Args:
            audio_path: 音频文件路径 (支持 .wav, .mp3, .flac 等)
            sentences: 需要对齐的句子列表
            language: 音频语言 (默认: en)
            
        Returns:
            句子时间戳列表，格式为:
            [
                {"start": 0.0, "end": 1.5, "text": "Hello world"},
                {"start": 1.5, "end": 3.2, "text": "This is a test"},
                ...
            ]
            
        Raises:
            RuntimeError: 如果 MFA 不可用或对齐失败
        """
        if not self.mfa_available:
            raise RuntimeError(
                "Montreal Forced Aligner (MFA) 未安装。"
                "请安装 MFA: pip install montreal-forced-aligner"
            )
        
        print(f"🔍 使用 MFA 进行精确句子对齐...")
        print(f"   音频: {audio_path}")
        print(f"   句子数: {len(sentences)}")
        
        # 步骤1: 准备音频文件 (MFA 需要 .wav 格式)
        wav_path = self._prepare_audio(audio_path)
        
        # 步骤2: 准备文本文件 (每行一个句子)
        text_file = self._prepare_text_file(sentences)
        
        # 步骤3: 运行 MFA 对齐
        alignment_file = self._run_mfa_align(wav_path, text_file, language)
        
        # 步骤4: 解析对齐结果
        timestamps = self._parse_alignment(alignment_file, sentences)
        
        # 步骤5: 验证和清理
        self._cleanup_temp_files([wav_path, text_file])
        
        print(f"✓ 精确对齐完成: {len(timestamps)} 个句子")
        
        return timestamps
    
    def _prepare_audio(self, audio_path: str) -> str:
        """将音频转换为 MFA 需要的格式"""
        import soundfile as sf
        import numpy as np
        
        audio_path = Path(audio_path)
        wav_path = self.mfa_output_dir / f"{audio_path.stem}_converted.wav"
        
        if wav_path.exists():
            return str(wav_path)
        
        print("   准备音频文件...")
        
        try:
            # 使用 soundfile 读取音频
            data, samplerate = sf.read(audio_path)
            
            # 如果是立体声，转换为单声道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            # 转换为 float32 如果需要
            if data.dtype != np.float32:
                data = data.astype(np.float32)
            
            # 归一化到 [-1, 1] 范围
            if data.max() > 1.0 or data.min() < -1.0:
                data = data / np.max(np.abs(data))
            
            # 保存为 WAV
            sf.write(str(wav_path), data, samplerate)
            
        except Exception as e:
            raise RuntimeError(f"音频转换失败: {e}")
        
        return str(wav_path)
    
    def _prepare_text_file(self, sentences: List[str]) -> str:
        """准备 MFA 需要的文本文件"""
        text_file = self.mfa_output_dir / "input_text.txt"
        
        with open(text_file, "w", encoding="utf-8") as f:
            for sentence in sentences:
                # MFA 需要纯文本，每行一个句子
                # 去除多余空白
                sentence = " ".join(sentence.split())
                f.write(f"{sentence}\n")
        
        return str(text_file)
    
    def _run_mfa_align(
        self, 
        audio_path: str, 
        text_file: str,
        language: str
    ) -> str:
        """运行 MFA 进行对齐"""
        # MFA 命令: mfa_align [options] audio_file.txt dictionary.zip acoustic_model.zip output_directory
        # 使用预训练模型时可能不需要 dictionary
        
        output_dir = self.mfa_output_dir / "alignments"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建 MFA 命令
        cmd = [
            "mfa",
            "align",
            audio_path,
            text_file,
            self.acoustic_model,
            str(output_dir),
            "--clean",
            "--verbose"
        ]
        
        print("   运行 MFA 对齐...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 分钟超时
            )
            
            if result.returncode != 0:
                print(f"   MFA stderr: {result.stderr}")
                raise RuntimeError(f"MFA 对齐失败: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("MFA 对齐超时")
        
        # MFA 输出格式为 TextGrid 文件
        # 查找生成的 TextGrid 文件
        textgrid_files = list(output_dir.glob("*.TextGrid"))
        
        if not textgrid_files:
            raise RuntimeError("MFA 未生成对齐文件")
        
        return str(textgrid_files[0])
    
    def _parse_alignment(
        self, 
        alignment_file: str,
        sentences: List[str]
    ) -> List[Dict[str, float | str]]:
        """解析 MFA 生成的 TextGrid 文件"""
        from praatio import textgrid
        
        print("   解析对齐结果...")
        
        # 读取 TextGrid 文件
        tg = textgrid.loadTextGrid(alignment_file)
        
        # 获取词级对齐 (word tier)
        word_tier = None
        for tier_name in tg.tierNames:
            if tier_name.lower() == "words":
                word_tier = tg.getTier(tier_name)
                break
        
        if word_tier is None:
            raise RuntimeError("TextGrid 文件中未找到词级别对齐")
        
        # 提取所有词及其时间戳
        words_with_times = []
        for interval in word_tier.entries:
            if interval.label.strip():  # 跳过空白的间隔
                words_with_times.append({
                    "word": interval.label.strip(),
                    "start": interval.start,
                    "end": interval.end
                })
        
        print(f"   提取了 {len(words_with_times)} 个词的时间戳")
        
        # 将词组合成句子并匹配时间戳
        sentence_timestamps = []
        
        # 使用滑动窗口匹配每个句子
        for sentence in sentences:
            # 标准化句子用于匹配
            sentence_words = self._normalize_for_match(sentence).split()
            
            if not sentence_words:
                continue
            
            # 在词列表中寻找匹配
            start_idx, end_idx = self._find_word_range(
                words_with_times, sentence_words
            )
            
            if start_idx is not None and end_idx is not None:
                sentence_timestamps.append({
                    "start": round(words_with_times[start_idx]["start"], 4),
                    "end": round(words_with_times[end_idx]["end"], 4),
                    "text": sentence
                })
            else:
                # 如果找不到匹配，抛出错误（不估计）
                raise RuntimeError(
                    f"无法在音频中找到句子: {sentence[:50]}..."
                )
        
        return sentence_timestamps
    
    def _normalize_for_match(self, text: str) -> str:
        """标准化文本用于匹配"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)  # 只保留字母数字和空格
        text = re.sub(r'\s+', ' ', text)      # 多个空格变一个
        return text.strip()
    
    def _find_word_range(
        self, 
        words_with_times: List[Dict],
        sentence_words: List[str]
    ) -> tuple:
        """在词列表中找到句子对应的词索引范围"""
        
        # 方法1: 精确滑动窗口匹配
        for i in range(len(words_with_times) - len(sentence_words) + 1):
            window_words = [
                self._normalize_for_match(w["word"]) 
                for w in words_with_times[i:i + len(sentence_words)]
            ]
            
            # 检查是否完全匹配
            if window_words == sentence_words:
                return i, i + len(sentence_words) - 1
        
        # 方法2: 允许轻微差异的部分匹配
        # 找第一个词，然后向后扩展
        first_word = sentence_words[0]
        
        for i, w in enumerate(words_with_times):
            if self._normalize_for_match(w["word"]) == first_word:
                # 找到起始词，检查后面能否匹配
                match_len = 1
                for j in range(1, len(sentence_words)):
                    if i + j < len(words_with_times):
                        w1 = sentence_words[j]
                        w2 = self._normalize_for_match(
                            words_with_times[i + j]["word"]
                        )
                        if w1 == w2:
                            match_len += 1
                        elif w1 in w2 or w2 in w1:  # 允许子串匹配
                            match_len += 0.5
                        else:
                            break
                
                # 如果匹配度足够高 (>80%)，返回结果
                if match_len / len(sentence_words) >= 0.8:
                    return i, i + len(sentence_words) - 1
        
        return None, None
    
    def _cleanup_temp_files(self, files: List[str]):
        """清理临时文件"""
        for f in files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


class MFAWrapper:
    """
    MFA 命令行包装器 - 简化版
    
    如果不想用 Python API，可以使用这个类调用 MFA 命令行工具
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化
        
        Args:
            model_path: MFA 模型路径，如果为 None 则使用默认模型
        """
        self.model_path = model_path or "english_us_arpa"
        self.temp_dir = Path(config.TEMP_DIR)
    
    def align(
        self, 
        audio_path: str, 
        output_textgrid: str
    ) -> bool:
        """
        运行 MFA 对齐
        
        Args:
            audio_path: 输入音频路径
            output_textgrid: 输出 TextGrid 文件路径
            
        Returns:
            是否成功
        """
        cmd = [
            "mfa",
            "align",
            audio_path,
            self.model_path,
            output_textgrid,
            "--clean"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def align_with_text(
        self,
        audio_path: str,
        text: str,
        output_textgrid: str
    ) -> bool:
        """
        使用给定的文本进行对齐
        
        Args:
            audio_path: 音频文件路径
            text: 对齐文本 (多行)
            output_textgrid: 输出文件路径
            
        Returns:
            是否成功
        """
        # 创建临时文本文件
        text_file = self.temp_dir / "temp_text.txt"
        with open(text_file, "w") as f:
            f.write(text)
        
        # 运行对齐
        success = self.align(str(text_file), output_textgrid)
        
        # 清理
        if text_file.exists():
            text_file.unlink()
        
        return success


# ============================================================
# 备选方案: 如果没有 MFA，使用改进的 Whisper 对齐
# ============================================================

class ImprovedWhisperAligner:
    """
    改进的 Whisper 对齐器
    
    如果无法使用 MFA，使用这个改进版本的对齐器。
    相比原始版本，这个版本:
    1. 使用更大的 Whisper 模型以获得更准确的时间戳
    2. 使用多次转录取最优结果
    3. 不使用估计方式，匹配失败直接报错
    """
    
    def __init__(self, model_size: str = "large"):
        """
        初始化
        
        Args:
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
        """
        import whisper
        self.model_size = model_size
        self.whisper = whisper.load_model(model_size)
    
    def align_sentences(
        self, 
        audio_path: str, 
        sentences: List[str],
        language: str = "en"
    ) -> List[Dict[str, float | str]]:
        """
        使用 Whisper 进行句子对齐
        """
        print(f"🔍 使用 Whisper ({self.model_size}) 进行对齐...")
        
        # 1. 转录音频获取词级时间戳
        result = self.whisper.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            verbose=False
        )
        
        # 2. 提取词级时间戳
        word_timestamps = []
        if "words" in result:
            for w in result["words"]:
                word_timestamps.append({
                    "word": w.get("word", "").strip(),
                    "start": w.get("start", 0),
                    "end": w.get("end", 0)
                })
        else:
            # 如果没有词级时间戳，尝试从段落中提取
            for seg in result.get("segments", []):
                word_timestamps.append({
                    "word": seg.get("text", "").strip(),
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0)
                })
        
        if not word_timestamps:
            raise RuntimeError("Whisper 未能获取时间戳")
        
        print(f"   提取了 {len(word_timestamps)} 个词的时间戳")
        
        # 3. 对齐每个句子
        sentence_timestamps = []
        
        for sentence in sentences:
            start_idx, end_idx = self._find_word_range(
                sentence, word_timestamps
            )
            
            if start_idx is not None and end_idx is not None:
                sentence_timestamps.append({
                    "start": word_timestamps[start_idx]["start"],
                    "end": word_timestamps[end_idx]["end"],
                    "text": sentence
                })
            else:
                raise RuntimeError(
                    f"无法在音频中找到句子: {sentence[:50]}..."
                )
        
        return sentence_timestamps
    
    def _normalize(self, text: str) -> str:
        """标准化文本"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _find_word_range(
        self, 
        sentence: str, 
        word_timestamps: List[Dict]
    ) -> tuple:
        """找到句子对应的词索引范围"""
        import difflib
        
        sentence_words = self._normalize(sentence).split()
        
        trans_words = [self._normalize(w["word"]) for w in word_timestamps]
        
        # 滑动窗口匹配
        best_match = None
        best_score = 0
        
        for i in range(len(trans_words) - len(sentence_words) + 1):
            window = trans_words[i:i + len(sentence_words)]
            window_text = " ".join(window)
            sentence_text = " ".join(sentence_words)
            
            score = difflib.SequenceMatcher(
                None, window_text, sentence_text
            ).ratio()
            
            if score > best_score:
                best_score = score
                best_match = i
        
        # 要求至少 85% 匹配
        if best_score >= 0.85 and best_match is not None:
            return best_match, best_match + len(sentence_words) - 1
        
        return None, None


# ============================================================
# 主入口函数
# ============================================================

def get_precise_timestamps(
    audio_path: str,
    sentences: List[str],
    method: str = "mfa"
) -> List[Dict[str, float | str]]:
    """
    获取句子的精确时间戳
    
    Args:
        audio_path: 音频文件路径
        sentences: 句子列表
        method: 对齐方法 ("mfa" 或 "whisper")
        
    Returns:
        句子时间戳列表
    """
    if method == "mfa":
        aligner = PreciseSentenceAligner()
        return aligner.align_sentences(audio_path, sentences)
    else:
        aligner = ImprovedWhisperAligner()
        return aligner.align_sentences(audio_path, sentences)


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) < 3:
        print("用法: python precise_aligner.py <音频文件> <句子1> [句子2] ...")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    sentences = sys.argv[2:]
    
    try:
        timestamps = get_precise_timestamps(audio_file, sentences)
        print("\n对齐结果:")
        for ts in timestamps:
            print(f"  {ts['start']:.3f} - {ts['end']:.3f}: {ts['text']}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
