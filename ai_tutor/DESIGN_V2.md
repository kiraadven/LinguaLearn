# AI Tutor V2 — 全双工自研语音课堂架构

> 本文档是 REDESIGN_PLAN.md 的升级版。
> 核心变更：**除 Claude LLM API 外，全部自建/自部署**。
> 全双工语音通道自研，课程架构全面简化。

---

## 一、架构总览

### 1.1 设计原则

1. **LLM 是大脑** — 所有教学决策由 LLM 通过 system prompt 完成，无需外部 PolicyRuntime/GraphMutator
2. **语音管道是身体** — 全自部署的 ASR + TTS + VAD，通过 WebSocket 实现全双工
3. **极简状态** — 只保留两层记忆（session context + learner profile），直接注入 prompt
4. **延迟为王** — 所有设计决策优先考虑端到端延迟，目标 < 500ms 感知延迟

### 1.2 技术栈

| 组件 | 方案 | 许可证 | 延迟 |
|------|------|--------|------|
| **VAD** | Silero VAD v5 | MIT | <1ms/chunk |
| **ASR** | FunASR Paraformer (streaming 2pass) | Apache 2.0 | ~200ms final |
| **LLM** | Claude Haiku 4.5 (streaming, prompt cached) | API | ~300-500ms first token |
| **TTS** | CosyVoice 2 (0.5B, streaming) | Apache 2.0 | ~150ms first chunk |
| **传输** | WebSocket (binary audio + JSON control) | — | ~5ms |
| **前端** | Vue 3 + Web Audio API + AudioWorklet | — | — |

### 1.3 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      BROWSER (Vue 3)                            │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │ Microphone   │   │ AudioWorklet │   │ Classroom UI         │ │
│  │ MediaStream  │──→│ (16kHz PCM)  │   │ - Transcript panel   │ │
│  └─────────────┘   └──────┬───────┘   │ - Phase indicator    │ │
│                            │           │ - Lesson progress    │ │
│  ┌─────────────┐   ┌──────▼───────┐   │ - Vocab tracker      │ │
│  │ Speaker     │◄──│ Audio Queue  │   └──────────────────────┘ │
│  │ Playback    │   │ (PCM buffer) │                             │
│  └─────────────┘   └──────▲───────┘                             │
│                            │                                     │
│         WebSocket (binary audio frames + JSON messages)         │
└────────────────────────────┼─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                VOICE PIPELINE SERVER (Python, asyncio)           │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                FULL-DUPLEX AUDIO ROUTER                    │  │
│  │                                                            │  │
│  │  Student PCM ──→ Silero VAD ──→ ┬── speech_start ──────┐ │  │
│  │       in            (<1ms)      │                       │ │  │
│  │                                 ├── speech_end ─────────┤ │  │
│  │                                 │                       │ │  │
│  │                                 └── is_speaking ────────┤ │  │
│  │                                      (continuous)       │ │  │
│  │                                                         ▼ │  │
│  │  ┌──────────────────────────────────────────────────────┐│  │
│  │  │           INTERRUPTION CONTROLLER                    ││  │
│  │  │                                                      ││  │
│  │  │  IF student_speaking AND teacher_playing:            ││  │
│  │  │    → stop TTS playback immediately                   ││  │
│  │  │    → cancel pending LLM generation                   ││  │
│  │  │    → switch to LISTENING state                       ││  │
│  │  │                                                      ││  │
│  │  │  IF student_speaking AND NOT teacher_playing:        ││  │
│  │  │    → normal LISTENING state                          ││  │
│  │  │    → after 2s+ of student speech, inject backchannel ││  │
│  │  └──────────────────────────────────────────────────────┘│  │
│  │                                                           │  │
│  │  speech_end ──→ FunASR (streaming) ──→ final_transcript  │  │
│  │                                              │            │  │
│  │                            ┌──────────────── │ ───────┐   │  │
│  │                            ▼                 ▼        │   │  │
│  │                    Filler Generator    Session Manager │   │  │
│  │                    (instant, <10ms)    (build prompt)  │   │  │
│  │                         │                    │        │   │  │
│  │                         ▼                    ▼        │   │  │
│  │                    Pre-synth audio    Claude LLM      │   │  │
│  │                    "Hmm..."          (streaming)      │   │  │
│  │                    "嗯..."              │             │   │  │
│  │                         │               ▼             │   │  │
│  │                         │         CosyVoice 2        │   │  │
│  │                         │         (streaming TTS)     │   │  │
│  │                         │               │             │   │  │
│  │                         ▼               ▼             │   │  │
│  │                    ┌─ Audio Mixer ◄─────┘             │   │  │
│  │                    │  (filler first, then real audio)  │   │  │
│  │                    └──────────┬───────────────────────┘   │  │
│  │                               │                           │  │
│  └───────────────────────────────┼───────────────────────────┘  │
│                                  ▼                               │
│                        WebSocket → Browser                       │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              SESSION MANAGER (Simplified)                  │  │
│  │                                                            │  │
│  │  - Builds LLM system prompt from:                         │  │
│  │    - Persona definition (natural language)                │  │
│  │    - Teaching guidelines (natural language)                │  │
│  │    - Current phase + lesson focus                         │  │
│  │    - Student profile (level, L1, frequent errors)         │  │
│  │    - Recent 5-8 turns of conversation                     │  │
│  │    - Vocab recycling list                                 │  │
│  │    - Energy arc hint                                      │  │
│  │                                                            │  │
│  │  - Parses LLM structured output:                          │  │
│  │    {"text": "...", "action": "recast", "phase": "teach"}  │  │
│  │                                                            │  │
│  │  - Updates session state (phase, covered skills, errors)  │  │
│  │  - Persists learner profile to SQLite after session       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              MODEL SERVERS (GPU, separate processes)       │  │
│  │                                                            │  │
│  │  Process 1: FunASR Server (WebSocket :10095)              │  │
│  │    - Paraformer-zh + Paraformer-en (2pass streaming)      │  │
│  │    - Silero VAD integrated (or separate)                  │  │
│  │                                                            │  │
│  │  Process 2: CosyVoice 2 Server (HTTP :9880)              │  │
│  │    - Streaming synthesis endpoint                         │  │
│  │    - Voice cloning loaded at startup                      │  │
│  │    - LightTTS wrapper for optimized inference             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、全双工语音通道详细设计

### 2.1 状态机

