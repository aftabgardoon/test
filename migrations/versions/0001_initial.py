"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-18

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("platform_user_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform", "platform_user_id", name="uq_users_platform_id"),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("platform_channel_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_channels_user_id", "channels", ["user_id"])

    op.create_table(
        "sync_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sync_links_user_id", "sync_links", ["user_id"])
    op.create_index("ix_sync_links_source_channel_id", "sync_links", ["source_channel_id"])
    op.create_index("ix_sync_links_destination_channel_id", "sync_links", ["destination_channel_id"])

    op.create_table(
        "message_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_link_id", sa.Integer(), sa.ForeignKey("sync_links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_message_id", sa.String(length=128), nullable=False),
        sa.Column("destination_message_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_message_logs_sync_link_id", "message_logs", ["sync_link_id"])

    op.create_table(
        "bot_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bot_tokens_platform", "bot_tokens", ["platform"])


def downgrade() -> None:
    op.drop_table("bot_tokens")
    op.drop_table("message_logs")
    op.drop_table("sync_links")
    op.drop_table("channels")
    op.drop_table("users")
