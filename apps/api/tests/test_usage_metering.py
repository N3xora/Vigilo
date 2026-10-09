"""Item 4: accepted Vigilo scans are metered into usage_counters."""

from __future__ import annotations

import vigilo_api.routers.scans as scans_module
from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_identity.org_repository import ensure_personal_org, list_usage
from vigilo_identity.repository import get_or_create_account
from vigilo_persistence import session_scope


async def _vigilo_scans(email: str) -> int:
    async with session_scope() as session:
        acc = await get_or_create_account(session, email=email)
        org = await ensure_personal_org(session, acc)
        counters = await list_usage(session, org.id)
    return sum(c.count for c in counters if (c.product_slug, c.meter) == ("vigilo", "scans"))


async def test_accepted_scans_are_counted_and_denied_ones_are_not(client, monkeypatch):
    email = "meter@example.com"
    for _ in range(2):
        r = await client.post(
            "/v1/scans", json={"target_url": "https://example.com", "email": email}
        )
        assert r.status_code == 202
    assert await _vigilo_scans(email) == 2

    monkeypatch.setattr(scans_module, "_DENYLIST", frozenset({"https://denylisted.test"}))
    denied = await client.post(
        "/v1/scans", json={"target_url": "https://denylisted.test", "email": email}
    )
    assert denied.status_code == 403
    assert await _vigilo_scans(email) == 2


async def test_usage_endpoint_reports_the_metered_scans(client):
    email = "meter-api@example.com"
    assert (
        await client.post("/v1/scans", json={"target_url": "https://example.com", "email": email})
    ).status_code == 202
    async with session_scope() as session:
        acc = await get_or_create_account(session, email=email, clerk_user_id="user_meter_api")
        org = await ensure_personal_org(session, acc)
    app.dependency_overrides[require_account] = lambda: acc
    try:
        usage = {
            (u["product_slug"], u["meter"]): u
            for u in (await client.get(f"/v1/orgs/{org.id}/usage")).json()
        }
    finally:
        app.dependency_overrides.pop(require_account, None)
    assert usage[("vigilo", "scans")]["used"] == 1
    assert usage[("vigilo", "scans")]["limit"] == 3
