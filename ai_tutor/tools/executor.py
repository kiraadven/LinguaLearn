"""
ToolExecutor: translate LLM tool calls → WebSocket messages to the frontend.

Each tool call is sent as:
  {"type": "tool_call", "tool": <name>, "args": <dict>}
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Signature: async send_fn(data: str | bytes) → None
SendFn = Callable[[str], Awaitable[None]]


class ToolExecutor:
    """
    Executes AI teacher tool calls by sending WebSocket messages to the frontend.
    """

    def __init__(self, send_fn: SendFn) -> None:
        self._send = send_fn

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict:
        """
        Execute a named tool and return a result dict (for the LLM tool-result message).

        Args:
            tool_name: one of the tool names in definitions.TEACHER_TOOLS
            tool_input: dict of arguments matching the tool's parameter schema

        Returns:
            Result dict passed back to the LLM as a tool result.
        """
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            logger.warning("Unknown tool: %s", tool_name)
            return {"ok": False, "error": f"Unknown tool: {tool_name}"}

        try:
            result = await handler(tool_input)
            return result
        except Exception as exc:
            logger.exception("Tool %s failed: %s", tool_name, exc)
            return {"ok": False, "error": str(exc)}

    async def _send_tool_call(self, tool: str, args: dict) -> None:
        msg = json.dumps({"type": "tool_call", "tool": tool, "args": args}, ensure_ascii=False)
        await self._send(msg)

    # ── Tool handlers ─────────────────────────────────────────────────────────

    async def _tool_play_full_video(self, args: dict) -> dict:
        await self._send_tool_call("play_full_video", {})
        return {"ok": True, "action": "play_full_video"}

    async def _tool_play_sentence(self, args: dict) -> dict:
        payload = {
            "sentence_index": int(args.get("sentence_index", 0)),
            "loop_count": int(args.get("loop_count", 1)),
        }
        await self._send_tool_call("play_sentence", payload)
        return {"ok": True, "action": "play_sentence", **payload}

    async def _tool_pause_video(self, args: dict) -> dict:
        await self._send_tool_call("pause_video", {})
        return {"ok": True, "action": "pause_video"}

    async def _tool_highlight_word(self, args: dict) -> dict:
        payload = {
            "word": str(args.get("word", "")),
            "sentence_index": int(args.get("sentence_index", 0)),
        }
        await self._send_tool_call("highlight_word", payload)
        return {"ok": True, "action": "highlight_word", **payload}

    async def _tool_show_note(self, args: dict) -> dict:
        payload = {
            "title": str(args.get("title", "")),
            "content": str(args.get("content", "")),
            "note_type": str(args.get("note_type", "grammar")),
        }
        await self._send_tool_call("show_note", payload)
        return {"ok": True, "action": "show_note", **payload}

    async def _tool_request_shadow(self, args: dict) -> dict:
        payload = {
            "text": str(args.get("text", "")),
            "sentence_index": int(args.get("sentence_index", 0)),
        }
        await self._send_tool_call("request_shadow", payload)
        return {"ok": True, "action": "request_shadow", **payload}

    async def _tool_advance_sentence(self, args: dict) -> dict:
        payload = {"current_index": int(args.get("current_index", 0))}
        await self._send_tool_call("advance_sentence", payload)
        return {"ok": True, "action": "advance_sentence", **payload}
