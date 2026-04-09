# Self-Thinking Voice Model 研发计划

## 概述

这不是传统的 TTS（Text-to-Speech）系统。这是一个**端到端自思考语音生成模型**，能够从结构化课堂状态直接生成教师语音，无需文本中间步骤。

### 核心定位

```
正常流程 (95%+ 回合):
  graph_state + persona + delivery_style + context → VoiceModel → audio

异常回退 (<5%):
  LLM supervisor → text → TTS adapter → audio
```

### 目标指标

- **真人相似度**: ≥95% (MOS ≥ 4.5/5.0)
- **首字节延迟**: < 300ms
- **Persona 一致性**: 同一会话内声音特征方差 < 阈值
- **教学适配性**: 语音风格与教学场景匹配度 ≥90%

---

## 一、模型架构

### 1.1 四阶段管道

```
┌─────────────────────────────────┐
│       Structured Encoder        │
│  (context ~30 fields → 1024d)   │
└──────────────┬──────────────────┘
               │ condition vector
┌──────────────▼──────────────────┐
│       Thinking Module           │
│  (condition → planning tokens)  │
│  K = 32-128 latent tokens       │
└──────────────┬──────────────────┘
               │ planning tokens
┌──────────────▼──────────────────┐
│       Speech Decoder            │
│  (planning → audio tokens)      │
│  autoregressive / flow-matching │
└──────────────┬──────────────────┘
               │ audio tokens / mel
┌──────────────▼──────────────────┐
│          Vocoder                │
│  (tokens → PCM waveform)        │
└─────────────────────────────────┘
```

### 1.2 Structured Encoder

将课堂上下文编码为稠密条件向量。

**输入表示 (~30 字段, 5 组)**:

| 组 | 字段 | 编码方式 |
|----|------|---------|
| **Graph State** | node_type (10种), phase (5种), visit_count, success/failure_count, lesson_progress, is_repair_mode | categorical → learned embedding; continuous → linear projection |
| **Policy Decision** | policy_action (16种), tool_action, delivery_style (10种) | one-hot → learned embedding |
| **Student State** | error_type, confidence, fatigue, engagement, lang_level (6级), consecutive_failures, silence_duration | mixed embedding + linear |
| **Persona Params** | warmth, formality, humor, patience, energy, gender, age_range | continuous → linear; categorical → embedding |
| **Delivery Style Params** | speaking_speed, pause_tendency, emphasis_intensity, emotion_amplitude, intonation_variability, backchannel_frequency, sentence_final_pattern | continuous → linear |
| **Content Context** | content_pack_embedding, recent_turns_embedding, target_skill_embedding | pre-computed dense vectors → cross-attention |

**架构细节**:
- Categorical features → learned embedding tables
- Continuous features → LayerNorm + Linear projection
- 所有 embedding 拼接 → Multi-Head Cross-Attention (8 heads)
- Content embeddings 作为 key/value，state embeddings 作为 query
- 输出: condition vector **c** ∈ R^1024

### 1.3 Thinking Module（核心创新）

这是与传统 TTS 的关键区别。Thinking Module 不生成文本，而是生成**学习到的隐表示**，代表"要说什么"和"怎么说"。

**架构**:
- 小型自回归 Transformer (6-8 层, 512d hidden, 8 heads)
- 输入: condition vector **c** → start token
- 输出: K 个 planning tokens (K = 32-128, 自适应长度)
- Planning tokens 是 continuous learned embeddings，不对应任何离散词表

**Planning tokens 学到什么**:
1. **内容规划**: "给一个关于过去时的提示" vs "直接纠正时态错误"
2. **韵律轮廓**: 全句的音高、节奏走向
3. **重音位置**: 哪些词/音节需要强调
4. **停顿位置**: 哪里插入自然停顿
5. **非语言元素**: 犹豫 (uh, hmm)、backchannel (嗯, 对)、笑声、叹气

**训练方式**:
- 与 Speech Decoder 端到端联合训练
- Loss = speech reconstruction loss + prosody matching loss
- Planning tokens 通过反向传播从 speech decoder 获得梯度
- 无需人工标注 planning tokens 的含义

**为什么不直接跳过 Thinking Module?**
- 直接 condition → speech decoder 会导致语音缺乏规划感
- 人类教师在开口前有一个隐式的 "想好怎么说" 过程
- Thinking Module 模拟这个过程，产生更自然、更有意图性的语音

### 1.4 Speech Decoder

两个候选架构：

#### 方案 A: 自回归 Audio Token Decoder（V1 推荐）

