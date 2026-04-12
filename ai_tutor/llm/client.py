from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from config import get_settings


class ClaudeClient:
    """Claude streaming client for tutoring responses and summaries."""

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
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
        return ""

    async def stream(self, prompt: str, max_tokens: int = 512) -> AsyncIterator[str]:
        """Yield text tokens from Claude streaming API."""
        if not self.api_key:
            fallback = (
                "I heard you. Let me recast that naturally. "
                "Could you try saying it one more time with present perfect?\n\n"
                "```json\n"
                '{"action":"check","phase":"teach","vocab_used":["already"],"error_noted":null}'
                "\n```"
            )
            yield fallback
            return

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
        }

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

    async def complete(self, prompt: str, max_tokens: int = 512) -> str:
        if not self.api_key:
            return '{"summary":"本次课程已完成。","strengths":["积极回应"],"next_focus":["继续present perfect"]}'

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": max_tokens,
            "stream": False,
        }
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
        return content.strip()

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