```
                    ┌─────────────┐
                    │   IDLE      │
                    │  (等待学生)  │
                    └──────┬──────┘
                           │ VAD: speech_start
                           ▼
                    ┌─────────────┐
         ┌────────→│  LISTENING   │◄────────────────────┐
         │         │  (学生说话)  │                      │
         │         └──────┬──────┘                      │
         │                │ VAD: speech_end              │
         │                ▼                              │
         │         ┌─────────────┐                      │
         │         │  PROCESSING  │                      │
         │         │  (ASR→LLM)  │                      │
         │         └──────┬──────┘                      │
         │                │ first audio chunk ready      │
         │                ▼                              │
         │         ┌─────────────┐   VAD: speech_start  │
         │         │  SPEAKING    │──────────────────────┘
         │         │  (老师说话)  │   (student interrupts)
         │         └──────┬──────┘
         │                │ TTS playback complete
         └────────────────┘
```

### 2.2 音频帧协议

Browser ↔ Server 通过单个 WebSocket 连接传输两种消息：

**Binary 消息（音频帧）：**
```
方向: client → server
格式: 16-bit PCM, 16kHz, mono
帧大小: 512 samples (32ms) — 与 Silero VAD 要求一致
每帧字节: 1024 bytes

方向: server → client  
格式: 16-bit PCM, 24kHz, mono (CosyVoice 2 输出采样率)
帧大小: streaming chunks (variable, ~100-500ms per chunk)
```

**JSON 消息（控制信令）：**
```json
// server → client
{"type": "state_change", "state": "listening|processing|speaking"}
{"type": "transcript", "text": "学生说的话", "is_final": true}
{"type": "teacher_text", "text": "老师说的话", "action": "recast"}
{"type": "phase_change", "phase": "teach", "focus": "present perfect"}
{"type": "session_end", "summary": {...}}

// client → server
{"type": "session_start", "lesson_id": "...", "learner_id": "..."}
{"type": "session_end"}
{"type": "text_input", "text": "..."} // 可选文字输入模式
```

### 2.3 延迟隐藏策略

**目标：感知延迟 < 500ms（学生说完到听到老师有意义的回应）**

实际管道延迟（最优情况）：
```
VAD speech_end detection:    ~60ms  (Silero 需要2-3帧确认)
ASR final transcript:        ~200ms (FunASR 2pass final correction)
Filler generation:           ~0ms   (pre-synthesized, instant)
LLM first token:             ~300ms (Haiku streaming, prompt cached)
LLM first sentence complete: ~500ms (average ~15 tokens)
TTS first audio chunk:       ~150ms (CosyVoice 2 streaming)
───────────────────────────────────
Total without filler:        ~910ms
Total with filler:           ~60ms (filler plays instantly after speech_end)
                             真实回应在 ~650ms 后无缝接入
```

**策略 1: Filler 即时播放**

当 VAD 检测到 speech_end：
1. 立即从 filler pool 选一个合适的 filler 发送给客户端播放
2. 同时异步处理 ASR → LLM → TTS
3. 当 TTS 第一个 chunk 准备好时，filler 已播放完毕，无缝衔接

```python
FILLER_POOL = {
    "acknowledgment": ["嗯...", "Hmm...", "Well...", "So..."],
    "thinking": ["Let me think...", "让我想想...", "Ah..."],
    "positive": ["Oh!", "Right!", "嗯嗯!"],
}
# 每个 filler 预先用 CosyVoice 合成好，存为 PCM 文件
# 运行时直接读文件发送，延迟 ~0ms
```

**策略 2: 预测性快速回应**

对常见模式直接跳过 LLM，用预合成的音频：
```python
FAST_RESPONSES = {
    "correct_simple": ["Good!", "That's right!", "Exactly!", "很好!"],
    "encourage_retry": ["Almost!", "Try again!", "差一点!"],
    "greeting": ["Hi there!", "Hello!", "你好!"],
}
# 由 Session Manager 的简单规则判断是否触发
# 例如：学生回答完全正确 + 答案很短 → 直接播放 "Good!"
```

**策略 3: 流式 TTS 管道**

不等 LLM 生成完整文本，逐句合成：
```
LLM output token stream: "Oh, | you went | to Paris? | Actually, | we'd say..."
                          ↓
Sentence detector: 检测到 "Oh, you went to Paris?" 是完整句
                          ↓
CosyVoice 2: 开始合成第一句（同时 LLM 继续生成后续）
                          ↓
Audio chunk → WebSocket → Browser playback
```

**策略 4: Backchannel 注入**

学生说话超过 2 秒时，在自然停顿处注入 backchannel：
```python
async def backchannel_monitor(vad_stream):
    student_speaking_duration = 0
    while True:
        frame = await vad_stream.get()
        if frame.is_speech:
            student_speaking_duration += frame.duration
        else:
            # 检测到短暂停顿
            if student_speaking_duration > 2.0 and frame.silence_duration > 0.3:
                await send_backchannel("嗯嗯")  # pre-synth audio
                student_speaking_duration = 0
```

### 2.4 打断处理

```python
class InterruptionController:
    """
    当学生在老师说话时开口，需要：
    1. 立即停止发送 TTS 音频给客户端
    2. 给客户端发送 stop_playback 指令
    3. 取消正在进行的 LLM 生成
    4. 切换到 LISTENING 状态
    5. 将老师被打断时已说出的内容记入上下文
    """

    async def on_vad_speech_start(self):
        if self.state == State.SPEAKING:
            # 1. 停止 TTS 输出
            self.tts_task.cancel()

            # 2. 通知客户端停止播放
            await self.ws.send_json({
                "type": "stop_playback"
            })

            # 3. 记录已说出的部分
            spoken_text = self.current_utterance[:self.spoken_char_index]
            self.session.add_partial_teacher_turn(spoken_text)

            # 4. 取消 LLM 生成
            if self.llm_task and not self.llm_task.done():
                self.llm_task.cancel()

            # 5. 切换状态
            self.state = State.LISTENING
```

### 2.5 回声消除（AEC）

在浏览器端：
```javascript
const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
        echoCancellation: true,      // 浏览器内置 AEC
        noiseSuppression: true,      // 噪音抑制
        autoGainControl: true,       // 自动增益
        sampleRate: 16000,
        channelCount: 1,
    }
});
```

关键：老师的音频通过 `<audio>` 元素或 AudioContext 播放（不是通过 WebRTC），
浏览器的 AEC 会自动将扬声器播放的内容从麦克风输入中减去。

如果浏览器 AEC 不够好（某些设备/浏览器），备选方案：
- 在 server 端使用 speexdsp 的 AEC
- 或在 teacher speaking 时关闭 VAD 检测（半双工降级）

---

## 三、课程架构全面简化

### 3.1 删除的组件

