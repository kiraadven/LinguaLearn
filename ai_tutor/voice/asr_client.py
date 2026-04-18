from __future__ import annotations

import asyncio
import json
import logging

import websockets


class ASRFinalTimeoutError(RuntimeError):
    """Raised when ASR final result times out with no transcript."""


class FunASRClient:
    """FunASR WebSocket streaming ASR client."""

    def __init__(self, server_url: str, *, final_timeout_seconds: float = 30.0) -> None:
        self.server_url = server_url
        self.final_timeout_seconds = final_timeout_seconds
        self.ws = None

    async def start_stream(self) -> None:
        if self.ws is not None:
            await self.ws.close()
        self.ws = await websockets.connect(self.server_url, max_size=8 * 1024 * 1024)
        await self.ws.send(
            json.dumps(
                {
                    "mode": "2pass",
                    "chunk_size": [5, 10, 5],
                    "wav_name": "realtime",
                    "is_speaking": True,
                    "wav_format": "pcm",
                    "audio_fs": 16000,
                }
            )
        )

    async def feed_chunk(self, pcm_data: bytes) -> None:
        if self.ws is not None:
            await self.ws.send(pcm_data)

    async def get_final(self) -> str:
        if self.ws is None:
            return ""

        final_text = ""
        try:
            await self.ws.send(json.dumps({"is_speaking": False}))
            deadline = asyncio.get_running_loop().time() + self.final_timeout_seconds
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError

                msg = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
                if isinstance(msg, bytes):
                    continue

                try:
                    result = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                text = str(result.get("text", "")).strip()
                if text:
                    final_text = text
                if result.get("is_final"):
                    break
        except asyncio.TimeoutError:
            if final_text:
                logging.warning(
                    "FunASR final result timeout (>%.1fs), returning best-effort transcript.",
                    self.final_timeout_seconds,
                )
            else:
                raise ASRFinalTimeoutError(
                    f"FunASR final result timeout (>{self.final_timeout_seconds:.1f}s)."
                )
        except websockets.exceptions.ConnectionClosedOK:
            # Peer closed gracefully; keep best-effort transcript if any.
            pass
        except websockets.exceptions.ConnectionClosedError as exc:
            logging.warning("FunASR websocket closed before final result: %s", exc)
        finally:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        return final_text
