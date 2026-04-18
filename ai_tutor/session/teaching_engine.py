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

from ai_tutor.content.loader import LinguaLearnContent
from ai_tutor.content.curriculum import Curriculum
from ai_tutor.content.language_profiles import get_language_profile, get_content_type_profile
from ai_tutor.llm.client import ClaudeClient
from ai_tutor.llm.course_prompts import (
    build_course_system_prompt,
    build_course_turn_message,
    build_review_system_prompt,
    build_review_turn_message,
)
from ai_tutor.llm.global_prompts import (
    build_global_system_prompt,
    build_global_turn_message,
)
from ai_tutor.memory.manager import MemoryManager
from ai_tutor.memory.short_term import ShortTermMemory
from ai_tutor.session.attention_monitor import AttentionMonitor, AttentionLevel
from ai_tutor.session.learner_profile import LearnerProfile
from ai_tutor.tools.definitions import get_tool_schemas
from ai_tutor.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

SendFn = Callable[[str], Awaitable[None]]


class TeachingPhase(str, Enum):
    IDLE = "idle"
    INTRO = "intro"           # Playing full video
    TEACHING = "teaching"     # Sentence-by-sentence
    REVIEW = "review"         # End of sentences, free summary
    END = "end"


@dataclass
class SentenceExecutionPlan:
    sentence_index: int
    objective: str
    focus: str
    question_policy: str = "no_question"  # no_question | light_check
    pace: str = "steady"
    replan_reason: str = ""

    def to_prompt_block(self) -> str:
        lines = [
            f"目标：{self.objective}",
            f"焦点：{self.focus}",
            f"节奏：{self.pace}",
            "提问策略：仅关键节点轻确认" if self.question_policy == "light_check" else "提问策略：本轮不提问",
        ]
        if self.replan_reason:
            lines.append(f"重规划原因：{self.replan_reason}")
        return "\n".join(lines)


