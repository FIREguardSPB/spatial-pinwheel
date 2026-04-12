"""forensics export and automatic degrade/freeze policy controls

Revision ID: 20260401_03
Revises: 20260401_02
Create Date: 2026-04-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260401_03'
down_revision = '20260401_02'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    columns = [
        ('auto_degrade_enabled', sa.Boolean(), 'true'),
        ('auto_freeze_enabled', sa.Boolean(), 'true'),
        ('auto_policy_lookback_days', sa.Integer(), '14'),
        ('auto_degrade_max_execution_errors', sa.Integer(), '4'),
        ('auto_freeze_max_execution_errors', sa.Integer(), '10'),
        ('auto_degrade_min_profit_factor', sa.Numeric(6, 3), '0.95'),
        ('auto_freeze_min_profit_factor', sa.Numeric(6, 3), '0.70'),
        ('auto_degrade_min_expectancy', sa.Numeric(18, 4), '-50.0'),
        ('auto_freeze_min_expectancy', sa.Numeric(18, 4), '-250.0'),
        ('auto_degrade_drawdown_pct', sa.Numeric(6, 3), '2.5'),
        ('auto_freeze_drawdown_pct', sa.Numeric(6, 3), '5.0'),
        ('auto_degrade_risk_multiplier', sa.Numeric(6, 3), '0.55'),
        ('auto_degrade_threshold_penalty', sa.Integer(), '8'),
        ('auto_freeze_new_entries', sa.Boolean(), 'true'),
    ]
    for name, col_type, default in columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c['name'] for c in insp.get_columns('settings')}
    for name in [
        'auto_freeze_new_entries',
        'auto_degrade_threshold_penalty',
        'auto_degrade_risk_multiplier',
        'auto_freeze_drawdown_pct',
        'auto_degrade_drawdown_pct',
        'auto_freeze_min_expectancy',
        'auto_degrade_min_expectancy',
        'auto_freeze_min_profit_factor',
        'auto_degrade_min_profit_factor',
        'auto_freeze_max_execution_errors',
        'auto_degrade_max_execution_errors',
        'auto_policy_lookback_days',
        'auto_freeze_enabled',
        'auto_degrade_enabled',
    ]:
        if name in existing:
            op.drop_column('settings', name)
