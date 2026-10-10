"""Organizations (docs/architecture.md §2, replica/schema.sql). Step 1 of a
three-step tenancy migration: add the org tables, add NULLABLE `org_id`
columns to projects/subscriptions/api_keys/branding_profiles, and backfill a
personal organization (with an owner membership and Vigilo enabled) for every
existing account. A later migration sets `org_id` NOT NULL once every writer
sets it. Nothing here removes or changes existing columns, so the previous
release keeps working against this schema.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clerk_org_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=48), nullable=False),
        sa.Column("is_personal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["accounts.id"], name=op.f("fk_organizations_created_by_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("clerk_org_id", name=op.f("uq_organizations_clerk_org_id")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_index(op.f("ix_organizations_created_by"), "organizations", ["created_by"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "role in ('owner','admin','member','viewer')", name=op.f("ck_memberships_role")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_memberships_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("org_id", "account_id", name="uq_memberships_org_id_account_id"),
    )
    op.create_index(op.f("ix_memberships_org_id"), "memberships", ["org_id"])
    op.create_index(op.f("ix_memberships_account_id"), "memberships", ["account_id"])
    op.create_index(
        "uq_memberships_one_owner_per_org",
        "memberships",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )

    op.create_table(
        "product_enablements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("product_slug", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="enabled"),
        sa.Column("enabled_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint(
            "product_slug in ('vigilo','sentinel','cspm','gateway','neurawall')",
            name=op.f("ck_product_enablements_slug"),
        ),
        sa.CheckConstraint(
            "status in ('enabled','disabled')", name=op.f("ck_product_enablements_status")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_product_enablements_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_enablements")),
        sa.UniqueConstraint("org_id", "product_slug", name="uq_product_enablements_org_product"),
    )
    op.create_index(op.f("ix_product_enablements_org_id"), "product_enablements", ["org_id"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("product_slug", sa.String(length=32), nullable=False),
        sa.Column("meter", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("count >= 0", name=op.f("ck_usage_counters_count")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_usage_counters_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_counters")),
        sa.UniqueConstraint(
            "org_id", "product_slug", "meter", "period_start", name="uq_usage_counters_key"
        ),
    )
    op.create_index(op.f("ix_usage_counters_org_id"), "usage_counters", ["org_id"])

    op.create_table(
        "org_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.CheckConstraint("role in ('admin','member','viewer')", name=op.f("ck_org_invites_role")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_org_invites_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["accounts.id"],
            name=op.f("fk_org_invites_invited_by_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_org_invites_token_hash")),
    )
    op.create_index(op.f("ix_org_invites_org_id"), "org_invites", ["org_id"])

    # Existing tables: nullable org_id (+ product/interval on subscriptions).
    for table in ("projects", "subscriptions", "api_keys", "branding_profiles"):
        op.add_column(table, sa.Column("org_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_org_id_organizations"),
            table,
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(op.f(f"ix_{table}_org_id"), table, ["org_id"])
    op.add_column(
        "subscriptions",
        sa.Column("product_slug", sa.String(length=32), server_default="vigilo", nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("billing_interval", sa.String(length=8), server_default="month", nullable=False),
    )

    # Backfill: one personal org per account, then point existing rows at it.
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, is_personal, created_by)
        SELECT gen_random_uuid(), 'Personal workspace',
               'personal-' || substr(replace(id::text, '-', ''), 1, 12), true, id
        FROM accounts
        """
    )
    op.execute(
        """
        INSERT INTO memberships (id, org_id, account_id, role)
        SELECT gen_random_uuid(), o.id, o.created_by, 'owner'
        FROM organizations o WHERE o.is_personal
        """
    )
    op.execute(
        """
        INSERT INTO product_enablements (id, org_id, product_slug)
        SELECT gen_random_uuid(), o.id, 'vigilo' FROM organizations o WHERE o.is_personal
        """
    )
    for table in ("projects", "subscriptions", "api_keys", "branding_profiles"):
        op.execute(
            f"""
            UPDATE {table} t SET org_id = o.id
            FROM organizations o
            WHERE o.is_personal AND o.created_by = t.account_id
            """
        )


def downgrade() -> None:
    for table in ("branding_profiles", "api_keys", "subscriptions", "projects"):
        op.drop_index(op.f(f"ix_{table}_org_id"), table_name=table)
        op.drop_constraint(op.f(f"fk_{table}_org_id_organizations"), table, type_="foreignkey")
        op.drop_column(table, "org_id")
    op.drop_column("subscriptions", "billing_interval")
    op.drop_column("subscriptions", "product_slug")
    op.drop_table("org_invites")
    op.drop_table("usage_counters")
    op.drop_table("product_enablements")
    op.drop_table("memberships")
    op.drop_table("organizations")
