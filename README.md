# LinguaLearn — 多语言学习视频生成平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-6c63ff?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-00b4d8?style=for-the-badge&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Vue-3-35495e?style=for-the-badge&logo=vue.js&logoColor=white">
  <img src="https://img.shields.io/badge/FFmpeg-Pure-ff6b6b?style=for-the-badge">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-green?style=for-the-badge">
</p>

> 把任何外语视频自动变成结构化的「逐句精听」学习视频 —— 支持 8 种语言双向互学

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🎙️ **自动转录** | 本地 Whisper 模型，支持 8 种语言，带单词级时间戳 |
| ✂️ **智能分句** | LLM 辅助分句，自动对齐时间戳，每句 5-30 词 |
| 🧠 **AI 词汇分析** | DeepSeek 并行分析，每句提取 2-6 个关键词 + 1-3 个实用表达 |
| 🎬 **三段式视频结构** | Part1（原速）→ Part2（慢速+覆盖框）→ Part3（原速+覆盖框）|
| 🖼️ **可视化覆盖层** | 使用 Konva + Node.js 渲染（与前端同源），或 Chrome Headless 降级 |
| 📐 **可视化编辑器** | Vue 3 + Konva 前端拖拽/缩放三个覆盖框，实时预览位置和大小 |
| 🎨 **主题系统** | 13 种预设主题 + 7 种动画 + 16 种字体，样式完全可自定义 |
| 📊 **实时进度** | WebSocket 推送每帧渲染进度，支持随时取消 |
| 📝 **Markdown 文字稿** | 自动生成结构化学习笔记，含原文/译文/音标/释义 |
| 👤 **用户系统** | 邮箱注册+验证码、个人任务历史、密码修改 |
| 💾 **预设保存** | 保存/加载编辑器配置，支持批处理 |

---

## 支持语言

| 代码 | 语言 | 
|------|------|
| `en` | 🇺🇸 English  
| `zh` | 🇨🇳 中文      |
| `ja` | 🇯🇵 日本語    |
| `ko` | 🇰🇷 한국어    |
| `de` | 🇩🇪 Deutsch   | 
| `fr` | 🇫🇷 Français  | 
| `es` | 🇪🇸 Español   |
| `ru` | 🇷🇺 Русский   |

任意两种语言之间均可互学。

---

## 技术栈

### 后端
- **FastAPI** - REST API + WebSocket
- **SQLite** - 用户和任务数据存储
- **Whisper** - 音频转录（OpenAI 本地模型）
- **FFmpeg** - 纯媒体处理（无 MoviePy）
- **Chrome Headless** - HTML→PNG 渲染（降级模式）
- **Node.js** - Konva 渲染 sidecar（优先模式）

### 前端
- **Vue 3** - 现代化 SPA
- **Vite** - 快速构建工具
- **Konva** - 基于 Canvas 的编辑器
- **响应式设计** - 移动友好

### 渲染模式（优先级）
- **Konva JSON** （优先）- Node.js sidecar 同源渲染，最快

---

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/kiraadven/lingualearn.git
cd lingualearn

# 创建 Conda 环境
conda create -n automation python=3.10 -y
conda activate automation

# 安装依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install && npm run build
cd ..
```

### 2. 环境配置

```bash
# 复制环境模板
cp .env.example .env
```

编辑 `.env` 文件（必填项）：

```env
# ===== LLM API（兼容 OpenAI 格式，推荐 DeepSeek）=====
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.deepseek.com

# ===== 分句 API（可与上面相同，也可用更快的模型）=====
SPLITTER_API_KEY=sk-xxxx
SPLITTER_BASE_URL=https://api.deepseek.com
SPLITTER_MODEL=deepseek-chat

# ===== Whisper 模型大小 =====
# 可选：tiny / base / small（推荐）/ medium / large
WHISPER_MODEL_SIZE=small

# ===== 邮件 API（可选）=====
# 不配置则在控制台打印验证码（适合本地开发）
RESEND_API_KEY=re_xxxx

# ===== 视频分辨率（可选，默认 1080p）=====
# 可选：1080p / 720p
VIDEO_RESOLUTION=1080p
```


### 3. 启动服务

```bash
# 激活环境
conda activate automation

