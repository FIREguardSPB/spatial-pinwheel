"""add api_tokens table

Revision ID: 0003_api_tokens
Revises: 818dacab6670
Create Date: 2026-03-07

P8-01: Table for UI-managed API tokens.
Allows managing all secrets (AUTH_TOKEN, CLAUDE_API_KEY, TELEGRAM_BOT_TOKEN, etc.)
directly from the web UI without editing config files or restarting services.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_api_tokens"
down_revision = "818dacab6670"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id",           sa.String(),  primary_key=True),
        sa.Column("key_name",     sa.String(),  nullable=False),
        sa.Column("value",        sa.String(),  nullable=False, server_default=""),
        sa.Column("label",        sa.String(),  server_default=""),
        sa.Column("description",  sa.String(),  server_default=""),
        sa.Column("category",     sa.String(),  server_default="general"),
        sa.Column("is_active",    sa.Boolean(), server_default="true"),
        sa.Column("created_ts",   sa.BigInteger(), nullable=True),
        sa.Column("updated_ts",   sa.BigInteger(), nullable=True),
        sa.Column("last_used_ts", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "idx_api_tokens_key_name",
        "api_tokens",
        ["key_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_api_tokens_key_name", table_name="api_tokens")
    op.drop_table("api_tokens")
