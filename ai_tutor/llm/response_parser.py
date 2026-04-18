from __future__ import annotations

import json
import re
from typing import Any


DEFAULT_PAYLOAD = {
    "action": "encourage",
    "phase": "teach",
    "vocab_used": [],
    "error_noted": None,
}


class ResponseParser:
    """Parse teacher text + trailing JSON metadata from model output."""

    JSON_BLOCK_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

    @classmethod
    def parse(cls, raw_text: str) -> dict[str, Any]:
        raw_text = (raw_text or "").strip()
        match = cls.JSON_BLOCK_PATTERN.search(raw_text)

        payload = DEFAULT_PAYLOAD.copy()
        teacher_text = raw_text

        if match:
            json_blob = match.group(1)
            try:
                parsed_payload = json.loads(json_blob)
                if isinstance(parsed_payload, dict):
                    payload.update(parsed_payload)
            except json.JSONDecodeError:
                pass

            teacher_text = (raw_text[: match.start()] + raw_text[match.end() :]).strip()

        if not teacher_text:
            teacher_text = "Let me think..."

        return {
            "text": teacher_text,
            "action": payload.get("action", "encourage"),
            "phase": payload.get("phase", "teach"),
            "vocab_used": payload.get("vocab_used") or [],
            "error_noted": payload.get("error_noted"),
            "raw": raw_text,
        }
