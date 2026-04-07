# Skill Chain 集成指南

## 概述

`SkillChainOrchestrator` 是新的端到端讲课脚本生成系统，综合了5个专业Agent的协作。

## 系统架构

```
ContentAnalyzer    → 分析内容类型、难度、风格
         ↓
LessonPlanner      → 逐句规划讲解策略（深度、重点、互动机会）
         ↓
LessonWriter       → 工具调用驱动生成讲解脚本（核心Agent）
         ↓
QualityValidator   → 评估脚本质量（7维度评分）
         ↓
ScriptRepair       → 条件执行：如果质量<80分，自动修复
         ↓
Success (score ≥ 80)
```

## 快速开始

### 1. 基础用法

```python
from core.learning.agents import SkillChainOrchestrator

orchestrator = SkillChainOrchestrator()

result = orchestrator.generate_lesson(
    md_content="# Video Transcript\nHere's the content...",
    segments=[
        {"text": "Sentence 1", "start_time": 0.0, "end_time": 2.5},
        {"text": "Sentence 2", "start_time": 2.5, "end_time": 5.0},
    ],
    source_lang="en",
    target_lang="zh-Hans",
)

print(f"Success: {result['success']}")
print(f"Score: {result['validation_result']['score']}")
print(f"Script length: {len(result['lesson_script'])} instructions")
```

### 2. 保存中间结果

```python
result = orchestrator.generate_lesson_and_save(
    md_content=md_content,
    segments=segments,
    output_dir=Path("./output"),
    source_lang="en",
    target_lang="zh-Hans",
)
```

输出文件：
- `content_profile.json` - 内容分析结果
- `lesson_plan.json` - 逐句规划
- `lesson_script.json` - 生成的脚本
- `validation_result.json` - 质量评估结果
- `metadata.json` - 执行元数据

## 输出格式

### content_profile (dict)
```json
{
  "content_type": "news|vlog|drama_movie|interview|lecture_educational|podcast_talk|other",
  "estimated_cefr": "A1-C2",
  "register": "formal|semi_formal|casual|mixed",
  "dominant_themes": ["theme1", "theme2"],
  "speaker_profile": "描述说话人",
  "teaching_focus_priority": ["vocabulary", "grammar", "cultural_context"],
  "tone_for_teacher": "warm_casual|encouraging_professional|analytical_academic"
}
```

### lesson_plan (list of dict)
```json
[
  {
    "sentence_id": 0,
    "sentence_text": "原始句子",
    "depth": "light|standard|deep",
    "focus_items": ["word1", "phrase2"],
    "grammar_point": "语法点或null",
    "cultural_note": "文化背景或null",
    "pronunciation_note": "发音技巧或null",
    "replay_after_explain": true,
    "insert_question_after": false,
    "insert_summary_after": false
  }
]
```

### lesson_script (list of dict)
脚本由多种指令类型组成：

```json
[
  {
    "type": "speak",
    "subtype": "intro",
    "sentence_id": null,
    "text": "课程开场..."
  },
  {
    "type": "play",
    "sentence_id": 0,
    "label": "来听一遍原句"
  },
  {
    "type": "speak",
    "subtype": "explanation",
    "sentence_id": 0,
    "text": "这句话的意思是..."
  },
  {
    "type": "question",
    "sentence_id": 0,
    "question_type": "comprehension",
    "text": "你怎么理解这句话？",
    "answer_hint": "提示..."
  },
  {
    "type": "speak",
    "subtype": "outro",
    "sentence_id": null,
    "text": "课程结尾..."
  }
]
```

指令类型：
- `play`: 播放原始音频
- `speak`: 讲解（包括多个subtype）
  - `explanation`: 主要讲解
  - `grammar`: 语法详解
  - `culture`: 文化背景
  - `usage`: 用法示例
  - `pronunciation`: 发音技巧
  - `transition`: 过渡语句
  - `summary`: 阶段总结
  - `intro/outro`: 课程开场/结尾
- `question`: 互动提问

