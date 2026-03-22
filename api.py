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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import redirect_stdout
from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core'))

import config
import database

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

def get_job_or_404(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "任务不存在")
    return jobs[job_id]


# ===== Email sender =====

def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP. Returns True if sent, False in dev mode (no SMTP)."""
    host = getattr(config, 'SMTP_HOST', '')
    user = getattr(config, 'SMTP_USER', '')
    pw   = getattr(config, 'SMTP_PASS', '')
    port = int(getattr(config, 'SMTP_PORT', 587))
    from_addr = getattr(config, 'SMTP_FROM', 'LinguaLearn <noreply@lingualearn.app>')

    if not host or not user:
        return False  # dev mode

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = from_addr
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
        s.sendmail(from_addr, to_email, msg.as_string())
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


# ===== Video processing task =====

async def process_video_job(
    job_id: str, video_path: str,
    source_lang: str, target_lang: str, resolution: str,
    part1_repeat: int, part2_repeat: int, part3_repeat: int,
    part2_slow_speed: float,
    num_words: int, num_expressions: int,
    layout: Optional[dict], style: Optional[dict],
    loop: asyncio.AbstractEventLoop,
):
    def run_in_thread():
        capture    = ProgressCapture(job_id, loop)
        old_stdout = sys.stdout
        sys.stdout = capture
        try:
            # Apply config
            config.SOURCE_LANGUAGE    = source_lang
            config.TARGET_LANGUAGE    = target_lang
            config.VIDEO_RESOLUTION   = resolution
            config.PART1_REPEAT_COUNT = part1_repeat
            config.PART2_REPEAT_COUNT = part2_repeat
            config.PART3_REPEAT_COUNT = part3_repeat
            config.SPEED_SLOW         = part2_slow_speed

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

            output_name = Path(video_path).stem[:50]

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
            transcriber = AudioTranscriber(source_lang=source_lang)
            audio_path  = transcriber.extract_audio_from_video(video_path)
            transcription = transcriber.transcribe_once_with_word_timestamps(audio_path)
            text = transcription["text"]

            # Step 2 – split sentences
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 2, "name": "智能分句", "total": 5}), loop)
            update_job(job_id, step=2, step_name="正在分割句子...")
            splitter   = SentenceSplitter(max_words=config.MAX_SENTENCE_WORDS,
                                          min_words=config.MIN_SENTENCE_WORDS,
                                          source_lang=source_lang)
            sentences  = splitter.split_text(text)
            timestamps = transcriber.align_sentences_to_timestamps(audio_path, sentences, output_name)

            # Step 3 – analyse
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 3, "name": "词汇分析", "total": 5}), loop)
            update_job(job_id, step=3, step_name=f"正在分析 {len(sentences)} 个句子...")
            analyzer       = WordAnalyzer(source_lang=source_lang, target_lang=target_lang)
            sentences_data = analyzer.batch_analyze(sentences)

            # Trim words/expressions per sentence if user set limits
            if num_words > 0 or num_expressions > 0:
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
            exporter = MarkdownExporter(output_dir=str(job_out),
                                        source_lang=source_lang, target_lang=target_lang)
            markdown_path = exporter.export(sentences_data, f"{output_name}.md")

            # Step 5 – render video
            if check_cancelled(): return
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "step", {"step": 5, "name": "渲染学习视频", "total": 5}), loop)
            update_job(job_id, step=5, step_name="正在渲染视频（最耗时）...")
            processor     = VideoProcessor()
            segments_info = [{"start": ts.get("start", 0), "end": ts.get("end", 0)} for ts in timestamps]
            video_output  = str(job_out / f"{output_name}.mp4")

            # Merge layout + style into combined style dict
            combined_style = {}
            if style:
                combined_style.update(style)
            if layout:
                combined_style.update(layout)

            video_paths = processor.process_full_video(
                video_path, sentences_data, video_output, segments_info,
                progress_callback=progress_callback,
                style=combined_style or None,
                cancelled_fn=check_cancelled,
            )

            if video_paths.get('cancelled'):
                return

            full_video = job_out / f"{output_name}_full.mp4"
            final_full = job_out / "学习版.mp4"
            if full_video.exists():
                shutil.move(str(full_video), str(final_full))

            update_job(job_id, status="done", step=5, step_name="完成！",
                       result={
                           "sentences_count": len(sentences_data),
                           "full_video":  "学习版.mp4" if final_full.exists() else None,
                           "markdown":    f"{output_name}.md",
                           "source_lang": source_lang,
                           "target_lang": target_lang,
                       })
            asyncio.run_coroutine_threadsafe(
                _push(job_id, "done", {"sentences": len(sentences_data)}), loop)

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"❌ 处理失败: {e}\n{err}")
            update_job(job_id, status="error", error=str(e))
            asyncio.run_coroutine_threadsafe(_push(job_id, "error", str(e)), loop)
        finally:
            sys.stdout = old_stdout

    await asyncio.get_event_loop().run_in_executor(None, run_in_thread)


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
    return {"token": token, "name": user["name"], "email": email}


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
        return {"token": token, "name": user["name"], "email": email}

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
        return {"token": token, "name": user["name"], "phone": phone}

    elif login_type == "phone_code":
        # 手机号+验证码登陆（用户不存在则自动注册）
        phone = phone.strip()
        code = code.strip()
        if not phone or not code:
            raise HTTPException(400, "手机号和验证码不能为空")

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
async def get_me(current_user: Optional[dict] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(401, "未登录")
    return {"email": current_user["email"], "name": current_user["name"],
            "created_at": current_user["created_at"]}


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


# ============================================================
# PREVIEW route
# ============================================================

@app.post("/api/preview")
async def generate_preview(
    source_lang:     str   = Form("en"),
    target_lang:     str   = Form("zh"),
    resolution:      str   = Form("1080p"),
    num_words:       int   = Form(4),
    num_expressions: int   = Form(2),
    style:           str   = Form("{}"),
):
    valid_langs = set(config.LANGUAGE_NATIVE_NAMES.keys())
    if source_lang not in valid_langs or target_lang not in valid_langs:
        raise HTTPException(400, "不支持的语言代码")

    config.VIDEO_RESOLUTION = resolution
    try:
        style_dict = json.loads(style) if style else {}
    except Exception:
        style_dict = {}

    try:
        from core.html_renderer import HTMLRenderer
        renderer   = HTMLRenderer()
        preview_dir = str(TEMP_DIR / "preview")
        result = renderer.generate_preview_images(
            num_words=max(1, min(6, num_words)),
            num_expressions=max(1, min(3, num_expressions)),
            source_lang=source_lang,
            target_lang=target_lang,
            resolution=resolution,
            output_dir=preview_dir,
            style=style_dict,
        )
        return result
    except Exception as e:
        import traceback
        raise HTTPException(500, f"预览生成失败: {e}\n{traceback.format_exc()}")


# ============================================================
# JOB routes
# ============================================================

@app.get("/api/languages")
async def get_languages():
    return {"languages": [
        {"code": code, "native_name": name, "flag": config.LANGUAGE_FLAGS.get(code, "🌐")}
        for code, name in config.LANGUAGE_NATIVE_NAMES.items()
    ]}


@app.post("/api/jobs")
async def create_job(
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
    layout:             str   = Form("{}"),   # position percentages
    style:              str   = Form("{}"),   # visual style options
    current_user: dict = Depends(require_user),
):
    valid_langs = set(config.LANGUAGE_NATIVE_NAMES.keys())
    if source_lang not in valid_langs or target_lang not in valid_langs:
        raise HTTPException(400, "不支持的语言代码")
    if source_lang == target_lang:
        raise HTTPException(400, "源语言和目标语言不能相同")

    try:
        layout_dict = json.loads(layout) if layout else {}
    except Exception:
        layout_dict = {}
    try:
        style_dict = json.loads(style) if style else {}
    except Exception:
        style_dict = {}

    job_id        = str(uuid.uuid4())
    video_filename = f"{job_id}_{video.filename}"
    video_path    = UPLOAD_DIR / video_filename
    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

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
    }
    job_ws_queues[job_id] = asyncio.Queue()

    asyncio.create_task(process_video_job(
        job_id=job_id, video_path=str(video_path),
        source_lang=source_lang, target_lang=target_lang, resolution=resolution,
        part1_repeat=part1_repeat, part2_repeat=part2_repeat, part3_repeat=part3_repeat,
        part2_slow_speed=part2_slow_speed,
        num_words=num_words, num_expressions=num_expressions,
        layout=layout_dict or None, style=style_dict or None,
        loop=asyncio.get_event_loop(),
    ))

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    return get_job_or_404(job_id)


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str, current_user: dict = Depends(require_user)):
    job = get_job_or_404(job_id)
    if job["status"] in ("done", "error", "cancelled"):
        raise HTTPException(400, "任务已结束，无法取消")
    update_job(job_id, status="cancelled", cancelled=True, step_name="已取消")
    await _push(job_id, "cancelled", {})
    return {"status": "cancelled"}


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
                    await websocket.send_json({"type": "status", "data": jobs[job_id]})
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
async def download_file(job_id: str, filename: str):
    job = get_job_or_404(job_id)
    if job["status"] != "done":
        raise HTTPException(400, "任务尚未完成")
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path=str(file_path), filename=filename,
                        media_type="application/octet-stream")


@app.get("/api/jobs/{job_id}/stream/{filename}")
async def stream_file(job_id: str, filename: str):
    """Stream video with range request support for in-browser playback."""
    get_job_or_404(job_id)
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path=str(file_path), media_type="video/mp4")


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


@app.get("/api/jobs")
async def list_jobs(current_user: Optional[dict] = Depends(get_current_user)):
    job_list = sorted(jobs.values(), key=lambda x: x.get("created_at", ""), reverse=True)
    # Only show user's own jobs if logged in
    if current_user:
        job_list = [j for j in job_list if j.get("created_by") == current_user["email"]]
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("🚀 LinguaLearn 服务启动中...")
    print("📱 打开浏览器访问: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
