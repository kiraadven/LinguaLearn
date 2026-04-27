# LinguaLearn

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-6c63ff?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-00b4d8?style=for-the-badge&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Vue_3-Vite_8-42b883?style=for-the-badge&logo=vue.js&logoColor=white">
  <img src="https://img.shields.io/badge/Whisper-OpenAI-ff6b6b?style=for-the-badge&logo=openai&logoColor=white">
  <img src="https://img.shields.io/badge/License-CC%20BY--NC%204.0-green?style=for-the-badge">
</p>

LinguaLearn 是一个端到端的 AI 语言学习平台。用户上传任意语言的视频，系统自动完成 **语音转录 → 智能分句 → 词汇/表达分析 → 可视化学习视频合成**，并提供 **AI 实时语音教学、间隔重复复习系统、词典查词** 等学习闭环。

支持 9 种语言的互相学习：English · 中文(简/繁) · 日本語 · 한국어 · Deutsch · Français · Español · Русский

---

## 功能总览

### 1. 视频学习内容生成

完整的 5 步自动化流水线，用户上传一段视频即可获得完整学习材料：

| 步骤 | 功能 | 实现 |
|------|------|------|
| **音频转录** | 从视频中提取音频，使用 Whisper 转录为文字 | `core/learning/audio_transcriber.py`，支持 CJK 与 Latin 脚本，可选简繁中文转换 (OpenCC) |
| **智能分句** | 将转录文本切分为适合学习的句子单元 | `core/learning/sentence_splitter.py`，LLM 分句为主、NLTK punkt 降级兜底，可配置句长上下限 |
| **词汇分析** | 为每句提取关键词（词元化、音标、难度）和实用表达 | `core/learning/word_analyzer.py`，LLM 驱动，每句 2–12 词 + 1–8 表达 |
| **文稿导出** | 生成结构化 Markdown 学习笔记（含词汇表、听写练习） | `core/learning/markdown_exporter.py`，支持 PDF 导出（Playwright 渲染） |
| **视频合成** | 叠加字幕、词框、表达框，生成多 Part 学习视频 | `core/learning/video_processor.py`，FFmpeg 流水线 + Konva Node 或 Chrome Headless 渲染叠加层 |

生成的学习视频支持多 Part 结构：原速无字幕 → 慢速带字幕/词框 → 原速带字幕，每个 Part 的重复次数、速度、可见元素均可在前端编辑器中自由配置。

### 2. 可视化 Timeline 编辑器

前端基于 **vue-konva** 提供所见即所得的画布编辑器：

- **元素管理**：字幕、词框、表达框、水印的位置/大小/样式拖拽调节
- **Part 配置**：添加/复制/删除/排序 Part，逐 Part 控制元素可见性
- **12 套艺术主题**（赛博霓虹、森林水墨、极光暗色等）+ 多字体选择
- **入场动画预览**（fade / slide / pop 等）
- **布局预设系统**：保存/加载/删除常用配置
- 前后端使用同一套 `shared/konva-renderer.js` 保证编辑器预览与服务端渲染一致

### 3. 学习工作室（JobDetail 页面）

视频生成完成后进入学习工作室，三个学习模式：

- **精听 (Intensive Listening)**：视频播放器 + 实时同步字幕面板，点击句子跳转对应时间点。支持清晰度切换（auto/1080p/720p/360p）、倍速播放（0.5x–2x，会员）
- **随身听 (Podcast)**：AI 生成讲解音频 + 原声切片拼接的随身听 MP3
- **测验 (Quiz)**：跳转到间隔重复复习系统

额外功能：
- **词典查词**：悬浮/点击词汇即时弹出释义卡片（音标、词义、近义词、发音）
- **学习笔记**：渲染 Markdown 文稿，支持 PDF 导出（会员）
- **键盘快捷键**：Space/K 播放、J/← 后退 5s、L/→ 前进 5s、F 全屏、M 静音

### 4. AI 讲课 & AI 随身听

基于已生成的视频学习材料，调用 LLM 进一步生成结构化教学内容：

- **内容分析**：自动识别视频类型（新闻/电影/访谈/纪录片/日常等）
- **AI 讲课脚本**：LLM 规划课程结构 → 生成教学文稿 → TTS 合成语音
- **AI 随身听脚本**：生成播客风格讲解 → TTS 合成 → 拼接原声切片为完整 MP3
- **异步生成 + 轮询进度**：后台任务，前端通过 `/tutor/status` 轮询

