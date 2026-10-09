from __future__ import annotations

import uuid

import vigilo_api.routers.scans as scans_module
from vigilo_core.models import Tier, VerificationMethod
from vigilo_identity.repository import get_or_create_account, upsert_subscription
from vigilo_orchestrator.service import create_scan_job
from vigilo_persistence import session_scope
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    issue_ownership_proof,
    mark_proof_verified,
)


async def test_submit_scan_returns_202_with_the_authorized_status(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "authorized"
    assert body["granted_tier"] == "passive"
    assert "scan_job_id" in body


async def test_submit_scan_rejects_a_malformed_url(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "not-a-url", "email": "owner@example.com"}
    )
    assert response.status_code == 422


async def test_submit_scan_rejects_an_invalid_email(client):
    response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "not-an-email"}
    )
    assert response.status_code == 422


async def test_submit_scan_denies_a_denylisted_target(client, monkeypatch):
    monkeypatch.setattr(scans_module, "_DENYLIST", frozenset({"https://denylisted.test"}))

    response = await client.post(
        "/v1/scans", json={"target_url": "https://denylisted.test", "email": "owner@example.com"}
    )
    assert response.status_code == 403


async def test_get_scan_status_returns_404_for_an_unknown_job(client):
    response = await client.get(f"/v1/scans/{uuid.uuid4()}")
    assert response.status_code == 404


async def _upgrade_to_studio(session, account_id: uuid.UUID, email: str):
    # Studio's scans_per_month_limit is None (unlimited) — needed so these
    # tests can seed 21+ scan jobs without tripping the *separate*
    # SCANS_MONTHLY billing quota before reaching the 24h abuse ceiling
    # this test is actually about.
    await upsert_subscription(
        session,
        account_id=account_id,
        plan_id="pro",
        status="active",
        provider="stripe",
        provider_subscription_id=f"sub_{email}",
        current_period_end=None,
    )


async def test_submit_scan_denies_the_22nd_scan_of_the_same_target_within_24h(client):
    email = "ratelimit-owner@example.com"
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        await _upgrade_to_studio(session, account.id, email)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://ratelimit-target.test")
        # Seed 21 scan jobs directly — the ceiling denies when the count
        # already exceeds 20, so the 22nd real submission (below) must be
        # denied.
        for _ in range(21):
            await create_scan_job(session, target.id, Tier.PASSIVE, email, "0.1")

    response = await client.post(
        "/v1/scans",
        json={"target_url": "https://ratelimit-target.test", "email": email},
    )

    assert response.status_code == 403
    assert "rate limit" in response.json()["detail"]


async def test_submit_scan_allows_a_22nd_scan_of_a_different_target(client):
    """Confirms the ceiling is genuinely per-target, not per-account —
    the same account scanning a *different* target isn't affected by the
    other target's recent volume."""
    email = "ratelimit-scope-owner@example.com"
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        await _upgrade_to_studio(session, account.id, email)
        project = await get_or_create_default_project(session, account.id)
        busy_target = await create_target(session, project.id, "https://busy-target.test")
        for _ in range(21):
            await create_scan_job(session, busy_target.id, Tier.PASSIVE, email, "0.1")

    response = await client.post(
        "/v1/scans",
        json={"target_url": "https://quiet-target.test", "email": email},
    )

    assert response.status_code == 202


async def test_submit_scan_requesting_active_tier_stays_passive_for_a_new_target(client):
    """A brand-new submitter has no prior verification state — requesting
    active tier is a downgrade, not a rejection, per ADR-0003."""
    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "first-timer@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "passive"


async def test_submit_scan_grants_active_tier_for_a_returning_verified_target(client):
    """The tier-stub fix (Phase 6): a returning submitter with a real,
    already-verified target for this exact origin, on a plan that includes
    active tier (Phase 7 — Free does not), gets active tier through the
    actual submission path, not just in theory."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="verified-owner@example.com")
        await upsert_subscription(
            session,
            account_id=account.id,
            plan_id="pro",
            status="active",
            provider="stripe",
            provider_subscription_id="sub_verified_owner",
            current_period_end=None,
        )
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)
        await mark_proof_verified(session, proof.id)

    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "verified-owner@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "active"


async def test_submit_scan_with_valid_proof_but_free_plan_stays_passive(client):
    """Phase 7's plan gate: a verified ownership proof alone is no longer
    enough for active tier — the account's plan (defaulting to Free, which
    excludes active tier) must permit it too. The concrete, testable
    analogue of the roadmap's "a plan change correctly and immediately
    restricts access" exit criterion."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="free-but-verified@example.com")
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://example.com")
        proof = await issue_ownership_proof(session, target.id, VerificationMethod.DNS_TXT)
        await mark_proof_verified(session, proof.id)

    response = await client.post(
        "/v1/scans",
        json={
            "target_url": "https://example.com",
            "email": "free-but-verified@example.com",
            "requested_tier": "active",
        },
    )

    assert response.status_code == 202
    assert response.json()["granted_tier"] == "passive"


