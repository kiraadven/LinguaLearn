from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from huggingface_hub import snapshot_download
from modelscope import snapshot_download as ms_snapshot_download


def download_funasr(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    ms_snapshot_download(
        "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        local_dir=target_dir.as_posix(),
    )


def download_cosyvoice(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download("FunAudioLLM/CosyVoice2-0.5B", local_dir=target_dir.as_posix())


def ensure_cosyvoice_code(target_dir: Path) -> None:
    cosyvoice_pkg = target_dir / "cosyvoice" / "cli" / "cosyvoice.py"
    if cosyvoice_pkg.exists():
        return

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists() and any(target_dir.iterdir()):
        raise RuntimeError(
            f"CosyVoice code dir is not empty and doesn't look like a CosyVoice repo: {target_dir}"
        )

    if target_dir.exists():
        target_dir.rmdir()

    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/FunAudioLLM/CosyVoice.git",
            target_dir.as_posix(),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local model assets for AI Tutor V2")
    parser.add_argument("--funasr-dir", default="models/assets/funasr")
    parser.add_argument("--cosyvoice-dir", default="models/assets/CosyVoice2-0.5B")
    parser.add_argument("--cosyvoice-code-dir", default="models/CosyVoice")
    parser.add_argument("--skip-funasr", action="store_true")
    parser.add_argument("--skip-cosyvoice", action="store_true")
    parser.add_argument("--skip-cosyvoice-code", action="store_true")
    args = parser.parse_args()

    if not args.skip_funasr:
        download_funasr(Path(args.funasr_dir))

    if not args.skip_cosyvoice:
        download_cosyvoice(Path(args.cosyvoice_dir))

    if not args.skip_cosyvoice_code:
        ensure_cosyvoice_code(Path(args.cosyvoice_code_dir))


if __name__ == "__main__":
    main()
