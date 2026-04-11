# V3 — 自研多语言全双工 Speech-to-Speech 教学模型训练方案

> V2 = Cascade 拼接方案（Claude + CosyVoice + FunASR），保持不变，先做出来。
> V3 = 端到端全双工模型，最终替代 V2。本文档是 V3 的训练方案。

---

## 一、目标

构建一个端到端的 speech-to-speech 模型，具备以下能力：

| 能力 | 具体要求 |
|------|---------|
| **全双工** | 听和说同时进行，支持打断、backchannel、自然 turn-taking |
| **多语言** | 至少支持 en/zh/ja/ko/de/fr/es/ru 8 种语言 |
| **教学行为** | 具备 recast、解释、鼓励、纠错、引导自纠等教学技能 |
| **Persona 控制** | 通过 text prompt + voice prompt 控制角色和声音 |
| **低延迟** | Turn-taking < 200ms，打断 < 300ms |
| **真人感** | 自然语调、口头语、停顿、笑声 |

---

## 二、技术路线选型

### 2.1 可选的基座架构

| 架构 | 全双工 | 多语言 | 开源 | 适合改造 |
|------|--------|--------|------|---------|
| **Moshi** (Kyutai) | **原生** | ❌ 英语 | ✅ MIT | ✅ 架构最佳 |
| **PersonaPlex** (NVIDIA) | **原生** | ❌ 英语 | ✅ MIT | ✅ 已验证 persona 控制 |
| **Qwen3-Omni** (Alibaba) | ⚠️ 流式但非双工 | **✅ 119 语言** | ✅ | ⚠️ 非全双工架构 |
| **GLM-4-Voice** (Zhipu) | ❌ 半双工 | ⚠️ 中英 | ✅ | ❌ 不适合 |
| **从零训练** | 自定义 | 自定义 | — | ❌ 成本过高 |

### 2.2 选定路线：Moshi 架构 + 多语言改造

**理由：**
1. Moshi 是目前唯一经过验证的**原生全双工**架构
2. PersonaPlex 证明了从 Moshi fine-tune 只需 **6 小时 × 8 A100**
3. Qwen3-Omni 虽然多语言，但 Thinker-Talker 架构不是真正的全双工（仍是 turn-based + streaming output）
4. 我们的核心需求是全双工，多语言可以通过替换组件解决

**改造方案：**
```
原始 Moshi:                    V3 改造：
  Mimi (英语 codec)        →    Mimi-ML (多语言 codec, XLS-R 蒸馏)
  Helium (英语 7B LLM)     →    Qwen2.5-7B (多语言 LLM backbone)
  Fisher (英语对话)         →    多语言教学对话数据
  通用对话能力              →    语言教学专用能力
```

---

## 三、模型架构详解

### 3.1 整体架构（基于 Moshi，3 个关键改动）