| 组件 | 原位置 | 删除原因 |
|------|--------|----------|
| GraphEngine | `graph/graph_engine.py` | NetworkX 状态机过度设计，教学决策应由 LLM 完成 |
| GraphAssembler | `graph/graph_assembler.py` | 同上 |
| GraphMutator | `graph/graph_mutator.py` | 动态子图插入增加延迟且不可解释 |
| SubgraphFactory | `graph/subgraph_factory.py` | 同上 |
| EdgeWeights | `graph/edge_weights.py` | 伪精确的权重算术 |
| NodeTemplates | `graph/node_templates.py` | 40+ YAML 模板，LLM prompt 能做同样的事 |
| PolicyRuntime | `runtime/policy_runtime.py` | if-else 规则链导致机械感，合并进 LLM prompt |
| AssessmentEngine | `runtime/assessment.py` | LLM 内联评估学生输入，无需独立引擎 |
| 4-layer Memory | `runtime/memory.py` | 简化为 2 层，直接注入 prompt |
| VoiceModelInput (30+字段) | `graph/schema.py` | 已否定的端到端架构产物 |
| VoiceDispatcher | `voice/dispatcher.py` | 新的 AudioRouter 替代 |
| PersonaManager (7 floats) | `voice/persona.py` | persona 用自然语言描述，放在 prompt 里 |
| WS Protocol (graph_diff) | `graph/ws_protocol.py` | 不再广播图状态，改为简单的音频+控制消息 |
| ContentConnector | `graph/content_connector.py` | 内容直接在 prompt 里描述 |
| ContentPrefetcher | — | 不需要预获取，LLM 即时生成 |
| skill_matrix_templates.yaml | `graph/templates/` | 所有模板目录删除 |

### 3.2 新的目录结构

```
ai_tutor/
├── server.py                    # FastAPI + WebSocket 主服务
├── config.py                    # 配置（模型路径、端口、API key）
│
├── voice/                       # 语音管道（全双工核心）
│   ├── audio_router.py          # 全双工音频路由 + 状态机
│   ├── vad.py                   # Silero VAD 封装
│   ├── asr_client.py            # FunASR WebSocket 客户端
│   ├── tts_client.py            # CosyVoice 2 streaming 客户端
│   ├── filler.py                # Filler 池管理 + 预合成
│   ├── interruption.py          # 打断控制器
│   └── audio_mixer.py           # 音频混合（filler → real audio）
│
├── session/                     # 会话管理（极简）
│   ├── manager.py               # Session 生命周期 + prompt 构建
│   ├── prompt_builder.py        # LLM system prompt 模板
│   ├── learner_profile.py       # 学习者档案（SQLite 持久化）
│   └── lesson_plan.py           # 课程计划（简单 JSON）
│
├── llm/                         # LLM 交互
│   ├── client.py                # Claude API streaming 客户端
│   ├── response_parser.py       # 解析 LLM 结构化输出
│   └── prompts/                 # System prompt 模板
│       ├── persona_sarah.md     # Sarah 老师人设
│       ├── persona_kenji.md     # Kenji 老师人设（日语）
│       ├── teaching_rules.md    # 通用教学规则
│       └── phase_rules.md       # 各阶段特定规则
│
├── models/                      # 本地模型管理
│   ├── setup.py                 # 下载 + 初始化模型
│   ├── funasr_server.py         # FunASR 服务启动脚本
│   └── cosyvoice_server.py      # CosyVoice 服务启动脚本
│
├── data/
│   ├── fillers/                 # 预合成的 filler 音频 (PCM)
│   │   ├── en/                  # 英语 fillers
│   │   ├── zh/                  # 中文 fillers
│   │   └── ja/                  # 日语 fillers
│   ├── voices/                  # 声音克隆参考音频
│   └── learner_profiles.db      # SQLite 学习者档案
│
└── frontend/                    # 前端组件（集成到现有 Vue 项目）
    └── src/
        ├── pages/AiTutor.vue           # 主课堂页面
        ├── composables/
        │   ├── useVoiceChannel.js       # WebSocket 音频通道
        │   ├── useAudioPlayback.js      # 音频播放队列
        │   └── useMicrophone.js         # 麦克风采集 + AudioWorklet
        └── components/tutor/
            ├── ClassroomView.vue        # 课堂主视图
            ├── TranscriptPanel.vue      # 实时字幕面板
            ├── LessonProgress.vue       # 课程进度
            └── VoiceIndicator.vue       # 语音状态指示器
```

### 3.3 教学阶段（替代原 19 种节点类型）

只保留 **4 个阶段**，由 LLM 自行决定转换：

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ OPENING  │──→│  TEACH   │◄─→│ PRACTICE │──→│ CLOSING  │
│ (2-3min) │   │ (混合)   │   │ (自由)    │   │ (2-3min) │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                 ↑                 │
                 └─── 如果需要 ────┘
```

| 阶段 | 老师行为 | 学生行为 | 持续时间 |
|------|---------|---------|---------|
| **opening** | 问候、暖场、简单对话、引出今天的主题 | 回应、简单聊天 | 2-3 min |
| **teach** | 讲解 + 引导练习 + 理解检查（混合） | 听、回答、模仿、尝试 | 10-15 min |
| **practice** | 最少干预，只在需要时 recast | 自由对话、角色扮演 | 10-15 min |
| **closing** | 总结今天内容、预告下次、告别 | 回顾、提问 | 2-3 min |

**阶段转换**由 LLM 自行决定：
```json
// LLM 每次回复的结构化输出
{
    "text": "Oh, you've been to Paris? That's so cool! ...",
    "action": "recast",          // recast|explain|encourage|check|practice_prompt|advance|closing
    "phase": "teach",            // opening|teach|practice|closing — LLM 可以建议切换
    "vocab_used": ["nevertheless"],  // 本轮使用了哪些目标词汇
    "error_noted": "simple_past_instead_of_present_perfect"  // 或 null
}
```

### 3.4 System Prompt 设计

```markdown
# [PERSONA]
你是 Sarah，一位28岁的美国英语老师，在上海教英语5年了。
性格：温和、有耐心、偶尔幽默，喜欢用日常生活话题教学。
口头禅：
- 学生说对了："Exactly!" "That's it!" "Nice one!"
- 思考时："Hmm..." "Well..." "Let me think..."
- 惊讶时："Oh!" "Wait, really?" "No way!"
- 鼓励时："Almost there!" "You're so close!"
你说话不完美——偶尔重新组织语言，用缩写（gonna, wanna），有自然停顿。
你绝不说 "Good job!" 这种教科书式的夸奖。

# [TEACHING GUIDELINES]
你的教学风格基于以下原则：
1. i+1 策略：你说的话比学生水平略高一点点，不超过一个等级
2. Recast 优先：学生语法错但意思对时，你自然地把正确形式用进你的回应，不指出错误
   例：学生 "I goed to park" → 你 "Oh you went to the park? Nice! What did you do there?"
