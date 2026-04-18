from __future__ import annotations

from typing import Any, AsyncIterator

import httpx


class CosyVoiceClient:
    """CosyVoice 2 streaming TTS client."""

    def __init__(
        self,
        server_url: str,
        *,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 180.0,
        write_timeout_seconds: float = 60.0,
        pool_timeout_seconds: float = 60.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        # This client only talks to a local CosyVoice service, so ignore proxy
        # env vars to avoid accidental localhost->proxy routing and timeouts.
        self.client = httpx.AsyncClient(timeout=timeout, trust_env=False)

    @staticmethod
    def _raise_for_status_with_detail(response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload.get("error") or "")
        except Exception:
            detail = ""

        if not detail:
            detail = response.text.strip()

        message = (
            f"Server error '{response.status_code} {response.reason_phrase}' "
            f"for url '{response.request.url}'"
        )
        if detail:
            message += f" | detail: {detail}"

        raise httpx.HTTPStatusError(message, request=response.request, response=response)

    async def get_health(self) -> dict[str, Any]:
        response = await self.client.get(f"{self.server_url}/health")
        self._raise_for_status_with_detail(response)
        try:
            payload = response.json()
        except Exception:
            return {"status": "unknown", "raw": response.text}
        if isinstance(payload, dict):
            return payload
        return {"status": "unknown", "raw": payload}

    async def stream_synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        language: str = "en",
        prompt_text: str = "",
    ) -> AsyncIterator[bytes]:
        async with self.client.stream(
            "POST",
            f"{self.server_url}/api/tts/stream",
            json={
                "text": text,
                "voice_id": voice_id,
                "speed": speed,
                "format": "pcm",
                "sample_rate": 24000,
                "language": language,
                "prompt_text": prompt_text,
            },
        ) as response:
            self._raise_for_status_with_detail(response)
            async for chunk in response.aiter_bytes(chunk_size=4800):
                if chunk:
                    yield chunk

    async def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        voice_id: str = "default",
        fmt: str = "pcm",
        sample_rate: int = 24000,
        language: str = "en",
        prompt_text: str = "",
    ) -> None:
        """Synthesize *text* and write to *output_path* via the streaming endpoint."""
        with open(output_path, "wb") as f:
            async with self.client.stream(
                "POST",
                f"{self.server_url}/api/tts/stream",
                json={
                    "text": text,
                    "voice_id": voice_id,
                    "speed": 1.0,
                    "format": "pcm",
                    "sample_rate": sample_rate,
                    "language": language,
                    "prompt_text": prompt_text,
                },
            ) as response:
                self._raise_for_status_with_detail(response)
                async for chunk in response.aiter_bytes(chunk_size=4800):
                    if chunk:
                        f.write(chunk)

    async def close(self) -> None:
        await self.client.aclose()
