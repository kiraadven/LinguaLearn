import os
from typing import List, Dict
from datetime import datetime


class MarkdownExporter:
    def __init__(self, output_dir: str = 'output'):
        """
        初始化Markdown导出器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
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
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # ===== 头部信息 =====
            f.write("---\n")
            f.write("layout: default\n")
            f.write("title: 英语学习文字稿\n")
            f.write("---\n\n")
            
            # ===== 主标题 =====
            f.write("# 🌟 英语学习文字稿\n\n")
            f.write(f"**生成时间：** {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
            
            # ===== 统计卡片 =====
            f.write("<div class=\"stats-cards\">\n\n")
            f.write(f"| 📊 总句子数 | 📚 单词总数 | 📝 总字符数 |\n")
            f.write(f"|:---:|:---:|:---:|\n")
            f.write(f"| **{total_sentences}** | **{total_words}** | **{total_chars}** |\n\n")
            f.write("</div>\n\n")
            
            f.write("---\n\n")
            
            # ===== 每个句子的详细内容 =====
            for i, sentence_data in enumerate(sentences_data, 1):
                f.write(f"<div class=\"sentence-card\" id=\"句子-{i}\">\n\n")
                
                f.write(f"## 🔹 句子 {i}\n\n")
                
                # 英文原文 - 使用引用块
                f.write("### 📝 英文原文\n\n")
                f.write(f"> **{sentence_data['original_text']}**\n\n")
                
                # 中文翻译 - 使用引用块
                f.write("### 🇨🇳 中文翻译\n\n")
                f.write(f"> *{sentence_data['chinese_translation']}*\n\n")
                
                # 重难点单词
                if sentence_data.get('key_words'):
                    f.write("### 📚 重难点单词\n\n")
                    
                    # 使用更美观的表格样式
                    f.write("| 序号 | 单词 | 音标 | 中文释义 | 难度 |\n")
                    f.write("|:---:|:---:|:---:|:---:|:---:|\n")
                    
                    for j, word_info in enumerate(sentence_data['key_words'], 1):
                        word = word_info.get('word', '')
                        phonetic = word_info.get('phonetic', '')
                        translation = word_info.get('translation', '')
                        difficulty = word_info.get('difficulty', 0)
                        difficulty_stars = "💫" * difficulty + "☆" * (5 - difficulty)
                        
                        f.write(f"| {j} | **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
                    
                    f.write("\n")
                
                f.write("</div>\n\n")
                f.write("---\n\n")
            
            # ===== 单词汇总表 =====
            f.write("## 📖 单词汇总表\n\n")
            
            all_words = {}
            for sentence_data in sentences_data:
                for word_info in sentence_data.get('key_words', []):
                    word = word_info.get('word', '').lower()
                    if word not in all_words:
                        all_words[word] = word_info
            
            if all_words:
                f.write("| 单词 | 音标 | 中文释义 | 难度 |\n")
                f.write("|:---:|:---:|:---:|:---:|\n")
                
                # 按字母顺序排序
                for word in sorted(all_words.keys()):
                    word_info = all_words[word]
                    phonetic = word_info.get('phonetic', '')
                    translation = word_info.get('translation', '')
                    difficulty = word_info.get('difficulty', 0)
                    difficulty_stars = "💫" * difficulty + "☆" * (5 - difficulty)
                    
                    f.write(f"| **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
            
            f.write("\n---\n\n")
            
            # ===== 页脚 =====
            f.write("<div align=\"center\">\n\n")
            f.write("*📚 本文档由英语学习视频自动化生成系统创建*\n\n")
            f.write("*坚持每天学习，让英语进步！* 🚀\n\n")
            f.write("</div>\n")
        
        print(f"Markdown文字稿已导出到: {output_path}")
        return output_path


if __name__ == "__main__":
    # 测试代码
    exporter = MarkdownExporter()
    
    test_data = [
        {
            'original_text': 'Climate change is one of the most pressing issues of our time.',
            'chinese_translation': '气候变化是我们这个时代最紧迫的问题之一。',
            'key_words': [
                {'word': 'climate', 'phonetic': '/ˈklaɪmət/', 'translation': '气候', 'difficulty': 3},
                {'word': 'pressing', 'phonetic': '/ˈpresɪŋ/', 'translation': '紧迫的', 'difficulty': 4}
            ]
        },
        {
            'original_text': 'Scientists around the world are working to understand its impacts.',
            'chinese_translation': '世界各地的科学家正在努力了解其影响。',
            'key_words': [
                {'word': 'scientist', 'phonetic': '/ˈsaɪəntɪst/', 'translation': '科学家', 'difficulty': 2},
                {'word': 'impact', 'phonetic': '/ˈɪmpækt/', 'translation': '影响', 'difficulty': 3}
            ]
        }
    ]
    
    exporter.export(test_data, 'test_transcript.md')
