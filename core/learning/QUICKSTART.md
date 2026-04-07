# Skill Chain 快速开始指南

## 30秒快速演示

```python
from core.learning.agents import SkillChainOrchestrator
from pathlib import Path

# 1. 初始化
orchestrator = SkillChainOrchestrator()

# 2. 准备数据
segments = [
    {"text": "Hello, how are you?", "start_time": 0, "end_time": 2},
    {"text": "I'm doing well!", "start_time": 2, "end_time": 4},
]

# 3. 生成
result = orchestrator.generate_lesson(
    md_content="Sample dialogue",
    segments=segments,
    source_lang="en",
    target_lang="zh-Hans",
)

# 4. 查看结果
print(f"成功: {result['success']}")
print(f"质量: {result['validation_result']['score']}/100")
```

## 系统流程 (5步)

```
Step 1: ContentAnalyzer    分析内容 (2秒)
  ↓
Step 2: LessonPlanner      规划课程 (3秒)
  ↓
Step 3: LessonWriter       生成脚本 (10-15秒) ← 最耗时
  ↓
Step 4: QualityValidator   评估质量 (5秒)
  ↓
Step 5: ScriptRepair       修复(可选) (5-10秒 × 修复次数)

总耗时: 25-45秒 (取决于长度和修复次数)
```

## API 使用

### 生成讲课脚本
```python
result = orchestrator.generate_lesson(
    md_content: str,              # 视频内容（markdown）
    segments: List[Dict],         # 句子列表：[{"text": "...", "start_time": 0, "end_time": 2}]
    source_lang: str = "en",      # 源语言（要学的）
    target_lang: str = "zh-Hans", # 目标语言（学生母语）
)
```

### 保存到文件
```python
result = orchestrator.generate_lesson_and_save(
    md_content=md_content,
    segments=segments,
    output_dir=Path("./output"),  # 输出目录
    source_lang="en",
    target_lang="zh-Hans",
)

# 输出 5 个 JSON 文件：
# - content_profile.json
# - lesson_plan.json
# - lesson_script.json
# - validation_result.json
# - metadata.json
```

## 理解输出

### 1. 内容分析 (content_profile)
```json
{
  "content_type": "news",  // 内容类型
  "estimated_cefr": "B1",  // 难度（A1-C2）
  "register": "formal",    // 正式程度
  "teaching_focus_priority": ["vocabulary", "grammar"]
}
```

### 2. 课程规划 (lesson_plan)
```json
[
  {
    "sentence_id": 0,
    "depth": "deep",              // light/standard/deep
    "focus_items": ["important"],
    "grammar_point": "present tense",
    "replay_after_explain": true
  }
]
```

### 3. 生成脚本 (lesson_script) ← 最重要！
```json
[
  {"type": "speak", "subtype": "intro", "text": "课程开场"},
  {"type": "play", "sentence_id": 0, "label": "来听原句"},
  {"type": "speak", "subtype": "explanation", "text": "讲解"},
  {"type": "question", "sentence_id": 0, "text": "提问"},
  {"type": "speak", "subtype": "outro", "text": "课程结尾"}
]
```

**脚本类型**：
- `play`: 播放原始音频
- `speak`: 讲解（包括多个子类型）
- `question`: 互动提问

### 4. 质量评估 (validation_result)
```json
{
  "passed": true,
  "score": 85.3,
  "dimension_scores": {
    "structure": 100,      // 结构（intro/outro）
    "coverage": 95,        // 覆盖率（所有句子）
    "interaction": 80,     // 互动（问题/总结频率）
    "deep_coverage": 85,   // 深度讲解质量
    "natural_tone": 75,    // 自然度
    "pacing": 90,          // 节奏感
    "accuracy": 100        // 准确性
  },
  "issues": ["可能的问题"],
  "suggestions": ["改进建议"]
}
```

**通过标准**: score ≥ 80

