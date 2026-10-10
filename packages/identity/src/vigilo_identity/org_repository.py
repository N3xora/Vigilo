"""Organization tenancy: orgs, memberships, product enablement, usage and
invites (docs/architecture.md §2). Same contract as `repository.py`: every
function takes an open `AsyncSession` and the caller owns the transaction.

Authorization is by explicit `org_id` on every query — there is no row-level
security — so callers resolve membership first (`get_membership`) and pass
the org id down.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import (
    Account,
    Membership,
    MemberWithEmail,
    Organization,
    OrgInvite,
    ProductEnablement,
    UsageCounter,
)
from vigilo_identity.orm import (
    AccountRow,
    MembershipRow,
    OrganizationRow,
    OrgInviteRow,
    ProductEnablementRow,
    SubscriptionRow,
    UsageCounterRow,
)

PRODUCT_SLUGS = ("vigilo", "sentinel", "cspm", "gateway", "neurawall")
# Products this build can actually run. The others are known (they have plans,
# pricing and pages) but their engines are separate projects, so an organisation
# cannot turn them on yet. Add a slug here when its engine is connected.
AVAILABLE_PRODUCTS = ("vigilo",)
ROLES = ("viewer", "member", "admin", "owner")  # ascending privilege
INVITABLE_ROLES = ("viewer", "member", "admin")
INVITE_TTL = timedelta(days=7)
_SLUG_RE = re.compile(r"^[a-z0-9-]{2,48}$")


class OrgError(Exception):
    """Domain error for org operations; `code` is mapped to HTTP by the API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def role_at_least(role: str, minimum: str) -> bool:
    return ROLES.index(role) >= ROLES.index(minimum)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def period_start(today: date | None = None) -> date:
    today = today or datetime.now(UTC).date()
    return today.replace(day=1)


async def create_org(
    session: AsyncSession,
    owner: Account,
    name: str,
    slug: str,
    *,
    is_personal: bool = False,
) -> Organization:
    if not _SLUG_RE.match(slug):
        raise OrgError("invalid_slug", "slug must be 2-48 lowercase letters, digits or dashes")
    org = OrganizationRow(
        name=name.strip(), slug=slug, is_personal=is_personal, created_by=owner.id
    )
    session.add(org)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise OrgError("slug_taken", "that slug is already in use") from exc
    session.add(MembershipRow(org_id=org.id, account_id=owner.id, role="owner"))
    session.add(ProductEnablementRow(org_id=org.id, product_slug="vigilo"))
    await session.flush()
    return Organization.model_validate(org)


async def ensure_personal_org(session: AsyncSession, account: Account) -> Organization:
    """Lazy provisioning, idempotent: the account's personal org, created on
    first use. Accounts that existed before migration 0009 already have one
    from the backfill."""
    result = await session.execute(
        select(OrganizationRow).where(
            OrganizationRow.created_by == account.id, OrganizationRow.is_personal.is_(True)
        )
    )
    row = result.scalars().first()
    if row is not None:
        return Organization.model_validate(row)
    slug = f"personal-{account.id.hex[:12]}"
    try:
        # The slug is derived from the account id, so the unique constraint is
        # the race guard: of two concurrent first requests, one loses here and
        # reads back the winner's row. The savepoint keeps the loser's
        # transaction usable.
        async with session.begin_nested():
            return await create_org(session, account, "Personal workspace", slug, is_personal=True)
    except OrgError as exc:
        if exc.code != "slug_taken":
            raise
    result = await session.execute(select(OrganizationRow).where(OrganizationRow.slug == slug))
    return Organization.model_validate(result.scalar_one())


async def personal_org_id(session: AsyncSession, account_id: uuid.UUID) -> uuid.UUID:
    """The org id that account-scoped writers stamp on new rows (projects,
    subscriptions, api keys, branding). Provisions the personal org if the
    account predates it. Until org-scoped routes pass an explicit org, every
    row belongs to its creator's personal org."""
    row = await session.get(AccountRow, account_id)
    if row is None:
        raise OrgError("not_found", "account not found")
    return (await ensure_personal_org(session, Account.model_validate(row))).id


