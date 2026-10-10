"""Show a pending cancellation. When a customer cancels in Stripe's portal the
subscription stays active until the period ends and Stripe flags it with
`cancel_at_period_end`; the billing view needs that to say "ends on <date>"
instead of looking like a normal renewal.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-08 12:00:00.000000
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
    op.add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "cancel_at_period_end")
