"""Add fully runtime-controlled economic filter fields.

Revision ID: 20260321_01b
Revises: 20260318_01
Create Date: 2026-03-21 12:40:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260321_01b'
down_revision = '20260321_01'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        if not _has_column('settings', 'min_tick_floor_rub'):
            batch_op.add_column(sa.Column('min_tick_floor_rub', sa.Numeric(18, 6), nullable=True, server_default='0.0'))
        if not _has_column('settings', 'commission_dominance_warn_ratio'):
            batch_op.add_column(sa.Column('commission_dominance_warn_ratio', sa.Numeric(6, 3), nullable=True, server_default='0.30'))
        if not _has_column('settings', 'volatility_sl_floor_multiplier'):
            batch_op.add_column(sa.Column('volatility_sl_floor_multiplier', sa.Numeric(6, 3), nullable=True, server_default='0.0'))
        if not _has_column('settings', 'sl_cost_floor_multiplier'):
            batch_op.add_column(sa.Column('sl_cost_floor_multiplier', sa.Numeric(6, 3), nullable=True, server_default='0.0'))

    op.execute("UPDATE settings SET min_tick_floor_rub = COALESCE(min_tick_floor_rub, 0.0)")
    op.execute("UPDATE settings SET commission_dominance_warn_ratio = COALESCE(commission_dominance_warn_ratio, 0.30)")
    op.execute("UPDATE settings SET volatility_sl_floor_multiplier = COALESCE(volatility_sl_floor_multiplier, 0.0)")
    op.execute("UPDATE settings SET sl_cost_floor_multiplier = COALESCE(sl_cost_floor_multiplier, 0.0)")


def downgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        if _has_column('settings', 'sl_cost_floor_multiplier'):
            batch_op.drop_column('sl_cost_floor_multiplier')
        if _has_column('settings', 'volatility_sl_floor_multiplier'):
            batch_op.drop_column('volatility_sl_floor_multiplier')
        if _has_column('settings', 'commission_dominance_warn_ratio'):
            batch_op.drop_column('commission_dominance_warn_ratio')
        if _has_column('settings', 'min_tick_floor_rub'):
            batch_op.drop_column('min_tick_floor_rub')
