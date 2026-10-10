"""Let the audit trail outlive an account. `audit_events.account_id` was a
foreign key to `accounts`, which would make deleting an account impossible
(the table is append-only, so its rows can be neither deleted nor nulled).
Dropping the constraint keeps the security record, which then holds only a
pseudonymous id for a deleted person; readers show it as "Former member".

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-09 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK = "fk_audit_events_account_id_accounts"


def upgrade() -> None:
    op.drop_constraint(_FK, "audit_events", type_="foreignkey")


def downgrade() -> None:
    # Fails if events reference accounts that were deleted since: by design,
    # restoring the constraint over orphaned history would be wrong.
    op.create_foreign_key(_FK, "audit_events", "accounts", ["account_id"], ["id"])
