from __future__ import annotations

import asyncio
import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.org_repository import increment_usage, list_usage
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


async def _account(email: str, clerk: str):
    async with session_scope() as session:
        return await get_or_create_account(session, email=email, clerk_user_id=clerk)


def _act_as(account):
    app.dependency_overrides[require_account] = lambda: account


@pytest_asyncio.fixture
async def alice():
    return await _account("alice@example.com", "user_alice")


@pytest_asyncio.fixture
async def bob():
    return await _account("bob@example.com", "user_bob")


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


async def _create_org(client, slug="acme"):
    resp = await client.post("/v1/orgs", json={"name": "Acme", "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()["org_id"]


async def test_list_orgs_provisions_personal_org_once(client, alice):
    _act_as(alice)
    first = (await client.get("/v1/orgs")).json()
    second = (await client.get("/v1/orgs")).json()
    assert len(first) == 1 and first[0]["is_personal"] and first[0]["role"] == "owner"
    assert first == second


async def test_create_org_validates_and_rejects_duplicate_slug(client, alice, bob):
    _act_as(alice)
    await _create_org(client, "acme")
    assert (
        await client.post("/v1/orgs", json={"name": "X", "slug": "Bad Slug!"})
    ).status_code == 422
    _act_as(bob)
    dup = await client.post("/v1/orgs", json={"name": "Other", "slug": "acme"})
    assert dup.status_code == 409


async def test_non_member_gets_404_everywhere(client, alice, bob):
    _act_as(alice)
    org_id = await _create_org(client)
    _act_as(bob)
    for method, path, body in [
        ("get", f"/v1/orgs/{org_id}/members", None),
        ("get", f"/v1/orgs/{org_id}/products", None),
        ("get", f"/v1/orgs/{org_id}/usage", None),
        ("post", f"/v1/orgs/{org_id}/invites", {"email": "x@example.com", "role": "member"}),
        ("post", f"/v1/orgs/{org_id}/products/sentinel/enable", None),
    ]:
        resp = await client.request(method, path, json=body)
        assert resp.status_code == 404, (method, path, resp.status_code)


async def test_invite_accept_flow_and_role_gates(client, alice, bob):
    _act_as(alice)
    org_id = await _create_org(client)
    invite = (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": "Bob@Example.com", "role": "member"}
        )
    ).json()
    assert invite["token"].startswith("nxi_")

    _act_as(bob)
    accepted = await client.post(f"/v1/invites/{invite['token']}/accept")
    assert accepted.status_code == 200 and accepted.json()["role"] == "member"
    # a second accept is rejected
    assert (await client.post(f"/v1/invites/{invite['token']}/accept")).status_code == 404
    # member can read but not administer
    assert (await client.get(f"/v1/orgs/{org_id}/members")).status_code == 200
    forbidden = await client.post(f"/v1/orgs/{org_id}/invites", json={"email": "c@example.com"})
    assert forbidden.status_code == 403


async def test_invite_for_other_email_cannot_be_accepted(client, alice, bob):
    _act_as(alice)
    org_id = await _create_org(client)
    invite = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": "someone-else@example.com"})
    ).json()
    _act_as(bob)
    assert (await client.post(f"/v1/invites/{invite['token']}/accept")).status_code == 404


async def test_owner_cannot_be_changed_or_removed(client, alice):
    _act_as(alice)
    org_id = await _create_org(client)
    assert (
        await client.patch(f"/v1/orgs/{org_id}/members/{alice.id}", json={"role": "viewer"})
    ).status_code == 409
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{alice.id}")).status_code == 409


async def test_product_enablement(client, alice):
    _act_as(alice)
    org_id = await _create_org(client)
    listed = {p["slug"]: p for p in (await client.get(f"/v1/orgs/{org_id}/products")).json()}
    assert listed["vigilo"]["enabled"] is True and listed["vigilo"]["available"] is True
    # the other four are known but this build cannot run them yet
    for slug in ("sentinel", "cspm", "gateway", "neurawall"):
        assert listed[slug] == {"slug": slug, "enabled": False, "available": False}
    refused = await client.post(f"/v1/orgs/{org_id}/products/sentinel/enable")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "not_available"
    # enabling what is on is a no-op, not an error
    again = await client.post(f"/v1/orgs/{org_id}/products/vigilo/enable")
    assert again.status_code == 200 and again.json()["enabled"] is True
    assert (await client.post(f"/v1/orgs/{org_id}/products/nope/enable")).status_code == 404