```
┌─────────────────────────────────────────────────────────────┐
│                    V3 Model Architecture                     │
│                                                              │
│  输入流（同时）：                                             │
│  ┌──────────┐        ┌──────────────────┐                    │
│  │ 学生音频  │──────→│ Mimi-ML Encoder  │──→ 学生 audio tokens│
│  │ (24kHz)   │       │ (多语言 codec)    │    (12.5 Hz, 8 VQ) │
│  └──────────┘        └──────────────────┘                    │
│                                                              │
│  ┌──────────┐                                                │
│  │ Text Prompt│  Persona + 教学上下文 + 学生档案               │
│  │ (UTF-8)   │                                               │
│  └─────┬─────┘                                               │
│        │                                                     │
│        ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Temporal Transformer (7B)                   │ │
│  │              [初始化自 Qwen2.5-7B]  ←── 改动 1          │ │
│  │                                                          │ │
│  │  处理 4 路交错 token 流：                                 │ │
│  │  1. 学生 audio tokens (semantic level)                   │ │
│  │  2. Agent text tokens (inner monologue) ←── 改动 3      │ │
│  │  3. Agent audio tokens (semantic level)                  │ │
│  │  4. Text prompt tokens                                   │ │
│  │                                                          │ │
│  │  每个时间步 (80ms)：                                      │ │
│  │    consume student audio token                           │ │
│  │    → predict agent text token                            │ │
│  │    → predict agent semantic audio token                  │ │
│  │    → feed to Depth Transformer                           │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Depth Transformer (~300M)                   │ │
│  │                                                          │ │
│  │  输入: agent semantic token (from Temporal)              │ │
│  │  输出: 7 个 acoustic tokens (残差量化层)                  │ │
│  │                                                          │ │
│  │  Token 生成顺序 (per timestep):                          │ │
│  │    text → semantic_audio → acoustic_1 → ... → acoustic_7 │ │
│  └───────────────────────────┬─────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌──────────────────┐                                        │
│  │ Mimi-ML Decoder  │──→ 老师音频 (24kHz, streaming)         │
│  │ (多语言 codec)    │    ←── 改动 2                          │
│  └──────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 三个关键改动

#### 改动 1: Temporal Transformer backbone → Qwen2.5-7B

| | 原始 Moshi (Helium) | V3 (Qwen2.5-7B) |
|--|-----|------|
| 参数量 | 7B | 7B |
| 训练数据 | 2.1T tokens 英语 | 18T tokens 多语言 |
| MMLU | 54.3% | 74.2% |
| 中文能力 | ❌ | ✅ |
| CJK 支持 | ❌ | ✅ |

**初始化方法：**
1. 加载 Qwen2.5-7B 的预训练权重
2. 扩展 vocabulary 以包含 Mimi 的 audio token ID（2048 × 8 codebook = 16,384 个 audio tokens）
3. 新增的 audio embedding 随机初始化
4. 保留 Qwen2.5 的 text embedding 不变
5. Temporal Transformer 的架构参数（hidden_dim, num_heads, num_layers）需要匹配 Qwen2.5-7B

**注意：** Qwen2.5-7B 使用 GQA（Grouped Query Attention），与 Moshi 的 MHA 不同。
需要确认 Moshi 的多流处理逻辑是否与 GQA 兼容，如果不兼容需要微调架构。

#### 改动 2: Mimi → Mimi-ML（多语言 codec）

**问题：** 原始 Mimi 使用英语 WavLM 做语义蒸馏，英语音素覆盖率高但 CJK 音素可能映射不良。

**方案：用 XLS-R 替代 WavLM 作为蒸馏目标**

| | WavLM (原始 Mimi) | XLS-R-300M |
|--|-----|------|
| 训练数据 | 94K hours 英语 | 436K hours, 128 语言 |
| 语言覆盖 | 英语为主 | 128 语言 (含全部 8 目标语言) |
| 特征维度 | 1024 | 1024 |
| 接口兼容 | ✅ | ✅ (相同维度) |

**训练步骤：**
1. 保持 Mimi encoder/decoder 架构不变（Conv + Transformer）
2. 将蒸馏目标从 WavLM 替换为 XLS-R-300M
3. 在多语言音频数据上重新训练（不是 fine-tune，是重新训练 codec）
4. 保持 12.5 Hz frame rate、8 codebooks、2048 entries per codebook

**训练数据（codec 训练不需要对话数据，只需要干净音频）：**

| 语言 | 数据源 | 小时数 |
|------|--------|-------|
| English | LibriSpeech + Common Voice | ~1000h |
| Chinese | WenetSpeech + AISHELL | ~1000h |
| Japanese | Common Voice + CSJ | ~500h |
| Korean | KSponSpeech + Common Voice | ~500h |
| German | MLS German + Common Voice | ~500h |
| French | MLS French + Common Voice | ~500h |
| Spanish | MLS Spanish + Common Voice | ~500h |
| Russian | Common Voice + VoxForge | ~300h |
| **合计** | | **~4,800h** |

**计算成本估算：**
- 4 × A100 (80GB) × 5-7 天
- 云成本：4 × $3/hr × 168h ≈ **$2,000**

#### 改动 3: Inner Monologue 增强（教学行为）

Moshi 的 Inner Monologue 是辅助性的 text token 预测。
V3 将其升级为**教学行为控制通道**：

```
每个时间步的 token 生成顺序：

原始 Moshi:
  [student_semantic] → [agent_text] → [agent_semantic] → [agent_acoustic × 7]
                        ↑
                    普通文本预测

V3:
  [student_semantic] → [agent_text] → [agent_semantic] → [agent_acoustic × 7]
                        ↑
                    结构化教学文本:
                    "<recast>Oh you went to the park?</recast>"
                    "<explain>So in English we use 'went'...</explain>"
                    "<encourage>Almost there!</encourage>"
```

通过在训练数据中使用结构化 text token，模型学会将**教学意图**编码到内部文本流中，
然后自然地映射到对应的语音表达。

这是 V3 最关键的创新点：**Inner Monologue 变成了教学思维链**。

---

## 四、训练数据管道

### 4.1 数据来源总览

| 数据类型 | 用途 | 来源 | 规模 |
|---------|------|------|------|
| **多语言干净音频** | Mimi-ML codec 训练 | 公开语音数据集 | ~4,800h |
| **多语言文本** | Qwen2.5-7B 已有 | 不需要额外 | 18T tokens |
| **真实对话录音** | 学习自然 turn-taking + 全双工 | Fisher, AISHELL-4, Magic Data | ~3,000h |
| **合成教学对话** | 学习教学行为 + 多语言 | Claude 生成脚本 + CosyVoice 合成 | ~5,000h |
| **合成全双工混合** | 学习 overlap + backchannel | 对上述数据做 overlap 混音 | 包含在上述中 |

### 4.2 合成教学对话数据管道（核心创新）

这是整个训练方案中**最关键**的数据来源。PersonaPlex 证明了合成数据可以有效教会模型新行为。

#### Step 1: Claude 生成教学对话脚本

```python
# 用 Claude 生成 10,000+ 教学对话脚本
# 每个脚本包含完整的一节课（约 30-50 轮对话）

