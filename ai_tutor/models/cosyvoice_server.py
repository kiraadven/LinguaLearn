"""CosyVoice 2 streaming HTTP server."""
from __future__ import annotations

import argparse
import io
import importlib.util
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = ROOT_DIR / "models" / "assets" / "CosyVoice2-0.5B"
DEFAULT_VOICE_DIR = ROOT_DIR.parent / "data" / "voices"
DEFAULT_CODE_DIR = ROOT_DIR / "models" / "CosyVoice"
COSYVOICE_REPO_URL = "https://github.com/FunAudioLLM/CosyVoice.git"
MODEL_DIR = Path(os.getenv("COSYVOICE_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
VOICE_DIR = Path(os.getenv("COSYVOICE_VOICE_DIR", str(DEFAULT_VOICE_DIR)))
CODE_DIR = Path(os.getenv("COSYVOICE_CODE_DIR", str(DEFAULT_CODE_DIR)))
MASKED_OPTIONAL_DEPS = ("sklearn", "scipy", "torchvision")


# Language tags for inference_cross_lingual mode
_LANG_TAG: dict[str, str] = {
    "en": "<|en|>",
    "zh": "<|zh|>",
    "ja": "<|ja|>",
    "ko": "<|ko|>",
    "de": "<|de|>",
    "fr": "<|fr|>",
    "es": "<|es|>",
}


class TTSRequest(BaseModel):
    text: str
    voice_id: str = "default"
    speed: float = 1.0
    format: str = "pcm"
    sample_rate: int = 24000
    # Optional: transcript of the reference audio (for zero-shot mode).
    # If empty the server falls back to cross-lingual inference which needs
    # no transcript — only a language hint.
    prompt_text: str = ""
    language: str = "en"  # en | zh | ja | ko | …


def _cosyvoice_pkg_path(code_dir: Path) -> Path:
    return code_dir / "cosyvoice" / "cli" / "cosyvoice.py"


def _ensure_cosyvoice_code(code_dir: Path) -> None:
    if _cosyvoice_pkg_path(code_dir).exists():
        return

    code_dir = code_dir.resolve()
    code_dir.parent.mkdir(parents=True, exist_ok=True)
    if code_dir.exists() and any(code_dir.iterdir()):
        raise RuntimeError(
            f"CosyVoice code dir exists but doesn't look like a CosyVoice repo: {code_dir}"
        )

    if code_dir.exists():
        code_dir.rmdir()

    logging.info("CosyVoice code not found, cloning to: %s", code_dir)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            COSYVOICE_REPO_URL,
            code_dir.as_posix(),
        ],
        check=True,
    )


@contextmanager
def _mask_optional_transformers_deps():
    """Mask optional deps that are not required for CosyVoice TTS path.

    Some mixed Python environments have broken scipy/sklearn/torchvision installs,
    which can crash `transformers` import even though CosyVoice does not need them.
    """
    original_find_spec = importlib.util.find_spec

    def patched_find_spec(name: str, package: str | None = None):
        for dep in MASKED_OPTIONAL_DEPS:
            if name == dep or name.startswith(f"{dep}."):
                return None
        return original_find_spec(name, package)

    importlib.util.find_spec = patched_find_spec
    try:
        yield
    finally:
        importlib.util.find_spec = original_find_spec


def _import_cosyvoice2():
    try:
        with _mask_optional_transformers_deps():
            from cosyvoice.cli.cosyvoice import CosyVoice2

        return CosyVoice2
    except ModuleNotFoundError as exc:
        # If cosyvoice package is present but one of its dependencies is missing,
        # propagate directly instead of masking the true dependency error.
        if exc.name and exc.name != "cosyvoice":
            raise

    candidate_dirs = []
    for candidate in [CODE_DIR, ROOT_DIR / "models" / "CosyVoice", ROOT_DIR / "CosyVoice"]:
        if candidate not in candidate_dirs:
            candidate_dirs.append(candidate)

    for candidate in candidate_dirs:
        try:
            _ensure_cosyvoice_code(candidate)
        except Exception:
            continue

        if _cosyvoice_pkg_path(candidate).exists():
            sys.path.insert(0, str(candidate))
            # CosyVoice uses in-repo third_party/Matcha-TTS for `matcha` imports.
            matcha_dir = candidate / "third_party" / "Matcha-TTS"
            if matcha_dir.exists():
                sys.path.insert(0, str(matcha_dir))
            with _mask_optional_transformers_deps():
                from cosyvoice.cli.cosyvoice import CosyVoice2

            return CosyVoice2

    raise ModuleNotFoundError("No module named 'cosyvoice'")


