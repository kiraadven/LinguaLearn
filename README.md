# LinguaLearn — 多语言学习视频生成平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-6c63ff?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-00b4d8?style=for-the-badge&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Whisper-OpenAI-ff6b6b?style=for-the-badge&logo=openai&logoColor=white">
  <img src="https://img.shields.io/badge/MoviePy-1.0.3-4ecdc4?style=for-the-badge">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-green?style=for-the-badge">
</p>

> 把任何外语视频自动变成结构化的「逐句精听」学习视频 —— 支持 7 种语言双向互学

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🎙️ **自动转录** | 本地 Whisper 模型，支持 7 种语言，带单词级时间戳 |
| ✂️ **智能分句** | LLM 辅助分句，自动对齐时间戳，每句 5-30 词 |
| 🧠 **AI 词汇分析** | DeepSeek 并行分析，每句提取 2-6 个关键词 + 1-3 个实用表达 |
| 🎬 **三段式视频结构** | Part1（原速）→ Part2（慢速+覆盖框）→ Part3（原速+覆盖框）|
| 🖼️ **可视化覆盖层** | Chrome Headless 渲染字幕框、单词框、表达框为 PNG |
| 📐 **布局编辑器** | 前端拖拽/缩放三个覆盖框，实时预览位置和大小 |
| 🎨 **样式个性化** | 字体族、字号倍率、行间距、背景色、文字色均可自定义 |
| 📊 **实时进度** | WebSocket 推送每帧渲染进度，支持随时取消 |
| 📝 **Markdown 文字稿** | 自动生成结构化学习笔记，含原文/译文/音标/释义 |
| 👤 **用户系统** | 邮箱注册+验证码、个人任务历史、密码修改 |

---

## 支持语言

| 代码 | 语言 | 学习方向示例 |
|------|------|-------------|
| `en` | 🇺🇸 English  | 英 → 中、英 → 日 |
| `zh` | 🇨🇳 中文      | 中 → 英、中 → 日 |
| `ja` | 🇯🇵 日本語    | 日 → 中、日 → 英 |
| `ko` | 🇰🇷 한국어    | 韩 → 中、韩 → 英 |
| `de` | 🇩🇪 Deutsch   | 德 → 英、德 → 中 |
| `fr` | 🇫🇷 Français  | 法 → 英、法 → 中 |
| `es` | 🇪🇸 Español   | 西 → 英、西 → 中 |

任意两种语言之间均可互学。

---

## 视频结构说明

每一句话生成三段子视频拼接：

```
┌──────────────────────────────────────────┐
│  Part 1 · 原速播放（无覆盖层）           │  × repeat1 次
│  "听音辨义" — 先尝试理解原声            │
├──────────────────────────────────────────┤
│  Part 2 · 慢速播放（0.75x，有覆盖层）   │  × repeat2 次
│  字幕框 ＋ 单词框 ＋ 表达框            │
├──────────────────────────────────────────┤
│  Part 3 · 原速播放（有覆盖层）           │  × repeat3 次
│  巩固记忆，配合覆盖层复习              │
└──────────────────────────────────────────┘
```

---

## 快速开始（Web 界面）

### 1. 克隆并安装

```bash
git clone https://github.com/yourusername/lingualearn.git
cd lingualearn

conda create -n automation python=3.10 -y
conda activate automation
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env   # 然后编辑 .env
```

```env
# 必填：LLM API（兼容 OpenAI 格式，推荐 DeepSeek）
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.deepseek.com

# 分句用 API（可与上面相同，也可用更快的模型）
SPLITTER_API_KEY=sk-xxxx
SPLITTER_BASE_URL=https://api.openai.com/v1
SPLITTER_MODEL=gpt-4-ca

# Whisper 模型大小: tiny / base / small / medium / large
WHISPER_MODEL_SIZE=small

# 可选：邮件 SMTP（不配置则在控制台打印验证码，适合本地开发）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=LinguaLearn <your@gmail.com>
```

### 3. 启动服务

```bash
bash start_web.sh
# 访问 http://localhost:8000
```

---

## 快速开始（命令行）

```bash
conda activate automation
python main.py path/to/video.mp4 [output_name]
```

---

## 用户自定义配置（前端 Web）

### 语言设置
- **源语言**：视频中的语言
- **目标语言**：你的母语（用于翻译和释义）

