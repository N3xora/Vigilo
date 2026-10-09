"""Per-organisation billing: one Stripe customer per organisation, and a guard
against out-of-order webhook delivery. `organizations.billing_customer_id`
stores the Stripe customer a checkout created, so the next checkout for the
same organisation reuses it instead of creating a second customer.
`subscriptions.provider_event_created` is the creation time of the last Stripe
event applied; an older event arriving later is ignored.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-08 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("billing_customer_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        op.f("uq_organizations_billing_customer_id"), "organizations", ["billing_customer_id"]
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_event_created", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "provider_event_created")
    op.drop_constraint(op.f("uq_organizations_billing_customer_id"), "organizations", type_="unique")
    op.drop_column("organizations", "billing_customer_id")
