"""
Markdown导出模块
生成英汉互译文字稿
"""
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
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入标题
            f.write("# 英语学习文字稿\n\n")
            f.write(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            # 写入目录
            f.write("## 📑 目录\n\n")
            for i, sentence_data in enumerate(sentences_data, 1):
                # 截取前30个字符作为预览
                preview = sentence_data['original_text'][:30]
                if len(sentence_data['original_text']) > 30:
                    preview += "..."
                f.write(f"{i}. [{preview}](#句子-{i})\n")
            f.write("\n---\n\n")
            
            # 写入每个句子的详细内容
            for i, sentence_data in enumerate(sentences_data, 1):
                f.write(f"## 句子 {i}\n\n")
                
                # 英文原文
                f.write("### 📝 英文原文\n\n")
                f.write(f"> {sentence_data['original_text']}\n\n")
                
                # 中文翻译
                f.write("### 🇨🇳 中文翻译\n\n")
                f.write(f"> {sentence_data['chinese_translation']}\n\n")
                
                # 重难点单词
                if sentence_data.get('key_words'):
                    f.write("### 📚 重难点单词\n\n")
                    f.write("| 序号 | 单词 | 音标 | 中文释义 | 难度 |\n")
                    f.write("|------|------|------|----------|------|\n")
                    
                    for j, word_info in enumerate(sentence_data['key_words'], 1):
                        word = word_info.get('word', '')
                        phonetic = word_info.get('phonetic', '')
                        translation = word_info.get('translation', '')
                        difficulty = word_info.get('difficulty', 0)
                        difficulty_stars = "⭐" * difficulty
                        
                        f.write(f"| {j} | **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
                    
                    f.write("\n")
                
                f.write("---\n\n")
            
            # 写入统计信息
            f.write("## 📊 统计信息\n\n")
            f.write(f"- 总句子数：{len(sentences_data)}\n")
            
            total_words = sum(len(s.get('key_words', [])) for s in sentences_data)
            f.write(f"- 重难点单词总数：{total_words}\n")
            
            total_chars = sum(len(s['original_text']) for s in sentences_data)
            f.write(f"- 总字符数：{total_chars}\n\n")
            
            # 写入所有单词汇总
            f.write("## 📖 单词汇总\n\n")
            all_words = {}
            for sentence_data in sentences_data:
                for word_info in sentence_data.get('key_words', []):
                    word = word_info.get('word', '').lower()
                    if word not in all_words:
                        all_words[word] = word_info
            
            if all_words:
                f.write("| 单词 | 音标 | 中文释义 | 难度 |\n")
                f.write("|------|------|----------|------|\n")
                
                # 按字母顺序排序
                for word in sorted(all_words.keys()):
                    word_info = all_words[word]
                    phonetic = word_info.get('phonetic', '')
                    translation = word_info.get('translation', '')
                    difficulty = word_info.get('difficulty', 0)
                    difficulty_stars = "⭐" * difficulty
                    
                    f.write(f"| **{word}** | {phonetic} | {translation} | {difficulty_stars} |\n")
            
            f.write("\n---\n\n")
            f.write("*本文档由英语学习视频自动化生成系统创建*\n")
        
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

