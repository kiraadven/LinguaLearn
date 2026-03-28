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
import hmac
import random
import smtplib
import base64
import subprocess
import html
from urllib.parse import urlencode, quote_plus
try:
    import resend
except ImportError:
    resend = None
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import redirect_stdout
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core'))

import config
import database
import markdown as md_lib

app = FastAPI(title="LinguaLearn API", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===== 目录 =====
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path(config.OUTPUT_DIR)
TEMP_DIR   = Path(config.TEMP_DIR)
STATIC_DIR = Path("static")

for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, STATIC_DIR]:
    d.mkdir(exist_ok=True)

# ===== 内存存储 =====
jobs:          Dict[str, dict] = {}
job_ws_queues: Dict[str, asyncio.Queue] = {}

# 用户和验证码现在存储在 SQLite 数据库中（见 database.py）

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

_FREE_DAILY_VIDEO_LIMIT = 5
_FREE_MAX_VIDEO_SECONDS = 5 * 60
_MEMBER_MAX_VIDEO_SECONDS = 30 * 60

_DEFAULT_VIDEO_WATERMARK = {
    "text": "LinguaLearn",
    "position": {"x": 0.348, "y": 0.352},   # x34.8, y35.2 (%)
    "size": {"w": 0.18, "h": 0.06},         # w18, h6 (%)
    "rotation": -30,
    "opacity": 0.35,                         # 35%
    "font_size": 90,
}

_MEMBERSHIP_PLAN_SETS = {
    "cn": [
        {"code": "cn_day", "label": "1天体验价", "days": 1, "price": 3.0, "currency": "CNY", "period": "day", "auto_renew": False, "trial_once": True},
        {"code": "cn_week", "label": "连续包周", "days": 7, "price": 8.0, "currency": "CNY", "period": "week", "auto_renew": True, "trial_once": False},
        {"code": "cn_month", "label": "连续包月", "days": 30, "price": 25.0, "currency": "CNY", "period": "month", "auto_renew": True, "trial_once": False},
        {"code": "cn_year", "label": "连续包年", "days": 365, "price": 260.0, "currency": "CNY", "period": "year", "auto_renew": True, "trial_once": False},
    ],
    "intl": [
        {"code": "intl_day", "label": "1-day Trial", "days": 1, "price": 0.8, "currency": "USD", "period": "day", "auto_renew": False, "trial_once": True},
        {"code": "intl_week", "label": "Weekly", "days": 7, "price": 2.0, "currency": "USD", "period": "week", "auto_renew": True, "trial_once": False},
        {"code": "intl_month", "label": "Monthly", "days": 30, "price": 7.0, "currency": "USD", "period": "month", "auto_renew": True, "trial_once": False},
        {"code": "intl_year", "label": "Yearly", "days": 365, "price": 75.0, "currency": "USD", "period": "year", "auto_renew": True, "trial_once": False},
    ],
}
_PLAN_BY_CODE = {p["code"]: p for plans in _MEMBERSHIP_PLAN_SETS.values() for p in plans}

_FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg") else "ffmpeg"
_FFPROBE_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe" if os.path.exists("/opt/homebrew/opt/ffmpeg-full/bin/ffprobe") else "ffprobe"


def _country_bucket(country_code: str) -> str:
    code = (country_code or "").strip().upper()
    return "cn" if code in {"CN", "CHN", "CHINA", "中国"} else "intl"


def _detect_country_code(request: Optional[Request], fallback: str = "CN") -> str:
    if not request:
        return fallback
    # Common proxy/CDN headers
    for key in ("cf-ipcountry", "x-country-code", "x-vercel-ip-country"):
        v = request.headers.get(key)
        if v:
            return v.strip().upper()
    return fallback


def _get_plan_catalog(country_code: str, trial_used: bool = False) -> list:
    bucket = _country_bucket(country_code)
    plans = []
    for p in _MEMBERSHIP_PLAN_SETS[bucket]:
        item = dict(p)
        item["available"] = not (item.get("trial_once") and trial_used)
        plans.append(item)
    return plans


def _membership_limits(tier: str) -> dict:
    is_member = tier == "member"
    return {
        "daily_video_limit": None if is_member else _FREE_DAILY_VIDEO_LIMIT,
        "max_video_seconds": _MEMBER_MAX_VIDEO_SECONDS if is_member else _FREE_MAX_VIDEO_SECONDS,
        "can_remove_default_watermark": is_member,
        "can_customize_video_watermark": is_member,
        "can_customize_doc_watermark": is_member,
        "premium_badge": is_member,
    }


