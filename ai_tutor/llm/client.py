from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ai_tutor.config import get_settings


ChatMessage = dict[str, str]
ToolCallChunk = dict[str, Any]


class ClaudeClient:
    """LLM client for tutoring responses and summaries.

    Backward compatible with legacy `stream(prompt)` / `complete(prompt)` APIs,
    while supporting message-based chat requests:
      - system_prompt: stable instruction layer
      - messages: prior chat history
      - user_message: current turn context
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.anthropic_model
        self.api_key = settings.anthropic_api_key
        self.base_url = settings.llm_api_base_url.rstrip("/")
        self.chat_path = settings.llm_chat_path
        timeout = httpx.Timeout(
            connect=min(settings.llm_timeout_seconds, 10.0),
            read=settings.llm_timeout_seconds,
            write=min(settings.llm_timeout_seconds, 30.0),
            pool=min(settings.llm_timeout_seconds, 30.0),
        )
        # Avoid accidental proxy routing for local/dev environments.
        self.http = httpx.AsyncClient(timeout=timeout, trust_env=False)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_url(self) -> str:
        if self.chat_path.startswith("http://") or self.chat_path.startswith("https://"):
            return self.chat_path
        path = self.chat_path if self.chat_path.startswith("/") else f"/{self.chat_path}"
        if self.base_url.endswith("/v1") and path.startswith("/v1/"):
            path = path[3:]
        return f"{self.base_url}{path}"

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    # OpenAI-like delta/content block
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
        return ""

    @staticmethod
    def _sanitize_messages(messages: list[dict[str, Any]] | None) -> list[ChatMessage]:
        clean: list[ChatMessage] = []
        if not messages:
            return clean

        for raw in messages:
            if not isinstance(raw, dict):
                continue
            role = raw.get("role")
            content = raw.get("content")
            if role not in {"system", "user", "assistant"}:
                continue
            if isinstance(content, str) and content.strip():
                clean.append({"role": role, "content": content})
        return clean

    def _build_messages(
        self,
        prompt: str | None,
        system_prompt: str | None,
        user_message: str | None,
        messages: list[dict[str, Any]] | None,
    ) -> list[ChatMessage]:
        """Assemble final chat messages with backward compatibility."""
        # Legacy mode: prompt only
        if (
            prompt is not None
            and system_prompt is None
            and user_message is None
            and not messages
        ):
            return [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "请按照上述教学目标继续。"},
            ]

        assembled = self._sanitize_messages(messages)

        if system_prompt:
            assembled = [{"role": "system", "content": system_prompt}] + assembled
        elif prompt:
            assembled = [{"role": "system", "content": prompt}] + assembled

        if user_message:
            assembled.append({"role": "user", "content": user_message})

        if not assembled:
            assembled = [
                {
                    "role": "system",
                    "content": "你是一名自然、耐心、专业的语言老师。",
                },
                {"role": "user", "content": "请继续。"},
            ]

        return assembled

    async def stream(
        self,
        prompt: str | None = None,
        max_tokens: int = 512,
        *,
        system_prompt: str | None = None,
        user_message: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str | ToolCallChunk]:
        """Yield text tokens from streaming API."""
        final_messages = self._build_messages(
            prompt=prompt,
            system_prompt=system_prompt,
            user_message=user_message,
            messages=messages,
        )

        if not self.api_key:
            fallback = (
                "我明白你的意思了。我们换一种更自然的说法再试一次。\n\n"
                "```json\n"
                '{"tool_calls":[]}'
                "\n```"
            )
            yield fallback
            return

        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # OpenAI-compatible streaming tool-call aggregation.
        # key=index, value={"name": str, "arguments_text": str}
        streamed_tool_calls: dict[int, dict[str, str]] = {}

        async with self.http.stream(
            "POST",
            self._chat_url(),
            headers=self._headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    content = self._extract_text(delta.get("content"))
                    if content:
                        yield content
                    if tools:
                        raw_calls = delta.get("tool_calls") or []
                        if isinstance(raw_calls, list):
                            for raw in raw_calls:
                                if not isinstance(raw, dict):
                                    continue
                                idx_raw = raw.get("index", 0)
                                try:
                                    idx = int(idx_raw)
                                except (TypeError, ValueError):
                                    idx = 0
                                item = streamed_tool_calls.setdefault(
                                    idx,
                                    {"name": "", "arguments_text": ""},
                                )
                                fn = raw.get("function")
                                if isinstance(fn, dict):
                                    name_part = fn.get("name")
                                    if isinstance(name_part, str) and name_part:
                                        item["name"] += name_part
                                    args_part = fn.get("arguments")
                                    if isinstance(args_part, str) and args_part:
                                        item["arguments_text"] += args_part

        if tools and streamed_tool_calls:
            for idx in sorted(streamed_tool_calls.keys()):
                tc = streamed_tool_calls[idx]
                name = tc["name"].strip()
                if not name:
                    continue
                arguments: dict[str, Any] = {}
                raw_args = tc["arguments_text"].strip()
                if raw_args:
                    try:
                        parsed_args = json.loads(raw_args)
                        if isinstance(parsed_args, dict):
                            arguments = parsed_args
                    except json.JSONDecodeError:
                        arguments = {}
                yield {
                    "type": "tool_call",
                    "name": name,
                    "arguments": arguments,
                }

    async def complete(
        self,
        prompt: str | None = None,
        max_tokens: int = 512,
        *,
        system_prompt: str | None = None,
        user_message: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.4,
    ) -> str:
        final_messages = self._build_messages(
            prompt=prompt,
            system_prompt=system_prompt,
            user_message=user_message,
            messages=messages,
        )

        if not self.api_key:
            return '{"summary":"本次课程已完成。","strengths":["积极回应"],"next_focus":["继续巩固表达"]}'

        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
        response = await self.http.post(
            self._chat_url(),
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()

        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = self._extract_text(message.get("content"))
        if content.strip():
            return content.strip()

        # Some providers may return tool_calls with empty text content.
        # Keep compatibility with downstream text parser by encoding
        # a minimal JSON block when needed.
        tool_calls = message.get("tool_calls") or []
        if isinstance(tool_calls, list) and tool_calls:
            normalized: list[dict[str, Any]] = []
            for raw in tool_calls:
                if not isinstance(raw, dict):
                    continue
                fn = raw.get("function")
                if not isinstance(fn, dict):
                    continue
                name = fn.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                arguments: dict[str, Any] = {}
                raw_args = fn.get("arguments")
                if isinstance(raw_args, str) and raw_args.strip():
                    try:
                        parsed = json.loads(raw_args)
                        if isinstance(parsed, dict):
                            arguments = parsed
                    except json.JSONDecodeError:
                        arguments = {}
                normalized.append({"name": name.strip(), "arguments": arguments})
            if normalized:
                return (
                    "```json\n"
                    + json.dumps({"tool_calls": normalized}, ensure_ascii=False)
                    + "\n```"
                )
        return ""

    async def summarize_session(self, turns: list[dict], errors: list[dict]) -> str:
        prompt = (
            "你是一名资深二语习得评估老师。"
            "请基于以下课堂数据，对该学生做详细、可执行、证据驱动的学习分析。"
            "输出必须是纯 JSON，不要任何 markdown、解释文字或代码块。\n\n"
            "要求：\n"
            "1) 只基于给定 turns/errors 进行判断，不要臆测未出现的信息。\n"
            "2) 每个关键结论都要给 evidence（引用 turn 序号和片段）。\n"
            "3) 对每个维度给 confidence（low|medium|high）。\n"
            "4) 如果数据不足，明确写出 unknown，并解释缺口。\n"
            "5) 给出下节课可直接执行的教学建议（具体到任务与话术）。\n\n"
            "输出 JSON Schema（字段名固定）：\n"
            "{\n"
            '  "summary": "2-4句总评（中文）",\n'
            '  "learner_snapshot": {\n'
            '    "provisional_level": "A1|A2|B1|B2|C1|unknown",\n'
            '    "engagement": "high|medium|low|unknown",\n'
            '    "fluency": "high|medium|low|unknown",\n'
            '    "accuracy": "high|medium|low|unknown",\n'
            '    "confidence": "low|medium|high"\n'
            "  },\n"
            '  "strengths": [\n'
            '    {"point": "...", "evidence": ["turn#2: ..."], "confidence": "low|medium|high"}\n'
            "  ],\n"
            '  "weaknesses": [\n'
            '    {"point": "...", "impact": "...", "evidence": ["turn#4: ..."], "confidence": "low|medium|high"}\n'
            "  ],\n"
            '  "error_analysis": {\n'
            '    "grammar": [\n'
            '      {"pattern": "...", "frequency": 0, "severity": "high|medium|low", "evidence": ["turn#..."], "fix_tip": "..."}\n'
            "    ],\n"
            '    "vocabulary": [\n'
            '      {"pattern": "...", "frequency": 0, "severity": "high|medium|low", "evidence": ["turn#..."], "fix_tip": "..."}\n'
            "    ],\n"
            '    "discourse_or_pragmatics": [\n'
            '      {"pattern": "...", "frequency": 0, "severity": "high|medium|low", "evidence": ["turn#..."], "fix_tip": "..."}\n'
            "    ]\n"
            "  },\n"
            '  "phase_performance": {\n'
            '    "opening": {"observation": "...", "confidence": "low|medium|high"},\n'
            '    "teach": {"observation": "...", "confidence": "low|medium|high"},\n'
            '    "practice": {"observation": "...", "confidence": "low|medium|high"},\n'
            '    "closing": {"observation": "...", "confidence": "low|medium|high"}\n'
            "  },\n"
            '  "next_session_plan": {\n'
            '    "primary_goals": ["..."],\n'
            '    "target_structures": ["..."],\n'
            '    "drills": [\n'
            '      {"name": "...", "duration_min": 0, "steps": ["..."], "success_criteria": "..."}\n'
            "    ],\n"
            '    "teacher_language_strategy": ["可直接使用的话术建议"],\n'
            '    "homework": ["..."]\n'
            "  },\n"
            '  "risk_flags": [\n'
            '    {"risk": "...", "signal": "...", "mitigation": "..."}\n'
            "  ]\n"
            "}\n\n"
            f"turns={json.dumps(turns, ensure_ascii=False)}\n"
            f"errors={json.dumps(errors, ensure_ascii=False)}"
        )
        return await self.complete(prompt, max_tokens=900)
