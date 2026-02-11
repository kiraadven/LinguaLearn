# 英语学习视频自动化生成系统

这是一个功能强大的英语学习视频自动化生成系统，可以将英文新闻视频自动转换为带有精美字幕和重难点单词标注的学习视频。

## ✨ 功能特点

### 🎯 核心功能

1. **智能句子分割**
   - 使用 NLTK 自动识别和分割英文句子
   - 支持复杂句式和标点符号

2. **AI 单词分析**
   - 使用 OpenAI API 智能识别每句话的重难点单词（2-6个）
   - 自动获取单词的音标（IPA格式）和中文释义
   - 按难度等级排序

3. **多速度播放**
   - 原速无字幕播放（1.0x）
   - 慢速带字幕播放（0.75x，重复2次）
   - 正常速度带字幕播放（1.0x）

4. **精美视觉设计**
   - 占画面下方 1/4 的渐变字幕框，显示中英文对照
   - 占画面右侧 3/16 的单词框，显示重难点单词详情
   - 现代化的配色方案和动画效果

5. **Markdown 文字稿导出**
   - 自动生成完整的英汉互译文字稿
   - 包含所有重难点单词的详细信息
   - 提供单词汇总和统计信息

## 📋 系统要求

- Python 3.8+
- FFmpeg（用于视频处理）
- OpenAI API Key（或兼容的 API 服务）

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 FFmpeg (Mac)
brew install ffmpeg

# 安装 FFmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# 安装 FFmpeg (Windows)
# 从 https://ffmpeg.org/download.html 下载并安装
```

### 2. 配置 API Key

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
# OPENAI_API_KEY=your_api_key_here
# OPENAI_BASE_URL=https://api.openai.com/v1
```

### 3. 设置输入视频路径

在 `config.py` 文件中设置你的视频路径：

```python
# 输入视频配置
INPUT_VIDEO_PATH = 'your_video.mp4'  # 修改为你的视频路径
```

### 4. 运行程序

```bash
python main.py
```

程序会自动：
- 从视频中提取音频
- 使用 Whisper API 转录为文字
- 分析句子和单词
- 生成学习视频和 Markdown 文字稿

## 📖 使用方法

### 方式一：自动处理（推荐）

1. 在 `config.py` 中设置视频路径：
```python
INPUT_VIDEO_PATH = 'your_video.mp4'
```

2. 运行程序：
```bash
python main.py
```

程序会自动完成所有处理，无需任何交互！

### 方式二：编程使用

```python
from main import EnglishLearningVideoGenerator

# 创建生成器
generator = EnglishLearningVideoGenerator()

# 仅从视频生成（自动提取文字）
result = generator.generate_from_video_only(
    video_path="input_video.mp4",
    output_name="my_learning_video"
)

print(f"视频已保存到: {result['video_path']}")
print(f"文字稿已保存到: {result['markdown_path']}")
```

## 📁 项目结构

```
automation/
├── main.py                 # 主程序入口
├── config.py              # 配置文件（在这里设置视频路径）
├── sentence_splitter.py   # 句子分割模块
├── word_analyzer.py       # 单词分析模块
├── audio_transcriber.py   # 音频转文字模块（Whisper API）
├── video_processor.py     # 视频处理模块
├── markdown_exporter.py   # Markdown导出模块
├── requirements.txt       # Python依赖
├── .env                   # 环境变量配置（需自行创建）
├── .env.example          # 环境变量配置模板
├── README.md             # 项目说明
├── output/               # 输出目录（自动创建）
│   ├── *.mp4            # 生成的视频
│   └── *.md             # 生成的文字稿
└── temp/                 # 临时文件目录（自动创建）
```

## 🎨 视觉设计

### 字幕框设计
- 位置：画面底部，占 1/4 高度
- 背景：深蓝色渐变，带透明度
- 顶部装饰：金色装饰线
- 内容：
  - 英文原文（金色，大字体）
  - 中文翻译（浅蓝色，中等字体）
- 效果：文字带阴影，增强可读性

