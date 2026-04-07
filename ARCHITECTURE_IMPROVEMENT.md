# LinguaLearn AI Tutor 架构重构说明

## 概述

这是一个基于 **open-claude-code 的 Skills 系统** 的完整重构，目的是：
- ✨ **提升讲解质量** — 从"平淡机械"到"像经验老道的教师"
- 🎯 **降低 Token 消耗** — 通过质量验证和自动修复避免重复生成
- 📦 **模块化架构** — 5个独立Skill，可以单独使用或组合
- 📚 **知识库驱动** — 所有Agent都基于教学最佳实践

## 核心改进方向

### 1. Skill Chain 架构（而非单一Agent）

**原来**：`ai_lesson.py` 中3层Agent串联在一起，紧耦合

**现在**：5个独立Skill，可组合使用
```
ContentAnalyzer
    ↓
LessonPlanner
    ↓
LessonWriter      ← 核心，融合所有教学知识库
    ↓
QualityValidator
    ↓
ScriptRepair      ← 如需要，自动修复缺陷
```

### 2. 知识库驱动（Reference Files）

**原来**：提示词中硬编码规则，不够具体

**现在**：将教学最佳实践写成知识库文件，Agent在生成时加载

```
core/learning/knowledge_base/
├── teaching_methodology.md           ← 综合教学法论文
├── teacher_principles.md             ← 可操作的优秀教师原则
├── pedagogical_frameworks/
│   ├── clt_principles.md            ← 交际教学法（CLT）
│   ├── scaffolding_guide.md         ← 支架式教学
│   ├── questioning_strategies.md    ← 提问技巧
│   └── lesson_pacing.md             ← 节奏与深度分配
└── quality_checklist.md              ← 质量评估标准

这些文件被加载到Agent的系统提示词中，
让Agent"学习"这些原则，而不是靠硬编码规则。
```

### 3. 质量验证 + 自动修复

**原来**：讲解一次成功率~40%，如果质量差就这样使用

**现在**：
1. 生成脚本
2. QualityValidator 评估（0-100分）
3. 如果 < 80分，ScriptRepair 自动修复
4. 再次验证，直到通过

### 4. 严谨的目录结构

```
core/learning/
├── __init__.py
├── ai_lesson.py                    # 保持原有高级接口（已有）
├── ai_podcast.py                   # 保持原有高级接口（已有）
│
├── agents/                         # ★ 新增：5个Skill实现
│   ├── __init__.py
│   ├── base_agent.py              # 基类：LLM、JSON解析、知识库加载
│   ├── content_analyzer.py        # Skill 1
│   ├── lesson_planner.py          # Skill 2
│   ├── lesson_writer.py           # Skill 3（核心）
│   ├── quality_validator.py       # Skill 4
│   └── script_repair.py           # Skill 5
│
├── knowledge_base/                # ★ 新增：教师知识库（Reference Files）
│   ├── teaching_methodology.md
│   ├── teacher_principles.md
│   ├── pedagogical_frameworks/
│   │   ├── clt_principles.md
│   │   ├── scaffolding_guide.md
│   │   ├── questioning_strategies.md
│   │   └── lesson_pacing.md
│   └── quality_checklist.md
│
├── validators/                    # ★ 新增：验证逻辑
│   ├── __init__.py
│   ├── quality_rules.py           # 质量规则（覆盖率、互动、深度等）
│   └── evaluation_metrics.py      # 评估指标计算
│
├── tools/                         # ★ 新增：工具定义与校验
│   ├── __init__.py
│   ├── lesson_tools.py            # play_sentence, explain_sentence 等
│   └── tool_validators.py         # Pydantic 参数校验
│
└── config/                        # ★ 新增：配置
    ├── __init__.py
    ├── skill_chain_config.py      # Skill链执行顺序、超参数
    └── prompts_config.py          # 所有提示词配置
```

## 关键文件说明

### agents/base_agent.py（基类）

