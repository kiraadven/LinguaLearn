# Content Pack 架构：离线备料 + Runtime 按需生成

## 核心原则

**离线只做备料，runtime 按需生成。**

一个句子可能有 5 个词汇、3 个表达，每个词汇在 graph 中可能经过 explain → practice → check 三个节点。如果离线就对所有节点生成完整教学内容（例句、纠错、语法分析、教学脚本），会产生大量永远不会被用到的内容——因为 graph 是动态的，学生可能跳过某些技能、某些节点可能永远不会被访问。

所以我们拆成两层：

```
离线（markdown_exporter.export_content_pack）
  → 轻量 content_pack.json（元数据 + 媒体锚点 + 干扰项池）

Runtime（ContentPrefetcher.prefetch）
  → 根据 graph 实时位置，提前 2 步生成深度内容
```

---

## 第一层：离线 Content Pack（轻量）

### 入口
`core/learning/markdown_exporter.py` → `MarkdownExporter.export_content_pack()`

### 输出格式（content_pack.json v3）

```json
{
  "version": 3,
  "meta": {
    "job_id": "uuid",
    "source_lang": "en",
    "target_lang": "zh-Hans",
    "generated_at": "ISO timestamp",
    "total_segments": 13,
    "total_skills": 50
  },
  "segments": [
    {
      "index": 0,
      "source_text": "原句英文",
      "translation": "中文翻译",
      "skills": ["vocab_suspect", "vocab_behind_bars", "expr_be_behind_bars"],
      "start_ms": 0,
      "end_ms": 8080,
      "audio_file": "sq_0001.mp3"
    }
  ],
  "skills": {
    "vocab_suspect": {
      "skill_type": "vocabulary",
      "difficulty": 2,
      "depth": "light",
      "segment_index": 0,
      "target_item": {
        "word": "suspect",
        "phonetic": "/səˈspekt/",
        "translation": "嫌疑人",
        "in_context": "原句全文",
        "context_translation": "原句翻译"
      },
      "media_anchors": {"type": "video", "start_ms": 0, "end_ms": 8080},
      "audio_file": "sq_0001.mp3",
      "content_packs": {}
    }
  },
  "word_pool": [
    {"word": "suspect", "translation": "嫌疑人", "difficulty": 2}
  ],
  "expr_pool": [
    {"expression": "be behind bars", "translation": "被关押", "difficulty": 3}
  ],
  "lesson_plan": [
    {"skill": "vocab_suspect", "depth": "light", "skill_type": "vocabulary", "difficulty": 2, "segment_index": 0}
  ]
}
```

### 关键设计
- `content_packs: {}` — 故意留空，由 runtime 填充
- `word_pool` / `expr_pool` — 全局词池，供选择题干扰项使用
- `lesson_plan` — 按段落顺序排列的技能序列，GraphAssembler 消费

---

## 第二层：Runtime ContentPrefetcher（按需深度生成）

### 入口
`ai_tutor/graph/content_connector.py` → `ContentPrefetcher`

### Runtime `node.content_pack` 统一 Schema（v1）

为避免各模块各自假设字段，运行时节点内容统一走：

- `ai_tutor/graph/schema.py` 中 `ContentPack` TypedDict
- `normalize_content_pack(raw, node_type=..., lang_level=..., source_lang=..., target_lang=...)`

核心约定：

- 规范化后总是包含 canonical keys（即使为空值）
- 未知字段不会丢失：会放入 `extras`，并保留在顶层（兼容旧代码）
- `content_pack == {}` 仍表示“尚未生成/尚未填充”，用于 prefetch 判定

canonical keys（节选）：

```json
{
  "schema_version": 1,
  "node_type": "explain",
  "lang_level": "B1",
  "source_lang": "en",
  "target_lang": "zh-Hans",
  "target_item": {},
  "script_outline": [],
  "examples": [{"source": "", "target": ""}],
  "common_mistakes": {
    "l1_transfer": "",
    "correction_strategy": "",
    "error_examples": [{"wrong": "", "correct": "", "explanation": ""}]
  },
  "media_anchors": [],
  "supplementary_links": [{"title": "", "url": ""}],
  "exercises": [],
  "quiz_items": [],
  "extras": {}
}
```

### 触发时机

```
SessionOrchestrator.init_session()
  → prefetcher.prefetch_sync(graph, start_node_id)   # 同步，确保前2个节点有内容

SessionOrchestrator.on_student_input() → advance
  → prefetcher.prefetch(graph, next_node_id)          # 异步，后台预取

SessionOrchestrator.auto_advance()
  → prefetcher.prefetch(graph, next_id)               # 异步
```

### Look-ahead 算法

从当前节点出发，沿 `on_success` / `auto_advance` / `on_minor_error` 边 BFS 前探 2 步。

