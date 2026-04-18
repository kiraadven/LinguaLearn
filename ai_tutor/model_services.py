from __future__ import annotations

import asyncio
import logging
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ai_tutor.config import Settings

logger = logging.getLogger(__name__)


def _is_local_host(host: str) -> bool:
    low = host.lower()
    return low in {"127.0.0.1", "localhost", "::1", "0.0.0.0", "::"}


def _connect_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _parse_host_port(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or default_port
    return host, int(port)


def _is_port_open(host: str, port: int, timeout_seconds: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _is_websocket_ready(url: str, timeout_seconds: float = 1.0) -> bool:
    try:
        import websockets
    except Exception:
        return False

    async def _check() -> bool:
        async with websockets.connect(
            url,
            open_timeout=timeout_seconds,
            close_timeout=timeout_seconds,
            max_size=1,
        ):
            return True

    try:
        return asyncio.run(_check())
    except Exception:
        return False


def _is_http_ready(url: str, timeout_seconds: float = 1.0) -> bool:
    req = Request(url=url, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            # CosyVoice /health returns 200 when ready and "degraded" when not ready.
            # Any HTTP response here means the HTTP server itself is up.
            return 100 <= int(resp.status) < 500
    except Exception:
        return False


def _wait_service_ready(
    ready_check: Callable[[], bool],
    timeout_seconds: float,
    process: subprocess.Popen | None = None,
) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if ready_check():
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.5)
    return False


@dataclass
class ManagedService:
    name: str
    process: subprocess.Popen
    host: str
    port: int


class ModelServiceManager:
    """Optionally auto-start local FunASR/CosyVoice services for development."""

    def __init__(self, settings: Settings, project_dir: Path) -> None:
        self.settings = settings
        self.project_dir = project_dir
        self._managed: dict[str, ManagedService] = {}
        self._lock = asyncio.Lock()

    async def ensure_started(self) -> None:
        if not self.settings.auto_start_model_services:
            return
        async with self._lock:
            await asyncio.to_thread(self._ensure_started_sync)

    async def stop_managed(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._stop_managed_sync)

    def _ensure_started_sync(self) -> None:
        python_bin = self.settings.model_service_python_bin or sys.executable

        # FunASR
        fun_host, fun_port = _parse_host_port(self.settings.funasr_ws_url, 10095)
        fun_connect_host = _connect_host(fun_host)
        fun_parsed = urlparse(self.settings.funasr_ws_url)
        fun_scheme = fun_parsed.scheme or "ws"
        fun_path = fun_parsed.path or ""
        if fun_parsed.query:
            fun_path = f"{fun_path}?{fun_parsed.query}"
        fun_probe_url = f"{fun_scheme}://{fun_connect_host}:{fun_port}{fun_path}"
        self._ensure_one_service(
            name="funasr",
            host=fun_host,
            port=fun_port,
            command=[
                python_bin,
                "models/funasr_server.py",
                "--host",
                "0.0.0.0",
                "--port",
                str(fun_port),
                "--device",
                self.settings.funasr_device,
            ],
            ready_check=lambda: _is_websocket_ready(fun_probe_url),
        )

        # CosyVoice
        cosy_host, cosy_port = _parse_host_port(self.settings.cosyvoice_http_url, 9880)
        cosy_connect_host = _connect_host(cosy_host)
        cosy_parsed = urlparse(self.settings.cosyvoice_http_url)
        cosy_scheme = cosy_parsed.scheme or "http"
        cosy_base_path = cosy_parsed.path.rstrip("/")
        cosy_health_path = f"{cosy_base_path}/health" if cosy_base_path else "/health"
        cosy_health_url = f"{cosy_scheme}://{cosy_connect_host}:{cosy_port}{cosy_health_path}"
        self._ensure_one_service(
            name="cosyvoice",
            host=cosy_host,
            port=cosy_port,
            command=[
                python_bin,
                "models/cosyvoice_server.py",
                "--host",
                "0.0.0.0",
                "--port",
                str(cosy_port),
            ],
            ready_check=lambda: _is_http_ready(cosy_health_url),
        )

    def _ensure_one_service(
        self,
        name: str,
        host: str,
        port: int,
        command: list[str],
        ready_check: Callable[[], bool] | None = None,
    ) -> None:
        if name in self._managed:
            proc = self._managed[name].process
            if proc.poll() is None:
                return
            self._managed.pop(name, None)

        connect_host = _connect_host(host)
        if not _is_local_host(host):
            logger.info(
                "Skip auto-start for %s: host '%s' is not local (assume external service).",
                name,
                host,
            )
            return

        effective_check = ready_check or (lambda: _is_port_open(connect_host, port))
        if effective_check():
            logger.info(
                "%s already listening on %s:%s; auto-start not needed.",
                name,
                connect_host,
                port,
            )
            return

        logger.info("Auto-starting %s with command: %s", name, " ".join(command))
        process = subprocess.Popen(command, cwd=self.project_dir.as_posix())

        if not _wait_service_ready(
            effective_check,
            timeout_seconds=self.settings.model_service_startup_timeout_seconds,
            process=process,
        ):
            logger.error(
                "Auto-started %s but %s:%s did not become ready in %.1fs.",
                name,
                connect_host,
                port,
                self.settings.model_service_startup_timeout_seconds,
            )
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                pass
            return

        self._managed[name] = ManagedService(
            name=name,
            process=process,
            host=connect_host,
            port=port,
        )
        logger.info("%s is ready on %s:%s", name, connect_host, port)

    def _stop_managed_sync(self) -> None:
        for name, svc in list(self._managed.items()):
            proc = svc.process
            if proc.poll() is not None:
                continue
            logger.info("Stopping managed service: %s (pid=%s)", name, proc.pid)
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._managed.clear()