所有Skill继承这个类，获得：
- `load_reference_file()` — 加载知识库
- `_request_json()` — LLM请求 + JSON解析
- `_build_system_prompt()` — 构建融合知识库的系统提示词

### knowledge_base/* （教师知识库）

每个文件都是"教学最佳实践"的具体体现：

| 文件 | 内容 | 用途 |
|------|------|------|
| `teaching_methodology.md` | 现代教学法综合（备课、讲解、互动） | ContentAnalyzer, QualityValidator 参考 |
| `teacher_principles.md` | 优秀教师的5个转变 + 备课框架 | 所有Agent参考 |
| `clt_principles.md` | 交际教学法（CLT）的5大原则 | LessonWriter 的讲解指导 |
| `scaffolding_guide.md` | 支架式教学的4层级 + 实现方法 | LessonWriter 讲解复杂点时参考 |
| `questioning_strategies.md` | 好提问的6特征 + 4层级 + 时机 | LessonWriter 生成提问时参考 |
| `lesson_pacing.md` | 深度分配指南（Light/Standard/Deep） | LessonPlanner 分配深度时参考 |
| `quality_checklist.md` | 评估清单（7个维度，80分及格） | QualityValidator 评估标准 |

### config/skill_chain_config.py

定义Skill链的执行流程和参数：
```python
SKILL_CHAIN_CONFIG = {
    "agents": [
        {"name": "ContentAnalyzer", "temperature": 0.2, ...},
        {"name": "LessonPlanner", "temperature": 0.3, ...},
        {"name": "LessonWriter", "temperature": 0.6, ...},
        {"name": "QualityValidator", "temperature": 0.1, ...},
        {"name": "ScriptRepair", "conditional": True, ...},
    ],
    "thresholds": {
        "quality_score_pass": 80,
        "max_repair_attempts": 2,
    }
}
```

## LessonWriter 的核心改进

这是质量改进的关键环节。原来的 ai_lesson.py:write_lesson() 会变成：

```python
# agents/lesson_writer.py

class LessonWriter(BaseAgent):
    def write(self, content_profile, lesson_plan, audio_files):
        # 1. 加载所有教学知识库
        knowledge = self.load_reference_files([
            "teaching_methodology.md",
            "pedagogical_frameworks/clt_principles.md",
            "pedagogical_frameworks/scaffolding_guide.md",
            "pedagogical_frameworks/questioning_strategies.md",
            "pedagogical_frameworks/lesson_pacing.md",
        ])
        
        # 2. 构建融合知识库的系统提示词
        system_prompt = self._build_system_prompt(
            base_prompt=LESSON_WRITER_BASE_PROMPT,
            reference_files=knowledge,
        )
        
        # 3. 调用 _run_writer_loop（工具调用）
        script = self._run_writer_loop(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tools=LESSON_WRITER_TOOLS,
        )
        
        return script
```

**关键差异**：
- ✓ 系统提示词中包含了 CLT、支架式教学、提问策略等具体指导
- ✓ Agent 不是"凭空生成"，而是"基于最佳实践生成"
- ✓ 讲解中会自然地包含支架、提问、文化背景等高质量元素

## QualityValidator 的工作流程

```python
# agents/quality_validator.py

class QualityValidator(BaseAgent):
    def validate(self, script, lesson_plan):
        # 1. 加载质量清单
        checklist = self.load_reference_file("quality_checklist.md")
        
        # 2. 构建评估提示词
        system_prompt = """
        根据以下清单评估脚本质量：
        {checklist}
        
        评估维度：
        - 整体结构（intro/outline/outro）
        - 讲解质量（meaning/form/use/contrast/culture）
        - 互动质量（提问/反馈/应用）
        - 自然度（不像模板，像真人）
        - 准确完整性
        
        输出：{
            'passed': bool,
            'score': 0-100,
            'issues': [...]
        }
        """
        
        # 3. LLM评估
        result = self._request_json(messages, expected_type=dict)
        
        return result
```

## 实施路线图

