"""
测试 precise_aligner.py
"""

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from precise_aligner import PreciseSentenceAligner, get_precise_timestamps


def load_sentences(file_path: str) -> list:
    """加载句子列表（去除数字前缀）"""
    sentences = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                # 去除 "1. " 这样的前缀
                # 匹配数字 + 英文句点 + 空格
                import re
                line = re.sub(r'^\d+\.\s*', '', line)
                sentences.append(line)
    return sentences


def main():
    # 配置路径
    audio_path = "/Users/yangyangqinqin/Desktop/automation/temp/extracted_audio.wav"
    sentences_file = "/Users/yangyangqinqin/Desktop/automation/output/Special Report_ Iran launches retaliatory attacks against Israel and U.S. targets in the Middle East_1_sentences.txt"
    output_file = "/Users/yangyangqinqin/Desktop/automation/output/timestamps_result.json"
    
    # 加载句子
    print("加载句子...")
    sentences = load_sentences(sentences_file)
    print(f"共 {len(sentences)} 个句子")
    print(f"前3个句子: {sentences[:3]}")
    
    # 检查音频文件
    if not os.path.exists(audio_path):
        print(f"错误: 音频文件不存在: {audio_path}")
        return
    
    print(f"\n音频文件: {audio_path}")
    print(f"音频大小: {os.path.getsize(audio_path) / 1024 / 1024:.1f} MB")
    
    # 测试 MFA 对齐
    print("\n" + "="*50)
    print("测试 MFA 对齐...")
    print("="*50)
    
    try:
        aligner = PreciseSentenceAligner()
        timestamps = aligner.align_sentences(audio_path, sentences)
        
        print(f"\n✅ 对齐成功! 共 {len(timestamps)} 个时间戳")
        
        # 保存结果
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(timestamps, f, indent=2, ensure_ascii=False)
        print(f"结果已保存到: {output_file}")
        
        # 打印前10个结果
        print("\n前10个句子时间戳:")
        for i, ts in enumerate(timestamps[:10]):
            print(f"  {ts['start']:.3f} - {ts['end']:.3f}: {ts['text'][:50]}...")
            
    except RuntimeError as e:
        print(f"\n❌ MFA 对齐失败: {e}")
        print("\n尝试使用 Whisper 对齐作为备选方案...")
        
        # 备选: 使用 Whisper
        try:
            from precise_aligner import ImprovedWhisperAligner
            
            aligner = ImprovedWhisperAligner(model_size="large")
            timestamps = aligner.align_sentences(audio_path, sentences)
            
            print(f"\n✅ Whisper 对齐成功! 共 {len(timestamps)} 个时间戳")
            
            # 保存结果
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(timestamps, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {output_file}")
            
        except Exception as e2:
            print(f"❌ Whisper 对齐也失败: {e2}")


if __name__ == "__main__":
    main()