@dataclass
class TeachingState:
    phase: TeachingPhase = TeachingPhase.IDLE
    sentence_index: int = 0    # Current sentence being taught
    total_sentences: int = 0
    awaiting_video_end: bool = False  # Waiting for frontend "video ended" event
    awaiting_student: bool = False    # Waiting for student to respond
    shadow_pending: bool = False
    interaction_mode: str = "adaptive"  # adaptive | lecture
    auto_advance_pending: bool = False
    teacher_turns_in_sentence: int = 0
    turns_since_check: int = 0


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
        self._tool_schemas = get_tool_schemas()
        self._send = send_fn
        self._attention = AttentionMonitor()
        self._session_start = time.time()
        self._last_teacher_end: float = time.time()
        self._auto_advance_task: asyncio.Task[None] | None = None
        self._execution_plan: SentenceExecutionPlan | None = None

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
        system_prompt = build_global_system_prompt(
            profile=self.profile,
            target_language=self.curriculum.target_language,
        )
        turn_message = build_global_turn_message(
            memory_context=ctx,
            profile=self.profile,
            student_input="",
            target_language=self.curriculum.target_language,
        )
        resp = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=turn_message,
            messages=self._recent_chat_messages(limit_turns=8),
            max_tokens=400,
        )
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
        self._cancel_auto_advance()
        latency = time.time() - self._last_teacher_end
        self._attention.record_response_latency(latency)
        self._attention.record_student_response(text)
        self.short.add_turn("student", text)

        mode_switch = _detect_interaction_mode_switch(text)
        if mode_switch and mode_switch != self._state.interaction_mode:
            self._state.interaction_mode = mode_switch
            if mode_switch == "lecture":
                await self._speak(
                    "收到，我来主讲，你不用每句都回复。你想打断时直接说“停一下”或“下一句”。"
                )
                if self._execution_plan:
                    self._execution_plan.question_policy = "no_question"
                    self._execution_plan.replan_reason = "学习者请求老师主讲，减少互动负担。"
            else:
                await self._speak("好，我们回到互动模式。我会边讲边少量提问。")
                if self._execution_plan:
                    self._execution_plan.question_policy = "light_check"
                    self._execution_plan.replan_reason = "学习者恢复互动模式，允许轻量确认。"
            if _is_interaction_preference_statement(text):
                return

        if self._state.phase == TeachingPhase.INTRO:
            # If student signals they've finished watching, start teaching immediately
            if _is_ready_signal(text):
                self._state.awaiting_video_end = False
                await self._begin_sentence(0)
            else:
                ack = await self._generate_brief_ack(text)
                await self._speak(ack)
            return

        if self._state.phase == TeachingPhase.TEACHING:
            self._reflect_and_replan(text)
            if _is_next_sentence_signal(text):
                await self._advance_to_next_sentence()
                return
            await self._handle_teaching_interaction(text)
        elif self._state.phase == TeachingPhase.REVIEW:
            await self._handle_review_interaction(text)

    async def _handle_teaching_interaction(self, student_text: str) -> None:
        """Generate teacher response during sentence teaching phase."""
        sentence = self.content.get_sentence(self._state.sentence_index)
        plan = self.curriculum.get_plan(self._state.sentence_index)
        ctx = self.memory.get_context(mode="course")

        system_prompt = build_course_system_prompt(
            profile=self.profile,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )
        allow_question = self._should_allow_question(turn_kind="student_followup")
        planning_stage = "replan" if self._execution_plan and self._execution_plan.replan_reason else "execute"
        turn_message = build_course_turn_message(
            sentence=sentence,
            plan=plan,
            memory_context=ctx,
            profile=self.profile,
            student_input=student_text,
            attention_label=self._attention.to_prompt_label(),
            should_advance=False,
            turn_kind="student_followup",
            interaction_mode=self._state.interaction_mode,
            planning_stage=planning_stage,
            execution_plan=self._execution_plan.to_prompt_block() if self._execution_plan else "",
            allow_question=allow_question,
            current_sentence_index=self._state.sentence_index,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )

        full_response = ""
        streamed_tool_calls: list[dict[str, Any]] = []
        history = self._recent_chat_messages(
            limit_turns=8,
            drop_last_student_text=student_text,
        )

        async for chunk in self._stream_with_tools(
            system_prompt=system_prompt,
            turn_message=turn_message,
            history=history,
            max_tokens=600,
        ):
            if isinstance(chunk, str):
                full_response += chunk
            elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                normalized = _normalize_tool_call(chunk)
                if normalized:
                    streamed_tool_calls.append(normalized)

        tool_calls, clean_text = _merge_tool_calls(
            streamed_calls=streamed_tool_calls,
            response_text=full_response,
        )

        # Speak the clean teacher text
        if clean_text.strip():
            polished_text = _polish_teacher_text(clean_text, allow_question=allow_question)
            if polished_text:
                self.short.add_turn("teacher", polished_text.strip())
                await self._speak(polished_text.strip())
                self._update_turn_cadence(polished_text)

        advanced = await self._execute_tool_calls(tool_calls, allow_advance=True)
        if advanced:
            await self._advance_to_next_sentence()
        elif self._execution_plan:
            # Clear transient replan reason once we've executed this round.
            self._execution_plan.replan_reason = ""

        self._last_teacher_end = time.time()

    async def _handle_review_interaction(self, student_text: str) -> None:
        ctx = self.memory.get_context(mode="global")
        system_prompt = build_global_system_prompt(
            profile=self.profile,
            target_language=self.curriculum.target_language,
        )
        turn_message = build_global_turn_message(
            memory_context=ctx,
            profile=self.profile,
            student_input=student_text,
            target_language=self.curriculum.target_language,
        )
        history = self._recent_chat_messages(
            limit_turns=8,
            drop_last_student_text=student_text,
        )
        resp = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=turn_message,
            messages=history,
            max_tokens=400,
        )
        if resp:
            self.short.add_turn("teacher", resp)
            await self._speak(resp)
        self._last_teacher_end = time.time()

    # ── Sentence flow ─────────────────────────────────────────────────────────

    async def _begin_sentence(self, index: int) -> None:
        if index >= self._state.total_sentences:
            await self._begin_review()
            return

        self._cancel_auto_advance()
        self._state.sentence_index = index
        self._state.phase = TeachingPhase.TEACHING
        self._state.auto_advance_pending = False
        self._state.teacher_turns_in_sentence = 0
        self._state.turns_since_check = 0
        sentence = self.content.get_sentence(index)
        plan = self.curriculum.get_plan(index)
        self._execution_plan = self._build_sentence_execution_plan(index, plan)
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

        system_prompt = build_course_system_prompt(
            profile=self.profile,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )
        allow_question = self._should_allow_question(turn_kind="opening_explain")
        turn_message = build_course_turn_message(
            sentence=sentence,
            plan=plan,
            memory_context=ctx,
            profile=self.profile,
            student_input="",  # Teacher initiates explanation
            attention_label=self._attention.to_prompt_label(),
            should_advance=False,
            turn_kind="opening_explain",
            interaction_mode=self._state.interaction_mode,
            planning_stage="plan_execute",
            execution_plan=self._execution_plan.to_prompt_block() if self._execution_plan else "",
            allow_question=allow_question,
            current_sentence_index=self._state.sentence_index,
            target_language=self.curriculum.target_language,
            content_type=self.curriculum.content_type,
        )

        full_response = ""
        streamed_tool_calls: list[dict[str, Any]] = []
        history = self._recent_chat_messages(limit_turns=8)
        async for chunk in self._stream_with_tools(
            system_prompt=system_prompt,
            turn_message=turn_message,
            history=history,
            max_tokens=600,
        ):
            if isinstance(chunk, str):
                full_response += chunk
            elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                normalized = _normalize_tool_call(chunk)
                if normalized:
                    streamed_tool_calls.append(normalized)

        parsed_tools, clean_text = _merge_tool_calls(
            streamed_calls=streamed_tool_calls,
            response_text=full_response,
        )

        if clean_text.strip():
            polished_text = _polish_teacher_text(clean_text, allow_question=allow_question)
            if polished_text:
                self.short.add_turn("teacher", polished_text.strip())
                await self._speak(polished_text.strip())
                self._update_turn_cadence(polished_text)

        await self._execute_tool_calls(parsed_tools, allow_advance=False)

        # Check if shadow reading is due
        if (
            self._state.interaction_mode != "lecture"
            and plan
            and plan.should_shadow
            and not self._state.shadow_pending
        ):
            self._state.shadow_pending = True
            await self._tool_exec.execute("request_shadow", {
                "text": sentence.text if sentence else "",
                "sentence_index": self._state.sentence_index,
            })
            self.short.shadow_requests += 1

        if self._state.interaction_mode == "lecture":
            self._state.awaiting_student = False
            self._schedule_auto_advance(delay_seconds=1.4)
        else:
            self._state.awaiting_student = True
        self._last_teacher_end = time.time()

    async def _advance_to_next_sentence(self) -> None:
        self._cancel_auto_advance()
        current = self._state.sentence_index
        self.short.mark_sentence_done(current)
        self._state.shadow_pending = False
        self._state.auto_advance_pending = False
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
        self._cancel_auto_advance()
        self._execution_plan = None
        self._state.phase = TeachingPhase.REVIEW
        await self._send(json.dumps({"type": "teaching_state", "phase": "review"}))

        ctx = self.memory.get_context(mode="course")
        system_prompt = build_review_system_prompt(
            profile=self.profile,
            target_language=self.curriculum.target_language,
        )
        turn_message = build_review_turn_message(
            memory_context=ctx,
            profile=self.profile,
            curriculum=self.curriculum,
            student_input="",
            target_language=self.curriculum.target_language,
        )
        resp = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=turn_message,
            messages=self._recent_chat_messages(limit_turns=10),
            max_tokens=400,
        )
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
            system_prompt = build_course_system_prompt(
                profile=self.profile,
                target_language=self.curriculum.target_language,
                content_type=self.curriculum.content_type,
            )
            turn_message = build_course_turn_message(
                sentence=sentence,
                plan=plan,
                memory_context=ctx,
                profile=self.profile,
                student_input="",
                attention_label="极低（需要立即提问重新吸引注意力）",
                should_advance=False,
                force_question=True,
                turn_kind="attention_reengage",
                interaction_mode=self._state.interaction_mode,
                current_sentence_index=self._state.sentence_index,
                target_language=self.curriculum.target_language,
                content_type=self.curriculum.content_type,
            )
            resp = await self._llm.complete(
                system_prompt=system_prompt,
                user_message=turn_message,
                messages=self._recent_chat_messages(limit_turns=8),
                max_tokens=150,
                temperature=0.6,
            )
            if resp:
                _, clean = _extract_tool_calls(resp)
                if clean.strip():
                    self.short.add_turn("teacher", clean.strip())
                    await self._speak(clean.strip())

    # ── LLM streaming ─────────────────────────────────────────────────────────

    async def _stream_with_tools(
        self,
        system_prompt: str,
        turn_message: str,
        history: list[dict[str, str]] | None = None,
        max_tokens: int = 600,
    ):
        """Stream from LLM with native tool calls + JSON-block fallback support."""
        try:
            async for chunk in self._llm.stream(
                system_prompt=system_prompt,
                user_message=turn_message,
                messages=history or [],
                tools=self._tool_schemas,
                tool_choice="auto",
                max_tokens=max_tokens,
                temperature=0.7,
            ):
                yield chunk
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Native tool-calling stream unavailable, fallback to text-json mode: %s",
                exc,
            )

        async for chunk in self._llm.stream(
            system_prompt=system_prompt,
            user_message=turn_message,
            messages=history or [],
            max_tokens=max_tokens,
            temperature=0.7,
        ):
            yield chunk

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        allow_advance: bool = True,
    ) -> bool:
        """
        Execute normalized tool calls safely.

        Returns:
            True if at least one `advance_sentence` tool call was issued.
        """
        should_advance = False
        for tc in tool_calls:
            name = tc.get("name")
            if not isinstance(name, str) or not name.strip():
                logger.warning("Skip malformed tool call (missing name): %s", tc)
                continue
            arguments = tc.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}

            if name == "advance_sentence" and not allow_advance:
                logger.info("Ignore advance_sentence in non-advance phase")
                continue

            await self._tool_exec.execute(name, arguments)
            if name == "advance_sentence":
                should_advance = True
        return should_advance

    def _build_sentence_execution_plan(
        self,
        sentence_index: int,
        sentence_plan: Any | None,
    ) -> SentenceExecutionPlan:
        focus = "综合理解"
        if sentence_plan and getattr(sentence_plan, "focus_areas", None):
            focus = "、".join(sentence_plan.focus_areas)

        if self._state.interaction_mode == "lecture":
            objective = "老师主讲本句核心信息，先讲意思再讲一个重点，不要求学生每轮作答。"
            question_policy = "no_question"
        else:
            objective = "先讲核心意思，再做一个小点讲透；仅在必要节点做轻量确认。"
            question_policy = "light_check"

        pace = "gentle" if str(self.profile.level).upper() in {"A0", "A1", "A2"} else "steady"

        return SentenceExecutionPlan(
            sentence_index=sentence_index,
            objective=objective,
            focus=focus,
            question_policy=question_policy,
            pace=pace,
        )

    def _reflect_and_replan(self, student_text: str) -> None:
        """
        Lightweight reflection step (plan -> execute -> replan loop).

        This runs before each teaching response so the next turn aligns with
        learner engagement and recent signals, rather than repeating a template.
        """
        if not self._execution_plan:
            return

        low = student_text.lower().strip()
        if not low:
            return

        if _is_disengaged_signal(low):
            self._execution_plan.question_policy = "no_question"
            self._execution_plan.objective = "降低互动负担，老师连续讲解，优先保证理解不断线。"
            self._execution_plan.replan_reason = "学习者出现抗拒/厌烦信号。"
            self._append_session_note("检测到学习者抗拒互动，切换为低提问连续讲解。")
            return

        if _is_confusion_signal(low):
            self._execution_plan.question_policy = "no_question"
            self._execution_plan.objective = "先用白话重述，再拆一个关键词，避免再加新负担。"
            self._execution_plan.replan_reason = "学习者表达听不懂/理解困难。"
            self._append_session_note("学习者有理解困难，已重规划为先释义后拆点。")
            return

        if self._state.interaction_mode == "lecture":
            self._execution_plan.question_policy = "no_question"
            self._execution_plan.replan_reason = ""
            return

        # Adaptive mode fallback: keep checks sparse.
        self._execution_plan.question_policy = "light_check"
        self._execution_plan.replan_reason = ""

    def _append_session_note(self, note: str) -> None:
        self.short.session_notes.append(note)
        if len(self.short.session_notes) > 20:
            self.short.session_notes = self.short.session_notes[-20:]

    def _should_allow_question(self, turn_kind: str) -> bool:
        if self._state.interaction_mode == "lecture":
            return False
        if turn_kind == "opening_explain":
            return False
        if self._execution_plan and self._execution_plan.question_policy == "no_question":
            return False
        # Keep question cadence sparse (avoid each-turn questioning).
        return self._state.turns_since_check >= 2

    def _update_turn_cadence(self, teacher_text: str) -> None:
        self._state.teacher_turns_in_sentence += 1
        if _contains_question(teacher_text):
            self._state.turns_since_check = 0
        else:
            self._state.turns_since_check += 1

    def _cancel_auto_advance(self) -> None:
        task = self._auto_advance_task
        if task and not task.done():
            task.cancel()
        self._state.auto_advance_pending = False
        self._auto_advance_task = None

    def _schedule_auto_advance(self, delay_seconds: float = 0.75) -> None:
        self._cancel_auto_advance()
        self._state.auto_advance_pending = True

        async def _runner() -> None:
            try:
                await asyncio.sleep(delay_seconds)
                if (
                    self._state.phase == TeachingPhase.TEACHING
                    and self._state.interaction_mode == "lecture"
                ):
                    await self._advance_to_next_sentence()
            except asyncio.CancelledError:
                raise
            finally:
                self._state.auto_advance_pending = False
                self._auto_advance_task = None

        self._auto_advance_task = asyncio.create_task(_runner())

    def _recent_chat_messages(
        self,
        limit_turns: int = 8,
        drop_last_student_text: str | None = None,
    ) -> list[dict[str, str]]:
        """Convert recent short-term turns into chat messages for the LLM API."""
        turns = self.short.recent_turns(limit_turns)
        if (
            drop_last_student_text
            and turns
            and turns[-1].role == "student"
            and turns[-1].text.strip() == drop_last_student_text.strip()
        ):
            turns = turns[:-1]

        messages: list[dict[str, str]] = []
        for t in turns:
            text = t.text.strip()
            if not text:
                continue
            role = "assistant" if t.role == "teacher" else "user"
            messages.append({"role": role, "content": text})
        return messages

    # ── Speech ────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """Send teacher text to the frontend (TTS is handled by audio pipeline separately)."""
        await self._send(json.dumps({
            "type": "teacher_text",
            "text": text,
        }, ensure_ascii=False))

    async def _generate_intro_speech(self) -> str:
        """Build a short, natural opening greeting for the student."""
        lang_profile = get_language_profile(self.curriculum.target_language)
        ct_profile = get_content_type_profile(self.curriculum.content_type)

        lang_display = lang_profile.get("display_name", self.curriculum.target_language)
        ct_label = ct_profile.get("label", "视频内容")

        name = self.profile.name
        level = self.profile.level
        total = self._state.total_sentences

        system_prompt = (
            "你是一名自然、亲切、专业的语言老师。"
            "请给学生一段 2-3 句的开场白，语气像真人老师，避免模板腔。"
        )
        turn_message = (
            f"学习者姓名：{name}\\n"
            f"目标语：{lang_display}\\n"
            f"内容类型：{ct_label}\\n"
            f"学习者水平：{level}\\n"
            f"总句数：{total}\\n"
            "要求：先欢迎，再简要说明学习方式（先看整段后逐句），鼓励但不过度夸张。"
        )
        try:
            intro = await self._llm.complete(
                system_prompt=system_prompt,
                user_message=turn_message,
                messages=self._recent_chat_messages(limit_turns=4),
                max_tokens=180,
                temperature=0.8,
            )
            if intro.strip():
                _, clean_intro = _extract_tool_calls(intro)
                if clean_intro.strip():
                    return clean_intro.strip()
        except Exception as exc:
            logger.warning("Dynamic intro generation failed, use fallback: %s", exc)

        return (
            f"{name}，今天我们来学习一段{lang_display}{ct_label}，共{total}句。"
            f"你现在的水平是 {level}，我会根据这个来调整讲解深度。"
            "先把整段视频看一遍，感受整体语境，不用担心听不懂——之后我们会逐句细讲。"
        )

    async def _generate_brief_ack(self, student_text: str) -> str:
        """Minimal acknowledgement when student speaks during the intro video."""
        # Keep short; we don't want to interrupt the video-watching experience
        lang_profile = get_language_profile(self.curriculum.target_language)
        lang_display = lang_profile.get("display_name", "")
        return f"嗯，先把视频看完，看完我们再聊。{'（注意感受一下' + lang_display + '的语感）' if lang_display else ''}"

    # ── Session end ───────────────────────────────────────────────────────────

    async def _end_session(self) -> None:
        self._cancel_auto_advance()
        self._execution_plan = None
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
        goodbye = ""
        try:
            goodbye = await self._llm.complete(
                system_prompt=(
                    "你是一名真人感很强的语言老师。"
                    "请生成 2 句自然的下课结束语，避免模板腔。"
                ),
                user_message=(
                    f"目标语：{lang_display}\\n"
                    f"本节完成句数：{sentences_done}\\n"
                    "要求：第一句总结学生进展；第二句给一个轻量可执行的课后建议（可提 quiz）。"
                ),
                messages=self._recent_chat_messages(limit_turns=8),
                max_tokens=120,
                temperature=0.75,
            )
        except Exception as exc:
            logger.warning("Dynamic closing generation failed, use fallback: %s", exc)

        if goodbye.strip():
            _, clean_goodbye = _extract_tool_calls(goodbye)
            goodbye = clean_goodbye.strip()

        if not goodbye:
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
    from ai_tutor.content.language_profiles import get_language_profile

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