SCRIPT_GENERATION_PROMPT = """
生成一段英语教学对话脚本。

[设定]
- 老师：{persona_name}，{persona_description}
- 学生：{student_name}，水平 {level}，母语 {l1}
- 教学重点：{topic}（例：present perfect tense）
- 课程阶段：{phase}（opening/teach/practice/closing）

[要求]
1. 每轮标注教学行为：<recast>, <explain>, <encourage>, <correct>, <check>, <practice_prompt>
2. 包含自然口头语、停顿标记 [pause]、笑声 [laugh]
3. 学生要犯符合其水平的真实错误
4. 老师用 recast 优先，直接纠正最少
5. 标注 overlap 标记：当学生说 "嗯嗯" 或老师说 "right" 时标注 [overlap_start] [overlap_end]
6. 标注打断：当学生在老师说话时开口 [interrupt]
7. 标注 backchannel：老师在学生说话时发出的简短回应 [backchannel: "uh-huh"]

[输出格式]
```json
{
  "persona": {"name": "Sarah", "voice_id": "sarah_en"},
  "student": {"name": "小明", "level": "B1", "l1": "zh"},
  "topic": "present perfect tense",
  "turns": [
    {
      "speaker": "teacher",
      "text": "<hook>Hey! How's your week been?</hook>",
      "timing": {"start": 0.0, "duration": 1.5},
      "emotion": "warm"
    },
    {
      "speaker": "student",
      "text": "Uh... my week is... good. I go to park yesterday.",
      "timing": {"start": 2.0, "duration": 3.5},
      "errors": ["tense: 'go' should be 'went'", "article: missing 'the'"],
      "overlaps": [
        {"type": "backchannel", "from": "teacher", "text": "Mm-hmm",
         "at_offset": 1.5}
      ]
    },
    {
      "speaker": "teacher",
      "text": "<recast>Oh nice, you went to the park! [pause] What did you do there?</recast>",
      "timing": {"start": 5.8, "duration": 2.5},
      "emotion": "curious"
    }
  ]
}
```
"""
```

**每种语言生成 1,000-2,000 个对话脚本：**

| 语言对 | 场景 | 脚本数 | 合成音频时长（估算） |
|--------|------|--------|-------------------|
| en→zh 学习者 | A1-C1, 各种语法/词汇/口语 | 2,000 | ~800h |
| zh→en 学习者 | A1-C1 | 2,000 | ~800h |
| ja→en 学习者 | A1-C1 | 1,000 | ~400h |
| ko→en 学习者 | A1-C1 | 1,000 | ~400h |
| de→en 学习者 | A1-C1 | 500 | ~200h |
| fr→en 学习者 | A1-C1 | 500 | ~200h |
| es→en 学习者 | A1-C1 | 500 | ~200h |
| ru→en 学习者 | A1-C1 | 500 | ~200h |
| en→ja/ko/de/fr/es/ru | 各 500 | 3,000 | ~1,200h |
| **合计** | | **~11,000** | **~4,400h** |

**Claude API 成本：** 11,000 脚本 × ~2,000 tokens/脚本 × $0.001/1K (Haiku cached) ≈ **~$22**

#### Step 2: CosyVoice 2/3 合成语音

```python
import asyncio
from cosyvoice_client import CosyVoiceClient

async def synthesize_conversation(script: dict) -> dict:
    """将一个对话脚本的所有 turns 合成为音频"""
    tts = CosyVoiceClient("http://localhost:9880")
    result = {"turns": []}

    for turn in script["turns"]:
        if turn["speaker"] == "teacher":
            voice_id = script["persona"]["voice_id"]
        else:
            voice_id = f"student_{script['student']['l1']}_sample"

        # 合成主音频
        audio = await tts.synthesize(
            text=strip_tags(turn["text"]),  # 移除 <recast> 等标签
            voice_id=voice_id,
            speed=get_speed_for_emotion(turn.get("emotion", "neutral")),
        )

        # 合成 overlap 音频（backchannel）
        overlaps_audio = []
        for overlap in turn.get("overlaps", []):
            ov_audio = await tts.synthesize(
                text=overlap["text"],
                voice_id=script["persona"]["voice_id"] if overlap["from"] == "teacher"
                         else f"student_{script['student']['l1']}_sample",
                speed=1.0,
            )
            overlaps_audio.append({
                "audio": ov_audio,
                "at_offset": overlap["at_offset"],
            })

        result["turns"].append({
            "speaker": turn["speaker"],
            "audio": audio,
            "text": turn["text"],        # 保留标签，用于 inner monologue
            "overlaps": overlaps_audio,
            "timing": turn["timing"],
        })

    return result
