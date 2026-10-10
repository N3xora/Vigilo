"""The organisation audit trail: what is written, who can read it, and that it
cannot be edited or leak secrets."""

from __future__ import annotations

import json
import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope
from vigilo_security.audit import AuditEvent, audit


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


async def _account(email: str):
    async with session_scope() as session:
        return await get_or_create_account(session, email=email, clerk_user_id=f"u_{email}")


def _as(a):
    app.dependency_overrides[require_account] = lambda: a


async def _org(client, owner, slug="audteam"):
    _as(owner)
    return (await client.post("/v1/orgs", json={"name": "Aud", "slug": slug})).json()["org_id"]


def _org_h(org_id: str) -> dict[str, str]:
    return {"X-Org-Id": org_id}


async def _log(client, org_id, **params):
    r = await client.get(f"/v1/orgs/{org_id}/audit", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_org_actions_land_in_the_trail_with_who_and_what(client, monkeypatch):
    from vigilo_identity import org_repository

    monkeypatch.setattr(org_repository, "AVAILABLE_PRODUCTS", ("vigilo", "sentinel"))
    owner = await _account("aud-owner@a.example")
    member = await _account("aud-member@a.example")
    org_id = await _org(client, owner)
    token = (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": member.email, "role": "member"}
        )
    ).json()["token"]
    _as(member)
    await client.post(f"/v1/invites/{token}/accept")
    _as(owner)
    await client.patch(f"/v1/orgs/{org_id}/members/{member.id}", json={"role": "admin"})
    await client.post(f"/v1/orgs/{org_id}/products/sentinel/enable")
    await client.post(
        "/v1/targets", json={"origin": "https://aud.example.com"}, headers=_org_h(org_id)
    )
    await client.delete(f"/v1/orgs/{org_id}/members/{member.id}")

    events = (await _log(client, org_id))["events"]
    actions = [e["action"] for e in events]
    # newest first
    assert actions[:6] == [
        "member_removed",
        "target_added",
        "product_enabled",
        "member_role_changed",
        "invite_accepted",
        "invite_created",
    ]
    assert actions[-1] == "org_created"
    by_action = {e["action"]: e for e in events}
    assert by_action["member_role_changed"]["details"] == {"previous": "member", "role": "admin"}
    assert by_action["member_role_changed"]["subject"] == member.email
    assert by_action["member_role_changed"]["actor_label"] == owner.email
    assert by_action["invite_accepted"]["actor_label"] == member.email
    assert by_action["target_added"]["subject"] == "https://aud.example.com"
    assert by_action["member_removed"]["details"] == {"role": "admin"}


async def test_keys_branding_and_billing_actions_are_recorded_without_secrets(client):
    owner = await _account("aud2-owner@a.example")
    org_id = await _org(client, owner, "audteam2")
    made = await client.post(
        "/v1/me/api-keys", json={"name": "ci", "scopes": ["scan:run"]}, headers=_org_h(org_id)
    )
    # free plan has no keys: the refusal must not be logged as a creation
    assert made.status_code == 429
    events = (await _log(client, org_id))["events"]
    assert "api_key_created" not in {e["action"] for e in events}

    from vigilo_identity.repository import upsert_subscription

    async with session_scope() as session:
        await upsert_subscription(
            session, owner.id, "pro", "active", "stripe", "sub_aud2", None, org_id=uuid.UUID(org_id)
        )
    made = await client.post(
        "/v1/me/api-keys", json={"name": "ci", "scopes": ["scan:run"]}, headers=_org_h(org_id)
    )
    assert made.status_code == 201
    plaintext = made.json()["api_key"]
    prefix = made.json()["prefix"]
    key_id = made.json()["api_key_id"]
    await client.put(
        "/v1/me/branding-profile", json={"footer_text": "hello"}, headers=_org_h(org_id)
    )
    await client.post(f"/v1/me/api-keys/{key_id}/revoke", headers=_org_h(org_id))

    page = await _log(client, org_id)
    by_action = {e["action"]: e for e in page["events"]}
    assert by_action["api_key_created"]["subject"] == prefix
    assert by_action["api_key_created"]["details"] == {"name": "ci", "scopes": ["vigilo:scan:run"]}
    assert by_action["api_key_revoked"]["subject"] == prefix
    assert by_action["branding_updated"]["details"] == {"fields": ["footer_text"]}
    assert plaintext not in json.dumps(page)


