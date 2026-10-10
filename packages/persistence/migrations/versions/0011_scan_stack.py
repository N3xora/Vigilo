"""Scan stack (replica/fixes.md item 2): the hosting, framework and backend
signals observed during a scan, stored on the scan so a report can say why a
finding matters for this particular app without reloading the evidence bundle
from object storage. Nullable: scans recorded earlier have no stack.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-07 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("stack", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "stack")
