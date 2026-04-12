"""
TeachingEngine: core state machine for the AI tutor session.

States:
  IDLE → INTRO → SENTENCE_LOOP → REVIEW → END

The engine:
  - Tracks which sentence the teacher is on
  - Decides when to shadow-read, when to intervene on attention
  - Builds prompts via llm/course_prompts.py
  - Delegates LLM calls to ClaudeClient
  - Delegates tool execution to ToolExecutor
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable

from content.loader import LinguaLearnContent
from content.curriculum import Curriculum
from content.language_profiles import get_language_profile, get_content_type_profile
from llm.client import ClaudeClient
from llm.course_prompts import build_course_prompt, build_review_prompt
from llm.global_prompts import build_global_prompt
from memory.manager import MemoryManager
from memory.short_term import ShortTermMemory
from session.attention_monitor import AttentionMonitor, AttentionLevel
from session.learner_profile import LearnerProfile
from tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

SendFn = Callable[[str], Awaitable[None]]


class TeachingPhase(str, Enum):
    IDLE = "idle"
    INTRO = "intro"           # Playing full video
    TEACHING = "teaching"     # Sentence-by-sentence
    REVIEW = "review"         # End of sentences, free summary
    END = "end"


@dataclass
class TeachingState:
    phase: TeachingPhase = TeachingPhase.IDLE
    sentence_index: int = 0    # Current sentence being taught
    total_sentences: int = 0
    awaiting_video_end: bool = False  # Waiting for frontend "video ended" event
    awaiting_student: bool = False    # Waiting for student to respond
    shadow_pending: bool = False


class TeachingEngine:
    """
    Orchestrates the full lesson flow.

    Usage:
        engine = TeachingEngine(content, curriculum, profile, memory_manager, send_fn)
        await engine.start_course()
        ...
        await engine.handle_message(msg)
    """

    def __init__(
        self,
        content: LinguaLearnContent,
        curriculum: Curriculum,
        profile: LearnerProfile,
        memory_manager: MemoryManager,
        send_fn: SendFn,
        mode: str = "course",
    ) -> None:
        self.content = content
        self.curriculum = curriculum
        self.profile = profile
        self.memory = memory_manager
        self.short: ShortTermMemory = memory_manager.short_term
        self.mode = mode
        self._state = TeachingState(total_sentences=content.sentence_count)
        self._llm = ClaudeClient()
        self._tool_exec = ToolExecutor(send_fn)
        self._send = send_fn
        self._attention = AttentionMonitor()
        self._session_start = time.time()
        self._last_teacher_end: float = time.time()

    # ── Public API ────────────────────────────────────────────────────────────

    async def start_course(self) -> None:
        """Begin the lesson: send curriculum to frontend, play full video."""
        self._state.phase = TeachingPhase.INTRO

        # Send curriculum summary to frontend
        await self._send(json.dumps({
            "type": "curriculum",
            "plan": self.curriculum.to_summary(),
            "total_sentences": self._state.total_sentences,
        }))

        await self._send(json.dumps({
            "type": "teaching_state",
            "phase": "intro",
            "sentence_index": -1,
            "total": self._state.total_sentences,
        }))

        # Teacher greeting + play full video tool call
        greeting = await self._generate_intro_speech()
        await self._speak(greeting)
        await self._tool_exec.execute("play_full_video", {})
        self._state.awaiting_video_end = True

    async def handle_message(self, msg: dict) -> None:
        """
        Dispatch incoming WebSocket messages from the frontend.

        Expected types:
          video_event, text_input, attention, transcript (from ASR)
        """
        msg_type = msg.get("type", "")

        if msg_type == "video_event":
            await self._handle_video_event(msg)

        elif msg_type in ("text_input", "transcript"):
            text = msg.get("text", "").strip()
            if text:
                await self._handle_student_input(text, msg)

        elif msg_type == "attention":
            await self._handle_attention_signal(msg)

        elif msg_type == "session_end":
            await self._end_session()

    async def start_global_mode(self) -> None:
        """Global review / chat mode: no structured sentences."""
        self._state.phase = TeachingPhase.REVIEW
        ctx = self.memory.get_context(mode="global")
        prompt = build_global_prompt(
            ctx, self.profile,
            student_input="",
            target_language=self.curriculum.target_language,
        )
        resp = await self._llm.complete(prompt, max_tokens=400)
        if resp:
            await self._speak(resp)

    # ── Video event handling ───────────────────────────────────────────────────

    async def _handle_video_event(self, msg: dict) -> None:
        event = msg.get("event", "")

        if event == "ended":
            if self._state.phase == TeachingPhase.INTRO and self._state.awaiting_video_end:
                self._state.awaiting_video_end = False
                await self._begin_sentence(0)

            elif self._state.phase == TeachingPhase.TEACHING:
                # Sentence clip finished playing → teacher explains
                await self._explain_current_sentence()

        elif event == "segment_ended":
            if self._state.phase == TeachingPhase.TEACHING:
                await self._explain_current_sentence()

    # ── Student input handling ─────────────────────────────────────────────────

    async def _handle_student_input(self, text: str, raw_msg: dict) -> None:
        latency = time.time() - self._last_teacher_end
        self._attention.record_response_latency(latency)
        self._attention.record_student_response(text)
        self.short.add_turn("student", text)

        if self._state.phase == TeachingPhase.INTRO:
            # Student spoke during intro video — brief acknowledgment
            ack = await self._generate_brief_ack(text)
            await self._speak(ack)
            return

        if self._state.phase == TeachingPhase.TEACHING:
            await self._handle_teaching_interaction(text)
        elif self._state.phase == TeachingPhase.REVIEW:
            await self._handle_review_interaction(text)

    async def _handle_teaching_interaction(self, student_text: str) -> None:
        """Generate teacher response during sentence teaching phase."""
        sentence = self.content.get_sentence(self._state.sentence_index)
        plan = self.curriculum.get_plan(self._state.sentence_index)
        ctx = self.memory.get_context(mode="course")

        prompt = build_course_prompt(
            sentence=sentence,
            plan=plan,
            memory_context=ctx,
            profile=self.profile,
            student_input=student_text,
            attention_label=self._attention.to_prompt_label(),
            should_advance=False,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )

        full_response = ""
        tool_calls: list[dict] = []

        async for chunk in self._stream_with_tools(prompt):
            if isinstance(chunk, str):
                full_response += chunk
            elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                tool_calls.append(chunk)

        # Parse embedded tool calls from the response text
        parsed_tools, clean_text = _extract_tool_calls(full_response)
        tool_calls.extend(parsed_tools)

        # Speak the clean teacher text
        if clean_text.strip():
            self.short.add_turn("teacher", clean_text.strip())
            await self._speak(clean_text.strip())

        # Execute tools
        for tc in tool_calls:
            await self._tool_exec.execute(tc["name"], tc.get("arguments", {}))

        # Check if advance_sentence was called → move to next
        for tc in tool_calls:
            if tc["name"] == "advance_sentence":
                await self._advance_to_next_sentence()
                break

        self._last_teacher_end = time.time()

    async def _handle_review_interaction(self, student_text: str) -> None:
        ctx = self.memory.get_context(mode="global")
        prompt = build_global_prompt(
            ctx, self.profile,
            student_input=student_text,
            target_language=self.curriculum.target_language,
        )
        resp = await self._llm.complete(prompt, max_tokens=400)
        if resp:
            self.short.add_turn("teacher", resp)
            await self._speak(resp)
        self._last_teacher_end = time.time()

    # ── Sentence flow ─────────────────────────────────────────────────────────

    async def _begin_sentence(self, index: int) -> None:
        if index >= self._state.total_sentences:
            await self._begin_review()
            return

        self._state.sentence_index = index
        self._state.phase = TeachingPhase.TEACHING
        sentence = self.content.get_sentence(index)
        if not sentence:
            return

        await self._send(json.dumps({
            "type": "teaching_state",
            "phase": "teaching",
            "sentence_index": index,
            "total": self._state.total_sentences,
        }))

        # Play the sentence clip
        await self._tool_exec.execute("play_sentence", {
            "sentence_index": index,
            "loop_count": 1,
        })
        # After clip plays, the frontend will send video_event.segment_ended
        # which triggers _explain_current_sentence()

    async def _explain_current_sentence(self) -> None:
        """Generate the teacher's opening explanation for the current sentence."""
        sentence = self.content.get_sentence(self._state.sentence_index)
        plan = self.curriculum.get_plan(self._state.sentence_index)
        ctx = self.memory.get_context(mode="course")

        prompt = build_course_prompt(
            sentence=sentence,
            plan=plan,
            memory_context=ctx,
            profile=self.profile,
            student_input="",  # Teacher initiates explanation
            attention_label=self._attention.to_prompt_label(),
            should_advance=False,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )

        full_response = ""
        async for chunk in self._stream_with_tools(prompt):
            if isinstance(chunk, str):
                full_response += chunk

        parsed_tools, clean_text = _extract_tool_calls(full_response)

        if clean_text.strip():
            self.short.add_turn("teacher", clean_text.strip())
            await self._speak(clean_text.strip())

        for tc in parsed_tools:
            await self._tool_exec.execute(tc["name"], tc.get("arguments", {}))

        # Check if shadow reading is due
        if plan and plan.should_shadow and not self._state.shadow_pending:
            self._state.shadow_pending = True
            await self._tool_exec.execute("request_shadow", {
                "text": sentence.text if sentence else "",
                "sentence_index": self._state.sentence_index,
            })
            self.short.shadow_requests += 1

        self._state.awaiting_student = True
        self._last_teacher_end = time.time()

    async def _advance_to_next_sentence(self) -> None:
        current = self._state.sentence_index
        self.short.mark_sentence_done(current)
        self._state.shadow_pending = False
        next_idx = current + 1

        # Brief language-aware transition message
        if next_idx < self._state.total_sentences:
            transition = _build_transition_message(
                next_idx,
                self._state.total_sentences,
                self.curriculum.target_language,
            )
            await self._speak(transition)
            await self._begin_sentence(next_idx)
        else:
            await self._begin_review()

    async def _begin_review(self) -> None:
        self._state.phase = TeachingPhase.REVIEW
        await self._send(json.dumps({"type": "teaching_state", "phase": "review"}))

        ctx = self.memory.get_context(mode="course")
        prompt = build_review_prompt(
            ctx, self.profile, self.curriculum,
            target_language=self.curriculum.target_language,
        )
        resp = await self._llm.complete(prompt, max_tokens=400)
        if resp:
            self.short.add_turn("teacher", resp)
            await self._speak(resp)
        self._last_teacher_end = time.time()

    # ── Attention handling ────────────────────────────────────────────────────

    async def _handle_attention_signal(self, msg: dict) -> None:
        signal = msg.get("signal", "")
        value = float(msg.get("value", 0.5))

        if signal == "tab_switch":
            self._attention.record_tab_switch()
        elif signal == "mouse_idle":
            self._attention.record_mouse_idle(float(msg.get("idle_seconds", 30)))
        elif signal == "audio_energy":
            self._attention.record_audio_energy(value)

        if self._attention.should_intervene():
            await self._intervene_attention()

    async def _intervene_attention(self) -> None:
        """Re-engage the learner when attention is low."""
        intervention = self._attention.get_intervention_type()
        sentence = self.content.get_sentence(self._state.sentence_index)
        plan = self.curriculum.get_plan(self._state.sentence_index)

        if intervention == "culture_note" and plan and plan.culture_note:
            lang_profile = get_language_profile(self.curriculum.target_language)
            culture_title = lang_profile.get("display_name", "文化") + "文化背景"
            await self._tool_exec.execute("show_note", {
                "title": culture_title,
                "content": plan.culture_note,
                "note_type": "culture",
            })
        else:
            # Ask a simple question to re-engage
            ctx = self.memory.get_context(mode="course")
            prompt = build_course_prompt(
                sentence=sentence,
                plan=plan,
                memory_context=ctx,
                profile=self.profile,
                student_input="",
                attention_label="极低（需要立即提问重新吸引注意力）",
                should_advance=False,
                force_question=True,
                target_language=self.curriculum.target_language,
                content_type=self.curriculum.content_type,
            )
            resp = await self._llm.complete(prompt, max_tokens=150)
            if resp:
                _, clean = _extract_tool_calls(resp)
                if clean.strip():
                    self.short.add_turn("teacher", clean.strip())
                    await self._speak(clean.strip())

    # ── LLM streaming ─────────────────────────────────────────────────────────

    async def _stream_with_tools(self, prompt: str):
        """Stream from LLM, yielding text chunks."""
        buffer = ""
        async for chunk in self._llm.stream(prompt, max_tokens=600):
            buffer += chunk
            yield chunk

    # ── Speech ────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """Send teacher text to the frontend (TTS is handled by audio pipeline separately)."""
        await self._send(json.dumps({
            "type": "teacher_text",
            "text": text,
        }, ensure_ascii=False))

    async def _generate_intro_speech(self) -> str:
        """
        Build a language-aware, content-type-aware opening speech.

        Uses the Curriculum's `intro_note` (generated by CurriculumBuilder from
        the language profile and content-type profile) so we never hardcode
        "英语新闻" or any other language/content combination.
        """
        lang_profile = get_language_profile(self.curriculum.target_language)
        ct_profile = get_content_type_profile(self.curriculum.content_type)

        lang_display = lang_profile.get("display_name", self.curriculum.target_language)
        ct_label = ct_profile.get("label", "视频内容")
        ct_intro_frame = ct_profile.get("intro_frame", "")

        brief = self.content.brief[:180] if self.content.brief else ""
        name = self.profile.name
        level = self.profile.level

        # Assemble intro using the curriculum's pre-built intro_note
        intro_note = getattr(self.curriculum, "intro_note", "") or brief

        speech_parts = []

        # Greeting with content-type framing
        if intro_note:
            speech_parts.append(f"{name}，{intro_note}")
        elif ct_intro_frame:
            speech_parts.append(f"{name}，{ct_intro_frame}")
        else:
            speech_parts.append(f"{name}，今天我们来学习一段{lang_display}{ct_label}。")

        # Level acknowledgement
        if brief and not intro_note:
            speech_parts.append(brief[:100] + "..." if len(brief) > 100 else brief)

        speech_parts.append(
            f"你现在的水平是 {level}，我会根据这个来调整讲解深度。"
            "先把整段视频看一遍，感受整体语境，不用担心听不懂——之后我们会逐句细讲。"
        )

        return "".join(speech_parts)

    async def _generate_brief_ack(self, student_text: str) -> str:
        """Minimal acknowledgement when student speaks during the intro video."""
        # Keep short; we don't want to interrupt the video-watching experience
        lang_profile = get_language_profile(self.curriculum.target_language)
        lang_display = lang_profile.get("display_name", "")
        return f"嗯，先把视频看完，看完我们再聊。{'（注意感受一下' + lang_display + '的语感）' if lang_display else ''}"

    # ── Session end ───────────────────────────────────────────────────────────

    async def _end_session(self) -> None:
        self._state.phase = TeachingPhase.END
        await self._send(json.dumps({"type": "teaching_state", "phase": "end"}))

        started_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._session_start)
        )
        await self.memory.save_session(
            learner_id=self.profile.learner_id,
            job_id=self.content.job_id,
            mode=self.mode,
            content=self.content,
            started_at=started_at,
        )

        # Update short-term attention in graph
        self.short.record_attention(self._attention.score)

        lang_profile = get_language_profile(self.curriculum.target_language)
        lang_display = lang_profile.get("display_name", "")
        sentences_done = len(self.short.sentences_covered)
        goodbye = (
            f"好，今天的课就到这里！你学了 {sentences_done} 句{lang_display}内容，做得很好。"
            "记得去做一下 Quiz 来巩固记忆，下次见！"
        )
        await self._speak(goodbye)


