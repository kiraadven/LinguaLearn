"""数据库模块 - 用户和验证码存储"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_FILE = Path("data/lingualearn.db")
DB_FILE.parent.mkdir(exist_ok=True)

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    c = conn.cursor()

    # 用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # 添加 phone 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT UNIQUE")
    except Exception:
        pass

    # 验证码表
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Token 表（用于登录）
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # 用户配置表（保存样式和布局配置）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    conn.commit()
    conn.close()

# ===== USER 操作 =====

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
    c.execute("SELECT email, password_hash, name, created_at FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "email": row["email"],
            "password_hash": row["password_hash"],
            "name": row["name"],
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

# ===== 验证码操作 =====

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

def delete_verification_code(email: str) -> bool:
    """删除验证码"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

# ===== Token 操作 =====

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

# ===== 用户配置操作 =====

def save_user_config(email: str, config_json: str) -> bool:
    """保存或更新用户配置"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT OR REPLACE INTO user_configs (email, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (email, config_json, now, now))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_user_config(email: str) -> str:
    """获取用户配置"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT config_json FROM user_configs WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row["config_json"] if row else None

# 初始化数据库
init_db()
