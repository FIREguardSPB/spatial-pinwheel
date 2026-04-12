"""pm throttle controls

Revision ID: 20260401_01
Revises: 20260331_04
Create Date: 2026-04-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260401_01'
down_revision = '20260331_04'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    columns = [
        ('pm_risk_throttle_enabled', sa.Boolean(), 'true'),
        ('pm_drawdown_soft_limit_pct', sa.Numeric(5, 2), '1.5'),
        ('pm_drawdown_hard_limit_pct', sa.Numeric(5, 2), '3.0'),
        ('pm_loss_streak_soft_limit', sa.Integer(), '2'),
        ('pm_loss_streak_hard_limit', sa.Integer(), '4'),
        ('pm_min_risk_multiplier', sa.Numeric(6, 3), '0.35'),
    ]
    for name, col_type, default in columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c['name'] for c in insp.get_columns('settings')}
    for name in [
        'pm_min_risk_multiplier',
        'pm_loss_streak_hard_limit',
        'pm_loss_streak_soft_limit',
        'pm_drawdown_hard_limit_pct',
        'pm_drawdown_soft_limit_pct',
        'pm_risk_throttle_enabled',
    ]:
        if name in existing:
            op.drop_column('settings', name)
