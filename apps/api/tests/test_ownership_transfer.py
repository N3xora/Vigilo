"""Handing an organisation to another member."""

from __future__ import annotations

import asyncio
import uuid

import pytest_asyncio
from sqlalchemy import func, select

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.orm import AccountRow, MembershipRow, OrganizationRow
from vigilo_identity.repository import get_or_create_account, upsert_subscription
from vigilo_persistence import session_scope


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


async def _acct(email: str):
    async with session_scope() as session:
        return await get_or_create_account(session, email=email, clerk_user_id=f"u_{email}")


def _as(a):
    app.dependency_overrides[require_account] = lambda: a


async def _team(client, slug: str):
    """owner + admin + member + viewer in one organisation."""
    owner = await _acct(f"{slug}-owner@t.example")
    people = {r: await _acct(f"{slug}-{r}@t.example") for r in ("admin", "member", "viewer")}
    _as(owner)
    org_id = (await client.post("/v1/orgs", json={"name": slug, "slug": slug})).json()["org_id"]
    for role, acc in people.items():
        _as(owner)
        token = (
            await client.post(f"/v1/orgs/{org_id}/invites", json={"email": acc.email, "role": role})
        ).json()["token"]
        _as(acc)
        await client.post(f"/v1/invites/{token}/accept")
    return owner, people, org_id


def _body(account, slug: str) -> dict:
    return {"new_owner_account_id": str(account.id), "confirm_slug": slug}


async def _roles(org_id: str) -> dict[str, str]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(AccountRow.email, MembershipRow.role)
                .join(MembershipRow, MembershipRow.account_id == AccountRow.id)
                .where(MembershipRow.org_id == uuid.UUID(org_id))
            )
        ).all()
    return {e.split("@")[0].split("-", 1)[1]: r for e, r in rows}


async def test_the_owner_hands_the_organisation_to_a_member(client):
    owner, people, org_id = await _team(client, "xfer1")
    _as(owner)
    r = await client.post(
        f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["member"], "xfer1")
    )
    assert r.status_code == 200 and r.json()["role"] == "owner"

    assert await _roles(org_id) == {
        "owner": "admin",
        "admin": "admin",
        "member": "owner",
        "viewer": "viewer",
    }
    async with session_scope() as session:
        created_by = (
            await session.execute(
                select(OrganizationRow.created_by).where(OrganizationRow.id == uuid.UUID(org_id))
            )
        ).scalar_one()
        owners = (
            await session.execute(
                select(func.count())
                .select_from(MembershipRow)
                .where(MembershipRow.org_id == uuid.UUID(org_id), MembershipRow.role == "owner")
            )
        ).scalar_one()
    assert (
        created_by == people["member"].id and owners == 1
    )  # exactly one owner, and created_by follows


async def test_the_new_owner_can_act_as_owner_and_the_old_one_is_an_admin(client):
    owner, people, org_id = await _team(client, "xfer2")
    _as(owner)
    await client.post(f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["admin"], "xfer2"))

    # the old owner keeps admin rights but can no longer hand the organisation over
    again = await client.post(
        f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["viewer"], "xfer2")
    )
    assert again.status_code == 403
    assert (await client.get(f"/v1/orgs/{org_id}/audit")).status_code == 200  # admin-level read

    # the new owner can: back to the first owner
    _as(people["admin"])
    back = await client.post(f"/v1/orgs/{org_id}/transfer-ownership", json=_body(owner, "xfer2"))
    assert back.status_code == 200
    assert (await _roles(org_id))["owner"] == "owner"


async def test_only_the_owner_may_transfer(client):
    owner, people, org_id = await _team(client, "xfer3")
    stranger = await _acct("xfer3-stranger@t.example")
    for who, expected in (
        (people["admin"], 403),
        (people["member"], 403),
        (people["viewer"], 403),
        (stranger, 404),
    ):
        _as(who)
        r = await client.post(f"/v1/orgs/{org_id}/transfer-ownership", json=_body(who, "xfer3"))
        assert r.status_code == expected, who.email
    assert (await _roles(org_id))["owner"] == "owner"  # nothing changed


async def test_the_confirmation_and_the_target_are_checked(client):
    owner, people, org_id = await _team(client, "xfer4")
    stranger = await _acct("xfer4-stranger@t.example")
    _as(owner)
    url = f"/v1/orgs/{org_id}/transfer-ownership"
    assert (await client.post(url, json=_body(people["admin"], "wrong-slug"))).status_code == 422
    assert (await client.post(url, json=_body(owner, "xfer4"))).status_code == 422  # not yourself
    assert (
        await client.post(url, json=_body(stranger, "xfer4"))
    ).status_code == 404  # not a member
    ghost = {"new_owner_account_id": str(uuid.uuid4()), "confirm_slug": "xfer4"}
    assert (await client.post(url, json=ghost)).status_code == 404
    assert (await _roles(org_id))["owner"] == "owner"


