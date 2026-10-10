"""Routes read and write by the active organisation (X-Org-Id), and target-scoped
routes follow the target's own organisation, whatever the caller's header."""

from __future__ import annotations

import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import (
    get_account_by_id,
    get_or_create_account,
    upsert_subscription,
)
from vigilo_persistence import session_scope


async def _account(email: str, plan: str = "free"):
    async with session_scope() as session:
        acc = await get_or_create_account(session, email=email, clerk_user_id=f"u_{email}")
        if plan != "free":
            await upsert_subscription(
                session, acc.id, plan, "active", "stripe", f"sub_{email}", None
            )
            acc = await get_account_by_id(session, acc.id)
    return acc


def _as(account):
    app.dependency_overrides[require_account] = lambda: account


def _org(org_id: str) -> dict[str, str]:
    return {"X-Org-Id": org_id}


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


async def _team(client, owner_plan: str = "pro"):
    """owner creates org X and invites an admin, a member and a viewer."""
    owner = await _account("owner@t.example")
    people = {r: await _account(f"{r}@t.example") for r in ("admin", "member", "viewer")}
    _as(owner)
    org_id = (await client.post("/v1/orgs", json={"name": "Team", "slug": "team"})).json()["org_id"]
    if owner_plan != "free":  # billing is per organisation: the team itself subscribes
        async with session_scope() as session:
            await upsert_subscription(
                session,
                owner.id,
                owner_plan,
                "active",
                "stripe",
                "sub_team",
                None,
                org_id=uuid.UUID(org_id),
            )
    for role, acc in people.items():
        _as(owner)
        token = (
            await client.post(f"/v1/orgs/{org_id}/invites", json={"email": acc.email, "role": role})
        ).json()["token"]
        _as(acc)
        assert (await client.post(f"/v1/invites/{token}/accept")).status_code == 200
    return owner, people, org_id


async def test_targets_are_kept_per_organisation(client):
    owner, _people, org_id = await _team(client)
    _as(owner)
    made = await client.post(
        "/v1/targets", json={"origin": "https://team.example.com"}, headers=_org(org_id)
    )
    assert made.status_code == 201
    in_team = await client.get("/v1/targets", headers=_org(org_id))
    personal = await client.get("/v1/targets")  # no header: the personal organisation
    assert [t["origin"] for t in in_team.json()] == ["https://team.example.com"]
    assert personal.json() == []


async def test_teammates_share_the_organisations_targets_by_role(client):
    owner, people, org_id = await _team(client)
    _as(owner)
    target = (
        await client.post(
            "/v1/targets", json={"origin": "https://shared.example.com"}, headers=_org(org_id)
        )
    ).json()

    _as(people["member"])
    assert len((await client.get("/v1/targets", headers=_org(org_id))).json()) == 1
    # no header needed for a specific target: its own organisation decides
    assert (await client.get(f"/v1/targets/{target['target_id']}")).status_code == 200
    added = await client.post(
        "/v1/targets", json={"origin": "https://member.example.com"}, headers=_org(org_id)
    )
    assert added.status_code == 201

    _as(people["viewer"])
    assert (await client.get("/v1/targets", headers=_org(org_id))).status_code == 200
    denied = await client.post(
        "/v1/targets", json={"origin": "https://viewer.example.com"}, headers=_org(org_id)
    )
    assert denied.status_code == 403


async def test_outsiders_and_bad_headers(client):
    owner, _people, org_id = await _team(client)
    _as(owner)
    target = (
        await client.post(
            "/v1/targets", json={"origin": "https://private.example.com"}, headers=_org(org_id)
        )
    ).json()
    stranger = await _account("stranger@t.example")
    _as(stranger)
    assert (await client.get("/v1/targets", headers=_org(org_id))).status_code == 404
    assert (await client.get(f"/v1/targets/{target['target_id']}")).status_code == 404
    assert (await client.get("/v1/targets", headers=_org("not-a-uuid"))).status_code == 422


async def test_quotas_follow_the_organisations_owner_not_the_caller(client):
    # Free owner: 1 target. A Pro member must not lift the team's limit.
    owner = await _account("freeowner@t.example")
    pro = await _account("promember@t.example", "pro")
    _as(owner)
    org_id = (await client.post("/v1/orgs", json={"name": "T", "slug": "quota"})).json()["org_id"]
    token = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": pro.email, "role": "member"})
    ).json()["token"]
    _as(pro)
    await client.post(f"/v1/invites/{token}/accept")

    first = await client.post(
        "/v1/targets", json={"origin": "https://one.example.com"}, headers=_org(org_id)
    )
    second = await client.post(
        "/v1/targets", json={"origin": "https://two.example.com"}, headers=_org(org_id)
    )
    assert first.status_code == 201
    assert second.status_code == 429
    # while in their own personal organisation the Pro member has Pro limits
    for i in range(2):
        r = await client.post("/v1/targets", json={"origin": f"https://mine{i}.example.com"})
        assert r.status_code == 201