- 使用 neural audio codec (EnCodec / SoundStream / 自研) 将音频离散化
- Transformer decoder 自回归生成 audio tokens
- Audio tokens → Vocoder → waveform
- **优势**: 已验证架构 (VALL-E, AudioLM)，高质量
- **劣势**: 顺序生成 = 延迟较高
- **流式优化**: 分 chunk 生成 (每 200ms 一个 chunk)，播放与生成并行

#### 方案 B: Flow-Matching Decoder（V2 考虑）

- 基于条件 flow matching (CFM) 的非自回归 decoder
- Condition + planning tokens → 并行生成 mel spectrogram
- Mel → HiFi-GAN vocoder → waveform
- **优势**: 推理速度快 (并行生成)
- **劣势**: 可能损失韵律自然度

**V1 决策**: 选方案 A，目标是 95%+ 真人相似度。延迟通过流式 chunk 优化。
**V2 计划**: 探索 A+B 混合——flow-matching 生成主体 + 自回归精修韵律关键段。

### 1.5 Vocoder

- V1: 使用成熟的 HiFi-GAN / BigVGAN
- 如用 audio token 方案: codec decoder (EnCodec decoder) + optional waveform refinement
- 24kHz / 16-bit PCM 输出

---

## 二、Persona 维护系统

### 2.1 PersonaState

```
固定身份（会话内不变）:
  - voice_identity_embedding: 参考音频的 speaker embedding
  - gender, age_range, accent
  - base_speaking_rate

固定人格（会话内不变）:
  - warmth (0-1)
  - formality (0-1)
  - humor (0-1)
  - patience (0-1)
  - energy (0-1)

动态状态（每几轮更新）:
  - current_emotion: neutral | encouraging | concerned | excited | thoughtful | firm
  - emotion_intensity (0-1)
  - energy_level: 长课中缓慢下降
  - rapport_level: 随互动成功逐渐上升

一致性追踪:
  - phrases_used_this_session
  - last_backchannel_type
  - turns_since_last_humor
```

### 2.2 PersonaManager 逻辑

每个回合:

1. **读取 persona 基础特质** (warmth, formality, ...)
2. **叠加 delivery style modifiers** (10 种风格各有 speed/pause/emphasis/emotion/intonation/backchannel 的数值调整)
3. **应用动态调整** (fatigue → slow down, low engagement → more energy, high rapport → warmer)
4. **一致性规则** (避免连续使用相同 backchannel, 控制 humor 频率)
5. **输出最终 VoiceModelInput** 的 persona + delivery 字段

### 2.3 跨会话一致性

- 固定身份存入 LearnerMemory
- 同一学生始终分配到同一 persona_id
- 恢复会话时从 LearnerMemory 读取 voice_identity_embedding

---

## 三、语音模型输入（VoiceModelInput）

完整输入约 30 个字段：

```python
# Graph State (7 fields)
current_node_type: str         # one-hot / 10 node types
current_phase: str             # one-hot / 5 phases
node_visit_count: int
node_success_count: int
node_failure_count: int
lesson_progress: float         # 0.0 - 1.0
is_repair_mode: bool

# Policy Decision (3 fields)
policy_action: str             # one-hot / 16 actions
tool_action: str | None
delivery_style: str            # one-hot / 10 styles

# Student State (8 fields)
student_error_type: str
student_confidence: float
student_fatigue: float
student_engagement: float
student_lang_level: str        # A1-C2
consecutive_failures: int
student_last_utterance_duration_ms: int
student_silence_duration_ms: int

# Persona Parameters (7 fields)
persona_warmth: float
persona_formality: float
persona_humor: float
persona_patience: float
persona_energy: float
persona_gender: str
persona_age_range: str

# Delivery Style Parameters (7 fields)
speaking_speed: float          # 0.5 - 2.0
pause_tendency: float          # 0.0 - 1.0
emphasis_intensity: float
emotion_amplitude: float
intonation_variability: float
backchannel_frequency: float
sentence_final_pattern: str    # falling | rising | sustained

# Content Context (3 embedding vectors)
content_pack_embedding: list[float]
recent_turns_embedding: list[float]
target_skill_embedding: list[float]
```

---

## 四、训练 Pipeline

### 4.1 六阶段训练

#### Stage 1: Speech Foundation 预训练 (6-12 月)

**目标**: 训练一个大型语音语言模型，学会生成自然语音。

- **数据**: 50,000+ 小时通用语音 (LibriSpeech, GigaSpeech, 多语种语料)
- **架构**: Transformer encoder-decoder + audio tokenizer
- **目标函数**: next-audio-token prediction
- **硬件**: 8-16 x A100/H100
- **输出**: 能生成自然语音的基础模型

#### Stage 2: Teacher Domain Adaptation (3-6 月)

**目标**: 让模型学会教师说话的模式和风格。

