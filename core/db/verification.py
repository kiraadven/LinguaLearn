"""Email verification code operations."""
from datetime import datetime

from .connection import get_db

def save_verification_code(email: str, code: str, expires_at: str) -> bool:
    """保存验证码"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT OR REPLACE INTO verification_codes (email, code, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (email, code, expires_at, now))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_verification_code(email: str) -> dict:
    """获取验证码"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT code, expires_at FROM verification_codes WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"code": row["code"], "expires_at": row["expires_at"]}
    return None

def verify_code(email: str, code: str) -> bool:
    """验证验证码是否正确且未过期"""
    vc = get_verification_code(email)
    if not vc:
        return False
    if vc["code"] != code:
        return False
    if datetime.fromisoformat(vc["expires_at"]) < datetime.now():
        return False
    return True

def delete_verification_code(email: str) -> bool:
    """删除验证码"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

