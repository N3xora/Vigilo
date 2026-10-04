"""Organisation-owned accounts: `accounts.clerk_org_id` and
`accounts.contact_email`, both nullable, so every existing (per-user)
account is untouched and the migration is a pure add (downgrade drops them).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("clerk_org_id", sa.String(length=128), nullable=True))
    op.add_column("accounts", sa.Column("contact_email", sa.String(length=320), nullable=True))
    op.create_unique_constraint(op.f("uq_accounts_clerk_org_id"), "accounts", ["clerk_org_id"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_accounts_clerk_org_id"), "accounts", type_="unique")
    op.drop_column("accounts", "contact_email")
    op.drop_column("accounts", "clerk_org_id")