3. 只有学生连续 3 次犯同一个错误时，才直接纠正
4. 每次回复 2-3 句话，不要太长
5. 确保学生说话时间 > 你说话时间（多提问，少讲解）
6. 可以用一句中文解释复杂语法，但立刻用英文重复
7. 自然地回顾之前教过的词汇

# [CURRENT LESSON]
- 阶段：{phase}
- 本节重点：{lesson_focus}（例：present perfect tense）
- 已覆盖内容：{covered_topics}
- 本节已引入词汇：{vocab_list_with_usage_count}
- 课程已进行：{elapsed_minutes} 分钟 / 共 {total_minutes} 分钟

# [STUDENT PROFILE]
- 姓名：{name}
- 水平：{level}（A1-C2）
- 母语：{l1}
- 高频错误：{frequent_errors}
- 学习偏好：{preferences}
- 上次课内容：{last_lesson_summary}

# [RECENT CONVERSATION]
{last_5_8_turns}

# [ENERGY ARC]
{energy_hint}
（例：课程已进行高强度练习15分钟，建议放松节奏。或：学生刚答对3题，可以推进难度。）

# [RULES]
- 每次回复必须包含一个 JSON 标记（放在回复最后，用 ```json 包裹）：
  {"action": "...", "phase": "...", "vocab_used": [...], "error_noted": "..."}
- action 必须是以下之一：
  recast — 自然重述正确形式
  explain — 讲解新知识点
  encourage — 鼓励
  check — 检查理解（提问）
  practice_prompt — 给练习题目
  advance — 推进到下一个知识点
  closing — 开始结束课程
- 如果你认为应该切换阶段，在 phase 字段中写新阶段名
- 不要输出你的思考过程，只输出老师会说的话
```

### 3.5 两层记忆系统

**Layer 1: Session Context（内存，单次课程）**

```python
@dataclass
class SessionContext:
    # 基本信息
    lesson_id: str
    learner_id: str
    start_time: datetime
    target_language: str      # en, zh, ja, ko, ...
    lesson_focus: str         # "present perfect tense"
    total_minutes: int        # 30

    # 动态状态
    current_phase: str        # opening|teach|practice|closing
    turns: list[Turn]         # 最近 5-8 轮对话
    covered_topics: list[str] # 本节已覆盖的知识点
    vocab_introduced: dict    # {"word": {"turn": 5, "uses": 2}}
    errors_this_session: list # [{error, turn, corrected}]
    energy_level: float       # 0-1, 通过连续正确/错误推断

    def to_prompt_context(self) -> str:
        """序列化为 system prompt 的 [CURRENT LESSON] 部分"""
        ...
```

**Layer 2: Learner Profile（SQLite，跨课程持久化）**

```python
@dataclass
class LearnerProfile:
    learner_id: str
    name: str
    level: str                    # A1-C2
    l1: str                       # 母语
    target_language: str
    frequent_errors: list[str]    # 高频错误模式
    mastery: dict                 # {"present_perfect": 0.7, "articles": 0.3}
    preferences: dict             # {"pace": "slow", "likes_humor": true}
    total_sessions: int
    last_session_summary: str     # 上次课的简要总结
    last_session_date: str

    def to_prompt_context(self) -> str:
        """序列化为 system prompt 的 [STUDENT PROFILE] 部分"""
        ...
```

课后更新流程：
```python
async def end_session(session: SessionContext, profile: LearnerProfile):
    # 让 LLM 总结本次课程
    summary = await llm.summarize_session(session.turns, session.errors_this_session)

    # 更新 learner profile
    profile.last_session_summary = summary
    profile.total_sessions += 1
    for error in session.errors_this_session:
        if error.pattern not in profile.frequent_errors:
            profile.frequent_errors.append(error.pattern)

    # 更新 mastery
    for topic in session.covered_topics:
        correct_rate = calculate_correct_rate(session, topic)
        old = profile.mastery.get(topic, 0.0)
        profile.mastery[topic] = old * 0.7 + correct_rate * 0.3  # 指数移动平均

    # 持久化
    await db.save_profile(profile)
```

---

## 四、核心组件实现规格

### 4.1 Voice Pipeline Server (`server.py`)

```python
# FastAPI + WebSocket

from fastapi import FastAPI, WebSocket
import asyncio

app = FastAPI()

@app.websocket("/ws/tutor")
async def tutor_session(ws: WebSocket):
    await ws.accept()

    # 初始化组件
    session_config = await ws.receive_json()  # {lesson_id, learner_id}
    session = SessionManager(session_config)
    audio_router = AudioRouter(ws, session)

    # 启动并行任务
    tasks = [
        asyncio.create_task(audio_router.receive_loop()),   # 接收学生音频
        asyncio.create_task(audio_router.process_loop()),    # 处理管道
        asyncio.create_task(audio_router.send_loop()),       # 发送老师音频
        asyncio.create_task(session.auto_advance_loop()),    # 自动推进（沉默检测）
    ]

    try:
        await asyncio.gather(*tasks)
    except Exception:
        for t in tasks:
            t.cancel()
    finally:
        await session.end()
```

### 4.2 AudioRouter (`voice/audio_router.py`)

