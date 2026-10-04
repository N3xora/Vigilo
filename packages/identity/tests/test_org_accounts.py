from __future__ import annotations

from vigilo_identity.repository import (
    get_account_by_clerk_org_id,
    get_or_create_account,
    get_or_create_org_account,
    org_account_email,
)


async def test_creates_an_active_org_account_with_a_synthetic_email(db_session):
    account = await get_or_create_org_account(db_session, "org_1", "owner@example.com")

    assert account.clerk_org_id == "org_1"
    assert account.status == "active"
    assert account.email == org_account_email("org_1")
    assert account.email.endswith(".invalid")
    assert account.notification_email == "owner@example.com"


async def test_is_idempotent_and_ignores_a_later_contact_email(db_session):
    first = await get_or_create_org_account(db_session, "org_1", "owner@example.com")
    again = await get_or_create_org_account(db_session, "org_1", "someone-else@example.com")

    assert again.id == first.id
    assert again.notification_email == "owner@example.com"


async def test_lookup_by_org_id(db_session):
    assert await get_account_by_clerk_org_id(db_session, "org_missing") is None
    created = await get_or_create_org_account(db_session, "org_1", "owner@example.com")
    found = await get_account_by_clerk_org_id(db_session, "org_1")
    assert found is not None and found.id == created.id


async def test_a_personal_account_has_no_org_and_notifies_its_own_email(db_session):
    account = await get_or_create_account(db_session, email="me@example.com", clerk_user_id="u1")

    assert account.clerk_org_id is None
    assert account.notification_email == "me@example.com"
