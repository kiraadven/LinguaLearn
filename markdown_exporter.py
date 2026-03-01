import os
import json
from typing import List, Dict
from datetime import datetime
from openai import OpenAI
import config


class MarkdownExporter:
    def __init__(self, output_dir: str = 'output'):
        """
        初始化Markdown导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化 OpenAI 客户端（用于生成介绍和使用指南）
        self.api_key = config.OPENAI_API_KEY
        self.base_url = config.OPENAI_BASE_URL
        self.client = None
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
    
    def _generate_introduction(self, sentences_data: List[Dict]) -> str:
        """
        调用 DeepSeek API 生成文章简介
        
        Args:
            sentences_data: 句子数据列表
            
        Returns:
            简介文本
        """
        if not self.client:
            return "（请配置 OPENAI_API_KEY 以生成简介）"
        
        # 提取所有英文句子
        all_sentences = [s.get('original_text', '') for s in sentences_data]
        sentences_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(all_sentences[:10]))  # 取前10句
        
        prompt = f"""请阅读以下英语学习视频的文字稿内容，然后生成一段简洁的中文概括性介绍（100-200字）：

{sentences_text}

请直接返回介绍内容，不要添加任何格式或前缀。介绍应该：
1. 说明这个视频的主题是什么
2. 涵盖视频的主要内容要点
3. 语言简洁明了，适合英语学习者阅读"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的英语教学助手，擅长概括文章主旨。请用简洁的语言生成内容介绍。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            return content
            
        except Exception as e:
            print(f"生成简介时出错: {e}")
            return "（生成简介失败）"
    
    
    def export(self, sentences_data: List[Dict], 
               output_filename: str = None) -> str:
        """
        导出Markdown格式的文字稿
        
        Args:
            sentences_data: 句子数据列表
            output_filename: 输出文件名
            
        Returns:
            输出文件路径
        """
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"transcript_{timestamp}.md"
        
        output_path = os.path.join(self.output_dir, output_filename)
        
        # 计算统计信息
        total_sentences = len(sentences_data)
        total_words = sum(len(s.get('key_words', [])) for s in sentences_data)
        total_chars = sum(len(s['original_text']) for s in sentences_data)
        
        # 生成简介和学习指南
        print("正在生成内容简介...")
        introduction = self._generate_introduction(sentences_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            # ===== 头部信息 =====
            f.write("---\n")
            f.write("layout: default\n")
            f.write("title: GetEverybodyLearning英语学习文字稿\n")
            f.write("---\n\n")
            
            # ===== 主标题 =====
            f.write("# 🌟 GetEverybodyLearning英语学习文字稿\n\n")
            f.write(f"**生成时间：** {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
            
            # ===== 简介部分 =====
            f.write("---\n\n")
            f.write("## 📖 内容简介\n\n")
            f.write(f"> *{introduction}*\n\n")
            f.write("---\n\n")
            
            # ===== 英文原文整合 =====
            f.write("## 📄 英文原文\n\n")
            for i, sentence_data in enumerate(sentences_data, 1):
                original_text = sentence_data['original_text']
                # 移除末尾的句号，避免重复
                original_text = original_text.rstrip('.!?')
                f.write(f"{original_text}. ")
            f.write("\n\n")
            f.write("---\n\n")
            
            # ===== 每个句子的详细内容 =====
            for i, sentence_data in enumerate(sentences_data, 1):
                f.write(f"<div class=\"sentence-card\" id=\"句子-{i}\">\n\n")
                
                f.write(f"## 🔹 句子 {i}\n\n")
                
                # 英文原文
                original_text = sentence_data['original_text']
                
                f.write("### 📝 英文原文\n\n")
                f.write(f"> **{original_text}**\n\n")
                
                # 中文翻译
                f.write("### 🇨🇳 中文翻译\n\n")
                f.write(f"> *{sentence_data['chinese_translation']}*")
                
                # 重难点单词
                keywords = sentence_data.get('key_words', [])
                if keywords:
                    f.write("\n\n### 📚 重难点单词\n\n")
                    
                    f.write("| 序号 | 单词 | 音标 | 中文释义 | 难度 |\n")
                    f.write("|:---:|:---:|:---:|:---:|:---:|\n")
                    
                    for j, word_info in enumerate(keywords, 1):
                        word = word_info.get('word', '')
                        phonetic = word_info.get('phonetic', '')
                        translation = word_info.get('translation', '')
                        difficulty = word_info.get('difficulty', 0)
                        difficulty_stars = "💫" * difficulty + "☆" * (5 - difficulty)
                        
                        f.write(f"| {j} | **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
                    
                    f.write("\n")
                
                # 有用表达
                expressions = sentence_data.get('useful_expressions', [])
                if expressions:
                    f.write("### 💬 有用表达\n\n")
                    
                    for expr in expressions:
                        english = expr.get('english', '')
                        chinese = expr.get('chinese', '')
                        if english and chinese:
                            f.write(f"- **{english}** {chinese}\n")
                    
                    f.write("\n")
                
                f.write("</div>\n\n")
                f.write("---\n\n")
            
            # ===== 单词汇总表 =====
            f.write("## 📖 单词汇总表\n\n")
            
            all_words = []
            seen_words = set()
            for sentence_data in sentences_data:
                for word_info in sentence_data.get('key_words', []):
                    word = word_info.get('word', '').lower()
                    if word and word not in seen_words:
                        seen_words.add(word)
                        all_words.append(word_info)
            
            # 打乱顺序（用于听写）
            import random
            random.seed(42)  # 固定种子，保持顺序一致
            shuffled_words = all_words.copy()
            random.shuffle(shuffled_words)
            
            if shuffled_words:
                f.write("| 单词 | 音标 | 中文释义 | 难度 |\n")
                f.write("|:---:|:---:|:---:|:---:|\n")
                
                # 使用打乱后的顺序
                for word_info in shuffled_words:
                    word = word_info.get('word', '')
                    phonetic = word_info.get('phonetic', '')
                    translation = word_info.get('translation', '')
                    difficulty = word_info.get('difficulty', 0)
                    difficulty_stars = "💫" * difficulty + "☆" * (5 - difficulty)
                    
                    f.write(f"| **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
            
            f.write("\n---\n\n")
            
            # ===== 单词听写模块 =====
            f.write("## ✍️ 单词听写练习\n\n")
            f.write("**根据中文提示，写出对应的英文单词：**\n\n")
            
            # 使用打乱后的单词列表
            if shuffled_words:
                f.write("| 单词1 | 单词2 | 单词3 |\n")
                f.write("|:---:|:---:|:---:|\n")
                
                for i in range(0, len(shuffled_words), 3):
                    row = shuffled_words[i:i+3]
                    # 填充空位
                    while len(row) < 3:
                        row.append({'translation': '', 'word': ''})
                    
                    # 每个单词后面紧跟横线
                    f.write(f"| {row[0]['translation']} __________ | {row[1]['translation']} __________ | {row[2]['translation']} __________ |\n")
            
            f.write("\n---\n\n")
            
            # ===== 表达汇总表 =====
            f.write("## 📝 表达汇总表\n\n")
            
            all_expressions = []
            seen_expressions = set()
            for sentence_data in sentences_data:
                for expr in sentence_data.get('useful_expressions', []):
                    english = expr.get('english', '').lower()
                    if english and english not in seen_expressions:
                        seen_expressions.add(english)
                        all_expressions.append(expr)
            
            if all_expressions:
                f.write("| 英文表达 | 中文释义 |\n")
                f.write("|:---|:---|\n")
                
                for expr in all_expressions:
                    english = expr.get('english', '')
                    chinese = expr.get('chinese', '')
                    f.write(f"| **{english}** | {chinese} |\n")
            
            f.write("\n---\n\n")
            
            # ===== 表达默写练习 =====
            f.write("## ✍️ 表达默写练习\n\n")
            f.write("**根据中文提示，写出对应的英文表达：**\n\n")
            
            if all_expressions:
                # 打乱顺序
                import random
                random.seed(42)
                shuffled_exprs = all_expressions.copy()
                random.shuffle(shuffled_exprs)
                
                f.write("| 表达1 | 表达2 |\n")
                f.write("|:---|:---|\n")
                
                for i in range(0, len(shuffled_exprs), 2):
                    row = shuffled_exprs[i:i+2]
                    while len(row) < 2:
                        row.append({'chinese': '', 'english': ''})
                    
                    f.write(f"| {row[0]['chinese']} ____________________ | {row[1]['chinese']} ____________________ |\n")
            
            f.write("\n---\n\n")
            
            # ===== 页脚 =====
            f.write("<div align=\"center\">\n\n")
            f.write("*📚 本文档由GetEverybodyLearning生成*\n\n")
            f.write("*坚持每天学习，让英语进步！* 🚀\n\n")
            f.write("</div>\n")
        
        print(f"Markdown文字稿已导出到: {output_path}")
        return output_path
