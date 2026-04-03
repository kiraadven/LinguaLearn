"""User config and presets operations."""
from datetime import datetime

from .connection import get_db

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