def _resolve_model_dir() -> str:
    return str(MODEL_DIR)


_SUPPORTED_AUDIO_EXTENSIONS = [".wav", ".m4a", ".mp3", ".flac", ".ogg", ".aac"]


def _resolve_voice_file(voice_id: str) -> Path:
    """Locate the voice reference file for *voice_id*.

    Tries ``.wav`` first.  If a file with any other supported extension is found
    it is automatically resampled to 16 kHz mono WAV and cached next to the
    original — subsequent calls then use the cached WAV directly.
    """
    wav_path = VOICE_DIR / f"{voice_id}.wav"
    if wav_path.exists():
        return wav_path

    for ext in _SUPPORTED_AUDIO_EXTENSIONS[1:]:
        src = VOICE_DIR / f"{voice_id}{ext}"
        if not src.exists():
            continue
        logging.info("Converting %s → %s for voice cloning (16 kHz mono WAV)…", src.name, wav_path.name)
        try:
            waveform, sr = torchaudio.load(str(src))
        except Exception as exc:
            logging.warning("Could not load %s: %s", src, exc)
            continue
        # Downmix to mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(0, keepdim=True)
        # Resample to 16 kHz (required by CosyVoice zero-shot)
        if sr != 16000:
            waveform = torchaudio.functional.resample(waveform, sr, 16000)
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(wav_path), waveform, 16000)
        logging.info("Saved converted WAV → %s", wav_path)
        return wav_path

    # Fall through so the caller can raise a meaningful 400 with the expected path
    return wav_path


def _to_pcm_bytes(audio_tensor: torch.Tensor) -> bytes:
    if audio_tensor.dim() > 1:
        audio_tensor = audio_tensor.squeeze(0)
    audio_tensor = audio_tensor.detach().cpu().clamp(-1.0, 1.0)
    return (audio_tensor * 32767.0).to(torch.int16).numpy().tobytes()


def _assert_model_ready(app: FastAPI) -> Any:
    model = getattr(app.state, "cosyvoice_model", None)
    load_error = getattr(app.state, "load_error", None)
    if model is None:
        detail = (
            "CosyVoice model is not ready. "
            f"{load_error or 'Unknown error.'} "
            "If cosyvoice package is missing, clone CosyVoice code to "
            "`ai_tutor/models/CosyVoice` or set `COSYVOICE_CODE_DIR`."
        )
        raise HTTPException(status_code=503, detail=detail)
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cosyvoice_model = None
    app.state.load_error = None
    model_dir = _resolve_model_dir()
    try:
        logging.info("Loading CosyVoice model from: %s", model_dir)
        logging.info("Using voice reference directory: %s", VOICE_DIR)
        logging.info("Using CosyVoice code directory: %s", CODE_DIR)
        CosyVoice2 = _import_cosyvoice2()
        app.state.cosyvoice_model = CosyVoice2(
            model_dir,
            load_jit=True,
            load_trt=False,
        )
        logging.info("CosyVoice model loaded.")
    except Exception as exc:
        app.state.load_error = f"{type(exc).__name__}: {exc}"
        logging.exception("CosyVoice model initialization failed")
    yield


app = FastAPI(title="CosyVoice Server", lifespan=lifespan)


@app.get("/health")
async def health():
    if getattr(app.state, "cosyvoice_model", None) is not None:
        return {"status": "ok"}
    return {"status": "degraded", "error": app.state.load_error}


