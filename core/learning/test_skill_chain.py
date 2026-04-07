"""
Skill Chain 快速测试脚本

演示如何使用 SkillChainOrchestrator 生成高质量的讲课脚本。
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.learning.agents import SkillChainOrchestrator


def test_basic_generation():
    """基础测试：生成一个简单对话的讲课脚本"""

    print("\n" + "="*70)
    print("Skill Chain 快速测试")
    print("="*70)

    # 定义测试句子
    segments = [
        {
            "text": "Hello, how are you doing today?",
            "start_time": 0.0,
            "end_time": 2.5,
        },
        {
            "text": "I'm doing great, thanks for asking!",
            "start_time": 2.5,
            "end_time": 5.0,
        },
        {
            "text": "How's your family?",
            "start_time": 5.0,
            "end_time": 7.0,
        },
        {
            "text": "They're all doing well, thanks.",
            "start_time": 7.0,
            "end_time": 9.0,
        },
    ]

    md_content = """# Simple English Dialogue

This is a basic greeting dialogue to teach conversational English.

## Learning Objectives
- Greeting phrases
- Polite responses
- Questions about family
"""

    try:
        print("\n[1/2] 初始化 SkillChainOrchestrator...")
        orchestrator = SkillChainOrchestrator()
        print("✓ 初始化成功")

        print("\n[2/2] 生成讲课脚本（完整 Skill Chain 流程）...")
        print("  → ContentAnalyzer: 分析内容...")
        print("  → LessonPlanner: 规划课程...")
        print("  → LessonWriter: 生成脚本...")
        print("  → QualityValidator: 评估质量...")
        print("  → ScriptRepair: 自动修复（如需要）...\n")

        result = orchestrator.generate_lesson(
            md_content=md_content,
            segments=segments,
            source_lang="en",
            target_lang="zh-Hans",
        )

        # 输出结果
        print("\n" + "="*70)
        print("生成结果汇总")
        print("="*70)

        print(f"\n✓ 生成成功: {result['success']}")
        print(f"✓ 最终质量分数: {result['validation_result']['score']:.1f}/100")
        print(f"✓ 修复尝试次数: {result['metadata']['repair_attempts']}")
        print(f"✓ 总执行时间: {result['metadata']['execution_time']}s")

        # 内容分析结果
        print("\n【内容分析】")
        cp = result['content_profile']
        print(f"  内容类型: {cp.get('content_type')}")
        print(f"  难度等级: {cp.get('estimated_cefr')}")
        print(f"  寄存器: {cp.get('register')}")

        # 规划统计
        print("\n【课程规划】")
        lp = result['lesson_plan']
        deep_count = sum(1 for s in lp if s.get('depth') == 'deep')
        standard_count = sum(1 for s in lp if s.get('depth') == 'standard')
        light_count = sum(1 for s in lp if s.get('depth') == 'light')
        print(f"  总句数: {len(lp)}")
        print(f"  深度句: {deep_count} ({deep_count*100//len(lp) if lp else 0}%)")
        print(f"  标准句: {standard_count} ({standard_count*100//len(lp) if lp else 0}%)")
        print(f"  简易句: {light_count} ({light_count*100//len(lp) if lp else 0}%)")

        # 脚本统计
        print("\n【生成的脚本】")
        script = result['lesson_script']
        speaks = [s for s in script if s.get('type') == 'speak']
        plays = [s for s in script if s.get('type') == 'play']
        questions = [s for s in script if s.get('type') == 'question']
        print(f"  总指令数: {len(script)}")
        print(f"  讲解: {len(speaks)} 条")
        print(f"  播放: {len(plays)} 条")
        print(f"  提问: {len(questions)} 条")

        # 质量评估
        print("\n【质量评估 (7维度)】")
        dims = result['validation_result']['dimension_scores']
        for dim, score in dims.items():
            bar = "█" * int(score/10) + "░" * (10 - int(score/10))
            print(f"  {dim:20} {score:5.1f}/100  {bar}")

        # 问题和建议
        validation = result['validation_result']
        if validation['issues']:
            print("\n【发现的问题】")
            for issue in validation['issues']:
                print(f"  ⚠ {issue}")

        if validation['suggestions']:
            print("\n【改进建议】")
            for suggestion in validation['suggestions']:
                print(f"  💡 {suggestion}")

        print("\n" + "="*70)
        print("✓ 测试完成")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_output_save():
    """测试带文件输出的完整流程"""

    print("\n" + "="*70)
    print("Skill Chain 测试（带文件输出）")
    print("="*70)

    segments = [
        {"text": "What is the capital of France?", "start_time": 0, "end_time": 2},
        {"text": "The capital of France is Paris.", "start_time": 2, "end_time": 4},
        {"text": "Paris is known for the Eiffel Tower.", "start_time": 4, "end_time": 6},
    ]

    md_content = "# Geography Quiz\n\nLearn about world capitals."
    output_dir = Path(__file__).parent / "test_output"

    try:
        print(f"\n初始化并生成讲课脚本...")
        print(f"输出目录: {output_dir.resolve()}\n")

        orchestrator = SkillChainOrchestrator()
        result = orchestrator.generate_lesson_and_save(
            md_content=md_content,
            segments=segments,
            output_dir=output_dir,
            source_lang="en",
            target_lang="zh-Hans",
        )

        print(f"✓ 生成完成!")
        print(f"✓ 质量分数: {result['validation_result']['score']:.1f}/100")
        print(f"✓ 通过验证: {result['success']}")

        # 列出输出文件
        print(f"\n【输出文件】")
        for f in sorted(output_dir.glob("*.json")):
            size = f.stat().st_size
            print(f"  ✓ {f.name} ({size} bytes)")

        print("\n" + "="*70)
        print("✓ 测试完成")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行两个测试
    success1 = test_basic_generation()
    success2 = test_with_output_save()

    if success1 and success2:
        print("\n✓✓✓ 所有测试通过 ✓✓✓\n")
        sys.exit(0)
    else:
        print("\n✗✗✗ 部分测试失败 ✗✗✗\n")
        sys.exit(1)
