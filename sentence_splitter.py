import re
import os
import nltk
from typing import List

class SentenceSplitter:
    def __init__(self):
        """初始化句子分割器"""

        # 设置本地 nltk_data 目录
        self.nltk_data_dir = os.path.join(
            os.path.dirname(__file__),
            "nltk_data"
        )
        os.makedirs(self.nltk_data_dir, exist_ok=True)

        # 添加到 nltk 搜索路径
        if self.nltk_data_dir not in nltk.data.path:
            nltk.data.path.insert(0, self.nltk_data_dir)

        # 检查 punkt 是否存在
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            print("正在下载 NLTK punkt tokenizer 到本地目录...")
            nltk.download("punkt", download_dir=self.nltk_data_dir)
    
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
    
 