- **数据**: 5,000+ 小时教师课堂录音
  - 来源: YouTube 在线教学视频、授权教学录音、MOOC 平台
  - 语言: 先做英语 + 中文，后扩展
- **方法**: 在 Stage 1 模型上 fine-tune
- **新增**: 注入 Structured Encoder，开始条件生成训练
  - 输入: (persona_params, delivery_style) → 条件生成
- **输出**: 模型能生成教师风格语音，具备基础 persona 控制

#### Stage 3: Thinking Module 训练 (3-6 月)

**目标**: 训练 planning token 层，实现从状态到语音的端到端生成。

- **数据**: 合成 state-audio pairs (见 4.2 数据收集)
  - 图模拟系统生成 VoiceModelInput 上下文
  - 专业配音演员录制对应语音
  - ~100 小时真人录制 + voice conversion 扩展到 ~1000 小时
- **方法**:
  1. 先冻结 Speech Decoder，只训练 Thinking Module
  2. 再联合 fine-tune Thinking Module + Speech Decoder
- **Loss**:
  - Audio reconstruction loss (mel spectrogram / codec token matching)
  - Prosody matching loss (pitch contour, energy contour, duration matching)
  - State fidelity loss (生成语音的隐式内容应与 context 对齐)
- **输出**: 模型能从纯状态输入生成情境适配的教师语音

#### Stage 4: Persona Consistency 训练 (2-3 月)

**目标**: 保证同一 persona 在整个会话中声音特征一致。

- **数据**: 500+ 小时/archetype，标注了 persona 特征的多轮对话
  - 3-5 个 persona archetype（温和女教师、严肃男教授、活力青年教师等）
- **方法**:
  - Contrastive loss: 同 persona 不同回合的语音应相似
  - Triplet loss: (anchor, positive_same_persona, negative_diff_persona)
  - 会话级 consistency regularization
- **输出**: 同 persona 跨回合声音稳定

#### Stage 5: RLHF / DPO 对齐 (2-3 月)

**目标**: 根据人类偏好优化语音质量和教学适配性。

- **数据**: 500+ 小时偏好对 (preferred_audio, rejected_audio | same_context)
- **评估维度**:
  - 自然度: 听起来像真人吗？
  - 教学适配性: 语气和风格适合当前教学场景吗？
  - Persona 一致性: 听起来像同一个老师吗？
  - 学生友好度: 作为学生你想继续听这个老师讲课吗？
- **方法**: DPO (Direct Preference Optimization)
- **输出**: 人类评判高自然度+高适配性的语音

#### Stage 6: 延迟优化 + 蒸馏 (1-2 月)

**目标**: 达到 < 300ms 首字节延迟的实时性能。

- **方法**:
  - Knowledge distillation: 大模型 → 小模型
  - Streaming decoder: 分 200ms chunk 生成
  - Audio chunk pipeline: 生成 chunk 1 时开始播放
  - 量化: INT8 / FP16 推理
- **硬件目标**: 单张 A10 / RTX 4090 实时推理
- **输出**: 生产环境可部署的模型

### 4.2 时间线估算

```
Month 1-12:  Stage 1 (Speech Foundation)
Month 6-12:  Stage 2 (Teacher Domain) [与 Stage 1 后半段并行]
Month 10-16: Stage 3 (Thinking Module)
Month 14-17: Stage 4 (Persona Consistency)
Month 16-19: Stage 5 (RLHF/DPO)
Month 18-20: Stage 6 (Latency Optimization)

总计: ~18-20 月 (有并行)
```

---

## 五、数据收集

### 5.1 数据类型

| 数据类型 | 用途 | 目标量 | 来源 |
|---------|------|--------|------|
| 通用语音 | Stage 1 预训练 | 50,000+ hrs | LibriSpeech, GigaSpeech, 多语种 |
| 教师课堂录音 | Stage 2 domain adapt | 5,000+ hrs | YouTube, MOOC, 授权录音 |
| State-audio 配对 | Stage 3 thinking | ~1,000 hrs | 合成 pipeline (见下) |
| Persona 标注语音 | Stage 4 consistency | 500+ hrs/archetype | 标注团队 + 配音演员 |
| 韵律标注语音 | 全流程 | 1,000+ hrs | 半自动: forced alignment + 人工校正 |
| Delivery style 标注 | Style 控制 | 200+ hrs/style | 从录音中人工标注 |
| 偏好对 | Stage 5 DPO | 500+ hrs | 人工评比 |

### 5.2 合成数据 Pipeline (State-Audio Pairs)

由于 graph-state-conditioned 语音数据不自然存在，需要合成：

1. **图模拟**: 运行 lesson graph 模拟器（无真实学生，用模拟响应）
2. **状态记录**: 每个回合记录完整的 VoiceModelInput
3. **配音录制**: 专业配音演员根据状态描述录制教师语音
   - 提供: 教学场景描述 + 目标风格 + 参考句式
   - 录制: 10+ 配音演员，每人 10+ 小时