async def plan_id_for_org(
    session: AsyncSession, org_id: uuid.UUID, product_slug: str = "vigilo"
) -> str | None:
    """An organisation's plan for a product is its own active subscription;
    with none it is on the free plan (`None`). Whoever in the organisation
    acts, they get these limits, and a personal Pro plan does not carry into
    other organisations the same person owns."""
    result = await session.execute(
        select(SubscriptionRow.plan_id)
        .where(
            SubscriptionRow.org_id == org_id,
            SubscriptionRow.product_slug == product_slug,
            SubscriptionRow.status == "active",
        )
        .order_by(SubscriptionRow.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_orgs_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[tuple[Organization, str]]:
    result = await session.execute(
        select(OrganizationRow, MembershipRow.role)
        .join(MembershipRow, MembershipRow.org_id == OrganizationRow.id)
        .where(MembershipRow.account_id == account_id)
        .order_by(OrganizationRow.created_at)
    )
    return [(Organization.model_validate(o), role) for o, role in result.all()]


async def get_membership(
    session: AsyncSession, org_id: uuid.UUID, account_id: uuid.UUID
) -> Membership | None:
    result = await session.execute(
        select(MembershipRow).where(
            MembershipRow.org_id == org_id, MembershipRow.account_id == account_id
        )
    )
    row = result.scalar_one_or_none()
    return Membership.model_validate(row) if row else None


async def get_org(session: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    row = await session.get(OrganizationRow, org_id)
    return Organization.model_validate(row) if row else None


async def list_members(session: AsyncSession, org_id: uuid.UUID) -> list[MemberWithEmail]:
    result = await session.execute(
        select(AccountRow.id, AccountRow.email, MembershipRow.role)
        .join(MembershipRow, MembershipRow.account_id == AccountRow.id)
        .where(MembershipRow.org_id == org_id)
        .order_by(MembershipRow.created_at)
    )
    return [MemberWithEmail(account_id=a, email=e, role=r) for a, e, r in result.all()]


async def set_member_role(
    session: AsyncSession, org_id: uuid.UUID, account_id: uuid.UUID, role: str
) -> Membership:
    if role not in INVITABLE_ROLES:
        raise OrgError("invalid_role", "role must be viewer, member or admin")
    result = await session.execute(
        select(MembershipRow).where(
            MembershipRow.org_id == org_id, MembershipRow.account_id == account_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise OrgError("not_found", "member not found")
    if row.role == "owner":
        raise OrgError("owner_immutable", "the owner's role cannot be changed")
    row.role = role
    await session.flush()
    return Membership.model_validate(row)


async def remove_member(session: AsyncSession, org_id: uuid.UUID, account_id: uuid.UUID) -> None:
    result = await session.execute(
        select(MembershipRow).where(
            MembershipRow.org_id == org_id, MembershipRow.account_id == account_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise OrgError("not_found", "member not found")
    if row.role == "owner":
        raise OrgError("owner_immutable", "the owner cannot be removed")
    await session.execute(delete(MembershipRow).where(MembershipRow.id == row.id))


async def transfer_ownership(
    session: AsyncSession,
    org_id: uuid.UUID,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
) -> None:
    """Hand an organisation to another of its members. The previous owner becomes
    an admin and the organisation's `created_by` follows the owner, so everything
    that treats it as "the owner's account" (the webhook fallback, account deletion)
    stays true. A personal workspace belongs to its person and cannot be handed over.

    The organisation row is locked while this runs, so two transfers cannot both
    succeed; the previous owner is demoted before the new one is promoted, because
    the database allows exactly one owner per organisation at every step."""
    org = (
        await session.execute(
            select(OrganizationRow).where(OrganizationRow.id == org_id).with_for_update()
        )
    ).scalar_one_or_none()
    if org is None:
        raise OrgError("not_found", "organisation not found")
    if org.is_personal:
        raise OrgError("personal_org", "a personal workspace cannot be handed over")
    if from_account_id == to_account_id:
        raise OrgError("invalid_target", "choose someone else to hand the organisation to")

    async def membership(account_id: uuid.UUID) -> MembershipRow | None:
        return (
            await session.execute(
                select(MembershipRow).where(
                    MembershipRow.org_id == org_id, MembershipRow.account_id == account_id
                )
            )
        ).scalar_one_or_none()

    current = await membership(from_account_id)
    if current is None or current.role != "owner":
        raise OrgError("not_owner", "only the current owner can hand the organisation over")
    target = await membership(to_account_id)
    if target is None:
        raise OrgError("not_found", "that person is not a member of this organisation")

    current.role = "admin"
    await session.flush()
    target.role = "owner"
    org.created_by = to_account_id
    await session.flush()


async def create_invite(
    session: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID,
) -> tuple[OrgInvite, str]:
    """Returns `(invite, plaintext_token)`; the token is shown once."""
    if role not in INVITABLE_ROLES:
        raise OrgError("invalid_role", "role must be viewer, member or admin")
    email = email.strip().lower()
    already = await session.execute(
        select(AccountRow.id)
        .join(MembershipRow, MembershipRow.account_id == AccountRow.id)
        .where(MembershipRow.org_id == org_id, func.lower(AccountRow.email) == email)
    )
    if already.first() is not None:
        raise OrgError("already_member", "that person is already a member")
    # One open invitation per address: a new one replaces the old link.
    await session.execute(
        delete(OrgInviteRow).where(
            OrgInviteRow.org_id == org_id,
            OrgInviteRow.email == email,
            OrgInviteRow.accepted_at.is_(None),
        )
    )
    token = f"nxi_{secrets.token_urlsafe(32)}"
    row = OrgInviteRow(
        org_id=org_id,
        email=email,
        role=role,
        token_hash=hash_invite_token(token),
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + INVITE_TTL,
    )
    session.add(row)
    await session.flush()
    return OrgInvite.model_validate(row), token


async def rotate_invite(
    session: AsyncSession, org_id: uuid.UUID, invite_id: uuid.UUID
) -> tuple[OrgInvite, str]:
    """A fresh link and a fresh 7 days for a pending invite. The old link stops
    working, because only the new token's hash is kept."""
    result = await session.execute(
        select(OrgInviteRow).where(
            OrgInviteRow.id == invite_id,
            OrgInviteRow.org_id == org_id,
            OrgInviteRow.accepted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise OrgError("not_found", "invite not found")
    token = f"nxi_{secrets.token_urlsafe(32)}"
    row.token_hash = hash_invite_token(token)
    row.expires_at = datetime.now(UTC) + INVITE_TTL
    await session.flush()
    return OrgInvite.model_validate(row), token


async def list_pending_invites(session: AsyncSession, org_id: uuid.UUID) -> list[OrgInvite]:
    result = await session.execute(
        select(OrgInviteRow)
        .where(OrgInviteRow.org_id == org_id, OrgInviteRow.accepted_at.is_(None))
        .order_by(OrgInviteRow.created_at.desc())
    )
    return [OrgInvite.model_validate(r) for r in result.scalars()]


async def revoke_invite(session: AsyncSession, org_id: uuid.UUID, invite_id: uuid.UUID) -> None:
    result = await session.execute(
        delete(OrgInviteRow)
        .where(
            OrgInviteRow.id == invite_id,
            OrgInviteRow.org_id == org_id,
            OrgInviteRow.accepted_at.is_(None),
        )
        .returning(OrgInviteRow.id)
    )
    if result.first() is None:
        raise OrgError("not_found", "invite not found")


async def accept_invite(session: AsyncSession, token: str, account: Account) -> Membership:
    """The invite must be unexpired, unused, and addressed to the accepting
    account's email. Accepting twice, or into an org the account is already
    in, is a conflict rather than a silent role change."""
    result = await session.execute(
        select(OrgInviteRow).where(OrgInviteRow.token_hash == hash_invite_token(token))
    )
    invite = result.scalar_one_or_none()
    if invite is None or invite.accepted_at is not None:
        raise OrgError("not_found", "invite not found")
    if invite.expires_at < datetime.now(UTC):
        raise OrgError("expired", "invite has expired")
    if invite.email != account.email.lower():
        raise OrgError("not_found", "invite not found")
    if await get_membership(session, invite.org_id, account.id) is not None:
        raise OrgError("already_member", "already a member of this organisation")
    membership = MembershipRow(org_id=invite.org_id, account_id=account.id, role=invite.role)
    session.add(membership)
    invite.accepted_at = datetime.now(UTC)
    await session.flush()
    return Membership.model_validate(membership)


async def list_enablements(session: AsyncSession, org_id: uuid.UUID) -> list[ProductEnablement]:
    result = await session.execute(
        select(ProductEnablementRow).where(ProductEnablementRow.org_id == org_id)
    )
    return [ProductEnablement.model_validate(r) for r in result.scalars()]


async def enable_product(
    session: AsyncSession, org_id: uuid.UUID, product_slug: str
) -> ProductEnablement:
    if product_slug not in PRODUCT_SLUGS:
        raise OrgError("not_found", "unknown product")
    if product_slug not in AVAILABLE_PRODUCTS:
        raise OrgError("not_available", "this product is not open to organisations yet")
    stmt = (
        pg_insert(ProductEnablementRow)
        .values(id=uuid.uuid4(), org_id=org_id, product_slug=product_slug, status="enabled")
        .on_conflict_do_update(
            constraint="uq_product_enablements_org_product", set_={"status": "enabled"}
        )
        .returning(ProductEnablementRow)
    )
    result = await session.execute(stmt)
    return ProductEnablement.model_validate(result.scalar_one())


async def increment_usage(
    session: AsyncSession,
    org_id: uuid.UUID,
    product_slug: str,
    meter: str,
    amount: int = 1,
    *,
    today: date | None = None,
) -> None:
    """Atomic upsert-increment; safe under concurrent callers."""
    if amount < 1:
        raise OrgError("invalid_amount", "amount must be positive")
    stmt = pg_insert(UsageCounterRow).values(
        id=uuid.uuid4(),
        org_id=org_id,
        product_slug=product_slug,
        meter=meter,
        period_start=period_start(today),
        count=amount,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_usage_counters_key",
        set_={"count": UsageCounterRow.count + amount},
    )
    await session.execute(stmt)


async def get_usage_count(
    session: AsyncSession,
    org_id: uuid.UUID,
    product_slug: str,
    meter: str,
    *,
    today: date | None = None,
) -> int:
    """This calendar month's (UTC) count for one meter: the same number the
    Usage page shows, so what a person sees is what the quota checks."""
    result = await session.execute(
        select(UsageCounterRow.count).where(
            UsageCounterRow.org_id == org_id,
            UsageCounterRow.product_slug == product_slug,
            UsageCounterRow.meter == meter,
            UsageCounterRow.period_start == period_start(today),
        )
    )
    return int(result.scalar_one_or_none() or 0)


async def list_usage(
    session: AsyncSession, org_id: uuid.UUID, *, today: date | None = None
) -> list[UsageCounter]:
    result = await session.execute(
        select(UsageCounterRow).where(
            UsageCounterRow.org_id == org_id, UsageCounterRow.period_start == period_start(today)
        )
    )
    return [UsageCounter.model_validate(r) for r in result.scalars()]
