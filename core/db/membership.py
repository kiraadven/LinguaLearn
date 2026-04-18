"""Membership and billing operations."""
from datetime import datetime

from .connection import get_db

def ensure_user_membership(email: str, country_code: str = 'CN') -> dict:
    """确保用户有会员记录（默认 free）"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM user_memberships WHERE email = ?", (email,))
    row = c.fetchone()
    if row:
        conn.close()
        return dict(row)

    now = datetime.now().isoformat()
    c.execute('''
        INSERT INTO user_memberships
        (email, tier, status, country_code, created_at, updated_at)
        VALUES (?, 'free', 'inactive', ?, ?, ?)
    ''', (email, country_code or 'CN', now, now))
    conn.commit()
    c.execute("SELECT * FROM user_memberships WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_membership(email: str) -> dict:
    """获取会员记录；不存在时自动创建 free 记录"""
    rec = ensure_user_membership(email)
    if not rec:
        return None
    # 自动过期处理：过期后降级为 free
    exp = rec.get("expires_at")
    if rec.get("tier") == "member" and exp:
        try:
            if datetime.fromisoformat(exp) < datetime.now():
                update_user_membership(
                    email,
                    tier='free',
                    status='expired',
                    auto_renew=0,
                    provider=None,
                    plan_code=None,
                    plan_name=None,
                    subscription_id=None,
                )
                rec = ensure_user_membership(email)
        except Exception:
            pass
    return rec

def update_user_membership(email: str, **fields) -> bool:
    """更新会员记录"""
    ensure_user_membership(email)
    conn = get_db()
    c = conn.cursor()
    allowed = {
        'tier', 'status', 'provider', 'plan_code', 'plan_name',
        'subscription_id', 'customer_id', 'country_code', 'started_at', 'expires_at',
        'auto_renew', 'trial_used', 'badge_unlocked',
        'doc_watermark_text', 'doc_watermark_enabled',
    }
    patch = {k: v for k, v in fields.items() if k in allowed}
    if not patch:
        conn.close()
        return False
    patch['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join([f"{k} = ?" for k in patch.keys()])
    values = list(patch.values()) + [email]
    try:
        c.execute(f"UPDATE user_memberships SET {set_clause} WHERE email = ?", values)
        conn.commit()
        ok = c.rowcount > 0
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB Error] update_user_membership: {e}")
        conn.close()
        return False

def mark_trial_used(email: str) -> bool:
    """标记用户已使用过 1 天体验价"""
    return update_user_membership(email, trial_used=1)

def get_today_usage(email: str, day: str = None) -> int:
    """获取当天视频生成数"""
    if day is None:
        day = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT videos_generated FROM daily_usage WHERE email = ? AND day = ?", (email, day))
    row = c.fetchone()
    conn.close()
    return int(row["videos_generated"]) if row else 0

def increment_daily_video_usage(email: str, day: str = None, step: int = 1) -> int:
    """增加当天视频生成数，返回最新数值"""
    if day is None:
        day = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, videos_generated FROM daily_usage WHERE email = ? AND day = ?", (email, day))
    row = c.fetchone()
    if row:
        new_count = int(row["videos_generated"]) + int(step)
        c.execute(
            "UPDATE daily_usage SET videos_generated = ?, updated_at = ? WHERE id = ?",
            (new_count, now, row["id"])
        )
    else:
        new_count = max(0, int(step))
        c.execute('''
            INSERT INTO daily_usage (email, day, videos_generated, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, day, new_count, now, now))
    conn.commit()
    conn.close()
    return new_count

def save_membership_order(
    order_id: str,
    email: str,
    provider: str,
    plan_code: str,
    currency: str,
    amount: float,
    status: str = 'pending',
    checkout_url: str = None,
    subscription_id: str = None,
    payload_json: str = None,
) -> bool:
    """创建/覆盖会员订单"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT OR REPLACE INTO membership_orders
            (order_id, email, provider, plan_code, currency, amount, status, checkout_url,
             subscription_id, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id, email, provider, plan_code, currency, float(amount), status,
            checkout_url, subscription_id, payload_json, now, now
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] save_membership_order: {e}")
        return False
    finally:
        conn.close()

def update_membership_order(order_id: str, **fields) -> bool:
    """更新会员订单"""
    conn = get_db()
    c = conn.cursor()
    allowed = {'status', 'checkout_url', 'subscription_id', 'payload_json'}
    patch = {k: v for k, v in fields.items() if k in allowed}
    if not patch:
        conn.close()
        return False
    patch['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join([f"{k} = ?" for k in patch.keys()])
    values = list(patch.values()) + [order_id]
    try:
        c.execute(f"UPDATE membership_orders SET {set_clause} WHERE order_id = ?", values)
        conn.commit()
        ok = c.rowcount > 0
        conn.close()
        return ok
    except Exception as e:
        print(f"[DB Error] update_membership_order: {e}")
        conn.close()
        return False

def get_membership_order(order_id: str) -> dict:
    """按订单号查询会员订单"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM membership_orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_membership_order_by_subscription(provider: str, subscription_id: str) -> dict:
    """按 provider+subscription_id 查询会员订单"""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM membership_orders WHERE provider = ? AND subscription_id = ? ORDER BY id DESC LIMIT 1",
        (provider, subscription_id)
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