4. **Voice conversion 扩展**: 100 小时真人 → 1000 小时（保持 state-audio 对齐）

### 5.3 数据收集工具

```
ai_tutor/voice/data_collection/
├── classroom_scraper.py        # 下载处理 YouTube/MOOC 教师录音
├── prosody_annotator.py        # 自动韵律标注 (pitch, energy, duration)
├── persona_labeler.py          # 半自动 persona 特征标注
├── delivery_style_labeler.py   # 语音片段 → delivery style 映射
├── state_audio_aligner.py      # 课堂状态与音频段对齐
└── synthetic_generator.py      # 图模拟 + 配音 → (VoiceModelInput, audio) 对
```

---

## 六、评估体系

### 6.1 指标

| 指标 | 方法 | 目标 |
|------|------|------|
| **MOS** (Mean Opinion Score) | 人工评分 1-5 | ≥ 4.5 |
| **Speaker Similarity** | 同 persona 跨回合 cosine similarity | ≥ 0.90 |
| **Pedagogical Fit** | 人工评分: 语音风格与教学场景匹配度 | ≥ 90% |
| **Latency** | 首字节时间测量 | < 300ms |
| **Style Controllability** | 10 种 delivery style 分类准确率 | ≥ 85% |
| **A/B vs Human** | 盲测: AI 教师 vs 真人教师 | 偏好差 < 15% |

### 6.2 评估工具

```
ai_tutor/voice/evaluation/
├── mos_eval.py                 # Mean Opinion Score 评估框架
├── persona_consistency.py      # 跨回合 persona 相似度指标
├── pedagogical_fit.py          # 教学场景匹配度评估
└── ab_test.py                  # A/B 测试框架
```

---

## 七、训练基础设施

### 7.1 目录结构

```
ai_tutor/voice/training/
├── configs/
│   ├── stage1_pretrain.yaml
│   ├── stage2_domain_adapt.yaml
│   ├── stage3_thinking.yaml
│   ├── stage4_persona.yaml
│   ├── stage5_alignment.yaml
│   └── stage6_distill.yaml
├── data_loaders.py
├── losses.py                   # AudioReconstructionLoss, ProsodyMatchLoss,
│                               # PersonaConsistencyLoss, StateFidelityLoss
├── train_foundation.py
├── train_domain.py
├── train_thinking.py
├── train_persona.py
├── train_alignment.py
├── distill.py
└── evaluate.py
```

### 7.2 硬件需求

| 阶段 | GPU | 预计训练时间 |
|------|-----|------------|
| Stage 1 | 8-16 x A100/H100 | 4-8 周 |
| Stage 2 | 4-8 x A100 | 2-4 周 |
| Stage 3 | 4-8 x A100 | 3-6 周 |
| Stage 4 | 2-4 x A100 | 1-2 周 |
| Stage 5 | 2-4 x A100 | 1-2 周 |
| Stage 6 | 1-2 x A100 | 1 周 |
| **推理** | 1 x A10/RTX4090 | 实时 |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 95% 真人相似度无法达标 | 核心产品质量 | TTS fallback 始终可用；阶段性交付，V1 先用高质量 TTS |
| Thinking Module 无法学到有意义的 planning | 语音缺乏意图性 | 回退到 Stage 2 模型（text-conditioned）作为中间方案 |
| 数据收集成本过高 | 训练进度受阻 | 优先合成数据 + voice conversion 扩展；渐进式数据收集 |
| 延迟无法达到 <300ms | 用户体验差 | 流式 chunk 生成；考虑 flow-matching decoder |
| Persona consistency 不稳定 | 学生体验割裂 | 加强 Stage 4 训练；运行时 consistency check + 重生成 |

---

## 九、阶段性里程碑

| 里程碑 | 交付物 | 预计时间 |
|--------|-------|---------|
| **M1: Persona + TTS Fallback** | PersonaManager + 高质量 TTS 集成，可用于 demo | 2 月 |
| **M2: Speech Foundation** | Stage 1 基础模型训练完成 | 12 月 |
| **M3: Teacher Voice** | Stage 2 教师语音模型，基础 persona 控制 | 15 月 |
| **M4: Self-Thinking Prototype** | Stage 3 完成，从状态生成语音的原型 | 18 月 |
| **M5: Production Model** | Stage 4-5 完成，高质量+persona 一致 | 20 月 |
| **M6: Real-Time Deployment** | Stage 6 完成，生产环境可部署 | 22 月 |

M1 可在 2 个月内完成，作为产品 demo 的临时方案。后续里程碑持续提升语音质量。