```python
class AudioRouter:
    """全双工音频路由核心"""

    def __init__(self, ws, session):
        self.ws = ws
        self.session = session
        self.state = State.IDLE
        self.vad = SileroVAD()
        self.asr = FunASRClient("ws://localhost:10095")
        self.tts = CosyVoiceClient("http://localhost:9880")
        self.filler = FillerPool()
        self.interruption = InterruptionController()

        # 异步队列
        self.incoming_audio = asyncio.Queue()    # 学生 PCM 帧
        self.outgoing_audio = asyncio.Queue()    # 老师 PCM 帧
        self.pending_transcript = asyncio.Event()

    async def receive_loop(self):
        """接收浏览器发来的音频帧"""
        while True:
            data = await self.ws.receive_bytes()
            await self.incoming_audio.put(data)

    async def process_loop(self):
        """主处理循环：VAD → ASR → LLM → TTS"""
        speech_buffer = bytearray()
        is_speaking = False

        while True:
            frame = await self.incoming_audio.get()

            # VAD 检测
            vad_result = self.vad.process(frame)

            if vad_result.is_speech and not is_speaking:
                # === SPEECH START ===
                is_speaking = True
                speech_buffer.clear()

                # 如果老师正在说话，触发打断
                if self.state == State.SPEAKING:
                    await self.interruption.handle(self)

                self.state = State.LISTENING
                await self.ws.send_json({"type": "state_change", "state": "listening"})

                # 开始流式 ASR
                await self.asr.start_stream()

            if is_speaking:
                speech_buffer.extend(frame)
                await self.asr.feed_chunk(frame)

                # Backchannel: 学生说话超过 2s 且有短暂停顿
                if len(speech_buffer) > 32000 and not vad_result.is_speech:
                    await self._inject_backchannel()

            if not vad_result.is_speech and is_speaking:
                # 需要多帧确认确实停止说话（避免误判）
                # Silero VAD 内置 min_silence_duration_ms
                is_speaking = False

                # === SPEECH END ===
                self.state = State.PROCESSING
                await self.ws.send_json({"type": "state_change", "state": "processing"})

                # 1. 立即播放 filler
                filler_audio = self.filler.get_random(self.session.language)
                await self.outgoing_audio.put(filler_audio)

                # 2. 获取 ASR 最终结果
                transcript = await self.asr.get_final()
                await self.ws.send_json({
                    "type": "transcript",
                    "text": transcript,
                    "is_final": True
                })

                # 3. LLM 生成 + 流式 TTS
                await self._generate_response(transcript)

    async def _generate_response(self, student_text: str):
        """LLM streaming → TTS streaming → audio output"""
        self.state = State.SPEAKING
        await self.ws.send_json({"type": "state_change", "state": "speaking"})

        # 构建 prompt
        prompt = self.session.build_prompt(student_text)

        # LLM streaming
        sentence_buffer = ""
        full_response = ""

        async for token in self.session.llm.stream(prompt):
            sentence_buffer += token
            full_response += token

            # 检测完整句子
            if self._is_sentence_end(sentence_buffer):
                # 流式 TTS：逐句合成
                async for audio_chunk in self.tts.stream_synthesize(
                    text=sentence_buffer,
                    voice_id=self.session.voice_id,
                ):
                    await self.outgoing_audio.put(audio_chunk)

                sentence_buffer = ""

        # 处理剩余文本
        if sentence_buffer.strip():
            async for audio_chunk in self.tts.stream_synthesize(sentence_buffer):
                await self.outgoing_audio.put(audio_chunk)

        # 解析 LLM 结构化输出
        parsed = self.session.parse_response(full_response)
        await self.ws.send_json({
            "type": "teacher_text",
            "text": parsed["text"],
            "action": parsed["action"],
        })

        # 更新 session 状态
        self.session.update(student_text, parsed)

        self.state = State.IDLE

    async def send_loop(self):
        """发送音频帧到浏览器"""
        while True:
            audio_data = await self.outgoing_audio.get()
            await self.ws.send_bytes(audio_data)
```

### 4.3 FunASR Client (`voice/asr_client.py`)

```python
import websockets
import json

class FunASRClient:
    """FunASR WebSocket 流式 ASR 客户端"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.ws = None

    async def start_stream(self):
        """开始一次新的识别会话"""
        self.ws = await websockets.connect(self.server_url)
        # 发送配置
        await self.ws.send(json.dumps({
            "mode": "2pass",  # 先给快速结果，再给精确结果
            "chunk_size": [5, 10, 5],
            "wav_name": "realtime",
            "is_speaking": True,
            "wav_format": "pcm",
            "audio_fs": 16000,
        }))

    async def feed_chunk(self, pcm_data: bytes):
        """喂入音频帧"""
        if self.ws:
            await self.ws.send(pcm_data)

    async def get_final(self) -> str:
        """通知结束并获取最终结果"""
        if not self.ws:
            return ""

        # 发送结束信号
        await self.ws.send(json.dumps({"is_speaking": False}))

        # 等待最终结果
        final_text = ""
        async for msg in self.ws:
            result = json.loads(msg)
            if result.get("is_final"):
                final_text = result.get("text", "")
                break

        await self.ws.close()
        self.ws = None
        return final_text
```

### 4.4 CosyVoice Client (`voice/tts_client.py`)

```python
import httpx
import asyncio

class CosyVoiceClient:
    """CosyVoice 2 流式 TTS 客户端"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def stream_synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """
        流式合成语音。
        yield PCM audio chunks (24kHz, 16bit, mono)
        """
        async with self.client.stream(
            "POST",
            f"{self.server_url}/api/tts/stream",
            json={
                "text": text,
                "voice_id": voice_id,
                "speed": speed,
                "format": "pcm",
                "sample_rate": 24000,
            },
        ) as response:
            async for chunk in response.aiter_bytes(chunk_size=4800):
                # 4800 bytes = 100ms of 24kHz 16-bit mono audio
                yield chunk

    async def synthesize_to_file(self, text: str, output_path: str, voice_id: str = "default"):
        """合成完整音频到文件（用于预合成 filler）"""
        response = await self.client.post(
            f"{self.server_url}/api/tts",
            json={
                "text": text,
                "voice_id": voice_id,
                "format": "wav",
                "sample_rate": 24000,
            },
        )
        with open(output_path, "wb") as f:
            f.write(response.content)
```

### 4.5 前端音频通道 (`useVoiceChannel.js`)

