"""Deleting an account: what goes, what stays, and what blocks it."""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_api.routers import accounts as accounts_router
from vigilo_core.config import config
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.org_repository import personal_org_id
from vigilo_identity.orm import AccountRow, MembershipRow, OrganizationRow, SubscriptionRow
from vigilo_identity.repository import get_or_create_account, upsert_subscription
from vigilo_integrations.clerk import delete_clerk_user
from vigilo_orchestrator.orm import FindingRow, ReportRow, ScanRow
from vigilo_orchestrator.reports import get_or_create_html_report
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.orm import ProjectRow, TargetRow
from vigilo_project.repository import create_target, get_or_create_default_project
from vigilo_security.orm import AuditEventRow


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    app.dependency_overrides.pop(require_account, None)


@pytest.fixture(autouse=True)
def _no_outside_world(monkeypatch):
    """Record storage and identity calls instead of making them."""
    calls: dict[str, list] = {"bundles": [], "reports": [], "clerk": []}

    async def bundle(i):
        calls["bundles"].append(i)

    async def report(i):
        calls["reports"].append(i)

    async def clerk(i):
        calls["clerk"].append(i)

    monkeypatch.setattr(accounts_router, "delete_evidence_bundle", bundle)
    monkeypatch.setattr(accounts_router, "delete_report_pdf", report)
    monkeypatch.setattr(accounts_router, "delete_clerk_user", clerk)
    return calls


async def _acct(email: str, clerk: str | None = None):
    async with session_scope() as session:
        return await get_or_create_account(
            session, email=email, clerk_user_id=clerk or f"u_{email}"
        )


def _as(a):
    app.dependency_overrides[require_account] = lambda: a


async def _scan_with_data(account, origin="https://del.example.com"):
    async with session_scope() as session:
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, origin)
        job = await create_scan_job(session, target.id, Tier.PASSIVE, account.email, "0.1")
        for step in ("authorized", "probing", "evaluating", "scoring"):
            job = await advance(session, job.id, step)
        finding = Finding(
            check_id="VG-HDR-001",
            verdict=Verdict.FAILED,
            severity=Severity.HIGH,
            confidence=Confidence.CONFIRMED,
            title="t",
            summary="s",
            fingerprint="fp-del",
        )
        scan = await record_scan_result(
            session,
            job,
            [finding],
            Score(value=50.0, grade="D", registry_version="0.1"),
            5,
            bundle_id="bundle-abc",
        )
        report = await get_or_create_html_report(session, scan.id)
    return target, scan, report


async def _count(model, *where):
    async with session_scope() as session:
        return (
            await session.execute(select(func.count()).select_from(model).where(*where))
        ).scalar_one()


async def test_deleting_removes_the_account_its_org_and_everything_under_it(
    client, _no_outside_world
):
    me = await _acct("del-me@d.example")
    target, scan, report = await _scan_with_data(me)
    async with session_scope() as session:
        org_id = await personal_org_id(session, me.id)
    _as(me)

    r = await client.post("/v1/me/delete", json={"confirm_email": "DEL-me@d.example"})
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": True, "identity_removed": True, "storage_cleanup": "complete"}

    assert await _count(AccountRow, AccountRow.id == me.id) == 0
    assert await _count(OrganizationRow, OrganizationRow.id == org_id) == 0
    assert await _count(ProjectRow, ProjectRow.org_id == org_id) == 0
    assert await _count(TargetRow, TargetRow.id == target.id) == 0
    assert await _count(ScanRow, ScanRow.id == scan.id) == 0
    assert await _count(FindingRow, FindingRow.scan_id == scan.id) == 0
    assert await _count(ReportRow, ReportRow.id == report.id) == 0
    assert _no_outside_world["bundles"] == ["bundle-abc"]
    assert _no_outside_world["reports"] == [str(report.id)]
    assert _no_outside_world["clerk"] == [me.clerk_user_id]