### Phase 1（已完成）：知识库建设
- ✅ 研究互联网上"好老师"的教学方法
- ✅ 创建 7 个知识库文件（总 ~8000 字）
- ✅ 设计严谨的目录结构
- ✅ 创建 BaseAgent 基类和配置

### Phase 2（待实施）：实现核心Agents
1. **ContentAnalyzer** — 融合 teaching_methodology.md
2. **LessonPlanner** — 融合 lesson_pacing.md
3. **LessonWriter** — 融合所有教学知识库（最关键）
4. **QualityValidator** — 融合 quality_checklist.md
5. **ScriptRepair** — 自动修复缺陷

### Phase 3（待实施）：集成和优化
1. 修改 ai_lesson.py 调用新的 Skill Chain
2. 创建 Skill Chain 的协调器（orchestrator）
3. 测试质量改进和 Token 消耗优化
4. 对比测试：旧 vs 新架构

## 预期效果

| 指标 | 旧架构 | 新架构 | 改进 |
|------|--------|--------|------|
| 讲解感觉 | 平淡、机械 | 像真人、有深度 | ★★★★★ |
| 质量稳定性 | 40% 一次成功 | 80%+ 通过验证 | ★★★★★ |
| Token 消耗 | 高（重试多） | 中（但质量高） | ★★★★ |
| 代码可维护性 | 单体、难改动 | 模块化、易扩展 | ★★★★ |
| 学生沉浸感 | 低（能感觉到AI） | 高（像有真人教师） | ★★★★★ |

## 使用知识库的原则

1. **加载，不改变** — 知识库是参考，不要在Agent中硬编码相反的逻辑
2. **在提示词中传递** — 加载文件内容 → 融合到系统提示词 → 传给LLM
3. **定期更新** — 如果发现讲解效果差，改进对应的知识库文件，不是改代码
4. **分层次用** — 不同Agent用不同的知识库文件，避免冗余

## 与 open-claude-code 的对标

| 概念 | open-claude-code | LinguaLearn AI Tutor |
|------|-------------------|----------------------|
| **Skill** | 独立的Agent（记住、简化等） | ContentAnalyzer, LessonWriter 等 |
| **Reference Files** | Skill 中的 `files` 字典 | knowledge_base/ 目录（大量教学文档） |
| **知识库** | 例子、模板、数据 | 教学法论文、最佳实践、评估标准 |
| **Validation** | 不显式做验证 | 有专门的 QualityValidator |
| **Self-repair** | 不自动修复 | ScriptRepair Agent |

## 下一步工作

1. **实现 LessonWriter** — 核心环节，决定质量
   - 加载知识库文件
   - 改进系统提示词
   - 测试讲解质量

2. **实现 QualityValidator + ScriptRepair** — 质量保障
   - 定义评估标准（基于 quality_checklist.md）
   - 自动修复逻辑

3. **集成和优化**
   - 修改 ai_lesson.py 调用新架构
   - 性能测试：时间、Token、质量

4. **验证效果**
   - 对比测试：旧 vs 新讲解
   - 用户反馈收集

---

## 文件清单

已创建的文件：
- ✅ knowledge_base/teaching_methodology.md
- ✅ knowledge_base/teacher_principles.md
- ✅ knowledge_base/pedagogical_frameworks/clt_principles.md
- ✅ knowledge_base/pedagogical_frameworks/scaffolding_guide.md
- ✅ knowledge_base/pedagogical_frameworks/questioning_strategies.md
- ✅ knowledge_base/pedagogical_frameworks/lesson_pacing.md
- ✅ knowledge_base/quality_checklist.md
- ✅ agents/base_agent.py
- ✅ agents/{content_analyzer, lesson_planner, lesson_writer, quality_validator, script_repair}.py （占位符）
- ✅ config/skill_chain_config.py
- ✅ config/prompts_config.py

待创建的文件：
- [ ] validators/quality_rules.py
- [ ] validators/evaluation_metrics.py
- [ ] tools/lesson_tools.py
- [ ] tools/tool_validators.py
- [ ] 各 Agent 的完整实现