async def test_invite_tokens_never_appear_in_the_trail(client):
    owner = await _account("aud3-owner@a.example")
    org_id = await _org(client, owner, "audteam3")
    r = (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": "x3@a.example"})).json()
    again = (await client.post(f"/v1/orgs/{org_id}/invites/{r['invite_id']}/resend")).json()
    dump = json.dumps(await _log(client, org_id))
    assert r["token"] not in dump and again["token"] not in dump
    assert {"invite_created", "invite_resent"} <= {
        e["action"] for e in (await _log(client, org_id))["events"]
    }


async def test_only_admins_read_it_and_outsiders_cannot_tell_the_org_exists(client):
    owner = await _account("aud4-owner@a.example")
    member = await _account("aud4-member@a.example")
    stranger = await _account("aud4-stranger@a.example")
    org_id = await _org(client, owner, "audteam4")
    token = (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": member.email, "role": "member"}
        )
    ).json()["token"]
    _as(member)
    await client.post(f"/v1/invites/{token}/accept")
    assert (await client.get(f"/v1/orgs/{org_id}/audit")).status_code == 403
    _as(stranger)
    assert (await client.get(f"/v1/orgs/{org_id}/audit")).status_code == 404


async def test_each_org_sees_only_its_own_events(client):
    owner = await _account("aud5-owner@a.example")
    one = await _org(client, owner, "audone")
    two = (await client.post("/v1/orgs", json={"name": "Two", "slug": "audtwo"})).json()["org_id"]
    await client.post(
        "/v1/targets", json={"origin": "https://only-one.example.com"}, headers=_org_h(one)
    )
    one_subjects = {e["subject"] for e in (await _log(client, one))["events"]}
    two_subjects = {e["subject"] for e in (await _log(client, two))["events"]}
    assert "https://only-one.example.com" in one_subjects
    assert "https://only-one.example.com" not in two_subjects


async def test_pagination_and_action_filter(client):
    owner = await _account("aud6-owner@a.example")
    org_id = await _org(client, owner, "audteam6")
    from vigilo_identity.repository import upsert_subscription

    async with session_scope() as session:  # Pro: more than the free plan's one target
        await upsert_subscription(
            session, owner.id, "pro", "active", "stripe", "sub_aud6", None, org_id=uuid.UUID(org_id)
        )
    for i in range(5):
        await client.post(
            "/v1/targets",
            json={"origin": f"https://p{i}.example.com"},
            headers=_org_h(org_id),
        )
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        page = await _log(client, org_id, limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [e["event_id"] for e in page["events"]]
        pages += 1
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 6  # 5 targets + org_created, none repeated or skipped
    assert pages == 3

    only = await _log(client, org_id, action="target_added")
    assert {e["action"] for e in only["events"]} == {"target_added"}
    assert set(only["actions"]) == {"org_created", "target_added"}
    assert (
        await client.get(f"/v1/orgs/{org_id}/audit", params={"cursor": "garbage"})
    ).status_code == 422
    assert (
        await client.get(f"/v1/orgs/{org_id}/audit", params={"action": "DROP TABLE"})
    ).status_code == 422
    assert (await client.get(f"/v1/orgs/{org_id}/audit", params={"limit": 1000})).status_code == 422


async def test_old_events_without_an_org_show_in_the_owners_personal_org_only(client):
    owner = await _account("aud7-owner@a.example")
    other = await _account("aud7-other@a.example")
    async with session_scope() as session:
        # exactly what the scan path wrote before audit_events.org_id existed
        await audit(
            session,
            AuditEvent(
                actor="api",
                action="scan_authorized",
                subject="https://legacy.example.com",
                account_id=owner.id,
            ),
        )
    _as(owner)
    personal = next(o for o in (await client.get("/v1/orgs")).json() if o["is_personal"])["org_id"]
    team = (await client.post("/v1/orgs", json={"name": "T", "slug": "audteam7"})).json()["org_id"]
    assert "https://legacy.example.com" in {
        e["subject"] for e in (await _log(client, personal))["events"]
    }
    assert "https://legacy.example.com" not in {
        e["subject"] for e in (await _log(client, team))["events"]
    }
    _as(other)
    other_personal = next(o for o in (await client.get("/v1/orgs")).json() if o["is_personal"])[
        "org_id"
    ]
    assert (await _log(client, other_personal))["events"] == []


async def test_system_actors_get_readable_labels(client):
    owner = await _account("aud8-owner@a.example")
    org_id = await _org(client, owner, "audteam8")
    async with session_scope() as session:
        await audit(
            session,
            AuditEvent(
                actor="stripe",
                action="subscription_updated",
                subject="sub_x",
                org_id=uuid.UUID(org_id),
                metadata={"plan_id": "pro", "api_token": "nope"},
            ),
        )
    event = next(
        e for e in (await _log(client, org_id))["events"] if e["action"] == "subscription_updated"
    )
    assert (event["actor_kind"], event["actor_label"]) == ("system", "Stripe")
    assert event["details"] == {"plan_id": "pro"}  # secret-looking keys are dropped on read
