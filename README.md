# English Learning Video Generator

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/MoviePy-1.0.3-green?style=for-the-badge" alt="MoviePy">
  <img src="https://img.shields.io/badge/OpenAI-Whisper-orange?style=for-the-badge" alt="Whisper">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-green?style=for-the-badge" alt="License">
</p>

> 📺 自动化英语学习视频生成工具 - 将任何英文视频转化为高质量的学习视频

## 📋 项目简介

English Learning Video Generator 是一个强大的自动化工具，可以将英文视频转化为结构化的英语学习视频。整个过程自动化完成包括：音频提取、自动转录、句子分割、AI 智能分析、学习内容标注，最终生成带有双语字幕、词汇注释和实用表达的的学习视频。

### ✨ 核心特性

- 🎬 **全自动处理**: 从视频输入到学习视频输出，全程自动化
- 🤖 **AI 智能分析**: 使用大语言模型分析句子，提取关键词和实用表达
- 📝 **双语字幕**: 清晰的英文原文 + 中文翻译字幕
- 📚 **词汇卡片**: 自动识别并标注重难点单词（含音标和释义）
- 💬 **表达积累**: 提取实用英语表达方式，帮助提升口语和写作
- 🎯 **双重模式**: 
  - 快速版：原速播放 + 字幕框
  - 学习版：慢速播放（0.75x）+ 正常速播放 + 字幕框 + 单词框 + 表达框
- 🎨 **精美 UI**: 使用 HTML + Chrome 渲染高质量字幕和卡片
- 💾 **断点续传**: 支持从中间步骤加载，继续生成视频

## 🏗️ 系统架构

```
输入视频 → 音频提取 → Whisper转录 → 句子分割 → AI分析 → Markdown导出 → 视频合成 → 输出视频
                                  ↓
                           ┌──────┴──────┐
                           ↓             ↓
                       快速版本      学习版本
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/english-learning-video-generator.git
cd english-learning-video-generator
```

### 2. 创建 Python 环境（推荐使用 conda）

#### 方式一：使用 conda（推荐）

```bash
# 创建新环境
conda create -n automation python=3.11 -y

# 激活环境
conda activate automation
```

#### 方式二：使用 venv

```bash
# 创建虚拟环境
python -m venv venv

# 激活环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> 📌 **注意**：如果你之前已经安装过一些包，可能需要更新：
> ```bash
> pip install --upgrade -r requirements.txt
> ```

### 4. 安装 Whisper 模型

首次运行程序时，Whisper 会自动下载模型（默认为 `small` 模型，约 140MB）。如需手动下载：

```bash
# 安装 whisper 后运行
python -c "import whisper; whisper.load_model('small')"
```

可用的模型大小：
| 模型 | 大小 | 速度 | 精度 |
|------|------|------|------|
| tiny | ~39 MB | 最快 | 较低 |
| base | ~74 MB | 快 | 一般 |
| small | ~244 MB | 中等 | 较好 |
| medium | ~769 MB | 慢 | 好 |
| large | ~1550 MB | 最慢 | 最好 |

### 5. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```env
# OpenAI API 配置（必须设置）
# 支持 OpenAI、DeepSeek 或其他 OpenAI 兼容 API
OPENAI_API_KEY=your_api_key_here
SPLITTER_API_KEY=your_api_key_here

# API 基础 URL（可选，默认使用 DeepSeek）
# DeepSeek: https://api.deepseek.com
# OpenAI: https://api.openai.com/v1
# Ollama: http://localhost:11434/v1
OPENAI_BASE_URL=https://api.deepseek.com
SPLITTER_BASE_URL=https://api.openai.com/v1
```

### 6. 准备输入视频

将你的英文视频放入项目目录，例如：

```
english-learning-video-generator/
├── input_videos/
│   └── your_video.mp4    # 放入你的视频
├── main.py
├── config.py
└── ...
```

然后编辑 `config.py`，设置视频路径：

```python
# config.py
INPUT_VIDEO_PATH = 'input_videos/your_video.mp4'
```

### 7. 运行程序

```bash
python main.py
```

---

## ⚙️ 配置文件说明

所有配置都在 `config.py` 文件中：

### API 配置

```python
# API 配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com')

# Whisper 模型大小
WHISPER_MODEL_SIZE = 'small'  # tiny/base/small/medium/large
```

### 视频参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FPS` | 30 | 视频帧率 |
| `AUDIO_FPS` | 44100 | 音频采样率 |
| `SPEED_SLOW` | 0.75 | 慢速播放倍数 |

