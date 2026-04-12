# AI Tutor V2

本仓库按 `DESIGN_V2.md` 已搭建完整代码骨架。你要求“不自动执行安装”，因此下面只提供完整安装与部署步骤。

## 1. 环境准备（Conda）

```bash
conda create -y -n ai_tutor_v2 python=3.11
conda activate ai_tutor_v2
```

## 2. 安装项目依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```


## 3. 配置环境变量

在仓库根目录创建 `.env`：

```env
HOST=0.0.0.0
PORT=8080
FUNASR_WS_URL=ws://127.0.0.1:10095
ASR_FINAL_TIMEOUT_SECONDS=30
COSYVOICE_HTTP_URL=http://127.0.0.1:9880
COSYVOICE_CONNECT_TIMEOUT_SECONDS=10
COSYVOICE_READ_TIMEOUT_SECONDS=180
COSYVOICE_WRITE_TIMEOUT_SECONDS=60
COSYVOICE_POOL_TIMEOUT_SECONDS=60
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=claude-3-5-haiku-latest
LLM_API_BASE_URL=https://api.chatanywhere.tech
LLM_CHAT_PATH=/v1/chat/completions
LLM_TIMEOUT_SECONDS=120
DEFAULT_VOICE_ID=sarah_en
DEFAULT_LANGUAGE=en
PROFILE_DB_PATH=data/learner_profiles.db
LESSON_PLAN_DIR=data/lesson_plans
FILLER_DIR=data/fillers
```

## 4. 下载模型

### 4.1 FunASR 模型

```bash
python models/setup.py --skip-cosyvoice
```

### 4.2 CosyVoice2 模型

```bash
python models/setup.py --skip-funasr
```

上面的命令现在会同时做两件事（均使用默认路径）：
- 下载 CosyVoice2-0.5B 权重到 `models/assets/CosyVoice2-0.5B`
- 自动克隆 CosyVoice 代码到 `models/CosyVoice`

如果你想手动按官方仓库流程：

```bash
git clone https://github.com/FunAudioLLM/CosyVoice.git models/CosyVoice
cd models/CosyVoice
pip install -r requirements.txt
```

## 5. 准备声音克隆参考音频

将参考音频放到 `data/voices/`：

- `sarah_en.wav`
- `sarah_zh.wav`
- `kenji_ja.wav`

录音要求见 `data/voices/README.md`。

## 6. 启动模型服务

### 6.1 启动 FunASR WebSocket 服务

```bash
python models/funasr_server.py --port 10095 --device cuda:0
```

### 6.2 启动 CosyVoice HTTP 服务

```bash
python models/cosyvoice_server.py
```

默认监听 `http://0.0.0.0:9880`，并使用内置默认路径：
- 模型：`models/assets/CosyVoice2-0.5B`
- 代码：`models/CosyVoice`
- 参考音频：`data/voices`

## 7. 预合成 filler 音频

```bash
python -m voice.filler --voice-id sarah_en
```

会在 `data/fillers/{en,zh,ja}` 下生成 `.pcm` 文件。

## 8. 启动主服务（FastAPI + WebSocket）

```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

## 9. 前端接入

前端代码位于：

- `frontend/src/pages/AiTutor.vue`
- `frontend/src/composables/useVoiceChannel.js`
- `frontend/src/composables/useMicrophone.js`
- `frontend/src/composables/useAudioPlayback.js`
- `frontend/src/components/tutor/*`
- `static/audio-worklet-processor.js`

集成要求：

1. 确保前端静态资源可访问 `/audio-worklet-processor.js`。
2. 页面可连接 `ws://<host>/ws/tutor`。
3. 在路由中挂载 `AiTutor.vue`。

## 10. 端到端验证清单

1. 模型服务已启动：`10095` + `9880`。
2. 主服务已启动：`8080`。
3. 浏览器进入 `AiTutor` 页面后可授权麦克风。
4. 说话后可收到：
   - `state_change`
   - `transcript`
   - `teacher_text`
   - 二进制 PCM 音频回放。
5. 打断老师说话时收到 `stop_playback`。

## 11. 常见问题

- `NoWritableEnvsDirError`：需要在有权限的 conda 目录创建环境。
- `externally-managed-environment`：不要用系统 Python 直装，使用 conda/venv。
- `Could not resolve host / proxy`：检查 `git` 与系统代理设置。
- `Using SOCKS proxy, but the 'socksio' package is not installed`：重新执行 `pip install -r requirements.txt`，确保 `socksio` 已安装。
- `No module named 'cosyvoice'`：优先执行 `python models/setup.py --skip-funasr`，该命令会按默认路径自动下载权重并克隆 `models/CosyVoice` 代码。
- `ANTHROPIC_API_KEY` 未配置时：代码会使用 fallback 回复，不能代表真实教学质量。

## 12. 当前代码结构

- `server.py`：WebSocket 会话入口
- `voice/*`：全双工语音管道、VAD、ASR/TTS 客户端、filler、打断
- `session/*`：两层记忆、prompt 构建、阶段推进、SQLite profile
- `llm/*`：Claude streaming 客户端与结构化输出解析
- `models/*`：模型下载与服务启动脚本
- `frontend/*`：课堂 UI 与音频通道
