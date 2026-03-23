# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LinguaLearn is a multilingual language learning video generation platform. It processes foreign language videos into structured learning materials with sentence-by-sentence breakdowns, phonetic annotations, visual overlays, and study notes.

Supported languages: English, Chinese, Japanese, Korean, German, French, Spanish.

## Commands

### Backend

```bash
# Install dependencies (requires conda)
conda activate automation
pip install -r requirements.txt

# Run web server
python api.py
# or
bash start_web.sh

# CLI batch processing
python main.py /path/to/video.mp4 [output_name]
```

### Frontend

```bash
cd frontend
npm install
npm run build   # Build to static/ (served by FastAPI)
npm run dev     # Dev server with hot reload
```

## Architecture

### Processing Pipeline

Videos go through a 5-step pipeline:

1. **Audio Transcription** (`core/audio_transcriber.py`) — Extract audio, transcribe with OpenAI Whisper (word-level timestamps)
2. **Sentence Splitting** (`core/sentence_splitter.py`) — LLM-assisted segmentation (5–30 word constraint)
3. **Word Analysis** (`core/word_analyzer.py`) — DeepSeek API extracts keywords + expressions (multi-threaded)
4. **Markdown Export** (`core/markdown_exporter.py`) — Study notes with IPA/Pinyin/phonetic markup
5. **Video Rendering** (`core/video_processor.py`) — FFmpeg-only pipeline:
   - Generate ASS subtitles (`core/ass_generator.py` + `core/ass_styles.py`)
   - Render overlay PNGs via Chrome Headless (`core/html_renderer.py`)
   - Compose 3-part video structure (see below)

### Output Video Structure

Each processed video has three parts per sentence:
- **Part 1:** 1x speed, no overlays (blind listening)
- **Part 2:** 2x repeat, 0.75x slow speed, all overlays (subtitle, wordbox, expressionbox)
- **Part 3:** 1x speed, overlays (consolidation)

### Key Components

| File | Role |
|------|------|
| `api.py` | FastAPI backend — auth, job management, WebSocket progress, config presets |
| `config.py` | All global settings — API keys, language mappings, video params, repeat counts |
| `database.py` | SQLite layer — users, tokens, jobs, config presets (via SQLAlchemy) |
| `core/video_processor.py` | FFmpeg subprocess orchestration |
| `core/html_renderer.py` | Chrome Headless rendering for overlay PNGs |
| `core/templates/` | Jinja2 HTML templates for subtitle/wordbox/expressionbox overlays |
| `frontend/` | Vue 3 + Vite SPA with layout editor and real-time progress |
| `static/` | Compiled frontend (served by FastAPI as static files) |

### API & Auth

- FastAPI on port 8000; frontend served from `static/`
- Auth supports: email+password, phone+password, phone+verification code (auto-register)
- Bearer token auth (30-day expiry); 10-minute verification code expiry
- WebSocket at `/ws/{job_id}` for real-time processing progress

### Configuration

All runtime configuration lives in `.env`:
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` — primary LLM (DeepSeek)
- `SPLITTER_API_KEY` / `SPLITTER_BASE_URL` / `SPLITTER_MODEL` — sentence splitting LLM
- `WHISPER_MODEL_SIZE` — Whisper model variant
- SMTP and Aliyun SMS settings (optional, for verification codes)

`config.py` contains all non-secret defaults: language mappings, video FPS (30), audio FPS (44100), slow speed (0.75x), sentence word limits (5–30), part repeat counts, output/temp/upload directories, and resolution settings.

### Database

SQLite at `data/lingualearn.db` with tables: `users`, `verification_codes`, `tokens`, `user_configs`, `user_config_presets`, `jobs`.

## System Dependencies

- **FFmpeg** — video processing (must be in PATH)
- **Chrome/Chromium** — headless rendering for overlay images
- **conda** — Python environment management (Python 3.10)
