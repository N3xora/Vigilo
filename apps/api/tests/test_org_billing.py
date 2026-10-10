"""Billing belongs to the organisation: it subscribes, it has one Stripe
customer, and its plan limits apply to everyone acting in it."""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import parse_qs

import httpx
import pytest
import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_api.routers import billing as billing_router
from vigilo_core.config import config
from vigilo_identity.org_repository import get_org, personal_org_id, plan_id_for_org
from vigilo_identity.repository import get_account_by_id, get_or_create_account
from vigilo_persistence import session_scope

_SECRET = "whsec_test"
_PRICE = "price_pro_test"
_YEARLY = "price_pro_yearly_test"


@pytest.fixture(autouse=True)
def _stripe(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", _PRICE)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO_YEARLY", _YEARLY)
    monkeypatch.setenv("WEB_APP_URL", "https://vigilo.test")
    config.cache_clear()
    yield
    config.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


def _signed(raw: bytes) -> str:
    ts = int(time.time())
    sig = hmac.new(_SECRET.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _event(
    sub_id: str,
    email: str,
    *,
    org_id: str | None = None,
    account_id: str | None = None,
    status: str = "active",
    event_type: str = "customer.subscription.updated",
    created: int = 1_790_000_000,
    customer: str = "cus_1",
    price: str = _PRICE,
    interval: str = "month",
) -> bytes:
    metadata = {"vigilo_account_email": email}
    if org_id:
        metadata["vigilo_org_id"] = org_id
    if account_id:
        metadata["vigilo_account_id"] = account_id
    return json.dumps(
        {
            "type": event_type,
            "created": created,
            "data": {
                "object": {
                    "id": sub_id,
                    "status": status,
                    "customer": customer,
                    "metadata": metadata,
                    "items": {
                        "data": [
                            {
                                "price": {"id": price, "recurring": {"interval": interval}},
                                "current_period_end": 1_792_022_400,
                            }
                        ]
                    },
                }
            },
        }
    ).encode()


async def _webhook(client, raw: bytes):
    return await client.post(
        "/v1/billing/webhook", content=raw, headers={"Stripe-Signature": _signed(raw)}
    )


async def _account(email: str):
    async with session_scope() as session:
        return await get_or_create_account(session, email=email, clerk_user_id=f"u_{email}")


async def _org(client, owner, slug: str) -> str:
    app.dependency_overrides[require_account] = lambda: owner
    return (await client.post("/v1/orgs", json={"name": slug, "slug": slug})).json()["org_id"]


def _stripe_mock(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/checkout/sessions":
            captured["form"] = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            return httpx.Response(200, json={"url": "https://checkout.stripe.com/c/pay/cs_test"})
        if request.url.path.startswith("/v1/subscriptions/"):
            captured["subscription_lookup"] = request.url.path
            return httpx.Response(200, json={"customer": "cus_portal"})
        return httpx.Response(200, json={"url": "https://billing.stripe.com/p/sess"})

    return httpx.MockTransport(handler)


def _use_mock(monkeypatch, captured):
    transport = _stripe_mock(captured)
    for name in ("create_checkout_url", "create_portal_url"):
        monkeypatch.setattr(
            billing_router,
            name,
            functools.partial(getattr(billing_router, name), transport=transport),
        )


async def test_a_team_subscribes_as_an_organisation_not_as_a_person(client):
    owner = await _account("pay-owner@b.example")
    org_id = await _org(client, owner, "payteam")
    raw = _event("sub_team_1", owner.email, org_id=org_id, account_id=str(owner.id))
    assert (await _webhook(client, raw)).json()["status"] == "applied"

    async with session_scope() as session:
        assert await plan_id_for_org(session, uuid.UUID(org_id)) == "pro"
        personal = await personal_org_id(session, owner.id)
        assert await plan_id_for_org(session, personal) is None  # the team paid, not the person
        assert (await get_account_by_id(session, owner.id)).plan_id != "pro"
        assert (await get_org(session, uuid.UUID(org_id))).billing_customer_id == "cus_1"

    app.dependency_overrides[require_account] = lambda: owner
    orgs = {o["org_id"]: o for o in (await client.get("/v1/orgs")).json()}
    assert orgs[org_id]["entitlements"]["plan_id"] == "pro"


async def test_a_personal_pro_plan_does_not_carry_into_other_organisations(client):
    owner = await _account("two-orgs@b.example")
    team = await _org(client, owner, "twoorgs")
    await _webhook(client, _event("sub_personal_only", owner.email))  # legacy: no org metadata
    async with session_scope() as session:
        assert await plan_id_for_org(session, await personal_org_id(session, owner.id)) == "pro"
        assert await plan_id_for_org(session, uuid.UUID(team)) is None


async def test_legacy_events_without_an_org_still_upgrade_the_personal_org(client):
    acc = await _account("legacy@b.example")
    assert (await _webhook(client, _event("sub_legacy", acc.email))).json()["status"] == "applied"
    async with session_scope() as session:
        assert (await get_account_by_id(session, acc.id)).plan_id == "pro"


async def test_cancelling_a_team_subscription_drops_the_team_to_free(client):
    owner = await _account("cancel-owner@b.example")
    org_id = await _org(client, owner, "cancelteam")
    await _webhook(client, _event("sub_c", owner.email, org_id=org_id, created=1_790_000_000))
    await _webhook(
        client,
        _event(
            "sub_c",
            owner.email,
            org_id=org_id,
            status="canceled",
            event_type="customer.subscription.deleted",
            created=1_790_000_100,
        ),
    )
    async with session_scope() as session:
        assert await plan_id_for_org(session, uuid.UUID(org_id)) is None


async def test_an_older_event_arriving_late_does_not_undo_a_newer_one(client):
    owner = await _account("order-owner@b.example")
    org_id = await _org(client, owner, "orderteam")
    cancelled = _event(
        "sub_o",
        owner.email,
        org_id=org_id,
        status="canceled",
        event_type="customer.subscription.deleted",
        created=1_790_000_200,
    )
    old_active = _event("sub_o", owner.email, org_id=org_id, created=1_790_000_100)
    await _webhook(client, _event("sub_o", owner.email, org_id=org_id, created=1_790_000_000))
    assert (await _webhook(client, cancelled)).json()["status"] == "applied"
    late = await _webhook(client, old_active)  # delivered after the cancel, but older
    assert late.json()["status"] == "stale"
    async with session_scope() as session:
        assert await plan_id_for_org(session, uuid.UUID(org_id)) is None


async def test_replaying_an_event_is_harmless(client):
    owner = await _account("replay-owner@b.example")
    org_id = await _org(client, owner, "replayteam")
    raw = _event("sub_r", owner.email, org_id=org_id)
    for _ in range(3):
        assert (await _webhook(client, raw)).status_code == 200
    async with session_scope() as session:
        assert await plan_id_for_org(session, uuid.UUID(org_id)) == "pro"


async def test_an_event_for_an_unknown_org_is_ignored(client):
    owner = await _account("ghost-owner@b.example")
    raw = _event("sub_g", owner.email, org_id=str(uuid.uuid4()))
    assert (await _webhook(client, raw)).json()["status"] == "ignored"


async def test_checkout_names_the_organisation_and_reuses_its_customer(client, monkeypatch):
    captured: dict = {}
    _use_mock(monkeypatch, captured)
    owner = await _account("co-owner@b.example")
    org_id = await _org(client, owner, "coteam")

    first = await client.post(
        "/v1/billing/checkout", json={"plan_id": "pro"}, headers={"X-Org-Id": org_id}
    )
    assert first.status_code == 200
    form = captured["form"]
    assert form["subscription_data[metadata][vigilo_org_id]"] == org_id
    assert form["customer_email"] == owner.email and "customer" not in form

    # the organisation pays once, then cancels; its next checkout reuses the customer
    await _webhook(client, _event("sub_co", owner.email, org_id=org_id, customer="cus_org"))
    await _webhook(
        client,
        _event(
            "sub_co",
            owner.email,
            org_id=org_id,
            customer="cus_org",
            status="canceled",
            event_type="customer.subscription.deleted",
            created=1_790_000_500,
        ),
    )
    again = await client.post(
        "/v1/billing/checkout", json={"plan_id": "pro"}, headers={"X-Org-Id": org_id}
    )
    assert again.status_code == 200
    assert captured["form"]["customer"] == "cus_org" and "customer_email" not in captured["form"]


async def test_an_organisation_that_already_pays_cannot_buy_a_second_plan(client, monkeypatch):
    _use_mock(monkeypatch, {})
    owner = await _account("dup-owner@b.example")
    org_id = await _org(client, owner, "dupteam")
    await _webhook(client, _event("sub_dup", owner.email, org_id=org_id))
    again = await client.post(
        "/v1/billing/checkout", json={"plan_id": "pro"}, headers={"X-Org-Id": org_id}
    )
    assert again.status_code == 409


async def test_only_owners_and_admins_manage_billing(client, monkeypatch):
    _use_mock(monkeypatch, {})
    owner = await _account("role-owner@b.example")
    member = await _account("role-member@b.example")
    org_id = await _org(client, owner, "roleteam")
    token = (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": member.email, "role": "member"}
        )
    ).json()["token"]
    app.dependency_overrides[require_account] = lambda: member
    await client.post(f"/v1/invites/{token}/accept")
    for path in ("/v1/billing/checkout", "/v1/billing/portal"):
        r = await client.post(path, json={"plan_id": "pro"}, headers={"X-Org-Id": org_id})
        assert r.status_code == 403, path
    # and a stranger cannot even see the organisation
    stranger = await _account("role-stranger@b.example")
    app.dependency_overrides[require_account] = lambda: stranger
    r = await client.post("/v1/billing/portal", headers={"X-Org-Id": org_id})
    assert r.status_code == 404


async def test_the_portal_opens_the_active_organisations_subscription(client, monkeypatch):
    captured: dict = {}
    _use_mock(monkeypatch, captured)
    owner = await _account("portal-owner@b.example")
    org_id = await _org(client, owner, "portalteam")
    await _webhook(client, _event("sub_portal_team", owner.email, org_id=org_id))
    r = await client.post("/v1/billing/portal", headers={"X-Org-Id": org_id})
    assert r.status_code == 200
    assert captured["subscription_lookup"] == "/v1/subscriptions/sub_portal_team"
    # the personal organisation has no subscription of its own
    assert (await client.post("/v1/billing/portal")).status_code == 404


async def test_yearly_interval_is_recorded(client):
    from vigilo_identity.repository import get_subscription_for_org

    owner = await _account("year-owner@b.example")
    org_id = await _org(client, owner, "yearteam")
    await _webhook(
        client, _event("sub_y", owner.email, org_id=org_id, price=_YEARLY, interval="year")
    )
    async with session_scope() as session:
        sub = await get_subscription_for_org(session, uuid.UUID(org_id))
    assert sub is not None and (sub.plan_id, sub.billing_interval) == ("pro", "year")


# --- cross-product billing summary -----------------------------------------


async def test_summary_lists_every_product_with_free_where_nothing_is_bought(client):
    owner = await _account("sum-owner@b.example")
    org_id = await _org(client, owner, "sumteam")
    body = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()
    assert [p["product_slug"] for p in body["products"]] == [
        "vigilo",
        "sentinel",
        "cspm",
        "gateway",
        "neurawall",
    ]
    assert {p["status"] for p in body["products"]} == {"free"}
    assert body["totals"] == {"monthly_cents": 0, "yearly_cents": 0, "currency": "usd"}
    can = {p["product_slug"]: p["can_purchase"] for p in body["products"]}
    assert can == {
        "vigilo": True,
        "sentinel": False,
        "cspm": False,
        "gateway": False,
        "neurawall": False,
    }


async def test_summary_shows_plan_cadence_price_renewal_and_totals(client):
    owner = await _account("sum2-owner@b.example")
    org_id = await _org(client, owner, "sum2team")
    await _webhook(client, _event("sub_s2", owner.email, org_id=org_id))
    body = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()
    vigilo = body["products"][0]
    assert (vigilo["plan_id"], vigilo["status"], vigilo["interval"]) == ("pro", "active", "month")
    assert vigilo["amount_cents"] == 2900 and vigilo["current_period_end"]
    assert vigilo["cancel_at_period_end"] is False
    assert body["totals"]["monthly_cents"] == 2900 and body["totals"]["yearly_cents"] == 0


async def test_summary_keeps_monthly_and_yearly_totals_separate(client):
    owner = await _account("sum3-owner@b.example")
    org_id = await _org(client, owner, "sum3team")
    await _webhook(
        client, _event("sub_s3", owner.email, org_id=org_id, price=_YEARLY, interval="year")
    )
    totals = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()[
        "totals"
    ]
    assert totals["yearly_cents"] == 29000 and totals["monthly_cents"] == 0


async def test_a_requested_cancellation_is_shown_as_ending_not_renewing(client):
    owner = await _account("sum4-owner@b.example")
    org_id = await _org(client, owner, "sum4team")
    raw = json.loads(_event("sub_s4", owner.email, org_id=org_id))
    raw["data"]["object"]["cancel_at_period_end"] = True
    await _webhook(client, json.dumps(raw).encode())
    vigilo = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()[
        "products"
    ][0]
    assert vigilo["status"] == "active" and vigilo["cancel_at_period_end"] is True
    # the customer changes their mind in the portal: a newer event clears it
    raw["data"]["object"]["cancel_at_period_end"] = False
    raw["created"] += 60
    await _webhook(client, json.dumps(raw).encode())
    vigilo = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()[
        "products"
    ][0]
    assert vigilo["cancel_at_period_end"] is False


async def test_a_cancelled_subscription_goes_back_to_free_in_the_summary(client):
    owner = await _account("sum5-owner@b.example")
    org_id = await _org(client, owner, "sum5team")
    await _webhook(client, _event("sub_s5", owner.email, org_id=org_id))
    await _webhook(
        client,
        _event(
            "sub_s5",
            owner.email,
            org_id=org_id,
            status="canceled",
            event_type="customer.subscription.deleted",
            created=1_790_000_900,
        ),
    )
    body = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()
    assert body["products"][0]["status"] == "free" and body["totals"]["monthly_cents"] == 0


async def test_only_owners_and_admins_see_the_summary_and_it_is_per_organisation(client):
    owner = await _account("sum6-owner@b.example")
    member = await _account("sum6-member@b.example")
    team = await _org(client, owner, "sum6team")
    await _webhook(client, _event("sub_s6", owner.email, org_id=team))
    token = (
        await client.post(
            f"/v1/orgs/{team}/invites", json={"email": member.email, "role": "member"}
        )
    ).json()["token"]
    app.dependency_overrides[require_account] = lambda: member
    await client.post(f"/v1/invites/{token}/accept")
    assert (await client.get("/v1/billing/summary", headers={"X-Org-Id": team})).status_code == 403
    # the owner's personal organisation does not show the team's plan
    app.dependency_overrides[require_account] = lambda: owner
    personal = (await client.get("/v1/billing/summary")).json()
    assert personal["products"][0]["status"] == "free"
    stranger = await _account("sum6-stranger@b.example")
    app.dependency_overrides[require_account] = lambda: stranger
    assert (await client.get("/v1/billing/summary", headers={"X-Org-Id": team})).status_code == 404
