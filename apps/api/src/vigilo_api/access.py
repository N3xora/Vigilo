"""Who may act on what. Two questions, answered separately:

* Target-scoped routes (a target, its scans, monitors, share links) ask
  `target_role()`: the caller's role in the organisation that owns the
  target's project. No header is needed, and a guessed id leaks nothing.
* List/create routes (targets, API keys, branding) act in the *active*
  organisation: the `X-Org-Id` header if present, else the caller's personal
  organisation. A header naming an organisation the caller is not in is a 404.

Quotas follow the organisation's plan, which is its owner's plan until
billing is per-organisation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import Account
from vigilo_identity.org_repository import (
    ensure_personal_org,
    get_membership,
    plan_id_for_org,
    role_at_least,
)
from vigilo_monitoring.orm import MonitorRow
from vigilo_project.orm import ProjectRow, TargetRow
from vigilo_project.repository import get_project, get_target


@dataclass(frozen=True)
class ActiveOrg:
    org_id: uuid.UUID
    role: str
    plan_id: str | None

    def require(self, minimum: str) -> None:
        if not role_at_least(self.role, minimum):
            raise HTTPException(status_code=403, detail=f"requires {minimum} role")


async def resolve_active_org(
    session: AsyncSession, account: Account, header_org_id: str | None
) -> ActiveOrg:
    if header_org_id:
        try:
            org_id = uuid.UUID(header_org_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="X-Org-Id must be a UUID") from exc
        membership = await get_membership(session, org_id, account.id)
        if membership is None:
            raise HTTPException(status_code=404, detail="organization not found")
        role = membership.role
    else:
        org_id = (await ensure_personal_org(session, account)).id
        role = "owner"
    return ActiveOrg(org_id, role, await plan_id_for_org(session, org_id))


async def target_role(session: AsyncSession, account: Account, target_id: uuid.UUID) -> str | None:
    """The caller's role in the organisation that owns the target's project
    (`"owner"` through `"viewer"`), or `None` for everyone else, including a
    target that does not exist."""
    target = await get_target(session, target_id)
    project = await get_project(session, target.project_id) if target else None
    if project is None:
        return None
    membership = await get_membership(session, project.org_id, account.id)
    return membership.role if membership else None


async def require_target_role(
    session: AsyncSession, account: Account, target_id: uuid.UUID, minimum: str
):
    """Returns the target, or 404 (not a member) / 403 (member, too junior)."""
    role = await target_role(session, account, target_id)
    target = await get_target(session, target_id)
    if role is None or target is None:
        raise HTTPException(status_code=404, detail="target not found")
    if not role_at_least(role, minimum):
        raise HTTPException(status_code=403, detail=f"requires {minimum} role")
    return target


async def org_id_for_target(session: AsyncSession, target_id: uuid.UUID) -> uuid.UUID | None:
    target = await get_target(session, target_id)
    project = await get_project(session, target.project_id) if target else None
    return project.org_id if project else None


async def plan_id_for_target(session: AsyncSession, target_id: uuid.UUID) -> str | None:
    target = await get_target(session, target_id)
    project = await get_project(session, target.project_id) if target else None
    return await plan_id_for_org(session, project.org_id) if project else None


async def count_monitors_for_org(session: AsyncSession, org_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(MonitorRow)
        .join(TargetRow, TargetRow.id == MonitorRow.target_id)
        .join(ProjectRow, ProjectRow.id == TargetRow.project_id)
        .where(ProjectRow.org_id == org_id, MonitorRow.enabled.is_(True))
    )
    return result.scalar_one()
