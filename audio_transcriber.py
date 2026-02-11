"""
音频转文字模块
支持两种方式：
1. OpenAI Whisper API（需要 API Key）
2. 本地 Whisper 模型（免费，需要下载模型）
"""
import os
from moviepy.editor import VideoFileClip
from openai import OpenAI
import config


class AudioTranscriber:
    def __init__(self, api_key: str = None, base_url: str = None, use_local: bool = False):
        """
        初始化音频转文字器
        
        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL
            use_local: 是否使用本地 Whisper 模型
        """
        self.use_local = use_local
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        
        if not use_local:
            if not self.api_key:
                raise ValueError("请在.env文件中设置OPENAI_API_KEY，或使用本地模式")
            
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            # 使用本地 Whisper 模型
            try:
                import whisper
                print("正在加载本地 Whisper 模型...")
                self.whisper_model = whisper.load_model("small")  # 可选: tiny, base, small, medium, large
                print("✓ Whisper 模型加载成功")
            except ImportError:
                raise ImportError(
                    "本地模式需要安装 openai-whisper 包。\n"
                    "请运行: pip install openai-whisper"
                )
        
        # 创建临时目录
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        # Whisper API 文件大小限制（25MB）
        self.max_file_size = 25 * 1024 * 1024
    
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
        使用 Whisper 将音频转换为文字
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        if self.use_local:
            return self._transcribe_local(audio_path)
        else:
            return self._transcribe_api(audio_path)
    
    def _transcribe_local(self, audio_path: str) -> str:
        """
        使用本地 Whisper 模型转录
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        print("正在使用本地 Whisper 模型转录音频...")
        
        try:
            result = self.whisper_model.transcribe(
                audio_path,
                language="en",
                verbose=False
            )
            
            text = result["text"].strip()
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            return text
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            raise
    
    def _transcribe_api(self, audio_path: str) -> str:
        """
        使用 Whisper API 转录
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        print("正在使用 Whisper API 转录音频...")
        
        try:
            # 检查文件大小
            file_size = os.path.getsize(audio_path)
            print(f"音频文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size > self.max_file_size:
                print(f"⚠️  文件超过25MB限制，将进行分段处理...")
                return self._transcribe_large_audio(audio_path)
            
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",  # 指定为英语
                    response_format="text"
                )
            
            text = transcript if isinstance(transcript, str) else transcript.text
            print(f"✓ 转录完成，共 {len(text)} 个字符")
            return text
            
        except Exception as e:
            print(f"❌ 转录失败: {e}")
            print(f"提示: 请确保音频文件小于25MB，且API Key有效")
            raise
    
    def _transcribe_large_audio(self, audio_path: str) -> str:
        """
        处理大于25MB的音频文件（分段处理）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文字
        """
        from pydub import AudioSegment
        
        print("正在分段处理大文件...")
        audio = AudioSegment.from_file(audio_path)
        
        # 每段10分钟
        segment_length = 10 * 60 * 1000  # 毫秒
        segments = []
        
        for i in range(0, len(audio), segment_length):
            segment = audio[i:i + segment_length]
            segment_path = os.path.join(config.TEMP_DIR, f"segment_{i}.mp3")
            segment.export(segment_path, format="mp3", bitrate="64k")
            
            print(f"正在转录第 {i // segment_length + 1} 段...")
            
            with open(segment_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="text"
                )
            
            text = transcript if isinstance(transcript, str) else transcript.text
            segments.append(text)
            
            # 清理临时文件
            os.remove(segment_path)
        
        full_text = " ".join(segments)
        print(f"✓ 所有段落转录完成，共 {len(full_text)} 个字符")
        return full_text
    
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

