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
    def __init__(self, max_words: int = 160, min_words: int = 30,
                 source_lang: str = None):
        """
        初始化句子分割器

        Args:
            max_words: 拉丁语系句子最大单词数；CJK语系则为最大字符数/5
            min_words: 拉丁语系句子最小单词数；CJK语系则为最小字符数/5
            source_lang: 源语言代码（影响分割逻辑）
        """
        self.max_words = max_words
        self.min_words = min_words
        self.source_lang = source_lang or getattr(config, 'SOURCE_LANGUAGE', 'en')
        self.target_lang = getattr(config, 'TARGET_LANGUAGE', 'zh')

        # CJK语言用字符数计算，换算成等效"词数"
        self.is_cjk = self.source_lang in getattr(config, 'CJK_LANGUAGES', {'zh', 'ja', 'ko'})
        if self.is_cjk:
            # CJK字符：大约每5个字符相当于1个英文单词
            self.max_chars = max_words * 5
            self.min_chars = min_words * 5

        # 分割映射：记录每个输出句子对应哪个原始句子
        self.split_mapping = {}

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=config.SPLITTER_API_KEY,
            base_url=config.SPLITTER_BASE_URL
        )

        # 分句提示词（根据源语言动态生成）
        self.prompt = self._build_split_prompt()

    def _build_split_prompt(self) -> str:
        """根据源语言构建分句提示词"""
        lang_names = getattr(config, 'LANGUAGE_DISPLAY_NAMES', {})
        aliases = getattr(config, 'LANGUAGE_CODE_ALIASES', {})
        canonical = aliases.get(self.source_lang, self.source_lang)
        native_names = getattr(config, 'LANGUAGE_NATIVE_NAMES', {})
        src_name = (
            lang_names.get(self.source_lang, {}).get(self.target_lang)
            or lang_names.get(canonical, {}).get(self.target_lang)
            or native_names.get(self.source_lang)
            or native_names.get(canonical)
            or self.source_lang
        )

        if self.is_cjk:
            # CJK语言分句提示词
            return f"""你是一个专业的{src_name}学习内容分句助手。你的任务是将下面标有序号的超长{src_name}句子拆分成长度适合学习的短句。

具体要求：
1. 只处理下面标有序号（1. 2. 3. 等）的{src_name}句子，其他句子不要改动
2. 对于每个超长句子，拆分规则优先级：
   - 在句号(。.）、问号(？?)、感叹号(！!)处分割（优先）
   - 在分号(；;)处分割
   - 在并列连词处分割
   - 在从属连词处分割
3. 拆分后每个子句必须在 {self.min_chars}-{self.max_chars} 个字符之间
4. 少于 {self.min_chars} 个字符的子句要与相邻子句合并
5. 保留原始标点，确保每个句子以标点结尾
6. 输出格式：每个编号的句子拆分后多行输出，编号仍保留（格式如 "1. 拆分的子句1"）
7. **绝对不要添加、删除或修改任何文字**，只做拆分动作

需要拆分的句子："""
        else:
            # 拉丁语系分句提示词
            return f"""你是一个专业的{src_name}学习内容分句助手。你的任务是将下面标有序号的超长{src_name}句子拆分成长度适合学习的短句。

具体要求：
1. 只处理下面标有序号（1. 2. 3. 等）的{src_name}句子，其他句子不要改动
2. 对于每个超长句子，拆分规则优先级：
   - 在句号(.)、问号(?)、感叹号(!)处分割（优先）
   - 在分号(;)处分割
   - 在并列连词(and, but, or, nor, so, yet, und, aber, oder, et, mais, y, pero)前分割
   - 在从属连词前分割
   - 在关系代词前分割
3. 拆分后每个子句必须在 {self.min_words}-{self.max_words} 个单词之间
4. 少于 {self.min_words} 个单词的子句要与相邻子句合并
5. 保留原始标点，确保每个句子以标点结尾
6. 输出格式：每个编号的句子拆分后多行输出，编号仍保留（格式如 "1. 拆分的子句1"）
7. **绝对不要添加、删除或修改任何单词**，只做拆分动作
8. 拆分后的子句语法不完整是正常的，不用追求语法完整

需要拆分的句子："""

    def _count_length(self, text: str) -> int:
        """根据语言返回适当的长度计数（单词数或字符数/5）"""
        if self.is_cjk:
            return len(text)
        else:
            return len(text.split())

    def _is_too_long(self, text: str) -> bool:
        """判断句子是否超过长度限制"""
        if self.is_cjk:
            return len(text) > self.max_chars
        else:
            return len(text.split()) > self.max_words

    def _split_by_cjk_punctuation(self, text: str) -> List[str]:
        """使用CJK标点符号进行基本分句"""
        # CJK句子结束符
        sentence_endings = r'[。！？!?；;]'
        parts = re.split(f'({sentence_endings})', text)

        sentences = []
        current = ''
        for part in parts:
            if re.match(sentence_endings, part):
                current += part
                if current.strip():
                    sentences.append(current.strip())
                current = ''
            else:
                current += part

        if current.strip():
            sentences.append(current.strip())

        return [s for s in sentences if s.strip()]

    def split_text(self, text: str) -> List[str]:
        """
        将文本分割成适合学习的句子

        Args:
            text: 输入文本（SOURCE_LANGUAGE）

        Returns:
            适合学习的句子列表
        """
        self.split_mapping = {}

        if not text or not text.strip():
            return []

        text = text.strip()

        if len(text) < 20:
            self.split_mapping[0] = 0
            return [self._clean_sentence(text)]

        if self.is_cjk:
            return self._split_cjk_text(text)
        else:
            return self._split_latin_text(text)

    def _split_cjk_text(self, text: str) -> List[str]:
        """CJK语言的句子分割逻辑"""
        # 先用标点分句
        basic_sentences = self._split_by_cjk_punctuation(text)

        if not basic_sentences:
            self.split_mapping[0] = 0
            return [self._clean_sentence(text)]

        # 检查是否有超长句子
        long_sentences = []
        long_indices = []
        for i, sent in enumerate(basic_sentences):
            if self._is_too_long(sent):
                long_sentences.append(sent)
                long_indices.append(i)

        if not long_sentences:
            for i in range(len(basic_sentences)):
                self.split_mapping[i] = i
            return [self._clean_sentence(s) for s in basic_sentences]

        # 有超长句子，送 API 进一步拆分
        numbered_text = ""
        for idx, sent in enumerate(long_sentences, 1):
            numbered_text += f"{idx}. {sent}\n"

        print(f"调用 API 进行智能拆分: {len(long_sentences)}个超长句子")
        try:
            split_result = self._call_api_split(numbered_text)
            split_by_index = self._parse_numbered_sentences_grouped(split_result)

            result = []
            output_idx = 0

            for i, sent in enumerate(basic_sentences):
                if i in long_indices:
                    idx = long_indices.index(i)
                    if idx in split_by_index:
                        for sub_sent in split_by_index[idx]:
                            result.append(self._clean_sentence(sub_sent))
                            self.split_mapping[output_idx] = i
                            output_idx += 1
                    else:
                        result.append(self._clean_sentence(sent))
                        self.split_mapping[output_idx] = i
                        output_idx += 1
                else:
                    result.append(self._clean_sentence(sent))
                    self.split_mapping[output_idx] = i
                    output_idx += 1

            return result

        except Exception as e:
            print(f"CJK分句时出错: {e}")
            for i in range(len(basic_sentences)):
                self.split_mapping[i] = i
            return [self._clean_sentence(s) for s in basic_sentences]

    def _split_latin_text(self, text: str) -> List[str]:
        """拉丁语系（英语、德语、法语、西班牙语等）的句子分割逻辑"""
        nltk_sentences = nltk.sent_tokenize(text)

        long_sentences = []
        long_indices = []

        for i, sent in enumerate(nltk_sentences):
            word_count = len(sent.split())
            if word_count > self.max_words:
                long_sentences.append(sent)
                long_indices.append(i)

        if not long_sentences:
            for i in range(len(nltk_sentences)):
                self.split_mapping[i] = i
            return self._postprocess_latin_sentences([self._clean_sentence(s) for s in nltk_sentences])

        numbered_text = ""
        for idx, sent in enumerate(long_sentences, 1):
            numbered_text += f"{idx}. {sent}\n"

        print(f"调用 API 进行智能拆分: {len(long_sentences)}个超长句子")
        try:
            split_result = self._call_api_split(numbered_text)
            split_by_index = self._parse_numbered_sentences_grouped(split_result)

            result = []
            output_idx = 0

            for i, sent in enumerate(nltk_sentences):
                if i in long_indices:
                    idx = long_indices.index(i)
                    if idx in split_by_index:
                        for sub_sent in split_by_index[idx]:
                            result.append(self._clean_sentence(sub_sent))
                            self.split_mapping[output_idx] = i
                            output_idx += 1
                    else:
                        result.append(self._clean_sentence(sent))
                        self.split_mapping[output_idx] = i
                        output_idx += 1
                else:
                    result.append(self._clean_sentence(sent))
                    self.split_mapping[output_idx] = i
                    output_idx += 1

            return self._postprocess_latin_sentences(result)

        except Exception as e:
            print(f"分句时出错: {e}")
            for i in range(len(nltk_sentences)):
                self.split_mapping[i] = i
            return self._postprocess_latin_sentences([self._clean_sentence(s) for s in nltk_sentences])

    def get_split_mapping(self) -> dict:
        return self.split_mapping

    def _parse_numbered_sentences_grouped(self, content: str) -> dict:
        if not content:
            return {}

        result = {}
        current_index = None

        for line in content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)[\.\:]\s*', line)
            if match:
                current_index = int(match.group(1)) - 1
                line = re.sub(r'^\d+[\.\:]\s*', '', line)
                if line:
                    if current_index not in result:
                        result[current_index] = []
                    result[current_index].append(line)
            else:
                if current_index is not None and current_index in result:
                    result[current_index].append(line)

        return result

    def _call_api_split(self, text: str) -> str:
        full_prompt = f"{self.prompt}\n\n{text}"

        response = self.client.chat.completions.create(
            model=config.SPLITTER_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.3,
            max_tokens=4000
        )

        return response.choices[0].message.content

    def _split_ellipsis_bridge(self, sentence: str) -> List[str]:
        """
        修复类似 “... Overnight, ...” 的桥接句误合并问题。
        当省略号后是明显的新句开头（大写字母）时拆分。
        """
        s = (sentence or "").strip()
        if not s or "..." not in s:
            return [s] if s else []

        # e.g. "Ten gunshots ... Overnight, ..."
        parts = re.split(r'(?<=\.\.\.)\s+(?=[A-Z][a-z])', s)
        parts = [p.strip() for p in parts if p and p.strip()]
        if len(parts) <= 1:
            return [s]

        # 防止误拆：每段至少 3 个词
        for p in parts:
            wc = len(re.findall(r"\b\w+\b", p))
            if wc < 3:
                return [s]

        return parts

    def _postprocess_latin_sentences(self, sentences: List[str]) -> List[str]:
        """
        对拉丁语系分句做轻量后处理，避免明显的误合并。
        同步维护 split_mapping。
        """
        if self.is_cjk:
            return sentences

        new_sentences: List[str] = []
        new_mapping = {}

        for out_idx, sent in enumerate(sentences):
            origin_idx = self.split_mapping.get(out_idx, out_idx)
            sub_parts = self._split_ellipsis_bridge(sent)
            if not sub_parts:
                sub_parts = [sent]

            for p in sub_parts:
                cleaned = self._clean_sentence(p)
                if not cleaned:
                    continue
                new_mapping[len(new_sentences)] = origin_idx
                new_sentences.append(cleaned)

        self.split_mapping = new_mapping
        return new_sentences

    def _clean_sentence(self, sentence: str) -> str:
        if not sentence:
            return ""

        sentence = sentence.strip()

        # CJK语言使用中文标点
        if self.is_cjk:
            if sentence and sentence[-1] not in '。！？!?；;':
                sentence = sentence + '。'
        else:
            if sentence and sentence[-1] not in '.!?;':
                sentence = sentence + '.'

        # 去除可能的编号
        sentence = re.sub(r'^\d+[\.\)]\s*', '', sentence)

        # 去除可能的引号包装
        sentence = re.sub(r'^["\'](.+?)["\']$', r'\1', sentence)

        # 规范化空格（CJK语言不需要）
        if not self.is_cjk:
            sentence = re.sub(r'\s+', ' ', sentence)

        return sentence

    def _fallback_split(self, text: str) -> List[str]:
        if self.is_cjk:
            return self._split_by_cjk_punctuation(text)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            return [self._clean_sentence(s) for s in sentences if s.strip()]
