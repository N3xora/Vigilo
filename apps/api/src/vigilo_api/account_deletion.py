"""Deleting a person's account and the data that is theirs.

What goes: the account; every organisation they own (they are its only member,
see the blockers); everything under those organisations (targets, scans,
findings, reports, share links, monitors, alerts, risks, keys, branding,
subscriptions, usage, invitations); their memberships elsewhere.

What stays, and why:
* Rows other people's organisations hold that this person created (a project,
  an API key, a monitor...) stay with those organisations. Their "created by" is
  moved to the organisation's owner, because the data belongs to the team.
* The audit trail stays, append-only, holding a pseudonymous account id that now
  reads as "Former member". It can name other people's addresses (for example
  an invitation) so it cannot be scrubbed row by row.
* Stripe keeps the customer and its invoices for the company's accounting.

Blockers (both are things a person must do first, because we cannot undo them
for someone else): an owned organisation that still has other members, and an
owned organisation with a paid plan that is not already set to end.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import Account
from vigilo_identity.orm import (
    AccountRow,
    ApiKeyRow,
    BrandingProfileRow,
    MembershipRow,
    OrganizationRow,
    OrgInviteRow,
    ProductEnablementRow,
    SubscriptionRow,
    UsageCounterRow,
)
from vigilo_monitoring.orm import AlertRow, MonitorRow
from vigilo_orchestrator.orm import FindingRow, ReportRow, ScanJobRow, ScanRow, ShareLinkRow
from vigilo_project.orm import OwnershipProofRow, ProjectRow, SuppressionRow, TargetRow


@dataclass(frozen=True)
class Blocker:
    kind: str  # "members" | "subscription"
    org_id: uuid.UUID
    org_name: str
    detail: str


@dataclass
class DeletionResult:
    org_ids: list[uuid.UUID] = field(default_factory=list)
    bundle_ids: list[str] = field(default_factory=list)
    report_ids: list[uuid.UUID] = field(default_factory=list)


async def _owned_orgs(session: AsyncSession, account_id: uuid.UUID) -> list[OrganizationRow]:
    result = await session.execute(
        select(OrganizationRow)
        .join(MembershipRow, MembershipRow.org_id == OrganizationRow.id)
        .where(MembershipRow.account_id == account_id, MembershipRow.role == "owner")
    )
    return list(result.scalars())


async def deletion_blockers(session: AsyncSession, account: Account) -> list[Blocker]:
    blockers: list[Blocker] = []
    for org in await _owned_orgs(session, account.id):
        others = (
            await session.execute(
                select(func.count())
                .select_from(MembershipRow)
                .where(MembershipRow.org_id == org.id, MembershipRow.account_id != account.id)
            )
        ).scalar_one()
        if others:
            noun = "member" if others == 1 else "members"
            blockers.append(
                Blocker(
                    "members",
                    org.id,
                    org.name,
                    f"{org.name} still has {others} other {noun}. "
                    "Hand the organisation to one of them, or remove them first.",
                )
            )
        paying = (
            await session.execute(
                select(func.count())
                .select_from(SubscriptionRow)
                .where(
                    SubscriptionRow.org_id == org.id,
                    SubscriptionRow.status == "active",
                    SubscriptionRow.cancel_at_period_end.is_(False),
                )
            )
        ).scalar_one()
        if paying:
            blockers.append(
                Blocker(
                    "subscription",
                    org.id,
                    org.name,
                    (
                        f"{org.name} has a paid plan that is still renewing. "
                        "Cancel it in billing first."
                    ),
                )
            )
    return blockers


async def delete_account(session: AsyncSession, account: Account) -> DeletionResult:
    """Caller must have checked `deletion_blockers()`. One transaction."""
    me = account.id
    owned = await _owned_orgs(session, me)
    owned_ids = [o.id for o in owned]
    result = DeletionResult(org_ids=owned_ids)

    # 1. Organisations I only belong to: hand my "created by" marks to their owner.
    member_of = (
        await session.execute(
            select(MembershipRow.org_id).where(
                MembershipRow.account_id == me, MembershipRow.role != "owner"
            )
        )
    ).scalars()
    for org_id in list(member_of):
        owner_id = (
            await session.execute(
                select(MembershipRow.account_id).where(
                    MembershipRow.org_id == org_id, MembershipRow.role == "owner"
                )
            )
        ).scalar_one_or_none()
        if owner_id is None:
            continue
        for model in (ProjectRow, ApiKeyRow, BrandingProfileRow, SubscriptionRow):
            await session.execute(
                update(model)
                .where(model.org_id == org_id, model.account_id == me)
                .values(account_id=owner_id)
            )
        org_targets = (
            select(TargetRow.id)
            .join(ProjectRow, ProjectRow.id == TargetRow.project_id)
            .where(ProjectRow.org_id == org_id)
        )
        await session.execute(
            update(MonitorRow)
            .where(MonitorRow.account_id == me, MonitorRow.target_id.in_(org_targets))
            .values(account_id=owner_id)
        )
        await session.execute(
            update(SuppressionRow)
            .where(
                SuppressionRow.created_by_account_id == me,
                SuppressionRow.target_id.in_(org_targets),
            )
            .values(created_by_account_id=owner_id)
        )

    # 2. Organisations I own: everything underneath, deepest first.
    if owned_ids:
        targets = (
            select(TargetRow.id)
            .join(ProjectRow, ProjectRow.id == TargetRow.project_id)
            .where(ProjectRow.org_id.in_(owned_ids))
        )
        scans = select(ScanRow.id).where(ScanRow.target_id.in_(targets))
        reports = select(ReportRow.id).where(ReportRow.scan_id.in_(scans))

        result.bundle_ids = [
            b
            for b in (
                await session.execute(
                    select(ScanRow.bundle_id).where(
                        ScanRow.target_id.in_(targets), ScanRow.bundle_id.is_not(None)
                    )
                )
            ).scalars()
        ]
        result.report_ids = list((await session.execute(reports)).scalars())

        await session.execute(delete(ShareLinkRow).where(ShareLinkRow.report_id.in_(reports)))
        await session.execute(delete(ReportRow).where(ReportRow.scan_id.in_(scans)))
        await session.execute(delete(AlertRow).where(AlertRow.target_id.in_(targets)))
        await session.execute(delete(FindingRow).where(FindingRow.scan_id.in_(scans)))
        await session.execute(delete(ScanRow).where(ScanRow.target_id.in_(targets)))
        await session.execute(delete(MonitorRow).where(MonitorRow.target_id.in_(targets)))
        await session.execute(delete(SuppressionRow).where(SuppressionRow.target_id.in_(targets)))
        await session.execute(
            delete(OwnershipProofRow).where(OwnershipProofRow.target_id.in_(targets))
        )
        await session.execute(delete(ScanJobRow).where(ScanJobRow.target_id.in_(targets)))
        await session.execute(
            delete(TargetRow).where(
                TargetRow.project_id.in_(
                    select(ProjectRow.id).where(ProjectRow.org_id.in_(owned_ids))
                )
            )
        )
        await session.execute(delete(ProjectRow).where(ProjectRow.org_id.in_(owned_ids)))
        for model in (
            SubscriptionRow,
            ApiKeyRow,
            BrandingProfileRow,
            ProductEnablementRow,
            UsageCounterRow,
            OrgInviteRow,
            MembershipRow,
        ):
            await session.execute(delete(model).where(model.org_id.in_(owned_ids)))
        await session.execute(delete(OrganizationRow).where(OrganizationRow.id.in_(owned_ids)))

    # 3. The account (memberships elsewhere go with it by ON DELETE CASCADE).
    await session.execute(delete(AccountRow).where(AccountRow.id == me))
    return result