async def test_the_audit_trail_survives_and_reads_as_a_former_member(client):
    me = await _acct("del-audit@d.example")
    async with session_scope() as session:
        org_id = await personal_org_id(session, me.id)
    _as(me)
    team = (await client.post("/v1/orgs", json={"name": "T", "slug": "delaudit"})).json()["org_id"]
    watcher = await _acct("del-watch@d.example")
    token = (
        await client.post(
            f"/v1/orgs/{team}/invites", json={"email": watcher.email, "role": "admin"}
        )
    ).json()["token"]
    _as(watcher)
    await client.post(f"/v1/invites/{token}/accept")
    # the owner removes the watcher? no: the watcher (admin) reads the trail after the owner is gone
    _as(me)
    await client.delete(f"/v1/orgs/{team}/members/{watcher.id}")
    # org with no other members now: deletable
    r = await client.post("/v1/me/delete", json={"confirm_email": me.email})
    assert r.status_code == 200
    async with session_scope() as session:
        kept = (
            await session.execute(
                select(func.count())
                .select_from(AuditEventRow)
                .where(AuditEventRow.actor == str(me.id))
            )
        ).scalar_one()
        last = (
            await session.execute(
                select(AuditEventRow.action, AuditEventRow.subject)
                .where(AuditEventRow.actor == str(me.id))
                .order_by(AuditEventRow.occurred_at.desc())
                .limit(1)
            )
        ).one()
    assert kept >= 3
    assert last == ("account_deleted", "account")  # no address kept in the record
    assert org_id is not None


async def test_the_email_must_be_typed_correctly(client):
    me = await _acct("del-confirm@d.example")
    _as(me)
    for wrong in ("", "someone-else@d.example"):
        r = await client.post("/v1/me/delete", json={"confirm_email": wrong})
        assert r.status_code == 422
    assert await _count(AccountRow, AccountRow.id == me.id) == 1


async def test_an_organisation_with_other_members_blocks_deletion(client):
    me = await _acct("del-owner@d.example")
    mate = await _acct("del-mate@d.example")
    _as(me)
    team = (await client.post("/v1/orgs", json={"name": "Crew", "slug": "delcrew"})).json()[
        "org_id"
    ]
    token = (
        await client.post(f"/v1/orgs/{team}/invites", json={"email": mate.email, "role": "member"})
    ).json()["token"]
    _as(mate)
    await client.post(f"/v1/invites/{token}/accept")

    _as(me)
    check = (await client.get("/v1/me/deletion-check")).json()
    assert [b["kind"] for b in check["blockers"]] == ["members"]
    assert "Crew" in check["blockers"][0]["detail"]
    r = await client.post("/v1/me/delete", json={"confirm_email": me.email})
    assert r.status_code == 409 and "Crew" in str(r.json())
    assert await _count(AccountRow, AccountRow.id == me.id) == 1

    # once the member is gone, deletion goes through and the empty team goes too
    await client.delete(f"/v1/orgs/{team}/members/{mate.id}")
    assert (await client.get("/v1/me/deletion-check")).json()["blockers"] == []
    assert (await client.post("/v1/me/delete", json={"confirm_email": me.email})).status_code == 200
    assert await _count(OrganizationRow, OrganizationRow.id == uuid.UUID(team)) == 0


async def test_a_renewing_paid_plan_blocks_but_a_cancelling_one_does_not(client):
    me = await _acct("del-pay@d.example")
    async with session_scope() as session:
        org_id = await personal_org_id(session, me.id)
        await upsert_subscription(session, me.id, "pro", "active", "stripe", "sub_del", None)
    _as(me)
    blockers = (await client.get("/v1/me/deletion-check")).json()["blockers"]
    assert [b["kind"] for b in blockers] == ["subscription"]
    assert (await client.post("/v1/me/delete", json={"confirm_email": me.email})).status_code == 409

    async with session_scope() as session:
        await upsert_subscription(
            session, me.id, "pro", "active", "stripe", "sub_del", None, cancel_at_period_end=True
        )
    assert (await client.get("/v1/me/deletion-check")).json()["blockers"] == []
    assert (await client.post("/v1/me/delete", json={"confirm_email": me.email})).status_code == 200
    assert await _count(SubscriptionRow, SubscriptionRow.org_id == org_id) == 0


