"""recalibration and allocator controls

Revision ID: 20260331_04
Revises: 20260331_03
Create Date: 2026-03-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260331_04'
down_revision = '20260331_03'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    columns = [
        ('capital_allocator_min_edge_improvement', sa.Numeric(6, 3), '0.18'),
        ('capital_allocator_max_position_concentration_pct', sa.Numeric(5, 2), '18.0'),
        ('capital_allocator_age_decay_per_hour', sa.Numeric(6, 3), '0.08'),
        ('symbol_recalibration_enabled', sa.Boolean(), 'true'),
        ('symbol_recalibration_hour_msk', sa.Integer(), '4'),
        ('symbol_recalibration_train_limit', sa.Integer(), '6'),
        ('symbol_recalibration_lookback_days', sa.Integer(), '180'),
    ]
    for name, col_type, default in columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c['name'] for c in insp.get_columns('settings')}
    for name in [
        'symbol_recalibration_lookback_days',
        'symbol_recalibration_train_limit',
        'symbol_recalibration_hour_msk',
        'symbol_recalibration_enabled',
        'capital_allocator_age_decay_per_hour',
        'capital_allocator_max_position_concentration_pct',
        'capital_allocator_min_edge_improvement',
    ]:
        if name in existing:
            op.drop_column('settings', name)