async def test_a_personal_workspace_cannot_be_handed_over(client):
    me = await _acct("xfer5-me@t.example")
    other = await _acct("xfer5-other@t.example")
    _as(me)
    personal = next(o for o in (await client.get("/v1/orgs")).json() if o["is_personal"])
    r = await client.post(
        f"/v1/orgs/{personal['org_id']}/transfer-ownership", json=_body(other, personal["slug"])
    )
    assert r.status_code in (
        404,
        409,
    )  # the other person is not a member; even a member would be refused

    token = (
        await client.post(
            f"/v1/orgs/{personal['org_id']}/invites", json={"email": other.email, "role": "admin"}
        )
    ).json()["token"]
    _as(other)
    await client.post(f"/v1/invites/{token}/accept")
    _as(me)
    r = await client.post(
        f"/v1/orgs/{personal['org_id']}/transfer-ownership", json=_body(other, personal["slug"])
    )
    assert r.status_code == 409


async def test_two_transfers_at_once_leave_exactly_one_owner(client):
    owner, people, org_id = await _team(client, "xfer6")
    _as(owner)
    url = f"/v1/orgs/{org_id}/transfer-ownership"
    results = await asyncio.gather(
        client.post(url, json=_body(people["admin"], "xfer6")),
        client.post(url, json=_body(people["member"], "xfer6")),
    )
    assert sorted(r.status_code for r in results) == [200, 403]  # the loser is no longer the owner
    roles = await _roles(org_id)
    assert list(roles.values()).count("owner") == 1


async def test_it_is_audited_with_who_handed_it_to_whom(client):
    owner, people, org_id = await _team(client, "xfer7")
    _as(owner)
    await client.post(
        f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["member"], "xfer7")
    )
    events = (await client.get(f"/v1/orgs/{org_id}/audit")).json()["events"]
    event = next(e for e in events if e["action"] == "ownership_transferred")
    assert event["subject"] == people["member"].email
    assert event["details"] == {"previous_owner": owner.email}
    assert event["actor_label"] == owner.email


async def test_the_old_owner_can_then_delete_their_account_and_the_team_survives(
    client, monkeypatch
):
    from vigilo_api.routers import accounts as accounts_router

    async def noop(_):
        return None

    for name in ("delete_evidence_bundle", "delete_report_pdf", "delete_clerk_user"):
        monkeypatch.setattr(accounts_router, name, noop)
    owner, people, org_id = await _team(client, "xfer8")
    _as(owner)
    # before the hand-over the owner is blocked by the team ...
    assert (await client.get("/v1/me/deletion-check")).json()["blockers"][0]["kind"] == "members"
    await client.post(
        f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["member"], "xfer8")
    )
    # ... after it they are free to go
    assert (await client.get("/v1/me/deletion-check")).json()["blockers"] == []
    assert (
        await client.post("/v1/me/delete", json={"confirm_email": owner.email})
    ).status_code == 200

    async with session_scope() as session:
        org = (
            await session.execute(
                select(OrganizationRow).where(OrganizationRow.id == uuid.UUID(org_id))
            )
        ).scalar_one()
        assert org.created_by == people["member"].id
    assert (await _roles(org_id))["member"] == "owner"


async def test_billing_and_limits_stay_with_the_organisation_through_a_transfer(client):
    owner, people, org_id = await _team(client, "xfer9")
    async with session_scope() as session:
        await upsert_subscription(
            session, owner.id, "pro", "active", "stripe", "sub_x9", None, org_id=uuid.UUID(org_id)
        )
    _as(owner)
    await client.post(
        f"/v1/orgs/{org_id}/transfer-ownership", json=_body(people["member"], "xfer9")
    )

    _as(people["member"])  # the new owner sees the team's plan, not their own free one
    org = next(o for o in (await client.get("/v1/orgs")).json() if o["org_id"] == org_id)
    assert org["entitlements"]["plan_id"] == "pro" and org["role"] == "owner"
    summary = (await client.get("/v1/billing/summary", headers={"X-Org-Id": org_id})).json()
    assert summary["products"][0]["plan_id"] == "pro"
    usage = {
        (u["product_slug"], u["meter"]): u
        for u in (await client.get(f"/v1/orgs/{org_id}/usage")).json()
    }
    assert usage[("vigilo", "scans")]["limit"] is None  # Pro: unlimited, as the quota enforces


async def test_a_second_transfer_started_mid_way_is_refused_cleanly_not_with_a_database_error(
    client,
):
    """Two transfers racing: while the first is still uncommitted, the second
    starts. The row lock makes the second wait, then see that its caller is no
    longer the owner (a clean refusal). Without the lock it would read the stale
    owner, collide with the one-owner-per-organisation index and fail with a
    database error."""
    import pytest

    from vigilo_identity.org_repository import OrgError, transfer_ownership

    owner, people, org_id = await _team(client, "xfer10")
    oid = uuid.UUID(org_id)

    async def second():
        async with session_scope() as session:
            await transfer_ownership(session, oid, owner.id, people["member"].id)

    async with session_scope() as first:
        await transfer_ownership(first, oid, owner.id, people["admin"].id)  # not committed yet
        task = asyncio.create_task(second())
        await asyncio.sleep(0.6)  # the second has started and is waiting on the first
    with pytest.raises(OrgError) as refused:
        await asyncio.wait_for(task, timeout=10)
    assert refused.value.code == "not_owner"
    roles = await _roles(org_id)
    assert roles["admin"] == "owner" and list(roles.values()).count("owner") == 1