async def test_a_product_becomes_enableable_once_it_is_available(client, alice, monkeypatch):
    """The gate is one constant: connecting an engine means adding its slug."""
    from vigilo_identity import org_repository

    monkeypatch.setattr(org_repository, "AVAILABLE_PRODUCTS", ("vigilo", "sentinel"))
    _act_as(alice)
    org_id = await _create_org(client)
    on = await client.post(f"/v1/orgs/{org_id}/products/sentinel/enable")
    assert on.status_code == 200 and on.json() == {
        "slug": "sentinel",
        "enabled": True,
        "available": True,
    }


async def test_usage_counter_is_atomic_under_concurrency(client, alice):
    _act_as(alice)
    org_id = await _create_org(client)
    import uuid

    oid = uuid.UUID(org_id)

    async def bump():
        async with session_scope() as session:
            await increment_usage(session, oid, "sentinel", "scans")

    await asyncio.gather(*(bump() for _ in range(10)))
    async with session_scope() as session:
        counters = await list_usage(session, oid)
    assert [(c.product_slug, c.count) for c in counters] == [("sentinel", 10)]
    usage = {
        (u["product_slug"], u["meter"]): u
        for u in (await client.get(f"/v1/orgs/{org_id}/usage")).json()
    }
    assert usage[("sentinel", "scans")]["used"] == 10
    assert usage[("vigilo", "scans")]["limit"] == 3  # free plan


# --- invite and role management UI support ---------------------------------


async def test_admin_lists_and_revokes_pending_invites(client, alice, bob):
    _act_as(alice)
    org_id = await _create_org(client)
    first = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": "p1@example.com"})
    ).json()
    listed = (await client.get(f"/v1/orgs/{org_id}/invites")).json()
    assert [i["email"] for i in listed] == ["p1@example.com"]
    assert "token" not in listed[0]  # the link is only ever shown at creation

    assert (
        await client.delete(f"/v1/orgs/{org_id}/invites/{first['invite_id']}")
    ).status_code == 204
    assert (await client.get(f"/v1/orgs/{org_id}/invites")).json() == []
    # a revoked link no longer works
    _act_as(await _account("p1@example.com", "user_p1"))
    assert (await client.post(f"/v1/invites/{first['token']}/accept")).status_code == 404
    # unknown id
    _act_as(alice)
    assert (
        await client.delete(f"/v1/orgs/{org_id}/invites/{first['invite_id']}")
    ).status_code == 404


async def test_a_second_invite_to_the_same_address_replaces_the_first(client, alice):
    _act_as(alice)
    org_id = await _create_org(client)
    one = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": "Same@Example.com"})
    ).json()
    two = (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": "same@example.com", "role": "viewer"}
        )
    ).json()
    listed = (await client.get(f"/v1/orgs/{org_id}/invites")).json()
    assert [(i["email"], i["role"]) for i in listed] == [("same@example.com", "viewer")]
    _act_as(await _account("same@example.com", "user_same"))
    assert (await client.post(f"/v1/invites/{one['token']}/accept")).status_code == 404
    assert (await client.post(f"/v1/invites/{two['token']}/accept")).status_code == 200


async def test_only_admins_see_pending_invites(client, alice, bob):
    _act_as(alice)
    org_id = await _create_org(client)
    token = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": bob.email, "role": "member"})
    ).json()["token"]
    _act_as(bob)
    await client.post(f"/v1/invites/{token}/accept")
    assert (await client.get(f"/v1/orgs/{org_id}/invites")).status_code == 403
    assert (await client.delete(f"/v1/orgs/{org_id}/invites/{uuid.uuid4()}")).status_code == 403


async def test_a_member_can_leave_but_not_remove_others_and_the_owner_cannot_leave(
    client, alice, bob
):
    _act_as(alice)
    org_id = await _create_org(client)
    token = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": bob.email, "role": "member"})
    ).json()["token"]
    _act_as(bob)
    await client.post(f"/v1/invites/{token}/accept")
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{alice.id}")).status_code == 403
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{bob.id}")).status_code == 204
    assert (await client.get(f"/v1/orgs/{org_id}/members")).status_code == 404  # gone
    _act_as(alice)
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{alice.id}")).status_code == 409