```

#### Step 3: 混音为全双工格式

```python
import numpy as np

def mix_to_dual_stream(conversation: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    将对话混合为两个独立的音频流（学生流 + 老师流），
    模拟全双工通话场景。

    Returns:
        student_stream: np.ndarray (24kHz, mono)
        teacher_stream: np.ndarray (24kHz, mono)
    """
    sample_rate = 24000
    total_duration = get_total_duration(conversation)
    total_samples = int(total_duration * sample_rate)

    student_stream = np.zeros(total_samples, dtype=np.float32)
    teacher_stream = np.zeros(total_samples, dtype=np.float32)

    for turn in conversation["turns"]:
        start_sample = int(turn["timing"]["start"] * sample_rate)
        audio = turn["audio"]

        if turn["speaker"] == "student":
            end_sample = start_sample + len(audio)
            student_stream[start_sample:end_sample] += audio
        else:
            end_sample = start_sample + len(audio)
            teacher_stream[start_sample:end_sample] += audio

        # 叠加 overlap 音频
        for overlap in turn.get("overlaps", []):
            ov_start = start_sample + int(overlap["at_offset"] * sample_rate)
            ov_audio = overlap["audio"]
            ov_end = ov_start + len(ov_audio)

            if overlap.get("from") == "teacher":
                teacher_stream[ov_start:ov_end] += ov_audio
            else:
                student_stream[ov_start:ov_end] += ov_audio

    return student_stream, teacher_stream
```

#### Step 4: Tokenize 为训练数据

```python
def tokenize_dual_stream(
    student_audio: np.ndarray,
    teacher_audio: np.ndarray,
    teacher_text: list[str],  # 带教学标签的文本，与 audio tokens 时间对齐
    text_prompt: str,         # persona + teaching context
    mimi_encoder,
    text_tokenizer,
) -> dict:
    """
    将双流音频 + 教学文本转换为训练样本。

    输出格式（per timestep, 12.5 Hz = 每 80ms 一步）：
    {
        "student_semantic_tokens": [int],      # 学生语义层 token 序列
        "student_acoustic_tokens": [[int] × 7], # 学生声学层 token 序列
        "teacher_text_tokens": [int],           # 老师内部文本 token（含教学标签）
        "teacher_semantic_tokens": [int],       # 老师语义层 token 序列
        "teacher_acoustic_tokens": [[int] × 7], # 老师声学层 token 序列
        "text_prompt_tokens": [int],            # Text prompt (persona + context)
    }
    """
    # 1. Mimi-ML 编码双流音频
    student_codes = mimi_encoder.encode(student_audio)  # [8, T] (8 codebooks × T frames)
    teacher_codes = mimi_encoder.encode(teacher_audio)  # [8, T]

    # 2. 文本 tokenize（教学标签保留为特殊 token）
    teacher_text_ids = text_tokenizer.encode(teacher_text, add_special_tokens=False)

    # 3. 时间对齐：将文本 token 分配到对应的 audio frame
    aligned_text = align_text_to_frames(teacher_text_ids, teacher_codes.shape[1])

    # 4. Text prompt tokenize
    prompt_ids = text_tokenizer.encode(text_prompt)

    return {
        "student_semantic_tokens": student_codes[0].tolist(),  # 第一层 = 语义
        "student_acoustic_tokens": student_codes[1:].tolist(), # 2-8层 = 声学
        "teacher_text_tokens": aligned_text,
        "teacher_semantic_tokens": teacher_codes[0].tolist(),
        "teacher_acoustic_tokens": teacher_codes[1:].tolist(),
        "text_prompt_tokens": prompt_ids,
    }
```

### 4.3 真实对话数据

| 数据集 | 语言 | 类型 | 小时数 | 用途 |
|--------|------|------|--------|------|
| **Fisher** | English | 电话对话 | 2,000h | 全双工 turn-taking |
| **AISHELL-4** | Chinese | 会议多人 | 120h | 中文自然对话 |
| **Magic Data LSMCSRC** | CN/JA/KO | 对话 | 60h | CJK 自然对话 |
| **MLC-SLM** | 多语言 | 对话 | 1,604h | 多语言对话 |
| **Common Voice** | 8 语言 | 朗读 | 各 100-500h | 补充语音覆盖 |
| **MLS** | 8 语言 | 朗读 | 各 100-2000h | 补充语音覆盖 |

**处理流程：**
1. Fisher / AISHELL-4 / Magic Data：已有双通道录音，直接分离为 student/teacher 双流
2. 使用 PyAnnote 做说话人分离（diarization）
3. 用 Whisper 生成对齐文本（作为 inner monologue 标签）
4. 对非教学对话，不加教学行为标签，让模型学习通用对话能力

---

## 五、训练阶段

### 5.1 训练流水线总览

```
Stage 0: Mimi-ML codec 训练
    多语言音频 + XLS-R 蒸馏 → 多语言语音 codec
    ↓
Stage 1: Backbone 适配
    Qwen2.5-7B 权重 → 扩展 vocabulary → 适配 Moshi 多流架构
    ↓
Stage 2: 多流预训练（单说话人 → 双说话人）
    大量多语言语音数据 → 学会音频 token 生成
    ↓
Stage 3: 全双工对话微调
    Fisher + AISHELL-4 + 多语言对话 → 学会自然 turn-taking
    ↓
Stage 4: 教学行为微调
    合成教学对话数据 → 学会教学技能 + persona 控制
    ↓
Stage 5: 对齐（DPO）
    人工偏好数据 → 教学质量优化
```

### 5.2 Stage 0: Mimi-ML Codec 训练

**目标：** 训练一个多语言版本的 Mimi 语音 codec。

**架构（与原始 Mimi 相同）：**
```
Encoder:
  5 × Conv1D (strides: 4, 5, 6, 8, 2 → 总降采样 1920×)
  8 × Causal Transformer (8 heads, 250 token context window)

Quantizer:
  Split RVQ:
    Level 1: Semantic VQ (2048 entries) ← XLS-R distillation
    Level 2-8: Acoustic RVQ (2048 entries each)

Decoder:
  Reverse of encoder (Transformer + TransposeConv)
```

**训练配置：**
```yaml
data:
  sources:
    - LibriSpeech (en, 960h)
    - WenetSpeech (zh, 1000h subset)
    - CSJ (ja, 500h)
    - KSponSpeech (ko, 500h)
    - MLS (de/fr/es, 500h each)
    - Common Voice (ru, 300h)
  total: ~4,800 hours
  sample_rate: 24000
  augmentation:
    - speed_perturb: [0.9, 1.0, 1.1]
    - noise_aug: SNR 10-40dB (MUSAN noise)

model:
  frame_rate: 12.5  # Hz
  codebook_size: 2048
  num_codebooks: 8
  latent_dim: 256

distillation:
  teacher: facebook/wav2vec2-xls-r-300m  # 替代 WavLM
  layer: 17  # 最佳语义表征层
  loss_weight: 1.0
  similarity: cosine

losses:
  - adversarial (multi-scale discriminator)
  - feature_matching
  - semantic_distillation (XLS-R cosine)
  # 不使用重建损失（参照原 Mimi 设计）

training:
  gpus: 4 × A100 (80GB)
  batch_size: 64 (per GPU)
  steps: 500,000
  optimizer: AdamW (lr=3e-4, warmup 10K)
  duration: ~5 days
```

**成本：** 4 × A100 × 5 天 × $3/hr = **~$1,440**

**验证指标：**
- ABX error (phoneme discrimination): 每种语言 < 10%
- MUSHRA (语音质量): > 60
- Character Error Rate (CER, 编码→解码→ASR): 每种语言 < 5%

### 5.3 Stage 1: Backbone 适配

**目标：** 将 Qwen2.5-7B 适配为 Moshi 的 Temporal Transformer。

**无需 GPU 训练**，纯架构改动：

```python
# 伪代码：backbone 适配

# 1. 加载 Qwen2.5-7B
qwen = AutoModel.from_pretrained("Qwen/Qwen2.5-7B")

# 2. 扩展 embedding 层
# Qwen2.5 vocab: 151,936 tokens
# 新增: 8 codebooks × 2048 entries = 16,384 audio tokens
# 新增: 特殊 token (<audio_pad>, <speech_start>, <speech_end>,
#        <recast>, <explain>, <encourage>, <correct>, <check>, 等)
new_vocab_size = 151_936 + 16_384 + 20  # ≈ 168,340
qwen.resize_token_embeddings(new_vocab_size)

# 3. 随机初始化新 audio embedding
# 旧 text embedding 权重保持不变
with torch.no_grad():
    qwen.embed_tokens.weight[151_936:] = torch.randn(16_404, 3584) * 0.02

# 4. 适配多流 attention mask
# Moshi 的多流需要 causal attention + cross-stream attention
# Qwen2.5 使用 GQA (num_heads=28, num_kv_heads=4)
# 需要修改 attention mask 以支持：
#   - 学生 audio stream 只能看到过去
#   - Agent text stream 可以看到学生 audio + 自己过去的 text
#   - Agent audio stream 可以看到 text + 学生 audio + 自己过去的 audio
#
# 实现方式: 自定义 attention_mask 生成函数
```

**关键兼容性问题：**
- Qwen2.5 使用 GQA (Grouped Query Attention)，Moshi 原始使用 MHA
- GQA 在多流场景下需要测试是否能正确处理 cross-stream 依赖
- 如有问题，可以将 Qwen2.5 的 KV heads 展开为 full MHA（增加参数量约 20%）

### 5.4 Stage 2: 多流预训练

**目标：** 让模型学会从 text + audio tokens 生成 audio tokens（基本的语音理解和生成能力）。

**子阶段 2a: 单流语音续写（warmup）**

先在单流模式下训练，让新的 audio embedding 学到有意义的表征：
```
输入: [text_prompt] [audio_token_1] [audio_token_2] ... [audio_token_N]
目标: 预测下一个 audio_token
```

```yaml
data:
  sources: 多语言干净音频 (同 Stage 0 数据 + 更多)
  total: ~10,000 hours
  format: 单流，Mimi-ML 编码后的 token 序列

training:
  gpus: 8 × A100
  batch_size: 16h audio / step (参照 Moshi)
  steps: 200,000
  optimizer: AdamW (lr=3e-4 → 2e-5 cosine)
  duration: ~7 days
```

**子阶段 2b: 模拟双流（diarization-based）**

使用 PyAnnote diarization 将多说话人音频分离为双流：
```
输入流 1 (speaker A): [audio_token_A1] [PAD] [audio_token_A3] ...
输入流 2 (speaker B): [PAD] [audio_token_B2] [PAD] ...
Text stream: Whisper 生成的对齐文本

目标: 预测 speaker B 的 audio tokens（模型扮演 speaker B）
```

```yaml
data:
  sources:
    - Fisher (en, 2000h, 已有 diarization)
    - AISHELL-4 (zh, 120h)
    - MLC-SLM (multilingual, 1604h)
    - LibriMix / WSJ0-2mix (模拟多说话人)
  total: ~5,000 hours
  format: 双流，PyAnnote diarization → dual Mimi-ML tokens

training:
  gpus: 8 × A100
  batch_size: 8h audio / step
  steps: 100,000
  duration: ~5 days
```

**Stage 2 合计成本：** 8 × A100 × 12 天 × $3/hr = **~$6,912**

### 5.5 Stage 3: 全双工对话微调

**目标：** 学会真实的 turn-taking、打断、backchannel。

```yaml
data:
  sources:
    - Fisher (en, 2000h) — 核心：真实的全双工电话对话
    - AISHELL-4 (zh, 120h) — 中文会议对话
    - Magic Data CN/JA/KO (60h)
    - 合成多语言对话 (Step 4.2 的子集, ~1000h)
  total: ~3,200 hours
  format: 真正的双通道录音 + 模拟全双工

  # 关键：保留 overlap 区域
  # Fisher 的原始录音包含真实的说话重叠
  # 模型需要学会在 overlap 时同时处理两个流

training:
  gpus: 8 × A100
  batch_size: 8h / step
  steps: 10,000  # PersonaPlex 在这个阶段也只用了 10K 步
  lr: 1e-5 (较低，避免灾难性遗忘)
  duration: ~6-12 hours
```

**成本：** 8 × A100 × 12h × $3/hr = **~$288**

### 5.6 Stage 4: 教学行为微调（核心阶段）

**目标：** 让模型学会语言教学的专业技能 + persona 控制。

```yaml
data:
  sources:
    - 合成教学对话 (Step 4.2), ~4,400 hours
    - 8 种语言, 11,000 个对话脚本
    - 包含教学行为标签 (<recast>, <explain>, 等)
    - 包含 persona text prompt + voice prompt
    - 包含模拟的全双工 overlap / backchannel

  format:
    每个训练样本：
    {
      "text_prompt": "You are Sarah, a 28-year-old English teacher...\n[STUDENT] Level: B1, L1: Chinese\n[TOPIC] Present perfect tense",
      "voice_prompt_tokens": [...],  # 30s 参考音频的 Mimi-ML tokens
      "student_stream_tokens": [...],
      "teacher_stream_tokens": [...],
      "teacher_text_tokens": [...]   # 带教学标签的 inner monologue
    }

training:
  gpus: 8 × A100
  batch_size: 4h / step
  steps: 50,000
  lr: 5e-6
  # 损失权重:
  loss_weights:
    teacher_text: 100    # 强调 inner monologue 质量
    teacher_semantic: 100 # 强调语义 token 准确
    teacher_acoustic: 1   # 声学细节权重低（Depth Transformer 处理）
    student_stream: 0     # 不预测学生 token（只消费）

  # 特殊训练策略：
  # 1. Voice prompt conditioning: 前 30s 参考音频的 tokens 作为 prefix
  # 2. Text prompt: persona + 教学上下文作为 text prefix
  # 3. 教学标签作为 special tokens 参与 loss 计算

  duration: ~3-4 days
```

**成本：** 8 × A100 × 4 天 × $3/hr = **~$2,304**

### 5.7 Stage 5: 对齐（DPO / RLHF）

**目标：** 使用人类偏好数据进一步优化教学质量。

**偏好数据收集：**
1. 让模型生成 200-500 段教学对话
2. 每段对话由 2-3 名语言教师评分
3. 评分维度：
   - 教学准确性（recast 是否恰当、纠错是否自然）
   - 自然度（是否像真人说话）
   - 学生体验（是否鼓励学生多说话）
   - Persona 一致性（是否保持角色）
4. 构建偏好对 (chosen, rejected)

**DPO 训练：**
```yaml
data:
  preference_pairs: ~5,000 对
  format: (text_prompt + student_input, chosen_response, rejected_response)

training:
  gpus: 4 × A100
  steps: 3,000
  lr: 1e-6
  beta: 0.1  # DPO temperature
  duration: ~12 hours
```

**成本：** 4 × A100 × 12h × $3/hr = **~$144** + 人工评估费用 ~$500-1000

---

## 六、计算成本汇总

| 阶段 | GPU 配置 | 时间 | 云成本 |
|------|---------|------|-------|
| Stage 0: Mimi-ML codec | 4 × A100 | 5 天 | $1,440 |
| Stage 1: Backbone 适配 | 无需 GPU | 1 天 | $0 |
| Stage 2a: 单流预训练 | 8 × A100 | 7 天 | $4,032 |
| Stage 2b: 模拟双流 | 8 × A100 | 5 天 | $2,880 |
| Stage 3: 全双工微调 | 8 × A100 | 12 小时 | $288 |
| Stage 4: 教学行为微调 | 8 × A100 | 4 天 | $2,304 |
| Stage 5: DPO 对齐 | 4 × A100 | 12 小时 | $144 |
| **合计训练** | | **~20 天** | **~$11,088** |

| 其他成本 | 金额 |
|---------|------|
| Claude API（脚本生成） | ~$22 |
| CosyVoice 合成（自部署 GPU） | ~$500（租 GPU 跑合成） |
| 数据存储（~10TB 音频） | ~$200/月 |
| 人工评估（DPO 数据） | ~$500-1,000 |
| **合计其他** | **~$1,500** |

### **总成本估算：~$12,000-15,000**

对比：
- Moshi 从零训练：1,016 H100 × 数周 ≈ **$500,000+**
- PersonaPlex fine-tune：8 A100 × 6h ≈ **$144**（但只是英语，没有 codec 重训）
- V3 完整训练：**~$12,000-15,000**（含多语言 codec + 全部微调）

---

## 七、推理部署

### 7.1 推理架构

```
实时推理流程 (每 80ms 一步):

1. 接收学生 24kHz 音频帧 (1920 samples)
2. Mimi-ML encoder → 1 组 tokens (1 semantic + 7 acoustic)
3. 拼接到学生 token 流

4. Temporal Transformer:
   [context + student_token] → predict teacher_text_token
   [context + student_token + text_token] → predict teacher_semantic_token

5. Depth Transformer:
   [teacher_semantic_token] → predict 7 acoustic tokens

6. Mimi-ML decoder:
   [semantic + 7 acoustic] → 1920 samples (80ms audio)

7. 发送到客户端
```

### 7.2 推理延迟预算

```
Mimi-ML encoder:     ~5ms   (Conv + small Transformer)
Temporal Transformer: ~30ms  (7B, KV-cache, 1 step)
Depth Transformer:    ~5ms   (300M, 7 steps)
Mimi-ML decoder:     ~5ms   (TransposeConv + small Transformer)
────────────────────────────
Total per step:       ~45ms  (< 80ms 帧间隔 ✅)
理论延迟:             ~160ms (80ms 帧 + 80ms codec 延迟)
```

### 7.3 硬件要求

| 配置 | 可行性 | 并发 |
|------|--------|------|
| RTX 4090 (24GB) | ✅ FP16 推理 | 1-2 用户 |
| A100 (40GB) | ✅ FP16 推理 | 5-8 用户 |
| A100 (80GB) | ✅ FP16 + batching | 10-15 用户 |

**优化手段：**
- KV-cache（必须）
- FlashAttention 2
- INT8 量化（如果 RTX 4090 显存不足）
- Speculative decoding（Depth Transformer 可用小模型加速）

---

## 八、评估框架

### 8.1 语音质量

| 指标 | 目标 | 测量方法 |
|------|------|---------|
| MOS (Mean Opinion Score) | > 4.0 / 5.0 | 人工评估 |
| MUSHRA | > 65 | 与真人教师对比 |
| Speaker Similarity (voice cloning) | > 0.85 cosine | 与参考音频对比 |

### 8.2 全双工质量

| 指标 | 目标 | PersonaPlex 参考 |
|------|------|-----------------|
| Turn-taking TOR | > 0.90 | 0.908 |
| Turn-taking latency | < 200ms | 170ms |
| Interruption TOR | > 0.95 | 0.950 |
| Interruption latency | < 300ms | 240ms |
| Backchannel 自然度 | MOS > 3.5 | — |

### 8.3 教学质量

| 指标 | 目标 | 测量方法 |
|------|------|---------|
| Recast 使用率 | > 40% of error corrections | 人工标注 |
| i+1 词汇控制 | 词汇超出学生水平 < 10% | 自动词频分析 |
| Student Talking Time | > 50% | 音频分析 |
| 教学准确性 | > 90% | 专业教师评审 |
| Persona 一致性 | > 85% | 声音/性格连续性评审 |

### 8.4 多语言质量

| 指标 | 目标 |
|------|------|
| 每种语言 WER (ASR test) | < 10% |
| 每种语言 CER (TTS test) | < 5% |
| Cross-lingual code-switching | 自然切换无卡顿 |

---

## 九、风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| Mimi-ML 多语言重训效果不达标 | 高 | 备选方案：用 Qwen3-TTS-Tokenizer-12Hz（已经多语言） |
| Qwen2.5 backbone 与 Moshi 多流不兼容 | 高 | 先做兼容性 POC（1-2天），不行就用 Helium + 多语言继续预训练 |
| 合成教学数据质量不足 | 中 | 引入人工审核，用 Claude Sonnet 审查脚本质量 |
| 全双工能力在多语言场景退化 | 中 | Stage 3 增加多语言对话数据比例 |
| 计算成本超预算 | 低 | 分阶段执行，每阶段验证后再继续 |
| 7B 模型知识不如 Claude | 已知 | 这是架构取舍，V2 的 Claude cascade 作为 fallback |

---

## 十、时间线

```
Month 1: 基础设施 + 数据
├── Week 1-2: 数据收集 + 下载公开数据集
├── Week 2-3: 合成数据管道开发（Claude 脚本 + CosyVoice 合成 + 混音）
└── Week 3-4: Stage 0 — Mimi-ML codec 训练

Month 2: 模型训练
├── Week 1: Stage 1 — Backbone 适配 + 兼容性验证
├── Week 1-2: Stage 2a — 单流预训练
├── Week 2-3: Stage 2b — 模拟双流预训练
└── Week 3-4: Stage 3 — 全双工对话微调 + 初步评估

Month 3: 教学能力 + 部署
├── Week 1-2: Stage 4 — 教学行为微调
├── Week 2-3: Stage 5 — DPO 对齐
├── Week 3: 推理优化 + 量化
└── Week 4: 集成到 V2 框架，替换 cascade pipeline

Month 4: 评估 + 迭代
├── 全面评估（语音质量、全双工、教学、多语言）
├── 根据评估结果迭代训练
└── A/B test: V3 vs V2 vs 真人教师
```

---

## 十一、与 V2 的关系

```
V2 (Cascade):  ASR → Claude → TTS  [现在开发，快速上线]
                    ↓ 收集真实用户对话数据
V3 (E2E Model): 端到端全双工       [3-4个月后替代]

V2 的价值：
1. 快速验证教学效果和 prompt 设计
2. 收集真实师生对话数据（极其宝贵的训练数据）
3. 作为 V3 的质量 baseline
4. V3 上线后，V2 作为 fallback
```

V2 运营期间收集的每一段真实对话，都会成为 V3 Stage 3/4 的训练数据。
这是 V2 除了产品价值外的**战略价值**。

---

## 十二、关键参考

| 资源 | 链接 |
|------|------|
| Moshi 论文 | https://arxiv.org/abs/2410.00037 |
| Moshi 代码 | https://github.com/kyutai-labs/moshi |
| PersonaPlex 论文 | https://arxiv.org/abs/2602.06053 |
| PersonaPlex 代码 | https://github.com/NVIDIA/personaplex |
| Qwen2.5-7B | https://huggingface.co/Qwen/Qwen2.5-7B |
| Qwen3-TTS-Tokenizer | https://github.com/QwenLM/Qwen3-TTS |
| XLS-R-300M | https://huggingface.co/facebook/wav2vec2-xls-r-300m |
| Fisher Corpus | https://catalog.ldc.upenn.edu/LDC2004T19 |
| MLC-SLM Challenge | https://arxiv.org/abs/2509.13785 |
| Magic Data | https://magichub.com |
| LightTTS (推理优化) | https://github.com/ModelTC/LightTTS |
| Silero VAD | https://github.com/snakers4/silero-vad |
| CosyVoice 2 | https://github.com/FunAudioLLM/CosyVoice |

---

## 十三、一句话总结

> **在 Moshi 的全双工架构上，换上 Qwen2.5 的多语言大脑和 XLS-R 蒸馏的多语言耳朵，
> 用 Claude 生成的教学对话喂出教学能力 — 总成本 ~$12K，时间 3-4 个月。**