### 视频结构
| 参数 | 默认 | 说明 |
|------|------|------|
| Part1 重复次数 | 1 | 原速无字幕，"盲听" |
| Part2 重复次数 | 2 | 慢速含字幕，精听 |
| Part3 重复次数 | 1 | 原速含字幕，巩固 |
| 慢速倍率 | 0.75x | 0.5x–0.9x 可调 |

### 覆盖层内容
| 参数 | 默认 | 说明 |
|------|------|------|
| 单词数量 | 不限 | 每句展示的关键词数（1–6）|
| 表达数量 | 不限 | 每句展示的实用表达数（1–3）|

### 样式个性化
| 参数 | 选项 | 说明 |
|------|------|------|
| 字体族 | 系统字体 / 衬线 / 圆体 / 等宽 | 覆盖层字体风格 |
| 字号倍率 | 0.8x – 1.3x | 在自动计算的基础上缩放 |
| 行间距 | 紧凑 / 标准 / 宽松 | 行高调节 |
| 字幕框背景 | 白色 / 米色 / 深色 / 蓝色 | 字幕背景主题 |
| 各框颜色 | 颜色选择器 | 背景色、文字色、音标色等 |

### 布局编辑器
点击「预览布局」生成示例图，拖拽/缩放三个覆盖框（字幕框、单词框、表达框），
确认后所有生成的视频都使用该布局。布局以百分比存储，与分辨率无关。

### 分辨率
- **1080p** (1920×1080) — 推荐，高质量
- **720p** (1280×720) — 快速，适合测试

---

## 系统架构

```
Browser ──HTTP/WS──▶ FastAPI (api.py)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        AudioTranscriber  WordAnalyzer  VideoProcessor
        (Whisper)         (DeepSeek)    (MoviePy)
              │                         │
              ▼                         ▼
        SentenceSplitter          HTMLRenderer
                                  (Chrome Headless)
```

### 文件结构

```
lingualearn/
├── api.py                  # FastAPI 主服务
├── main.py                 # CLI 入口
├── config.py               # 全局配置
├── core/
│   ├── audio_transcriber.py  # Whisper 转录 + 时间戳对齐
│   ├── sentence_splitter.py  # LLM 辅助智能分句
│   ├── word_analyzer.py      # DeepSeek 词汇分析（10线程并行）
│   ├── html_renderer.py      # Chrome Headless 渲染 PNG
│   ├── video_processor.py    # MoviePy 视频合成
│   ├── markdown_exporter.py  # Markdown 文字稿导出
│   └── templates/            # HTML 覆盖层模板
│       ├── subtitle_template.html
│       ├── wordbox_template.html
│       └── expressionbox_template.html
├── static/
│   └── index.html          # 前端 SPA
├── uploads/                # 上传的原始视频（临时）
├── output/                 # 生成的视频和文字稿
└── temp/                   # 临时 PNG 和音频文件
```

---

## Markdown 输出示例

```markdown
# Learning Notes · English → 中文

## Sentence 1
**原文：** The acquisition of language is a remarkable phenomenon.
**译文：** 语言习得是一种非凡的现象。

### 关键词
| 单词 | 音标 | 释义 | 难度 |
|------|------|------|------|
| acquisition | /ˌækwɪˈzɪʃən/ | 习得；获取 | ⭐⭐⭐⭐ |
| remarkable  | /rɪˈmɑːrkəbl/  | 非凡的     | ⭐⭐⭐   |

### 实用表达
- **in the long run** — 从长远来看
- **as a result of** — 由于…的结果
```

---

## 性能参考

| 视频长度 | 句子数 | 转录 | AI分析 | 视频渲染 | 总计 |
|---------|-------|------|--------|---------|------|
| 5 分钟  | ~20句 | 1分钟 | 2分钟  | 8分钟   | ~11分钟 |
| 10 分钟 | ~40句 | 2分钟 | 3分钟  | 15分钟  | ~20分钟 |
| 20 分钟 | ~80句 | 4分钟 | 5分钟  | 30分钟  | ~40分钟 |

> 渲染时间受机器性能、分辨率和重复次数影响较大。

---

## 开源协议

**CC BY-NC 4.0** — 允许个人学习和非商业使用，需署名。

---

<p align="center">Made with ❤️ for language learners worldwide</p>