async def test_api_keys_belong_to_the_organisation(client):
    owner, people, org_id = await _team(client)
    _as(people["admin"])
    created = await client.post(
        "/v1/me/api-keys",
        json={"name": "ci", "scopes": ["project:read", "report:read"]},
        headers=_org(org_id),
    )
    assert created.status_code == 201
    raw_key = created.json()["api_key"]

    _as(people["member"])
    assert (await client.get("/v1/me/api-keys", headers=_org(org_id))).status_code == 403
    _as(owner)
    assert len((await client.get("/v1/me/api-keys", headers=_org(org_id))).json()) == 1
    assert (await client.get("/v1/me/api-keys")).json() == []  # personal org: none

    # the key acts in the team's organisation, even though an admin made it
    projects = await client.get(
        "/public/v1/projects", headers={"Authorization": f"Bearer {raw_key}"}
    )
    assert projects.status_code == 200
    me_project = (
        await client.post(
            "/v1/targets", json={"origin": "https://viakey.example.com"}, headers=_org(org_id)
        )
    ).json()
    scores = await client.get(
        f"/public/v1/targets/{me_project['target_id']}/scores",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert scores.status_code == 200


async def test_a_key_cannot_reach_another_organisations_targets(client):
    owner, people, org_id = await _team(client)
    _as(owner)
    personal_target = (
        await client.post("/v1/targets", json={"origin": "https://personal.example.com"})
    ).json()
    raw_key = (
        await client.post(
            "/v1/me/api-keys", json={"name": "k", "scopes": ["report:read"]}, headers=_org(org_id)
        )
    ).json()["api_key"]
    r = await client.get(
        f"/public/v1/targets/{personal_target['target_id']}/scores",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert r.status_code == 404


async def test_branding_is_per_organisation(client):
    owner, people, org_id = await _team(client)
    _as(people["admin"])
    saved = await client.put(
        "/v1/me/branding-profile", json={"footer_text": "Team report"}, headers=_org(org_id)
    )
    assert saved.status_code == 200
    _as(people["member"])
    assert (await client.get("/v1/me/branding-profile", headers=_org(org_id))).json()[
        "footer_text"
    ] == "Team report"
    assert (await client.get("/v1/me/branding-profile")).json()["footer_text"] is None
    denied = await client.put(
        "/v1/me/branding-profile", json={"footer_text": "x"}, headers=_org(org_id)
    )
    assert denied.status_code == 403


async def test_removing_a_member_removes_their_access_to_the_orgs_targets(client):
    owner, people, org_id = await _team(client)
    _as(owner)
    target = (
        await client.post(
            "/v1/targets", json={"origin": "https://gone.example.com"}, headers=_org(org_id)
        )
    ).json()
    assert (
        await client.delete(f"/v1/orgs/{org_id}/members/{people['member'].id}")
    ).status_code == 204
    _as(people["member"])
    assert (await client.get(f"/v1/targets/{target['target_id']}")).status_code == 404
    assert (await client.get("/v1/targets", headers=_org(org_id))).status_code == 404


async def test_the_creator_loses_nothing_when_a_teammate_acts_first(client):
    """Whoever touches a new organisation first creates its one project; the
    owner still sees the same project and targets."""
    owner, people, org_id = await _team(client)
    _as(people["member"])
    await client.post(
        "/v1/targets", json={"origin": "https://first.example.com"}, headers=_org(org_id)
    )
    _as(owner)
    listed = await client.get("/v1/targets", headers=_org(org_id))
    assert [t["origin"] for t in listed.json()] == ["https://first.example.com"]


async def test_plan_shown_to_members_is_the_organisations_not_their_own(client):
    owner, people, org_id = await _team(client, owner_plan="pro")
    _as(owner)
    target = (
        await client.post(
            "/v1/targets", json={"origin": "https://plan.example.com"}, headers=_org(org_id)
        )
    ).json()
    _as(people["member"])  # a free account of their own
    orgs = {o["org_id"]: o for o in (await client.get("/v1/orgs")).json()}
    assert orgs[org_id]["entitlements"]["plan_id"] == "pro"
    personal = next(o for o in orgs.values() if o["is_personal"])
    assert personal["entitlements"]["plan_id"] == "free"
    seen = (await client.get(f"/v1/targets/{target['target_id']}")).json()
    assert seen["org_entitlements"]["plan_id"] == "pro"
    assert seen["org_entitlements"]["monitors_limit"] == 25