def _build_inference_generator(cosyvoice_model, req: TTSRequest, prompt_speech: Path):
    """Return the right CosyVoice generator based on whether prompt_text is supplied.

    - With prompt_text  → inference_zero_shot  (best quality, needs transcript)
    - Without prompt_text → inference_cross_lingual (no transcript needed,
      adds language tag so the model knows the target language)
    """
    if req.prompt_text:
        return cosyvoice_model.inference_zero_shot(
            tts_text=req.text,
            prompt_text=req.prompt_text,
            prompt_wav=str(prompt_speech),
            stream=True,
            speed=req.speed,
        )

    lang_tag = _LANG_TAG.get(req.language, "<|en|>")
    tagged_text = f"{lang_tag}{req.text}"
    return cosyvoice_model.inference_cross_lingual(
        tts_text=tagged_text,
        prompt_wav=str(prompt_speech),
        stream=True,
        speed=req.speed,
    )


@app.post("/api/tts/stream")
async def stream_tts(req: TTSRequest):
    cosyvoice_model = _assert_model_ready(app)
    prompt_speech = _resolve_voice_file(req.voice_id)
    if not prompt_speech.exists():
        raise HTTPException(status_code=400, detail=f"Voice file not found: {prompt_speech}")

    async def generate():
        for chunk in _build_inference_generator(cosyvoice_model, req, prompt_speech):
            audio = chunk["tts_speech"]
            pcm = _to_pcm_bytes(audio)
            if pcm:
                yield pcm

    return StreamingResponse(generate(), media_type="application/octet-stream")


@app.post("/api/tts")
async def full_tts(req: TTSRequest):
    """Non-streaming endpoint — collects all chunks from the generator."""
    cosyvoice_model = _assert_model_ready(app)
    prompt_speech = _resolve_voice_file(req.voice_id)
    if not prompt_speech.exists():
        raise HTTPException(status_code=400, detail=f"Voice file not found: {prompt_speech}")

    # Reuse the same generator, collect everything into a buffer
    pcm_chunks: list[bytes] = []
    for chunk in _build_inference_generator(cosyvoice_model, req, prompt_speech):
        pcm = _to_pcm_bytes(chunk["tts_speech"])
        if pcm:
            pcm_chunks.append(pcm)

    if not pcm_chunks:
        raise HTTPException(status_code=500, detail="TTS inference produced no audio.")

    raw_pcm = b"".join(pcm_chunks)

    if req.format == "wav":
        import numpy as np
        arr = np.frombuffer(raw_pcm, dtype=np.int16)
        import torch as _torch
        audio_tensor = _torch.from_numpy(arr).float().unsqueeze(0) / 32767.0
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio_tensor, req.sample_rate, format="wav")
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="audio/wav")

    return StreamingResponse(io.BytesIO(raw_pcm), media_type="application/octet-stream")


def main() -> None:
    import uvicorn

    global MODEL_DIR, VOICE_DIR, CODE_DIR

    parser = argparse.ArgumentParser(description="Run CosyVoice HTTP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("-p", "--port", type=int, default=9880)
    parser.add_argument("--model-dir", type=str, default=str(MODEL_DIR))
    parser.add_argument("--voice-dir", type=str, default=str(VOICE_DIR))
    parser.add_argument(
        "--cosyvoice-code-dir",
        type=str,
        default=str(CODE_DIR),
        help="Path to CosyVoice source repository (contains `cosyvoice/`).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "--uvicorn-log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
    )
    args = parser.parse_args()

    MODEL_DIR = Path(args.model_dir).expanduser().resolve()
    VOICE_DIR = Path(args.voice_dir).expanduser().resolve()
    CODE_DIR = Path(args.cosyvoice_code_dir).expanduser().resolve()

    os.environ["COSYVOICE_MODEL_DIR"] = str(MODEL_DIR)
    os.environ["COSYVOICE_VOICE_DIR"] = str(VOICE_DIR)
    os.environ["COSYVOICE_CODE_DIR"] = str(CODE_DIR)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.uvicorn_log_level)


if __name__ == "__main__":
    main()
