"""Job and profile-related operations."""
from datetime import datetime

from .connection import get_db

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

