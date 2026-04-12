"""signal pending ttl controls

Revision ID: 20260331_01
Revises: 20260330_02
Create Date: 2026-03-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260331_01'
down_revision = '20260330_02'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column('settings', 'pending_review_ttl_sec'):
        op.add_column('settings', sa.Column('pending_review_ttl_sec', sa.Integer(), nullable=True, server_default='900'))
    if not _has_column('settings', 'max_pending_per_symbol'):
        op.add_column('settings', sa.Column('max_pending_per_symbol', sa.Integer(), nullable=True, server_default='1'))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c['name'] for c in insp.get_columns('settings')}
    if 'max_pending_per_symbol' in existing:
        op.drop_column('settings', 'max_pending_per_symbol')
    if 'pending_review_ttl_sec' in existing:
        op.drop_column('settings', 'pending_review_ttl_sec')
