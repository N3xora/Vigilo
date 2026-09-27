"""Stripe integration (docs/modules.md §7's `billing` adapter). No SDK
dependency, matching `mail.py`'s "a single request is all the provider
needs" posture.

Webhook signatures: Stripe's `Stripe-Signature` header is
`t=<unix-timestamp>,v1=<hex-hmac-sha256>[,v1=...]`, computed over
`f"{t}.{raw_body}"` with the endpoint's signing secret. Verified exactly as
Stripe documents it, including the timestamp tolerance that stops a
captured request being replayed later.

Checkout: `create_checkout_url()` creates a hosted Checkout Session with
one server-to-server call. `transport` is the same `httpx.MockTransport`
dependency-injection seam `mail.py` uses, so no test talks to Stripe.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from vigilo_core.config import config
from vigilo_integrations.errors import BillingProviderError

_CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"
_REQUEST_TIMEOUT = 15.0
# Stripe's own libraries default to five minutes.
_SIGNATURE_TOLERANCE_SECONDS = 300


def price_to_plan() -> dict[str, str]:
    """Stripe price id → Vigilo plan id, for `interpret_webhook_event()`."""
    cfg = config()
    return {cfg.stripe_price_id_pro: "pro"} if cfg.stripe_price_id_pro else {}


def verify_webhook_signature(
    raw_body: bytes, signature_header: str, now: float | None = None
) -> bool:
    cfg = config()
    if not cfg.stripe_webhook_secret:
        raise BillingProviderError("Stripe is not configured (missing webhook secret)")

    timestamp: str | None = None
    signatures: list[str] = []
    for item in signature_header.split(","):
        key, sep, value = item.strip().partition("=")
        if not sep:
            continue
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        return False

    try:
        age = (time.time() if now is None else now) - int(timestamp)
    except ValueError:
        return False
    if abs(age) > _SIGNATURE_TOLERANCE_SECONDS:
        return False

    expected = hmac.new(
        cfg.stripe_webhook_secret.encode(),
        timestamp.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def parse_webhook_event(raw_body: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BillingProviderError("Stripe webhook body was not valid JSON") from exc


async def create_checkout_url(
    plan_id: str,
    account_email: str,
    account_reference: str,
    success_url: str,
    cancel_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    cfg = config()
    if not cfg.stripe_secret_key:
        raise BillingProviderError("Stripe is not configured (missing secret key)")

    price_id = cfg.stripe_price_id_pro if plan_id == "pro" else None
    if not price_id:
        raise BillingProviderError("no Stripe price configured for this plan", plan_id=plan_id)

    form = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "customer_email": account_email,
        "client_reference_id": account_reference,
        # Copied by Stripe onto the Subscription, so every
        # customer.subscription.* event carries it back to the webhook —
        # and marks the subscription as Vigilo's on a shared Stripe account.
        "subscription_data[metadata][vigilo_account_email]": account_email,
        "subscription_data[metadata][vigilo_account_id]": account_reference,
        "success_url": success_url,
        "cancel_url": cancel_url,
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
            response = await client.post(
                _CHECKOUT_SESSIONS_URL, data=form, auth=(cfg.stripe_secret_key, "")
            )
    except httpx.HTTPError as exc:
        raise BillingProviderError("Stripe request failed") from exc

    if response.status_code >= 400:
        raise BillingProviderError(
            "Stripe rejected the checkout session", status_code=response.status_code
        )
    url = response.json().get("url")
    if not url:
        raise BillingProviderError("Stripe returned no checkout URL")
    return url
