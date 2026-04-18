"""
AI Tutor V2 Server

Endpoints:
  Legacy (voice-only):
    GET  /health
    WS   /ws/tutor

  Interactive Teaching (new):
    WS   /ai-tutor/ws/{learner_id}       - Main real-time teaching session
    GET  /ai-tutor/jobs                  - List available LinguaLearn jobs
    GET  /ai-tutor/jobs/{job_id}/content - Parsed lesson content
    GET  /ai-tutor/learner/{learner_id}/memory - Learner memory summary
    POST /ai-tutor/learner               - Create / update learner profile
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.websockets import WebSocketDisconnect

from ai_tutor.config import get_settings
from ai_tutor.content.loader import load_job, LinguaLearnContent
from ai_tutor.content.curriculum import CurriculumBuilder
from ai_tutor.memory.manager import MemoryManager
from ai_tutor.session.learner_profile import LearnerProfile, LearnerProfileStore
from ai_tutor.session.manager import SessionManager
from ai_tutor.session.teaching_engine import TeachingEngine
from ai_tutor.model_services import ModelServiceManager
from ai_tutor.voice.audio_router import AudioRouter

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Tutor V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_profile_store = LearnerProfileStore()
_model_services = ModelServiceManager(get_settings(), Path(__file__).resolve().parent)

# ── Utility ────────────────────────────────────────────────────────────────────

def _settings():
    return get_settings()


@app.on_event("startup")
async def startup_event() -> None:
    await _model_services.ensure_started()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await _model_services.stop_managed()


def _ai_tutor_db() -> str:
    s = _settings()
    s.ai_tutor_db_path.parent.mkdir(parents=True, exist_ok=True)
    return s.ai_tutor_db_path.as_posix()


def _lingualearn_data_dir() -> str:
    return _settings().lingualearn_data_dir.as_posix()


def _lingualearn_db() -> str | None:
    p = _settings().lingualearn_db_path
    return p.as_posix() if p.exists() else None


# ── Legacy endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse({
        "service": "AI Tutor V2",
        "status": "ok",
        "websocket_legacy": "/ws/tutor",
        "websocket_interactive": "/ai-tutor/ws/{learner_id}",
        "jobs": "/ai-tutor/jobs",
    })


@app.get("/favicon.ico")
@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
async def empty_icon() -> Response:
    return Response(status_code=204)


@app.websocket("/ws/tutor")
async def tutor_session_legacy(ws: WebSocket) -> None:
    """Legacy voice-only session (existing functionality, untouched)."""
    await ws.accept()
    try:
        init_payload = json.loads(await ws.receive_text())
    except Exception:
        await ws.close(code=1003)
        return

    if init_payload.get("type") != "session_start":
        await ws.close(code=1008)
        return

    session = SessionManager(init_payload)
    await session.initialize()
    audio_router = AudioRouter(ws, session)

    tasks = [
        asyncio.create_task(audio_router.receive_loop(), name="receive_loop"),
        asyncio.create_task(audio_router.process_loop(), name="process_loop"),
        asyncio.create_task(audio_router.send_loop(), name="send_loop"),
        asyncio.create_task(session.auto_advance_loop(), name="auto_advance_loop"),
    ]

    try:
        await asyncio.gather(*tasks)
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await audio_router.close()
        await session.end()


# ── Interactive AI Tutor WebSocket ─────────────────────────────────────────────

@app.websocket("/ai-tutor/ws/{learner_id}")
async def interactive_tutor_session(ws: WebSocket, learner_id: str) -> None:
    """
    Main interactive teaching WebSocket.

    Client must send start message first:
      {"type": "start_course", "job_id": "...", "mode": "course|global"}
    or:
      {"type": "start_global"}
    """
    await ws.accept()

    async def send(data: str) -> None:
        try:
            await ws.send_text(data)
        except Exception:
            pass

    # Wait for start message
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
        start_msg = json.loads(raw)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
        await ws.close(code=1003)
        return

    mode = start_msg.get("mode", "course")
    job_id = start_msg.get("job_id", "")

    # Load learner profile
    profile = await _profile_store.load(learner_id)

    # Load content (for course mode)
    content: LinguaLearnContent | None = None
    if mode == "course" and job_id:
        try:
            content = load_job(job_id, _lingualearn_data_dir())
        except FileNotFoundError as e:
            await send(json.dumps({"type": "error", "message": str(e)}))
            await ws.close(code=1008)
            return

    # Initialize memory manager
    total_sentences = content.sentence_count if content else 0
    mem_manager = MemoryManager(
        ai_tutor_db_path=_ai_tutor_db(),
        lingualearn_db_path=_lingualearn_db(),
    )
    await mem_manager.initialize(
        learner_id=learner_id,
        job_id=job_id or "__global__",
        total_sentences=total_sentences,
    )

    # Build curriculum
    curriculum = None
    if content:
        curriculum = CurriculumBuilder.build(content, profile)

    # Create teaching engine
    engine = TeachingEngine(
        content=content or _empty_content(job_id),
        curriculum=curriculum or _empty_curriculum(job_id, learner_id),
        profile=profile,
        memory_manager=mem_manager,
        send_fn=send,
        mode=mode,
    )

    # Send ready signal
    await send(json.dumps({"type": "ready", "learner_id": learner_id, "mode": mode}))

    # Start session
    if mode == "course" and content:
        await engine.start_course()
    else:
        await engine.start_global_mode()

    # Main message loop
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive(), timeout=300.0)
            except asyncio.TimeoutError:
                # Session idle timeout
                break

            if "bytes" in raw:
                # Binary PCM audio — future: pipe to ASR
                continue

            text_data = raw.get("text", "")
            if not text_data:
                continue

            try:
                msg = json.loads(text_data)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "session_end":
                await engine.handle_message({"type": "session_end"})
                break

            await engine.handle_message(msg)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Interactive session error: %s", e)
        try:
            await send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        # Save session data on disconnect
        try:
            await mem_manager.save_session(
                learner_id=learner_id,
                job_id=job_id or "__global__",
                mode=mode,
                content=content,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.warning("Failed to save session: %s", e)


# ── REST endpoints ─────────────────────────────────────────────────────────────

@app.get("/ai-tutor/jobs")
async def list_jobs() -> JSONResponse:
    """List all available LinguaLearn job directories."""
    from pathlib import Path
    data_dir = Path(_lingualearn_data_dir())
    if not data_dir.exists():
        return JSONResponse([])

    jobs = []
    for job_dir in sorted(data_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        quiz_path = job_dir / "sentence_quiz.json"
        if not quiz_path.exists():
            continue
        try:
            quiz_data = json.loads(quiz_path.read_text(encoding="utf-8"))
            sentence_count = len(quiz_data.get("sentences", []))
            jobs.append({
                "job_id": job_dir.name,
                "sentence_count": sentence_count,
                "source_lang": quiz_data.get("source_lang", "en"),
                "target_lang": quiz_data.get("target_lang", "zh-Hans"),
                "generated_at": quiz_data.get("generated_at", ""),
            })
        except Exception:
            continue

    return JSONResponse(jobs)


@app.get("/ai-tutor/jobs/{job_id}/content")
async def get_job_content(job_id: str) -> JSONResponse:
    """Return parsed lesson content for a job (no video, no audio blobs)."""
    try:
        content = load_job(job_id, _lingualearn_data_dir())
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return JSONResponse({
        "job_id": content.job_id,
        "source_lang": content.source_lang,
        "target_lang": content.target_lang,
        "brief": content.brief,
        "sentence_count": content.sentence_count,
        "sentences": [
            {
                "index": s.index,
                "text": s.text,
                "translation": s.translation,
                "start": s.start,
                "end": s.end,
                "audio_file": s.audio_file,
                "vocab": [
                    {
                        "word": v.word,
                        "phonetic": v.phonetic,
                        "translation": v.translation,
                        "difficulty": v.difficulty,
                    }
                    for v in s.vocab
                ],
                "expressions": s.expressions,
            }
            for s in content.sentences
        ],
    })


@app.get("/ai-tutor/learner/{learner_id}/memory")
async def get_learner_memory(learner_id: str, job_id: str = "") -> JSONResponse:
    """Return the learner's memory summary for the frontend panel."""
    profile = await _profile_store.load(learner_id)
    mem = MemoryManager(
        ai_tutor_db_path=_ai_tutor_db(),
        lingualearn_db_path=_lingualearn_db(),
    )

    total = 0
    content = None
    if job_id:
        try:
            content = load_job(job_id, _lingualearn_data_dir())
            total = content.sentence_count
        except Exception:
            pass

    await mem.initialize(learner_id, job_id or "__global__", total)

    ctx = mem.get_context(mode="course" if job_id else "global")

    return JSONResponse({
        "learner_id": learner_id,
        "name": profile.name,
        "level": profile.level,
        "total_sessions": profile.total_sessions,
        "course_progress": ctx.course_progress if job_id else {},
        "quiz_summary": {
            "completion_rate": ctx.quiz_record.completion_rate,
            "error_sentences": ctx.quiz_record.error_sentences,
            "error_words": ctx.quiz_record.error_words,
            "last_quiz_date": ctx.quiz_record.last_quiz_date,
        },
        "learner_graph": {
            "interests": ctx.learner_graph.interests,
            "weak_areas": ctx.learner_graph.weak_areas,
            "strong_areas": ctx.learner_graph.strong_areas,
            "chat_insights": ctx.learner_graph.chat_insights,
        },
    })


