"""FunASR WebSocket server launcher."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import websockets

try:
    from funasr import AutoModel
except ModuleNotFoundError as exc:  # pragma: no cover - startup guard
    raise SystemExit(
        "Missing dependency: funasr. Install with `python -m pip install -r requirements.txt`."
    ) from exc

REMOTE_MODEL_ID = "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
LOCAL_MODEL_DIR = Path(__file__).resolve().parent / "assets" / "funasr"


def _default_model() -> str:
    if LOCAL_MODEL_DIR.exists():
        return str(LOCAL_MODEL_DIR)
    return REMOTE_MODEL_ID


def _extract_text(result: Any) -> str:
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            return str(first.get("text", ""))
        if isinstance(first, list) and first and isinstance(first[0], dict):
            return str(first[0].get("text", ""))
    if isinstance(result, dict):
        return str(result.get("text", ""))
    return ""


async def _transcribe(model: AutoModel, audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""
    result = await asyncio.to_thread(model.generate, input=audio_bytes)
    return _extract_text(result)


async def _handle_client(websocket: Any, model: AutoModel) -> None:
    audio_buffer = bytearray()
    async for message in websocket:
        if isinstance(message, bytes):
            audio_buffer.extend(message)
            continue

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logging.warning("Ignored non-JSON text frame from client.")
            continue

        if not isinstance(payload, dict):
            continue

        if payload.get("is_speaking") is False:
            try:
                text = await _transcribe(model, bytes(audio_buffer))
                reply = {"text": text, "is_final": True}
            except Exception as exc:  # pragma: no cover - runtime safety
                logging.exception("ASR inference failed")
                reply = {"text": "", "is_final": True, "error": str(exc)}

            try:
                await websocket.send(json.dumps(reply, ensure_ascii=False))
            except websockets.exceptions.ConnectionClosedOK:
                # Client may already time out and close while ASR is still running.
                break
            except websockets.exceptions.ConnectionClosedError as exc:
                logging.warning("Failed to send FunASR final result: %s", exc)
                break
            audio_buffer.clear()


async def _run_server(args: argparse.Namespace) -> None:
    logging.info("Loading ASR model from: %s", args.model)
    model = AutoModel(
        model=args.model,
        device=args.device,
        disable_update=True,
        disable_pbar=True,
    )
    logging.info("Loaded ASR model: %s", args.model)
    
    async def handler(websocket: Any) -> None:
        await _handle_client(websocket, model)

    async with websockets.serve(
        handler,
        args.host,
        args.port,
        max_size=args.max_size,
    ):
        logging.info("FunASR websocket server listening on ws://%s:%s", args.host, args.port)
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FunASR websocket server.")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("-p", "--port", type=int, default=10095)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument(
        "--model",
        type=str,
        default=_default_model(),
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=8 * 1024 * 1024,
        help="Maximum websocket frame size in bytes.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    try:
        asyncio.run(_run_server(args))
    except KeyboardInterrupt:
        logging.info("FunASR websocket server stopped.")


if __name__ == "__main__":
    main()