TTS 支持多个 provider：MiniMax（默认）、OpenAI、ElevenLabs、Azure。

### 5. AI Tutor 实时语音教学

全双工语音交互 AI 语言教师，基于 WebSocket 实时通信：

```
浏览器麦克风 → PCM 16kHz → WebSocket → FunASR (ASR) → LLM (Claude) → CosyVoice (TTS) → 音频流 → 浏览器
```

核心模块：

| 模块 | 功能 |
|------|------|
| `ai_tutor/voice/` | 全双工语音管道：VAD 语音检测、FunASR 流式 ASR、CosyVoice 流式 TTS、打断机制 |
| `ai_tutor/session/` | 教学状态机（IDLE → INTRO → TEACHING → REVIEW → END）、注意力监控、Prompt 构建 |
| `ai_tutor/llm/` | Claude 流式客户端、结构化输出解析、工具调用 |
| `ai_tutor/memory/` | 四层记忆系统：短期记忆、课程进度记忆、长期记忆、学习者画像图谱 |
| `ai_tutor/content/` | 课程大纲引擎，基于 SLA 理论（Krashen i+1、交互假说、间隔检索）逐句构建教学计划 |
| `ai_tutor/models/` | FunASR / CosyVoice 模型管理与服务进程管理 |

### 6. 间隔重复复习系统（Quiz）

FSRS 调度算法驱动的复习系统，覆盖单词、表达和句子三种题型：

- **单词/表达拼写**：逐字符输入网格，自动跳格，支持方向键导航
- **句子听写**：播放原声切片 + 完形填空输入
- **掌握标记**：已掌握项加入"掌握本"，支持取消掌握
- **全局复习**：跨视频 FSRS 调度，可配置每日复习上限
- **视频内复习**：针对单个视频的词汇/表达定向练习

### 7. 本地词典系统（Wiktextract）

基于 Wiktionary 数据的离线词典，支持悬浮查词和卡片展示：

- 数据源：kaikki.org 提供的 Wiktionary 解析数据（JSONL 格式）
- 构建流程：下载 → SQLite 索引 → 预计算卡片缓存
- 支持语言：en, zh, ja, ko, de, fr, es, ru
- 可选 Oxford Dictionary API 作为补充数据源
- LLM 翻译兜底：词典无结果时自动调用 LLM 翻译释义

### 8. 用户与会员体系

- **注册登录**：邮箱验证码 / 手机短信验证码（阿里云）
- **会员等级**：免费版 vs 会员版
  - 免费版：每日 3 个视频、单个视频 ≤5 分钟、系统水印、10 GB 存储
  - 会员版：每日 15 个视频、单个视频 ≤20 分钟、自定义水印、128 GB 存储、倍速播放、PDF 导出、高级样式
- **支付集成**：Stripe（国际）/ 支付宝（中国），支持日卡/周卡/月卡/年卡
- **国家检测**：通过 CDN 头自动区分 CN/国际市场，价格本地化（CNY / USD / EUR / JPY / KRW / RUB）

---

## 环境要求

- **Python 3.10+**
- **Node.js 20+**
- **FFmpeg**（`ffmpeg` + `ffprobe` 需在 PATH 中可用）

可选：

- **Playwright Chromium** — PDF 导出和 HTML 渲染降级模式：`playwright install chromium`
- **GPU + CUDA** — Whisper、FunASR、CosyVoice 推理加速

---

## 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# Node 依赖（服务端 Konva 渲染 sidecar）
npm install

# 前端依赖（仅需重新构建前端时）
cd frontend && npm install && cd ..
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，最少只需配置一个 LLM Key 即可运行核心功能：

```env
# ── 必填 ──
LLM_API_KEY=sk-xxxx

# ── 推荐配置 ──
LLM_PROVIDER=deepseek                          # deepseek | openai | gemini | custom
LLM_BASE_URL=https://api.deepseek.com/v1       # OpenAI 兼容 API 地址
WHISPER_MODEL_SIZE=small                        # tiny / base / small / medium / large
VIDEO_RESOLUTION=1080p                          # 1080p / 720p
PORT=8080
```

### 3. 启动服务

```bash
# 方式一：直接启动（推荐开发）
python api.py

# 方式二：使用脚本（自动创建 data/ 目录结构）
bash scripts/start_web.sh
```