def _build_membership_status(email: str, country_code: str = "CN") -> dict:
    rec = database.get_user_membership(email) or {}
    tier = "member" if (rec.get("tier") == "member" and rec.get("status") == "active") else "free"
    limits = _membership_limits(tier)
    used_today = database.get_today_usage(email)
    daily_limit = limits["daily_video_limit"]
    remaining = None if daily_limit is None else max(0, daily_limit - used_today)
    trial_used = bool(rec.get("trial_used", 0))
    plans = _get_plan_catalog(country_code or rec.get("country_code") or "CN", trial_used)
    return {
        "tier": tier,
        "status": rec.get("status", "inactive"),
        "provider": rec.get("provider"),
        "plan_code": rec.get("plan_code"),
        "plan_name": rec.get("plan_name"),
        "started_at": rec.get("started_at"),
        "expires_at": rec.get("expires_at"),
        "auto_renew": bool(rec.get("auto_renew", 0)),
        "trial_used": trial_used,
        "badge_unlocked": bool(rec.get("badge_unlocked", 0)),
        "doc_watermark_text": rec.get("doc_watermark_text") or "LinguaLearn",
        "doc_watermark_enabled": bool(rec.get("doc_watermark_enabled", 1)),
        "usage": {
            "day": datetime.now().strftime('%Y-%m-%d'),
            "videos_generated_today": used_today,
            "remaining_today": remaining,
        },
        "limits": limits,
        "plans": plans,
        "premium_logo": "/premium-badge.svg",
    }


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
    return v if v in {"auto", "1080", "720", "360"} else "auto"


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
    variant_path = out_dir / f"{source_path.stem}_{target_h}p.mp4"

    if variant_path.exists():
        try:
            if variant_path.stat().st_mtime >= source_path.stat().st_mtime:
                return variant_path
        except Exception:
            pass

    tmp_path = out_dir / f"{source_path.stem}_{target_h}p_{uuid.uuid4().hex[:8]}.tmp.mp4"
    vf = f"scale=-2:{target_h}:force_original_aspect_ratio=decrease"
    try:
        subprocess.run(
            [
                _FFMPEG_BIN, "-y",
                "-i", str(source_path),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
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

            from core.audio_transcriber import AudioTranscriber
            from core.sentence_splitter  import SentenceSplitter
            from core.word_analyzer      import WordAnalyzer
            from core.video_processor    import VideoProcessor
            from core.markdown_exporter  import MarkdownExporter

            job_out = OUTPUT_DIR / job_id
            job_out.mkdir(exist_ok=True)
            config.OUTPUT_DIR = str(job_out)
            config.TEMP_DIR   = str(TEMP_DIR / job_id)
            Path(config.TEMP_DIR).mkdir(exist_ok=True)

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
            print(f"✂️ 句子分割完成，共 {len(sentences)} 句")
            print("⏰ 开始对齐时间戳...")
            timestamps = transcriber.align_sentences_to_timestamps(audio_path, sentences, output_name)
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

                video_cursor = 0.0
                segs_with_text = []
                for i, (seg, sd) in enumerate(zip(segments_info, sentences_data)):
                    s_start = seg["start"]; s_end = seg["end"]
                    s_next = segments_info[i+1]["start"] if i+1 < len(segments_info) else s_end
                    seg_video_start = video_cursor  # 此句在生成视频中的起始
                    first_overlay_start = None      # 第一个有叠加内容（字幕/词框）的 part 起始
                    for j, part in enumerate(_parts_cfg):
                        spd = float(part.get("speed", 1.0))
                        is_slow = (spd != 1.0) or part.get("slow", False)
                        if part.get("slow", False) and spd == 1.0:
                            spd = float(getattr(config, "SPEED_SLOW", 0.75))
                        rpt = max(1, int(part.get("repeat", 1)))
                        raw_dur = (s_end - s_start) if is_slow else (s_next - s_start)
                        clip_dur = raw_dur / spd
                        has_overlay = (
                            part.get("show_subtitle", False) or
                            part.get("show_wordbox", False) or
                            part.get("show_exprbox", False)
                        )
                        if has_overlay and first_overlay_start is None:
                            first_overlay_start = video_cursor
                        video_cursor += clip_dur * rpt
                   
                    jump_target = seg_video_start
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
            sys.stdout = old_stdout

    print(f"[process_video_job] 🚀 Coroutine 启动, job={job_id[:8]}, 即将 run_in_executor")
    await asyncio.get_event_loop().run_in_executor(None, run_in_thread)
    print(f"[process_video_job] 🏁 run_in_executor 完成, job={job_id[:8]}")


# ============================================================
# AUTH routes
# ============================================================

@app.post("/api/auth/send-code")
async def send_code(email: str = Form(...)):
    """发送邮箱验证码（注册时调用）"""
    email = email.strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise HTTPException(400, "邮箱格式不正确")
    if database.user_exists(email):
        raise HTTPException(400, "该邮箱已注册，请直接登录")

    code = _gen_code()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    database.save_verification_code(email, code, expires_at)

    sent = _send_code_email(email, code)
    if sent:
        return {"status": "ok"}
    else:
        # Dev mode – return code in response
        print(f"[DEV] Verification code for {email}: {code}")
        return {"status": "ok", "dev_mode": True, "dev_code": code}


@app.post("/api/auth/send-sms-code")
async def send_sms_code(phone: str = Form(...)):
    """发送短信验证码（注册/登陆时调用）"""
    phone = phone.strip()
    if not phone or len(phone) < 10:
        raise HTTPException(400, "手机号格式不正确")

    code = _gen_code()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    database.save_verification_code(phone, code, expires_at)

    sent = _send_sms(phone, code)
    if sent:
        return {"status": "ok"}
    else:
        # Dev mode – return code in response
        print(f"[DEV] Verification code for {phone}: {code}")
        return {"status": "ok", "dev_mode": True, "dev_code": code}


@app.post("/api/auth/register")
async def register(
    email:    str = Form(...),
    password: str = Form(...),
    name:     str = Form(""),
    code:     str = Form(...),
    phone:    str = Form(""),
):
    """注册用户（邮箱或手机号）"""
    code = code.strip()

    # 手机号注册
    if phone:
        phone = phone.strip()
        if not phone or len(phone) < 10:
            raise HTTPException(400, "手机号格式不正确")
        if len(password) < 6:
            raise HTTPException(400, "密码至少6位")
        if database.user_exists_by_phone(phone):
            raise HTTPException(400, "该手机号已注册")

        # DEV: "000000" bypasses code check; remove when done
        if code != "000000":
            pending = database.get_verification_code(phone)
            if not pending:
                raise HTTPException(400, "请先获取验证码")
            if datetime.now() > datetime.fromisoformat(pending["expires_at"]):
                database.delete_verification_code(phone)
                raise HTTPException(400, "验证码已过期，请重新获取")
            if pending["code"] != code:
                raise HTTPException(400, "验证码错误")

        database.delete_verification_code(phone)
        # 使用手机号作为邮箱前缀（phone@lingualearn.local）
        email_generated = f"{phone}@lingualearn.local"
        user = database.create_user_with_phone(email_generated, _hash(password), phone, name.strip() or phone)
        if not user:
            raise HTTPException(400, "手机号已注册")

        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        database.save_token(token, email_generated, expires_at)

        return {"token": token, "name": user["name"], "phone": phone}

    # 邮箱注册（原逻辑）
    email = email.strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise HTTPException(400, "邮箱格式不正确")
    if len(password) < 6:
        raise HTTPException(400, "密码至少6位")
    if database.user_exists(email):
        raise HTTPException(400, "该邮箱已注册")

    # DEV: "000000" bypasses code check; remove when done
    if code != "000000":
        pending = database.get_verification_code(email)
        if not pending:
            raise HTTPException(400, "请先获取验证码")
        if datetime.now() > datetime.fromisoformat(pending["expires_at"]):
            database.delete_verification_code(email)
            raise HTTPException(400, "验证码已过期，请重新获取")
        if pending["code"] != code:
            raise HTTPException(400, "验证码错误")

    database.delete_verification_code(email)
    database.create_user(email, _hash(password), name.strip())

    token = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    database.save_token(token, email, expires_at)

    user = database.get_user(email)
    return {"token": token, "name": user["name"], "email": email, "avatar_url": user.get("avatar_url")}


@app.post("/api/auth/login")
async def login(
    login_type: str = Form("email_password"),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    code: str = Form(""),
):
    """登陆（支持三种方式）
    - login_type=email_password: email + password
    - login_type=phone_password: phone + password
    - login_type=phone_code: phone + code（验证码登陆）
    """

    if login_type == "email_password":
        # 邮箱+密码登陆
        email = email.strip().lower()
        if not email:
            raise HTTPException(400, "邮箱不能为空")
        user = database.get_user(email)
        if not user or user["password_hash"] != _hash(password):
            raise HTTPException(401, "邮箱或密码错误")
        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        database.save_token(token, email, expires_at)
        return {"token": token, "name": user["name"], "email": email, "avatar_url": user.get("avatar_url")}

    elif login_type == "phone_password":
        # 手机号+密码登陆
        phone = phone.strip()
        if not phone:
            raise HTTPException(400, "手机号不能为空")
        user = database.get_user_by_phone(phone)
        if not user or user["password_hash"] != _hash(password):
            raise HTTPException(401, "手机号或密码错误")
        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        database.save_token(token, user["email"], expires_at)
        return {"token": token, "name": user["name"], "phone": phone, "email": user["email"], "avatar_url": user.get("avatar_url")}

    elif login_type == "phone_code":
        # 手机号+验证码登陆（用户不存在则自动注册）
        phone = phone.strip()
        code = code.strip()
        if not phone or not code:
            raise HTTPException(400, "手机号和验证码不能为空")

        # DEV: "000000" bypasses code check; remove when done
        if code != "000000":
            pending = database.get_verification_code(phone)
            if not pending:
                raise HTTPException(400, "请先获取验证码")
            if datetime.now() > datetime.fromisoformat(pending["expires_at"]):
                database.delete_verification_code(phone)
                raise HTTPException(400, "验证码已过期，请重新获取")
            if pending["code"] != code:
                raise HTTPException(400, "验证码错误")

        database.delete_verification_code(phone)

        # 检查用户是否存在
        user = database.get_user_by_phone(phone)
        if not user:
            # 自动注册新用户（使用手机号作为名称）
            email_generated = f"{phone}@lingualearn.local"
            user = database.create_user_with_phone(
                email_generated,
                _hash(phone),  # 密码设为手机号（无登陆用）
                phone,
                phone
            )
            if not user:
                raise HTTPException(400, "注册失败")

        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        database.save_token(token, user["email"], expires_at)
        return {"token": token, "name": user["name"], "phone": phone}

    else:
        raise HTTPException(400, "login_type 不支持")


@app.get("/api/auth/me")
async def get_me(request: Request, current_user: Optional[dict] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(401, "未登录")
    country_code = _detect_country_code(request)
    membership = _build_membership_status(current_user["email"], country_code=country_code)
    return {
        "email": current_user["email"],
        "name": current_user["name"],
        "avatar_url": current_user.get("avatar_url"),
        "created_at": current_user["created_at"],
        "membership": membership,
    }


@app.post("/api/auth/change-password")
async def change_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    current_user: dict = Depends(require_user),
):
    if current_user["password_hash"] != _hash(old_password):
        raise HTTPException(400, "原密码错误")
    if len(new_password) < 6:
        raise HTTPException(400, "新密码至少6位")
    database.update_user_password(current_user["email"], _hash(new_password))
    return {"status": "ok"}


@app.post("/api/auth/send-email-code")
async def send_email_code(email: str = Form(...)):
    """发送邮件验证码到目标邮箱"""
    if not email or "@" not in email:
        raise HTTPException(400, "邮箱格式错误")

    code = f"{random.randint(100000, 999999)}"
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()

    database.save_verification_code(email, code, expires_at)

    # 使用 Resend 发送，fallback 到 SMTP
    if config.RESEND_API_KEY and resend:
        try:
            resend.api_key = config.RESEND_API_KEY
            r = resend.Emails.send({
                "from": "noreply@lingualearn.com",
                "to": email,
                "subject": "LinguaLearn 邮箱验证码",
                "html": f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#0a0a12;color:#e2e8f0;border-radius:16px;">
      <h1 style="font-size:24px;font-weight:800;background:linear-gradient(135deg,#6c63ff,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;">LinguaLearn</h1>
      <h2 style="font-size:14px;color:#64748b;font-weight:500;margin:0 0 24px;">邮箱验证</h2>
      <p style="font-size:32px;font-weight:800;color:#fff;margin:32px 0;letter-spacing:8px;text-align:center;">{code}</p>
      <p style="color:#64748b;font-size:13px;margin:0;">验证码 <strong>10 分钟</strong>内有效。如非本人操作，请忽略此邮件。</p>
    </div>
                """
            })
            if r.get("id"):
                return {"status": "ok", "message": "验证码已发送", "code": code}  # DEV: remove "code" when done
        except Exception as e:
            print(f"[Resend Error] {type(e).__name__}: {e}")
            # Fallback to SMTP
            pass

    # SMTP fallback
    sent = _send_email(email, "【LinguaLearn】邮箱验证码", f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#0a0a12;color:#e2e8f0;border-radius:16px;">
      <h1 style="font-size:24px;font-weight:800;background:linear-gradient(135deg,#6c63ff,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;">LinguaLearn</h1>
      <h2 style="font-size:14px;color:#64748b;font-weight:500;margin:0 0 24px;">邮箱验证</h2>
      <p style="font-size:32px;font-weight:800;color:#fff;margin:32px 0;letter-spacing:8px;text-align:center;">{code}</p>
      <p style="color:#64748b;font-size:13px;margin:0;">验证码 <strong>10 分钟</strong>内有效。如非本人操作，请忽略此邮件。</p>
    </div>
    """)
    # DEV: always return code for testing; remove "code" key when done
    print(f"[DEV] Verification code for {email}: {code}")
    return {"status": "ok", "message": "验证码已发送", "code": code}


@app.post("/api/auth/bind-email")
async def bind_email(
    email: str = Form(...),
    code: str = Form(...),
    current_user: dict = Depends(require_user),
):
    """验证邮箱验证码并绑定邮箱"""
    if not email or "@" not in email:
        raise HTTPException(400, "邮箱格式错误")

    # DEV: "000000" bypasses code check; remove when done
    if code != "000000":
        vc = database.verify_code(email, code)
        if not vc:
            raise HTTPException(400, "验证码错误或已过期")

    # 更新用户邮箱
    if not database.bind_email(current_user["email"], email):
        raise HTTPException(400, "邮箱已被其他用户使用")

    return {"status": "ok", "message": "邮箱已绑定", "email": email}


@app.post("/api/users/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_user),
):
    """上传用户头像"""
    if not file.filename:
        raise HTTPException(400, "未提供文件")

    # 验证文件类型
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "仅支持 JPG/PNG/WebP 格式")

    try:
        # 创建 avatars 目录（使用 uploads/ 而非 static/，避免前端构建时覆盖）
        avatar_dir = Path("uploads/avatars")
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # 确定文件扩展名
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp"
        }
        ext = ext_map.get(file.content_type, "jpg")

        # 保存文件
        filename = f"{current_user['email'].replace('@', '_')}.{ext}"
        filepath = avatar_dir / filename
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        # 更新数据库
        avatar_url = f"/avatars/{filename}"
        if not database.update_user_avatar(current_user["email"], avatar_url):
            raise HTTPException(500, "头像保存失败")

        return {"status": "ok", "avatar_url": avatar_url}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"头像上传失败: {e}")


