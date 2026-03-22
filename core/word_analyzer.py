import os
import json
from typing import List, Dict
from openai import OpenAI
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class WordAnalyzer:
    def __init__(self, api_key: str = None, base_url: str = None,
                 source_lang: str = None, target_lang: str = None):
        """
        初始化单词分析器

        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL
            source_lang: 视频语言代码（如 'en', 'zh', 'ja'）
            target_lang: 用户母语代码（如 'zh', 'en'）
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        self.source_lang = source_lang or getattr(config, 'SOURCE_LANGUAGE', 'en')
        self.target_lang = target_lang or getattr(config, 'TARGET_LANGUAGE', 'zh')

        if not self.api_key:
            raise ValueError("请在.env文件中设置OPENAI_API_KEY")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _get_lang_name(self, lang_code: str, display_in: str = None) -> str:
        """获取语言的显示名称"""
        display_in = display_in or self.target_lang
        display_names = getattr(config, 'LANGUAGE_DISPLAY_NAMES', {})
        return display_names.get(lang_code, {}).get(display_in, lang_code)

    def _get_phonetic_desc(self) -> str:
        """获取源语言的音标/注音系统描述"""
        phonetic_systems = getattr(config, 'PHONETIC_SYSTEM_NAMES', {})
        system = phonetic_systems.get(self.source_lang, {})
        return system.get(self.target_lang, system.get('default', 'IPA'))

    def _build_prompt(self, sentence: str) -> str:
        """根据语言对构建分析提示词"""
        src_name = self._get_lang_name(self.source_lang)
        tgt_name = self._get_lang_name(self.target_lang, self.target_lang)
        phonetic_desc = self._get_phonetic_desc()

        # 根据目标语言选择回复语言指令
        reply_instructions = {
            'zh': f'请用{tgt_name}回答所有翻译和解释部分。',
            'en': f'Please provide all translations and explanations in English.',
            'ja': f'翻訳と説明はすべて日本語で提供してください。',
            'ko': f'모든 번역과 설명은 한국어로 제공해 주세요.',
            'de': f'Bitte alle Übersetzungen und Erklärungen auf Deutsch angeben.',
            'fr': f'Veuillez fournir toutes les traductions et explications en français.',
            'es': f'Por favor proporcione todas las traducciones y explicaciones en español.',
        }
        reply_instruction = reply_instructions.get(self.target_lang, f'Please respond in {tgt_name}.')

        prompt = f"""请分析以下{src_name}句子，并以JSON格式返回结果。{reply_instruction}

句子：{sentence}

请返回以下信息：
1. chinese_translation: 将原句翻译成{tgt_name}（字段名保持 chinese_translation，内容为{tgt_name}）
2. key_words: 2-6个重难点词汇（数组），每个词汇包含：
   - word: 词汇原文（{src_name}）
   - phonetic: 发音标注（使用{phonetic_desc}）
   - translation: {tgt_name}释义
   - difficulty: 难度等级（1-5，5最难）
3. useful_expressions: 1-3个最有价值的{src_name}表达方式（数组），每个包含：
   - english: {src_name}表达原文（2-8个词的短语或句型，字段名保持 english）
   - chinese: {tgt_name}翻译（字段名保持 chinese）
   - difficulty: 难度等级（1-5，5最难）

选择重难点词汇的标准：
- 中高级词汇（相当于大学四六级及以上水平）
- 专业术语
- 不常见的动词、形容词、名词
- 避免选择简单的介词、冠词等功能词

选择有用表达的标准：
- 优先选择简短精炼的短语或句型（2-8个词）
- 优先提取固定搭配、介词短语、动词短语等
- 优先选择能体现{src_name}语言思维方式的表达
- 必须使用词汇原型，不要使用句子中的时态变体形式

请直接返回JSON格式，不要添加任何其他文字：
{{
  "chinese_translation": "{tgt_name}翻译",
  "key_words": [
    {{
      "word": "词汇",
      "phonetic": "发音标注",
      "translation": "{tgt_name}释义",
      "difficulty": 3
    }}
  ],
  "useful_expressions": [
    {{
      "english": "{src_name}表达",
      "chinese": "{tgt_name}翻译",
      "difficulty": 3
    }}
  ]
}}"""
        return prompt

    def analyze_sentence(self, sentence: str) -> Dict:
        """
        分析句子，提取关键词、翻译和有用表达（单次API调用）

        Args:
            sentence: 原文句子（SOURCE_LANGUAGE）

        Returns:
            包含翻译、关键词和有用表达的字典
        """
        prompt = self._build_prompt(sentence)

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"你是一个专业的语言教学助手，擅长分析句子并提取关键词和有用表达。请始终返回有效的JSON格式。"},
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
            # 过滤掉词数少于2个或多于8个的表达
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

    def batch_analyze(self, sentences: List[str], max_workers: int = 10) -> List[Dict]:
        """
        批量分析多个句子（并行API调用）

        Args:
            sentences: 句子列表
            max_workers: 最大并行数

        Returns:
            分析结果列表，顺序与输入的 sentences 保持一致
        """
        total = len(sentences)
        results = [None] * total
        completed_count = 0
        lock = threading.Lock()

        def analyze_with_index(args):
            index, sentence = args
            analysis_result = self.analyze_sentence(sentence)
            return index, analysis_result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(analyze_with_index, (i, sentence)): i
                for i, sentence in enumerate(sentences)
            }

            for future in as_completed(future_to_index):
                try:
                    index, analysis_result = future.result()
                    results[index] = {
                        'original_text': sentences[index],
                        'chinese_translation': analysis_result.get('chinese_translation', ''),
                        'key_words': analysis_result.get('key_words', []),
                        'useful_expressions': analysis_result.get('useful_expressions', [])
                    }

                    with lock:
                        completed_count += 1
                        if completed_count % 10 == 0:
                            print(f"完成进度: {completed_count}/{total}")
                except Exception as e:
                    index = future_to_index[future]
                    print(f"分析句子 {index + 1} 时出错: {e}")
                    results[index] = {
                        'original_text': sentences[index],
                        'chinese_translation': '（分析失败）',
                        'key_words': [],
                        'useful_expressions': []
                    }

        return results