### 句子分割

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_SENTENCE_WORDS` | 30 | 单句最大单词数 |
| `MIN_SENTENCE_WORDS` | 5 | 单句最小单词数 |

### 视频各部分配置

每个部分都可以独立配置显示内容：

```python
# Part 1: 原速播放（从句子开始到下一句开始）
PART1_REPEAT_COUNT = 1       # 播放几遍
PART1_SHOW_SUBTITLE = False  # 是否显示字幕框
PART1_SHOW_WORD_BOX = False  # 是否显示单词框
PART1_SHOW_EXPRESSION_BOX = False  # 是否显示表达框

# Part 2: 慢速播放（0.75倍速）
PART2_REPEAT_COUNT = 2       # 播放几遍
PART2_SHOW_SUBTITLE = True   # 显示字幕框
PART2_SHOW_WORD_BOX = True   # 显示单词框
PART2_SHOW_EXPRESSION_BOX = True  # 显示表达框

# Part 3: 正常速度有字幕
PART3_REPEAT_COUNT = 1       # 播放几遍
PART3_SHOW_SUBTITLE = True   # 显示字幕框
PART3_SHOW_WORD_BOX = True   # 显示单词框
PART3_SHOW_EXPRESSION_BOX = True  # 显示表达框
```

### 颜色配置

可以自定义字幕框、单词框、表达框的颜色：

```python
# 单词框颜色
WORD_BOX_BG_COLOR = "#fef9c3"      # 奶油黄背景
WORD_BOX_WORD_COLOR = "#0284c7"    # 单词文字颜色
WORD_BOX_PHONETIC_COLOR = "#6b7280"  # 音标颜色
WORD_BOX_TRANS_COLOR = "#111827"   # 释义颜色

# 表达框颜色
EXPR_BOX_BG_COLOR = "#e0f2fe"      # 淡蓝背景
EXPR_BOX_ENGLISH_COLOR = "#0369a1"  # 英文颜色
EXPR_BOX_CHINESE_COLOR = "#111827"  # 中文颜色

# 字幕框颜色
SUBTITLE_BOX_BG_COLOR = "#ffffff"
SUBTITLE_BOX_ENGLISH_COLOR = "#111827"
SUBTITLE_BOX_CHINESE_COLOR = "#374151"
```


---

## 📖 使用说明

### 基本使用

1. 在 `config.py` 中设置 `INPUT_VIDEO_PATH` 指向你的视频文件
2. 确保 `.env` 文件中配置了 `OPENAI_API_KEY`
3. 运行 `python main.py`

### 测试模式

如果想从中间步骤开始（用于调试或修改）：

```python
# 在 main.py 中设置
TEST_MODE = True
TEST_OUTPUT_NAME = "demo"      # 使用哪个中间结果
TEST_START_STEP = 2            # 从第几步开始: 
                                # 1 = 从句子文件加载
                                # 2 = 从分析结果加载  
                                # 3 = 直接生成视频
```

### 程序输出

运行完成后，`output` 目录下会生成：

```
output/
├── demo.md                    # Markdown 格式的学习笔记
├── demo.mp4                   # 视频文件（别名，指向 _full 版本）
├── demo_quick.mp4            # 快速版视频（原速 + 字幕）
└── demo_full.mp4             # 学习版视频（慢速 + 单词框 + 表达框）
```

### 中间文件（处理后自动清理）

```
output/
├── demo_1_sentences.txt       # 分割后的句子
├── demo_2_analysis.json       # AI 分析结果
└── demo_segments.json         # 句子时间戳信息
```

---


## 📝 Markdown 输出示例

生成的 `demo.md` 文件包含结构化的学习内容：

```markdown
# English Learning Notes

## Sentence 1
**Original:** The quality of your life depends on the quality of your thoughts.

**Translation:** 你生活的质量取决于你思想的质量。

### 🎯 Key Words
| Word | Phonetic | Translation | Difficulty |
|------|----------|-------------|------------|
| quality | /ˈkwɒləti/ | 质量 | ⭐⭐⭐ |

### 💬 Useful Expressions
- **depend on** - 取决于
- **the quality of** - ...的质量
```

---


---

## 📄 开源协议

本项目基于 **CC BY-NC 4.0**（知识共享署名-非商业性使用 4.0 国际）协议开源。

### 你可以：
- ✅ 自由使用、修改、传播本项目
- ✅ 用于个人学习或教育目的
- ✅ 分享本项目时需注明作者来源

### 你不能：
- ❌ 将本项目用于商业目的
- ❌ 未经授权将本项目商用

完整协议内容请查看 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音转文字
- [MoviePy](https://zulko.github.io/moviepy/) - 视频处理
- [DeepSeek](https://www.deepseek.com/) - 大语言模型 API
- 所有开源贡献者

---

<p align="center">Made with ❤️ for English learners</p>
