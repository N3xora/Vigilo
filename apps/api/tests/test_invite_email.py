"""Invitation emails: sent through Postmark (mocked at the HTTP layer), limited,
escaped, and never required for the invite to work."""

from __future__ import annotations

import functools
import json
import uuid

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis

from vigilo_api import invite_email
from vigilo_api.deps import require_account
from vigilo_api.main import app
from vigilo_core.config import config
from vigilo_identity.repository import get_or_create_account
from vigilo_integrations.mail import send_transactional_email
from vigilo_persistence import session_scope


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    redis = Redis.from_url(config().redis_url)
    for key in await redis.keys("invite-email:*"):
        await redis.delete(key)
    yield
    for key in await redis.keys("invite-email:*"):
        await redis.delete(key)
    await redis.aclose()
    app.dependency_overrides.pop(require_account, None)


@pytest.fixture
def postmark(monkeypatch):
    """Postmark configured, delivery captured instead of sent."""
    monkeypatch.setenv("POSTMARK_SERVER_TOKEN", "pm_test")
    monkeypatch.setenv("MAIL_FROM_ADDRESS", "invites@vigilo.test")
    monkeypatch.setenv("WEB_APP_URL", "https://app.vigilo.test/")
    config.cache_clear()
    sent: list[dict] = []
    state = {"status": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(state["status"], json={"ErrorCode": 0})

    monkeypatch.setattr(
        invite_email,
        "deliver",
        functools.partial(send_transactional_email, transport=httpx.MockTransport(handler)),
    )
    yield sent, state
    config.cache_clear()


async def _owner_and_org(client, name="Acme"):
    async with session_scope() as session:
        owner = await get_or_create_account(
            session, email=f"o-{uuid.uuid4().hex[:8]}@mail.example", clerk_user_id=uuid.uuid4().hex
        )
    app.dependency_overrides[require_account] = lambda: owner
    org_id = (
        await client.post("/v1/orgs", json={"name": name, "slug": f"o-{uuid.uuid4().hex[:10]}"})
    ).json()["org_id"]
    return owner, org_id


def _addr() -> str:
    return f"new-{uuid.uuid4().hex[:10]}@invitee.example"


async def test_without_postmark_the_invite_still_works_and_says_so(client):
    _, org_id = await _owner_and_org(client)
    r = await client.post(f"/v1/orgs/{org_id}/invites", json={"email": _addr()})
    assert r.status_code == 201
    assert r.json()["email_status"] == "not_configured" and r.json()["token"]


async def test_the_email_carries_the_same_link_the_inviter_sees(client, postmark):
    sent, _ = postmark
    owner, org_id = await _owner_and_org(client, "Platform Team")
    to = _addr()
    r = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": to, "role": "admin"})
    ).json()
    assert r["email_status"] == "sent"
    assert len(sent) == 1
    mail = sent[0]
    assert mail["To"] == to and mail["From"] == "invites@vigilo.test"
    link = f"https://app.vigilo.test/invite/{r['token']}"
    assert link in mail["HtmlBody"] and link in mail["TextBody"]
    assert owner.email in mail["TextBody"] and "as admin" in mail["TextBody"]
    assert "Platform Team" in mail["Subject"]


async def test_hostile_organisation_names_cannot_inject_markup_or_headers(client, postmark):
    sent, _ = postmark
    _, org_id = await _owner_and_org(client, 'Evil <script>alert(1)</script>\nBcc: x@y.z "quoted"')
    await client.post(f"/v1/orgs/{org_id}/invites", json={"email": _addr()})
    mail = sent[0]
    assert "<script>" not in mail["HtmlBody"] and "&lt;script&gt;" in mail["HtmlBody"]
    assert "\n" not in mail["Subject"] and "\r" not in mail["Subject"]


async def test_a_postmark_failure_does_not_lose_the_invite(client, postmark):
    sent, state = postmark
    state["status"] = 500
    _, org_id = await _owner_and_org(client)
    to = _addr()
    r = (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": to})).json()
    assert r["email_status"] == "failed"
    pending = (await client.get(f"/v1/orgs/{org_id}/invites")).json()
    assert [i["email"] for i in pending] == [to]
    async with session_scope() as session:
        invitee = await get_or_create_account(session, email=to, clerk_user_id=uuid.uuid4().hex)
    app.dependency_overrides[require_account] = lambda: invitee
    assert (await client.post(f"/v1/invites/{r['token']}/accept")).status_code == 200


async def test_one_address_cannot_be_mailed_more_than_three_times_a_day(client, postmark):
    sent, _ = postmark
    _, org_id = await _owner_and_org(client)
    to = _addr()
    statuses = []
    for _ in range(4):  # each new invite replaces the last, but each is an email
        statuses.append(
            (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": to})).json()[
                "email_status"
            ]
        )
    assert statuses == ["sent", "sent", "sent", "rate_limited"]
    assert len(sent) == 3


async def test_an_organisation_cannot_mail_unbounded_numbers_of_people(
    client, postmark, monkeypatch
):
    sent, _ = postmark
    monkeypatch.setattr(invite_email, "PER_ORG", (2, 3600))
    _, org_id = await _owner_and_org(client)
    statuses = [
        (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": _addr()})).json()[
            "email_status"
        ]
        for _ in range(3)
    ]
    assert statuses == ["sent", "sent", "rate_limited"]
    assert len(sent) == 2


async def test_if_the_limiter_is_down_nothing_is_mailed(client, postmark, monkeypatch):
    sent, _ = postmark

    def broken():
        raise RuntimeError("redis down")

    monkeypatch.setattr(invite_email, "get_redis_client", broken)
    _, org_id = await _owner_and_org(client)
    r = (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": _addr()})).json()
    assert r["email_status"] == "failed" and sent == []


async def test_resend_rotates_the_link_and_emails_again(client, postmark):
    sent, _ = postmark
    _, org_id = await _owner_and_org(client)
    to = _addr()
    first = (await client.post(f"/v1/orgs/{org_id}/invites", json={"email": to})).json()
    again = await client.post(f"/v1/orgs/{org_id}/invites/{first['invite_id']}/resend")
    assert again.status_code == 200
    second = again.json()
    assert second["email_status"] == "sent" and second["token"] != first["token"]
    assert f"/invite/{second['token']}" in sent[-1]["TextBody"]

    async with session_scope() as session:
        invitee = await get_or_create_account(session, email=to, clerk_user_id=uuid.uuid4().hex)
    app.dependency_overrides[require_account] = lambda: invitee
    assert (await client.post(f"/v1/invites/{first['token']}/accept")).status_code == 404
    assert (await client.post(f"/v1/invites/{second['token']}/accept")).status_code == 200


async def test_resend_needs_admin_and_a_real_pending_invite(client, postmark):
    _, org_id = await _owner_and_org(client)
    unknown = await client.post(f"/v1/orgs/{org_id}/invites/{uuid.uuid4()}/resend")
    assert unknown.status_code == 404

    to = _addr()
    token = (
        await client.post(f"/v1/orgs/{org_id}/invites", json={"email": to, "role": "member"})
    ).json()
    async with session_scope() as session:
        member = await get_or_create_account(session, email=to, clerk_user_id=uuid.uuid4().hex)
    app.dependency_overrides[require_account] = lambda: member
    await client.post(f"/v1/invites/{token['token']}/accept")
    forbidden = await client.post(f"/v1/orgs/{org_id}/invites/{token['invite_id']}/resend")
    assert forbidden.status_code == 403
