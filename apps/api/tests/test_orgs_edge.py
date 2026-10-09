"""Edge and negative cases from replica/test-plan.md (F02, F05)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import update

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.org_repository import hash_invite_token
from vigilo_identity.orm import OrgInviteRow
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


async def _account(email: str, clerk: str):
    async with session_scope() as session:
        return await get_or_create_account(session, email=email, clerk_user_id=clerk)


def _act_as(account):
    app.dependency_overrides[require_account] = lambda: account


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


async def _org_with_member(client, role: str):
    owner = await _account("owner@example.com", "user_owner")
    member = await _account("member@example.com", "user_member")
    _act_as(owner)
    org_id = (await client.post("/v1/orgs", json={"name": "Acme", "slug": "acme"})).json()["org_id"]
    invite = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": member.email, "role": role})
    ).json()
    _act_as(member)
    assert (await client.post(f"/v1/invites/{invite['token']}/accept")).status_code == 200
    return owner, member, org_id


# F02-E1: two tabs open at once on first sign-in must not 500.
async def test_concurrent_first_org_listing_provisions_one_personal_org(client):
    acc = await _account("race@example.com", "user_race")
    _act_as(acc)
    responses = await asyncio.gather(*(client.get("/v1/orgs") for _ in range(5)))
    assert [r.status_code for r in responses] == [200] * 5
    final = (await client.get("/v1/orgs")).json()
    assert len(final) == 1


# F02-E2: whitespace-only and over-long names.
async def test_org_name_must_not_be_blank_after_trimming(client):
    _act_as(await _account("name@example.com", "user_name"))
    assert (await client.post("/v1/orgs", json={"name": "   ", "slug": "blank"})).status_code == 422
    assert (
        await client.post("/v1/orgs", json={"name": "x" * 201, "slug": "long"})
    ).status_code == 422


# F02-E3: emoji and accents survive a round trip.
async def test_org_name_unicode_round_trip(client):
    _act_as(await _account("uni@example.com", "user_uni"))
    created = await client.post("/v1/orgs", json={"name": "Zażółć 🚀 Łódź", "slug": "unicode"})
    assert created.status_code == 201
    names = [o["name"] for o in (await client.get("/v1/orgs")).json()]
    assert "Zażółć 🚀 Łódź" in names


# F05-N1: invite to something that is not an email address.
async def test_invite_rejects_malformed_email(client):
    _act_as(await _account("inv@example.com", "user_inv"))
    org_id = (await client.post("/v1/orgs", json={"name": "A", "slug": "inv-org"})).json()["org_id"]
    for bad in ["not-an-email", "a@", "@b.com", "a b@c.com"]:
        resp = await client.post(f"/v1/orgs/{org_id}/invites", json={"email": bad})
        assert resp.status_code == 422, bad


# F05-N2: expired invite.
async def test_expired_invite_is_rejected_with_410(client):
    owner = await _account("owner@example.com", "user_owner")
    guest = await _account("guest@example.com", "user_guest")
    _act_as(owner)
    org_id = (await client.post("/v1/orgs", json={"name": "A", "slug": "exp-org"})).json()["org_id"]
    token = (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": guest.email})).json()[
        "token"
    ]
    async with session_scope() as session:
        await session.execute(
            update(OrgInviteRow)
            .where(OrgInviteRow.token_hash == hash_invite_token(token))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    _act_as(guest)
    assert (await client.post(f"/v1/invites/{token}/accept")).status_code == 410


# F05-N3: someone already in the org accepts a second invite -> conflict, role unchanged.
async def test_inviting_an_existing_member_conflicts_and_changes_nothing(client):
    owner, member, org_id = await _org_with_member(client, "viewer")
    _act_as(owner)
    # inviting someone who is already in is refused up front, so no stray link exists
    again = await client.post(
        f"/v1/orgs/{org_id}/invites", json={"email": member.email, "role": "admin"}
    )
    assert again.status_code == 409
    _act_as(member)
    roles = {m["email"]: m["role"] for m in (await client.get(f"/v1/orgs/{org_id}/members")).json()}
    assert roles[member.email] == "viewer"


# F05-N4: role gates, one per privilege boundary.
async def test_viewer_cannot_enable_products_or_manage_members(client):
    owner, viewer, org_id = await _org_with_member(client, "viewer")
    _act_as(viewer)
    assert (await client.get(f"/v1/orgs/{org_id}/usage")).status_code == 200
    assert (await client.post(f"/v1/orgs/{org_id}/products/sentinel/enable")).status_code == 403
    assert (
        await client.patch(f"/v1/orgs/{org_id}/members/{owner.id}", json={"role": "viewer"})
    ).status_code == 403
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{owner.id}")).status_code == 403


# F05-N5: an admin cannot mint an owner, and cannot touch the owner.
async def test_admin_cannot_create_or_modify_owner(client):
    owner, admin, org_id = await _org_with_member(client, "admin")
    _act_as(admin)
    assert (
        await client.post(
            f"/v1/orgs/{org_id}/invites", json={"email": "x@example.com", "role": "owner"}
        )
    ).status_code == 422
    assert (
        await client.patch(f"/v1/orgs/{org_id}/members/{admin.id}", json={"role": "owner"})
    ).status_code == 422
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{owner.id}")).status_code == 409


# F05-E1: removed member loses access immediately.
async def test_removed_member_loses_access(client):
    owner, member, org_id = await _org_with_member(client, "member")
    _act_as(owner)
    assert (await client.delete(f"/v1/orgs/{org_id}/members/{member.id}")).status_code == 204
    _act_as(member)
    assert (await client.get(f"/v1/orgs/{org_id}/members")).status_code == 404


# F03-E1: enabling twice is idempotent (double click).
async def test_enable_product_twice_is_idempotent(client):
    _act_as(await _account("idem@example.com", "user_idem"))
    org_id = (await client.post("/v1/orgs", json={"name": "A", "slug": "idem-org"})).json()[
        "org_id"
    ]
    first = await client.post(f"/v1/orgs/{org_id}/products/vigilo/enable")
    second = await client.post(f"/v1/orgs/{org_id}/products/vigilo/enable")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


# Malformed identifiers must not 500.
async def test_malformed_ids_return_422_not_500(client):
    _act_as(await _account("bad@example.com", "user_bad"))
    assert (await client.get("/v1/orgs/not-a-uuid/members")).status_code == 422
    assert (await client.post("/v1/invites/%20/accept")).status_code in (404, 422)
    assert (await client.get(f"/v1/orgs/{uuid.uuid4()}/members")).status_code == 404
