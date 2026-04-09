"""
TTS Fallback - Used when LLM supervisor generates text for exception cases.

Only active for <5% of turns. When the self-thinking voice model
cannot handle a situation (LLM escalation), the supervisor generates
text which is then synthesized via a conventional TTS system.
"""