# ============================================================
# MEMBERSHIP routes
# ============================================================

@app.get("/api/membership/status")
async def membership_status(request: Request, current_user: dict = Depends(require_user)):
    country_code = _detect_country_code(request)
    return _build_membership_status(current_user["email"], country_code=country_code)


@app.post("/api/membership/preferences")
async def update_membership_preferences(
    request: Request,
    current_user: dict = Depends(require_user),
):
    body = await request.json()
    rec = _build_membership_status(current_user["email"], country_code=_detect_country_code(request))
    if rec["tier"] != "member":
        raise HTTPException(403, "仅会员可自定义文稿水印")

    enabled = bool(body.get("doc_watermark_enabled", True))
    text = str(body.get("doc_watermark_text", "LinguaLearn")).strip()[:64]
    if enabled and not text:
        text = "LinguaLearn"
    database.update_user_membership(
        current_user["email"],
        doc_watermark_enabled=1 if enabled else 0,
        doc_watermark_text=text,
    )
    return _build_membership_status(current_user["email"], country_code=_detect_country_code(request))


@app.post("/api/membership/checkout/stripe")
async def create_stripe_checkout(
    request: Request,
    current_user: dict = Depends(require_user),
):
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(400, "未配置 STRIPE_SECRET_KEY")

    body = await request.json()
    plan_code = str(body.get("plan_code", "")).strip()
    plan = _PLAN_BY_CODE.get(plan_code)
    if not plan:
        raise HTTPException(400, "套餐不存在")

    country_code = (_detect_country_code(request) or "CN").upper()
    rec = _build_membership_status(current_user["email"], country_code=country_code)
    if plan.get("trial_once") and rec.get("trial_used"):
        raise HTTPException(400, "1天体验价每个账号仅可使用一次")

    price_id = _get_stripe_price_id(plan_code)
    if not price_id:
        raise HTTPException(400, f"套餐 {plan_code} 尚未配置 Stripe Price ID")

    order_id = f"ord_{uuid.uuid4().hex[:24]}"
    success_url = body.get("success_url") or f"{config.APP_BASE_URL}/#/profile?membership=success"
    cancel_url = body.get("cancel_url") or f"{config.APP_BASE_URL}/#/profile?membership=cancel"

    mode = "payment" if plan.get("period") == "day" else "subscription"
    payload = [
        ("mode", mode),
        ("line_items[0][price]", price_id),
        ("line_items[0][quantity]", "1"),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("client_reference_id", current_user["email"]),
        ("metadata[order_id]", order_id),
        ("metadata[email]", current_user["email"]),
        ("metadata[plan_code]", plan_code),
        ("metadata[country_code]", country_code),
    ]
    if mode == "subscription":
        payload.extend([
            ("subscription_data[metadata][order_id]", order_id),
            ("subscription_data[metadata][plan_code]", plan_code),
            ("subscription_data[metadata][email]", current_user["email"]),
        ])

    resp = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        data=payload,
        auth=(config.STRIPE_SECRET_KEY, ""),
        timeout=20,
    )
    if resp.status_code >= 400:
        raise HTTPException(400, f"Stripe 创建结算失败: {resp.text[:300]}")
    sd = resp.json()
    checkout_url = sd.get("url")
    if not checkout_url:
        raise HTTPException(400, "Stripe 未返回支付链接")

    database.save_membership_order(
        order_id=order_id,
        email=current_user["email"],
        provider="stripe",
        plan_code=plan_code,
        currency=plan["currency"],
        amount=plan["price"],
        status="pending",
        checkout_url=checkout_url,
        subscription_id=sd.get("subscription"),
        payload_json=json.dumps(sd, ensure_ascii=False),
    )
    return {
        "order_id": order_id,
        "provider": "stripe",
        "checkout_url": checkout_url,
        "session_id": sd.get("id"),
    }


