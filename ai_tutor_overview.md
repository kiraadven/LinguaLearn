# AI Tutor 商业化课堂系统方案 v4

## 当前目标

- 离线备课生成节点模板库和 content pack
- Runtime 实时组装、持续变异 lesson graph
- 自研端到端语音模型直接从课堂状态生成语音（非 TTS）
- Teaching policy 规则驱动，LLM 只处理异常
- WebSocket 实时推送图状态到前端

---

## 一、总架构

### 1. 离线备课线

离线阶段准备：

- **节点模板库** (`ai_tutor/graph/templates/`) — 多粒度 YAML 模板（micro/standard/macro）
- **content pack** — 网站生成的 md/json 教学材料
- **policy package** — 教学策略规则集
- **persona config** — 教师人格配置
- **media/material anchors** — 视频和材料锚点

离线只做"备料"，不生成固定的课堂流程图。

### 2. 在线 Runtime

Runtime 负责：

1. 从模板库 **实时组装** lesson graph（GraphAssembler）
2. 每个回合根据记忆层信号 **动态变异** 图（GraphMutator）
3. **规则级联** 选择 policy action + tool action + delivery style
4. **自思考语音模型** 直接生成教师语音（不经过文本）
5. WebSocket **实时推送** 图状态到前端
6. 异常时 **LLM supervisor 兜底**

主链路：

```
student input -> assessment -> memory update -> graph mutation
  -> policy select -> voice model -> audio output
  -> graph advance -> WS broadcast
```

### 3. 异常处理线

只有正常 policy 无法覆盖时，才触发 LLM supervisor：
- `no_valid_transition` — 当前 node 没有合适转移路径
- `policy_conflict` — 两条规则冲突
- `unsupported_student_behavior` — 超出预设的学生行为
- `repeated_failure_over_budget` — 连续失败超限
- `emotional_drop` — 学生明显挫败
- `safety_or_sensitive_case` — 安全/敏感话题

LLM supervisor 生成文本 → TTS fallback 生成语音。

---

## 二、Dynamic Lesson Graph

### 1. 核心思想：混合构建

- **离线**：准备多粒度节点模板 + content pack
- **Runtime**：根据 learner profile + 记忆层信号，从模板库中选取、实例化、连接成 live graph
- 图在课堂中**持续变异**：插入子图、调整边权、激活/跳过节点

### 2. 数据结构

#### NodeTemplate（离线模板，YAML）

```yaml
template_id: explain_grammar_v1
node_type: explain              # 10种: hook, explain, worked_example,
                                #       guided_practice, free_practice,
                                #       check_understanding, repair, review,
                                #       transition, wrap_up
granularity: standard           # micro (1-2 turns) | standard (3-5) | macro (compound)
phase: present                  # intro | present | practice | produce | review
teacher_goal_template: "Help student understand {{skill}}"
expected_evidence_types: [corrected_sentence, rule_explanation]
allowed_policy_actions: [ask_open, hint_light, re_explain_brief, encourage]
allowed_tool_actions: [open_material_section, highlight_material]
default_delivery_style: neutral_teach
content_pack_slots: [script_outline, examples, common_mistakes]
failure_budget: 2
success_threshold: student_correct_once
tags: [grammar]
```

#### LiveNode（运行时实例）

NodeTemplate 实例化后生成，附加运行时状态：

- `visit_count`, `success_count`, `failure_count`
- `status`: pending | active | completed | skipped | resumed
- `content_pack`: 已解析的具体教学内容
- `subgraph_origin`: 标记此节点属于哪个动态插入的子图

#### EdgeSpec（有向边）

```
source_id → target_id
event: on_success | on_minor_error | on_major_error | on_silence | on_off_topic | on_backtrack | auto_advance
weight: float (越低越优先，cost 语义)
priority: int (同 event 多条边时取高优先)
conditions: dict (可选 guard)
```

### 3. LessonGraph（NetworkX DiGraph 封装）

核心操作：

