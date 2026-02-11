"""
音频转文字模块
使用OpenAI Whisper API从视频中提取文字
"""
import os
from moviepy.editor import VideoFileClip
from openai import OpenAI
import config


class AudioTranscriber:
    def __init__(self, api_key: str = None, base_url: str = None):
        """
        初始化音频转文字器
        
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
        
        # 创建临时目录
        os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    def extract_audio_from_video(self, video_path: str) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            音频文件路径
        """
        print("正在从视频中提取音频...")
        
        video = VideoFileClip(video_path)
        audio_path = os.path.join(config.TEMP_DIR, "extracted_audio.mp3")
        
        # 提取音频并保存为MP3
        video.audio.write_audiofile(audio_path, codec='mp3', verbose=False, logger=None)
        video.close()
        
        print(f"✓ 音频已提取到: {audio_path}")
        return audio_path
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        使用Whisper API将音频转换为文字
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        print("正在使用Whisper API转录音频...")
        
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # 指定为英语
                )
            
            text = transcript.text
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            return text
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def transcribe_video(self, video_path: str) -> str:
        """
        从视频中提取文字（完整流程）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            转录的文字
        """
        # 1. 提取音频
        audio_path = self.extract_audio_from_video(video_path)
        
        # 2. 转录音频
        text = self.transcribe_audio(audio_path)
        
        # 3. 清理临时文件（可选）
        # os.remove(audio_path)
        
        return text


if __name__ == "__main__":
    # 测试代码
    transcriber = AudioTranscriber()
    
    # 假设有一个测试视频
    test_video = "test_video.mp4"
    
    if os.path.exists(test_video):
        text = transcriber.transcribe_video(test_video)
        print(f"\n转录结果:\n{text}")
    else:
        print(f"测试视频不存在: {test_video}")

