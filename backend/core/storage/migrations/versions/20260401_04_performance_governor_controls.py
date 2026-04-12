"""add performance governor settings controls

Revision ID: 20260401_04
Revises: 20260401_03
Create Date: 2026-04-01 19:45:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_04'
down_revision = '20260401_03'
branch_labels = None
depends_on = None


COLUMNS = [
    ('performance_governor_enabled', sa.Boolean(), sa.true()),
    ('performance_governor_lookback_days', sa.Integer(), '45'),
    ('performance_governor_min_closed_trades', sa.Integer(), '3'),
    ('performance_governor_strict_whitelist', sa.Boolean(), sa.true()),
    ('performance_governor_auto_suppress', sa.Boolean(), sa.true()),
    ('performance_governor_max_execution_error_rate', sa.Numeric(6, 3), '0.35'),
    ('performance_governor_min_take_fill_rate', sa.Numeric(6, 3), '0.20'),
    ('performance_governor_pass_risk_multiplier', sa.Numeric(6, 3), '1.20'),
    ('performance_governor_fail_risk_multiplier', sa.Numeric(6, 3), '0.60'),
    ('performance_governor_threshold_bonus', sa.Integer(), '6'),
    ('performance_governor_threshold_penalty', sa.Integer(), '10'),
    ('performance_governor_execution_priority_boost', sa.Numeric(6, 3), '1.20'),
    ('performance_governor_execution_priority_penalty', sa.Numeric(6, 3), '0.70'),
    ('performance_governor_allocator_boost', sa.Numeric(6, 3), '1.15'),
    ('performance_governor_allocator_penalty', sa.Numeric(6, 3), '0.80'),
]


def upgrade() -> None:
    for name, col_type, default in COLUMNS:
        op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=sa.text(default)))


def downgrade() -> None:
    for name, *_ in reversed(COLUMNS):
        op.drop_column('settings', name)