### 5. 元数据 (metadata)
```json
{
  "total_attempts": 1,           // 总尝试次数（生成+修复）
  "repair_attempts": 0,          // 修复次数（0-2）
  "final_score": 85.3,
  "execution_time": 35.2         // 秒
}
```

## 常见场景

### 场景 1: 快速生成，不保存
```python
result = orchestrator.generate_lesson(md_content, segments)
script = result['lesson_script']
# 直接使用脚本
```

### 场景 2: 保存中间结果，调试
```python
result = orchestrator.generate_lesson_and_save(
    md_content, segments, Path("./debug")
)
# 检查 content_profile.json 了解内容分析结果
# 检查 lesson_plan.json 了解规划策略
# 检查 validation_result.json 了解质量问题
```

### 场景 3: 定制配置
```python
config = {
    "max_repair_attempts": 3,        # 增加修复次数
    "quality_pass_threshold": 85,    # 提高通过标准
}

orchestrator = SkillChainOrchestrator(model="gpt-4", config=config)
result = orchestrator.generate_lesson(md_content, segments)
```

### 场景 4: 只使用某个Agent
```python
from core.learning.agents import ContentAnalyzer

analyzer = ContentAnalyzer()
profile = analyzer.analyze(md_content, segments)
# 只进行内容分析
```

## 调试技巧

### 1. 检查内容分析是否正确
```python
print(f"Content type: {result['content_profile']['content_type']}")
print(f"CEFR: {result['content_profile']['estimated_cefr']}")
```
如果不对，可能需要修改 knowledge_base/teaching_methodology.md

### 2. 检查规划是否合理
```python
plan = result['lesson_plan']
deep = sum(1 for s in plan if s['depth'] == 'deep')
print(f"深度句占比: {deep}/{len(plan)} = {deep*100//len(plan)}%")
```
应该接近 20%（根据 lesson_pacing.md 设定）

### 3. 检查脚本质量
```python
dims = result['validation_result']['dimension_scores']
worst = min(dims.items(), key=lambda x: x[1])
print(f"最弱维度: {worst[0]} = {worst[1]}")
```
如果某个维度很低，查看对应的建议

### 4. 启用详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# 运行生成，会看到详细日志
```

## 常见问题

**Q: 为什么第一次修复失败了？**
A: 这是正常的。有些问题需要2次修复才能解决。检查最终分数，如果≥80就说明成功了。

**Q: 如何提高质量分数？**
A: 
1. 检查 `issues` 和 `suggestions`
2. 对应的问题，修改相关知识库文件
3. 重新运行测试

**Q: 生成速度太慢？**
A: 
1. LessonWriter 使用工具调用，速度最慢
2. 长脚本（>20句）会更慢
3. 可以用更快的模型（如 gpt-4-turbo 改用 gpt-3.5-turbo）

**Q: 如何保留生成的脚本？**
A: 
```python
result = orchestrator.generate_lesson_and_save(..., output_dir=Path("./saved"))
# 所有结果保存到 ./saved/ 目录
```

**Q: 脚本为什么没有音频？**
A: 脚本只包含**指令**，不包含 TTS 音频。使用者需要：
1. 调用 TTS 服务（MiniMax/OpenAI/ElevenLabs）生成音频
2. 或使用原视频的音频段落

## 下一步

- [ ] 在真实数据上测试 (`test_skill_chain.py`)
- [ ] 集成到 API (`/api/lessons/v2`)
- [ ] 收集质量指标，对比旧系统
- [ ] 根据反馈优化知识库
- [ ] 完全迁移替换旧 ai_lesson.py

## 相关文档

- **详细集成指南**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- **完整实现总结**: 见 memory 中的 project_skill_chain_completion.md
- **测试脚本**: [test_skill_chain.py](test_skill_chain.py)
- **知识库文件**: `core/learning/knowledge_base/`

---

**最后更新**: 2026年4月
**系统版本**: 1.0 (核心功能完整)
