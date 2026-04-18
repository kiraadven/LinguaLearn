"""Auth token operations."""
from datetime import datetime

from .connection import get_db

def save_token(token: str, email: str, expires_at: str) -> bool:
    """保存 Token"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO tokens (token, email, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (token, email, now, expires_at))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_token_email(token: str) -> str:
    """从 Token 获取邮箱"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT email FROM tokens WHERE token = ? AND expires_at > ?", (token, now))
    row = c.fetchone()
    conn.close()
    return row["email"] if row else None

def delete_token(token: str) -> bool:
    """删除 Token"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

