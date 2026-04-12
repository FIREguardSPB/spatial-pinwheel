"""signal freshness controls

Revision ID: 20260331_03
Revises: 20260331_02
Create Date: 2026-03-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260331_03'
down_revision = '20260331_02'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    columns = [
        ('signal_freshness_enabled', sa.Boolean(), 'true'),
        ('signal_freshness_grace_bars', sa.Numeric(6, 2), '1.0'),
        ('signal_freshness_penalty_per_bar', sa.Integer(), '6'),
        ('signal_freshness_max_bars', sa.Numeric(6, 2), '3.0'),
    ]
    for name, col_type, default in columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c['name'] for c in insp.get_columns('settings')}
    for name in ['signal_freshness_max_bars', 'signal_freshness_penalty_per_bar', 'signal_freshness_grace_bars', 'signal_freshness_enabled']:
        if name in existing:
            op.drop_column('settings', name)