# 启动 FastAPI 服务（默认 http://localhost:8080）
python api.py
```

然后在浏览器中打开 http://localhost:8080，开始使用 Web 界面。

---

## 使用指南

### Web 界面工作流

#### 1️⃣ 创建任务

点击「**新建任务**」，上传视频文件：

| 参数 | 说明 |
|------|------|
| **视频文件** | 支持 MP4、MKV 等常见格式 |
| **源语言** | 视频中的语言 |
| **目标语言** | 你的母语（用于翻译和释义） |

#### 2️⃣ 编辑配置

**视频结构**

| 参数 | 默认 | 说明 |
|------|------|------|
| Part1 重复次数 | 1 | 原速无字幕，"盲听" |
| Part2 重复次数 | 2 | 慢速含字幕，精听 |
| Part3 重复次数 | 1 | 原速含字幕，巩固 |
| 慢速倍率 | 0.75x | 0.5x–2.0x 可调 |

**样式与主题**

- **13 种预设主题** —— 选择配色方案
- **7 种动画效果** —— 元素进入动画
- **16 种字体** —— 包括中日韩书法字体

**布局编辑**

点击「**预览布局**」后，在画布上拖拽和缩放三个覆盖框：
- **字幕框** — 原文和译文
- **单词框** — 关键词和音标
- **表达框** — 实用表达和释义

布局以百分比存储，与分辨率无关，所有句子自动应用。

#### 3️⃣ 生成视频

点击「**生成视频**」，系统自动：

1. 转录音频 → 获得时间戳
2. 智能分句 → 对齐时间戳
3. 词汇分析 → 提取关键词和表达
4. 渲染覆盖层 → 生成 PNG 图片（Konva 优先）
5. 视频合成 → 拼接三段视频

实时进度条显示各阶段进度，支持随时取消。

#### 4️⃣ 查看结果

完成后可以：
- **下载视频** — MP4 格式，可直接播放
- **下载文字稿** — Markdown 格式，包含全部信息
- **保存预设** — 保存当前编辑配置，下次快速加载

---

## 系统架构

```
┌────────────────────────────────────┐
│   浏览器 - Vue 3 SPA               │
│ ┌──────────────────────────────┐  │
│ │  Create.vue 编辑器            │  │
│ │ - Konva 可视化编辑            │  │
│ │ - 实时预览                    │  │
│ │ - 主题和字体管理              │  │
│ └──────────────────────────────┘  │
└────────────────┬───────────────────┘
                 │ HTTP/WS
                 ▼
