"""Organisation-owned accounts, exercised through the real `require_account`
(only the Clerk JWT verification is stubbed — it is covered in test_auth.py).
"""

from __future__ import annotations

import httpx
import pytest

from vigilo_api import deps
from vigilo_api.auth import ClerkClaims
from vigilo_api.routers import billing as billing_router
from vigilo_core.config import config


def _as(monkeypatch, **claims) -> dict[str, str]:
    monkeypatch.setattr(deps, "verify_clerk_jwt", lambda token: ClerkClaims(**claims))
    return {"Authorization": "Bearer stub"}


async def test_a_session_inside_an_org_gets_the_org_account(client, monkeypatch):
    headers = _as(
        monkeypatch,
        user_id="user_a",
        email="alice@example.com",
        org_id="org_1",
        org_role="org:admin",
    )

    body = (await client.get("/v1/me", headers=headers)).json()

    assert body["organization_id"] == "org_1"
    assert body["email"] == "alice@example.com"


async def test_every_member_of_the_org_shares_one_account(client, monkeypatch):
    alice = _as(monkeypatch, user_id="user_a", email="alice@example.com", org_id="org_1")
    first = (await client.get("/v1/me", headers=alice)).json()
    bob = _as(monkeypatch, user_id="user_b", email="bob@example.com", org_id="org_1")
    second = (await client.get("/v1/me", headers=bob)).json()

    assert first["account_id"] == second["account_id"]
    assert second["email"] == "alice@example.com"  # the contact is the first member, not the caller


async def test_a_different_org_gets_a_different_account(client, monkeypatch):
    one = _as(monkeypatch, user_id="user_a", email="a@example.com", org_id="org_1")
    first = (await client.get("/v1/me", headers=one)).json()
    two = _as(monkeypatch, user_id="user_a", email="a@example.com", org_id="org_2")
    second = (await client.get("/v1/me", headers=two)).json()

    assert first["account_id"] != second["account_id"]


async def test_a_session_without_an_org_keeps_the_personal_account(client, monkeypatch):
    personal = _as(monkeypatch, user_id="user_a", email="alice@example.com")
    solo = (await client.get("/v1/me", headers=personal)).json()
    inside = _as(monkeypatch, user_id="user_a", email="alice@example.com", org_id="org_1")
    org = (await client.get("/v1/me", headers=inside)).json()

    assert solo["organization_id"] is None
    assert solo["account_id"] != org["account_id"]
    # Going back out of the org returns to the same personal account.
    personal = _as(monkeypatch, user_id="user_a", email="alice@example.com")
    again = (await client.get("/v1/me", headers=personal)).json()
    assert again["account_id"] == solo["account_id"]


async def test_an_org_session_without_an_email_is_rejected(client, monkeypatch):
    headers = _as(monkeypatch, user_id="user_a", email=None, org_id="org_1")

    assert (await client.get("/v1/me", headers=headers)).status_code == 401


@pytest.fixture
def stripe_ok(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_pro_test")
    monkeypatch.setenv("WEB_APP_URL", "https://vigilo.test")
    config.cache_clear()

    async def fake_checkout(plan_id, email, account_id, **kwargs):
        fake_checkout.seen = {"email": email, "account_id": account_id}
        return "https://checkout.stripe.com/c/pay/x"

    monkeypatch.setattr(billing_router, "create_checkout_url", fake_checkout)
    yield fake_checkout
    config.cache_clear()


@pytest.mark.parametrize("role", ["org:member", None])
async def test_billing_in_an_org_needs_the_admin_role(client, monkeypatch, stripe_ok, role):
    headers = _as(
        monkeypatch, user_id="user_b", email="bob@example.com", org_id="org_1", org_role=role
    )

    response = await client.post("/v1/billing/checkout", json={"plan_id": "pro"}, headers=headers)

    assert response.status_code == 403


async def test_an_org_admin_can_check_out_and_the_receipt_goes_to_the_contact(
    client, monkeypatch, stripe_ok
):
    headers = _as(
        monkeypatch,
        user_id="user_a",
        email="alice@example.com",
        org_id="org_1",
        org_role="org:admin",
    )

    response = await client.post("/v1/billing/checkout", json={"plan_id": "pro"}, headers=headers)

    assert response.status_code == 200
    assert stripe_ok.seen["email"] == "alice@example.com"


async def test_a_personal_account_can_always_check_out(client, monkeypatch, stripe_ok):
    headers = _as(monkeypatch, user_id="user_a", email="alice@example.com")

    response = await client.post("/v1/billing/checkout", json={"plan_id": "pro"}, headers=headers)

    assert response.status_code == 200
    assert isinstance(response, httpx.Response)
