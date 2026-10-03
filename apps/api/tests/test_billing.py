from __future__ import annotations

import functools
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

import httpx
import pytest

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_api.routers import billing as billing_router
from vigilo_core.config import config
from vigilo_core.models import VerificationMethod
from vigilo_identity.repository import get_account_by_id, get_or_create_account
from vigilo_persistence import session_scope
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    issue_ownership_proof,
    mark_proof_verified,
)

_SECRET = "whsec_test"
_PRICE = "price_pro_test"


@pytest.fixture(autouse=True)
def _stripe_configured(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", _PRICE)
    monkeypatch.setenv("WEB_APP_URL", "https://vigilo.test")
    config.cache_clear()
    yield
    config.cache_clear()


def _signed_header(raw_body: bytes) -> str:
    timestamp = int(time.time())
    signature = hmac.new(
        _SECRET.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


def _subscription_event(
    event_type: str,
    subscription_id: str,
    email: str,
    status: str = "active",
    price: str = _PRICE,
) -> bytes:
    return json.dumps(
        {
            "type": event_type,
            "data": {
                "object": {
                    "id": subscription_id,
                    "status": status,
                    "metadata": {"vigilo_account_email": email},
                    "items": {
                        "data": [{"price": {"id": price}, "current_period_end": 1_792_022_400}]
                    },
                }
            },
        }
    ).encode()


async def _post_webhook(client, raw_body: bytes, header: str | None = None):
    return await client.post(
        "/v1/billing/webhook",
        content=raw_body,
        headers={"Stripe-Signature": header or _signed_header(raw_body)},
    )


async def test_checkout_requires_authentication(client):
    response = await client.post("/v1/billing/checkout", json={"plan_id": "pro"})
    assert response.status_code == 401


async def test_checkout_returns_a_stripe_url_for_pro(client, monkeypatch):
    captured: dict = {}

    def stripe(request: httpx.Request) -> httpx.Response:
        captured["form"] = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        return httpx.Response(200, json={"url": "https://checkout.stripe.com/c/pay/cs_test"})

    monkeypatch.setattr(
        billing_router,
        "create_checkout_url",
        functools.partial(
            billing_router.create_checkout_url, transport=httpx.MockTransport(stripe)
        ),
    )
    async with session_scope() as session:
        account = await get_or_create_account(session, email="checkout@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/checkout", json={"plan_id": "pro"})

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test"
    form = captured["form"]
    assert form["line_items[0][price]"] == _PRICE
    assert form["subscription_data[metadata][vigilo_account_email]"] == "checkout@example.com"
    assert form["success_url"] == "https://vigilo.test/dashboard/billing?checkout=success"
    assert form["cancel_url"] == "https://vigilo.test/dashboard/billing"


async def test_checkout_for_an_unpriced_plan_returns_500(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="freecheckout@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/checkout", json={"plan_id": "free"})

    assert response.status_code == 500
    assert response.json()["code"] == "BILLING_PROVIDER_ERROR"


async def test_list_plans_is_public(client):
    app.dependency_overrides.pop(require_account, None)
    response = await client.get("/v1/plans")
    assert response.status_code == 200


async def test_list_plans_lists_free_and_pro_with_prices(client):
    response = await client.get("/v1/plans")
    body = {plan["plan_id"]: plan for plan in response.json()}
    assert set(body) == {"free", "pro"}
    assert (body["free"]["price_cents"], body["pro"]["price_cents"]) == (0, 2900)
    assert body["pro"]["currency"] == "usd"


async def test_list_plans_reflects_the_free_plans_actual_limits(client):
    response = await client.get("/v1/plans")
    free = next(plan for plan in response.json() if plan["plan_id"] == "free")
    assert free["targets_limit"] == 1
    assert free["scans_per_month_limit"] == 3
    assert free["active_tier_allowed"] is False


async def test_webhook_rejects_an_invalid_signature(client):
    raw_body = _subscription_event("customer.subscription.created", "sub_x", "a@example.com")
    response = await _post_webhook(client, raw_body, header="t=1,v1=not-the-real-signature")
    assert response.status_code == 401


async def test_webhook_ignores_an_unrecognized_event_type(client):
    raw_body = json.dumps({"type": "invoice.paid", "data": {"object": {}}}).encode()
    response = await _post_webhook(client, raw_body)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_ignores_another_products_subscription(client):
    """NEXORA's own plans share the Stripe account and arrive here too."""
    async with session_scope() as session:
        await get_or_create_account(session, email="shared-account@example.com")
    raw_body = _subscription_event(
        "customer.subscription.created",
        "sub_nexora",
        "shared-account@example.com",
        price="price_nexora_pro",
    )
    response = await _post_webhook(client, raw_body)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_ignores_an_event_for_an_unknown_account(client):
    raw_body = _subscription_event(
        "customer.subscription.created", "sub_unknown", "never-signed-up@example.com"
    )
    response = await _post_webhook(client, raw_body)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


async def test_webhook_upgrades_a_known_account_to_pro(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="webhook-upgrade@example.com")

    raw_body = _subscription_event(
        "customer.subscription.created", "sub_webhook_upgrade", "webhook-upgrade@example.com"
    )
    response = await _post_webhook(client, raw_body)

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    async with session_scope() as session:
        updated = await get_account_by_id(session, account.id)
    assert updated.plan_id == "pro"


async def test_a_plan_upgrade_via_webhook_immediately_unlocks_active_tier(client):
    """A verified-owner account on the (default) Free plan stays passive;
    a real signed webhook — the same one Stripe sends — upgrades the
    account; the identical scan request is then granted active tier, with
    no other state having changed."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="live-upgrade@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)
        await mark_proof_verified(session, proof.id)

    scan_request = {
        "target_url": "https://example.com",
        "email": "live-upgrade@example.com",
        "requested_tier": "active",
    }

    before = await client.post("/v1/scans", json=scan_request)
    assert before.status_code == 202
    assert before.json()["granted_tier"] == "passive"

    raw_body = _subscription_event(
        "customer.subscription.created", "sub_live_upgrade", "live-upgrade@example.com"
    )
    webhook_response = await _post_webhook(client, raw_body)
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "applied"

    after = await client.post("/v1/scans", json=scan_request)
    assert after.status_code == 202
    assert after.json()["granted_tier"] == "active"


async def test_webhook_cancellation_resets_the_account_to_free(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="webhook-cancel@example.com")

    await _post_webhook(
        client,
        _subscription_event(
            "customer.subscription.created", "sub_webhook_cancel", "webhook-cancel@example.com"
        ),
    )
    response = await _post_webhook(
        client,
        _subscription_event(
            "customer.subscription.deleted",
            "sub_webhook_cancel",
            "webhook-cancel@example.com",
            status="canceled",
        ),
    )

    assert response.status_code == 200
    async with session_scope() as session:
        updated = await get_account_by_id(session, account.id)
    assert updated.plan_id == "free"


async def test_portal_is_404_without_a_subscription(client):
    async with session_scope() as session:
        account = await get_or_create_account(session, email="portal-none@example.com")
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/portal")

    assert response.status_code == 404


async def test_portal_opens_for_the_callers_own_subscription(client, monkeypatch):
    seen: list[str] = []

    def stripe(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.startswith("/v1/subscriptions/"):
            return httpx.Response(200, json={"customer": "cus_portal"})
        return httpx.Response(200, json={"url": "https://billing.stripe.com/p/sess"})

    monkeypatch.setattr(
        billing_router,
        "create_portal_url",
        functools.partial(billing_router.create_portal_url, transport=httpx.MockTransport(stripe)),
    )
    async with session_scope() as session:
        account = await get_or_create_account(session, email="portal-owner@example.com")
    await _post_webhook(
        client,
        _subscription_event(
            "customer.subscription.created", "sub_portal_owner", "portal-owner@example.com"
        ),
    )
    app.dependency_overrides[require_account] = lambda: account

    response = await client.post("/v1/billing/portal")

    assert response.status_code == 200
    assert response.json()["portal_url"] == "https://billing.stripe.com/p/sess"
    assert seen[0] == "/v1/subscriptions/sub_portal_owner"
