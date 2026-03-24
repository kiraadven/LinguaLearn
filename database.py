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
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # 添加 phone 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT UNIQUE")
    except Exception:
        pass

    # 添加 avatar_url 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
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

    # 命名配置预设表（每个用户可保存多个命名配置）
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_config_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')

    # Jobs 表（保存视频处理历史）
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            step INTEGER,
            step_name TEXT,
            source_lang TEXT,
            target_lang TEXT,
            video_filename TEXT,
            result_json TEXT,
            error TEXT,
            video_clips_pct INTEGER DEFAULT 0,
            video_write_pct INTEGER DEFAULT 0,
            name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (email) REFERENCES users(email)
        )
    ''')
    # 为旧表添加 name 列（若已存在则忽略）
    try:
        c.execute("ALTER TABLE jobs ADD COLUMN name TEXT")
    except Exception:
        pass

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

# ===== 命名配置预设操作 =====

def save_config_preset(email: str, name: str, config_json: str) -> int:
    """保存命名配置预设，返回新预设的 id"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO user_config_presets (email, name, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, name, config_json, now, now))
        conn.commit()
        return c.lastrowid
    except Exception as e:
        print(f"[DB Error] save_config_preset: {e}")
        return -1
    finally:
        conn.close()

def get_config_presets(email: str) -> list:
    """获取用户所有命名配置预设"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, email, name, config_json, created_at, updated_at
                 FROM user_config_presets WHERE email = ?
                 ORDER BY created_at DESC''', (email,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_config_preset(preset_id: int, email: str) -> bool:
    """删除命名配置预设（只能删除自己的）"""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM user_config_presets WHERE id = ? AND email = ?", (preset_id, email))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"[DB Error] delete_config_preset: {e}")
        return False
    finally:
        conn.close()

# ===== Jobs 操作 =====

def save_job(job_id: str, email: str, status: str, step: int, step_name: str,
             source_lang: str, target_lang: str, video_filename: str,
             result_json: str = None, error: str = None) -> bool:
    """保存或更新 Job"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT OR REPLACE INTO jobs
            (id, email, status, step, step_name, source_lang, target_lang,
             video_filename, result_json, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, email, status, step, step_name, source_lang, target_lang,
              video_filename, result_json, error, now, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] save_job: {e}")
        return False
    finally:
        conn.close()

def update_job_status(job_id: str, **fields) -> bool:
    """更新 Job 状态（status, step, step_name, error, result_json, video_clips_pct, video_write_pct）"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()

    # 白名单，只允许更新特定字段
    allowed = {'status', 'step', 'step_name', 'error', 'result_json', 'video_clips_pct', 'video_write_pct', 'name'}
    fields = {k: v for k, v in fields.items() if k in allowed}
    fields['updated_at'] = now

    if not fields:
        conn.close()
        return False

    set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [job_id]

    try:
        c.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"[DB Error] update_job_status: {e}")
        return False
    finally:
        conn.close()

def get_job(job_id: str) -> dict:
    """获取 Job 信息"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, email, status, step, step_name, source_lang, target_lang,
                 video_filename, result_json, error, video_clips_pct, video_write_pct,
                 name, created_at, updated_at FROM jobs WHERE id = ?''', (job_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_user_jobs(email: str, limit: int = 50) -> list:
    """获取用户的所有 Jobs"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, email, status, step, step_name, source_lang, target_lang,
                 video_filename, result_json, error, video_clips_pct, video_write_pct,
                 name, created_at, updated_at FROM jobs WHERE email = ?
                 ORDER BY created_at DESC LIMIT ?''', (email, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_job(job_id: str, email: str) -> bool:
    """删除 Job 记录（只能删除自己的）"""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM jobs WHERE id = ? AND email = ?", (job_id, email))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"[DB Error] delete_job: {e}")
        return False
    finally:
        conn.close()

def update_user_avatar(email: str, avatar_url: str) -> bool:
    """更新用户头像 URL"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE users SET avatar_url = ?, updated_at = ? WHERE email = ?",
              (avatar_url, now, email))
    conn.commit()
    result = c.rowcount > 0
    conn.close()
    return result

def bind_email(old_email: str, new_email: str) -> bool:
    """绑定邮箱 - 更新用户邮箱并同步 token 表"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        # 检查新邮箱是否已被使用
        c.execute("SELECT 1 FROM users WHERE email = ?", (new_email,))
        if c.fetchone():
            return False  # 新邮箱已被使用

        # 更新用户表
        c.execute("UPDATE users SET email = ?, updated_at = ? WHERE email = ?",
                  (new_email, now, old_email))

        # 同步 token 表
        c.execute("UPDATE tokens SET email = ? WHERE email = ?", (new_email, old_email))

        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"[DB Error] bind_email: {e}")
        return False
    finally:
        conn.close()
init_db()
