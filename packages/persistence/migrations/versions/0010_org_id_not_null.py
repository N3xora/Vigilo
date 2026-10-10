"""Step 3 of the tenancy migration: `org_id` becomes NOT NULL on projects,
subscriptions, api_keys and branding_profiles. Every writer now stamps the
creator's personal org (`personal_org_id()`); this migration first repairs
anything written between 0009 and that deploy — accounts created since the
backfill have no personal org, and their rows have `org_id IS NULL`.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("projects", "subscriptions", "api_keys", "branding_profiles")


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, is_personal, created_by)
        SELECT gen_random_uuid(), 'Personal workspace',
               'personal-' || substr(replace(a.id::text, '-', ''), 1, 12), true, a.id
        FROM accounts a
        WHERE NOT EXISTS (
            SELECT 1 FROM organizations o WHERE o.created_by = a.id AND o.is_personal
        )
        """
    )
    op.execute(
        """
        INSERT INTO memberships (id, org_id, account_id, role)
        SELECT gen_random_uuid(), o.id, o.created_by, 'owner'
        FROM organizations o
        WHERE o.is_personal
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.org_id = o.id)
        """
    )
    op.execute(
        """
        INSERT INTO product_enablements (id, org_id, product_slug)
        SELECT gen_random_uuid(), o.id, 'vigilo'
        FROM organizations o
        WHERE o.is_personal
          AND NOT EXISTS (
              SELECT 1 FROM product_enablements e
              WHERE e.org_id = o.id AND e.product_slug = 'vigilo'
          )
        """
    )
    for table in _TABLES:
        op.execute(
            f"""
            UPDATE {table} t SET org_id = o.id
            FROM organizations o
            WHERE t.org_id IS NULL AND o.is_personal AND o.created_by = t.account_id
            """
        )
        op.alter_column(table, "org_id", nullable=False)


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "org_id", nullable=True)
