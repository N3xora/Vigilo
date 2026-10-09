"""Writing to an organisation's audit trail from API routes.

One call per notable action: who did it (the account), what, to what, and a
small dict of non-sensitive details. Never put secrets in `details`: no tokens,
no API key plaintext, no card data. Callers pass names and ids, not credentials.
"""

from __future__ import annotations

import base64
import contextlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vigilo_identity.models import Account
from vigilo_identity.org_repository import get_org
from vigilo_identity.orm import AccountRow
from vigilo_security.audit import AuditEvent, audit
from vigilo_security.orm import AuditEventRow


async def record(
    session: AsyncSession,
    account: Account,
    org_id: uuid.UUID | None,
    action: str,
    subject: str,
    **details: object,
) -> None:
    await audit(
        session,
        AuditEvent(
            actor=str(account.id),
            action=action,
            subject=subject[:255],
            account_id=account.id,
            org_id=org_id,
            metadata={k: v for k, v in details.items() if v is not None},
        ),
    )


# --- reading -----------------------------------------------------------------


_SYSTEM_ACTORS = {
    "stripe": "Stripe",
    "scanner": "Scanner",
    "monitoring": "Monitoring",
    "api": "API",
    "public_api": "API key",
}
# Belt and braces: nothing here writes secrets, but never return a field whose
# name suggests one.
_SECRETISH = re.compile(r"token|secret|password|authorization|api_key", re.IGNORECASE)


@dataclass(frozen=True)
class AuditEntry:
    id: uuid.UUID
    occurred_at: datetime
    action: str
    subject: str
    actor_kind: str  # "person" | "system"
    actor_label: str
    details: dict


def encode_cursor(occurred_at: datetime, event_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{occurred_at.isoformat()}|{event_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    at, _, ident = raw.partition("|")
    return datetime.fromisoformat(at), uuid.UUID(ident)


async def list_audit_entries(
    session: AsyncSession,
    org_id: uuid.UUID,
    *,
    limit: int = 50,
    before: tuple[datetime, uuid.UUID] | None = None,
    action: str | None = None,
) -> tuple[list[AuditEntry], str | None, list[str]]:
    """Newest first, keyset-paginated. Returns `(entries, next_cursor, actions)`
    where `actions` lists the distinct actions in this organisation's trail (for
    a filter menu). A personal organisation also shows its owner's events from
    before `org_id` was recorded (those rows are append-only and cannot be
    updated, so they are attributed here instead)."""
    org = await get_org(session, org_id)
    scope = AuditEventRow.org_id == org_id
    if org is not None and org.is_personal:
        scope = or_(
            scope, and_(AuditEventRow.org_id.is_(None), AuditEventRow.account_id == org.created_by)
        )

    actions = list(
        (
            await session.execute(
                select(AuditEventRow.action).where(scope).distinct().order_by(AuditEventRow.action)
            )
        ).scalars()
    )

    stmt = select(AuditEventRow).where(scope)
    if action:
        stmt = stmt.where(AuditEventRow.action == action)
    if before is not None:
        at, ident = before
        stmt = stmt.where(
            or_(
                AuditEventRow.occurred_at < at,
                and_(AuditEventRow.occurred_at == at, AuditEventRow.id < ident),
            )
        )
    stmt = stmt.order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.id.desc()).limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    has_more = len(rows) > limit
    rows = rows[:limit]

    person_ids: set[uuid.UUID] = set()
    for r in rows:
        with contextlib.suppress(ValueError):  # system actors ("stripe", "scanner"...) are not ids
            person_ids.add(uuid.UUID(r.actor))
    emails: dict[uuid.UUID, str] = {}
    if person_ids:
        found = await session.execute(
            select(AccountRow.id, AccountRow.email).where(AccountRow.id.in_(person_ids))
        )
        emails = {i: e for i, e in found.all()}

    entries: list[AuditEntry] = []
    for r in rows:
        try:
            who = uuid.UUID(r.actor)
            kind, label = "person", emails.get(who, "Former member")
        except ValueError:
            kind, label = "system", _SYSTEM_ACTORS.get(r.actor, r.actor)
        details = {
            k: v for k, v in (r.event_metadata or {}).items() if not _SECRETISH.search(str(k))
        }
        entries.append(AuditEntry(r.id, r.occurred_at, r.action, r.subject, kind, label, details))

    next_cursor = encode_cursor(rows[-1].occurred_at, rows[-1].id) if has_more and rows else None
    return entries, next_cursor, actions