@app.post("/ai-tutor/learner")
async def create_or_update_learner(body: dict) -> JSONResponse:
    """Create or update a learner profile."""
    learner_id = body.get("learner_id", "")
    if not learner_id:
        raise HTTPException(status_code=400, detail="learner_id required")

    profile = await _profile_store.load(learner_id)
    if body.get("name"):
        profile.name = body["name"]
    if body.get("level"):
        profile.level = body["level"]
    if body.get("l1"):
        profile.l1 = body["l1"]
    if body.get("target_language"):
        profile.target_language = body["target_language"]

    await _profile_store.save(profile)
    return JSONResponse({"ok": True, "learner_id": learner_id})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _empty_content(job_id: str) -> LinguaLearnContent:
    """Placeholder content for global mode (no specific job)."""
    from pathlib import Path
    from ai_tutor.content.loader import LinguaLearnContent
    return LinguaLearnContent(
        job_id=job_id or "__global__",
        job_dir=Path("."),
        source_lang="en",
        target_lang="zh-Hans",
        sentences=[],
    )


def _empty_curriculum(job_id: str, learner_id: str):
    from ai_tutor.content.curriculum import Curriculum
    return Curriculum(
        job_id=job_id or "__global__",
        learner_id=learner_id,
        intro_note="",
        sentences_plan=[],
        review_note="",
        total_sentences=0,
    )
