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
import base64
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
                            }
                            seen_layout.add(lkey)
            if not nested_layout and layout:
                # 从旧式 flat layout_dict 转换
                if "subtitle_width_pct" in layout:
                    nested_layout["subtitle"] = {
                        "x_pct": layout.get("subtitle_x_pct", 0.05),
                        "y_pct": layout.get("subtitle_y_pct", 0.76),
                        "w_pct": layout.get("subtitle_width_pct", 0.90),
                        "h_pct": layout.get("subtitle_height_pct", 0.14),
                    }
                if "wordbox_width_pct" in layout:
                    nested_layout["wordbox"] = {
                        "x_pct": layout.get("wordbox_x_pct", 0.75),
                        "y_pct": layout.get("wordbox_y_pct", 0.005),
                        "w_pct": layout.get("wordbox_width_pct", 0.245),
                        "h_pct": layout.get("wordbox_height_pct", 0.65),
                    }
                if "exprbox_width_pct" in layout:
                    nested_layout["exprbox"] = {
                        "x_pct": layout.get("exprbox_x_pct", 0.005),
                        "y_pct": layout.get("exprbox_y_pct", 0.005),
                        "w_pct": layout.get("exprbox_width_pct", 0.245),
                        "h_pct": layout.get("exprbox_height_pct", 0.55),
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
                                        source_lang=source_lang, target_lang=target_lang)
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
            )
            print("🎬 视频处理完成")

            if video_paths.get('cancelled'):
                return

            # 保存含时间戳的 segments.json，供视频预览页使用
            try:
                segs_with_text = [
                    {"start": seg["start"], "end": seg["end"], "text": sd.get("original_text", "")}
                    for seg, sd in zip(segments_info, sentences_data)
                ]
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

@app.post("/api/render-box")
async def render_box(
    box_type:        str   = Form(...),     # subtitle / wordbox / expressionbox
    width_pct:       float = Form(0.8),     # % of frame width
    height_pct:      float = Form(0.2),     # % of frame height
    source_lang:     str   = Form("en"),
    target_lang:     str   = Form("zh"),
    resolution:      str   = Form("1080p"),
    num_words:       int   = Form(4),
    num_expressions: int   = Form(2),
    style:           str   = Form("{}"),
    current_user: dict = Depends(get_current_user),
):
    """实时渲染单个框，返回 base64 PNG 用于预览"""
    if box_type not in ('subtitle', 'wordbox', 'expressionbox'):
        raise HTTPException(400, "不支持的框类型")

    config.VIDEO_RESOLUTION = resolution
    try:
        style_dict = json.loads(style) if style else {}
    except Exception:
        style_dict = {}

    try:
        from core.html_renderer import HTMLRenderer
        renderer = HTMLRenderer()

        # 根据分辨率计算像素尺寸
        is_1080p = resolution == "1080p"
        frame_w = 1920 if is_1080p else 1280
        frame_h = 1080 if is_1080p else 720

        width_px = int(frame_w * width_pct)
        height_px = int(frame_h * height_pct)

        # 限制最小尺寸（避免渲染过小的框）
        width_px = max(80, width_px)
        height_px = max(60, height_px)

        print(f"[render-box] type={box_type} width_pct={width_pct:.3f} height_pct={height_pct:.3f} => {width_px}x{height_px}px  res={resolution}")

        preview_dir = str(TEMP_DIR / "render-box")
        os.makedirs(preview_dir, exist_ok=True)

        # 获取示例数据
        from core.html_renderer import _PREVIEW_EXAMPLES
        example = _PREVIEW_EXAMPLES.get(source_lang, _PREVIEW_EXAMPLES['en'])

        result = {}

        if box_type == 'subtitle':
            sentence = example['sentence']
            translation = example['translations'].get(target_lang) or list(example['translations'].values())[0]
            filepath = os.path.join(preview_dir, f'render_sub_{int(time.time()*1000)}.png')
            if renderer.render_subtitle(sentence, translation, width_px, height_px, filepath, style=style_dict):
                with open(filepath, 'rb') as f:
                    result['image'] = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
                os.unlink(filepath)

        elif box_type == 'wordbox':
            words = example['words'][:max(1, min(num_words, 6))]
            filepath = os.path.join(preview_dir, f'render_wb_{int(time.time()*1000)}.png')
            if renderer.render_wordbox(words, width_px, height_px, filepath, style=style_dict):
                with open(filepath, 'rb') as f:
                    result['image'] = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
                os.unlink(filepath)

        elif box_type == 'expressionbox':
            expressions = example['expressions'][:max(1, min(num_expressions, 3))]
            filepath = os.path.join(preview_dir, f'render_expr_{int(time.time()*1000)}.png')
            if renderer.render_expressionbox(expressions, width_px, height_px, filepath, style=style_dict):
                with open(filepath, 'rb') as f:
                    result['image'] = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
                os.unlink(filepath)

        return result

    except Exception as e:
        import traceback
        raise HTTPException(500, f"框渲染失败: {e}\n{traceback.format_exc()}")


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
    try:
        parts_list = json.loads(parts_json) if parts_json else []
    except Exception:
        parts_list = []

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
        # 删除已完成任务：清理文件 + 删除 DB 记录
        import shutil as _shutil
        job_out = OUTPUT_DIR / job_id
        if job_out.exists():
            _shutil.rmtree(str(job_out), ignore_errors=True)
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("🚀 LinguaLearn 服务启动中...")
    print("📱 打开浏览器访问: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
