"""authorized users for the manager bot

Revision ID: 0002_authorized_users
Revises: 0001_initial
Create Date: 2026-09-23

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_authorized_users"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    """Whether ``name`` already exists (e.g. created by ``create_all``)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    # ``init_db()`` calls ``create_all`` on startup, which may already have
    # created this table before ``alembic upgrade`` runs.  Skip in that case
    # so the migration is safe to run in any order.
    if _table_exists("authorized_users"):
        return

    op.create_table(
        "authorized_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("platform_user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "platform", "platform_user_id", name="uq_authorized_platform_id"
        ),
    )


def downgrade() -> None:
    if _table_exists("authorized_users"):
        op.drop_table("authorized_users")