```javascript
// composables/useVoiceChannel.js
import { ref, onUnmounted } from 'vue'

export function useVoiceChannel() {
    const state = ref('idle')          // idle|listening|processing|speaking
    const transcript = ref('')         // 实时转写文本
    const teacherText = ref('')        // 老师说的文本
    const connected = ref(false)

    let ws = null
    let audioContext = null
    let mediaStream = null
    let workletNode = null
    let playbackQueue = []
    let isPlaying = false

    async function connect(lessonId, learnerId) {
        // 1. 获取麦克风
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                sampleRate: 16000,
                channelCount: 1,
            }
        })

        // 2. 创建 AudioContext
        audioContext = new AudioContext({ sampleRate: 24000 })  // 播放采样率

        // 3. 创建 AudioWorklet 用于采集 PCM
        await audioContext.audioWorklet.addModule('/audio-worklet-processor.js')
        const source = audioContext.createMediaStreamSource(mediaStream)
        workletNode = new AudioWorkletNode(audioContext, 'pcm-capture-processor')
        source.connect(workletNode)

        // 4. 连接 WebSocket
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
        ws = new WebSocket(`${protocol}//${location.host}/ws/tutor`)
        ws.binaryType = 'arraybuffer'

        ws.onopen = () => {
            connected.value = true
            ws.send(JSON.stringify({
                type: 'session_start',
                lesson_id: lessonId,
                learner_id: learnerId,
            }))
        }

        // 5. 发送麦克风 PCM 到服务器
        workletNode.port.onmessage = (event) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(event.data)  // Int16Array as binary
            }
        }

        // 6. 接收服务器消息
        ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                // 音频帧 → 放入播放队列
                playbackQueue.push(event.data)
                if (!isPlaying) playNext()
            } else {
                // JSON 控制消息
                const msg = JSON.parse(event.data)
                handleMessage(msg)
            }
        }
    }

    function handleMessage(msg) {
        switch (msg.type) {
            case 'state_change':
                state.value = msg.state
                break
            case 'transcript':
                transcript.value = msg.text
                break
            case 'teacher_text':
                teacherText.value = msg.text
                break
            case 'stop_playback':
                // 学生打断了老师 → 停止播放
                playbackQueue = []
                isPlaying = false
                break
            case 'phase_change':
                // 阶段切换
                break
        }
    }

    async function playNext() {
        if (playbackQueue.length === 0) {
            isPlaying = false
            return
        }
        isPlaying = true
        const buffer = playbackQueue.shift()

        // 将 PCM 转为 AudioBuffer
        const pcm16 = new Int16Array(buffer)
        const audioBuffer = audioContext.createBuffer(1, pcm16.length, 24000)
        const channelData = audioBuffer.getChannelData(0)
        for (let i = 0; i < pcm16.length; i++) {
            channelData[i] = pcm16[i] / 32768.0
        }

        const source = audioContext.createBufferSource()
        source.buffer = audioBuffer
        source.connect(audioContext.destination)
        source.onended = playNext
        source.start()
    }

    function disconnect() {
        if (ws) ws.close()
        if (mediaStream) mediaStream.getTracks().forEach(t => t.stop())
        if (audioContext) audioContext.close()
        connected.value = false
    }

    onUnmounted(disconnect)

    return {
        state,
        transcript,
        teacherText,
        connected,
        connect,
        disconnect,
    }
}
```

### 4.6 AudioWorklet Processor (`static/audio-worklet-processor.js`)

```javascript
class PCMCaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super()
        this.buffer = new Float32Array(512)  // 32ms at 16kHz
        this.bufferIndex = 0
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0]
        if (!input || !input[0]) return true

        const inputChannel = input[0]

        for (let i = 0; i < inputChannel.length; i++) {
            this.buffer[this.bufferIndex++] = inputChannel[i]

            if (this.bufferIndex >= 512) {
                // 转换为 16-bit PCM
                const pcm16 = new Int16Array(512)
                for (let j = 0; j < 512; j++) {
                    pcm16[j] = Math.max(-32768, Math.min(32767,
                        Math.round(this.buffer[j] * 32768)))
                }
                this.port.postMessage(pcm16.buffer, [pcm16.buffer])
                this.buffer = new Float32Array(512)
                this.bufferIndex = 0
            }
        }

        return true
    }
}

registerProcessor('pcm-capture-processor', PCMCaptureProcessor)
```

---

## 五、模型部署

### 5.1 FunASR 部署

```bash
# 安装
pip install funasr modelscope

# 下载模型
python -c "
from modelscope import snapshot_download
snapshot_download('iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch', local_dir='models/funasr')
"

# 启动 WebSocket 服务
cd ai_tutor/models
python funasr_server.py --port 10095 --device cuda:0
```

**funasr_server.py:**
```python
"""FunASR WebSocket Server 启动脚本"""
import argparse
from funasr import AutoModel

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=10095)
    parser.add_argument("--device", type=str, default="cuda:0")
    args = parser.parse_args()

    # 加载模型
    model = AutoModel(
        model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device=args.device,
    )

    # 启动 WebSocket 服务
    # 使用 FunASR 自带的 WebSocket server
    from funasr.runtime.python.websocket import funasr_wss_server
    funasr_wss_server.start(
        port=args.port,
        asr_model=model,
    )

if __name__ == "__main__":
    main()
```

### 5.2 CosyVoice 2 部署

```bash
# 克隆仓库
git clone https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice

# 安装依赖
pip install -r requirements.txt

