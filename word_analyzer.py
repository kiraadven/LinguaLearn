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
        分析句子，提取关键词、翻译和有用表达（单次API调用）
        
        Args:
            sentence: 英文句子
            
        Returns:
            包含翻译、关键词和有用表达的字典
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
3. useful_expressions: 1-3个最有价值的英语表达方式（数组），每个包含：
   - english: 英文表达（建议2-8个单词的短语或句型，简洁实用）
   - chinese: 中文翻译
   - difficulty: 难度等级（1-5，5最难）

选择重难点单词的标准：
- 大学四六级及以上词汇
- 专业术语
- 不常见的动词、形容词、名词
- 避免选择简单的介词、冠词等

选择有用表达的标准：
- 优先选择简短精炼的短语或句型（2-8个单词）
- 优先提取固定搭配、介词短语、动词短语等
- 优先选择能体现英语思维方式的表达
- 必须使用动词原型，不要使用句子中的时态形式

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
  ],
  "useful_expressions": [
    {{
      "english": "英文表达",
      "chinese": "中文翻译",
      "difficulty": 3
    }}
  ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的英语教学助手，擅长分析英文句子并提取关键词和有用表达。请始终返回有效的JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # 尝试提取JSON（如果AI返回了额外的文字）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # 验证结果格式
            if 'chinese_translation' not in result:
                raise ValueError("API返回格式不正确")
            
            # 确保 key_words 存在
            if 'key_words' not in result:
                result['key_words'] = []
            
            # 确保 useful_expressions 存在
            if 'useful_expressions' not in result:
                result['useful_expressions'] = []
            
            # 限制单词数量在2-6个之间
            if len(result['key_words']) > 6:
                result['key_words'] = sorted(
                    result['key_words'], 
                    key=lambda x: x.get('difficulty', 0), 
                    reverse=True
                )[:6]
            
            # 删除难度为1的表达，并限制在1-3个
            expressions = [expr for expr in result['useful_expressions'] if expr.get('difficulty', 0) != 1]
            # 过滤掉单词数少于3个或多于8个的表达
            expressions = [expr for expr in expressions if 2 <= len(expr.get('english', '').split()) <= 8]
            if len(expressions) > 3:
                expressions = sorted(expressions, key=lambda x: x.get('difficulty', 0), reverse=True)[:3]
            result['useful_expressions'] = expressions
            
            # 确保每个表达都有 difficulty 字段
            for expr in result['useful_expressions']:
                if 'difficulty' not in expr:
                    expr['difficulty'] = 3
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"API返回内容: {content}")
            return {
                'chinese_translation': '（翻译失败）',
                'key_words': [],
                'useful_expressions': []
            }
        except Exception as e:
            print(f"分析句子时出错: {e}")
            return {
                'chinese_translation': '（翻译失败）',
                'key_words': [],
                'useful_expressions': []
            }
    
    def batch_analyze(self, sentences: List[str]) -> List[Dict]:
        """
        批量分析多个句子（单次API调用）
        
        Args:
            sentences: 句子列表
            
        Returns:
            分析结果列表，每个包含 original_text, chinese_translation, key_words, useful_expressions
        """
        results = []
        total = len(sentences)
        
        for i, sentence in enumerate(sentences, 1):
            print(f"正在分析句子 {i}/{total}...")
            
            # 一次性调用API获取关键词和表达
            analysis_result = self.analyze_sentence(sentence)
            
            # 整理结果
            result = {
                'original_text': sentence,
                'chinese_translation': analysis_result.get('chinese_translation', ''),
                'key_words': analysis_result.get('key_words', []),
                'useful_expressions': analysis_result.get('useful_expressions', [])
            }
            results.append(result)
        
        return results
    
    def extract_keywords(self, sentence: str) -> Dict:
        """
        提取句子的关键词和翻译
        
        Args:
            sentence: 英文句子
            
        Returns:
            包含翻译和关键词的字典
        """
        result = self.analyze_sentence(sentence)
        return {
            'chinese_translation': result.get('chinese_translation', ''),
            'key_words': result.get('key_words', [])
        }
    
    def extract_expressions(self, sentence: str) -> List[Dict]:
        """
        提取句子的有用表达方式
        
        Args:
            sentence: 英文句子
            
        Returns:
            表达方式列表，每个包含 english, chinese 和 difficulty
        """
        result = self.analyze_sentence(sentence)
        return result.get('useful_expressions', [])

