# LinguaLearn

LinguaLearn 是一个基于 FastAPI + Vue 3 的语言学习平台，支持视频生成、词汇抽取、复习单词本、会员体系与个人学习记录。

## 当前功能

- 多语言视频学习内容生成（转录、分句、词汇分析、视频合成）
- Web 端任务创建与进度追踪
- 用户登录注册、任务历史、个人资料
- 单词复习本（保存、标记掌握、删除）
- 会员与支付（Stripe / 支付宝，按配置启用）

## 环境要求

- Python 3.10+
- Node.js 20+
- FFmpeg（需 `ffmpeg` / `ffprobe` 可执行）

可选依赖：

- Playwright Chromium（用于部分 PDF/HTML 渲染能力）
  - 安装命令：`playwright install chromium`

## 安装

```bash
# 1) Python 依赖
pip install -r requirements.txt

# 2) Node 依赖（服务端 Konva 渲染 sidecar）
npm install

# 3) 前端依赖（仅在你需要重新构建前端时）
cd frontend && npm install
```

## 环境变量

先复制模板：

```bash
cp .env.example .env
```

推荐至少配置以下字段：

```env
# 必填：LLM Key
OPENAI_API_KEY=sk-xxxx

# 可选：兼容 OpenAI 的网关地址（默认 https://api.deepseek.com）
OPENAI_BASE_URL=https://api.deepseek.com

# 可选：分句模型专用配置（不填会回退到 OPENAI_*）
SPLITTER_API_KEY=sk-xxxx
SPLITTER_BASE_URL=https://api.deepseek.com
SPLITTER_MODEL=deepseek-chat

# 可选：Whisper 模型（tiny/base/small/medium/large）
WHISPER_MODEL_SIZE=small

# 可选：输出分辨率（1080p / 720p）
VIDEO_RESOLUTION=1080p

# 可选：邮件服务
RESEND_API_KEY=re_xxxx
```

其他支付相关字段（`STRIPE_*`、`ALIPAY_*`）按需配置，不配置不会影响本地基础功能。

## 启动

```bash
python api.py
```

服务默认地址：`http://localhost:8080`

也可以使用脚本（会自动创建 `data/...` 目录）：

```bash
bash scripts/start_web.sh
```

## 字体下载（Konva 渲染）

如果你要让服务端导出视频时的字体和编辑器尽量一致，先下载字体：

```bash
bash scripts/download_fonts.sh
```

说明：

- 默认下载到 `data/fonts/`（不会被前端 `vite build` 清空）；
- 可选参数 `--dir <path>` 自定义目录；
- 可选参数 `--sync-static` 额外复制一份到 `static/fonts/`；
- 渲染器会优先读取 `LINGUA_FONT_DIR`，否则自动尝试 `data/fonts/`。

## 项目结构

- `api.py`: FastAPI 服务入口
- `core/`: 后端核心逻辑（按领域拆分）
  - `core/db/`: 数据库分层模块（users/jobs/membership/config 等）
  - `core/app/`: API 相关服务层（词典路由、会员状态服务、分组路由注册）
    - `core/app/routes/`: auth / membership / config / i18n / review 路由模块
  - `core/learning/`: 学习内容处理流程（转录、分句、词汇分析、导出、视频处理）
  - `core/rendering/`: 渲染层（HTML/Konva 渲染器与模板）
  - `core/wiktextract/`: 本地词典管线分层模块（shared/extractors/pipeline/lookup）
- `frontend/`: Vue 3 前端工程
- `frontend/src/pages/job-detail/`: JobDetail 页面拆分出的样式与 composables
- `frontend/src/pages/quiz/`: Quiz 页面拆分出的样式与 composables
- `config.py`: 环境变量与系统配置
- `data/`: 运行时数据目录
  - `data/uploads/`: 上传文件、头像、贴纸
  - `data/output/`: 每个任务的输出结果
  - `data/temp/`: 任务临时文件（任务结束自动清理）
  - `data/wiktextract/`: 词典原始数据

## TODO
0. 测试每一种语言的视频生成功能
1. 增加复习模式：支持单词、词组、听音频补全句子，并增加复习推荐算法。
2. 做一个个人知识库，并在此基础上增加一个简单 Agent（lesson based copilot）。
3. 注册/上传流程增加《用户协议》主动勾选（默认不勾选，必须用户手动勾选后才能提交）；关键条款需明确包含：
   - 用户声明对上传内容拥有合法权利
   - 平台仅提供技术处理服务
   - 因版权产生的法律责任由用户自行承担
4. 上传页面增加显眼合规提示文案，例如：`请确保您有权上传此视频，平台不存储原始视频，处理完成后将自动删除。`
5. 建立 DMCA 下架流程并公开版权投诉邮箱（用于美国/国际市场的版权投诉受理与处理）。
6. 确保原始视频在处理完成后确实删除，并验证生产环境清理逻辑稳定执行（含失败重试/异常路径）。
7. 增加新手引导的动画
8. 重新设计网站的图标，和前端的引导文字


## 词典数据管线

词典查询依赖 `data/wiktextract_trans.sqlite3`。
现在统一使用一个脚本：`scripts/wiktextract_build.py`，可自由选择执行阶段。

### 数据流说明

```
kaikki.org (.jsonl.gz)
        │
        ▼
wiktextract_build.py --stages download
        │
        ▼
wiktextract_build.py --stages build
        │
        ▼
wiktextract_build.py --stages precompute
```

`card_cache` 是前端实际读取的数据来源，格式：

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

### 支持阶段

`download, build, precompute`

### 支持语言

`en, zh, ja, ko, de, fr, es, ru`

### 常用命令

1. 只下载

```bash
python scripts/wiktextract_build.py \
  --stages download \
  --langs en,zh,ja,ko,de,fr,es,ru
```

2. 只建索引（默认阶段就是 build）

```bash
python scripts/wiktextract_build.py \
  --stages build \
  --langs en,zh,ja,ko,de,fr,es,ru
```

3. 只 precompute（预热 `card_cache`）

```bash
python scripts/wiktextract_build.py \
  --stages precompute \
  --langs en,zh,ja,ko,de,fr,es,ru \
  --precompute-limit 50000 \
  --zh-script both
```

4. 一次跑完整流程（下载 + build + precompute）

```bash
python scripts/wiktextract_build.py \
  --stages all \
  --langs en,zh,ja,ko,de,fr,es,ru
```

### 关键参数

- `--stages`：`download,build,precompute`，可组合；`all` 代表全部
- `--langs`：只处理指定语言；省略则处理全部支持语言
- `--reset`：build 前清空 DB
- `--overwrite-download`：强制重下原始数据
- `--precompute-limit`：每个源语言最多预热多少词
- `--zh-script`：`hans` / `hant` / `both`（默认 `both`）
