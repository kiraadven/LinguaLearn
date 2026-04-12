from __future__ import annotations

from collections import deque


class AudioMixer:
    """Simple queue mixer: filler first, then synthesized response."""

    def __init__(self) -> None:
        self._queue: deque[bytes] = deque()

    def enqueue(self, chunk: bytes) -> None:
        if chunk:
            self._queue.append(chunk)

    def clear(self) -> None:
        self._queue.clear()

    def pop(self) -> bytes:
        if not self._queue:
            return b""
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)