def _verify_stripe_signature(raw_body: bytes, sig_header: str, secret: str) -> bool:
    if not secret:
        return True
    try:
        pieces = {}
        for part in (sig_header or "").split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                pieces.setdefault(k.strip(), []).append(v.strip())
        ts = pieces.get("t", [None])[0]
        sigs = pieces.get("v1", [])
        if not ts or not sigs:
            return False
        signed_payload = f"{ts}.{raw_body.decode('utf-8')}"
        expected = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, s) for s in sigs)
    except Exception:
        return False


@app.post("/api/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not _verify_stripe_signature(raw, sig, config.STRIPE_WEBHOOK_SECRET):
        raise HTTPException(400, "Stripe 签名校验失败")

    event = json.loads(raw.decode("utf-8"))
    typ = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if typ == "checkout.session.completed":
        meta = obj.get("metadata", {}) or {}
        order_id = meta.get("order_id")
        order = database.get_membership_order(order_id) if order_id else None
        if order:
            sub_id = obj.get("subscription") or order.get("subscription_id")
            database.update_membership_order(
                order_id,
                status="paid",
                subscription_id=sub_id,
                payload_json=json.dumps(obj, ensure_ascii=False),
            )
            _activate_membership_for_user(
                email=order["email"],
                plan_code=order["plan_code"],
                provider="stripe",
                subscription_id=sub_id,
                customer_id=obj.get("customer"),
                country_code=(meta.get("country_code") or "CN"),
            )

    elif typ == "invoice.paid":
        sub_id = obj.get("subscription")
        if sub_id:
            order = database.get_membership_order_by_subscription("stripe", sub_id)
            if order:
                database.update_membership_order(
                    order["order_id"],
                    status="paid",
                    payload_json=json.dumps(obj, ensure_ascii=False),
                )
                _activate_membership_for_user(
                    email=order["email"],
                    plan_code=order["plan_code"],
                    provider="stripe",
                    subscription_id=sub_id,
                    customer_id=obj.get("customer"),
                    country_code=(database.get_user_membership(order["email"]) or {}).get("country_code", "CN"),
                )

    elif typ in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub_id = obj.get("id")
        if sub_id:
            order = database.get_membership_order_by_subscription("stripe", sub_id)
            if order:
                is_cancelled = typ == "customer.subscription.deleted" or obj.get("cancel_at_period_end")
                if is_cancelled:
                    database.update_user_membership(order["email"], auto_renew=0, status="cancelled")

    return {"received": True}


@app.post("/api/membership/checkout/alipay")
async def create_alipay_checkout(
    request: Request,
    current_user: dict = Depends(require_user),
):
    body = await request.json()
    plan_code = str(body.get("plan_code", "")).strip()
    plan = _PLAN_BY_CODE.get(plan_code)
    if not plan:
        raise HTTPException(400, "套餐不存在")

    rec = _build_membership_status(current_user["email"], country_code=_detect_country_code(request))
    if plan.get("trial_once") and rec.get("trial_used"):
        raise HTTPException(400, "1天体验价每个账号仅可使用一次")

    if not (config.ALIPAY_APP_ID and config.ALIPAY_PRIVATE_KEY and config.ALIPAY_PUBLIC_KEY):
        raise HTTPException(400, "未配置支付宝签约参数（ALIPAY_APP_ID/ALIPAY_PRIVATE_KEY/ALIPAY_PUBLIC_KEY）")

    try:
        from alipay import AliPay
    except Exception:
        raise HTTPException(500, "请先安装 python-alipay-sdk 才能启用支付宝支付")

    order_id = f"ali_{uuid.uuid4().hex[:24]}"
    alipay = AliPay(
        appid=config.ALIPAY_APP_ID,
        app_notify_url=config.ALIPAY_NOTIFY_URL or None,
        app_private_key_string=config.ALIPAY_PRIVATE_KEY,
        alipay_public_key_string=config.ALIPAY_PUBLIC_KEY,
        sign_type="RSA2",
        debug=("sandbox" in (config.ALIPAY_GATEWAY or "")),
    )

    # 支付宝“自动续费签约”在线上一般需要代扣签约流程。
    # 这里先提供标准支付能力，并保留 auto_renew 标志由 webhook + 业务续签接入。
    pay_str = alipay.api_alipay_trade_wap_pay(
        out_trade_no=order_id,
        total_amount=str(plan["price"]),
        subject=f"LinguaLearn 会员 - {plan['label']}",
        return_url=config.ALIPAY_RETURN_URL or f"{config.APP_BASE_URL}/#/profile?membership=success",
        notify_url=config.ALIPAY_NOTIFY_URL or f"{config.APP_BASE_URL}/api/payments/alipay/webhook",
    )
    checkout_url = f"{config.ALIPAY_GATEWAY}?{pay_str}"

    database.save_membership_order(
        order_id=order_id,
        email=current_user["email"],
        provider="alipay",
        plan_code=plan_code,
        currency=plan["currency"],
        amount=plan["price"],
        status="pending",
        checkout_url=checkout_url,
        payload_json=json.dumps({"pay_str": pay_str}, ensure_ascii=False),
    )
    return {"order_id": order_id, "provider": "alipay", "checkout_url": checkout_url}


@app.post("/api/payments/alipay/webhook")
async def alipay_webhook(request: Request):
    form = dict(await request.form())
    sign = form.pop("sign", None)
    form.pop("sign_type", None)
    if not sign:
        raise HTTPException(400, "缺少签名")

    try:
        from alipay import AliPay
    except Exception:
        raise HTTPException(500, "服务端未安装 python-alipay-sdk")

    alipay = AliPay(
        appid=config.ALIPAY_APP_ID,
        app_notify_url=config.ALIPAY_NOTIFY_URL or None,
        app_private_key_string=config.ALIPAY_PRIVATE_KEY,
        alipay_public_key_string=config.ALIPAY_PUBLIC_KEY,
        sign_type="RSA2",
        debug=("sandbox" in (config.ALIPAY_GATEWAY or "")),
    )
    if not alipay.verify(form, sign):
        raise HTTPException(400, "支付宝签名校验失败")

    order_id = form.get("out_trade_no")
    trade_status = form.get("trade_status")
    order = database.get_membership_order(order_id) if order_id else None
    if order and trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        agreement_no = form.get("agreement_no") or form.get("trade_no")
        database.update_membership_order(
            order_id,
            status="paid",
            subscription_id=agreement_no,
            payload_json=json.dumps(form, ensure_ascii=False),
        )
        _activate_membership_for_user(
            email=order["email"],
            plan_code=order["plan_code"],
            provider="alipay",
            subscription_id=agreement_no,
            country_code=(database.get_user_membership(order["email"]) or {}).get("country_code", "CN"),
        )
    elif order and trade_status:
        database.update_membership_order(order_id, status="failed", payload_json=json.dumps(form, ensure_ascii=False))

    return PlainTextResponse("success")


@app.post("/api/membership/cancel-auto-renew")
async def cancel_auto_renew(
    request: Request,
    current_user: dict = Depends(require_user),
):
    rec = database.get_user_membership(current_user["email"]) or {}
    if rec.get("tier") != "member" or rec.get("status") != "active":
        raise HTTPException(400, "当前不是有效会员")

    provider = rec.get("provider")
    sub_id = rec.get("subscription_id")
    if provider == "stripe" and sub_id and config.STRIPE_SECRET_KEY:
        resp = requests.post(
            f"https://api.stripe.com/v1/subscriptions/{sub_id}",
            data={"cancel_at_period_end": "true"},
            auth=(config.STRIPE_SECRET_KEY, ""),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise HTTPException(400, f"Stripe 取消自动续费失败: {resp.text[:300]}")

    database.update_user_membership(current_user["email"], auto_renew=0, status="cancelled")
    return {"status": "ok", "auto_renew": False}


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
    """返回所有 ASS 样式模版的预览信息（供前端样式画廊使用）"""
    from core.ass_styles import STYLE_TEMPLATES
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
    target_lang:        str   = Form("zh"),
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
    style_id:           str   = Form("aurora_dark"),  # ASS 样式模版 ID
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
    if q != "auto":
        try:
            stream_path = await asyncio.to_thread(_ensure_stream_variant, job_id, file_path, q)
        except Exception as e:
            print(f"⚠️ 生成 {q}p 流失败，回退原视频: {e}")
            stream_path = file_path

    return FileResponse(path=str(stream_path), media_type="video/mp4")


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


# ===== 配置保存/加载 =====

@app.post("/api/config/save")
async def save_config(
    config_json: str = Form(...),
    current_user: dict = Depends(require_user),
):
    """保存用户配置"""
    try:
        # 验证 JSON 格式
        import json
        json.loads(config_json)
    except:
        raise HTTPException(400, "配置 JSON 格式不正确")

    if database.save_user_config(current_user["email"], config_json):
        return {"status": "ok"}
    else:
        raise HTTPException(500, "保存配置失败")


@app.get("/api/config/load")
async def load_config(current_user: dict = Depends(require_user)):
    """加载用户配置"""
    config = database.get_user_config(current_user["email"])
    if config:
        return {"config": config}
    else:
        return {"config": None}


# ===== 命名配置预设接口 =====

@app.post("/api/config/presets")
async def create_config_preset(
    name: str = Form(...),
    config_json: str = Form(...),
    current_user: dict = Depends(require_user),
):
    """保存命名配置预设"""
    try:
        json.loads(config_json)
    except Exception:
        raise HTTPException(400, "配置 JSON 格式不正确")
    name = name.strip() or f"配置 {datetime.now().strftime('%m-%d %H:%M')}"
    preset_id = database.save_config_preset(current_user["email"], name, config_json)
    if preset_id < 0:
        raise HTTPException(500, "保存预设失败")
    return {"id": preset_id, "name": name, "created_at": datetime.now().isoformat()}


@app.get("/api/config/presets")
async def list_config_presets(current_user: dict = Depends(require_user)):
    """列出用户所有命名配置预设"""
    presets = database.get_config_presets(current_user["email"])
    return {"presets": presets}


@app.delete("/api/config/presets/{preset_id}")
async def delete_config_preset(preset_id: int, current_user: dict = Depends(require_user)):
    """删除命名配置预设"""
    ok = database.delete_config_preset(preset_id, current_user["email"])
    if not ok:
        raise HTTPException(404, "预设不存在")
    return {"status": "ok"}


# ===== Segments 接口 =====

@app.get("/api/jobs/{job_id}/segments")
async def get_job_segments(job_id: str):
    """获取视频的句子时间戳（供视频预览页同步文稿使用）"""
    get_job_or_404(job_id)
    path = OUTPUT_DIR / job_id / "segments.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


# ============================================================
# STICKER routes
# ============================================================

STICKER_DIR = Path("uploads/stickers")
STICKER_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/stickers")
async def list_stickers():
    """列出所有已上传的贴纸"""
    stickers = []
    if STICKER_DIR.exists():
        for f in sorted(STICKER_DIR.iterdir()):
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
                stickers.append({
                    "id": f.stem,
                    "url": f"/stickers/{f.name}",
                    "name": f.name,
                })
    return stickers


@app.post("/api/stickers")
async def upload_sticker(image: UploadFile = File(...)):
    """上传贴纸图片"""
    if not image.filename:
        raise HTTPException(400, "未提供文件")

    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp"}
    if image.content_type and image.content_type not in allowed_types:
        raise HTTPException(400, "仅支持 PNG/JPG/GIF/SVG/WebP 格式")

    # Generate unique filename
    ext = Path(image.filename).suffix.lower() or '.png'
    sticker_id = f"stk_{uuid.uuid4().hex[:8]}"
    filename = f"{sticker_id}{ext}"
    filepath = STICKER_DIR / filename

    content = await image.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "id": sticker_id,
        "url": f"/stickers/{filename}",
        "name": filename,
    }


@app.get("/api/dictionary/{word}")
async def lookup_dictionary(word: str, target_lang: str = "zh"):
    """查询英文单词释义（Free Dictionary API v2），可选翻译到目标语言"""
    import urllib.request
    import urllib.error

    word = word.strip().lower()
    if not word or not all(c.isalpha() or c in "-'" for c in word):
        raise HTTPException(400, "无效单词")

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    def _fetch():
        req = urllib.request.Request(url, headers={"User-Agent": "LinguaLearn/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _fetch)
        entry = data[0]

        # 提取音标和音频
        phonetic = entry.get("phonetic", "")
        audio_url = ""
        for ph in entry.get("phonetics", []):
            if ph.get("text") and not phonetic:
                phonetic = ph["text"]
            if ph.get("audio") and not audio_url:
                audio_url = ph["audio"]
                if audio_url.startswith("//"):
                    audio_url = "https:" + audio_url

        # 提取释义（最多3个词性）
        meanings = []
        for m in entry.get("meanings", [])[:3]:
            defs = m.get("definitions", [])
            if defs:
                d = defs[0]
                syns = (m.get("synonyms", []) + d.get("synonyms", []))[:3]
                meanings.append({
                    "pos": m.get("partOfSpeech", ""),
                    "definition": d.get("definition", ""),
                    "example": d.get("example", ""),
                    "synonyms": syns,
                })

        result = {
            "word": entry.get("word", word),
            "phonetic": phonetic,
            "audio": audio_url,
            "meanings": meanings,
        }

        # 翻译释义到目标语言（非英文时）
        if target_lang and target_lang != "en" and meanings:
            try:
                translated = await _translate_definitions(word, meanings, target_lang)
                if translated:
                    result["translated_meanings"] = translated
            except Exception as te:
                print(f"⚠️ 翻译释义失败: {te}")

        return result

    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTPException(404, "单词不存在")
        raise HTTPException(502, "词典服务错误")
    except Exception as e:
        raise HTTPException(500, f"查询失败: {e}")


# 释义翻译缓存
_translation_cache: dict = {}

async def _translate_definitions(word: str, meanings: list, target_lang: str) -> list:
    """使用 DeepSeek/OpenAI 将英文释义翻译成目标语言"""
    cache_key = f"{word}_{target_lang}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    lang_names = {
        "zh": "中文", "ja": "日本語", "ko": "한국어",
        "de": "Deutsch", "fr": "français", "es": "español", "ru": "русский"
    }
    lang_name = lang_names.get(target_lang, target_lang)

    # 构建翻译请求
    defs_text = "\n".join(
        f"{i+1}. [{m['pos']}] {m['definition']}"
        for i, m in enumerate(meanings) if m.get('definition')
    )

    from openai import OpenAI
    api_key = getattr(config, 'OPENAI_API_KEY', '')
    base_url = getattr(config, 'OPENAI_BASE_URL', '')
    if not api_key:
        return []

    def _do_translate():
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"你是一个精准的词典翻译助手。将英文释义翻译成{lang_name}，保持简洁准确。每行一个翻译，格式为数字序号开头，只返回翻译内容。"},
                {"role": "user", "content": f"翻译以下「{word}」的英文释义为{lang_name}：\n{defs_text}"}
            ],
            temperature=0.2,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()

    raw = await asyncio.get_event_loop().run_in_executor(None, _do_translate)

    # 解析翻译结果
    translated = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 去除序号前缀 "1. " / "1、" / "1) "
        import re
        cleaned = re.sub(r'^\d+[\.\、\)\]\s]+', '', line).strip()
        # 去除可能的 [pos] 前缀
        cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned).strip()
        if cleaned:
            translated.append(cleaned)

    _translation_cache[cache_key] = translated
    return translated


