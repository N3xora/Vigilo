"""Audit log per organisation. `audit_events.org_id` records which organisation an
event belongs to so owners and admins can read their own trail. Deliberately
NOT a foreign key: the table is append-only (a trigger rejects UPDATE/DELETE),
and an ON DELETE rule on a foreign key would be exactly such an UPDATE/DELETE
when an organisation is removed. Events written before this migration keep
`org_id` NULL (they cannot be updated); the read side attributes those to the
acting account's personal organisation.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-08 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("org_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_audit_events_org_id_occurred_at", "audit_events", ["org_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_org_id_occurred_at", table_name="audit_events")
    op.drop_column("audit_events", "org_id")
