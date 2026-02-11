"""
句子分割模块
使用NLTK进行智能句子分割
"""
import re
import nltk
from typing import List

class SentenceSplitter:
    def __init__(self):
        """初始化句子分割器"""
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("正在下载NLTK punkt tokenizer...")
            nltk.download('punkt')
    
    def split_text(self, text: str) -> List[str]:
        """
        将文本分割成句子
        
        Args:
            text: 输入的英文文本
            
        Returns:
            句子列表
        """
        # 清理文本
        text = text.strip()
        
        # 使用NLTK进行句子分割
        sentences = nltk.sent_tokenize(text)
        
        # 清理每个句子
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def split_with_timestamps(self, text: str, audio_duration: float) -> List[dict]:
        """
        分割句子并估算时间戳
        
        Args:
            text: 输入文本
            audio_duration: 音频总时长（秒）
            
        Returns:
            包含句子和时间戳的字典列表
        """
        sentences = self.split_text(text)
        
        if not sentences:
            return []
        
        # 计算每个句子的字符数
        total_chars = sum(len(s) for s in sentences)
        
        # 根据字符数比例分配时间
        result = []
        current_time = 0
        
        for sentence in sentences:
            char_ratio = len(sentence) / total_chars
            duration = audio_duration * char_ratio
            
            result.append({
                'text': sentence,
                'start_time': current_time,
                'end_time': current_time + duration,
                'duration': duration
            })
            
            current_time += duration
        
        return result


if __name__ == "__main__":
    # 测试代码
    splitter = SentenceSplitter()
    
    test_text = """
    Climate change is one of the most pressing issues of our time. 
    Scientists around the world are working to understand its impacts. 
    We must take action now to protect our planet for future generations.
    """
    
    sentences = splitter.split_text(test_text)
    print("分割结果：")
    for i, sentence in enumerate(sentences, 1):
        print(f"{i}. {sentence}")