- `add_node(LiveNode)` / `add_edge(EdgeSpec)` — 构建
- `resolve_transition(node_id, event, context)` — 选最佳目标节点
- `advance_to(target_id)` — 移动游标
- `insert_subgraph(SubgraphSpec, attach_after, return_to)` — 动态插入子图
- `drain_mutations()` — 返回变异日志给 WS 广播
- 每次变异 `_version++`，WS 用 version 做增量同步

### 4. 子图动态插入

4 种子图类型：

| 类型 | 触发条件 | 结构 |
|------|---------|------|
| **repair** | 学生技能失败 ≥2 次 | explain → practice → check |
| **backtrack** | 学生回溯旧内容 | review_recall → review_check |
| **enrichment** | 学生掌握度 >0.85 | challenge → free_practice |
| **assessment** | 需多技能微测 | quiz_1 → quiz_2 → summary |

#### Backtrack 示例

学生在 node_007，突然问起 node_003 的内容：

1. `SubgraphFactory.build_backtrack_subgraph(skill, "node_003")`
   → 生成 [backtrack_review → backtrack_check]
2. `graph.insert_subgraph(subgraph, attach_after="node_007", return_to="node_007")`
   → 添加 node_007 → backtrack_review → backtrack_check → node_007 路径
3. 游标移到 backtrack_review，完成后回到 node_007（resumed 状态）

机械步骤：
1. 移除 attach_after → return_to 直接边
2. 添加子图所有节点到 G
3. 添加入口边：attach_after → subgraph.entry
4. 添加出口边：subgraph.exit → return_to
5. 添加子图内部边

### 5. 边权重计算

语义：**越低越优先**（cost）

| 信号 | 影响 |
|------|------|
| mastery 高 | on_success 边权降低 → 倾向前进 |
| consecutive_failures 高 | repair 边权降低 → 倾向进入修复 |
| fatigue 高 | encourage/break 边权降低 |
| engagement 低 | interactive 类型边权降低 |
| time_pressure 高 | enrichment 边权升高 |

### 6. Content Connector

节点内容解析优先级：
1. **离线 content pack**（md/json，网站生成）— 始终首选
2. **缓存 web search 结果**
3. **实时 web search**（async + timeout fallback）

也连接到 policy 文档：学生触发特殊情况时检索处理方案。

### 7. Graph Assembly（初始图构建）

从离线课程计划 → LessonGraph：
1. 按 skill 和 depth 分段
2. 每段选取匹配的 NodeTemplate
3. 构建线性主干：hook → explain* → practice* → wrap_up
4. 添加分支边：on_success → next, on_error → repair, on_silence → hint
5. 解析每个节点的 content pack

---

## 三、Action Schema

老师行为拆成 3 层：

### 1. Policy Action（教学意图）

16 个核心动作，跨学科复用：

- `ask_open` — 开放提问
- `ask_check` — 快速确认理解
- `ask_recall` — 让学生回忆
- `hint_light` — 轻提示
- `hint_strong` — 强提示
- `re_explain_brief` — 简短重讲
- `re_explain_simplify` — 降低难度重讲
- `give_example` — 给标准例子
- `compare_contrast` — 对比正误
- `direct_correct` — 直接纠正
- `scaffold_step` — 拆成小步
- `backtrack` — 回到前一节点
- `advance` — 前进
- `encourage` — 稳定情绪
- `pause_wait` — 给思考时间
- `wrap_up` — 阶段收束

### 2. Tool Action（课堂工具）

视频类: `pause_video`, `resume_video`, `rewind_video_5s`, `rewind_video_10s`, `seek_video_anchor`
材料类: `open_material_section`, `flip_material_page`, `highlight_material`, `zoom_material`
音频类: `play_reference_audio`, `replay_student_audio`
控制类: `mark_checkpoint`, `trigger_micro_quiz`, `save_lesson_note`, `pin_common_error`

### 3. Delivery Style（说话风格）

10 种预设，映射到语音模型参数：

