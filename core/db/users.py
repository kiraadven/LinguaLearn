"""User related DB operations."""
import sqlite3
from datetime import datetime

from .connection import get_db

def user_exists(email: str) -> bool:
    """检查用户是否存在"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def create_user(email: str, password_hash: str, name: str = "") -> dict:
    """创建用户"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO users (email, password_hash, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, password_hash, name or email.split('@')[0], now, now))
        conn.commit()
        return {"email": email, "password_hash": password_hash, "name": name or email.split('@')[0], "created_at": now}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user(email: str) -> dict:
    """获取用户信息"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email, password_hash, name, avatar_url, created_at FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "email": row["email"],
            "password_hash": row["password_hash"],
            "name": row["name"],
            "avatar_url": row["avatar_url"],
            "created_at": row["created_at"]
        }
    return None

def update_user_password(email: str, password_hash: str) -> bool:
    """更新用户密码"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ?",
              (password_hash, now, email))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

def user_exists_by_phone(phone: str) -> bool:
    """检查手机号用户是否存在"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE phone = ?", (phone,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def get_user_by_phone(phone: str) -> dict:
    """通过手机号获取用户信息"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT email, phone, password_hash, name, created_at FROM users WHERE phone = ?", (phone,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "email": row["email"],
            "phone": row["phone"],
            "password_hash": row["password_hash"],
            "name": row["name"],
            "created_at": row["created_at"]
        }
    return None

def create_user_with_phone(email: str, password_hash: str, phone: str, name: str = "") -> dict:
    """创建带手机号的用户"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO users (email, phone, password_hash, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (email, phone, password_hash, name or phone, now, now))
        conn.commit()
        return {"email": email, "phone": phone, "password_hash": password_hash, "name": name or phone, "created_at": now}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_user_phone(email: str, phone: str) -> bool:
    """为现有用户添加或更新手机号"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute("UPDATE users SET phone = ?, updated_at = ? WHERE email = ?",
                  (phone, now, email))
        conn.commit()
        result = c.rowcount > 0
        conn.close()
        return result
    except sqlite3.IntegrityError:
        conn.close()
        return False

