"""
LinguaLearn API - 多语言学习视频生成后端
FastAPI + WebSocket 实时进度 + 邮箱验证注册
"""
import os
import sys
import json
import asyncio
import uuid
import shutil
import time
import io
import hashlib
import random
import smtplib
import subprocess
import html
import traceback
try:
    import resend
except ImportError:
    resend = None
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, _PROJECT_ROOT.as_posix())

import config
import core.db as database
import markdown as md_lib
from core.app.dictionary_router import router as dictionary_router
from core.app.routes.auth_routes import build_auth_router
from core.app.routes.membership_routes import build_membership_router
from core.app.routes.config_routes import build_config_router
from core.app.routes.i18n_routes import build_i18n_router
from core.app.routes.review_routes import build_review_router
from core.app.membership_service import (
    _FREE_MAX_VIDEO_SECONDS,
    _DEFAULT_VIDEO_WATERMARK,
    _PLAN_BY_CODE,
    _detect_country_code,
    _build_membership_status,
)
from ai_tutor.server import (
    startup_event as ai_tutor_startup_event,
    shutdown_event as ai_tutor_shutdown_event,
    tutor_session_legacy as ai_tutor_tutor_session_legacy,
    interactive_tutor_session as ai_tutor_interactive_tutor_session,
    list_jobs as ai_tutor_list_jobs,
    get_job_content as ai_tutor_get_job_content,
    get_learner_memory as ai_tutor_get_learner_memory,
    create_or_update_learner as ai_tutor_create_or_update_learner,
)