async def test_submit_scan_for_a_new_origin_beyond_the_free_plan_target_limit_is_denied(client):
    """The bypass fix: `submit_scan` used to auto-create a `Target` for any
    new origin a returning account scanned, with no quota check at all.
    Free plan's targets_limit is 1 — a returning account with one existing
    target, scanning a second, brand-new origin, must be denied exactly
    like `POST /v1/targets` would deny it."""
    async with session_scope() as session:
        account = await get_or_create_account(session, email="repeat-scanner@example.com")
        project = await get_or_create_default_project(session, account.id)
        await create_target(session, project.id, "https://first.example.com")

    response = await client.post(
        "/v1/scans",
        json={"target_url": "https://second.example.com", "email": "repeat-scanner@example.com"},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_submit_scan_beyond_the_free_plan_monthly_scan_limit_is_denied(client):
    """Free plan's scans_per_month_limit is 3 (packages/billing/plans.py). The
    quota reads the same per-organisation counter the Usage page shows, so a
    4th scan this calendar month is denied: by actually submitting them."""
    body = {"target_url": "https://example.com", "email": "frequent-scanner@example.com"}
    for _ in range(3):
        assert (await client.post("/v1/scans", json=body)).status_code == 202

    response = await client.post("/v1/scans", json=body)

    assert response.status_code == 429
    assert response.json()["code"] == "QUOTA_EXCEEDED"


async def test_the_quota_counts_this_calendar_month_only_and_matches_the_usage_page(client):
    from datetime import UTC, datetime

    from vigilo_identity.org_repository import (
        get_usage_count,
        increment_usage,
        personal_org_id,
    )

    email = "month-boundary@example.com"
    body = {"target_url": "https://example.com", "email": email}
    assert (await client.post("/v1/scans", json=body)).status_code == 202  # creates the account

    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        org_id = await personal_org_id(session, account.id)
        # three scans last month do not count against this month...
        last_month = datetime.now(UTC).date().replace(day=1)
        last_month = last_month.replace(
            year=last_month.year - (last_month.month == 1),
            month=12 if last_month.month == 1 else last_month.month - 1,
        )
        await increment_usage(session, org_id, "vigilo", "scans", 3, today=last_month)
        assert await get_usage_count(session, org_id, "vigilo", "scans") == 1

    assert (await client.post("/v1/scans", json=body)).status_code == 202
    assert (await client.post("/v1/scans", json=body)).status_code == 202
    # ...and this month's three do: the fourth is refused, at exactly the number
    # the Usage page reports (3 of 3).
    denied = await client.post("/v1/scans", json=body)
    assert denied.status_code == 429
    async with session_scope() as session:
        assert await get_usage_count(session, org_id, "vigilo", "scans") == 3


async def test_a_paying_organisation_is_not_held_to_the_free_scan_limit(client):
    email = "pro-scanner@example.com"
    body = {"target_url": "https://example.com", "email": email}
    assert (await client.post("/v1/scans", json=body)).status_code == 202
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        await upsert_subscription(session, account.id, "pro", "active", "stripe", "sub_ps", None)
    for _ in range(5):  # Pro has no monthly scan limit
        assert (await client.post("/v1/scans", json=body)).status_code == 202


async def test_get_scan_status_reflects_the_authorized_job(client):
    submit_response = await client.post(
        "/v1/scans", json={"target_url": "https://example.com", "email": "owner@example.com"}
    )
    job_id = submit_response.json()["scan_job_id"]

    response = await client.get(f"/v1/scans/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert body["target_origin"] == "https://example.com"
    assert body["score"] is None
