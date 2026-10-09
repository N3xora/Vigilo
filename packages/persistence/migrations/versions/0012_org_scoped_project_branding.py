"""Org-scoped reads: one project per organisation, one branding profile per
organisation. Before this, both were one-per-account; a second org (or a
teammate acting in someone's org) needs them keyed by `org_id`. Safe on
existing data: 0009/0010 gave every account exactly one personal org, so each
org has at most one project and one profile today.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-07 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_projects_org_id"), table_name="projects")
    op.create_index(op.f("ix_projects_org_id"), "projects", ["org_id"], unique=True)

    op.drop_index(op.f("ix_branding_profiles_account_id"), table_name="branding_profiles")
    op.create_index(
        op.f("ix_branding_profiles_account_id"), "branding_profiles", ["account_id"], unique=False
    )
    op.drop_index(op.f("ix_branding_profiles_org_id"), table_name="branding_profiles")
    op.create_index(op.f("ix_branding_profiles_org_id"), "branding_profiles", ["org_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_branding_profiles_org_id"), table_name="branding_profiles")
    op.create_index(
        op.f("ix_branding_profiles_org_id"), "branding_profiles", ["org_id"], unique=False
    )
    op.drop_index(op.f("ix_branding_profiles_account_id"), table_name="branding_profiles")
    op.create_index(
        op.f("ix_branding_profiles_account_id"), "branding_profiles", ["account_id"], unique=True
    )
    op.drop_index(op.f("ix_projects_org_id"), table_name="projects")
    op.create_index(op.f("ix_projects_org_id"), "projects", ["org_id"], unique=False)
