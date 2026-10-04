"""NEXORA Core -> Vigilo plan sync: signature checks and the endpoint end to end."""

from __future__ import annotations

import json
import time

import pytest

from vigilo_api import deps
from vigilo_api.auth import ClerkClaims
from vigilo_api.core_sync import REPLAY_WINDOW_SECONDS, sign, verify
from vigilo_core.config import config

SECRET = "test-shared-secret"
ORG = "org_2abcdefghijk"


def _signed(body: dict | bytes, ts: int | None = None, secret: str = SECRET) -> tuple[bytes, dict]:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    ts = int(time.time()) if ts is None else ts
    return raw, {
        "X-Nexora-Timestamp": str(ts),
        "X-Nexora-Signature": sign(secret, ts, raw),
        "Content-Type": "application/json",
    }


class TestSignature:
    def test_accepts_a_fresh_correct_signature(self):
        body = b'{"x":1}'
        assert verify(SECRET, "1000", sign(SECRET, 1000, body), body, now=1000)

    def test_rejects_wrong_secret_tampered_body_and_missing_headers(self):
        body = b'{"x":1}'
        good = sign(SECRET, 1000, body)
        assert not verify("other", "1000", good, body, now=1000)
        assert not verify(SECRET, "1000", good, b'{"x":2}', now=1000)
        assert not verify(SECRET, None, good, body, now=1000)
        assert not verify(SECRET, "1000", None, body, now=1000)
        assert not verify(SECRET, "not-a-number", good, body, now=1000)

    def test_rejects_stale_and_future_timestamps(self):
        body = b"{}"
        sig = sign(SECRET, 1000, body)
        assert verify(SECRET, "1000", sig, body, now=1000 + REPLAY_WINDOW_SECONDS)
        assert not verify(SECRET, "1000", sig, body, now=1000 + REPLAY_WINDOW_SECONDS + 1)
        assert not verify(SECRET, "1000", sig, body, now=1000 - REPLAY_WINDOW_SECONDS - 1)


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("NEXORA_SYNC_SECRET", SECRET)
    config.cache_clear()
    yield
    config.cache_clear()


async def test_the_endpoint_does_not_exist_until_a_secret_is_configured(client, monkeypatch):
    monkeypatch.delenv("NEXORA_SYNC_SECRET", raising=False)
    config.cache_clear()
    raw, headers = _signed({"clerk_org_id": ORG, "plan_id": "pro"})

    assert (
        await client.post("/v1/internal/org-plan", content=raw, headers=headers)
    ).status_code == 404


async def test_rejects_a_bad_or_stale_signature_the_same_way(client, secret):
    raw, headers = _signed({"clerk_org_id": ORG, "plan_id": "pro"}, secret="wrong")
    stale_raw, stale_headers = _signed(
        {"clerk_org_id": ORG, "plan_id": "pro"}, ts=int(time.time()) - 3600
    )

    for content, hdrs in ((raw, headers), (stale_raw, stale_headers)):
        response = await client.post("/v1/internal/org-plan", content=content, headers=hdrs)
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid signature"}


@pytest.mark.parametrize(
    "payload",
    [
        {"clerk_org_id": ORG, "plan_id": "enterprise"},
        {"clerk_org_id": "user_123", "plan_id": "pro"},
        {"clerk_org_id": ORG},
        {"plan_id": "pro"},
        {"clerk_org_id": 5, "plan_id": "pro"},
    ],
)
async def test_rejects_a_malformed_payload_even_when_signed(client, secret, payload):
    raw, headers = _signed(payload)

    assert (
        await client.post("/v1/internal/org-plan", content=raw, headers=headers)
    ).status_code == 400


async def test_pro_creates_the_organisation_account_and_unlocks_pro_entitlements(
    client, secret, monkeypatch
):
    raw, headers = _signed({"clerk_org_id": ORG, "plan_id": "pro"})
    response = await client.post("/v1/internal/org-plan", content=raw, headers=headers)
    assert response.json() == {"status": "applied"}

    monkeypatch.setattr(
        deps,
        "verify_clerk_jwt",
        lambda token: ClerkClaims(user_id="user_a", email="alice@example.com", org_id=ORG),
    )
    me = (await client.get("/v1/me", headers={"Authorization": "Bearer x"})).json()
    assert me["organization_id"] == ORG
    assert me["entitlements"]["plan_id"] == "pro"
    assert me["entitlements"]["targets_limit"] == 25
    # The first member to act in the organisation becomes its contact.
    assert me["email"] == "alice@example.com"


async def test_is_idempotent_and_a_downgrade_returns_the_account_to_free(
    client, secret, monkeypatch
):
    for plan in ("pro", "pro", "free"):
        raw, headers = _signed({"clerk_org_id": ORG, "plan_id": plan})
        assert (
            await client.post("/v1/internal/org-plan", content=raw, headers=headers)
        ).json() == {"status": "applied"}

    monkeypatch.setattr(
        deps,
        "verify_clerk_jwt",
        lambda token: ClerkClaims(user_id="user_a", email="a@example.com", org_id=ORG),
    )
    me = (await client.get("/v1/me", headers={"Authorization": "Bearer x"})).json()
    assert me["entitlements"]["plan_id"] == "free"


async def test_a_downgrade_for_an_organisation_vigilo_has_never_seen_changes_nothing(
    client, secret
):
    raw, headers = _signed({"clerk_org_id": "org_2neverseenxx", "plan_id": "free"})

    response = await client.post("/v1/internal/org-plan", content=raw, headers=headers)

    assert response.json() == {"status": "ignored"}
