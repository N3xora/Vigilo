from __future__ import annotations

from vigilo_identity.repository import (
    get_account_by_clerk_org_id,
    get_or_create_account,
    get_or_create_org_account,
    org_account_email,
    set_org_account_plan,
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


async def test_set_plan_creates_a_paid_org_account_without_a_contact(db_session):
    account = await set_org_account_plan(db_session, "org_9", "pro")

    assert account is not None
    assert (account.plan_id, account.clerk_org_id, account.contact_email) == ("pro", "org_9", None)


async def test_set_plan_never_creates_an_account_for_a_downgrade(db_session):
    assert await set_org_account_plan(db_session, "org_ghost", "free") is None
    assert await get_account_by_clerk_org_id(db_session, "org_ghost") is None


async def test_set_plan_updates_an_existing_account_and_keeps_its_contact(db_session):
    await get_or_create_org_account(db_session, "org_9", "owner@example.com")

    await set_org_account_plan(db_session, "org_9", "pro")
    account = await set_org_account_plan(db_session, "org_9", "free")

    assert account is not None
    assert (account.plan_id, account.notification_email) == ("free", "owner@example.com")


async def test_the_first_acting_member_becomes_the_contact_of_a_synced_account(db_session):
    await set_org_account_plan(db_session, "org_9", "pro")

    account = await get_or_create_org_account(db_session, "org_9", "alice@example.com")

    assert account.contact_email == "alice@example.com"
    # A later member does not take over the contact.
    again = await get_or_create_org_account(db_session, "org_9", "bob@example.com")
    assert again.contact_email == "alice@example.com"
