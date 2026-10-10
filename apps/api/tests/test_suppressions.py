from __future__ import annotations

import uuid

import pytest_asyncio

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


@pytest_asyncio.fixture
async def account():
    async with session_scope() as session:
        acc = await get_or_create_account(
            session, email="suppression-owner@example.com", clerk_user_id="user_suppression"
        )
    app.dependency_overrides[require_account] = lambda: acc
    yield acc
    app.dependency_overrides.pop(require_account, None)


@pytest_asyncio.fixture
async def target_id(client, account):
    response = await client.post("/v1/targets", json={"origin": "https://suppress.example.com"})
    return response.json()["target_id"]


async def test_suppress_finding_returns_201(client, account, target_id):
    response = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "abc123", "check_id": "HDR-001", "reason": "accepted risk"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["target_id"] == target_id
    assert body["fingerprint"] == "abc123"
    assert body["check_id"] == "HDR-001"
    assert body["reason"] == "accepted risk"
    assert body["expires_at"] is None
    assert body["created_by_account_id"] == str(account.id)


async def test_suppress_finding_upserts_by_fingerprint(client, account, target_id):
    first = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "dupe123", "check_id": "HDR-001", "reason": "first reason"},
    )
    second = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "dupe123", "check_id": "HDR-001", "reason": "updated reason"},
    )

    assert first.json()["suppression_id"] == second.json()["suppression_id"]
    assert second.json()["reason"] == "updated reason"

    listing = await client.get(f"/v1/targets/{target_id}/suppressions")
    assert len(listing.json()) == 1


async def test_suppress_finding_requires_ownership_of_the_target(client, account, target_id):
    async with session_scope() as session:
        other = await get_or_create_account(
            session, email="suppression-other@example.com", clerk_user_id="user_suppression_other"
        )
    app.dependency_overrides[require_account] = lambda: other

    response = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "abc123", "check_id": "HDR-001", "reason": "not mine"},
    )
    assert response.status_code == 404


async def test_list_suppressions_returns_only_this_targets_suppressions(client, account, target_id):
    await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "fp1", "check_id": "HDR-001", "reason": "r1"},
    )
    await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "fp2", "check_id": "HDR-002", "reason": "r2"},
    )

    response = await client.get(f"/v1/targets/{target_id}/suppressions")

    assert response.status_code == 200
    fingerprints = {item["fingerprint"] for item in response.json()}
    assert fingerprints == {"fp1", "fp2"}


async def test_revoke_suppression_succeeds_for_the_owner(client, account, target_id):
    create_response = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "to-revoke", "check_id": "HDR-001", "reason": "temp"},
    )
    suppression_id = create_response.json()["suppression_id"]

    response = await client.post(f"/v1/targets/{target_id}/suppressions/{suppression_id}/revoke")
    assert response.status_code == 200
    assert response.json()["suppression_id"] == suppression_id

    listing = await client.get(f"/v1/targets/{target_id}/suppressions")
    assert listing.json() == []


async def test_revoke_suppression_requires_ownership(client, account, target_id):
    create_response = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "to-revoke", "check_id": "HDR-001", "reason": "temp"},
    )
    suppression_id = create_response.json()["suppression_id"]

    async with session_scope() as session:
        other = await get_or_create_account(
            session,
            email="suppression-revoke-other@example.com",
            clerk_user_id="user_suppression_revoke_other",
        )
    app.dependency_overrides[require_account] = lambda: other

    response = await client.post(f"/v1/targets/{target_id}/suppressions/{suppression_id}/revoke")
    assert response.status_code == 404


async def test_revoke_an_unknown_suppression_returns_404(client, account, target_id):
    response = await client.post(f"/v1/targets/{target_id}/suppressions/{uuid.uuid4()}/revoke")
    assert response.status_code == 404


async def test_suppression_endpoints_require_authentication(client):
    response = await client.post(
        f"/v1/targets/{uuid.uuid4()}/findings/suppress",
        json={"fingerprint": "x", "check_id": "HDR-001", "reason": "x"},
    )
    assert response.status_code == 401


# --- team-shared risk acceptance (fix-plan item 3) ---------------------------


async def _org_member(client, owner, role: str, email: str, clerk: str):
    """Invite a second account into the owner's personal org with `role`."""
    from vigilo_identity.org_repository import ensure_personal_org

    async with session_scope() as session:
        org = await ensure_personal_org(session, owner)
        member = await get_or_create_account(session, email=email, clerk_user_id=clerk)
    app.dependency_overrides[require_account] = lambda: owner
    token = (
        await client.post(f"/v1/orgs/{org.id}/invites", json={"email": email, "role": role})
    ).json()["token"]
    app.dependency_overrides[require_account] = lambda: member
    assert (await client.post(f"/v1/invites/{token}/accept")).status_code == 200
    return member


async def test_org_member_can_accept_a_risk_on_a_teammates_target(client, account, target_id):
    member = await _org_member(client, account, "member", "teammate@example.com", "user_mate")
    app.dependency_overrides[require_account] = lambda: member
    response = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "team1", "check_id": "HDR-001", "reason": "CDN adds this header"},
    )
    assert response.status_code == 201
    assert response.json()["created_by_account_id"] == str(member.id)

    app.dependency_overrides[require_account] = lambda: account
    listing = await client.get(f"/v1/targets/{target_id}/suppressions")
    assert [s["reason"] for s in listing.json()] == ["CDN adds this header"]


async def test_org_viewer_can_read_but_not_accept_risks(client, account, target_id):
    viewer = await _org_member(client, account, "viewer", "viewer@example.com", "user_view")
    app.dependency_overrides[require_account] = lambda: viewer
    assert (await client.get(f"/v1/targets/{target_id}/suppressions")).status_code == 200
    denied = await client.post(
        f"/v1/targets/{target_id}/findings/suppress",
        json={"fingerprint": "v1", "check_id": "HDR-001", "reason": "nope"},
    )
    assert denied.status_code == 403


async def test_outsider_cannot_see_or_accept_risks(client, account, target_id):
    async with session_scope() as session:
        stranger = await get_or_create_account(
            session, email="stranger@example.com", clerk_user_id="user_stranger"
        )
    app.dependency_overrides[require_account] = lambda: stranger
    assert (await client.get(f"/v1/targets/{target_id}/suppressions")).status_code == 404
    assert (
        await client.post(
            f"/v1/targets/{target_id}/findings/suppress",
            json={"fingerprint": "x", "check_id": "HDR-001", "reason": "r"},
        )
    ).status_code == 404


async def test_a_reason_is_required(client, account, target_id):
    for reason in ["", "   "]:
        response = await client.post(
            f"/v1/targets/{target_id}/findings/suppress",
            json={"fingerprint": "r1", "check_id": "HDR-001", "reason": reason},
        )
        assert response.status_code == 422