def _extract_tool_calls(text: str) -> tuple[list[dict[str, Any]], str]:
    """
    Extract embedded JSON tool calls from LLM response text.
    Format expected at end of response:
      ```json
      {"tool_calls": [{"name": "play_sentence", "arguments": {"sentence_index": 0}}]}
      ```
    Returns (tool_calls, clean_text_without_json_block).
    """
    import re
    tool_calls: list[dict[str, Any]] = []

    pattern = re.compile(r"```json\s*(\{[\s\S]*?\})\s*```", re.MULTILINE)
    matches = list(pattern.finditer(text))

    clean_text = text
    for match in reversed(matches):
        try:
            data = json.loads(match.group(1))
            tcs = data.get("tool_calls", [])
            if isinstance(tcs, dict):
                tcs = [tcs]
            if isinstance(tcs, list):
                tool_calls.extend(_normalize_tool_calls(tcs))
            else:
                single_call = _normalize_tool_call(data)
                if single_call:
                    tool_calls.append(single_call)
        except json.JSONDecodeError:
            pass
        clean_text = clean_text[:match.start()] + clean_text[match.end():]

    return tool_calls, clean_text.strip()


def _merge_tool_calls(
    streamed_calls: list[dict[str, Any]],
    response_text: str,
) -> tuple[list[dict[str, Any]], str]:
    """
    Merge native streamed tool_calls with JSON-embedded fallback calls.

    Dedupes by (name, arguments-json) to avoid double execution when a provider
    emits both tool_calls and a textual JSON block in the same turn.
    """
    parsed_calls, clean_text = _extract_tool_calls(response_text)
    merged = _normalize_tool_calls(streamed_calls) + _normalize_tool_calls(parsed_calls)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for call in merged:
        key = (
            f"{call['name']}::"
            + json.dumps(call["arguments"], ensure_ascii=False, sort_keys=True)
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(call)

    return deduped, clean_text


def _normalize_tool_calls(raw_calls: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_calls:
        call = _normalize_tool_call(raw)
        if call:
            normalized.append(call)
    return normalized


def _normalize_tool_call(raw_call: Any) -> dict[str, Any] | None:
    if not isinstance(raw_call, dict):
        return None

    name = raw_call.get("name") or raw_call.get("tool") or raw_call.get("action")
    arguments = (
        raw_call.get("arguments")
        or raw_call.get("args")
        or raw_call.get("input")
        or raw_call.get("parameters")
    )

    function_payload = raw_call.get("function")
    if isinstance(function_payload, dict):
        if not name:
            name = (
                function_payload.get("name")
                or function_payload.get("tool")
                or function_payload.get("action")
            )
        if arguments is None:
            arguments = (
                function_payload.get("arguments")
                or function_payload.get("args")
                or function_payload.get("input")
            )

    if not isinstance(name, str):
        logger.warning("Skip invalid tool call without name: %s", raw_call)
        return None
    name = name.strip()
    if not name:
        logger.warning("Skip empty-name tool call: %s", raw_call)
        return None

    if isinstance(arguments, str):
        try:
            parsed_args = json.loads(arguments)
            arguments = parsed_args if isinstance(parsed_args, dict) else {}
        except json.JSONDecodeError:
            arguments = {}
    elif not isinstance(arguments, dict):
        arguments = {}

    return {"name": name, "arguments": arguments}


# ── Ready-signal detection ─────────────────────────────────────────────────────

_READY_PATTERNS = [
    # Chinese
    "看完了", "看过了", "看好了", "已经看了", "看完", "看好",
    "开始吧", "直接开始", "进入正题", "直接进", "开始讲",
    "跳过", "skip", "结束了", "好了", "准备好了", "可以开始",
    # English shortcuts
    "done", "ready", "let's go", "start", "begin",
]

_NEXT_SENTENCE_PATTERNS = [
    "下一句", "下句", "next", "continue", "继续", "skip",
]

_LECTURE_MODE_PATTERNS = [
    "别让我选", "不要互动", "不互动", "你一直自己说",
    "你自己说", "我不和你互动", "少问我", "别问我",
    "你讲就行", "不用问我", "我不想回答",
]

_ADAPTIVE_MODE_PATTERNS = [
    "可以互动", "可以问我", "多问我", "恢复互动",
    "normal mode", "interactive mode",
]

_DISENGAGED_PATTERNS = [
    "有病", "烦", "别问", "不和你互动", "不互动",
    "你自己说", "别让我选", "不想回答", "stop asking",
]

_CONFUSION_PATTERNS = [
    "听不懂", "不懂", "啥意思", "什么意思", "没懂",
    "confused", "don't understand", "not understand",
]

def _is_ready_signal(text: str) -> bool:
    """Return True if the student text indicates they've finished watching."""
    lower = text.lower().strip()
    return any(kw in lower for kw in _READY_PATTERNS)


def _is_next_sentence_signal(text: str) -> bool:
    lower = text.lower().strip()
    return any(kw in lower for kw in _NEXT_SENTENCE_PATTERNS)


def _detect_interaction_mode_switch(text: str) -> str | None:
    lower = text.lower().strip()
    if any(kw in lower for kw in _LECTURE_MODE_PATTERNS):
        return "lecture"
    if any(kw in lower for kw in _ADAPTIVE_MODE_PATTERNS):
        return "adaptive"
    return None


def _is_interaction_preference_statement(text: str) -> bool:
    lower = text.lower().strip()
    return any(kw in lower for kw in (_LECTURE_MODE_PATTERNS + _ADAPTIVE_MODE_PATTERNS))


def _is_disengaged_signal(text: str) -> bool:
    return any(kw in text for kw in _DISENGAGED_PATTERNS)


def _is_confusion_signal(text: str) -> bool:
    return any(kw in text for kw in _CONFUSION_PATTERNS)


def _contains_question(text: str) -> bool:
    return "?" in text or "？" in text


def _polish_teacher_text(text: str, allow_question: bool) -> str:
    import re

    cleaned = text.strip()
    if not cleaned:
        return ""

    # Keep teacher persona stable; avoid flippant or self-deprecating lines.
    banned_fragments = [
        "骂我也没事",
        "我就当你在跟我聊天",
        "你爱看就看",
        "不回也没关系",
        "哈哈",
    ]
    for frag in banned_fragments:
        cleaned = cleaned.replace(frag, "")

    if allow_question:
        return re.sub(r"\s+", " ", cleaned).strip()

    # No-question mode: strip explicit question sentences.
    parts = re.split(r"(?<=[。！？!?])", cleaned)
    kept = [p.strip() for p in parts if p.strip() and not p.strip().endswith(("?", "？"))]
    if kept:
        cleaned = " ".join(kept)
    else:
        cleaned = cleaned.replace("？", "。").replace("?", "。")

    cleaned = re.sub(r"[，,]\s*[。.!！]", "。", cleaned)
    cleaned = re.sub(r"[。.!！]{2,}", "。", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", cleaned):
        return ""
    return cleaned
