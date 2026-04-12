from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random

import httpx

from config import get_settings
from voice.tts_client import CosyVoiceClient


class FillerPool:
    """Pre-synthesized filler audio pool."""

    FILLERS = {
        "en": {
            "acknowledge": ["Hmm...", "Well...", "So...", "Right..."],
            "think": ["Let me think...", "Ah...", "Um..."],
            "positive": ["Oh!", "Okay!", "I see!"],
        },
        "zh": {
            "acknowledge": ["嗯...", "这个...", "好的..."],
            "think": ["让我想想...", "嗯..."],
            "positive": ["哦!", "好!", "嗯嗯!"],
        },
        "ja": {
            "acknowledge": ["ええと...", "そうですね...", "はい..."],
            "think": ["ちょっと待ってね...", "うーん..."],
            "positive": ["ああ!", "そう!", "うん!"],
        },
    }

    def __init__(self, data_dir: str = "data/fillers") -> None:
        self.data_dir = data_dir
        self.audio_cache: dict[str, bytes] = {}

    async def presynthesize_all(
        self,
        tts_client: CosyVoiceClient,
        voice_id: str,
        max_retries: int = 3,
    ) -> None:
        for lang, categories in self.FILLERS.items():
            lang_dir = os.path.join(self.data_dir, lang)
            os.makedirs(lang_dir, exist_ok=True)

            for category, texts in categories.items():
                for i, text in enumerate(texts):
                    key = f"{lang}/{category}/{i}"
                    path = os.path.join(lang_dir, f"{category}_{i}.pcm")

                    if not os.path.exists(path):
                        for attempt in range(1, max_retries + 1):
                            try:
                                await tts_client.synthesize_to_file(
                                    text,
                                    path,
                                    voice_id=voice_id,
                                    fmt="pcm",
                                )
                                break
                            except httpx.TimeoutException:
                                if attempt >= max_retries:
                                    raise
                                wait_seconds = min(2 * attempt, 5)
                                logging.warning(
                                    "Timeout synthesizing filler '%s' (%s, retry %s/%s), waiting %ss",
                                    text,
                                    lang,
                                    attempt,
                                    max_retries,
                                    wait_seconds,
                                )
                                await asyncio.sleep(wait_seconds)

                    with open(path, "rb") as f:
                        self.audio_cache[key] = f.read()

    def load_cached(self) -> None:
        if not os.path.isdir(self.data_dir):
            return
        for lang in os.listdir(self.data_dir):
            lang_dir = os.path.join(self.data_dir, lang)
            if not os.path.isdir(lang_dir):
                continue
            for filename in os.listdir(lang_dir):
                if not filename.endswith(".pcm"):
                    continue
                path = os.path.join(lang_dir, filename)
                base = filename[:-4]
                category, _, idx = base.rpartition("_")
                if not category or not idx.isdigit():
                    continue
                key = f"{lang}/{category}/{idx}"
                with open(path, "rb") as f:
                    self.audio_cache[key] = f.read()

    def get_random(self, lang: str, category: str | None = None) -> bytes:
        if category is None:
            categories = list(self.FILLERS.get(lang, {}).keys())
            category = random.choice(categories) if categories else "acknowledge"

        candidates = [k for k in self.audio_cache if k.startswith(f"{lang}/{category}/")]
        if not candidates:
            candidates = [k for k in self.audio_cache if k.startswith(f"{lang}/")]
        if not candidates:
            return b""

        return self.audio_cache[random.choice(candidates)]


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Pre-synthesize filler PCM files")
    parser.add_argument("--voice-id", default="sarah_en")
    args = parser.parse_args()

    settings = get_settings()
    pool = FillerPool(settings.filler_dir.as_posix())
    tts = CosyVoiceClient(
        settings.cosyvoice_http_url,
        connect_timeout_seconds=settings.cosyvoice_connect_timeout_seconds,
        read_timeout_seconds=settings.cosyvoice_read_timeout_seconds,
        write_timeout_seconds=settings.cosyvoice_write_timeout_seconds,
        pool_timeout_seconds=settings.cosyvoice_pool_timeout_seconds,
    )
    try:
        health = await tts.get_health()
        if health.get("status") != "ok":
            error = health.get("error", "unknown error")
            raise SystemExit(
                f"CosyVoice server not ready at {settings.cosyvoice_http_url}: {error}"
            )

        await pool.presynthesize_all(tts, voice_id=args.voice_id)
    finally:
        await tts.close()


if __name__ == "__main__":
    asyncio.run(_main())
