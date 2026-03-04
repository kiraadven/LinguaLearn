import os
import re
import json
import nltk
from typing import List
from openai import OpenAI
import config

# 确保 nltk 资源已下载
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class SentenceSplitter:
    def __init__(self, max_words: int = 160, min_words: int = 30):
        """
        初始化句子分割器
        
        Args:
            max_words: 句子最大单词数
            min_words: 句子最小单词数
        """
        self.max_words = max_words
        self.min_words = min_words
        
        # 分割映射：记录每个输出句子对应哪个原始句子
        # 结构: {输出句子索引: 原始句子索引}
        self.split_mapping = {}
        
        # 初始化 OpenAI 客户端 (gpt-4-ca)
        self.client = OpenAI(
            api_key=config.SPLITTER_API_KEY,
            base_url=config.SPLITTER_BASE_URL
        )
        
        # 分句提示词
        self.prompt = f"""你是一个专业的英语学习内容分句助手。你的任务是将下面标有序号的超长英文句子拆分成长度适合英语学习者学习的短句。

具体要求：
1. 只处理下面标有序号（1. 2. 3. 等）的英文句子，其他句子不要改动
2. 对于每个超长句子，拆分规则优先级：
   - 在句号(.)、问号(?)、感叹号(!)处分割（优先）
   - 在分号(;)处分割
   - 在并列连词(and, but, or, nor, so, yet)前分割
   - 在从属连词(because, although, while, whereas, if, unless, since, when, where, why, how)前分割
   - 在关系代词(which, that, who, whom, whose)前分割
3. 拆分后每个子句必须在 {self.min_words}-{self.max_words} 个单词之间
4. 少于 {self.min_words} 个单词的子句要与相邻子句合并
5. 保留原始标点，确保每个句子以标点结尾
6. 输出格式：每个编号的句子拆分后多行输出，编号仍保留（格式如 "1. 拆分的子句1"）
7. 不要有任何解释或其他内容

需要拆分的句子："""

    def split_text(self, text: str) -> List[str]:
        """
        使用 gpt-4-ca API 将文本分割成适合学习的句子
        
        Args:
            text: 输入的英文文本
            
        Returns:
            适合学习的句子列表
        """
        # 重置映射
        self.split_mapping = {}
        
        if not text or not text.strip():
            return []
        
        # 预处理文本
        text = text.strip()
     
        # 如果文本太短，直接返回
        if len(text) < 50:
            self.split_mapping[0] = 0  # 输出索引0 -> 原始索引0
            return [self._clean_sentence(text)]
        
        # 用 NLTK 进行句子分割
        nltk_sentences = nltk.sent_tokenize(text)
        
        # 分离出超长的句子（超过 max_words 的）和正常的句子
        long_sentences = []
        long_indices = []  # 记录超长句子在原列表中的索引
        
        for i, sent in enumerate(nltk_sentences):
            word_count = len(sent.split())
            if word_count > self.max_words:
                long_sentences.append(sent)
                long_indices.append(i)
        
        if not long_sentences:
            # 没有超长句子，直接返回 NLTK 分句结果
            # 每个输出句子对应原始句子
            for i in range(len(nltk_sentences)):
                self.split_mapping[i] = i
            return [self._clean_sentence(s) for s in nltk_sentences]
        
        # 有超长句子，标记序号后一次性送给 API
        # 构建带序号的超长句子文本
        numbered_text = ""
        for idx, sent in enumerate(long_sentences, 1):
            numbered_text += f"{idx}. {sent}\n"
        
        print(f"调用 API 进行智能拆分: {len(numbered_text)}个句子")
        try:
            split_result = self._call_api_split(numbered_text)
            
            # 解析返回的句子，按原始序号分组
            split_by_index = self._parse_numbered_sentences_grouped(split_result)
            
            # 重建结果列表，保持原始位置顺序
            result = []
            output_idx = 0
            
            for i, sent in enumerate(nltk_sentences):
                if i in long_indices:
                    # 这是一个超长句子，获取对应的拆分结果
                    idx = long_indices.index(i)  # 这是第几个超长句子
                    if idx in split_by_index:
                        # 拆分结果可能有多个句子，全部加入
                        for sub_sent in split_by_index[idx]:
                            result.append(self._clean_sentence(sub_sent))
                            # 记录映射：输出索引 -> 原始句子索引
                            self.split_mapping[output_idx] = i
                            output_idx += 1
                    else:
                        # 如果没有拆分结果，保持原句
                        result.append(self._clean_sentence(sent))
                        self.split_mapping[output_idx] = i
                        output_idx += 1
                else:
                    # 正常句子，直接加入
                    result.append(self._clean_sentence(sent))
                    self.split_mapping[output_idx] = i
                    output_idx += 1
            
            return result
            
        except Exception as e:
            print(f"分句时出错: {e}")
            # 出错时使用 NLTK 分句结果
            for i in range(len(nltk_sentences)):
                self.split_mapping[i] = i
            return [self._clean_sentence(s) for s in nltk_sentences]
    
    def get_split_mapping(self) -> dict:
        """
        获取分割映射
        
        Returns:
            字典，key 是输出句子索引，value 是对应的原始句子索引
        """
        return self.split_mapping
    
    def _parse_numbered_sentences_grouped(self, content: str) -> dict:
        """
        解析 API 返回的带序号的句子，按原始序号分组
        
        Args:
            content: API 返回的原始内容
            
        Returns:
            字典，key 是原始序号(0-based)，value 是该句子拆分后的子句列表
        """
        if not content:
            return {}
        
        result = {}
        current_index = None
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 检查是否以序号开头（如 "1. " 或 "1:"）
            match = re.match(r'^(\d+)[\.\:]\s*', line)
            if match:
                # 这是一个新的句子组
                current_index = int(match.group(1)) - 1  # 转为 0-based
                # 去掉序号部分
                line = re.sub(r'^\d+[\.\:]\s*', '', line)
                if line:
                    if current_index not in result:
                        result[current_index] = []
                    result[current_index].append(line)
            else:
                # 这是上一个句子的续行（超长句子拆分后可能有续行）
                if current_index is not None and current_index in result:
                    result[current_index].append(line)
        
        return result
    
    def _parse_numbered_sentences(self, content: str) -> List[str]:
        """
        解析 API 返回的带序号的句子
        
        Args:
            content: API 返回的原始内容
            
        Returns:
            句子列表（去除序号）
        """
        if not content:
            return []
        
        sentences = []
        current_sentence = ""
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 去掉开头的序号（如 "1. " 或 "1:"）
            line = re.sub(r'^\d+[\.\:]\s*', '', line)
            
            if line:
                sentences.append(line)
        
        return sentences
    
    def _has_sentences_exceeding_limit(self, sentences: List[str]) -> bool:
        """
        检查是否存在超过单词限制的句子
        
        Args:
            sentences: 句子列表
            
        Returns:
            是否存在超长句子
        """
        for sentence in sentences:
            word_count = len(sentence.split())
            if word_count > self.max_words:
                return True
        return False
    
    def _call_api_split(self, text: str) -> str:
        """
        调用 Splitter API 进行分句
        
        Args:
            text: 输入文本
            
        Returns:
            API 返回的原始内容（未解析的句子字符串）
        """
        full_prompt = f"{self.prompt}\n\n{text}"
        
        response = self.client.chat.completions.create(
            model=config.SPLITTER_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.3,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        
        return content
    
    def _parse_sentences(self, content: str) -> List[str]:
        """
        解析 API 返回的内容为句子列表
        
        Args:
            content: API 返回的原始内容
            
        Returns:
            句子列表
        """
        if not content:
            return []
        
        # 按行分割，去除空行
        lines = content.strip().split('\n')
        
        sentences = []
        for line in lines:
            line = line.strip()
            if line:
                sentences.append(line)
        
        return sentences
    
   
    def _clean_sentence(self, sentence: str) -> str:
        """
        清理句子
        
        Args:
            sentence: 原始句子
            
        Returns:
            清理后的句子
        """
        if not sentence:
            return ""
        
        # 去除首尾空白
        sentence = sentence.strip()
        
        # 确保句子以标点结尾
        if sentence and sentence[-1] not in '.!?;':
            # 如果没有标点，尝试添加句号
            sentence = sentence + '.'
        
        # 去除可能的编号（如 "1. ", "2. " 等）
        sentence = re.sub(r'^\d+[\.\)]\s*', '', sentence)
        
        # 去除可能的引号包装
        sentence = re.sub(r'^["\'](.+?)["\']$', r'\1', sentence)
        
        # 规范化空格
        sentence = re.sub(r'\s+', ' ', sentence)
        
        return sentence
    
    def _fallback_split(self, text: str) -> List[str]:
        """
        备用分句方法（当 API 调用失败时使用）
        
        Args:
            text: 输入文本
            
        Returns:
            句子列表
        """
        # 简单的正则分句
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # 清理并返回
        return [self._clean_sentence(s) for s in sentences if s.strip()]
    