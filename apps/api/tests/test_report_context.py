"""Fix-plan items 2 and 3 as seen through the report API."""

from __future__ import annotations

from vigilo_api.deps import optional_account
from vigilo_api.main import app
from vigilo_core.models import Confidence, Finding, Score, Severity, Tier, Verdict
from vigilo_identity.repository import get_or_create_account
from vigilo_orchestrator.service import advance, create_scan_job, record_scan_result
from vigilo_persistence import session_scope
from vigilo_project.repository import create_target, get_or_create_default_project


async def _scan(check_id: str, stack: list[str] | None, email: str = "ctx@example.com"):
    async with session_scope() as session:
        account = await get_or_create_account(session, email=email)
        project = await get_or_create_default_project(session, account.id)
        target = await create_target(session, project.id, "https://ctx.example.com")
        job = await create_scan_job(session, target.id, Tier.PASSIVE, email, "0.1")
        for step in ("authorized", "probing", "evaluating", "scoring"):
            job = await advance(session, job.id, step)
        findings = [
            Finding(
                check_id=check_id,
                verdict=Verdict.FAILED,
                severity=Severity.CRITICAL,
                confidence=Confidence.CONFIRMED,
                title="Supabase REST schema is not publicly introspectable",
                summary="the schema is open",
                fingerprint="fp-ctx",
            )
        ]
        score = Score(value=40.0, grade="F", registry_version="0.1")
        await record_scan_result(session, job, findings, score, duration_ms=5, stack=stack)
        await advance(session, job.id, "reporting")
        await advance(session, job.id, "complete")
    return job, account


async def test_report_carries_the_detected_stack_and_a_why_line(client):
    job, _ = await _scan("VG-DAT-002", ["supabase", "vercel"])
    body = (await client.get(f"/v1/scans/{job.id}/report")).json()
    assert body["stack"] == ["Supabase", "Vercel"]
    finding = body["findings"][0]
    assert "Supabase" in finding["why_here"]


async def test_supabase_finding_gets_the_step_by_step_guide(client):
    job, _ = await _scan("VG-DAT-002", ["supabase"])
    finding = (await client.get(f"/v1/scans/{job.id}/report")).json()["findings"][0]
    steps = finding["remediation"]["remediation_steps"]
    assert len(steps) == 5 and "row level security" in steps[1]
    assert "service_role" in finding["remediation"]["agent_prompt"]


async def test_scans_recorded_without_a_stack_still_render(client):
    job, _ = await _scan("VG-DAT-002", None)
    body = (await client.get(f"/v1/scans/{job.id}/report")).json()
    assert body["stack"] == [] and body["findings"][0]["why_here"] is None


async def test_can_accept_risk_follows_the_org_role(client):
    from vigilo_identity.org_repository import ensure_personal_org

    job, owner = await _scan("VG-DAT-002", ["supabase"])
    async with session_scope() as session:
        org = await ensure_personal_org(session, owner)
        viewer = await get_or_create_account(session, email="v@example.com", clerk_user_id="u_v")
        member = await get_or_create_account(session, email="m@example.com", clerk_user_id="u_m")
    from vigilo_api.deps import require_account

    async def accept(account, role):
        app.dependency_overrides[require_account] = lambda: owner
        token = (
            await client.post(
                f"/v1/orgs/{org.id}/invites", json={"email": account.email, "role": role}
            )
        ).json()["token"]
        app.dependency_overrides[require_account] = lambda: account
        await client.post(f"/v1/invites/{token}/accept")

    await accept(viewer, "viewer")
    await accept(member, "member")

    async def can(account):
        app.dependency_overrides[optional_account] = lambda: account
        body = (await client.get(f"/v1/scans/{job.id}/report")).json()
        return body["can_accept_risk"], body["is_owner"]

    try:
        assert await can(owner) == (True, True)
        assert await can(member) == (True, False)  # may accept risks, not owner-only controls
        assert await can(viewer) == (False, False)
        assert await can(None) == (False, False)
    finally:
        app.dependency_overrides.pop(optional_account, None)
        app.dependency_overrides.pop(require_account, None)
