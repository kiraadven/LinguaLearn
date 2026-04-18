"""Membership and payment routes."""

from datetime import datetime
import hashlib
import hmac
import json
import uuid
from typing import Callable

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse


def _verify_stripe_signature(raw_body: bytes, sig_header: str, secret: str) -> bool:
    if not secret:
        return True
    try:
        pieces = {}
        for part in (sig_header or "").split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                pieces.setdefault(k.strip(), []).append(v.strip())
        ts = pieces.get("t", [None])[0]
        sigs = pieces.get("v1", [])
        if not ts or not sigs:
            return False
        signed_payload = f"{ts}.{raw_body.decode('utf-8')}"
        expected = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, s) for s in sigs)
    except Exception:
        return False


def build_membership_router(
    *,
    database,
    config,
    require_user: Callable,
    detect_country_code: Callable,
    build_membership_status: Callable,
    plan_by_code: dict,
    get_stripe_price_id: Callable[[str], str],
    activate_membership_for_user: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/membership/status")
    async def membership_status(request: Request, current_user: dict = Depends(require_user)):
        country_code = detect_country_code(request)
        return build_membership_status(current_user["email"], country_code=country_code)

    @router.post("/api/membership/preferences")
    async def update_membership_preferences(
        request: Request,
        current_user: dict = Depends(require_user),
    ):
        body = await request.json()
        rec = build_membership_status(current_user["email"], country_code=detect_country_code(request))
        if rec["tier"] != "member":
            raise HTTPException(403, "仅会员可自定义文稿水印")

        enabled = bool(body.get("doc_watermark_enabled", True))
        text = str(body.get("doc_watermark_text", "LinguaLearn")).strip()[:64]
        if enabled and not text:
            text = "LinguaLearn"
        database.update_user_membership(
            current_user["email"],
            doc_watermark_enabled=1 if enabled else 0,
            doc_watermark_text=text,
        )
        return build_membership_status(current_user["email"], country_code=detect_country_code(request))

    @router.post("/api/membership/checkout/stripe")
    async def create_stripe_checkout(
        request: Request,
        current_user: dict = Depends(require_user),
    ):
        if not config.STRIPE_SECRET_KEY:
            raise HTTPException(400, "未配置 STRIPE_SECRET_KEY")

        body = await request.json()
        plan_code = str(body.get("plan_code", "")).strip()
        plan = plan_by_code.get(plan_code)
        if not plan:
            raise HTTPException(400, "套餐不存在")

        country_code = (detect_country_code(request) or "CN").upper()
        rec = build_membership_status(current_user["email"], country_code=country_code)
        if plan.get("trial_once") and rec.get("trial_used"):
            raise HTTPException(400, "1天体验价每个账号仅可使用一次")

        price_id = get_stripe_price_id(plan_code)
        if not price_id:
            raise HTTPException(400, f"套餐 {plan_code} 尚未配置 Stripe Price ID")

        order_id = f"ord_{uuid.uuid4().hex[:24]}"
        success_url = body.get("success_url") or f"{config.APP_BASE_URL}/#/profile?membership=success"
        cancel_url = body.get("cancel_url") or f"{config.APP_BASE_URL}/#/profile?membership=cancel"

        mode = "payment" if plan.get("period") == "day" else "subscription"
        payload = [
            ("mode", mode),
            ("line_items[0][price]", price_id),
            ("line_items[0][quantity]", "1"),
            ("success_url", success_url),
            ("cancel_url", cancel_url),
            ("client_reference_id", current_user["email"]),
            ("metadata[order_id]", order_id),
            ("metadata[email]", current_user["email"]),
            ("metadata[plan_code]", plan_code),
            ("metadata[country_code]", country_code),
        ]
        if mode == "subscription":
            payload.extend(
                [
                    ("subscription_data[metadata][order_id]", order_id),
                    ("subscription_data[metadata][plan_code]", plan_code),
                    ("subscription_data[metadata][email]", current_user["email"]),
                ]
            )

        resp = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            auth=(config.STRIPE_SECRET_KEY, ""),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise HTTPException(400, f"Stripe 创建结算失败: {resp.text[:300]}")
        sd = resp.json()
        checkout_url = sd.get("url")
        if not checkout_url:
            raise HTTPException(400, "Stripe 未返回支付链接")

        database.save_membership_order(
            order_id=order_id,
            email=current_user["email"],
            provider="stripe",
            plan_code=plan_code,
            currency=plan["currency"],
            amount=plan["price"],
            status="pending",
            checkout_url=checkout_url,
            subscription_id=sd.get("subscription"),
            payload_json=json.dumps(sd, ensure_ascii=False),
        )
        return {
            "order_id": order_id,
            "provider": "stripe",
            "checkout_url": checkout_url,
            "session_id": sd.get("id"),
        }

    @router.post("/api/payments/stripe/webhook")
    async def stripe_webhook(request: Request):
        raw = await request.body()
        sig = request.headers.get("stripe-signature", "")
        if not _verify_stripe_signature(raw, sig, config.STRIPE_WEBHOOK_SECRET):
            raise HTTPException(400, "Stripe 签名校验失败")

        event = json.loads(raw.decode("utf-8"))
        typ = event.get("type")
        obj = event.get("data", {}).get("object", {})

        if typ == "checkout.session.completed":
            meta = obj.get("metadata", {}) or {}
            order_id = meta.get("order_id")
            order = database.get_membership_order(order_id) if order_id else None
            if order:
                sub_id = obj.get("subscription") or order.get("subscription_id")
                database.update_membership_order(
                    order_id,
                    status="paid",
                    subscription_id=sub_id,
                    payload_json=json.dumps(obj, ensure_ascii=False),
                )
                activate_membership_for_user(
                    email=order["email"],
                    plan_code=order["plan_code"],
                    provider="stripe",
                    subscription_id=sub_id,
                    customer_id=obj.get("customer"),
                    country_code=(meta.get("country_code") or "CN"),
                )

        elif typ == "invoice.paid":
            sub_id = obj.get("subscription")
            if sub_id:
                order = database.get_membership_order_by_subscription("stripe", sub_id)
                if order:
                    database.update_membership_order(
                        order["order_id"],
                        status="paid",
                        payload_json=json.dumps(obj, ensure_ascii=False),
                    )
                    activate_membership_for_user(
                        email=order["email"],
                        plan_code=order["plan_code"],
                        provider="stripe",
                        subscription_id=sub_id,
                        customer_id=obj.get("customer"),
                        country_code=(database.get_user_membership(order["email"]) or {}).get("country_code", "CN"),
                    )

        elif typ in ("customer.subscription.updated", "customer.subscription.deleted"):
            sub_id = obj.get("id")
            if sub_id:
                order = database.get_membership_order_by_subscription("stripe", sub_id)
                if order:
                    is_cancelled = typ == "customer.subscription.deleted" or obj.get("cancel_at_period_end")
                    if is_cancelled:
                        database.update_user_membership(order["email"], auto_renew=0, status="cancelled")

        return {"received": True}

    @router.post("/api/membership/checkout/alipay")
    async def create_alipay_checkout(
        request: Request,
        current_user: dict = Depends(require_user),
    ):
        body = await request.json()
        plan_code = str(body.get("plan_code", "")).strip()
        plan = plan_by_code.get(plan_code)
        if not plan:
            raise HTTPException(400, "套餐不存在")

        rec = build_membership_status(current_user["email"], country_code=detect_country_code(request))
        if plan.get("trial_once") and rec.get("trial_used"):
            raise HTTPException(400, "1天体验价每个账号仅可使用一次")

        if not (config.ALIPAY_APP_ID and config.ALIPAY_PRIVATE_KEY and config.ALIPAY_PUBLIC_KEY):
            raise HTTPException(400, "未配置支付宝签约参数（ALIPAY_APP_ID/ALIPAY_PRIVATE_KEY/ALIPAY_PUBLIC_KEY）")

        try:
            from alipay import AliPay
        except Exception:
            raise HTTPException(500, "请先安装 python-alipay-sdk 才能启用支付宝支付")

        order_id = f"ali_{uuid.uuid4().hex[:24]}"
        alipay = AliPay(
            appid=config.ALIPAY_APP_ID,
            app_notify_url=config.ALIPAY_NOTIFY_URL or None,
            app_private_key_string=config.ALIPAY_PRIVATE_KEY,
            alipay_public_key_string=config.ALIPAY_PUBLIC_KEY,
            sign_type="RSA2",
            debug=("sandbox" in (config.ALIPAY_GATEWAY or "")),
        )

        pay_str = alipay.api_alipay_trade_wap_pay(
            out_trade_no=order_id,
            total_amount=str(plan["price"]),
            subject=f"LinguaLearn 会员 - {plan['label']}",
            return_url=config.ALIPAY_RETURN_URL or f"{config.APP_BASE_URL}/#/profile?membership=success",
            notify_url=config.ALIPAY_NOTIFY_URL or f"{config.APP_BASE_URL}/api/payments/alipay/webhook",
        )
        checkout_url = f"{config.ALIPAY_GATEWAY}?{pay_str}"

        database.save_membership_order(
            order_id=order_id,
            email=current_user["email"],
            provider="alipay",
            plan_code=plan_code,
            currency=plan["currency"],
            amount=plan["price"],
            status="pending",
            checkout_url=checkout_url,
            payload_json=json.dumps({"pay_str": pay_str}, ensure_ascii=False),
        )
        return {"order_id": order_id, "provider": "alipay", "checkout_url": checkout_url}

    @router.post("/api/payments/alipay/webhook")
    async def alipay_webhook(request: Request):
        form = dict(await request.form())
        sign = form.pop("sign", None)
        form.pop("sign_type", None)
        if not sign:
            raise HTTPException(400, "缺少签名")

        try:
            from alipay import AliPay
        except Exception:
            raise HTTPException(500, "服务端未安装 python-alipay-sdk")

        alipay = AliPay(
            appid=config.ALIPAY_APP_ID,
            app_notify_url=config.ALIPAY_NOTIFY_URL or None,
            app_private_key_string=config.ALIPAY_PRIVATE_KEY,
            alipay_public_key_string=config.ALIPAY_PUBLIC_KEY,
            sign_type="RSA2",
            debug=("sandbox" in (config.ALIPAY_GATEWAY or "")),
        )
        if not alipay.verify(form, sign):
            raise HTTPException(400, "支付宝签名校验失败")

        order_id = form.get("out_trade_no")
        trade_status = form.get("trade_status")
        order = database.get_membership_order(order_id) if order_id else None
        if order and trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            agreement_no = form.get("agreement_no") or form.get("trade_no")
            database.update_membership_order(
                order_id,
                status="paid",
                subscription_id=agreement_no,
                payload_json=json.dumps(form, ensure_ascii=False),
            )
            activate_membership_for_user(
                email=order["email"],
                plan_code=order["plan_code"],
                provider="alipay",
                subscription_id=agreement_no,
                country_code=(database.get_user_membership(order["email"]) or {}).get("country_code", "CN"),
            )
        elif order and trade_status:
            database.update_membership_order(order_id, status="failed", payload_json=json.dumps(form, ensure_ascii=False))

        return PlainTextResponse("success")

    @router.post("/api/membership/cancel-auto-renew")
    async def cancel_auto_renew(
        request: Request,
        current_user: dict = Depends(require_user),
    ):
        rec = database.get_user_membership(current_user["email"]) or {}
        if rec.get("tier") != "member" or rec.get("status") != "active":
            raise HTTPException(400, "当前不是有效会员")

        provider = rec.get("provider")
        sub_id = rec.get("subscription_id")
        if provider == "stripe" and sub_id and config.STRIPE_SECRET_KEY:
            resp = requests.post(
                f"https://api.stripe.com/v1/subscriptions/{sub_id}",
                data={"cancel_at_period_end": "true"},
                auth=(config.STRIPE_SECRET_KEY, ""),
                timeout=20,
            )
            if resp.status_code >= 400:
                raise HTTPException(400, f"Stripe 取消自动续费失败: {resp.text[:300]}")

        database.update_user_membership(current_user["email"], auto_renew=0, status="cancelled")
        return {"status": "ok", "auto_renew": False}

    return router

