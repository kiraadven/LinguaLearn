"""
示例脚本：演示如何使用系统
"""
from main import EnglishLearningVideoGenerator

# 示例英文新闻文本
sample_text = """
Climate change is one of the most pressing issues of our time. 
Scientists around the world are working to understand its impacts. 
Rising temperatures are causing glaciers to melt at an alarming rate. 
We must take immediate action to reduce carbon emissions. 
Renewable energy sources offer a sustainable solution for the future.
"""

def example_basic_usage():
    """基础使用示例"""
    print("示例 1: 基础使用")
    print("-" * 60)
    
    generator = EnglishLearningVideoGenerator()
    
    # 假设你有一个视频文件
    video_path = "input_video.mp4"  # 替换为你的视频路径
    
    result = generator.generate_from_text_and_video(
        text=sample_text,
        video_path=video_path,
        output_name="climate_change_learning"
    )
    
    print(f"\n生成完成！")
    print(f"视频: {result['video_path']}")
    print(f"文字稿: {result['markdown_path']}")


def example_from_file():
    """从文件读取示例"""
    print("示例 2: 从文件读取")
    print("-" * 60)
    
    # 创建示例文本文件
    with open("sample_news.txt", "w", encoding="utf-8") as f:
        f.write(sample_text)
    
    generator = EnglishLearningVideoGenerator()
    
    result = generator.generate_from_text_file(
        text_file="sample_news.txt",
        video_path="input_video.mp4",  # 替换为你的视频路径
        output_name="news_learning"
    )
    
    print(f"\n生成完成！")
    print(f"视频: {result['video_path']}")
    print(f"文字稿: {result['markdown_path']}")


def example_batch_processing():
    """批量处理示例"""
    print("示例 3: 批量处理")
    print("-" * 60)
    
    generator = EnglishLearningVideoGenerator()
    
    # 多个新闻文本和对应的视频
    tasks = [
        {
            "text": "Technology is rapidly changing our daily lives.",
            "video": "tech_video.mp4",
            "output": "tech_learning"
        },
        {
            "text": "Education plays a crucial role in society.",
            "video": "edu_video.mp4",
            "output": "edu_learning"
        }
    ]
    
    results = []
    for task in tasks:
        try:
            result = generator.generate_from_text_and_video(
                text=task["text"],
                video_path=task["video"],
                output_name=task["output"]
            )
            results.append(result)
            print(f"✓ 完成: {task['output']}")
        except Exception as e:
            print(f"✗ 失败: {task['output']} - {e}")
    
    print(f"\n批量处理完成！共处理 {len(results)} 个视频")


def example_custom_analysis():
    """自定义分析示例"""
    print("示例 4: 单独使用各个模块")
    print("-" * 60)
    
    from sentence_splitter import SentenceSplitter
    from word_analyzer import WordAnalyzer
    
    # 1. 分割句子
    splitter = SentenceSplitter()
    sentences = splitter.split_text(sample_text)
    print(f"分割出 {len(sentences)} 个句子")
    
    # 2. 分析单个句子
    analyzer = WordAnalyzer()
    result = analyzer.analyze_sentence(sentences[0])
    
    print(f"\n句子: {sentences[0]}")
    print(f"翻译: {result['chinese_translation']}")
    print(f"重难点单词:")
    for word in result['key_words']:
        print(f"  - {word['word']} {word['phonetic']}: {word['translation']}")


if __name__ == "__main__":
    print("=" * 60)
    print("英语学习视频生成系统 - 使用示例")
    print("=" * 60)
    print("\n请选择要运行的示例：")
    print("1. 基础使用")
    print("2. 从文件读取")
    print("3. 批量处理")
    print("4. 单独使用各个模块")
    
    choice = input("\n请输入选项 (1-4): ").strip()
    
    if choice == "1":
        example_basic_usage()
    elif choice == "2":
        example_from_file()
    elif choice == "3":
        example_batch_processing()
    elif choice == "4":
        example_custom_analysis()
    else:
        print("无效的选项")

