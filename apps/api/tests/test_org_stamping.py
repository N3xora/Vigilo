"""Item 1 of the org cutover: every account-scoped writer stamps the
creator's personal org, so `org_id` can be NOT NULL."""

from __future__ import annotations

from sqlalchemy import select

from vigilo_identity.org_repository import ensure_personal_org
from vigilo_identity.orm import ApiKeyRow, BrandingProfileRow, SubscriptionRow
from vigilo_identity.repository import (
    create_api_key,
    get_or_create_account,
    upsert_branding_profile,
    upsert_subscription,
)
from vigilo_persistence import session_scope
from vigilo_project.orm import ProjectRow
from vigilo_project.repository import get_or_create_default_project


async def test_writers_stamp_the_creators_personal_org(client):
    async with session_scope() as session:
        acc = await get_or_create_account(session, email="stamp@example.com")
        project = await get_or_create_default_project(session, acc.id)
        await create_api_key(session, acc.id, "ci", ["scan:run"])
        await upsert_branding_profile(session, acc.id, footer_text="hi")
        await upsert_subscription(session, acc.id, "pro", "active", "stripe", "sub_stamp", None)
        org = await ensure_personal_org(session, acc)

        for row_cls in (ProjectRow, ApiKeyRow, BrandingProfileRow, SubscriptionRow):
            rows = (await session.execute(select(row_cls))).scalars().all()
            assert len(rows) == 1, row_cls
            assert rows[0].org_id == org.id, row_cls
        assert project.id is not None


async def test_two_accounts_never_share_an_org(client):
    async with session_scope() as session:
        a = await get_or_create_account(session, email="a-stamp@example.com")
        b = await get_or_create_account(session, email="b-stamp@example.com")
        await get_or_create_default_project(session, a.id)
        await get_or_create_default_project(session, b.id)
        rows = (await session.execute(select(ProjectRow))).scalars().all()
        assert len({r.org_id for r in rows}) == 2
