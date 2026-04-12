from __future__ import annotations

from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class InterruptionController:
    """Handle student interruption while teacher is speaking."""

    async def handle(self, router) -> None:
        if router.state != State.SPEAKING:
            return

        if router.tts_task and not router.tts_task.done():
            router.tts_task.cancel()

        await router.ws.send_json({"type": "stop_playback"})

        spoken_text = router.current_utterance[: router.spoken_char_index]
        router.session.add_partial_teacher_turn(spoken_text)

        if router.llm_task and not router.llm_task.done():
            router.llm_task.cancel()

        router.clear_outgoing_audio()
        router.state = State.LISTENING
        await router.ws.send_json({"type": "state_change", "state": "listening"})