| 风格 | 语速 | 停顿 | 重音 | 情绪 | 语调变化 |
|------|------|------|------|------|---------|
| neutral_teach | 1.0 | 中 | 中 | 低 | 中 |
| warm_encourage | 0.95 | 略多 | 较强 | 中高 | 较丰富 |
| gentle_corrective | 0.9 | 多 | 中 | 中 | 平稳 |
| firm_corrective | 0.85 | 多 | 强 | 低 | 平稳 |
| slow_repair | 0.75 | 很多 | 较强 | 低 | 平稳 |
| energetic_advance | 1.1 | 少 | 中 | 中高 | 丰富 |
| curious_probe | 0.95 | 多 | 中 | 中 | 很丰富 |
| surprised_react | 1.05 | 中 | 很强 | 高 | 很丰富 |
| celebrate_success | 1.05 | 略少 | 强 | 高 | 丰富 |
| calm_reset | 0.85 | 多 | 低 | 低 | 平缓 |

一个完整回合输出：

```json
{
  "policy_action": "hint_light",
  "tool_action": "rewind_video_5s",
  "delivery_style": "gentle_corrective"
}
```

---

## 四、Policy Runtime（规则级联）

替代旧的 RuleBasedPolicy，图感知的规则级联决策：

1. 读取当前 LiveNode 的 `allowed_actions`
2. 结合 HotMemory（fatigue, engagement, repair_mode）
3. 规则级联：
   - fatigue > 0.7 → `encourage` + `calm_reset`
   - repair_mode → 受限 repair actions + `slow_repair`
   - 学生正确 → `advance` + `energetic_advance` / `celebrate_success`
   - 学生错误且 < budget → `hint_light` / `ask_recall` + `curious_probe`
   - 学生错误且 ≥ budget → `direct_correct` + `firm_corrective`
   - silence → `pause_wait` / `encourage` + `warm_encourage`
4. 输出 `(policy_action, tool_action, delivery_style)`

LLM 不参与此决策链。

---

## 五、老师记忆层

### 4 层结构

| 层 | 生命周期 | 核心职责 |
|---|---------|---------|
| **HotMemory** | 每轮重建 | 当前 node、allowed actions、最近 3-5 轮对话、media 位置、repair 状态 |
| **LessonMemory** | 单节课 | 已访问 node 路径、每个 node 成败、已覆盖技能、错误日志、已给过的解释/例子 |
| **LearnerMemory** | 跨课程 | 技能掌握度、高频错误、卡点 node 类型、节奏/提示偏好、复习历史 |
| **TeacherControlMemory** | 单节课 | persona 参数、默认 style、允许的工具、禁用表达、supervisor 介入记录 |

### 关键接口：`get_graph_mutation_signals()`

交叉查询 4 层，输出驱动 GraphMutator 的信号：

```python
{
    "should_repair": bool,        # 学生连续失败 ≥2
    "repair_skill": str,
    "should_backtrack": bool,     # 学生问起旧内容
    "backtrack_target": str,
    "backtrack_skill": str,
    "should_enrich": bool,        # 学生掌握度 >0.85
    "enrich_skill": str,
    "should_slow_down": bool,     # fatigue >0.7
    "edge_weight_adjustments": [{"source", "target", "delta"}],
    "fatigue": float,
    "engagement": float,
    "mastery": {"skill_id": float},
    "consecutive_failures": int,
    "error_severity": float,
    "time_pressure": float,
}
```

### 记忆写入原则

- 原始长文本不无限堆积
- 回合结束写结构化摘要
- lesson 结束后压缩成 learner memory（`compress_lesson_to_learner`）
- 只保留对下一次决策有帮助的信息

---

## 六、Self-Thinking Voice Model（概要）

> 完整研发计划见 `ai_tutor/voice_model_rd_plan.md`

### 核心理念

这不是 TTS。正常流程（95%+ 回合）：

```
graph_state + persona + delivery_style + context → VoiceModel → audio
（无文本中间步骤）
```

异常回退（<5%）：

```
LLM supervisor → text → TTS adapter → audio
```

### 模型架构

```
Structured Encoder → Thinking Module → Speech Decoder → Vocoder
     (context)        (planning)        (audio gen)     (waveform)
```

