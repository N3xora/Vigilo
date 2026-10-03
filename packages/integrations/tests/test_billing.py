from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs

import httpx
import pytest

from vigilo_core.config import config
from vigilo_integrations.billing import (
    create_checkout_url,
    create_portal_url,
    parse_webhook_event,
    price_to_plan,
    verify_webhook_signature,
)
from vigilo_integrations.errors import BillingProviderError

_SECRET = "whsec_test"
_NOW = 1_700_000_000


@pytest.fixture(autouse=True)
def _stripe_configured(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_pro")
    config.cache_clear()
    yield
    config.cache_clear()


def _signed_header(raw_body: bytes, timestamp: int = _NOW, secret: str = _SECRET) -> str:
    signature = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_accepts_a_valid_signature():
    raw_body = b'{"type":"customer.subscription.created"}'
    assert verify_webhook_signature(raw_body, _signed_header(raw_body), now=_NOW) is True


def test_accepts_when_any_of_several_v1_signatures_matches():
    """Stripe sends one v1 per active secret while a secret is being rolled."""
    raw_body = b"{}"
    header = _signed_header(raw_body).replace("v1=", "v1=deadbeef,v1=")
    assert verify_webhook_signature(raw_body, header, now=_NOW) is True


def test_rejects_a_tampered_body():
    header = _signed_header(b'{"status":"active"}')
    assert verify_webhook_signature(b'{"status":"canceled"}', header, now=_NOW) is False


def test_rejects_a_signature_made_with_another_secret():
    raw_body = b"{}"
    header = _signed_header(raw_body, secret="whsec_other")
    assert verify_webhook_signature(raw_body, header, now=_NOW) is False


def test_rejects_a_replayed_old_request():
    raw_body = b"{}"
    header = _signed_header(raw_body, timestamp=_NOW - 301)
    assert verify_webhook_signature(raw_body, header, now=_NOW) is False


@pytest.mark.parametrize("header", ["", "not-a-valid-header", "t=abc,v1=00", "t=1700000000"])
def test_rejects_a_malformed_header(header):
    assert verify_webhook_signature(b"{}", header, now=_NOW) is False


def test_raises_when_the_webhook_secret_is_unset(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    config.cache_clear()
    with pytest.raises(BillingProviderError):
        verify_webhook_signature(b"{}", "t=1,v1=abc")


def test_parse_webhook_event_returns_the_decoded_payload():
    raw_body = json.dumps({"type": "customer.subscription.created"}).encode()
    assert parse_webhook_event(raw_body) == {"type": "customer.subscription.created"}


def test_parse_webhook_event_raises_on_invalid_json():
    with pytest.raises(BillingProviderError):
        parse_webhook_event(b"not json")


def test_price_to_plan_maps_the_configured_price(monkeypatch):
    assert price_to_plan() == {"price_pro": "pro"}
    monkeypatch.delenv("STRIPE_PRICE_ID_PRO", raising=False)
    config.cache_clear()
    assert price_to_plan() == {}


def _checkout(**kwargs):
    defaults = {
        "plan_id": "pro",
        "account_email": "owner@example.com",
        "account_reference": "account-ref-123",
        "success_url": "https://app.test/dashboard/billing?checkout=success",
        "cancel_url": "https://app.test/dashboard/billing",
    }
    return create_checkout_url(**(defaults | kwargs))


async def test_creates_a_subscription_checkout_session():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["form"] = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        return httpx.Response(200, json={"url": "https://checkout.stripe.com/c/pay/cs_test"})

    url = await _checkout(transport=httpx.MockTransport(handler))

    assert url == "https://checkout.stripe.com/c/pay/cs_test"
    assert captured["url"] == "https://api.stripe.com/v1/checkout/sessions"
    assert captured["auth"].startswith("Basic ")
    form = captured["form"]
    assert form["mode"] == "subscription"
    assert form["line_items[0][price]"] == "price_pro"
    assert form["customer_email"] == "owner@example.com"
    assert form["subscription_data[metadata][vigilo_account_email]"] == "owner@example.com"
    assert form["subscription_data[metadata][vigilo_account_id]"] == "account-ref-123"
    assert form["success_url"].endswith("?checkout=success")


async def test_raises_when_stripe_rejects_the_session():
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={"error": {}}))
    with pytest.raises(BillingProviderError):
        await _checkout(transport=transport)


async def test_raises_on_a_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(BillingProviderError):
        await _checkout(transport=httpx.MockTransport(handler))


async def test_raises_when_the_secret_key_is_unset(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    config.cache_clear()
    with pytest.raises(BillingProviderError):
        await _checkout()


@pytest.mark.parametrize("plan_id", ["free", "builder", "nonsense"])
async def test_raises_for_a_plan_without_a_stripe_price(plan_id):
    with pytest.raises(BillingProviderError):
        await _checkout(plan_id=plan_id)


def _stripe_portal(subscription_status: int = 200, portal_status: int = 200):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.startswith("/v1/subscriptions/"):
            return httpx.Response(subscription_status, json={"customer": "cus_123"})
        return httpx.Response(portal_status, json={"url": "https://billing.stripe.com/p/sess"})

    return calls, httpx.MockTransport(handler)


async def test_creates_a_portal_session_for_the_subscriptions_customer():
    calls, transport = _stripe_portal()

    url = await create_portal_url("sub_1", "https://app.test/billing", transport=transport)

    assert url == "https://billing.stripe.com/p/sess"
    assert calls[0].url.path == "/v1/subscriptions/sub_1"
    form = {k: v[0] for k, v in parse_qs(calls[1].content.decode()).items()}
    assert form == {"customer": "cus_123", "return_url": "https://app.test/billing"}


async def test_passes_a_configured_portal_configuration(monkeypatch):
    monkeypatch.setenv("STRIPE_PORTAL_CONFIGURATION_ID", "bpc_123")
    config.cache_clear()
    calls, transport = _stripe_portal()

    await create_portal_url("sub_1", "https://app.test/billing", transport=transport)

    assert parse_qs(calls[1].content.decode())["configuration"] == ["bpc_123"]


@pytest.mark.parametrize("subscription_status,portal_status", [(404, 200), (200, 400)])
async def test_portal_raises_when_stripe_refuses(subscription_status, portal_status):
    _, transport = _stripe_portal(subscription_status, portal_status)
    with pytest.raises(BillingProviderError):
        await create_portal_url("sub_1", "https://app.test/billing", transport=transport)


async def test_yearly_checkout_uses_the_yearly_price(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_monthly")
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO_YEARLY", "price_yearly")
    config.cache_clear()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"url": "https://checkout.stripe.test/s"})

    await _checkout(interval="year", transport=httpx.MockTransport(handler))
    assert "price_yearly" in captured["body"]
    assert price_to_plan() == {"price_monthly": "pro", "price_yearly": "pro"}