async def test_things_a_member_made_in_someone_elses_org_stay_with_that_org(client):
    owner = await _acct("del-keep-owner@d.example")
    member = await _acct("del-keep-member@d.example")
    _as(owner)
    team = (await client.post("/v1/orgs", json={"name": "Keep", "slug": "delkeep"})).json()[
        "org_id"
    ]
    token = (
        await client.post(
            f"/v1/orgs/{team}/invites", json={"email": member.email, "role": "member"}
        )
    ).json()["token"]
    _as(member)
    await client.post(f"/v1/invites/{token}/accept")
    # the member is first to touch the org: they become the project's "creator"
    made = await client.post(
        "/v1/targets", json={"origin": "https://kept.example.com"}, headers={"X-Org-Id": team}
    )
    assert made.status_code == 201

    deleted = await client.post("/v1/me/delete", json={"confirm_email": member.email})
    assert deleted.status_code == 200
    assert await _count(AccountRow, AccountRow.id == member.id) == 0

    _as(owner)
    listed = await client.get("/v1/targets", headers={"X-Org-Id": team})
    assert [t["origin"] for t in listed.json()] == ["https://kept.example.com"]
    async with session_scope() as session:
        project = (
            await session.execute(select(ProjectRow).where(ProjectRow.org_id == uuid.UUID(team)))
        ).scalar_one()
        members = (
            await session.execute(
                select(func.count())
                .select_from(MembershipRow)
                .where(MembershipRow.org_id == uuid.UUID(team))
            )
        ).scalar_one()
    assert project.account_id == owner.id and members == 1


async def test_one_persons_deletion_does_not_touch_anyone_else(client):
    me = await _acct("del-iso-me@d.example")
    other = await _acct("del-iso-other@d.example")
    await _scan_with_data(me, "https://mine.example.com")
    other_target, other_scan, _ = await _scan_with_data(other, "https://theirs.example.com")
    _as(me)
    assert (await client.post("/v1/me/delete", json={"confirm_email": me.email})).status_code == 200
    assert await _count(AccountRow, AccountRow.id == other.id) == 1
    assert await _count(TargetRow, TargetRow.id == other_target.id) == 1
    assert await _count(ScanRow, ScanRow.id == other_scan.id) == 1


async def test_failures_outside_do_not_undo_the_deletion(client, monkeypatch):
    from vigilo_integrations.errors import IdentityProviderError, ObjectStoreError

    async def broken_store(_):
        raise ObjectStoreError("down")

    async def broken_idp(_):
        raise IdentityProviderError("down")

    monkeypatch.setattr(accounts_router, "delete_evidence_bundle", broken_store)
    monkeypatch.setattr(accounts_router, "delete_report_pdf", broken_store)
    monkeypatch.setattr(accounts_router, "delete_clerk_user", broken_idp)
    me = await _acct("del-fail@d.example")
    await _scan_with_data(me)
    _as(me)
    r = await client.post("/v1/me/delete", json={"confirm_email": me.email})
    assert r.status_code == 200
    assert r.json() == {"deleted": True, "identity_removed": False, "storage_cleanup": "partial"}
    assert await _count(AccountRow, AccountRow.id == me.id) == 0


async def test_clerk_user_deletion_calls_the_right_endpoint_and_treats_404_as_done(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    config.cache_clear()
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer sk_test_x"
        return httpx.Response(404 if "gone" in request.url.path else 200, json={})

    transport = httpx.MockTransport(handler)
    await delete_clerk_user("user_1", transport=transport)
    await delete_clerk_user("user_gone", transport=transport)
    assert seen == [("DELETE", "/v1/users/user_1"), ("DELETE", "/v1/users/user_gone")]

    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    from vigilo_integrations.errors import IdentityProviderError

    with pytest.raises(IdentityProviderError):
        await delete_clerk_user("user_2", transport=httpx.MockTransport(failing))
    config.cache_clear()


async def test_requires_sign_in(client):
    assert (await client.post("/v1/me/delete", json={"confirm_email": "x@y.z"})).status_code == 401
    assert (await client.get("/v1/me/deletion-check")).status_code == 401