- **Structured Encoder**: ~30 个字段（graph state + policy + student state + persona + delivery style + content embeddings）→ 1024d condition vector
- **Thinking Module**: 核心创新。自回归 transformer 生成 planning tokens（非文本），表示"说什么 + 怎么说"
- **Speech Decoder**: V1 自回归 audio token decoder，V2 考虑 flow-matching
- **Vocoder**: audio tokens → PCM waveform

### Persona 维护

PersonaManager 维护：
- **固定身份**（会话内不变）：voice embedding, gender, accent, speaking rate
- **固定人格**（会话内不变）：warmth, formality, humor, patience, energy
- **动态状态**（每几轮更新）：emotion, energy_level（缓降）, rapport_level（渐增）
- **跨会话一致性**：固定身份存入 LearnerMemory，同一学生始终听到同一老师

---

## 七、WebSocket 协议

### Server → Client

| 消息类型 | 触发时机 | 内容 |
|---------|---------|------|
| `graph_full_state` | 首次连接/重连 | 全量图快照（nodes, edges, current_node, progress） |
| `graph_diff` | 每次图变异后 | 增量变异列表（add_node, insert_subgraph, move_cursor, update_edge_weight） |
| `node_active` | 游标移动时 | 当前节点详情（teacher_goal, expected_evidence, delivery_style） |
| `turn_result` | 每个回合后 | 回合结果（teacher_action, tool_action, delivery_style, audio_url） |

### Client → Server

| 消息类型 | 内容 |
|---------|------|
| `student_input` | ASR text + audio_features |
| `request_full_state` | 请求全量同步 |

---

## 八、Session Orchestrator（主循环）

### Hot Path: `on_student_input()`

```
student_text
  → AssessmentEngine.evaluate()
  → MemoryManager.apply_assessment()
  → MemoryManager.get_graph_mutation_signals()
  → GraphMutator.apply_mutations()    → WS broadcast_diff
  → [check supervisor escalation?]
  → PolicyRuntime.select_action()     → (action, tool, style)
  → VoiceDispatcher.dispatch()        → audio
  → graph.resolve_transition()        → advance_to(next_node)
  → WS broadcast_node_active + turn_result
```

### Auto-Advance（无学生响应时）

- 非交互节点（explain, transition, hook）→ 自动前进
- 交互节点（practice, check）→ 生成提示/鼓励，延长等待

---

## 九、目录结构

```
ai_tutor/
├── graph/
│   ├── schema.py              # NodeTemplate, LiveNode, EdgeSpec, SubgraphSpec, VoiceModelInput
│   ├── node_templates.py      # NodeTemplateLibrary (YAML 加载 + 索引)
│   ├── graph_engine.py        # LessonGraph (NetworkX DiGraph)
│   ├── graph_mutator.py       # GraphMutator (记忆信号 → 图变异)
│   ├── subgraph_factory.py    # SubgraphFactory (repair/backtrack/enrichment/assessment)
│   ├── edge_weights.py        # EdgeWeightComputer
│   ├── content_connector.py   # ContentConnector (content pack + web search)
│   ├── graph_assembler.py     # GraphAssembler (离线计划 → 初始图)
│   ├── ws_protocol.py         # WebSocket 消息 schema
│   ├── ws_server.py           # FastAPI WebSocket endpoint
│   └── templates/             # 离线 YAML 节点模板
├── runtime/
│   ├── memory.py              # 4 层记忆 (Hot, Lesson, Learner, TeacherControl)
│   ├── policy_runtime.py      # 图感知规则级联 policy
│   ├── assessment.py          # 启发式学生评估
│   └── session_orchestrator.py # 主循环
├── voice/
│   ├── schema.py              # VoiceModelInput, AudioOutput
│   ├── persona.py             # PersonaState, PersonaManager, DELIVERY_STYLE_MAP
│   ├── dispatcher.py          # VoiceDispatcher (正常/异常路由)
│   ├── model/                 # 自思考语音模型架构
│   ├── fallback/              # LLM text → TTS 降级
│   ├── training/              # 训练 pipeline
│   ├── data_collection/       # 语音数据收集
│   └── evaluation/            # 语音质量评估
├── inference/
│   └── session_manager.py     # 会话状态管理
└── data/                      # 离线数据
```
