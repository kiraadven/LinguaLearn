"""
Self-Thinking Voice Model

NOT a text-to-speech system. End-to-end voice generation that takes
structured classroom context and directly produces speech audio.

Normal flow (95%+):
  graph_state + persona + delivery_style + context -> VoiceModel -> audio

Exception fallback (<5%):
  LLM supervisor -> text -> TTS adapter -> audio

Core modules:
- schema:     VoiceModelInput, AudioOutput
- persona:    PersonaState, PersonaManager, DELIVERY_STYLE_MAP
- dispatcher: VoiceDispatcher (routes normal vs fallback)
- model/      Model architecture (encoder, thinking, decoder, vocoder)
- fallback/   LLM text -> TTS adapter
"""