```python
def _look_ahead(graph, start_id, steps=2):
    # BFS，只跟主干边，不跟 repair/backtrack 边
    # 返回前方可能到达的节点列表
```

**为什么是 2 步？**
- 1 步不够：如果当前节点是 explain，下一步 practice 马上要用内容，但 LLM 生成需要 2-5 秒
- 3 步太多：离 graph mutation 太远，预测可能不准，浪费 token
- 2 步是 latency 和 cost 的平衡点

### 按 node_type 分发提示词

不同类型节点需要的内容完全不同，不应该用同一个巨大提示词：

| node_type | 生成内容 | 大致 token |
|-----------|---------|-----------|
| **explain** | 讲解脚本 + 3 例句 + 搭配 + L1错误 + 记忆技巧 | ~800 |
| **guided_practice** | 2-3 填空题 + 1 纠错题 + 1 翻译题 + scaffolding hints | ~600 |
| **free_practice** | 造句指令 + 参考答案 + 同上 | ~600 |
| **check_understanding** | 1 选择题 + 1 填空题 + 错误后纠正话术 | ~400 |
| **reading_comprehension** | 阅读文本 + 主旨/细节/推断题 + 分层提示 | ~550 |
| **dialogue_practice** | 场景角色设定 + 多轮对话目标 + 修复回合 | ~650 |
| **dictation** | 音频分块听写 + 核对纠错 | ~500 |
| **error_analysis** | 错误回放 + 学生自我分析 + 改写重做 | ~450 |
| **cultural_note** | 文化背景说明 + 跨文化对比 + 情境小题 | ~350 |
| **repair** | 简化讲解 + 类比 + 最简例句 + 母语迁移分析 + 1 微练习 | ~500 |
| **worked_example** | 问题 + 分步骤解答 + 核心要点 | ~400 |
| **review** | 回忆提示 + 简短回顾 + 1 检索练习 | ~300 |
| **hook/transition/wrap_up** | 一句话脚本 | ~100 |

### 不重复生成
- `node.content_pack` 非空 → 跳过
- `self._generating` set 记录正在生成的 node_id → 避免重入

### LLM 选择
- 默认 `deepseek-reasoner`（适合结构化教学内容生成）
- 失败时 fallback 到最小内容（仅含基本信息）

---

## 数据流全景

```
[离线阶段]
WordAnalyzer.batch_analyze()        → sentences_data (词汇+表达+翻译)
MarkdownExporter.export_content_pack() → content_pack.json (轻量元数据)

[Session 初始化]
GraphAssembler.assemble(lesson_plan)  → LessonGraph (节点图，content_pack 为空)
ContentPrefetcher.prefetch_sync()     → 为前 2 个节点生成深度内容

[每轮交互]
on_student_input()
  → assess → mutate graph → policy → voice → advance
  → ContentPrefetcher.prefetch()      → 异步为前方 2 节点预取内容

[节点执行时]
PolicyRuntime 读取 node.content_pack 来决定如何教学
VoiceDispatcher 读取 content_pack 来生成语音
```

---

## 与 Graph 的关系

### GraphAssembler 如何使用 content pack

GraphAssembler 从 `lesson_plan` 构建初始图。每个 plan entry 变成若干节点（explain → practice → check）。节点的 `learning_targets` 指向 skill_id，但 `content_pack` 为空。

### ContentPrefetcher 如何找到技能数据

Prefetcher 初始化时接收完整的 content_pack.json 数据：

```python
prefetcher = ContentPrefetcher(
    llm_client=openai_client,
    content_pack_data=content_pack_json,  # 离线生成的 JSON
)
```

当需要为某个节点生成内容时，通过 `node.learning_targets[0]` 找到 skill_id，再从 content_pack_data 中取 `skills[skill_id].target_item` 作为 LLM 提示词的输入。

### 动态子图的内容

GraphMutator 插入 repair/backtrack/enrichment 子图时，新节点同样 `content_pack` 为空。下一轮 prefetch 会自动覆盖这些新节点（因为它们在前方 2 步内）。

---

## 已知限制和未来改进

1. **LLM 延迟**：deepseek-reasoner 单次调用 ~2-5 秒。如果 graph advance 速度很快（如连续 auto_advance），prefetch 可能来不及。解决：对 non-interactive 节点链做批量预取。

2. **提示词质量**：当前按 node_type 用固定模板。未来可以根据学生 LearnerMemory（L1 语言、错误历史、偏好风格）动态调整提示词。

3. **缓存策略**：当前只在内存中。未来可以将生成的 content 持久化到 Redis/SQLite，跨 session 复用相同 skill + node_type 的内容。

4. **token 成本**：每个节点 ~300-800 tokens 输入，一节课 ~20-40 个节点被访问，总计 ~10K-20K tokens/课。可以接受。
