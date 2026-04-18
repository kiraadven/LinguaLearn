"""
Tool definitions for the AI teacher.

These are expressed as OpenAI-compatible function schemas (also accepted by
Claude via the /v1/chat/completions endpoint with tools=[...]).

The AI uses these tools to:
  - Control the video player on the frontend
  - Highlight vocabulary
  - Show grammar/culture notes
  - Request shadow reading from the learner
"""
from __future__ import annotations

TEACHER_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "play_full_video",
            "description": (
                "Play the entire learning video from the beginning. "
                "Call this at the start of a course session so the learner gets an "
                "overview of the content before sentence-by-sentence teaching."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_sentence",
            "description": (
                "Play a specific sentence clip from the video. "
                "Always call this before explaining a new sentence so the learner "
                "hears the sentence in context first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence_index": {
                        "type": "integer",
                        "description": "0-based index of the sentence to play.",
                    },
                    "loop_count": {
                        "type": "integer",
                        "description": "Number of times to play the clip (default 1).",
                        "default": 1,
                    },
                },
                "required": ["sentence_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_video",
            "description": "Pause the video player.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "highlight_word",
            "description": (
                "Highlight a specific word in the current sentence transcript "
                "to draw the learner's attention during vocabulary explanation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "The word to highlight.",
                    },
                    "sentence_index": {
                        "type": "integer",
                        "description": "The sentence the word belongs to.",
                    },
                },
                "required": ["word", "sentence_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_note",
            "description": (
                "Display a grammar explanation or cultural background note "
                "as a popup card on the learner's screen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the note (e.g. '完成时态', 'LAPD是什么').",
                    },
                    "content": {
                        "type": "string",
                        "description": "Note content in Chinese or bilingual format.",
                    },
                    "note_type": {
                        "type": "string",
                        "enum": ["grammar", "culture", "vocabulary", "pronunciation"],
                        "description": "Category of note for UI styling.",
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_shadow",
            "description": (
                "Ask the learner to shadow-read (repeat after) the current sentence "
                "for pronunciation practice. Use when the sentence is long, "
                "phonetically challenging, or when the learner is at A1–B1 level."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The English text the learner should repeat.",
                    },
                    "sentence_index": {
                        "type": "integer",
                        "description": "Index of the sentence.",
                    },
                },
                "required": ["text", "sentence_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance_sentence",
            "description": (
                "Signal readiness to move to the next sentence. "
                "Call this after finishing the explanation and any interaction for "
                "the current sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "current_index": {
                        "type": "integer",
                        "description": "Index of the sentence that just finished.",
                    },
                },
                "required": ["current_index"],
            },
        },
    },
]


def get_tool_schemas() -> list[dict]:
    """Return the tool list for passing to the LLM API."""
    return TEACHER_TOOLS