┌────────────────────────────────────┐
│   FastAPI 服务 (api.py)            │
├────────────────────────────────────┤
│  核心处理流程：                    │
│ ┌────────────────────────────┐    │
│ │ 1. AudioTranscriber        │    │
│ │    (Whisper 转录)          │    │
│ └────────────────────────────┘    │
│                ▼                   │
│ ┌────────────────────────────┐    │
│ │ 2. SentenceSplitter        │    │
│ │    (LLM 分句)              │    │
│ └────────────────────────────┘    │
│                ▼                   │
│ ┌────────────────────────────┐    │
│ │ 3. WordAnalyzer            │    │
│ │    (DeepSeek 词汇分析)     │    │
│ └────────────────────────────┘    │
│                ▼                   │
│ ┌────────────────────────────┐    │
│ │ 4. VideoProcessor          │    │
│ │  ├─ KonvaRenderer (优先)   │    │
│ │  ├─ HTMLRenderer (备选)    │    │
│ │  └─ ASSGenerator (降级)    │    │
│ └────────────────────────────┘    │
│                ▼                   │
│ ┌────────────────────────────┐    │
│ │ 5. MarkdownExporter        │    │
│ │    (生成文字稿)            │    │
│ └────────────────────────────┘    │
│                                    │
│  数据存储：SQLite (data/)          │
│  用户系统：邮箱验证、token        │
│  WebSocket：实时进度推送          │
└────────────────────────────────────┘
```

### 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| **转录** | `core/audio_transcriber.py` | Whisper 音频→文本 + 单词时间戳 |
| **分句** | `core/sentence_splitter.py` | LLM 辅助句子分割 + 时间戳对齐 |
| **词汇** | `core/word_analyzer.py` | DeepSeek 并行词汇分析 |
| **渲染** | `core/konva_renderer.py` | Node.js Konva PNG 渲染 (优先) |
| **降级** | `core/html_renderer.py` | Chrome Headless PNG 渲染 |
| **降级** | `core/ass_generator.py` | ASS 字幕生成 |
| **视频** | `core/video_processor.py` | FFmpeg 纯媒体处理流水线 |
| **文稿** | `core/markdown_exporter.py` | Markdown 学习笔记导出 |
| **数据库** | `database.py` | SQLite 用户和任务管理 |
| **前端** | `frontend/src/pages/Create.vue` | Vue 3 编辑器主页面 |

---

## 文件结构

```
lingualearn/
├── api.py                          # FastAPI 主服务
├── config.py                       # 全局配置（必填项、默认值）
├── database.py                     # SQLite 用户/任务管理
├── .env.example                    # 环境变量模板
├── requirements.txt                # Python 依赖
│
├── core/                           # 处理模块
│   ├── audio_transcriber.py        # Whisper 转录
│   ├── sentence_splitter.py        # LLM 分句
│   ├── word_analyzer.py            # DeepSeek 词汇分析
│   ├── konva_renderer.py           # Konva 渲染（Python 包装）
│   ├── konva_render_worker.mjs     # Node.js Konva 渲染 sidecar
│   ├── html_renderer.py            # Chrome Headless 渲染
│   ├── ass_generator.py            # ASS 字幕生成
│   ├── ass_styles.py               # ASS 样式定义
│   ├── video_processor.py          # FFmpeg 视频处理
│   ├── markdown_exporter.py        # Markdown 导出
│   └── templates/                  # HTML 渲染模板（废弃，保留兼容）
│
├── shared/                         # 前后端共享模块（ESM）
│   ├── konva-renderer.js           # 前端 Konva 渲染
│   ├── animation-engine.js         # 动画预设定义
│   ├── theme-mapper.js             # 13 种主题定义
│   ├── font-registry.js            # 16 种字体注册
│   ├── text-layout.js              # 文本布局算法
│   ├── element-renderers/          # Konva 元素渲染器
│   │   ├── subtitle.js
│   │   ├── wordbox.js
│   │   ├── exprbox.js
│   │   ├── watermark.js
│   │   └── sticker.js
│   └── package.json                # ESM 模块配置
│
├── frontend/                       # Vue 3 前端
│   ├── src/
│   │   ├── main.js                 # 入口
│   │   ├── App.vue                 # 根组件
│   │   ├── i18n.js                 # 8 语言国际化系统
│   │   ├── pages/
│   │   │   ├── Create.vue          # 编辑器主页面
│   │   │   ├── JobDetail.vue       # 结果页面
│   │   │   ├── Quiz.vue            # 自测页面（开发中）
│   │   │   └── ...
│   │   ├── components/
│   │   │   └── editor/             # 编辑器组件
│   │   │       ├── KonvaCanvas.vue
│   │   │       ├── PartsSidebar.vue
│   │   │       ├── PropertiesPanel.vue
│   │   │       ├── StyleThemePanel.vue
│   │   │       ├── ToolbarPanel.vue
│   │   │       ├── WatermarkDialog.vue
│   │   │       ├── StickerPicker.vue
│   │   │       └── ColorPicker.vue
│   │   └── composables/            # Vue 3 composables
│   │       ├── useTimeline.js      # 编辑器状态管理
│   │       ├── useKonvaEditor.js   # 拖拽和变形
│   │       └── useAnimationPreview.js  # 动画预览
│   ├── vite.config.js
│   ├── package.json
│   └── public/
│
├── static/                         # 前端构建产物
│   ├── index.html
│   └── assets/
│
├── uploads/                        # 用户上传的视频（临时）
├── output/                         # 生成的视频和文字稿
├── data/                           # SQLite 数据库
└── temp/                           # 临时 PNG、音频、ASS 文件
```

---

## 性能参考

| 视频长度 | 句子数 | 转录 | AI分析 | 视频渲染 | 总计 |
|---------|-------|------|--------|---------|------|
| 5 分钟  | ~20句 | 1分钟 | 2分钟  | 8分钟   | ~11分钟 |
| 10 分钟 | ~40句 | 2分钟 | 3分钟  | 15分钟  | ~20分钟 |
| 20 分钟 | ~80句 | 4分钟 | 5分钟  | 30分钟  | ~40分钟 |

> 渲染时间受机器性能、分辨率、重复次数和渲染模式影响较大。
> Konva 模式通常比 HTML 快 20-30%。

---

## 开源协议

**CC BY-NC 4.0** — 允许个人学习和非商业使用，需署名。

---

## 📋 开发计划 (TODO)

### 🎯 用户体验优化
- [ ] **优化结果展示页面**：提升舒适度和流畅度，包括布局优化、文稿与视频时间戳的智能对应、智能跳转功能
- [ ] **重新设计首页**：优化布局，删除过于专业性的词汇，提升用户友好度
- [ ] **优化配置页面**：改进布局设计，增加新手指引功能

### 🔒 安全与版权
- [ ] **添加水印功能**：为生成的视频和导出文档添加水印保护

### 🌐 网站架构
- [ ] **多页面支持**：支持多个网站页面的跳转，优化用户导航体验
- [ ] **完善网站文档**：编写详细的用户使用文档和开发文档

### 👤 用户系统
- [ ] **丰富个人页面**：增加头像、昵称等个性化配置，增加用户等级系统
- [ ] **社群建设**：增加用户沟通社群功能，类似 Keep 的社区互动

### 📝 学习功能
- [ ] **独立自测平台**：将默写功能独立，支持显示目标语言，用户输入源语言，智能判断对错并打分
- [ ] **AI 学习助手**：集成聊天机器人，解答学习疑问
- [ ] **学习进度追踪**：记录用户学习历史，生成学习统计图表

---

<p align="center">Made with ❤️ for language learners worldwide</p>