服务默认地址：`http://localhost:8080`

### 4. 构建前端（可选）

开发模式使用 Vite dev server + 代理：

```bash
cd frontend && npm run dev
```

生产构建（输出到 `static/`，由 FastAPI 直接托管）：

```bash
cd frontend && npm run build
```

---

## 环境变量详解

所有配置项见 `.env.example`，按功能分组说明：

### A. 主 LLM（词汇分析、翻译）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 服务商 | `deepseek` |
| `LLM_API_KEY` | API Key（**必填**） | — |
| `LLM_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.deepseek.com/v1` |

### B. 分句模型（Sentence Splitter）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SPLITTER_PROVIDER` | `inherit`（复用主 LLM）/ `custom` | `inherit` |
| `SPLITTER_MODEL` | 分句使用的模型名 | `deepseek-reasoner` |
| `SPLITTER_API_KEY` | 仅 `custom` 时需要 | 回退到 `LLM_API_KEY` |
| `SPLITTER_BASE_URL` | 仅 `custom` 时需要 | 回退到 `LLM_BASE_URL` |

### C. TTS（语音合成）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TTS_PROVIDER` | `minimax` / `openai` / `elevenlabs` / `azure` | `minimax` |
| `TTS_MODEL` | 模型名称 | `speech-2.8-turbo` |
| `TTS_API_KEY` | 对应 provider 的 Key | — |
| `TTS_VOICE` | 音色 ID | `male-qn-qingse` |
| `TTS_ENDPOINT` | API 地址 | `https://api.minimax.io/v1/t2a_v2` |

ElevenLabs / Azure 各有独立的 Key、Voice、Region 配置，见 `.env.example`。

### D. 词典

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DICT_MODE` | `wiktextract`（本地 SQLite）/ `oxford` | `wiktextract` |
| `DICT_DB_PATH` | 词典数据库路径 | `data/wiktextract_trans.sqlite3` |
| `DICT_ENABLE_LLM_TRANSLATION` | 词典无结果时用 LLM 翻译 | `1` |

Oxford API 需额外配置 `DICT_OXFORD_APP_ID` / `DICT_OXFORD_APP_KEY`。

### E. Whisper & 视频

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WHISPER_MODEL_SIZE` | 模型大小 | `small` |
| `VIDEO_RESOLUTION` | 输出分辨率 | `1080p` |

### F. 邮件 & 短信

| 变量 | 说明 |
|------|------|
| `RESEND_API_KEY` | Resend 邮件服务 Key |
| `SMS_ACCESS_KEY_ID` / `SMS_ACCESS_KEY_SECRET` / `SMS_TEMPLATE_CODE` | 阿里云短信 |

### G. 支付

| 变量 | 说明 |
|------|------|
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe 支付 |
| `STRIPE_PRICE_CN_*` / `STRIPE_PRICE_INTL_*` | 各档位 Price ID |
| `ALIPAY_APP_ID` / `ALIPAY_PRIVATE_KEY` / `ALIPAY_PUBLIC_KEY` | 支付宝 |
| `APP_BASE_URL` | 支付回调地址 |

> 支付、邮件、短信不配置不影响核心功能，仅相关功能不可用。

---

## AI Tutor 配置（FunASR + CosyVoice）

AI Tutor 是独立的实时语音教学模块，需要额外安装模型。不配置 AI Tutor 不影响其他功能。

### 1. 安装额外依赖

```bash
pip install -r ai_tutor/requirements.txt
```

包含 `funasr`、`modelscope`、`torch`、`torchaudio`、`transformers`、`aiosqlite` 等。Linux 下若遇到 `sox` 报错需安装系统包：`apt install sox libsox-dev`。

### 2. 下载 ASR / TTS 模型

```bash
python ai_tutor/models/setup.py \
  --funasr-dir ai_tutor/models/assets/funasr \
  --cosyvoice-dir ai_tutor/models/assets/CosyVoice2-0.5B \
  --cosyvoice-code-dir ai_tutor/models/CosyVoice
```

该脚本会：
- 从 ModelScope 下载 FunASR 模型
- 从 HuggingFace 下载 CosyVoice2-0.5B 权重
- 自动 `git clone` CosyVoice 推理代码

### 3. 准备声音克隆参考音频