# 下载模型
python -c "
from huggingface_hub import snapshot_download
snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')
"
```

**cosyvoice_server.py:**
```python
"""CosyVoice 2 Streaming HTTP Server"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import torch
import torchaudio
import io

app = FastAPI()

# 全局加载模型
cosyvoice_model = None

class TTSRequest(BaseModel):
    text: str
    voice_id: str = "default"
    speed: float = 1.0
    format: str = "pcm"          # pcm | wav
    sample_rate: int = 24000

@app.on_event("startup")
async def load_model():
    global cosyvoice_model
    from cosyvoice.cli.cosyvoice import CosyVoice2
    cosyvoice_model = CosyVoice2(
        "pretrained_models/CosyVoice2-0.5B",
        load_jit=True,
        load_trt=False,
    )

@app.post("/api/tts/stream")
async def stream_tts(req: TTSRequest):
    """流式 TTS — 逐 chunk 返回 PCM 音频"""
    async def generate():
        # 使用 zero-shot voice cloning
        prompt_speech = f"data/voices/{req.voice_id}.wav"

        for chunk in cosyvoice_model.inference_zero_shot(
            tts_text=req.text,
            prompt_text="",  # 可选 prompt text
            prompt_speech_16k=prompt_speech,
            stream=True,
            speed=req.speed,
        ):
            audio = chunk["tts_speech"]
            # 转换为 16-bit PCM bytes
            pcm_bytes = (audio * 32768).to(torch.int16).numpy().tobytes()
            yield pcm_bytes

    return StreamingResponse(generate(), media_type="application/octet-stream")

@app.post("/api/tts")
async def full_tts(req: TTSRequest):
    """完整 TTS — 返回完整音频文件"""
    prompt_speech = f"data/voices/{req.voice_id}.wav"

    result = cosyvoice_model.inference_zero_shot(
        tts_text=req.text,
        prompt_text="",
        prompt_speech_16k=prompt_speech,
        stream=False,
        speed=req.speed,
    )

    audio = next(result)["tts_speech"]

    if req.format == "wav":
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio.unsqueeze(0), req.sample_rate, format="wav")
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/wav")
    else:
        pcm_bytes = (audio * 32768).to(torch.int16).numpy().tobytes()
        return StreamingResponse(io.BytesIO(pcm_bytes), media_type="application/octet-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9880)
```

### 5.3 Silero VAD

```python
# voice/vad.py
import torch
import numpy as np

class SileroVAD:
    """Silero VAD v5 封装"""

    def __init__(self, threshold: float = 0.5, min_silence_ms: int = 300):
        self.model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
        )
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self.sample_rate = 16000

        # 状态
        self._is_speech = False
        self._silence_frames = 0
        self._speech_frames = 0

    def process(self, pcm_frame: bytes) -> dict:
        """
        处理一帧 PCM 音频 (512 samples, 32ms, 16kHz, 16-bit)

        Returns:
            {
                "is_speech": bool,
                "speech_start": bool,  # 上升沿
                "speech_end": bool,    # 下降沿
                "probability": float,
            }
        """
        # bytes → tensor
        audio = np.frombuffer(pcm_frame, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio)

        # 推理
        prob = self.model(tensor, self.sample_rate).item()

        speech_detected = prob > self.threshold
        speech_start = False
        speech_end = False

        if speech_detected:
            self._silence_frames = 0
            self._speech_frames += 1
            if not self._is_speech and self._speech_frames >= 3:  # ~96ms 确认
                self._is_speech = True
                speech_start = True
        else:
            self._speech_frames = 0
            self._silence_frames += 1
            silence_ms = self._silence_frames * 32  # 每帧 32ms
            if self._is_speech and silence_ms >= self.min_silence_ms:
                self._is_speech = False
                speech_end = True

        return {
            "is_speech": self._is_speech,
            "speech_start": speech_start,
            "speech_end": speech_end,
            "probability": prob,
        }

    def reset(self):
        self.model.reset_states()
        self._is_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
```

### 5.4 Filler Pool

```python
# voice/filler.py
import os
import random

class FillerPool:
    """预合成的 filler 音频池"""

    FILLERS = {
        "en": {
            "acknowledge": ["Hmm...", "Well...", "So...", "Right..."],
            "think": ["Let me think...", "Ah...", "Um..."],
            "positive": ["Oh!", "Okay!", "I see!"],
        },
        "zh": {
            "acknowledge": ["嗯...", "这个...", "好的..."],
            "think": ["让我想想...", "嗯..."],
            "positive": ["哦!", "好!", "嗯嗯!"],
        },
        "ja": {
            "acknowledge": ["ええと...", "そうですね...", "はい..."],
            "think": ["ちょっと待ってね...", "うーん..."],
            "positive": ["ああ!", "そう!", "うん!"],
        },
    }

    def __init__(self, data_dir: str = "data/fillers"):
        self.data_dir = data_dir
        self.audio_cache = {}  # {lang/category/index: bytes}

    async def presynthesize_all(self, tts_client, voice_id: str):
        """用 CosyVoice 预合成所有 filler 音频"""
        for lang, categories in self.FILLERS.items():
            lang_dir = os.path.join(self.data_dir, lang)
            os.makedirs(lang_dir, exist_ok=True)

            for category, texts in categories.items():
                for i, text in enumerate(texts):
                    key = f"{lang}/{category}/{i}"
                    path = os.path.join(lang_dir, f"{category}_{i}.pcm")

                    if not os.path.exists(path):
                        await tts_client.synthesize_to_file(text, path, voice_id)

                    with open(path, "rb") as f:
                        self.audio_cache[key] = f.read()

    def get_random(self, lang: str, category: str = None) -> bytes:
        """获取一个随机 filler 音频"""
        if category is None:
            category = random.choice(list(self.FILLERS.get(lang, {}).keys()))

        candidates = [
            k for k in self.audio_cache
            if k.startswith(f"{lang}/{category}/")
        ]

        if not candidates:
            # fallback
            candidates = [k for k in self.audio_cache if k.startswith(f"{lang}/")]

        if not candidates:
            return b""

        return self.audio_cache[random.choice(candidates)]
```

---

## 六、声音克隆

### 6.1 录音要求

每种语言/每个 persona 需要录制一段参考音频：

| 要求 | 规格 |
|------|------|
| 时长 | 最少 10 秒（zero-shot），推荐 30-60 秒 |
| 采样率 | 16kHz 或更高 |
| 格式 | WAV, 单声道 |
| 环境 | 安静房间，无回声 |
| 内容 | 自然的教学对话，覆盖多种语气 |
| 设备 | 专业麦克风或高质量耳机麦克风 |

### 6.2 参考音频存放

```
data/voices/
├── sarah_en.wav       # Sarah 老师英文参考音
├── sarah_zh.wav       # Sarah 老师中文参考音（双语老师）
├── kenji_ja.wav       # Kenji 老师日文参考音
└── README.md          # 录音指南
```

CosyVoice 2 支持 zero-shot voice cloning，只需在推理时传入参考音频即可。

---

## 七、GPU 要求

### 7.1 最低配置（开发/小规模）

| 组件 | 显存 | 说明 |
|------|------|------|
| FunASR Paraformer | ~2 GB | 流式模型较小 |
| CosyVoice 2 (0.5B) | ~4 GB | 半精度推理 |
| Silero VAD | ~50 MB | 极小，可 CPU 运行 |
| **合计** | **~6 GB** | **一张 RTX 3060 (12GB) 即可** |

### 7.2 推荐配置（生产/低延迟）

| 组件 | 推荐硬件 |
|------|---------|
| FunASR | RTX 4060 或更好 |
| CosyVoice 2 | RTX 4090 (24GB) — 用于最低延迟 |
| 或使用 LightTTS 优化框架 | 可在 RTX 3090 上达到类似效果 |

### 7.3 单 GPU 部署优化

如果只有一张 GPU，使用时分复用：
- ASR 和 TTS 不会同时运行（学生说话时跑 ASR，学生停了跑 TTS）
- 可以共享同一张 GPU，通过 CUDA stream 管理

---

## 八、实施路线图（Sonnet 执行计划）

### Phase 0: 环境准备（1-2 天）

```
任务清单：
□ 安装 FunASR + 下载 Paraformer 模型
□ 安装 CosyVoice 2 + 下载 0.5B 模型
□ 安装 Silero VAD (pip install silero-vad 或 torch.hub)
□ 验证 GPU 可用 + 各模型独立运行
□ 录制/准备至少一个 teacher voice 参考音频
□ 创建 ai_tutor/ 新目录结构（删除旧文件之前先 git archive 备份）
```

### Phase 1: 语音管道 MVP（3-5 天）

**目标：浏览器 ↔ 服务器全双工音频通道可用**

```
Day 1-2: 后端音频管道
□ 实现 voice/vad.py — Silero VAD 封装
□ 实现 voice/asr_client.py — FunASR WebSocket 客户端
□ 实现 voice/tts_client.py — CosyVoice 2 HTTP streaming 客户端
□ 实现 voice/filler.py — Filler 池 + 预合成脚本
□ 实现 voice/audio_mixer.py — 简单的音频序列拼接
□ 实现 voice/interruption.py — 打断控制器

Day 2-3: WebSocket 服务
□ 实现 server.py — FastAPI WebSocket endpoint
□ 实现 voice/audio_router.py — 全双工核心状态机
□ 端到端测试：命令行 Python client → server → echo back

Day 3-5: 前端音频通道
□ 实现 static/audio-worklet-processor.js — PCM 采集
□ 实现 useVoiceChannel.js — WebSocket 音频通道
□ 实现 useMicrophone.js — 麦克风权限 + AudioWorklet
□ 实现 useAudioPlayback.js — PCM 播放队列 + stop_playback
□ 实现 AiTutor.vue 最小化版 — 只有麦克风按钮 + 播放
□ 端到端测试：浏览器说话 → 服务器 ASR → 回传文本
```

### Phase 2: LLM 集成 + 教学逻辑（2-3 天）

**目标：完整的对话循环可用**

```
Day 6-7: LLM 集成
□ 实现 llm/client.py — Claude API streaming 客户端 (anthropic SDK)
□ 实现 llm/response_parser.py — 解析结构化 JSON 输出
□ 编写 llm/prompts/persona_sarah.md — 第一个教师 persona
□ 编写 llm/prompts/teaching_rules.md — 教学规则
□ 编写 llm/prompts/phase_rules.md — 各阶段规则

Day 7-8: Session Manager
□ 实现 session/prompt_builder.py — 组装完整 system prompt
□ 实现 session/manager.py — Session 生命周期管理
□ 实现 session/learner_profile.py — SQLite 持久化
□ 实现 session/lesson_plan.py — 简单 JSON 课程计划

Day 8: 集成测试
□ 完整对话循环：说话 → ASR → LLM → TTS → 播放
□ 延迟测量：记录每个环节耗时
□ Filler 效果验证：确认 filler 能掩盖延迟
□ 打断测试：老师说话时学生开口能正确打断
```

### Phase 3: 前端课堂 UI（2-3 天）

**目标：完整的课堂界面**

```
Day 9-10: UI 组件
□ 实现 ClassroomView.vue — 课堂主视图布局
□ 实现 TranscriptPanel.vue — 实时双语字幕
□ 实现 LessonProgress.vue — 课程阶段 + 进度条
□ 实现 VoiceIndicator.vue — 语音状态可视化（谁在说话）
□ 重写 AiTutor.vue — 集成所有组件

Day 10-11: 完善
□ 课程选择页 — 选择课程计划 + 确认开始
□ 课后总结页 — 显示本次课程摘要
□ 学习历史页 — 显示过往课程 + 掌握度
□ 响应式布局 — 移动端适配
```

### Phase 4: 质量优化（持续）

```
□ 延迟优化：
  - 实测端到端延迟，找瓶颈
  - 尝试 LightTTS 替代原生 CosyVoice 推理（可能快 2-3x）
  - LLM prompt 缓存优化（system prompt 部分缓存）
  - 预测性快速回应（常见正确/错误模式直接回复）

□ 教学质量：
  - 测试不同 persona prompt 的教学效果
  - 收集真实对话样本，迭代 system prompt
  - 添加更多语言支持（每种语言一个 persona + voice）

□ 声音质量：
  - 测试不同参考音频的克隆质量
  - 尝试 CosyVoice 3 / Fish-Speech 对比效果
  - 优化 filler 到 real audio 的衔接自然度

□ 长期探索：
  - 评估 PersonaPlex-7B 作为全双工层的可能性
  - 评估本地 7B LLM (Qwen) 替代 Claude API 的可行性
  - 发音评估集成（FunASR 的 pronunciation scoring 或其他方案）
```

---

## 九、成本估算

### 每节课成本（30分钟，~150轮对话）

| 组件 | 方案 | 成本 |
|------|------|------|
| ASR | FunASR 本地 | $0（GPU 电费） |
| LLM | Claude Haiku 4.5 (cached) | ~$0.12 |
| TTS | CosyVoice 2 本地 | $0（GPU 电费） |
| VAD | Silero VAD 本地 | $0 |
| **合计** | | **~$0.12/节课** |

### GPU 成本（云部署估算）

| 配置 | 月租 | 可支撑并发 |
|------|------|-----------|
| RTX 4060 (8GB) | ~$50/月 | ~5 并发学生 |
| RTX 4090 (24GB) | ~$150/月 | ~15 并发学生 |
| A100 (40GB) | ~$300/月 | ~30 并发学生 |

如果每个学生每月上 20 节课，定价 $20/月：
- RTX 4090 支撑 15 学生 = $300 收入 / $150 GPU = **毛利率 50%+**
- 加上 LLM API 成本：$0.12 × 20 × 15 = $36/月
- 实际毛利率：($300 - $150 - $36) / $300 = **38%**

---

## 十、与现有系统的关系

### 保留
- `api.py` — 主 API 服务器，新增 WebSocket endpoint
- `frontend/` — Vue 3 前端，新增 AiTutor 页面和组件
- `database.py` — SQLite 连接，复用给 learner_profile
- `config.py` — 配置管理

### 重构
- `ai_tutor/` — 全面重写为新架构
- `frontend/src/pages/AiTutor.vue` — 从 stub 重写为完整课堂

### 废弃（保留在 git 历史中）
- `ai_tutor/graph/` — 全部（GraphEngine, GraphAssembler, GraphMutator, SubgraphFactory, EdgeWeights, NodeTemplates, ContentConnector, schema.py 中的旧类型）
- `ai_tutor/runtime/policy_runtime.py` — 合并进 LLM prompt
- `ai_tutor/runtime/assessment.py` — 合并进 LLM
- `ai_tutor/runtime/memory.py` — 简化为 session/learner_profile.py
- `ai_tutor/voice/dispatcher.py` — 替换为 audio_router.py
- `ai_tutor/voice/persona.py` — persona 改为 markdown prompt 文件
- `ai_tutor/voice/schema.py` 中的 VoiceModelInput — 废弃
- `ai_tutor/voice_model_rd_plan.md` — 已否定的方案
- `ai_tutor/REDESIGN_PLAN.md` — 被本文档取代

---

## 十一、关键技术参考

| 技术 | 链接 |
|------|------|
| CosyVoice 2 | https://github.com/FunAudioLLM/CosyVoice |
| CosyVoice 2 论文 | https://arxiv.org/abs/2412.10117 |
| LightTTS (优化推理) | https://github.com/ModelTC/LightTTS |
| FunASR | https://github.com/modelscope/FunASR |
| Silero VAD | https://github.com/snakers4/silero-vad |
| Pipecat (参考架构) | https://github.com/pipecat-ai/pipecat |
| PersonaPlex-7B (长期探索) | https://github.com/NVIDIA/personaplex |
| Fish-Speech (备选 TTS) | https://github.com/fishaudio/fish-speech |
| Claude API Streaming | https://docs.anthropic.com/en/api/streaming |

---

## 十二、一句话总结

> **把复杂的教学状态机还给 LLM，把工程精力集中在自建全双工语音管道上。**
> 最终产品：Claude 的大脑 + 真人声音克隆 + 自研低延迟语音通道 = 分不出来是不是真人的 AI 语言老师。
