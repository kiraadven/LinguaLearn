"""Membership plan/status helpers extracted from api.py."""
from datetime import datetime
from typing import Optional

from fastapi import Request

import core.db as database

_FREE_DAILY_VIDEO_LIMIT = 3
_MEMBER_DAILY_VIDEO_LIMIT = 15
_FREE_MAX_VIDEO_SECONDS = 5 * 60
_MEMBER_MAX_VIDEO_SECONDS = 20 * 60

_DEFAULT_VIDEO_WATERMARK = {
    "text": "LinguaLearn",
    "position": {"x": 0.33, "y": 0.16},     # 居中偏上（左上角锚点）
    "size": {"w": 0.34, "h": 0.12},         # 放大水印显示区域
    "rotation": 30,
    "opacity": 0.20,                         # 20%
    "font_size": 120,
}

_MEMBERSHIP_PLAN_SETS = {
    "cn": [
        {"code": "cn_day", "label": "1天体验价", "days": 1, "price": 3.0, "currency": "CNY", "period": "day", "auto_renew": False, "trial_once": True},
        {"code": "cn_week", "label": "连续包周", "days": 7, "price": 21.0, "currency": "CNY", "period": "week", "auto_renew": True, "trial_once": False},
        {"code": "cn_month", "label": "连续包月", "days": 30, "price": 75.0, "currency": "CNY", "period": "month", "auto_renew": True, "trial_once": False},
        {"code": "cn_year", "label": "连续包年", "days": 365, "price": 730.0, "currency": "CNY", "period": "year", "auto_renew": True, "trial_once": False},
    ],
    "intl": [
        {"code": "intl_day", "label": "1-day Trial", "days": 1, "price": 0.42, "currency": "USD", "period": "day", "auto_renew": False, "trial_once": True},
        {"code": "intl_week", "label": "Weekly", "days": 7, "price": 2.94, "currency": "USD", "period": "week", "auto_renew": True, "trial_once": False},
        {"code": "intl_month", "label": "Monthly", "days": 30, "price": 10.5, "currency": "USD", "period": "month", "auto_renew": True, "trial_once": False},
        {"code": "intl_year", "label": "Yearly", "days": 365, "price": 102.2, "currency": "USD", "period": "year", "auto_renew": True, "trial_once": False},
    ],
}
_PLAN_BY_CODE = {p["code"]: p for plans in _MEMBERSHIP_PLAN_SETS.values() for p in plans}


def _country_bucket(country_code: str) -> str:
    code = (country_code or "").strip().upper()
    return "cn" if code in {"CN", "CHN", "CHINA", "中国"} else "intl"


def _detect_country_code(request: Optional[Request], fallback: str = "CN") -> str:
    if not request:
        return fallback
    # Common proxy/CDN headers
    for key in ("cf-ipcountry", "x-country-code", "x-vercel-ip-country"):
        v = request.headers.get(key)
        if v:
            return v.strip().upper()
    return fallback


def _get_plan_catalog(country_code: str, trial_used: bool = False) -> list:
    bucket = _country_bucket(country_code)
    plans = []
    for p in _MEMBERSHIP_PLAN_SETS[bucket]:
        item = dict(p)
        item["available"] = not (item.get("trial_once") and trial_used)
        plans.append(item)
    return plans


def _membership_limits(tier: str) -> dict:
    is_member = tier == "member"
    return {
        "daily_video_limit": _MEMBER_DAILY_VIDEO_LIMIT if is_member else _FREE_DAILY_VIDEO_LIMIT,
        "max_video_seconds": _MEMBER_MAX_VIDEO_SECONDS if is_member else _FREE_MAX_VIDEO_SECONDS,
        "can_remove_default_watermark": is_member,
        "can_customize_video_watermark": is_member,
        "can_customize_doc_watermark": is_member,
        "premium_badge": is_member,
        "storage_gb": 128 if is_member else 10,
        "subtitle_style_tier": "advanced" if is_member else "basic",
        "ai_tutor_assist": is_member,
    }


def _build_membership_status(email: str, country_code: str = "CN") -> dict:
    rec = database.get_user_membership(email) or {}
    tier = "member" if (rec.get("tier") == "member" and rec.get("status") == "active") else "free"
    limits = _membership_limits(tier)
    used_today = database.get_today_usage(email)
    daily_limit = limits["daily_video_limit"]
    remaining = None if daily_limit is None else max(0, daily_limit - used_today)
    trial_used = bool(rec.get("trial_used", 0))
    plans = _get_plan_catalog(country_code or rec.get("country_code") or "CN", trial_used)
    return {
        "tier": tier,
        "status": rec.get("status", "inactive"),
        "provider": rec.get("provider"),
        "plan_code": rec.get("plan_code"),
        "plan_name": rec.get("plan_name"),
        "started_at": rec.get("started_at"),
        "expires_at": rec.get("expires_at"),
        "auto_renew": bool(rec.get("auto_renew", 0)),
        "trial_used": trial_used,
        "badge_unlocked": bool(rec.get("badge_unlocked", 0)),
        "doc_watermark_text": rec.get("doc_watermark_text") or "LinguaLearn",
        "doc_watermark_enabled": bool(rec.get("doc_watermark_enabled", 1)),
        "usage": {
            "day": datetime.now().strftime('%Y-%m-%d'),
            "videos_generated_today": used_today,
            "remaining_today": remaining,
        },
        "limits": limits,
        "plans": plans,
        "premium_logo": "/premium-badge.svg",
    }
