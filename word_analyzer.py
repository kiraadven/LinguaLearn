import os
import json
from typing import List, Dict
from openai import OpenAI
import config


class WordAnalyzer:
    def __init__(self, api_key: str = None, base_url: str = None):
        """
        初始化单词分析器
        
        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        
        if not self.api_key:
            raise ValueError("请在.env文件中设置OPENAI_API_KEY")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def analyze_sentence(self, sentence: str) -> Dict:
        """
        分析句子，提取重难点单词、翻译等信息
        
        Args:
            sentence: 英文句子
            
        Returns:
            包含翻译和重难点单词的字典
        """
        prompt = f"""请分析以下英文句子，并以JSON格式返回结果：

句子：{sentence}

请返回以下信息：
1. chinese_translation: 中文翻译
2. key_words: 2-6个重难点单词（数组），每个单词包含：
   - word: 单词拼写
   - phonetic: 音标（使用国际音标IPA格式，如 /ˈwɜːrd/）
   - translation: 中文释义
   - difficulty: 难度等级（1-5，5最难）

选择重难点单词的标准：
- 大学四六级及以上词汇
- 专业术语
- 不常见的动词、形容词、名词
- 避免选择简单的介词、冠词等

请直接返回JSON格式，不要添加任何其他文字：
{{
  "chinese_translation": "中文翻译",
  "key_words": [
    {{
      "word": "单词",
      "phonetic": "/音标/",
      "translation": "中文释义",
      "difficulty": 3
    }}
  ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的英语教学助手，擅长分析英文句子并识别重难点单词。请始终返回有效的JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # 尝试提取JSON（如果AI返回了额外的文字）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # 验证结果格式
            if 'chinese_translation' not in result or 'key_words' not in result:
                raise ValueError("API返回格式不正确")
            
            # 限制单词数量在2-6个之间
            if len(result['key_words']) > 6:
                # 按难度排序，取前6个
                result['key_words'] = sorted(
                    result['key_words'], 
                    key=lambda x: x.get('difficulty', 0), 
                    reverse=True
                )[:6]
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"API返回内容: {content}")
            # 返回默认结果
            return {
                'chinese_translation': '（翻译失败）',
                'key_words': []
            }
        except Exception as e:
            print(f"分析句子时出错: {e}")
            return {
                'chinese_translation': '（翻译失败）',
                'key_words': []
            }
    
    def batch_analyze(self, sentences: List[str]) -> List[Dict]:
        """
        批量分析多个句子
        
        Args:
            sentences: 句子列表
            
        Returns:
            分析结果列表
        """
        results = []
        total = len(sentences)
        
        for i, sentence in enumerate(sentences, 1):
            print(f"正在分析句子 {i}/{total}...")
            result = self.analyze_sentence(sentence)
            result['original_text'] = sentence
            results.append(result)
        
        return results


if __name__ == "__main__":
    # 测试代码
    analyzer = WordAnalyzer()
    
    test_sentence = "Climate change is one of the most pressing issues of our time."
    
    print(f"测试句子: {test_sentence}\n")
    result = analyzer.analyze_sentence(test_sentence)
    
    print(f"中文翻译: {result['chinese_translation']}\n")
    print("重难点单词:")
    for word_info in result['key_words']:
        print(f"  - {word_info['word']} {word_info['phonetic']}")
        print(f"    {word_info['translation']} (难度: {word_info['difficulty']})")