将参考音频放入 `data/voices/`，文件名与 `DEFAULT_VOICE_ID` 对应：

```
data/voices/sarah_en.wav
data/voices/kenji_ja.wav
```

### 4. 配置环境变量

在 `.env` 中补充：

```env
# ASR / TTS 服务地址
FUNASR_WS_URL=ws://127.0.0.1:10095
COSYVOICE_HTTP_URL=http://127.0.0.1:9880

# 自动拉起本地模型服务（推荐）
AUTO_START_MODEL_SERVICES=true
MODEL_SERVICE_STARTUP_TIMEOUT_SECONDS=120

# AI Tutor 对话模型
ANTHROPIC_API_KEY=sk-ant-xxxx
ANTHROPIC_MODEL=claude-haiku-4-5-20251001-thinking
LLM_API_BASE_URL=https://api.chatanywhere.tech
LLM_CHAT_PATH=/v1/chat/completions

# 数据目录
PROFILE_DB_PATH=data/learner_profiles.db
LESSON_PLAN_DIR=data/lesson_plans
FILLER_DIR=data/fillers
DEFAULT_VOICE_ID=sarah_en
```

### 5. 启动

**推荐**：使用主服务统一入口。当 `AUTO_START_MODEL_SERVICES=true` 且 ASR/TTS 地址指向本机时，主服务启动时会自动拉起 FunASR (10095) 和 CosyVoice (9880)：

```bash
bash scripts/start_web.sh
```

**手动调试**（分别启动各服务）：

```bash
# 终端 1 - FunASR
cd ai_tutor && python models/funasr_server.py --host 0.0.0.0 --port 10095 --device cpu

# 终端 2 - CosyVoice
cd ai_tutor && python models/cosyvoice_server.py --host 0.0.0.0 --port 9880

# 终端 3 - 主服务
python api.py
```

健康检查：

```bash
curl http://127.0.0.1:9880/health
```

---

## 字体下载（Konva 渲染）

服务端视频渲染需要字体文件，确保渲染结果与前端编辑器一致：

```bash
bash scripts/download_fonts.sh
```

- 默认下载到 `data/fonts/`
- `--dir <path>` 自定义目录
- `--sync-static` 额外复制到 `static/fonts/`
- 渲染器优先读取 `LINGUA_FONT_DIR`，否则使用 `data/fonts/`

---

## 词典数据管线

词典查词依赖 `data/wiktextract_trans.sqlite3`，通过 `scripts/wiktextract_build.py` 构建：

```
kaikki.org (.jsonl.gz) → download → build (SQLite索引) → precompute (卡片缓存)
```

### 常用命令

```bash
# 一次跑完整流程
python scripts/wiktextract_build.py --stages all --langs en,zh,ja,ko,de,fr,es,ru

# 只下载
python scripts/wiktextract_build.py --stages download --langs en,zh

# 只建索引
python scripts/wiktextract_build.py --stages build --langs en,zh

# 只预热缓存
python scripts/wiktextract_build.py --stages precompute --langs en,zh \
  --precompute-limit 50000 --zh-script both
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--stages` | `download` / `build` / `precompute`，可组合，`all` 代表全部 |
| `--langs` | 指定语言，省略则处理所有 |
| `--reset` | build 前清空数据库 |
| `--overwrite-download` | 强制重新下载 |
| `--precompute-limit` | 每语言最多预热词数 |
| `--zh-script` | `hans` / `hant` / `both`（默认 `both`） |

卡片数据格式：

```json
{
  "word": "pound",
  "phonetic": "/paʊnd/",
  "audio": "",
  "meanings": [
    {"pos": "noun", "definition": "A unit of weight equal to 16 ounces.", "example": "...", "synonyms": []}
  ],
  "translated_meanings": ["磅（重量单位，等于16盎司）"]
}
```

---

## 项目结构

