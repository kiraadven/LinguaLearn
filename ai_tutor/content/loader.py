"""
Parse LinguaLearn job output into structured content for the AI tutor.

Job directory layout:
  {job_id}/
    {job_id}_demo.md               - Main markdown with sentences, vocab, expressions
    {job_id}_demo_segments.json    - [{start, end, text}, ...]
    sentence_quiz.json             - {sentences: [{sentence_index, text, start, end, audio_file}]}
    sq_0001.mp3 ...                - Per-sentence audio
    学习版.mp4                      - Full video
    _stream_variants/              - 720p/360p variants
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ai_tutor.content.language_profiles import detect_content_type


@dataclass
class VocabItem:
    word: str
    phonetic: str
    translation: str
    difficulty: int  # 1-5 (count of filled ★)


@dataclass
class SentenceData:
    index: int                          # 0-based
    text: str                           # English original
    translation: str                    # Chinese translation
    start: float                        # video start time (seconds)
    end: float                          # video end time (seconds)
    audio_file: str                     # e.g. "sq_0001.mp3"
    vocab: list[VocabItem] = field(default_factory=list)
    expressions: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_prompt_block(self) -> str:
        vocab_lines = "\n".join(
            f"  - {v.word} {v.phonetic}：{v.translation}（难度{v.difficulty}/5）"
            for v in self.vocab
        )
        expr_lines = "\n".join(f"  - {e}" for e in self.expressions)
        return (
            f"句子 {self.index + 1}（{self.start:.1f}s–{self.end:.1f}s）\n"
            f"  原文：{self.text}\n"
            f"  译文：{self.translation}\n"
            f"  重点词汇：\n{vocab_lines or '  （无）'}\n"
            f"  有用表达：\n{expr_lines or '  （无）'}"
        )


@dataclass
class LinguaLearnContent:
    job_id: str
    job_dir: Path
    source_lang: str
    target_lang: str
    sentences: list[SentenceData]
    title: str = ""
    brief: str = ""
    content_type: str = "unknown"   # news / movie / tv_show / interview / documentary / …

    @property
    def video_path(self) -> Path | None:
        for candidate in self.job_dir.iterdir():
            if candidate.suffix == ".mp4" and "_副本" not in candidate.name:
                return candidate
        return None

    @property
    def sentence_count(self) -> int:
        return len(self.sentences)

    def get_sentence(self, index: int) -> SentenceData | None:
        if 0 <= index < len(self.sentences):
            return self.sentences[index]
        return None


# ── Regex helpers ─────────────────────────────────────────────────────────────

_SENTENCE_BLOCK = re.compile(
    r"## 🔹 句子 (\d+)\s*\n+"
    r"> \*\*(.+?)\*\*\s*\n"   # English text line
    r"(?:>\s*\n)*"            # optional blank blockquote lines (>)
    r"> \*(.+?)\*",           # Chinese translation
    re.DOTALL,
)

_VOCAB_ROW = re.compile(
    r"\|\s*\*\*(.+?)\*\*\s*\|\s*`(.+?)`\s*\|\s*(.+?)\s*\|\s*(★+[☆]*)\s*\|"
)

_EXPR_LINE = re.compile(r"^-\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+)$", re.MULTILINE)

_VOCAB_SECTION = re.compile(
    r"### 📚 重难点词汇\s*\n([\s\S]+?)(?=###|\n## |\Z)"
)
_EXPR_SECTION = re.compile(
    r"### 💬 有用表达\s*\n([\s\S]+?)(?=## |\Z)"
)

_BRIEF_SECTION = re.compile(
    r"## 📚 内容简介\s*\n+> (.+?)(?=\n---|\Z)", re.DOTALL
)


def _count_stars(star_str: str) -> int:
    return star_str.count("★")


def _parse_md(md_text: str) -> tuple[str, list[dict]]:
    """Return (brief, [{index, text, translation, vocab, expressions}])."""
    brief = ""
    brief_match = _BRIEF_SECTION.search(md_text)
    if brief_match:
        brief = brief_match.group(1).strip()

    # Split on sentence headers
    sentence_blocks = re.split(r"(?=## 🔹 句子 \d+)", md_text)

    sentences: list[dict] = []
    for block in sentence_blocks:
        header_match = _SENTENCE_BLOCK.search(block)
        if not header_match:
            continue

        idx = int(header_match.group(1)) - 1  # convert to 0-based
        text = header_match.group(2).strip()
        translation = header_match.group(3).strip()

        # Vocab
        vocab: list[VocabItem] = []
        vocab_section = _VOCAB_SECTION.search(block)
        if vocab_section:
            for row in _VOCAB_ROW.finditer(vocab_section.group(1)):
                word = row.group(1).strip()
                phonetic = row.group(2).strip()
                cn = row.group(3).strip()
                difficulty = _count_stars(row.group(4))
                vocab.append(VocabItem(word=word, phonetic=phonetic, translation=cn, difficulty=difficulty))

        # Expressions
        expressions: list[str] = []
        expr_section = _EXPR_SECTION.search(block)
        if expr_section:
            for m in _EXPR_LINE.finditer(expr_section.group(1)):
                expressions.append(f"{m.group(1)} — {m.group(2).strip()}")

        sentences.append({
            "index": idx,
            "text": text,
            "translation": translation,
            "vocab": vocab,
            "expressions": expressions,
        })

    sentences.sort(key=lambda s: s["index"])
    return brief, sentences


def load_job(job_id: str, data_dir: str | Path) -> LinguaLearnContent:
    """
    Load a LinguaLearn job from disk.

    Args:
        job_id: UUID-style job identifier
        data_dir: Path to the LinguaLearn output root (contains {job_id}/ subdirs)

    Returns:
        LinguaLearnContent with all sentences, vocab, expressions, and timing data.
    """
    data_dir = Path(data_dir)
    job_dir = data_dir / job_id
    if not job_dir.exists():
        raise FileNotFoundError(f"Job directory not found: {job_dir}")

    # ── sentence_quiz.json ────────────────────────────────────────────────────
    quiz_path = job_dir / "sentence_quiz.json"
    if not quiz_path.exists():
        raise FileNotFoundError(f"sentence_quiz.json not found in {job_dir}")

    with quiz_path.open(encoding="utf-8") as f:
        quiz_data = json.load(f)

    source_lang = quiz_data.get("source_lang", "en")
    target_lang = quiz_data.get("target_lang", "zh-Hans")

    # Build timing + audio lookup by sentence_index
    timing: dict[int, dict] = {}
    for s in quiz_data.get("sentences", []):
        idx = s["sentence_index"]
        timing[idx] = {
            "start": s["start"],
            "end": s["end"],
            "audio_file": s.get("audio_file", f"sq_{idx + 1:04d}.mp3"),
        }

    # ── *_demo.md ────────────────────────────────────────────────────────────
    md_candidates = list(job_dir.glob("*_demo.md"))
    if not md_candidates:
        raise FileNotFoundError(f"No *_demo.md found in {job_dir}")

    md_text = md_candidates[0].read_text(encoding="utf-8")
    brief, parsed_sentences = _parse_md(md_text)

    # ── Merge ─────────────────────────────────────────────────────────────────
    sentences: list[SentenceData] = []
    for ps in parsed_sentences:
        idx = ps["index"]
        t = timing.get(idx, {"start": 0.0, "end": 0.0, "audio_file": f"sq_{idx + 1:04d}.mp3"})
        sentences.append(
            SentenceData(
                index=idx,
                text=ps["text"],
                translation=ps["translation"],
                start=t["start"],
                end=t["end"],
                audio_file=t["audio_file"],
                vocab=ps["vocab"],
                expressions=ps["expressions"],
            )
        )

    # ── Title ─────────────────────────────────────────────────────────────────
    # Try to extract title from the first H1 in the markdown
    title = ""
    title_match = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    # ── Content type ──────────────────────────────────────────────────────────
    # First check sentence_quiz.json for an explicit field, then auto-detect
    content_type: str = quiz_data.get("content_type", "")
    if not content_type:
        content_type = detect_content_type(title, brief)

    return LinguaLearnContent(
        job_id=job_id,
        job_dir=job_dir,
        source_lang=source_lang,
        target_lang=target_lang,
        sentences=sentences,
        title=title,
        brief=brief,
        content_type=content_type,
    )