app = FastAPI(title="LinguaLearn API", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(dictionary_router)


@app.on_event("startup")
async def _startup_ai_tutor_services() -> None:
    await ai_tutor_startup_event()


@app.on_event("shutdown")
async def _shutdown_ai_tutor_services() -> None:
    await ai_tutor_shutdown_event()

_FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"
_FFPROBE_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffprobe") else "ffprobe"

# ===== 目录 =====
DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = Path(config.OUTPUT_DIR)
TEMP_DIR   = Path(config.TEMP_DIR)
STATIC_DIR = Path("static")
AVATAR_DIR = UPLOAD_DIR / "avatars"

for d in [DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, STATIC_DIR, AVATAR_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 启动时清理历史临时文件（例如上次异常退出遗留）
for p in TEMP_DIR.iterdir():
    try:
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
    except Exception:
        pass


def _cleanup_job_temp_dir(job_id: str) -> None:
    """删除任务临时目录，确保任务结束后不残留 temp 文件。"""
    job_tmp = TEMP_DIR / job_id
    if job_tmp.exists():
        shutil.rmtree(str(job_tmp), ignore_errors=True)
    try:
        if TEMP_DIR.exists() and not any(TEMP_DIR.iterdir()):
            TEMP_DIR.rmdir()
    except Exception:
        pass


def _export_sentence_quiz_assets(
    *,
    job_id: str,
    job_out: Path,
    audio_path: str,
    source_lang: str,
    target_lang: str,
    timestamps: List[Dict[str, Any]],
    sentences_data: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Export per-sentence original audio clips and a sentence quiz manifest.
    Files are written under output/<job_id>/:
      - sentence_quiz.json
      - sq_0001.mp3, sq_0002.mp3, ...
    """
    if not timestamps or not sentences_data:
        return None

    total = min(len(timestamps), len(sentences_data))
    if total <= 0:
        return None

    items: List[Dict[str, Any]] = []
    audio_ok = 0
    for i in range(total):
        ts = timestamps[i] or {}
        sd = sentences_data[i] or {}
        text = (sd.get("original_text") or ts.get("sentence") or "").strip()
        if not text:
            continue

        start = max(0.0, float(ts.get("start", 0.0) or 0.0))
        end = max(start + 0.18, float(ts.get("end", start + 0.18) or (start + 0.18)))
        duration = max(0.18, end - start)

        audio_file = f"sq_{i + 1:04d}.mp3"
        out_audio = job_out / audio_file
        if out_audio.exists():
            out_audio.unlink(missing_ok=True)

        has_audio = False
        if audio_path and Path(audio_path).exists():
            try:
                subprocess.run(
                    [
                        _FFMPEG_BIN,
                        "-y",
                        "-v",
                        "error",
                        "-ss",
                        f"{start:.3f}",
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        str(audio_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "22050",
                        "-b:a",
                        "48k",
                        str(out_audio),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if out_audio.exists() and out_audio.stat().st_size > 0:
                    has_audio = True
                    audio_ok += 1
            except Exception as e:
                print(f"⚠️ 句子音频切片失败 idx={i}: {e}")

        items.append({
            "sentence_index": i,
            "text": text,
            "start": round(start, 3),
            "end": round(end, 3),
            "audio_file": audio_file if has_audio else "",
        })

    if not items:
        return None

    manifest = {
        "version": 1,
        "job_id": job_id,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "audio_ready_count": audio_ok,
        "generated_at": datetime.now().isoformat(),
        "sentences": items,
    }
    (job_out / "sentence_quiz.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ sentence_quiz.json 已保存: {len(items)} 句，音频 {audio_ok} 条")
    return manifest

# ===== 内存存储 =====
jobs:          Dict[str, dict] = {}
job_ws_queues: Dict[str, asyncio.Queue] = {}

# 用户和验证码现在存储在 SQLite 数据库中（见 core/db 模块）

security = HTTPBearer(auto_error=False)


# ===== Auth helpers =====

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _gen_code() -> str:
    return f"{random.randint(0, 999999):06d}"

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    if not credentials:
        return None
    email = database.get_token_email(credentials.credentials)
    if not email:
        return None
    return database.get_user(email)

def require_user(current_user: Optional[dict] = Depends(get_current_user)) -> dict:
    if not current_user:
        raise HTTPException(401, "请先登录")
    return current_user

def _normalize_job(j: dict) -> dict:
    """Convert DB row format (result_json string) to API format (result dict)."""
    if 'result_json' in j:
        result_str = j.pop('result_json', None)
        j['result'] = json.loads(result_str) if result_str else None
    return j


def get_job_or_404(job_id: str) -> dict:
    if job_id in jobs:
        return jobs[job_id]
    # Fall back to DB (e.g. after server restart)
    db_job = database.get_job(job_id)
    if db_job:
        return _normalize_job(db_job)
    raise HTTPException(404, "任务不存在")


# ===== Membership helpers =====

def _probe_video_duration_seconds(path: Path) -> Optional[float]:
    try:
        result = subprocess.run(
            [
                _FFPROBE_BIN, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        v = (result.stdout or "").strip()
        return float(v) if v else None
    except Exception:
        return None


def _normalize_stream_quality(value: str) -> str:
    v = (value or "auto").strip().lower()
    if v in {"auto", "source", "original"}:
        return "auto"
    if v.endswith("p"):
        v = v[:-1]
    return v if v in {"1080", "720", "360"} else "auto"


def _probe_video_height(path: Path) -> Optional[int]:
    try:
        result = subprocess.run(
            [
                _FFPROBE_BIN, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=height",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        v = (result.stdout or "").strip()
        return int(v) if v else None
    except Exception:
        return None


def _ensure_stream_variant(job_id: str, source_path: Path, quality: str) -> Path:
    q = _normalize_stream_quality(quality)
    if q == "auto":
        return source_path
    if source_path.suffix.lower() != ".mp4":
        return source_path

    target_h = int(q)
    src_h = _probe_video_height(source_path)
    if src_h and src_h <= target_h + 2:
        return source_path

    out_dir = OUTPUT_DIR / job_id / "_stream_variants"
    out_dir.mkdir(parents=True, exist_ok=True)
    # bump variant version to invalidate old cache files with incompatible encoding params
    variant_path = out_dir / f"{source_path.stem}_{target_h}p_v2.mp4"

    if variant_path.exists():
        try:
            if variant_path.stat().st_mtime >= source_path.stat().st_mtime:
                return variant_path
        except Exception:
            pass

    tmp_path = out_dir / f"{source_path.stem}_{target_h}p_{uuid.uuid4().hex[:8]}.tmp.mp4"
    vf = (
        f"scale=-2:{target_h}:"
        "flags=lanczos:"
        "force_original_aspect_ratio=decrease"
    )
    try:
        subprocess.run(
            [
                _FFMPEG_BIN, "-y",
                "-i", str(source_path),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                "-profile:v", "high",
                "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(tmp_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        tmp_path.replace(variant_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return variant_path


def _ensure_default_watermark_in_timeline(timeline: dict) -> dict:
    """
    强制注入默认 LinguaLearn 水印（给非会员用）。
    """
    if not timeline:
        return timeline

    elements = timeline.get("elements") or []
    parts = timeline.get("parts") or []
    if not isinstance(elements, list) or not isinstance(parts, list):
        return timeline

    wm_id = None
    for el in elements:
        if el.get("type") == "watermark" and (el.get("style", {}).get("text") == "LinguaLearn" or el.get("id") == "watermark_default"):
            wm_id = el.get("id")
            break

    wm_payload = {
        "id": wm_id or "watermark_default",
        "type": "watermark",
        "visible": True,
        "position": dict(_DEFAULT_VIDEO_WATERMARK["position"]),
        "size": dict(_DEFAULT_VIDEO_WATERMARK["size"]),
        "rotation": _DEFAULT_VIDEO_WATERMARK["rotation"],
        "opacity": _DEFAULT_VIDEO_WATERMARK["opacity"],
        "zIndex": 99,
        "style": {
            "text": _DEFAULT_VIDEO_WATERMARK["text"],
            "fontFamily": "system",
            "fontSize": _DEFAULT_VIDEO_WATERMARK["font_size"],
            "color": "#ffffff",
            "strokeColor": "rgba(0,0,0,0.28)",
            "strokeWidth": 0,
            "locked": True,
            "lockedReason": "free_plan_default_watermark",
        },
        "animation": {
            "enter": {"type": "none", "duration": 0, "easing": "linear"},
            "exit": {"type": "none", "duration": 0, "easing": "linear"},
        },
    }

    # 免费用户仅保留系统默认水印，不允许自定义其他 watermark 元素
    kept = []
    replaced = False
    for el in elements:
        if el.get("type") != "watermark":
            kept.append(el)
            continue
        if (el.get("id") == wm_payload["id"] or el.get("style", {}).get("text") == "LinguaLearn") and not replaced:
            kept.append(wm_payload)
            replaced = True
        # 其他 watermark 直接剔除
    if not replaced:
        kept.append(wm_payload)
    elements = kept

    if not parts:
        parts.append({
            "id": "p_1",
            "repeat": 1,
            "speed": 1.0,
            "styleId": None,
            "elementVisibility": {},
            "elementConfigs": {},
        })

    for p in parts:
        vis = p.setdefault("elementVisibility", {})
        # 清理自定义 watermark 可见性
        for k in list(vis.keys()):
            if k != wm_payload["id"] and str(k).startswith("watermark"):
                del vis[k]
        vis[wm_payload["id"]] = True
        cfg = p.setdefault("elementConfigs", {})
        for k in list(cfg.keys()):
            if k != wm_payload["id"] and str(k).startswith("watermark"):
                del cfg[k]
        cfg[wm_payload["id"]] = {
            "position": dict(_DEFAULT_VIDEO_WATERMARK["position"]),
            "size": dict(_DEFAULT_VIDEO_WATERMARK["size"]),
            "style": dict(wm_payload["style"]),
            "rotation": _DEFAULT_VIDEO_WATERMARK["rotation"],
            "opacity": _DEFAULT_VIDEO_WATERMARK["opacity"],
            "zIndex": 99,
            "animation": dict(wm_payload["animation"]),
        }

    timeline["elements"] = elements
    timeline["parts"] = parts
    return timeline


def _get_stripe_price_id(plan_code: str) -> str:
    mapping = {
        "cn_day": config.STRIPE_PRICE_CN_DAY,
        "cn_week": config.STRIPE_PRICE_CN_WEEK,
        "cn_month": config.STRIPE_PRICE_CN_MONTH,
        "cn_year": config.STRIPE_PRICE_CN_YEAR,
        "intl_day": config.STRIPE_PRICE_INTL_DAY,
        "intl_week": config.STRIPE_PRICE_INTL_WEEK,
        "intl_month": config.STRIPE_PRICE_INTL_MONTH,
        "intl_year": config.STRIPE_PRICE_INTL_YEAR,
    }
    return mapping.get(plan_code, "")


def _activate_membership_for_user(
    email: str,
    plan_code: str,
    provider: str,
    subscription_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    country_code: str = "CN",
) -> None:
    plan = _PLAN_BY_CODE.get(plan_code)
    if not plan:
        raise HTTPException(400, f"未知套餐: {plan_code}")
    now = datetime.now()
    rec = database.get_user_membership(email) or {}
    base = now
    exp = rec.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            if exp_dt > now:
                base = exp_dt
        except Exception:
            pass
    expires_at = (base + timedelta(days=int(plan["days"]))).isoformat()
    database.update_user_membership(
        email,
        tier="member",
        status="active",
        provider=provider,
        plan_code=plan_code,
        plan_name=plan["label"],
        subscription_id=subscription_id,
        customer_id=customer_id,
        country_code=country_code,
        started_at=now.isoformat(),
        expires_at=expires_at,
        auto_renew=1 if plan.get("auto_renew") else 0,
        badge_unlocked=1,
    )
    if plan.get("trial_once"):
        database.mark_trial_used(email)


def _render_markdown_pdf(markdown_text: str, output_pdf: Path, watermark_text: Optional[str] = None) -> None:
    """
    将 markdown 转为 PDF（使用 Playwright 打印，保证样式一致可控）。
    """
    from playwright.sync_api import sync_playwright

    body_html = md_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )
    wm_html = ""
    if watermark_text:
        safe_wm = html.escape(watermark_text)
        wm_html = f'<div class="wm">{safe_wm}</div>'

    doc_html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    @page {{ size: A4; margin: 18mm; }}
    body {{
      font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      color: #111827; line-height: 1.7; font-size: 13px;
    }}
    h1,h2,h3,h4 {{ margin: 14px 0 8px; line-height: 1.35; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 19px; border-left: 4px solid #6366f1; padding-left: 10px; }}
    h3 {{ font-size: 16px; }}
    p {{ margin: 8px 0; }}
    blockquote {{
      margin: 10px 0; padding: 8px 12px; border-left: 3px solid #6366f1; background: #f8fafc;
    }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; font-weight: 700; }}
    code {{ background: #f3f4f6; padding: 1px 5px; border-radius: 4px; }}
    pre {{ background: #111827; color: #e5e7eb; padding: 10px; border-radius: 8px; overflow: auto; }}
    hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 16px 0; }}
    .wm {{
      position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
      pointer-events: none; user-select: none; font-size: 74px; font-weight: 800;
      color: rgba(148,163,184,.22); transform: rotate(-30deg); z-index: 9999;
      letter-spacing: 1px;
    }}
  </style>
</head>
<body>
  {wm_html}
  {body_html}
</body>
</html>"""

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(doc_html, wait_until="load")
        page.pdf(path=str(output_pdf), format="A4", print_background=True)
        browser.close()


# ===== Email sender =====

def _send_email(to_email: str, subject: str, html_body: str, from_email: str = None) -> bool:
    """Send email via Resend (priority) or SMTP fallback. Returns True if sent, False otherwise."""
    if not from_email:
        from_email = getattr(config, 'SMTP_FROM', 'noreply@lingualearn.app')

    # Try Resend first
    if config.RESEND_API_KEY and resend:
        try:
            resend.api_key = config.RESEND_API_KEY
            r = resend.Emails.send({
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "html": html_body
            })
            if r.get("id"):  # Success if id is returned
                return True
        except Exception as e:
            print(f"[Resend Error] {type(e).__name__}: {e}")
            # Fall through to SMTP

    # SMTP fallback
    host = getattr(config, 'SMTP_HOST', '')
    user = getattr(config, 'SMTP_USER', '')
    pw   = getattr(config, 'SMTP_PASS', '')
    port = int(getattr(config, 'SMTP_PORT', 587))

    if not host or not user:
        return False  # dev mode

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = from_email
    msg['To']      = to_email
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        # 使用 SSL (465) 或 TLS (587)
        if port == 465:
            import ssl
            s = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            s = smtplib.SMTP(host, port, timeout=10)
            s.ehlo()
            s.starttls()

        s.login(user, pw)
        s.sendmail(from_email, to_email, msg.as_string())
        s.quit()
        return True
    except Exception as e:
        print(f"[SMTP Error] {type(e).__name__}: {e}")
        return False


def _send_code_email(to_email: str, code: str) -> bool:
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#0a0a12;color:#e2e8f0;border-radius:16px;">
      <h1 style="font-size:24px;font-weight:800;background:linear-gradient(135deg,#6c63ff,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;">LinguaLearn</h1>
      <p style="color:#94a3b8;margin:0 0 32px;font-size:14px;">语言学习视频生成平台</p>
      <p style="margin:0 0 16px;color:#e2e8f0;">您的邮箱验证码：</p>
      <div style="background:#1e1e3a;border:1px solid #6c63ff44;border-radius:12px;padding:24px;text-align:center;margin:0 0 24px;">
        <span style="font-size:40px;font-weight:900;letter-spacing:12px;color:#6c63ff;">{code}</span>
      </div>
      <p style="color:#64748b;font-size:13px;margin:0;">验证码 <strong>10 分钟</strong>内有效。如非本人操作，请忽略此邮件。</p>
    </div>
    """
    return _send_email(to_email, "【LinguaLearn】邮箱验证码", html)


def _send_sms(phone: str, code: str) -> bool:
    """发送短信验证码（使用阿里云）"""
    key_id = getattr(config, 'SMS_ACCESS_KEY_ID', '')
    key_secret = getattr(config, 'SMS_ACCESS_KEY_SECRET', '')
    sign_name = getattr(config, 'SMS_SIGN_NAME', 'LinguaLearn')
    template_code = getattr(config, 'SMS_TEMPLATE_CODE', '')

    if not key_id or not key_secret or not template_code:
        return False  # dev mode

    try:
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_dysmsapi20170525.models import SendSmsRequest
        from alibabacloud_core.config import Config as AliConfig

        config_obj = AliConfig(
            access_key_id=key_id,
            access_key_secret=key_secret,
            region_id='cn-hangzhou',
        )
        client = Client(config_obj)
        request = SendSmsRequest(
            phone_numbers=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=json.dumps({"code": code})
        )
        response = client.send_sms(request)
        return response.body.code == 'Ok'
    except Exception as e:
        print(f"[SMS Error] {type(e).__name__}: {e}")
        return False


# ===== Progress push =====

class ProgressCapture(io.StringIO):
    def __init__(self, job_id: str, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.job_id = job_id
        self.loop   = loop

    def write(self, text: str):
        super().write(text)
        text = text.strip()
        if text:
            asyncio.run_coroutine_threadsafe(
                _push(self.job_id, "log", text), self.loop
            )

    def flush(self): pass


async def _push(job_id: str, msg_type: str, data):
    if job_id in job_ws_queues:
        await job_ws_queues[job_id].put({"type": msg_type, "data": data, "timestamp": time.time()})


def update_job(job_id: str, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        # 同步保存到数据库
        job = jobs[job_id]
        database.update_job_status(
            job_id,
            status=job.get("status"),
            step=job.get("step"),
            step_name=job.get("step_name"),
            error=job.get("error"),
            result_json=json.dumps(job.get("result")) if job.get("result") else None,
            video_clips_pct=job.get("video_clips_pct", 0),
            video_write_pct=job.get("video_write_pct", 0),
        )


# ===== Video processing task =====

async def process_video_job(
    job_id: str, video_path: str,
    source_lang: str, target_lang: str, resolution: str,
    part1_repeat: int, part2_repeat: int, part3_repeat: int,
    part2_slow_speed: float,
    num_words: int, num_expressions: int,
    layout: Optional[dict], style: Optional[dict],
    parts_list: Optional[list],
    style_id: str,
    animation: Optional[str],
    loop: asyncio.AbstractEventLoop,
    timeline_json: Optional[dict] = None,
    owner_email: str = "",
    membership_tier: str = "free",
    doc_watermark_text: str = "LinguaLearn",
    doc_watermark_enabled: bool = True,
):
    def run_in_thread():
        # 这行打印直接输出到真实终端（在 stdout 重定向之前）
        import sys as _sys
        _real_stdout = _sys.__stdout__
        _real_stdout.write(f"\n[Thread] ✅ 后台线程启动: job={job_id[:8]}\n")
        _real_stdout.flush()

        capture    = ProgressCapture(job_id, loop)
        old_stdout = sys.stdout
        sys.stdout = capture
        try:
            sentence_quiz_manifest = None
            # Apply config globals
            config.SOURCE_LANGUAGE  = source_lang
            config.TARGET_LANGUAGE  = target_lang
            config.VIDEO_RESOLUTION = resolution

            # ── 构建 parts_config（新格式）──
            if parts_list and len(parts_list) > 0:
                print(f"📋 使用新的 Part 配置: {len(parts_list)} 个 Part")
                new_parts_config = []
                for p in parts_list:
                    boxes_list = [b.get("type", "") for b in p.get("boxes", [])]
                    new_parts_config.append({
                        "repeat": p.get("repeat", 1),
                        "slow":   p.get("slow", False),
                        "speed":  float(p.get("speed", 1.0)),
                        "show_subtitle": "subtitle" in boxes_list,
                        "show_wordbox":  "wordbox" in boxes_list,
                        "show_exprbox":  "expressionbox" in boxes_list,
                    })
                for j, pc in enumerate(new_parts_config):
                    print(f"  Part{j+1}: repeat={pc['repeat']} slow={pc['slow']} "
                          f"sub={pc['show_subtitle']} wb={pc['show_wordbox']} eb={pc['show_exprbox']}")
            else:
                print("📋 使用旧的 Part 配置（config 常量）")
                new_parts_config = None  # VideoProcessor 内部 _legacy_parts_config() 处理

                # 旧式：设置 config 常量（向后兼容）
                config.PART1_REPEAT_COUNT = part1_repeat
                config.PART2_REPEAT_COUNT = part2_repeat
                config.PART3_REPEAT_COUNT = part3_repeat
                config.SPEED_SLOW         = part2_slow_speed

            # ── 构建嵌套 layout（新格式）──
            nested_layout: dict = {}
            seen_layout: set = set()
            _key_map = {"subtitle": "subtitle", "wordbox": "wordbox", "expressionbox": "exprbox"}
            if parts_list:
                for p in parts_list:
                    for box in p.get("boxes", []):
                        btype = box.get("type", "")
                        lkey  = _key_map.get(btype)
                        if lkey and lkey not in seen_layout:
                            nested_layout[lkey] = {
                                "x_pct": box.get("x", 0) / 100.0,
                                "y_pct": box.get("y", 0) / 100.0,
                                "w_pct": box.get("w", 20) / 100.0,
                                "h_pct": box.get("h", 20) / 100.0,
                                "font_scale": box.get("font_scale", 1.0),
                            }
                            seen_layout.add(lkey)
            if not nested_layout and layout:
                # 从旧式 flat layout_dict 转换
                if "subtitle_width_pct" in layout:
                    nested_layout["subtitle"] = {
                        "x_pct": layout.get("subtitle_x_pct", 0.011),
                        "y_pct": layout.get("subtitle_y_pct", 0.704),
                        "w_pct": layout.get("subtitle_width_pct", 0.961),
                        "h_pct": layout.get("subtitle_height_pct", 0.346),
                        "font_scale": layout.get("subtitle_font_size_scale", 1.15),
                    }
                if "wordbox_width_pct" in layout:
                    nested_layout["wordbox"] = {
                        "x_pct": layout.get("wordbox_x_pct", 0.761),
                        "y_pct": layout.get("wordbox_y_pct", 0.008),
                        "w_pct": layout.get("wordbox_width_pct", 0.222),
                        "h_pct": layout.get("wordbox_height_pct", 0.689),
                        "font_scale": layout.get("wordbox_font_size_scale", 0.9),
                    }
                if "exprbox_width_pct" in layout:
                    nested_layout["exprbox"] = {
                        "x_pct": layout.get("exprbox_x_pct", 0.002),
                        "y_pct": layout.get("exprbox_y_pct", 0.005),
                        "w_pct": layout.get("exprbox_width_pct", 0.275),
                        "h_pct": layout.get("exprbox_height_pct", 0.483),
                        "font_scale": layout.get("exprbox_font_size_scale", 1.0),
                    }

            update_job(job_id, status="running", step=1, step_name="正在提取音频...")

            from core.learning.audio_transcriber import AudioTranscriber
            from core.learning.sentence_splitter import SentenceSplitter
            from core.learning.word_analyzer import WordAnalyzer
            from core.learning.video_processor import VideoProcessor
            from core.learning.markdown_exporter import MarkdownExporter

            job_out = OUTPUT_DIR / job_id
            job_out.mkdir(exist_ok=True)
            job_tmp = TEMP_DIR / job_id
            job_tmp.mkdir(parents=True, exist_ok=True)
            config.OUTPUT_DIR = str(job_out)
            config.TEMP_DIR   = str(job_tmp)

            # 调试快照：落盘本次任务使用的 timeline，便于排查“编辑器与成片不一致”。
            if timeline_json:
                try:
                    with open(job_out / "timeline_debug.json", "w", encoding="utf-8") as f:
                        json.dump(timeline_json, f, ensure_ascii=False, indent=2)
                except Exception as _e:
                    print(f"⚠️ timeline_debug.json 写入失败: {_e}")

            output_name = Path(video_path).stem[:50]

            print(f"\n{'='*60}")
            print(f"🎬 开始处理任务 {job_id[:8]}")
            print(f"📁 视频路径: {video_path}")
            print(f"📁 输出目录: {job_out}")
            print(f"🌐 {source_lang} -> {target_lang} | 分辨率: {config.VIDEO_RESOLUTION}")
            print(f"🔧 Part1: repeat={config.PART1_REPEAT_COUNT}, sub={config.PART1_SHOW_SUBTITLE}, wb={config.PART1_SHOW_WORD_BOX}, eb={config.PART1_SHOW_EXPRESSION_BOX}")
            print(f"🔧 Part2: repeat={config.PART2_REPEAT_COUNT}, slow={config.SPEED_SLOW}, sub={config.PART2_SHOW_SUBTITLE}, wb={config.PART2_SHOW_WORD_BOX}, eb={config.PART2_SHOW_EXPRESSION_BOX}")
            print(f"🔧 Part3: repeat={config.PART3_REPEAT_COUNT}, sub={config.PART3_SHOW_SUBTITLE}, wb={config.PART3_SHOW_WORD_BOX}, eb={config.PART3_SHOW_EXPRESSION_BOX}")
            print(f"{'='*60}\n")

            def check_cancelled():
                return jobs.get(job_id, {}).get('status') == 'cancelled'

            def progress_callback(phase, data):
                asyncio.run_coroutine_threadsafe(
                    _push(job_id, 'video_clips' if phase == 'clips' else 'video_write', data), loop
                )

            # Step 1 – transcribe
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 1, "name": "音频转录", "total": 5}), loop)
            print(f"🎵 开始提取音频: {video_path}")
            transcriber = AudioTranscriber(source_lang=source_lang)
            audio_path  = transcriber.extract_audio_from_video(video_path)
            print(f"🎵 音频提取完成: {audio_path}")
            print("🎙️ 开始转录音频...")
            transcription = transcriber.transcribe_once_with_word_timestamps(audio_path)
            text = transcription["text"]
            print(f"✅ 转录完成，文本长度: {len(text)} 字符")

            # Step 2 – split sentences
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 2, "name": "智能分句", "total": 5}), loop)
            update_job(job_id, step=2, step_name="正在分割句子...")
            print("✂️ 开始分割句子...")
            splitter   = SentenceSplitter(max_words=config.MAX_SENTENCE_WORDS,
                                          min_words=config.MIN_SENTENCE_WORDS,
                                          source_lang=source_lang)
            sentences  = splitter.split_text(text)
            split_mapping = splitter.get_split_mapping()
            print(f"✂️ 句子分割完成，共 {len(sentences)} 句")
            print("⏰ 开始对齐时间戳...")
            timestamps = transcriber.align_sentences_to_timestamps(
                audio_path, sentences, output_name, split_mapping=split_mapping
            )
            print("✅ 时间戳对齐完成")

            # Step 3 – analyse
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 3, "name": "词汇分析", "total": 5}), loop)
            update_job(job_id, step=3, step_name=f"正在分析 {len(sentences)} 个句子...")
            print(f"🧠 开始分析 {len(sentences)} 个句子...")
            analyzer       = WordAnalyzer(source_lang=source_lang, target_lang=target_lang)
            sentences_data = analyzer.batch_analyze(sentences)
            print("✅ 词汇分析完成")

            # Trim words/expressions per sentence if user set limits
            if num_words > 0 or num_expressions > 0:
                print(f"✏️ 限制每句单词数: {num_words}, 表达数: {num_expressions}")
                for sd in sentences_data:
                    if num_words > 0:
                        sd['key_words'] = sd.get('key_words', [])[:num_words]
                    if num_expressions > 0:
                        sd['useful_expressions'] = sd.get('useful_expressions', [])[:num_expressions]

            # Step 4 – markdown
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 4, "name": "生成文字稿", "total": 5}), loop)
            update_job(job_id, step=4, step_name="正在生成学习文档...")
            print("📝 开始生成 Markdown 学习文档...")
            exporter = MarkdownExporter(output_dir=str(job_out),
                                        source_lang=source_lang, target_lang=target_lang,
                                        footer_watermark_text=doc_watermark_text,
                                        footer_watermark_enabled=doc_watermark_enabled)
            markdown_path = exporter.export(sentences_data, f"{output_name}.md")
            print(f"✅ 文档生成完成: {markdown_path}")

            # Step 5 – render video
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 5, "name": "渲染学习视频", "total": 5}), loop)
            update_job(job_id, step=5, step_name="正在渲染视频（最耗时）...")
            print("🎬 开始渲染视频...")
            processor     = VideoProcessor()
            segments_info = [{"start": ts.get("start", 0), "end": ts.get("end", 0)} for ts in timestamps]
            video_output  = str(job_out / f"{output_name}.mp4")
            print(f"🎯 输出路径: {video_output}")
            print(f"🎨 样式模版: {style_id}")
            if nested_layout:
                print(f"📐 布局: {list(nested_layout.keys())}")

            print("🚀 开始处理完整视频...")
            # 将语言信息注入 style_dict，供 html_renderer 使用
            if style:
                style['source_lang'] = source_lang
                style['target_lang'] = target_lang
            video_paths = processor.process_full_video(
                video_path=video_path,
                sentences_data=sentences_data,
                output_path=video_output,
                segments_info=segments_info,
                progress_callback=progress_callback,
                style_id=style_id,
                layout=nested_layout or None,
                parts_config=new_parts_config,
                animation=animation,
                cancelled_fn=check_cancelled,
                style=style or None,
                timeline_json=timeline_json,
                membership_tier=membership_tier,
                forced_watermark=_DEFAULT_VIDEO_WATERMARK if membership_tier != "member" else None,
            )
            print("🎬 视频处理完成")

            if video_paths.get('cancelled'):
                return

            # 保存含时间戳的 segments.json，供视频预览页使用
            try:
                saved_with_real_timing = False
                real_timing = video_paths.get("sentence_timing") if isinstance(video_paths, dict) else None
                if isinstance(real_timing, list) and len(real_timing) == len(segments_info):
                    segs_with_text = []
                    for seg, sd, st in zip(segments_info, sentences_data, real_timing):
                        seg_video_start = float(st.get("seg_start", 0.0))
                        seg_video_end = float(st.get("seg_end", seg_video_start))
                        first_overlay_start = st.get("first_overlay_start")
                        jump_target = (
                            float(first_overlay_start)
                            if first_overlay_start is not None
                            else seg_video_start
                        )
                        segs_with_text.append({
                            "start": seg["start"],
                            "end": seg["end"],
                            "video_start": round(jump_target, 3),   # 跳转（真实片段时间线）
                            "seg_start": round(seg_video_start, 3),  # 高亮起点
                            "seg_end": round(seg_video_end, 3),      # 高亮终点
                            "text": sd.get("original_text", ""),
                        })
                    (job_out / "segments.json").write_text(
                        json.dumps(segs_with_text, ensure_ascii=False, indent=2), encoding='utf-8'
                    )
                    print(f"✅ segments.json 已保存(真实时长): {len(segs_with_text)} 条")
                    saved_with_real_timing = True

                if not saved_with_real_timing:
                    # 构建与 video_processor 实际使用的 parts 完全一致的列表
                    _parts_cfg = None

                    # 优先级1：timeline_json 模式（与 video_processor.py 110-135 行逻辑一致）
                    if timeline_json and not new_parts_config:
                        tl_parts = timeline_json.get("parts", [])
                        tl_elements = timeline_json.get("elements", [])
                        elem_type_map = {e["id"]: e["type"] for e in tl_elements}
                        _parts_cfg = []
                        for tp in tl_parts:
                            vis = tp.get("elementVisibility", {})
                            show_sub = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "subtitle")
                            show_wb  = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "wordbox")
                            show_eb  = any(vis.get(eid) for eid, etype in elem_type_map.items() if etype == "exprbox")
                            speed = float(tp.get("speed", 1.0))
                            _parts_cfg.append({
                                "repeat": tp.get("repeat", 1),
                                "slow": speed != 1.0,
                                "speed": speed,
                                "show_subtitle": show_sub,
                                "show_wordbox": show_wb,
                                "show_exprbox": show_eb,
                            })
                        print(f"📋 segments.json 使用 timeline_json parts: {len(_parts_cfg)} 个")

                    # 优先级2：new_parts_config（Form 表单模式）
                    if not _parts_cfg and new_parts_config:
                        _parts_cfg = new_parts_config

                    # 优先级3：旧 config 常量（兼容旧模式）
                    if not _parts_cfg:
                        _parts_cfg = []
                        if getattr(config, "PART1_REPEAT_COUNT", 0) > 0:
                            _parts_cfg.append({
                                "repeat": config.PART1_REPEAT_COUNT, "speed": 1.0, "slow": False,
                                "show_subtitle": getattr(config, "PART1_SHOW_SUBTITLE", False),
                                "show_wordbox":  getattr(config, "PART1_SHOW_WORD_BOX", False),
                                "show_exprbox":  getattr(config, "PART1_SHOW_EXPRESSION_BOX", False),
                            })
                        if getattr(config, "PART2_REPEAT_COUNT", 0) > 0:
                            _parts_cfg.append({
                                "repeat": config.PART2_REPEAT_COUNT,
                                "speed": getattr(config, "SPEED_SLOW", 0.75), "slow": True,
                                "show_subtitle": getattr(config, "PART2_SHOW_SUBTITLE", True),
                                "show_wordbox":  getattr(config, "PART2_SHOW_WORD_BOX", True),
                                "show_exprbox":  getattr(config, "PART2_SHOW_EXPRESSION_BOX", True),
                            })
                        if getattr(config, "PART3_REPEAT_COUNT", 0) > 0:
                            _parts_cfg.append({
                                "repeat": config.PART3_REPEAT_COUNT, "speed": 1.0, "slow": False,
                                "show_subtitle": getattr(config, "PART3_SHOW_SUBTITLE", True),
                                "show_wordbox":  getattr(config, "PART3_SHOW_WORD_BOX", True),
                                "show_exprbox":  getattr(config, "PART3_SHOW_EXPRESSION_BOX", True),
                            })
                        if not _parts_cfg:
                            _parts_cfg = [
                                {"repeat": 1, "speed": 1.0, "slow": False,
                                 "show_subtitle": False, "show_wordbox": False, "show_exprbox": False},
                                {"repeat": 2, "speed": 0.75, "slow": True,
                                 "show_subtitle": True,  "show_wordbox": True,  "show_exprbox": True},
                            ]

                    sentence_part_mode = False
                    if timeline_json:
                        bind_raw = str(
                            timeline_json.get("partBinding")
                            or timeline_json.get("part_binding")
                            or timeline_json.get("sentencePartMode")
                            or ""
                        ).strip().lower()
                        if bind_raw in {"sentence", "per_sentence", "per-sentence", "one_to_one", "1:1", "one-to-one"}:
                            sentence_part_mode = True
                        elif len(_parts_cfg) == len(segments_info) and len(_parts_cfg) > 0:
                            all_repeat_once = all(max(1, int(p.get("repeat", 1))) == 1 for p in _parts_cfg)
                            if all_repeat_once:
                                sentence_part_mode = True

                    video_cursor = 0.0
                    segs_with_text = []
                    for i, (seg, sd) in enumerate(zip(segments_info, sentences_data)):
                        s_start = float(seg["start"]); s_end = float(seg["end"])
                        s_next = float(segments_info[i+1]["start"]) if i+1 < len(segments_info) else s_end
                        if i > 0 and i - 1 < len(segments_info):
                            prev_end = float(segments_info[i - 1]["end"])
                            if s_start < prev_end:
                                s_start = prev_end
                        if s_next < s_end:
                            s_end = s_next
                        if s_end <= s_start:
                            s_end = s_start + 0.1
                        seg_video_start = video_cursor  # 此句在生成视频中的起始
                        first_overlay_start = None      # 第一个有叠加内容（字幕/词框）的 part 起始
                        if sentence_part_mode:
                            if i < len(_parts_cfg):
                                part_iter = [(i, _parts_cfg[i])]
                            else:
                                part_iter = []
                        else:
                            part_iter = list(enumerate(_parts_cfg))

                        for j, part in part_iter:
                            spd = float(part.get("speed", 1.0))
                            is_slow = (spd != 1.0) or part.get("slow", False)
                            if part.get("slow", False) and spd == 1.0:
                                spd = float(getattr(config, "SPEED_SLOW", 0.75))
                            rpt = max(1, int(part.get("repeat", 1)))
                            # 与渲染规则一致：
                            # part1 用下一句 start，其余 part 用当前句 end
                            is_part1 = (j == 0)
                            part_end = s_next if (is_part1 and i + 1 < len(segments_info)) else s_end
                            if part_end <= s_start:
                                part_end = s_end
                            raw_dur = max(0.1, part_end - s_start)
                            clip_dur = raw_dur / spd
                            has_overlay = (
                                part.get("show_subtitle", False) or
                                part.get("show_wordbox", False) or
                                part.get("show_exprbox", False)
                            )
                            if has_overlay and first_overlay_start is None:
                                first_overlay_start = video_cursor
                            video_cursor += clip_dur * rpt
                       
                        # 智能跳转优先落到“该句第一次可见”的时间点；
                        # 若该句所有 part 都无可见叠加内容，则退回句子在视频中的起始。
                        jump_target = first_overlay_start if first_overlay_start is not None else seg_video_start
                        segs_with_text.append({
                            "start": seg["start"],
                            "end": seg["end"],
                            "video_start": round(jump_target, 3),       # 跳转
                            "seg_start": round(seg_video_start, 3),     # 高亮用：句子在视频起始
                            "seg_end": round(video_cursor, 3),           # 高亮用：句子在视频结束
                            "text": sd.get("original_text", ""),
                        })
                    (job_out / "segments.json").write_text(
                        json.dumps(segs_with_text, ensure_ascii=False, indent=2), encoding='utf-8'
                    )
                    print(f"✅ segments.json 已保存: {len(segs_with_text)} 条")
            except Exception as e:
                print(f"⚠️ segments.json 保存失败: {e}")

            full_video = job_out / f"{output_name}_full.mp4"
            final_full = job_out / "学习版.mp4"
            if full_video.exists():
                shutil.move(str(full_video), str(final_full))

            # 预生成可选清晰度（完成任务前先转好，观看页可立即切换）
            if final_full.exists():
                try:
                    print("🎞️ 开始预生成 720p/360p 播放版本...")
                    for q in ("720", "360"):
                        vp = _ensure_stream_variant(job_id, final_full, q)
                        print(f"  ✓ {q}p: {vp.name}")
                except Exception as _sv_e:
                    print(f"⚠️ 预生成清晰度失败（可回退点播转码）: {_sv_e}")

            # 句子听写资产（原声切片 + sentence_quiz.json）
            try:
                sentence_quiz_manifest = _export_sentence_quiz_assets(
                    job_id=job_id,
                    job_out=job_out,
                    audio_path=audio_path,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    timestamps=timestamps,
                    sentences_data=sentences_data,
                )
                if sentence_quiz_manifest and owner_email:
                    inserted = database.upsert_review_sentences(
                        owner_email,
                        job_id,
                        sentence_quiz_manifest.get("sentences", []),
                        source_lang=source_lang,
                        target_lang=target_lang,
                    )
                    print(f"🧠 已写入句子复习库: +{inserted}")
            except Exception as _sqe:
                print(f"⚠️ 句子听写资产生成失败: {_sqe}")

            # 尝试自动生成视频名称（若尚未命名）
            auto_name = None
            try:
                if sentences_data:
                    auto_name = analyzer.generate_video_name(sentences_data)
            except Exception as _ne:
                print(f"⚠️ 自动命名失败: {_ne}")

            update_job(job_id, status="done", step=5, step_name="完成！",
                       result={
                           "sentences_count": len(sentences_data),
                           "full_video":  "学习版.mp4" if final_full.exists() else None,
                           "markdown":    f"{output_name}.md",
                           "sentence_quiz": "sentence_quiz.json" if sentence_quiz_manifest else None,
                           "source_lang": source_lang,
                           "target_lang": target_lang,
                       })
            if auto_name and jobs.get(job_id, {}).get("name") is None:
                database.update_job_status(job_id, name=auto_name)
                if job_id in jobs:
                    jobs[job_id]["name"] = auto_name
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "done", {"sentences": len(sentences_data)}), loop)

            # Delete uploaded source video now that output is ready
            try:
                src_video = Path(video_path)
                if src_video.exists():
                    src_video.unlink()
                    print(f"🗑️ 已删除上传视频: {src_video.name}")
            except Exception as _del_e:
                print(f"⚠️ 删除上传视频失败: {_del_e}")

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"❌ 处理失败: {e}\n{err}")
            update_job(job_id, status="error", error=str(e))
            asyncio.run_coroutine_threadsafe(_push(job_id, "error", str(e)), loop)
        finally:
            _cleanup_job_temp_dir(job_id)
            sys.stdout = old_stdout

    print(f"[process_video_job] 🚀 Coroutine 启动, job={job_id[:8]}, 即将 run_in_executor")
    await asyncio.get_event_loop().run_in_executor(None, run_in_thread)
    print(f"[process_video_job] 🏁 run_in_executor 完成, job={job_id[:8]}")


# ============================================================
# Route composition
# ============================================================

app.include_router(build_auth_router(
    database=database,
    config=config,
    get_current_user=get_current_user,
    require_user=require_user,
    detect_country_code=_detect_country_code,
    build_membership_status=_build_membership_status,
    gen_code=_gen_code,
    hash_password=_hash,
    send_code_email=_send_code_email,
    send_sms=_send_sms,
    send_email=_send_email,
    avatar_dir=AVATAR_DIR,
    resend_module=resend,
))
app.include_router(build_membership_router(
    database=database,
    config=config,
    require_user=require_user,
    detect_country_code=_detect_country_code,
    build_membership_status=_build_membership_status,
    plan_by_code=_PLAN_BY_CODE,
    get_stripe_price_id=_get_stripe_price_id,
    activate_membership_for_user=_activate_membership_for_user,
))
app.include_router(build_config_router(
    database=database,
    require_user=require_user,
    get_job_or_404=get_job_or_404,
    output_dir=OUTPUT_DIR,
))
app.include_router(build_i18n_router(config=config))
app.include_router(build_review_router(
    database=database,
    config=config,
    require_user=require_user,
    get_job_or_404=get_job_or_404,
    output_dir=OUTPUT_DIR,
))

# ============================================================
# JOB routes
# ============================================================

@app.get("/api/languages")
async def get_languages():
    return {"languages": [
        {"code": code, "native_name": name, "flag": config.LANGUAGE_FLAGS.get(code, "🌐")}
        for code, name in config.LANGUAGE_NATIVE_NAMES.items()
    ]}


@app.get("/api/styles")
async def get_styles():
    """返回所有样式模版的预览信息（供前端样式画廊使用）"""
    from core.rendering.style_templates import STYLE_TEMPLATES
    return {
        sid: {
            "name":           t["name"],
            "desc":           t["desc"],
            "preview_colors": t["preview_colors"],
            "animation":      t.get("animation", "fade"),
            "css":            t.get("css", {}),
        }
        for sid, t in STYLE_TEMPLATES.items()
    }


@app.post("/api/jobs")
async def create_job(
    request:            Request,
    video:              UploadFile = File(...),
    source_lang:        str   = Form("en"),
    target_lang:        str   = Form("zh-Hans"),
    resolution:         str   = Form("1080p"),
    part1_repeat:       int   = Form(1),
    part2_repeat:       int   = Form(2),
    part3_repeat:       int   = Form(1),
    part2_slow_speed:   float = Form(0.75),
    num_words:          int   = Form(0),      # 0 = no limit
    num_expressions:    int   = Form(0),
    layout:             str   = Form("{}"),   # position percentages（旧格式，保留兼容）
    style:              str   = Form("{}"),   # visual style options
    parts_json:         str   = Form("[]"),   # 新的 Part 配置
    style_id:           str   = Form("aurora_dark"),  # 样式模版 ID
    animation:          str   = Form("fade"),          # 入场动画类型
    timeline_json:      str   = Form(""),              # 新 Timeline JSON（优先级最高）
    current_user: dict = Depends(require_user),
):
    valid_langs = set(config.LANGUAGE_NATIVE_NAMES.keys())
    if source_lang not in valid_langs or target_lang not in valid_langs:
        raise HTTPException(400, "不支持的语言代码")
    if source_lang == target_lang:
        raise HTTPException(400, "源语言和目标语言不能相同")

    country_code = _detect_country_code(request)
    membership = _build_membership_status(current_user["email"], country_code=country_code)
    limits = membership["limits"]
    tier = membership["tier"]
    daily_limit = limits.get("daily_video_limit")
    if daily_limit is not None and membership["usage"]["videos_generated_today"] >= daily_limit:
        raise HTTPException(403, f"免费用户每日最多生成 {daily_limit} 个视频，请开通会员继续。")

    try:
        layout_dict = json.loads(layout) if layout else {}
    except Exception:
        layout_dict = {}
    try:
        style_dict = json.loads(style) if style else {}
    except Exception:
        style_dict = {}
    try:
        parts_list = json.loads(parts_json) if parts_json else []
    except Exception:
        parts_list = []

    # ===== 新 Timeline JSON 模式 =====
    timeline_dict = None
    if timeline_json and timeline_json.strip():
        try:
            timeline_dict = json.loads(timeline_json)
            # 从 timeline 中提取配置（覆盖 form 字段的值）
            source_lang = timeline_dict.get("sourceLang", source_lang)
            target_lang = timeline_dict.get("targetLang", target_lang)
            tl_res = timeline_dict.get("resolution", {})
            if tl_res.get("width") == 1920:
                resolution = "1080p"
            elif tl_res.get("width") == 1280:
                resolution = "720p"
            num_words = timeline_dict.get("numWords", num_words)
            num_expressions = timeline_dict.get("numExprs", num_expressions)
            style_id = timeline_dict.get("styleId", style_id)
            if tier != "member":
                timeline_dict = _ensure_default_watermark_in_timeline(timeline_dict)
            # timeline_json 是新主配置源，避免与旧版 parts/layout 双轨混用导致渲染结果不一致
            parts_list = []
            layout_dict = {}
            print(f"📦 使用 Timeline JSON 模式: {len(timeline_dict.get('elements', []))} 个元素, "
                  f"{len(timeline_dict.get('parts', []))} 个 Part")
        except Exception as e:
            print(f"⚠️ timeline_json 解析失败: {e}, 回退到旧模式")
            timeline_dict = None

    # timeline 覆盖后再次校验语言参数，确保支持任意合法组合
    if source_lang not in valid_langs or target_lang not in valid_langs:
        raise HTTPException(400, "不支持的语言代码")
    if source_lang == target_lang:
        raise HTTPException(400, "源语言和目标语言不能相同")

    # ===== 从 parts_list 提取框的布局信息 =====
    # 将新的 parts/boxes 系统中的框位置（0-100%）转换为 VideoProcessor 期望的格式（0-1小数）
    if parts_list:
        print(f"\n{'='*60}")
        print(f"📦 解析 parts_list: {len(parts_list)} 个 Part")
        for i, p in enumerate(parts_list):
            box_types = [b.get('type','?') for b in p.get('boxes', [])]
            print(f"  Part {i+1} [{p.get('label','?')}]: repeat={p.get('repeat',1)}, slow={p.get('slow',False)}, boxes={box_types}")
        print(f"{'='*60}\n")

        # 遍历所有 Part 的 boxes，提取各类型框的位置（以第一次出现为准）
        for part in parts_list:
            for box in part.get('boxes', []):
                btype = box.get('type', '')
                x = box.get('x', 0) / 100.0
                y = box.get('y', 0) / 100.0
                w = box.get('w', 0) / 100.0
                h = box.get('h', 0) / 100.0

                if btype == 'subtitle' and 'subtitle_width_pct' not in layout_dict:
                    layout_dict['subtitle_x_pct'] = x
                    layout_dict['subtitle_y_pct'] = y
                    layout_dict['subtitle_width_pct'] = w
                    layout_dict['subtitle_height_pct'] = h
                    print(f"📐 subtitle 布局: x={x:.3f}, y={y:.3f}, w={w:.3f}, h={h:.3f}")

                elif btype == 'wordbox' and 'wordbox_width_pct' not in layout_dict:
                    layout_dict['wordbox_x_pct'] = x
                    layout_dict['wordbox_y_pct'] = y
                    layout_dict['wordbox_width_pct'] = w
                    layout_dict['wordbox_height_pct'] = h
                    print(f"📐 wordbox 布局: x={x:.3f}, y={y:.3f}, w={w:.3f}, h={h:.3f}")

                elif btype == 'expressionbox' and 'exprbox_width_pct' not in layout_dict:
                    layout_dict['exprbox_x_pct'] = x
                    layout_dict['exprbox_y_pct'] = y
                    layout_dict['exprbox_width_pct'] = w
                    layout_dict['exprbox_height_pct'] = h
                    print(f"📐 exprbox 布局: x={x:.3f}, y={y:.3f}, w={w:.3f}, h={h:.3f}")

        # 根据 parts_list 设置每个 Part 的框显示配置（映射到固定的 3-Part 结构）
        import config as cfg_module
        for i, part in enumerate(parts_list[:3]):
            box_types = set(b.get('type', '') for b in part.get('boxes', []))
            show_sub  = 'subtitle' in box_types
            show_wb   = 'wordbox' in box_types
            show_eb   = 'expressionbox' in box_types
            print(f"🎬 Part{i+1} 显示配置: subtitle={show_sub}, wordbox={show_wb}, exprbox={show_eb}")
            if i == 0:
                cfg_module.PART1_SHOW_SUBTITLE       = show_sub
                cfg_module.PART1_SHOW_WORD_BOX       = show_wb
                cfg_module.PART1_SHOW_EXPRESSION_BOX = show_eb
            elif i == 1:
                cfg_module.PART2_SHOW_SUBTITLE       = show_sub
                cfg_module.PART2_SHOW_WORD_BOX       = show_wb
                cfg_module.PART2_SHOW_EXPRESSION_BOX = show_eb
            elif i == 2:
                cfg_module.PART3_SHOW_SUBTITLE       = show_sub
                cfg_module.PART3_SHOW_WORD_BOX       = show_wb
                cfg_module.PART3_SHOW_EXPRESSION_BOX = show_eb

    job_id        = str(uuid.uuid4())
    video_filename = f"{job_id}_{video.filename}"
    video_path    = UPLOAD_DIR / video_filename
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    # 非会员：单视频时长上限 5 分钟；会员：30 分钟
    duration_sec = _probe_video_duration_seconds(video_path)
    max_sec = limits.get("max_video_seconds", _FREE_MAX_VIDEO_SECONDS)
    if duration_sec and duration_sec > max_sec:
        try:
            video_path.unlink(missing_ok=True)
        except Exception:
            pass
        max_min = int(max_sec // 60)
        raise HTTPException(403, f"当前账号单个视频最长支持 {max_min} 分钟（当前约 {duration_sec/60:.1f} 分钟）")

    jobs[job_id] = {
        "id":             job_id,
        "status":         "queued",
        "step":           0,
        "step_name":      "等待处理...",
        "source_lang":    source_lang,
        "target_lang":    target_lang,
        "video_filename": video.filename,
        "created_by":     current_user["email"],
        "created_at":     datetime.now().isoformat(),
        "updated_at":     datetime.now().isoformat(),
        "result":         None,
        "error":          None,
        "cancelled":      False,
        "video_clips_pct": 0,
        "video_write_pct": 0,
        "name":           None,
    }

    # 保存到数据库
    database.save_job(
        job_id=job_id,
        email=current_user["email"],
        status="queued",
        step=0,
        step_name="等待处理...",
        source_lang=source_lang,
        target_lang=target_lang,
        video_filename=video.filename,
    )

    job_ws_queues[job_id] = asyncio.Queue()

    asyncio.create_task(process_video_job(
            job_id=job_id, video_path=str(video_path),
            source_lang=source_lang, target_lang=target_lang, resolution=resolution,
            part1_repeat=part1_repeat, part2_repeat=part2_repeat, part3_repeat=part3_repeat,
            part2_slow_speed=part2_slow_speed,
            num_words=num_words, num_expressions=num_expressions,
            layout=layout_dict or None, style=style_dict or None,
            parts_list=parts_list or None,
            style_id=style_id or "aurora_dark",
            animation=animation or "fade",
            timeline_json=timeline_dict,
            owner_email=current_user["email"],
            membership_tier=tier,
            doc_watermark_text=(
                membership.get("doc_watermark_text") if tier == "member" else "LinguaLearn"
            ),
            doc_watermark_enabled=(
                bool(membership.get("doc_watermark_enabled", True)) if tier == "member" else True
            ),
            loop=asyncio.get_event_loop(),
        ))

    database.increment_daily_video_usage(current_user["email"])

    return {
        "job_id": job_id,
        "status": "queued",
        "membership_tier": tier,
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    return get_job_or_404(job_id)


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str, current_user: dict = Depends(require_user)):
    job = get_job_or_404(job_id)
    if job["status"] in ("done", "error", "cancelled"):
        # 删除已完成任务：清理文件 + 删除 DB 记录
        import shutil as _shutil
        job_out = OUTPUT_DIR / job_id
        if job_out.exists():
            _shutil.rmtree(str(job_out), ignore_errors=True)
        _cleanup_job_temp_dir(job_id)
        # Also remove uploaded source video if it still exists
        if job.get("video_filename"):
            src_video = UPLOAD_DIR / f"{job_id}_{job['video_filename']}"
            if src_video.exists():
                src_video.unlink(missing_ok=True)
        if job_id in jobs:
            del jobs[job_id]
        database.delete_job(job_id, current_user["email"])
        return {"status": "deleted"}
    update_job(job_id, status="cancelled", cancelled=True, step_name="已取消")
    await _push(job_id, "cancelled", {})
    return {"status": "cancelled"}


@app.patch("/api/jobs/{job_id}")
async def rename_job(job_id: str, name: str = Form(...), current_user: dict = Depends(require_user)):
    """重命名任务"""
    get_job_or_404(job_id)
    name = name.strip()[:100]
    database.update_job_status(job_id, name=name)
    if job_id in jobs:
        jobs[job_id]["name"] = name
    return {"status": "ok", "name": name}


@app.websocket("/api/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in jobs:
        await websocket.send_json({"type": "error", "data": "任务不存在"})
        await websocket.close()
        return

    await websocket.send_json({"type": "status", "data": jobs[job_id]})

    if job_id not in job_ws_queues:
        job_ws_queues[job_id] = asyncio.Queue()
    queue = job_ws_queues[job_id]

    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                if msg["type"] == "video_clips":
                    update_job(job_id, video_clips_pct=msg["data"].get("pct", 0))
                elif msg["type"] == "video_write":
                    update_job(job_id, video_write_pct=msg["data"].get("pct", 0))
                await websocket.send_json(msg)
                if msg["type"] in ("done", "error", "cancelled"):
                    await websocket.send_json({"type": "status", "data": jobs.get(job_id, {})})
                    break
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                job = jobs.get(job_id, {})
                if job.get("status") in ("done", "error", "cancelled"):
                    await websocket.send_json({"type": "status", "data": job})
                    break
    except WebSocketDisconnect:
        pass


@app.get("/api/jobs/{job_id}/download/{filename}")
async def download_file(
    job_id: str,
    filename: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user),
):
    job = get_job_or_404(job_id)
    if job["status"] != "done":
        raise HTTPException(400, "任务尚未完成")

    # Markdown 导出仅会员可用
    if filename.lower().endswith(".md"):
        if not current_user:
            raise HTTPException(401, "导出 Markdown 需要先登录会员账号")
        owner = job.get("email") or job.get("created_by") or ""
        if owner and owner != current_user.get("email"):
            raise HTTPException(403, "仅任务创建者可导出该文稿")
        membership = _build_membership_status(
            current_user["email"],
            country_code=_detect_country_code(request),
        )
        if membership.get("tier") != "member":
            raise HTTPException(403, "Markdown 导出为会员专属功能")

    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path=str(file_path), filename=filename,
                        media_type="application/octet-stream")


@app.get("/api/jobs/{job_id}/stream/{filename}")
async def stream_file(job_id: str, filename: str, quality: str = "auto"):
    """Stream video with range request support for in-browser playback."""
    get_job_or_404(job_id)
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    stream_path = file_path
    q = _normalize_stream_quality(quality)
    applied_quality = "auto"
    if q != "auto":
        try:
            stream_path = await asyncio.to_thread(_ensure_stream_variant, job_id, file_path, q)
            applied_quality = q
        except Exception as e:
            print(f"⚠️ 生成 {q}p 流失败，回退原视频: {e}")
            stream_path = file_path

    headers = {
        "Cache-Control": "no-store",
        "X-Stream-Quality": applied_quality,
    }
    return FileResponse(path=str(stream_path), media_type="video/mp4", headers=headers)


@app.get("/api/jobs/{job_id}/preview/{filename}")
async def preview_file(job_id: str, filename: str):
    get_job_or_404(job_id)
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    if filename.endswith(".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return FileResponse(path=str(file_path))


@app.get("/api/jobs/{job_id}/export-notes-pdf")
async def export_notes_pdf(
    job_id: str,
    request: Request,
):
    job = get_job_or_404(job_id)
    owner = job.get("email") or job.get("created_by") or ""

    result = job.get("result") or {}
    if isinstance(result, str):
        result = json.loads(result) if result else {}
    md_file = result.get("markdown")
    if not md_file:
        raise HTTPException(404, "未找到学习文稿")

    md_path = OUTPUT_DIR / job_id / md_file
    if not md_path.exists():
        raise HTTPException(404, "文稿文件不存在")

    membership = _build_membership_status(owner, country_code=_detect_country_code(request)) if owner else {
        "tier": "free",
        "doc_watermark_enabled": True,
        "doc_watermark_text": "LinguaLearn",
    }
    if membership["tier"] == "member":
        wm_text = membership.get("doc_watermark_text") if membership.get("doc_watermark_enabled") else None
    else:
        wm_text = "LinguaLearn"

    pdf_name = f"{Path(md_file).stem}.pdf"
    pdf_path = OUTPUT_DIR / job_id / pdf_name
    content = md_path.read_text(encoding="utf-8")
    try:
        await asyncio.to_thread(_render_markdown_pdf, content, pdf_path, wm_text)
    except Exception as e:
        raise HTTPException(500, f"PDF 导出失败: {e}")

    return FileResponse(
        path=str(pdf_path),
        filename=pdf_name,
        media_type="application/pdf",
    )


@app.get("/api/jobs")
async def list_jobs(current_user: Optional[dict] = Depends(get_current_user)):
    if current_user:
        # 从数据库加载用户的 jobs
        db_jobs = database.get_user_jobs(current_user["email"], limit=50)
        # 用内存中的活跃 jobs 更新数据库的数据（获取最新的实时进度）
        for db_job in db_jobs:
            if db_job["id"] in jobs:
                db_job.update({
                    "status": jobs[db_job["id"]]["status"],
                    "step": jobs[db_job["id"]]["step"],
                    "step_name": jobs[db_job["id"]]["step_name"],
                    "video_clips_pct": jobs[db_job["id"]]["video_clips_pct"],
                    "video_write_pct": jobs[db_job["id"]]["video_write_pct"],
                    "error": jobs[db_job["id"]].get("error"),
                })
        return {"jobs": [_normalize_job(j) for j in db_jobs]}
    else:
        # 未登录只显示内存中的公开 jobs（最多50个）
        job_list = sorted(jobs.values(), key=lambda x: x.get("created_at", ""), reverse=True)
        return {"jobs": job_list[:50]}


# ── AI 讲师端点 ──────────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse as _StreamingResponse
try:
    from core.learning.ai_lesson import AILesson
    from core.learning.ai_podcast import AIPodcast
except ModuleNotFoundError:
    AILesson = None  # type: ignore[assignment]
    AIPodcast = None  # type: ignore[assignment]


def _get_lesson_for_job(job: dict) -> AILesson:
    """根据 job 的语言配置构造 AILesson 实例"""
    if AILesson is None:
        raise HTTPException(503, "AI Lesson 模块未安装（core.learning.ai_lesson 缺失）")
    return AILesson(
        source_lang=job.get("source_lang", "en"),
        target_lang=job.get("target_lang", "zh-Hans"),
    )


def _get_podcast_for_job(job: dict) -> AIPodcast:
    """根据 job 的语言配置构造 AIPodcast 实例"""
    if AIPodcast is None:
        raise HTTPException(503, "AI Podcast 模块未安装（core.learning.ai_podcast 缺失）")
    return AIPodcast(
        source_lang=job.get("source_lang", "en"),
        target_lang=job.get("target_lang", "zh-Hans"),
    )


def _load_job_tutor_files(job_id: str):
    """
    加载 job 的 MD 文件和 segments.json，返回 (md_content, segments, job_output_dir)。
    若文件缺失则抛出 HTTPException。
    """
    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, "Job 输出目录不存在")

    # 找 .md 文件
    md_files = list(job_dir.glob("*.md"))
    if not md_files:
        raise HTTPException(404, "未找到学习文稿文件")
    md_content = md_files[0].read_text(encoding="utf-8")

    # 找 segments.json
    seg_path = job_dir / "segments.json"
    if not seg_path.exists():
        raise HTTPException(404, "未找到 segments.json")
    segments = json.loads(seg_path.read_text(encoding="utf-8"))

    return md_content, segments, job_dir


def _script_tts_ready(script_path: Path) -> tuple[bool, int, int]:
    """检查脚本中 speak 项的 TTS 就绪情况。"""
    if not script_path.exists():
        return False, 0, 0
    try:
        script = json.loads(script_path.read_text(encoding="utf-8"))
    except Exception:
        return False, 0, 0
    speaks = [s for s in script if s.get("type") == "speak"]
    total = len(speaks)
    ready = sum(1 for s in speaks if s.get("tts_audio"))
    return ready == total, ready, total


def _tutor_progress_path(tutor_dir: Path) -> Path:
    return tutor_dir / "progress.json"


def _tutor_debug_log_path(tutor_dir: Path) -> Path:
    return tutor_dir / "debug.log"


def _read_tutor_progress(tutor_dir: Path) -> dict:
    p = _tutor_progress_path(tutor_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_tutor_progress(tutor_dir: Path, *, phase: str, message: str, **extra) -> dict:
    tutor_dir.mkdir(exist_ok=True)
    payload = {
        "phase": phase,
        "message": message,
        "updated_at": datetime.now().isoformat(),
        **extra,
    }
    _tutor_progress_path(tutor_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    line = f"[TutorProgress] phase={phase} message={message}"
    if extra:
        line += f" extra={extra}"
    print(line, flush=True)
    try:
        with _tutor_debug_log_path(tutor_dir).open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception:
        pass
    return payload


def _tutor_text_outputs(tutor_dir: Path) -> dict:
    names = [
        "lesson_manuscript.txt",
        "lesson_tts_manuscript.txt",
        "podcast_manuscript.txt",
        "podcast_tts_manuscript.txt",
    ]
    files = []
    for n in names:
        p = tutor_dir / n
        if p.exists():
            files.append(str(p))
    return {"manuscript_files": files}


@app.post("/api/jobs/{job_id}/tutor/generate")
async def tutor_generate(
    job_id: str,
    current_user: dict = Depends(require_user),
):
    """
    生成 AI 讲师课程脚本 + TTS 音频（异步后台任务）。
    立即返回 202，前端通过 GET /tutor/status 轮询或 SSE /tutor/stream 获取进度。
    """
    job = database.get_job(job_id)
    if not job or job.get("email") != current_user["email"]:
        raise HTTPException(404, "Job 不存在")
    if job.get("status") != "done":
        raise HTTPException(400, "视频尚未处理完成")

    tutor_dir = OUTPUT_DIR / job_id / "tutor"
    # 如果已经生成过，直接返回
    lesson_ok, _, _ = _script_tts_ready(tutor_dir / "tutor_script.json")
    podcast_ok, _, _ = _script_tts_ready(tutor_dir / "podcast_script.json")
    if lesson_ok and podcast_ok:
        return {"status": "already_done", "message": "课程脚本已存在，可直接使用"}

    # 标记生成中（写一个 lock 文件）
    tutor_dir.mkdir(exist_ok=True)
    lock_file = tutor_dir / "generating.lock"
    if lock_file.exists():
        prog = _read_tutor_progress(tutor_dir)
        stale = False
        try:
            updated_at = prog.get("updated_at")
            if updated_at:
                last = datetime.fromisoformat(updated_at)
                stale = (datetime.now() - last).total_seconds() > 20 * 60
            else:
                mtime = datetime.fromtimestamp(lock_file.stat().st_mtime)
                stale = (datetime.now() - mtime).total_seconds() > 20 * 60
        except Exception:
            stale = False
        if stale:
            print(f"[TutorProgress] stale lock detected for job={job_id}, auto-clearing", flush=True)
            lock_file.unlink(missing_ok=True)
        else:
            return {
                "status": "in_progress",
                "message": prog.get("message", "正在生成中，请稍候"),
                "progress": prog,
            }

    # 清理历史错误和进度
    for stale in ("error.txt", "progress.json", "debug.log"):
        (tutor_dir / stale).unlink(missing_ok=True)
    lock_file.write_text("generating")
    _write_tutor_progress(tutor_dir, phase="queued", message="任务已入队，准备开始生成", percent=0)

    async def _bg_generate():
        try:
            _write_tutor_progress(tutor_dir, phase="load_input", message="正在读取文稿和分句数据", percent=5)
            md_content, segments, job_dir = _load_job_tutor_files(job_id)
            audio_files = sorted(f.name for f in job_dir.glob("sq_*.mp3"))

            # Layer 1: 内容分析（AI课堂负责，随身听共用）
            lesson = _get_lesson_for_job(job)
            _write_tutor_progress(tutor_dir, phase="analyze_content", message="正在分析内容类型", percent=12)
            content_profile = lesson.analyze_content(md_content, segments)
            (tutor_dir / "content_profile.json").write_text(
                json.dumps(content_profile, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # AI课堂：规划 + 生成脚本
            _write_tutor_progress(tutor_dir, phase="plan_lesson", message="正在规划 AI讲课 脚本结构", percent=22)
            lesson_plan = lesson.plan_lesson(content_profile, segments)
            (tutor_dir / "lesson_plan.json").write_text(
                json.dumps(lesson_plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            _write_tutor_progress(tutor_dir, phase="write_lesson", message="正在生成 AI讲课 文稿", percent=38)
            lesson_script = lesson.write_lesson(content_profile, lesson_plan, audio_files)
            lesson_script = lesson.rewrite_tts(lesson_script)
            (tutor_dir / "tutor_script.json").write_text(
                json.dumps(lesson_script, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            lesson.write_manuscript(lesson_script, tutor_dir)

            # AI随身听：规划 + 生成脚本（复用 content_profile）
            podcast = _get_podcast_for_job(job)
            _write_tutor_progress(tutor_dir, phase="plan_podcast", message="正在规划 AI随身听 脚本结构", percent=48)
            podcast_plan = podcast.plan_podcast(content_profile, segments)
            (tutor_dir / "podcast_plan.json").write_text(
                json.dumps(podcast_plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            _write_tutor_progress(tutor_dir, phase="write_podcast", message="正在生成 AI随身听 文稿", percent=58)
            podcast_script = podcast.write_podcast(content_profile, podcast_plan, audio_files)
            podcast_script = podcast.rewrite_tts(podcast_script)
            (tutor_dir / "podcast_script.json").write_text(
                json.dumps(podcast_script, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            podcast.write_manuscript(podcast_script, tutor_dir)

            # TTS 合成
            _write_tutor_progress(tutor_dir, phase="tts_lesson", message="正在合成 AI讲课 语音", percent=68)
            lesson.synthesize_tts(
                lesson_script, tutor_dir,
                script_filename="tutor_script.json",
                filename_prefix="tts",
                flush_each=True,
            )

            _write_tutor_progress(tutor_dir, phase="tts_podcast", message="正在合成 AI随身听 语音", percent=84)
            podcast.synthesize_tts(
                podcast_script, tutor_dir,
                filename_prefix="pod_tts",
                flush_each=True,
            )

            _write_tutor_progress(
                tutor_dir,
                phase="done",
                message="AI讲课与AI随身听已生成完成",
                percent=100,
                **_tutor_text_outputs(tutor_dir),
            )
        except Exception as e:
            tb = traceback.format_exc()
            (tutor_dir / "error.txt").write_text(tb, encoding="utf-8")
            print(f"[TutorProgress] job={job_id} exception:\n{tb}", flush=True)
            _write_tutor_progress(
                tutor_dir,
                phase="error",
                message=f"生成失败：{e}",
                percent=100,
                error=str(e),
            )
        finally:
            lock_file.unlink(missing_ok=True)

    asyncio.create_task(_bg_generate())
    return {"status": "started", "message": "课程生成已启动"}


@app.get("/api/jobs/{job_id}/tutor/status")
async def tutor_status(
    job_id: str,
    current_user: dict = Depends(require_user),
):
    """查询 AI 讲师生成状态"""
    job = database.get_job(job_id)
    if not job or job.get("email") != current_user["email"]:
        raise HTTPException(404, "Job 不存在")

    tutor_dir = OUTPUT_DIR / job_id / "tutor"
    progress = _read_tutor_progress(tutor_dir)
    txt_outputs = _tutor_text_outputs(tutor_dir)
    lesson_ready, lesson_speak_ready, lesson_speak_total = _script_tts_ready(tutor_dir / "tutor_script.json")
    podcast_ready, podcast_speak_ready, podcast_speak_total = _script_tts_ready(tutor_dir / "podcast_script.json")
    if lesson_ready and podcast_ready:
        return {
            "status": "done",
            "tts_ready": True,
            "progress": progress,
            "lesson": {
                "ready": True,
                "speak_ready": lesson_speak_ready,
                "speak_total": lesson_speak_total,
            },
            "podcast": {
                "ready": True,
                "speak_ready": podcast_speak_ready,
                "speak_total": podcast_speak_total,
            },
            **txt_outputs,
        }
    if (tutor_dir / "generating.lock").exists():
        return {
            "status": "in_progress",
            "progress": progress,
            "lesson": {
                "ready": lesson_ready,
                "speak_ready": lesson_speak_ready,
                "speak_total": lesson_speak_total,
            },
            "podcast": {
                "ready": podcast_ready,
                "speak_ready": podcast_speak_ready,
                "speak_total": podcast_speak_total,
            },
            **txt_outputs,
        }
    if (tutor_dir / "error.txt").exists():
        err = (tutor_dir / "error.txt").read_text(encoding="utf-8")
        return {
            "status": "error",
            "message": err,
            "progress": progress,
            **txt_outputs,
        }
    if lesson_ready or podcast_ready:
        return {
            "status": "in_progress",
            "progress": progress,
            "lesson": {
                "ready": lesson_ready,
                "speak_ready": lesson_speak_ready,
                "speak_total": lesson_speak_total,
            },
            "podcast": {
                "ready": podcast_ready,
                "speak_ready": podcast_speak_ready,
                "speak_total": podcast_speak_total,
            },
            **txt_outputs,
        }
    return {"status": "not_started", "progress": progress, **txt_outputs}


@app.get("/api/jobs/{job_id}/tutor/script")
async def tutor_get_script(
    job_id: str,
    current_user: dict = Depends(require_user),
):
    """获取已生成的课程脚本 JSON"""
    job = database.get_job(job_id)
    if not job or job.get("email") != current_user["email"]:
        raise HTTPException(404, "Job 不存在")

    script_path = OUTPUT_DIR / job_id / "tutor" / "tutor_script.json"
    if not script_path.exists():
        raise HTTPException(404, "课程脚本尚未生成")

    script = json.loads(script_path.read_text(encoding="utf-8"))
    return {"script": script}


@app.get("/api/jobs/{job_id}/tutor/audio/{filename}")
async def tutor_audio(
    job_id: str,
    filename: str,
    current_user: dict = Depends(require_user),
):
    """
    提供 TTS 合成的音频文件（tts_xxxx.mp3）。
    仅允许 tutor/ 目录下的 tts_*.mp3 文件。
    """
    job = database.get_job(job_id)
    if not job or job.get("email") != current_user["email"]:
        raise HTTPException(404, "Job 不存在")

    # 安全校验：只允许 tts_ 或 pod_tts_ 前缀的 mp3
    if not ((filename.startswith("tts_") or filename.startswith("pod_tts_")) and filename.endswith(".mp3")):
        raise HTTPException(400, "非法文件名")

    audio_path = OUTPUT_DIR / job_id / "tutor" / filename
    if not audio_path.exists():
        raise HTTPException(404, "音频文件不存在")

    return FileResponse(str(audio_path), media_type="audio/mpeg")


@app.get("/api/jobs/{job_id}/tutor/podcast")
async def tutor_podcast(
    job_id: str,
    current_user: dict = Depends(require_user),
):
    """
    生成并下载完整 Podcast MP3（TTS + 原音拼接）。
    如已生成则直接返回，否则实时生成（可能较慢）。
    """
    job = database.get_job(job_id)
    if not job or job.get("email") != current_user["email"]:
        raise HTTPException(404, "Job 不存在")

    tutor_dir = OUTPUT_DIR / job_id / "tutor"
    podcast_path = tutor_dir / "podcast.mp3"

    if not podcast_path.exists():
        podcast_script_path = tutor_dir / "podcast_script.json"
        lesson_script_path = tutor_dir / "tutor_script.json"
        script_path = podcast_script_path if podcast_script_path.exists() else lesson_script_path
        if not script_path.exists():
            raise HTTPException(400, "请先生成课程脚本")
        script = json.loads(script_path.read_text(encoding="utf-8"))

        # 检查 TTS 是否就绪
        missing_tts = [
            s for s in script
            if s["type"] == "speak" and not s.get("tts_audio")
        ]
        if missing_tts:
            raise HTTPException(400, "TTS 音频尚未全部合成完成")

        podcast_inst = _get_podcast_for_job(job)
        podcast_inst.build_podcast(script, OUTPUT_DIR / job_id, podcast_path)

    return FileResponse(
        str(podcast_path),
        media_type="audio/mpeg",
        filename=f"{job.get('name', job_id)}_讲课.mp3",
    )


# ===== AI Tutor 子模块入口（单服务统一入口）=====
app.add_api_websocket_route("/ws/tutor", ai_tutor_tutor_session_legacy)
app.add_api_websocket_route("/ai-tutor/ws/{learner_id}", ai_tutor_interactive_tutor_session)
app.add_api_route("/ai-tutor/jobs", ai_tutor_list_jobs, methods=["GET"])
app.add_api_route("/ai-tutor/jobs/{job_id}/content", ai_tutor_get_job_content, methods=["GET"])
app.add_api_route(
    "/ai-tutor/learner/{learner_id}/memory",
    ai_tutor_get_learner_memory,
    methods=["GET"],
)
app.add_api_route("/ai-tutor/learner", ai_tutor_create_or_update_learner, methods=["POST"])


# 头像目录单独挂载，避免被前端构建覆盖
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatars")
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    import os as _os
    _port = int(_os.getenv("PORT", 8080))
    print("🚀 LinguaLearn 服务启动中...")
    print(f"📱 打开浏览器访问: http://localhost:{_port}")
    uvicorn.run(app, host="0.0.0.0", port=_port, reload=False)
