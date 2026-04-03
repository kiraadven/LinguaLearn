#!/usr/bin/env python3
"""
wiktextract_build.py — unified wiktextract data pipeline entrypoint.

One script, three optional stages:
  1) download   Download .jsonl.gz from kaikki.org
  2) build      Build SQLite index tables (lexemes / lookup_index / translations)
  3) precompute Pre-warm card_cache from built-in wiktextract translations

Examples:
  # Only download
  python scripts/wiktextract_build.py --stages download --langs en,zh,ja,ko,de,fr,es,ru

  # Only build (default stage)
  python scripts/wiktextract_build.py --langs en,zh,ja,ko,de,fr,es,ru

  # Download + build + precompute
  python scripts/wiktextract_build.py --stages download,build,precompute --langs en,zh,ja,ko,de,fr,es,ru

  # Build from scratch (clear DB first)
  python scripts/wiktextract_build.py --stages build --reset
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.wiktextract.pipeline import build_wiktextract_index, download_wiktextract_archives
from core.wiktextract.lookup import precompute_cache
from core.wiktextract.shared import SUPPORTED_LANGS, normalize_lang_code

DEFAULT_DATA_DIR = "data/wiktextract"
DEFAULT_DB_PATH = "data/wiktextract_trans.sqlite3"
STAGE_ORDER = ("download", "build", "precompute")


def parse_langs(raw: str, arg_name: str = "--langs") -> Optional[List[str]]:
    if not raw:
        return None
    out: List[str] = []
    bad: List[str] = []
    for part in raw.split(","):
        src = part.strip()
        if not src:
            continue
        code = normalize_lang_code(src)
        if code in SUPPORTED_LANGS:
            if code not in out:
                out.append(code)
        else:
            bad.append(src)
    if bad:
        allowed = ",".join(SUPPORTED_LANGS)
        raise ValueError(f"{arg_name} contains unsupported codes: {','.join(bad)} (allowed: {allowed})")
    return out or None


def parse_stages(raw: str) -> List[str]:
    value = (raw or "build").strip().lower()
    if value in {"all", "*"}:
        return list(STAGE_ORDER)
    requested: List[str] = []
    bad: List[str] = []
    for item in value.split(","):
        stage = item.strip().lower()
        if not stage:
            continue
        if stage in STAGE_ORDER:
            if stage not in requested:
                requested.append(stage)
        else:
            bad.append(stage)
    if bad:
        raise ValueError(f"--stages contains unsupported stage(s): {','.join(bad)}")
    if not requested:
        return ["build"]
    # Execute in fixed lifecycle order even if user input is shuffled.
    return [s for s in STAGE_ORDER if s in requested]


def pick_stages(args: argparse.Namespace) -> List[str]:
    # Backward compatibility with old flags:
    #   --download --no-build --precompute
    use_legacy = bool(args.download or args.no_build or args.precompute)
    if use_legacy:
        picked: List[str] = []
        if args.download:
            picked.append("download")
        if not args.no_build:
            picked.append("build")
        if args.precompute:
            picked.append("precompute")
        if not picked:
            raise ValueError("No stages selected (legacy flags resulted in empty stage set).")
        return [s for s in STAGE_ORDER if s in picked]
    return parse_stages(args.stages)


def langs_label(langs: Optional[Iterable[str]]) -> str:
    if not langs:
        return "all"
    return ",".join(langs)


def run_download(args: argparse.Namespace, langs: Optional[List[str]], show_progress: bool) -> None:
    print(f"\n[download] data_dir={args.data_dir}  langs={langs_label(langs)}")
    t0 = time.time()
    files = download_wiktextract_archives(
        data_dir=args.data_dir,
        langs=langs,
        overwrite=bool(args.overwrite_download),
        show_progress=show_progress,
    )
    print(f"[download] done: {len(files)} file(s) in {time.time() - t0:.1f}s")


def run_build(args: argparse.Namespace, langs: Optional[List[str]], show_progress: bool) -> None:
    print(f"\n[build] db={args.db}  reset={args.reset}  langs={langs_label(langs)}")
    t0 = time.time()
    stats = build_wiktextract_index(
        data_dir=args.data_dir,
        db_path=args.db,
        langs=langs,
        reset=bool(args.reset),
        show_progress=show_progress,
    )
    print(
        f"[build] done in {time.time() - t0:.1f}s — "
        f"files={stats.files}  parsed={stats.parsed}  kept={stats.kept}  "
        f"lexemes={stats.inserted_lexemes}  "
        f"index_rows={stats.inserted_index_rows}  "
        f"translations={stats.inserted_translations}"
    )


def run_precompute(args: argparse.Namespace, langs: Optional[List[str]], show_progress: bool) -> None:
    scripts = ["hans", "hant"] if args.zh_script == "both" else [args.zh_script]
    grand_total = 0
    print(
        f"\n[precompute] langs={langs_label(langs)}  "
        f"limit_per_src={args.precompute_limit}  zh_script={args.zh_script}"
    )
    for script in scripts:
        t0 = time.time()
        total = precompute_cache(
            db_path=args.db,
            src_langs=langs,
            tgt_langs=langs,
            limit_per_src=args.precompute_limit,
            zh_script=script,
            show_progress=show_progress,
        )
        grand_total += total
        print(f"[precompute] zh_script={script}: {total} cards in {time.time() - t0:.1f}s")
    print(f"[precompute] total_created={grand_total}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--stages",
        default="build",
        help="Comma-separated stages: download,build,precompute (default: build; use 'all' for full pipeline)",
    )
    p.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help=f"Directory for raw .jsonl.gz files (default: {DEFAULT_DATA_DIR})",
    )
    p.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"SQLite output path (default: {DEFAULT_DB_PATH})",
    )
    p.add_argument(
        "--langs",
        default="",
        help="Comma-separated language codes: en,zh,ja,ko,de,fr,es,ru (default: all)",
    )
    p.add_argument(
        "--overwrite-download",
        action="store_true",
        help="Re-download even if files already exist",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing DB data before build stage",
    )
    p.add_argument(
        "--precompute-limit",
        type=int,
        default=50000,
        help="Max words per src_lang to precompute (default: 50000)",
    )
    p.add_argument(
        "--zh-script",
        choices=("hans", "hant", "both"),
        default="both",
        help="Chinese script variant for precompute cache key (default: both)",
    )
    p.add_argument("--no-progress", action="store_true", help="Suppress progress bars")

    # Backward-compat flags (deprecated but kept for existing commands).
    p.add_argument("--download", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-build", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--precompute", action="store_true", help=argparse.SUPPRESS)

    args = p.parse_args()

    try:
        stages = pick_stages(args)
        langs = parse_langs(args.langs, "--langs")
    except ValueError as e:
        p.error(str(e))
        return 2

    if args.precompute_limit < 1:
        p.error("--precompute-limit must be >= 1")
        return 2

    show_progress = not args.no_progress
    Path(args.data_dir).mkdir(parents=True, exist_ok=True)
    Path(args.db).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[config] stages={','.join(stages)}  data_dir={args.data_dir}  "
        f"db={args.db}  langs={langs_label(langs)}"
    )

    for stage in stages:
        if stage == "download":
            run_download(args, langs, show_progress)
        elif stage == "build":
            run_build(args, langs, show_progress)
        elif stage == "precompute":
            run_precompute(args, langs, show_progress)

    print(f"\n[done] db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