# ===== Quiz / Review Words API =====

@app.get("/api/jobs/{job_id}/quiz-data")
async def get_quiz_data(job_id: str, debug: bool = False):
    """从 Markdown 文档提取词汇和表达数据用于自测"""
    job_out = OUTPUT_DIR / job_id
    # 获取 job 信息
    j = get_job_or_404(job_id)
    result = j.get("result") or {}
    if isinstance(result, str):
        result = json.loads(result) if result else {}
    if not isinstance(result, dict):
        result = {}
    md_file = result.get("markdown")
    if not md_file:
        raise HTTPException(404, "无学习笔记")

    md_path = job_out / md_file
    if not md_path.exists():
        raise HTTPException(404, f"笔记文件不存在: {md_path}")

    content = md_path.read_text(encoding='utf-8')

    # 更健壮的表格提取：找到标题后，提取表格（直到下一个 ## 标题或文件结尾）
    import re
    words = []
    expressions = []

    # 各语言词汇/表达汇总表的完整标题（避免与内容简介标题混淆）
    _tl = result.get("target_lang", "zh")
    _VOCAB_HEADERS = {
        'zh': '## 📖 词汇汇总表', 'en': '## 📖 Vocabulary Summary',
        'ja': '## 📖 語彙まとめ',  'ko': '## 📖 어휘 정리',
        'de': '## 📖 Vokabeln Zusammenfassung', 'fr': '## 📖 Résumé du vocabulaire',
        'es': '## 📖 Resumen de vocabulario',   'ru': '## 📖 Итоговый словарь',
    }
    _EXPR_HEADERS = {
        'zh': '## 📝 表达汇总表', 'en': '## 📝 Expressions Summary',
        'ja': '## 📝 表現まとめ',  'ko': '## 📝 표현 정리',
        'de': '## 📝 Ausdrücke Zusammenfassung', 'fr': '## 📝 Résumé des expressions',
        'es': '## 📝 Resumen de expresiones',    'ru': '## 📝 Итоговые выражения',
    }
    _vocab_header = _VOCAB_HEADERS.get(_tl, '## 📖 词汇汇总表')
    _expr_header  = _EXPR_HEADERS.get(_tl, '## 📝 表达汇总表')

    def extract_markdown_table(content, section_header):
        """从Markdown中提取指定section的表格"""
        # 先找到section标题
        section_pattern = re.escape(section_header) + r'[^\n]*\n+(.*?)(?=\n##|$)'
        section_match = re.search(section_pattern, content, re.DOTALL)
        if not section_match:
            return []

        section_content = section_match.group(1)

        # 从section内容中提取表格行（以 | 开头的行）
        lines = section_content.split('\n')
        table_rows = []
        in_table = False
        for line in lines:
            if line.strip().startswith('|'):
                # 检查是否是分隔线（包含 --- 或 :---: 等）
                if '---' in line or ':---' in line:
                    in_table = True
                    continue
                if in_table:
                    table_rows.append(line)

        return table_rows

    # 提取词汇表
    word_rows = extract_markdown_table(content, _vocab_header)
    for row in word_rows:
        if not row.strip():
            continue
        cols = [c.strip() for c in row.strip('|').split('|')]
        if len(cols) >= 3:
            word = re.sub(r'\*\*(.+?)\*\*', r'\1', cols[0]).strip()
            phonetic = re.sub(r'`(.+?)`', r'\1', cols[1]).strip()
            meaning = cols[2].strip()
            if word and meaning:
                words.append({"word": word, "phonetic": phonetic, "meaning": meaning})

    # 提取表达表
    expr_rows = extract_markdown_table(content, _expr_header)
    for row in expr_rows:
        if not row.strip():
            continue
        cols = [c.strip() for c in row.strip('|').split('|')]
        if len(cols) >= 2:
            expr = re.sub(r'\*\*(.+?)\*\*', r'\1', cols[0]).strip()
            meaning = cols[1].strip()
            if expr and meaning:
                expressions.append({"word": expr, "meaning": meaning})

    result_data = {
        "words": words,
        "expressions": expressions,
        "source_lang": result.get("source_lang", "en"),
        "target_lang": result.get("target_lang", "zh"),
        "job_name": j.get("name") or j.get("video_filename") or job_id[:12],
    }

    # Debug mode: 返回额外信息用于调试
    if debug:
        result_data["debug"] = {
            "md_file": str(md_file),
            "md_exists": md_path.exists(),
            "word_rows_found": len(word_rows),
            "expr_rows_found": len(expr_rows),
            "markdown_length": len(content),
            "has_word_section": _vocab_header in content,
            "has_expr_section": _expr_header in content,
        }

    return result_data


