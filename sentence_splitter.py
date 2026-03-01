import re
import os
import nltk
from typing import List

class SentenceSplitter:
    def __init__(self, max_length: int = 130, min_length: int = 20):
        """
        初始化句子分割器
        
        Args:
            max_length: 句子最大字符数，超过则尝试智能分割
            min_length: 句子最小字符数，太短的句子会合并
        """
        # 设置本地 nltk_data 目录
        self.nltk_data_dir = os.path.join(
            os.path.dirname(__file__),
            "nltk_data"
        )

        # 添加到 nltk 搜索路径
        if self.nltk_data_dir not in nltk.data.path:
            nltk.data.path.insert(0, self.nltk_data_dir)

        # 检查 punkt 是否存在
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            print("正在下载 NLTK punkt tokenizer 到本地目录...")
            nltk.download("punkt", download_dir=self.nltk_data_dir)
        
        # 配置参数
        self.max_length = max_length
        self.min_length = min_length
        
        # 智能断句位置 - 在这些词后面分割
        self.split_patterns = [
            # 从句连词
            r'\b(that|which|who|whom|whose|where|when|why|how|if|unless|although|though|while|because|since|as|after|before|until|whenever|wherever)\b',
            # 并列连词 (前面有逗号时)
            r',\s*(and|but|or|so|yet|for|nor)\s+',
            # 介词短语后 (在较长的介词短语后分割)
            r'\b(in\s+the|in\s+his|in\s+her|in\s+its|in\s+their|on\s+the|at\s+the|to\s+the|for\s+the|with\s+the|from\s+the)\s+',
            # 关系从句前
            r'\b(which|that|who|whom)\s+',
            # 数字序号
            r'\d+\.\s+',
        ]
        
        # 不分割的位置（避免在这些词后分割）
        self.no_split_patterns = [
            r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|e\.g|i\.e|\.\.\.)\b',
            r'\b[A-Z][a-z]+\s+(is|are|was|were|be|been|being|have|has|had|do|does|did|will|would|could|should|may|might|must)\b',
        ]
    
    def _clean_transcription_errors(self, text: str) -> str:
        """
        清理转录错误
        
        常见转录错误：
        1. 重复词 (如 "the the")
        2. 缺失空格 (如 "wordword")
        3. 异常字符
        4. 口语填充词 (um, uh, like, you know)
        
        Args:
            text: 输入文本
            
        Returns:
            清理后的文本
        """
        # 移除重复词 (the the -> the)
        text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
        
        # 移除口语填充词
        filler_words = r'\b(um|uh|er|ah|like|you know|I mean|sort of|kind of|basically|actually|literally)\b'
        text = re.sub(filler_words, '', text, flags=re.IGNORECASE)
        
        # 清理多余空格
        text = re.sub(r'\s+', ' ', text)
        
        # 移除句子开头/结尾的标点和空白
        text = text.strip('.,;:!? ')
        
        return text
    
    def _validate_sentence(self, sentence: str) -> bool:
        """
        验证句子是否有效
        
        Args:
            sentence: 句子
            
        Returns:
            是否有效
        """
        # 跳过太短的句子
        if len(sentence) < 10:
            return False
        
        # 检查是否包含至少一个完整单词
        if not re.search(r'\b[a-zA-Z]+\b', sentence):
            return False
        
        # 检查是否有过多的特殊字符（可能是转录错误）
        special_chars = len(re.findall(r'[^\w\s\.,!?\'"-]', sentence))
        if special_chars > len(sentence) * 0.1:
            return False
        
        return True
    
    def _should_split_here(self, text: str, pos: int) -> bool:
        """检查是否应该在这里分割"""
        # 获取分割位置前后的上下文
        before = text[:pos].lower()
        after = text[pos:pos+50].lower()
        
        # 检查是否在不应该分割的位置
        for pattern in self.no_split_patterns:
            if re.search(pattern, before + after, re.IGNORECASE):
                return False
        
        # 检查是否在应该分割的位置
        for pattern in self.split_patterns:
            if re.search(pattern, before + after, re.IGNORECASE):
                # 额外检查：分割点前应该有实际的单词
                if before.strip() and not before.strip().endswith(('.', '!', '?')):
                    return True
        
        return False
    
    def _find_best_split_point(self, text: str, start: int, end: int) -> int:
        """
        找到最佳的分割点
        
        Args:
            text: 文本
            start: 起始位置
            end: 结束位置
            
        Returns:
            最佳分割点位置
        """
        text_slice = text[start:end]
        
        # 首先尝试在智能断点分割
        for pattern in self.split_patterns:
            match = re.search(pattern, text_slice, re.IGNORECASE)
            if match:
                split_pos = start + match.start()
                # 确保分割点前有足够的文本
                if split_pos - start > self.min_length // 2:
                    return split_pos
        
        # 如果没有找到智能断点，在句子中间位置分割
        mid = (start + end) // 2
        # 尝试找到最近的空格或逗号
        for sep in [', ', '; ', ': ', ' - ', '– ']:
            pos = text_slice.find(sep)
            if pos > 0 and pos < len(text_slice) // 2:
                return start + pos + len(sep)
        
        # 最后手段：在空格处分割
        space_pos = text.find(' ', mid)
        if space_pos > start and space_pos < end:
            return space_pos
        
        return end
    
    def _smart_split_long_sentence(self, sentence: str) -> List[str]:
        """
        智能分割过长的句子
        
        Args:
            sentence: 输入句子
            
        Returns:
            分割后的句子列表
        """
        if len(sentence) <= self.max_length:
            return [sentence]
        
        result = []
        current_start = 0
        text = sentence
        
        while current_start < len(text):
            # 找到剩余文本的结束位置
            remaining = text[current_start:]
            
            if len(remaining) <= self.max_length:
                result.append(remaining.strip())
                break
            
            # 找到最佳分割点
            search_end = current_start + self.max_length
            split_point = self._find_best_split_point(text, current_start, search_end)
            
            # 确保不会分成太短的片段
            if split_point - current_start < self.min_length:
                split_point = min(current_start + self.max_length, len(text))
            
            segment = text[current_start:split_point].strip()
            if segment:
                result.append(segment)
            
            current_start = split_point
        
        # 合并太短的片段
        if len(result) > 1:
            merged = []
            buffer = ""
            for seg in result:
                if len(buffer) + len(seg) < self.max_length:
                    buffer = (buffer + " " + seg).strip() if buffer else seg
                else:
                    if buffer:
                        merged.append(buffer)
                    buffer = seg
            if buffer:
                merged.append(buffer)
            result = merged
        
        return result
    
    def _clean_sentence(self, sentence: str) -> str:
        """清理句子"""
        # 移除多余的空白
        sentence = ' '.join(sentence.split())
        
        # 移除句子开头/结尾的标点
        sentence = sentence.strip('.,;:!? ')
        
        # 确保句子以大写字母开头
        if sentence and not sentence[0].isupper():
            sentence = sentence[0].upper() + sentence[1:]
        
        # 确保句子以标点结尾
        if sentence and sentence[-1] not in '.!?':
            sentence += '.'
        
        return sentence
    
    def split_text(self, text: str) -> List[str]:
        """
        将文本分割成适合学习的句子
        
        分割策略：
        1. 清理转录错误
        2. 使用 NLTK 进行基本句子分割
        3. 对过长的句子进行智能二次分割
        4. 清理和规范化每个句子
        5. 验证并过滤无效句子
        
        Args:
            text: 输入的英文文本
            
        Returns:
            适合学习的句子列表
        """
        # 预处理文本
        text = text.strip()
        
        # 清理转录错误
        text = self._clean_transcription_errors(text)
        
        # 规范化引号和特殊字符
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('…', '...')
        
        # 使用NLTK进行基本句子分割
        sentences = nltk.sent_tokenize(text)
        
        # 处理每个句子
        result_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 清理句子
            sentence = self._clean_sentence(sentence)
            
            # 验证句子是否有效
            if not self._validate_sentence(sentence):
                continue
            
            # 检查长度，必要时进行智能分割
            if len(sentence) > self.max_length:
                # 递归分割直到满足长度要求
                sub_sentences = self._smart_split_long_sentence(sentence)
                # 验证每个子句子
                for sub in sub_sentences:
                    if self._validate_sentence(sub):
                        result_sentences.append(sub)
            else:
                result_sentences.append(sentence)
        
        # 合并相邻的短句子
        if len(result_sentences) > 1:
            merged = []
            buffer = result_sentences[0] if result_sentences else ""
            
            for i in range(1, len(result_sentences)):
                current = result_sentences[i]
                
                # 如果缓冲区和当前句子都很短，合并它们
                if len(buffer) < self.min_length and len(current) < self.min_length:
                    buffer = buffer + " " + current
                else:
                    # 如果缓冲区达到最大长度，先输出
                    if len(buffer) > self.max_length * 0.8:
                        merged.append(buffer)
                        buffer = current
                    # 如果当前句子太短，缓冲
                    elif len(current) < self.min_length / 2:
                        buffer = buffer + " " + current
                    else:
                        merged.append(buffer)
                        buffer = current
            
            if buffer:
                merged.append(buffer)
            result_sentences = merged
        
        # 最终清理
        final_sentences = [self._clean_sentence(s) for s in result_sentences if s and self._validate_sentence(s)]
        
        return final_sentences
    
    def split_text_simple(self, text: str) -> List[str]:
        """
        简单模式：只使用 NLTK 进行基本句子分割，不做长度限制
        
        Args:
            text: 输入的英文文本
            
        Returns:
            句子列表
        """
        text = text.strip()
        sentences = nltk.sent_tokenize(text)
        return [s.strip() for s in sentences if s.strip()]