```
├── api.py / config.py          # 根目录兼容入口 → 转发到 backend/
├── backend/
│   ├── api.py                  # FastAPI 主服务（路由组合、任务调度、WebSocket）
│   └── config.py               # 全局配置（env 加载、语言常量、渲染默认值）
├── core/                       # 后端核心逻辑
│   ├── app/routes/             # API 路由模块（auth / membership / config / i18n / review）
│   ├── app/                    # 服务层（词典路由、会员服务、Oxford 客户端）
│   ├── db/                     # SQLite 数据层（users / jobs / review / membership / tokens）
│   ├── learning/               # 视频处理流水线（transcriber → splitter → analyzer → processor → exporter）
│   ├── rendering/              # 渲染引擎（Konva Node sidecar / Chrome Headless / 12 套样式模板）
│   └── wiktextract/            # 词典管线（download → index → lookup → cache）
├── ai_tutor/                   # AI 实时语音教学模块
│   ├── voice/                  # 语音管道（ASR 客户端、TTS 客户端、VAD、打断、混音）
│   ├── session/                # 教学状态机、注意力监控、Prompt 构建
│   ├── llm/                    # Claude LLM 客户端、课程 Prompt 模板
│   ├── memory/                 # 四层记忆系统（短期 / 课程 / 长期 / 学习者画像）
│   ├── content/                # 课程大纲引擎（SLA 理论驱动、CEFR 分级）
│   ├── tools/                  # LLM 工具定义与执行器
│   └── models/                 # 模型下载脚本、FunASR/CosyVoice 服务启动器
├── shared/                     # 前后端共享的 Konva 渲染引擎和动画引擎（JS/ESM）
├── frontend/                   # Vue 3 + Vite 前端
│   └── src/
│       ├── pages/              # 页面（Home / Create / Results / JobDetail / Quiz / AiTutor / Profile / Membership）
│       ├── composables/        # 组合式函数（auth / api / timeline / konva-editor / dictionary / toast 等）
│       └── components/         # 公共组件（MembershipModal / editor 子组件）
├── scripts/                    # 工具脚本（start_web.sh / download_fonts.sh / wiktextract_build.py）
└── data/                       # 运行时数据（SQLite DB / uploads / output / fonts / voices / wiktextract）
```

---

## API 概览

### 视频任务

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/jobs` | 上传视频 + Timeline JSON，创建生成任务 |
| `GET` | `/api/jobs` | 获取当前用户的任务列表 |
| `GET` | `/api/jobs/:id` | 查询任务状态 |
| `PATCH` | `/api/jobs/:id` | 重命名任务 |
| `DELETE` | `/api/jobs/:id` | 取消/删除任务 |
| `WS` | `/api/ws/:id` | 实时进度推送（5 步 + 渲染百分比 + 日志） |
| `GET` | `/api/jobs/:id/stream/:file?quality=` | 视频流播放（支持清晰度切换） |
| `GET` | `/api/jobs/:id/download/:file` | 文件下载 |
| `GET` | `/api/jobs/:id/export-notes-pdf` | PDF 导出 |

### AI 讲课 & 随身听

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/jobs/:id/tutor/generate` | 启动 AI 讲课 + 随身听脚本生成（异步） |
| `GET` | `/api/jobs/:id/tutor/status` | 查询生成进度 |
| `GET` | `/api/jobs/:id/tutor/script` | 获取讲课脚本 JSON |
| `GET` | `/api/jobs/:id/tutor/audio/:file` | 获取 TTS 合成音频 |
| `GET` | `/api/jobs/:id/tutor/podcast` | 下载完整随身听 MP3 |

### AI Tutor 实时教学

| 方法 | 路径 | 说明 |
|------|------|------|
| `WS` | `/ws/tutor` | 旧版语音交互入口 |
| `WS` | `/ai-tutor/ws/:learner_id` | 新版交互式教学会话 |
| `GET` | `/ai-tutor/learner/:id/memory` | 获取学习者记忆 |
| `POST` | `/ai-tutor/learner` | 创建/更新学习者档案 |

### 复习系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/review/session` | 创建复习会话 |
| `POST` | `/api/review/grade` | 提交答题结果 |
| `PATCH` | `/api/review/items/:id/mastered` | 标记/取消掌握 |
| `GET` | `/api/review/mastered` | 查看掌握本 |
| `GET/PATCH` | `/api/review/settings` | 复习设置 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/languages` | 支持的语言列表 |
| `GET` | `/api/styles` | 样式模板列表 |
| `GET` | `/api/dictionary/lookup` | 词典查词 |
| `GET` | `/api/membership/status` | 会员状态 |
| `POST` | `/api/membership/checkout/stripe` | Stripe 支付 |
| `POST` | `/api/membership/checkout/alipay` | 支付宝支付 |

---

## 许可证

本项目采用 [CC BY-NC 4.0](LICENSE) 协议，仅允许非商业用途。
