"""
BaseAgent — 所有Skill代理的基类

提取公共功能：
  - LLM 请求（OpenAI）
  - JSON 解析和验证
  - 日志记录
  - Prompt 构建和优化
  - Reference files 加载

每个Skill代理继承这个类，专注于自己的任务。
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# 获取知识库路径
KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge_base"


class BaseAgent:
    """所有AI Tutor Skill代理的基类"""

    def __init__(
        self,
        agent_name: str,
        model: str = "gpt-4-turbo",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        knowledge_base_path: Optional[Path] = None,
    ):
        """
        初始化Agent

        Args:
            agent_name: Agent的名字（用于日志）
            model: 使用的模型
            temperature: 生成的随机度
            max_tokens: 最大token数
            knowledge_base_path: 知识库路径（默认使用项目知识库）
        """
        self.agent_name = agent_name
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.knowledge_base_path = knowledge_base_path or KNOWLEDGE_BASE_PATH

        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        logger.info(f"[{self.agent_name}] 初始化完成 (model={model})")

    def load_reference_file(self, filepath: str) -> str:
        """
        加载知识库文件

        Args:
            filepath: 相对于 knowledge_base 的路径，例如 "teaching_methodology.md"

        Returns:
            文件内容
        """
        full_path = self.knowledge_base_path / filepath
        if not full_path.exists():
            logger.warning(f"[{self.agent_name}] 知识库文件不存在: {filepath}")
            return ""

        try:
            content = full_path.read_text(encoding="utf-8")
            logger.debug(f"[{self.agent_name}] 加载知识库文件: {filepath} ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"[{self.agent_name}] 加载知识库文件失败: {filepath}, {e}")
            return ""

    def load_reference_files(self, filepaths: List[str]) -> Dict[str, str]:
        """
        批量加载知识库文件

        Args:
            filepaths: 文件路径列表

        Returns:
            {filepath: content} 字典
        """
        result = {}
        for filepath in filepaths:
            content = self.load_reference_file(filepath)
            if content:
                result[filepath] = content
        return result

    def _request_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        scene: str = "json_request",
        expected_type: type = dict,
        max_attempts: int = 3,
    ) -> Any:
        """
        请求LLM并解析JSON回复

        这是提取的公共逻辑，所有Agent都会用到。

        Args:
            messages: OpenAI 消息列表
            temperature: 可选的自定义温度
            max_tokens: 可选的自定义token数
            scene: 场景名（用于日志）
            expected_type: 期望的JSON类型（dict 或 list）
            max_attempts: 重试次数

        Returns:
            解析后的JSON对象

        Raises:
            ValueError: 如果无法解析或类型不匹配
        """
        temp = temperature or self.temperature
        tokens = max_tokens or self.max_tokens

        last_err = None
        for idx in range(1, max_attempts + 1):
            try:
                logger.debug(f"[{self.agent_name}] {scene} 请求 (attempt {idx}/{max_attempts})")

                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                )

                resp_text = resp.choices[0].message.content

                # 尝试从 markdown fence 中提取JSON
                if "```" in resp_text:
                    start = resp_text.find("```") + 3
                    if resp_text[start:start+4] == "json":
                        start += 4
                    end = resp_text.rfind("```")
                    raw = resp_text[start:end].strip()
                else:
                    raw = resp_text.strip()

                data = json.loads(raw)

                # 类型检查
                if expected_type and not isinstance(data, expected_type):
                    # 尝试解包 {"items": [...]}
                    if isinstance(data, dict):
                        for v in data.values():
                            if isinstance(v, expected_type.__bases__[0] if expected_type.__bases__ else list):
                                data = v
                                break

                if expected_type and not isinstance(data, expected_type):
                    raise ValueError(
                        f"类型错误: 期望 {expected_type.__name__}, 实际 {type(data).__name__}"
                    )

                logger.debug(f"[{self.agent_name}] {scene} 成功")
                return data

            except Exception as e:
                last_err = e
                preview = str(locals().get("raw", ""))[:200].replace("\n", "\\n")
                logger.warning(
                    f"[{self.agent_name}] {scene} 失败 attempt {idx}/{max_attempts}: {e}; preview={preview}"
                )

        raise last_err or ValueError(f"{scene} 最终失败")

    def _build_system_prompt(
        self,
        base_prompt: str,
        reference_files: Optional[Dict[str, str]] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        构建系统提示词，包含知识库内容

        Args:
            base_prompt: 基础提示词（Agent的核心指令）
            reference_files: 知识库文件内容
            additional_context: 额外上下文

        Returns:
            完整的系统提示词
        """
        parts = [base_prompt]

        if reference_files:
            parts.append("\n\n## 教学知识库参考\n")
            for filepath, content in reference_files.items():
                parts.append(f"\n### {filepath}\n{content}")

        if additional_context:
            parts.append(f"\n\n## 额外上下文\n{additional_context}")

        return "\n".join(parts)

    def log_stats(self, **kwargs):
        """
        记录Agent的统计信息

        Args:
            **kwargs: 任意键值对统计
        """
        msg = f"[{self.agent_name}] 统计: "
        msg += ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(msg)