### 单词框设计
- 位置：画面右侧，占 3/16 宽度
- 背景：深色圆角矩形
- 标题栏：粉红色背景，显示 "📚 Key Words"
- 单词列表：
  - 序号圆圈（金色背景）
  - 单词拼写（金色，大字体）
  - 音标（浅蓝色，小字体）
  - 中文释义（白色，中等字体）
- 最多显示 6 个单词

## ⚙️ 配置选项

在 `config.py` 中可以自定义：

- 视频分辨率（默认 1920x1080）
- 字幕框和单词框的尺寸比例
- 颜色方案
- 字体大小
- 播放速度
- 输出目录

## 🔧 高级功能

### 自定义 API 服务

支持使用兼容 OpenAI API 的其他服务（如 DeepSeek）：

```bash
# 在 .env 文件中设置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
```

### 批量处理

```python
from main import EnglishLearningVideoGenerator

generator = EnglishLearningVideoGenerator()

# 批量处理多个视频
videos = [
    ("text1.txt", "video1.mp4", "output1"),
    ("text2.txt", "video2.mp4", "output2"),
]

for text_file, video_file, output_name in videos:
    generator.generate_from_text_file(text_file, video_file, output_name)
```

## 📊 输出示例

### 视频输出
- 格式：MP4 (H.264 + AAC)
- 分辨率：1920x1080
- 帧率：30fps
- 包含完整的字幕和单词标注

### Markdown 文字稿
- 包含目录导航
- 每个句子的详细信息
- 重难点单词表格
- 统计信息
- 单词汇总（按字母排序）

## 🐛 常见问题

### 1. FFmpeg 未找到
确保已安装 FFmpeg 并添加到系统 PATH。

### 2. API 调用失败
检查 API Key 是否正确，网络连接是否正常。

### 3. 字体显示问题
系统会自动尝试使用系统字体，如果显示异常，可以在 `config.py` 中指定字体路径。

### 4. 视频处理速度慢
视频处理是 CPU 密集型任务，处理时间取决于：
- 视频长度
- 句子数量
- 计算机性能

建议使用较短的视频片段进行测试。

### 5. Whisper 转录不准确
- 确保视频音频清晰
- 避免背景噪音过大
- 建议使用标准英语发音的视频

## 💡 使用提示

1. **首次运行**时，NLTK会自动下载必要的数据包
2. **视频处理**是CPU密集型任务，建议先用短视频（1-2分钟）测试
3. **API调用费用**：
   - Whisper API：约 $0.006/分钟
   - GPT API：根据使用量计费
   - 建议使用便宜的API服务（如DeepSeek）
4. **字体问题**：系统会自动使用系统字体，Mac上效果最佳
5. **输入视频要求**：
   - 格式：MP4（推荐）
   - 音频：清晰的英语语音
   - 时长：建议5分钟以内（测试用）

## 🎯 工作流程

```
输入视频 (MP4)
    ↓
提取音频 → Whisper API 转录 → 英文文本
    ↓
句子分割 (NLTK)
    ↓
AI 分析每个句子 → 翻译 + 重难点单词
    ↓
视频处理 (MoviePy)
    ├─ 原速无字幕 (1.0x)
    ├─ 慢速带字幕 (0.75x × 2)
    └─ 正常带字幕 (1.0x)
    ↓
输出
    ├─ 学习视频 (MP4)
    └─ 文字稿 (Markdown)
```

## 🎯 下一步

1. **准备视频**：找一个英文新闻或演讲视频（MP4格式）
2. **配置路径**：在 `config.py` 中设置 `INPUT_VIDEO_PATH`
3. **配置 API**：在 `.env` 中设置 `OPENAI_API_KEY`
4. **运行程序**：`python main.py`
5. **开始学习**：查看 `output/` 目录中的视频和文字稿！

## 📝 待办事项

- [ ] 支持音频文件输入（自动生成视频背景）
- [ ] 支持自定义字体
- [ ] 添加进度条显示
- [ ] 支持多语言（不仅限于英语）
- [ ] 添加 GPU 加速支持
- [ ] Web 界面

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 Issue。

---

**享受学习英语的乐趣！** 🎉

