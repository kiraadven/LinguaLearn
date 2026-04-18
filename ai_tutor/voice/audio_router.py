from __future__ import annotations

import asyncio
import json
import logging

from ai_tutor.config import get_settings
from ai_tutor.voice.asr_client import FunASRClient
from ai_tutor.voice.audio_mixer import AudioMixer
from ai_tutor.voice.filler import FillerPool
from ai_tutor.voice.interruption import InterruptionController, State
from ai_tutor.voice.tts_client import CosyVoiceClient
from ai_tutor.voice.vad import SileroVAD


class AudioRouter:
    """Full-duplex audio routing: VAD -> ASR -> LLM -> TTS."""

    def __init__(self, ws, session) -> None:
        self.ws = ws
        self.session = session
        self.state = State.IDLE

        settings = get_settings()
        self.vad = SileroVAD()
        self.asr = FunASRClient(
            settings.funasr_ws_url,
            final_timeout_seconds=settings.asr_final_timeout_seconds,
        )
        self.tts = CosyVoiceClient(
            settings.cosyvoice_http_url,
            connect_timeout_seconds=settings.cosyvoice_connect_timeout_seconds,
            read_timeout_seconds=settings.cosyvoice_read_timeout_seconds,
            write_timeout_seconds=settings.cosyvoice_write_timeout_seconds,
            pool_timeout_seconds=settings.cosyvoice_pool_timeout_seconds,
        )
        self.filler = FillerPool(settings.filler_dir.as_posix())
        self.filler.load_cached()

        self.interruption = InterruptionController()

        self.incoming_audio: asyncio.Queue[bytes] = asyncio.Queue()

        # Audio output pipeline: AudioMixer stages chunks synchronously;
        # _send_signal wakes up send_loop so it can drain the mixer.
        self.mixer = AudioMixer()
        self._send_signal: asyncio.Queue[None] = asyncio.Queue()

        self.tts_task: asyncio.Task | None = None
        self.llm_task: asyncio.Task | None = None
        self.current_utterance = ""
        self.spoken_char_index = 0

        self._student_is_speaking = False
        self._student_speech_ms = 0
        self._backchannel_sent = False

    @staticmethod
    def _on_background_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logging.error(
                "Background task failed: %s",
                exc,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def _set_llm_task(self, coro) -> None:
        if self.llm_task and not self.llm_task.done():
            self.llm_task.cancel()
        self.llm_task = asyncio.create_task(coro)
        self.llm_task.add_done_callback(self._on_background_task_done)

    async def _safe_send_json(self, payload: dict) -> None:
        try:
            await self.ws.send_json(payload)
        except Exception:
            pass

    async def _notify_error(self, message: str) -> None:
        await self._safe_send_json({"type": "error", "message": message})

    def clear_outgoing_audio(self) -> None:
        """Drop all buffered audio immediately (used on interruption)."""
        self.mixer.clear()
        while True:
            try:
                self._send_signal.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _enqueue_audio(self, chunk: bytes) -> None:
        """Stage *chunk* in the mixer and wake up send_loop."""
        if chunk:
            self.mixer.enqueue(chunk)
            await self._send_signal.put(None)

    async def receive_loop(self) -> None:
        while True:
            msg = await self.ws.receive()
            msg_type = msg.get("type")
            if msg_type == "websocket.disconnect":
                raise RuntimeError("WebSocket disconnected")

            if "bytes" in msg and msg["bytes"] is not None:
                await self.incoming_audio.put(msg["bytes"])
                continue

            if "text" in msg and msg["text"]:
                await self._handle_control_message(msg["text"])

    async def _handle_control_message(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return

        msg_type = payload.get("type")
        if msg_type == "session_end":
            raise RuntimeError("Session ended by client")
        if msg_type == "text_input":
            transcript = (payload.get("text") or "").strip()
            if transcript:
                self._set_llm_task(self._generate_response(transcript))

    async def process_loop(self) -> None:
        while True:
            frame = await self.incoming_audio.get()
            vad_result = self.vad.process(frame)

            if vad_result.speech_start and not self._student_is_speaking:
                self._student_is_speaking = True
                self._student_speech_ms = 0
                self._backchannel_sent = False

                if self.state == State.SPEAKING:
                    await self.interruption.handle(self)

                self.state = State.LISTENING
                await self._safe_send_json({"type": "state_change", "state": "listening"})
                try:
                    await self.asr.start_stream()
                except Exception as exc:
                    self._student_is_speaking = False
                    self.state = State.IDLE
                    logging.warning("Failed to start FunASR stream: %s", exc)
                    await self._notify_error("ASR 服务不可用，请检查 10095 端口。")
                    await self._safe_send_json({"type": "state_change", "state": "idle"})
                    continue

            if self._student_is_speaking:
                self._student_speech_ms += 32
                try:
                    await self.asr.feed_chunk(frame)
                except Exception as exc:
                    self._student_is_speaking = False
                    self.state = State.IDLE
                    logging.warning("Failed to feed audio to FunASR: %s", exc)
                    await self._notify_error("语音识别中断，请稍后重试。")
                    await self._safe_send_json({"type": "state_change", "state": "idle"})
                    continue

                if (
                    self._student_speech_ms >= 2000
                    and not self._backchannel_sent
                    and vad_result.probability < 0.25
                ):
                    await self._inject_backchannel()
                    self._backchannel_sent = True

            if vad_result.speech_end and self._student_is_speaking:
                self._student_is_speaking = False
                self.state = State.PROCESSING
                await self._safe_send_json({"type": "state_change", "state": "processing"})

                filler_audio = self.filler.get_random(self.session.language)
                if filler_audio:
                    await self._enqueue_audio(filler_audio)

                try:
                    transcript = (await self.asr.get_final()).strip()
                except Exception as exc:
                    transcript = ""
                    logging.warning("Failed to get ASR final text: %s", exc)
                    await self._notify_error("语音识别返回超时，请重试。")

                await self._safe_send_json(
                    {
                        "type": "transcript",
                        "text": transcript,
                        "is_final": True,
                    }
                )

                if transcript:
                    fast = self.session.maybe_fast_response(transcript)
                    if fast is not None:
                        self._set_llm_task(self._speak_fast_response(transcript, fast))
                    else:
                        self._set_llm_task(self._generate_response(transcript))
                else:
                    self.state = State.IDLE
                    await self._safe_send_json({"type": "state_change", "state": "idle"})

    async def _inject_backchannel(self) -> None:
        audio = self.filler.get_random(self.session.language, category="acknowledge")
        if audio:
            await self._enqueue_audio(audio)

    async def _synthesize_sentence(self, sentence: str) -> None:
        async for audio_chunk in self.tts.stream_synthesize(
            text=sentence,
            voice_id=self.session.voice_id,
        ):
            await self._enqueue_audio(audio_chunk)

    async def _speak_fast_response(self, student_text: str, parsed: dict) -> None:
        self.state = State.SPEAKING
        await self._safe_send_json({"type": "state_change", "state": "speaking"})

        self.current_utterance = parsed["text"]
        self.spoken_char_index = 0

        try:
            self.tts_task = asyncio.create_task(self._synthesize_sentence(parsed["text"]))
            await self.tts_task
            self.spoken_char_index = len(parsed["text"])

            await self._safe_send_json(
                {
                    "type": "teacher_text",
                    "text": parsed["text"],
                    "action": parsed.get("action", "encourage"),
                }
            )
            self.session.update(student_text, parsed)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.warning("Fast response TTS failed: %s", exc)
            await self._notify_error("语音合成失败，请检查 9880 服务。")
        finally:
            if self.state == State.SPEAKING:
                self.state = State.IDLE
                await self._safe_send_json({"type": "state_change", "state": "idle"})

    async def _generate_response(self, student_text: str) -> None:
        self.state = State.SPEAKING
        await self._safe_send_json({"type": "state_change", "state": "speaking"})

        prompt = self.session.build_prompt(student_text)
        sentence_buffer = ""
        full_response = ""
        self.current_utterance = ""
        self.spoken_char_index = 0

        try:
            async for token in self.session.llm.stream(prompt):
                sentence_buffer += token
                full_response += token

                if self._is_sentence_end(sentence_buffer):
                    self.current_utterance += sentence_buffer
                    self.tts_task = asyncio.create_task(self._synthesize_sentence(sentence_buffer))
                    await self.tts_task
                    self.spoken_char_index = len(self.current_utterance)
                    sentence_buffer = ""

            if sentence_buffer.strip():
                self.current_utterance += sentence_buffer
                self.tts_task = asyncio.create_task(self._synthesize_sentence(sentence_buffer))
                await self.tts_task
                self.spoken_char_index = len(self.current_utterance)

            parsed = self.session.parse_response(full_response)
            await self._safe_send_json(
                {
                    "type": "teacher_text",
                    "text": parsed["text"],
                    "action": parsed["action"],
                }
            )

            old_phase = self.session.context.current_phase
            self.session.update(student_text, parsed)
            new_phase = self.session.context.current_phase
            if new_phase != old_phase:
                await self._safe_send_json(
                    {
                        "type": "phase_change",
                        "phase": new_phase,
                        "focus": self.session.context.lesson_focus,
                    }
                )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.exception("LLM/TTS response pipeline failed: %s", exc)
            await self._notify_error("模型响应失败，请检查 LLM/TTS 服务配置。")
        finally:
            if self.state == State.SPEAKING:
                self.state = State.IDLE
                await self._safe_send_json({"type": "state_change", "state": "idle"})

    async def send_loop(self) -> None:
        """Drain the AudioMixer and forward chunks to the browser."""
        while True:
            await self._send_signal.get()
            chunk = self.mixer.pop()
            if chunk:
                await self.ws.send_bytes(chunk)

    async def close(self) -> None:
        if self.llm_task and not self.llm_task.done():
            self.llm_task.cancel()
        if self.tts_task and not self.tts_task.done():
            self.tts_task.cancel()
        await self.tts.close()

    @staticmethod
    def _is_sentence_end(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        return stripped.endswith((".", "?", "!", "。", "？", "！"))
