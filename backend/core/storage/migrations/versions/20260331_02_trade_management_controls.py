"""trade management controls and position telemetry

Revision ID: 20260331_02
Revises: 20260331_01
Create Date: 2026-03-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260331_02'
down_revision = '20260331_01'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    settings_columns = [
        ('adaptive_exit_partial_cooldown_sec', sa.Integer(), '180'),
        ('adaptive_exit_max_partial_closes', sa.Integer(), '2'),
    ]
    for name, col_type, default in settings_columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))

    position_columns = [
        ('partial_closes_count', sa.Integer(), '0'),
        ('last_partial_close_ts', sa.BigInteger(), None),
        ('last_mark_price', sa.Numeric(18, 9), None),
        ('last_mark_ts', sa.BigInteger(), None),
    ]
    for name, col_type, default in position_columns:
        if not _has_column('positions', name):
            kwargs = {'nullable': True}
            if default is not None:
                kwargs['server_default'] = default
            op.add_column('positions', sa.Column(name, col_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    settings_existing = {c['name'] for c in insp.get_columns('settings')}
    positions_existing = {c['name'] for c in insp.get_columns('positions')}
    for name in ['last_mark_ts', 'last_mark_price', 'last_partial_close_ts', 'partial_closes_count']:
        if name in positions_existing:
            op.drop_column('positions', name)
    for name in ['adaptive_exit_max_partial_closes', 'adaptive_exit_partial_cooldown_sec']:
        if name in settings_existing:
            op.drop_column('settings', name)