@app.post("/api/review-words")
async def save_review_words(
    request: Request,
    current_user: dict = Depends(require_user),
):
    """保存错误单词到复习本"""
    body = await request.json()
    job_id = body.get("job_id", "")
    words = body.get("words", [])
    if not job_id or not words:
        raise HTTPException(400, "缺少 job_id 或 words")
    added = database.add_review_words(current_user["email"], job_id, words)
    return {"added": added, "total": len(words)}


@app.get("/api/review-words")
async def list_review_words(
    job_id: str = None,
    mastered: int = None,
    current_user: dict = Depends(require_user),
):
    """获取复习单词列表"""
    words = database.get_review_words(current_user["email"], job_id=job_id, mastered=mastered)
    return {"words": words}


@app.patch("/api/review-words/{word_id}")
async def update_review_word(
    word_id: int,
    request: Request,
    current_user: dict = Depends(require_user),
):
    """更新复习单词状态"""
    body = await request.json()
    mastered = body.get("mastered", 0)
    ok = database.update_review_word(word_id, current_user["email"], mastered)
    if not ok:
        raise HTTPException(404, "单词不存在")
    return {"ok": True}


@app.delete("/api/review-words/{word_id}")
async def delete_review_word_api(
    word_id: int,
    current_user: dict = Depends(require_user),
):
    """删除复习单词"""
    ok = database.delete_review_word(word_id, current_user["email"])
    if not ok:
        raise HTTPException(404, "单词不存在")
    return {"ok": True}


# 头像目录单独挂载，避免被前端构建覆盖
Path("uploads/avatars").mkdir(parents=True, exist_ok=True)
app.mount("/avatars", StaticFiles(directory="uploads/avatars"), name="avatars")
# 贴纸目录
Path("uploads/stickers").mkdir(parents=True, exist_ok=True)
app.mount("/stickers", StaticFiles(directory="uploads/stickers"), name="stickers")
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    import os as _os
    _port = int(_os.getenv("PORT", 8080))
    print("🚀 LinguaLearn 服务启动中...")
    print(f"📱 打开浏览器访问: http://localhost:{_port}")
    uvicorn.run(app, host="0.0.0.0", port=_port, reload=False)
