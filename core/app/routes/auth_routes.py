"""Authentication and profile routes."""

from datetime import datetime, timedelta
import random
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile


def build_auth_router(
    *,
    database,
    config,
    get_current_user: Callable,
    require_user: Callable,
    detect_country_code: Callable,
    build_membership_status: Callable,
    gen_code: Callable[[], str],
    hash_password: Callable[[str], str],
    send_code_email: Callable[[str, str], bool],
    send_sms: Callable[[str, str], bool],
    send_email: Callable[[str, str, str], bool],
    avatar_dir: Path,
    resend_module: Optional[Any] = None,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/send-code")
    async def send_code(email: str = Form(...)):
        """发送邮箱验证码（注册时调用）"""
        email = email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(400, "邮箱格式不正确")
        if database.user_exists(email):
            raise HTTPException(400, "该邮箱已注册，请直接登录")

        code = gen_code()
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        database.save_verification_code(email, code, expires_at)

        sent = send_code_email(email, code)
        if sent:
            return {"status": "ok"}
        print(f"[DEV] Verification code for {email}: {code}")
        return {"status": "ok", "dev_mode": True, "dev_code": code}

    @router.post("/api/auth/send-sms-code")
    async def send_sms_code(phone: str = Form(...)):
        """发送短信验证码（注册/登陆时调用）"""
        phone = phone.strip()
        if not phone or len(phone) < 10:
            raise HTTPException(400, "手机号格式不正确")

        code = gen_code()
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        database.save_verification_code(phone, code, expires_at)

        sent = send_sms(phone, code)
        if sent:
            return {"status": "ok"}
        print(f"[DEV] Verification code for {phone}: {code}")
        return {"status": "ok", "dev_mode": True, "dev_code": code}

    @router.post("/api/auth/register")
    async def register(
        email: str = Form(...),
        password: str = Form(...),
        name: str = Form(""),
        code: str = Form(...),
        phone: str = Form(""),
    ):
        """注册用户（邮箱或手机号）"""
        code = code.strip()

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
            email_generated = f"{phone}@lingualearn.local"
            user = database.create_user_with_phone(
                email_generated, hash_password(password), phone, name.strip() or phone
            )
            if not user:
                raise HTTPException(400, "手机号已注册")

            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            database.save_token(token, email_generated, expires_at)

            return {"token": token, "name": user["name"], "phone": phone}

        email = email.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
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
        database.create_user(email, hash_password(password), name.strip())

        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        database.save_token(token, email, expires_at)

        user = database.get_user(email)
        return {"token": token, "name": user["name"], "email": email, "avatar_url": user.get("avatar_url")}

    @router.post("/api/auth/login")
    async def login(
        login_type: str = Form("email_password"),
        email: str = Form(""),
        phone: str = Form(""),
        password: str = Form(""),
        code: str = Form(""),
    ):
        """登陆（支持三种方式）"""
        if login_type == "email_password":
            email = email.strip().lower()
            if not email:
                raise HTTPException(400, "邮箱不能为空")
            user = database.get_user(email)
            if not user or user["password_hash"] != hash_password(password):
                raise HTTPException(401, "邮箱或密码错误")
            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            database.save_token(token, email, expires_at)
            return {"token": token, "name": user["name"], "email": email, "avatar_url": user.get("avatar_url")}

        if login_type == "phone_password":
            phone = phone.strip()
            if not phone:
                raise HTTPException(400, "手机号不能为空")
            user = database.get_user_by_phone(phone)
            if not user or user["password_hash"] != hash_password(password):
                raise HTTPException(401, "手机号或密码错误")
            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            database.save_token(token, user["email"], expires_at)
            return {
                "token": token,
                "name": user["name"],
                "phone": phone,
                "email": user["email"],
                "avatar_url": user.get("avatar_url"),
            }

        if login_type == "phone_code":
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
            user = database.get_user_by_phone(phone)
            if not user:
                email_generated = f"{phone}@lingualearn.local"
                user = database.create_user_with_phone(
                    email_generated, hash_password(phone), phone, phone
                )
                if not user:
                    raise HTTPException(400, "注册失败")

            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            database.save_token(token, user["email"], expires_at)
            return {"token": token, "name": user["name"], "phone": phone}

        raise HTTPException(400, "login_type 不支持")

    @router.get("/api/auth/me")
    async def get_me(request: Request, current_user: Optional[dict] = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(401, "未登录")
        country_code = detect_country_code(request)
        membership = build_membership_status(current_user["email"], country_code=country_code)
        return {
            "email": current_user["email"],
            "name": current_user["name"],
            "avatar_url": current_user.get("avatar_url"),
            "created_at": current_user["created_at"],
            "membership": membership,
        }

    @router.post("/api/auth/change-password")
    async def change_password(
        old_password: str = Form(...),
        new_password: str = Form(...),
        current_user: dict = Depends(require_user),
    ):
        if current_user["password_hash"] != hash_password(old_password):
            raise HTTPException(400, "原密码错误")
        if len(new_password) < 6:
            raise HTTPException(400, "新密码至少6位")
        database.update_user_password(current_user["email"], hash_password(new_password))
        return {"status": "ok"}

    @router.post("/api/auth/send-email-code")
    async def send_email_code(email: str = Form(...)):
        """发送邮件验证码到目标邮箱"""
        if not email or "@" not in email:
            raise HTTPException(400, "邮箱格式错误")

        code = f"{random.randint(100000, 999999)}"
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        database.save_verification_code(email, code, expires_at)

        # Use Resend first when configured, fallback to SMTP.
        if config.RESEND_API_KEY and resend_module:
            try:
                resend_module.api_key = config.RESEND_API_KEY
                r = resend_module.Emails.send(
                    {
                        "from": "noreply@lingualearn.com",
                        "to": email,
                        "subject": "LinguaLearn 邮箱验证码",
                        "html": f"""
    <div style=\"font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#0a0a12;color:#e2e8f0;border-radius:16px;\">
      <h1 style=\"font-size:24px;font-weight:800;background:linear-gradient(135deg,#6c63ff,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;\">LinguaLearn</h1>
      <h2 style=\"font-size:14px;color:#64748b;font-weight:500;margin:0 0 24px;\">邮箱验证</h2>
      <p style=\"font-size:32px;font-weight:800;color:#fff;margin:32px 0;letter-spacing:8px;text-align:center;\">{code}</p>
      <p style=\"color:#64748b;font-size:13px;margin:0;\">验证码 <strong>10 分钟</strong>内有效。如非本人操作，请忽略此邮件。</p>
    </div>
                """,
                    }
                )
                if r.get("id"):
                    return {"status": "ok", "message": "验证码已发送", "code": code}
            except Exception as e:
                print(f"[Resend Error] {type(e).__name__}: {e}")

        send_email(
            email,
            "【LinguaLearn】邮箱验证码",
            f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#0a0a12;color:#e2e8f0;border-radius:16px;">
      <h1 style="font-size:24px;font-weight:800;background:linear-gradient(135deg,#6c63ff,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;">LinguaLearn</h1>
      <h2 style="font-size:14px;color:#64748b;font-weight:500;margin:0 0 24px;">邮箱验证</h2>
      <p style="font-size:32px;font-weight:800;color:#fff;margin:32px 0;letter-spacing:8px;text-align:center;">{code}</p>
      <p style="color:#64748b;font-size:13px;margin:0;">验证码 <strong>10 分钟</strong>内有效。如非本人操作，请忽略此邮件。</p>
    </div>
    """,
        )
        print(f"[DEV] Verification code for {email}: {code}")
        return {"status": "ok", "message": "验证码已发送", "code": code}

    @router.post("/api/auth/bind-email")
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

        if not database.bind_email(current_user["email"], email):
            raise HTTPException(400, "邮箱已被其他用户使用")

        return {"status": "ok", "message": "邮箱已绑定", "email": email}

    @router.post("/api/users/avatar")
    async def upload_avatar(
        file: UploadFile = File(...),
        current_user: dict = Depends(require_user),
    ):
        """上传用户头像"""
        if not file.filename:
            raise HTTPException(400, "未提供文件")

        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(400, "仅支持 JPG/PNG/WebP 格式")

        try:
            avatar_dir.mkdir(parents=True, exist_ok=True)

            ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
            ext = ext_map.get(file.content_type, "jpg")

            filename = f"{current_user['email'].replace('@', '_')}.{ext}"
            filepath = avatar_dir / filename
            content = await file.read()
            filepath.write_bytes(content)

            avatar_url = f"/avatars/{filename}"
            if not database.update_user_avatar(current_user["email"], avatar_url):
                raise HTTPException(500, "头像保存失败")

            return {"status": "ok", "avatar_url": avatar_url}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"头像上传失败: {e}")

    return router

