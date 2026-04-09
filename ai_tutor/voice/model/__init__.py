"""
Self-Thinking Voice Model Architecture

4-stage pipeline:
1. StructuredEncoder:  context (~30 fields) -> condition vector (1024d)
2. ThinkingModule:     condition -> planning tokens (32-128 tokens)
3. SpeechDecoder:      planning tokens -> audio tokens
4. Vocoder:            audio tokens -> PCM waveform

The ThinkingModule is the core innovation: it generates a learned
latent representation of "what to say and how to say it" WITHOUT
going through text. Trained end-to-end with the SpeechDecoder.
"""