# ── Transition message builder ────────────────────────────────────────────────

def _build_transition_message(
    next_idx: int,
    total: int,
    target_language: str,
) -> str:
    """
    Build a brief, natural sentence-transition message.

    Avoids a single hardcoded Chinese string — instead uses the language profile's
    display name so the teacher's meta-commentary feels appropriate for the language
    being studied. The message stays short (one line) and non-formulaic.
    """
    from content.language_profiles import get_language_profile

    lang_profile = get_language_profile(target_language)
    lang_display = lang_profile.get("display_name", "")

    progress = f"{next_idx + 1}/{total}"
    lang_tag = f"（{lang_display}）" if lang_display else ""

    # Rotate phrasing so it doesn't sound robotic after many sentences
    phrases = [
        f"好，我们来看第 {next_idx + 1} 句{lang_tag}。",
        f"接下来是第 {progress} 句，继续。",
        f"来，第 {next_idx + 1} 句——",
        f"第 {progress} 句。",
    ]
    return phrases[next_idx % len(phrases)]


# ── Tool call extraction ───────────────────────────────────────────────────────

def _extract_tool_calls(text: str) -> tuple[list[dict], str]:
    """
    Extract embedded JSON tool calls from LLM response text.
    Format expected at end of response:
      ```json
      {"tool_calls": [{"name": "play_sentence", "arguments": {"sentence_index": 0}}]}
      ```
    Returns (tool_calls, clean_text_without_json_block).
    """
    import re
    tool_calls: list[dict] = []

    pattern = re.compile(r"```json\s*(\{[\s\S]*?\})\s*```", re.MULTILINE)
    matches = list(pattern.finditer(text))

    clean_text = text
    for match in reversed(matches):
        try:
            data = json.loads(match.group(1))
            tcs = data.get("tool_calls", [])
            if isinstance(tcs, list):
                tool_calls.extend(tcs)
        except json.JSONDecodeError:
            pass
        clean_text = clean_text[:match.start()] + clean_text[match.end():]

    return tool_calls, clean_text.strip()