### validation_result (dict)
```json
{
  "passed": true,
  "score": 85.3,
  "dimension_scores": {
    "structure": 100,
    "coverage": 95,
    "interaction": 80,
    "deep_coverage": 85,
    "natural_tone": 75,
    "pacing": 90,
    "accuracy": 100
  },
  "issues": ["可能的问题1", "可能的问题2"],
  "suggestions": ["改进建议1", "改进建议2"]
}
```

## 配置和定制

### 自定义配置

```python
config = {
    "max_repair_attempts": 3,  # 默认2
    "quality_pass_threshold": 85,  # 默认80
}

orchestrator = SkillChainOrchestrator(config=config)
```

### 指定模型

```python
orchestrator = SkillChainOrchestrator(model="gpt-4-turbo")
```

## 与现有 ai_lesson.py 的对比

### 新系统优势

| 方面 | 旧系统 | 新系统 |
|------|------|------|
| 架构 | 单体 3层 | 模块化 5个Agent |
| 知识库 | 硬编码在提示词 | 可维护的 markdown 文件 |
| 质量保证 | 仅生成 | 生成+评估+自动修复 |
| 调试能力 | 整体输出 | 每步可追踪 |
| 重用性 | 单用途 | 每个Agent可独立使用 |
| 质量目标 | ~40% 首次通过 | 目标 80%+ 首次/修复通过 |

### 逐步迁移

#### 步骤1：并行测试
```python
# 旧系统
old_result = old_ai_lesson.generate(md_content, segments)

# 新系统
new_result = orchestrator.generate_lesson(md_content, segments)

# 比较质量
compare_quality(old_result, new_result)
```

#### 步骤2：替换生成逻辑
在 api.py 中，可以添加新的端点：
```python
@app.post("/api/lessons/v2")
def generate_lesson_v2(request: LessonRequest):
    orchestrator = SkillChainOrchestrator()
    result = orchestrator.generate_lesson(
        md_content=request.content,
        segments=request.segments,
    )
    return result
```

#### 步骤3：监控指标
收集指标对比：
- 质量分数分布
- 首次通过率
- 修复成功率
- Token 消耗
- 执行时间

## 故障排除

### 问题：LLM 调用失败
```
ModuleNotFoundError: No module named 'openai'
```
**解决方案**：确保 OpenAI SDK 已安装
```bash
pip install openai
```

### 问题：知识库文件未找到
```
[Agent] 知识库文件不存在: teaching_methodology.md
```
**解决方案**：检查 `core/learning/knowledge_base/` 目录，确保所有 markdown 文件存在。

### 问题：脚本质量分数持续低于 80
**排查步骤**：
1. 检查 `validation_result['issues']` 了解具体问题
2. 查看 `dimension_scores` 找出最弱的维度
3. 对应知识库文件可能需要更新或增强
4. 可以增加 `max_repair_attempts` 给修复更多机会

## 测试

### 快速测试脚本

```python
# test_skill_chain.py
from pathlib import Path
from core.learning.agents import SkillChainOrchestrator

def test_basic_generation():
    orchestrator = SkillChainOrchestrator()
    
    segments = [
        {"text": "Hello, how are you?", "start_time": 0, "end_time": 2},
        {"text": "I'm doing well.", "start_time": 2, "end_time": 4},
        {"text": "What about you?", "start_time": 4, "end_time": 6},
    ]
    
    result = orchestrator.generate_lesson_and_save(
        md_content="Sample dialogue",
        segments=segments,
        output_dir=Path("./test_output"),
    )
    
    assert result['success'], f"Failed: {result['validation_result']['issues']}"
    assert result['validation_result']['score'] >= 80
    print(f"✓ Test passed. Score: {result['validation_result']['score']}")

if __name__ == "__main__":
    test_basic_generation()
```

运行测试：
```bash
python test_skill_chain.py
```

## 下一步

1. **集成到 API**：在 api.py 中添加 `/api/lessons/v2` 端点
2. **监控和对比**：收集新旧系统的质量指标
3. **逐步迁移**：当新系统稳定且性能更好时，逐步替换旧系统
4. **知识库优化**：根据实际使用情况持续改进教学知识库文件
5. **Agent 微调**：根据反馈调整各个Agent的温度和提示词
