"""Add economic viability settings defaults.

Revision ID: 20260315_02
Revises: 20260315_01
Create Date: 2026-03-15 21:55:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260315_02'
down_revision = '20260315_01'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        if not _has_column('settings', 'min_sl_distance_pct'):
            batch_op.add_column(sa.Column('min_sl_distance_pct', sa.Numeric(6, 3), nullable=True, server_default='0.5'))
        if not _has_column('settings', 'min_profit_after_costs_multiplier'):
            batch_op.add_column(sa.Column('min_profit_after_costs_multiplier', sa.Numeric(6, 3), nullable=True, server_default='2.0'))
        if not _has_column('settings', 'min_trade_value_rub'):
            batch_op.add_column(sa.Column('min_trade_value_rub', sa.Numeric(18, 4), nullable=True, server_default='1000.0'))
        if not _has_column('settings', 'min_instrument_price_rub'):
            batch_op.add_column(sa.Column('min_instrument_price_rub', sa.Numeric(18, 4), nullable=True, server_default='10.0'))

    op.execute("UPDATE settings SET min_sl_distance_pct = COALESCE(min_sl_distance_pct, 0.5)")
    op.execute("UPDATE settings SET min_profit_after_costs_multiplier = COALESCE(min_profit_after_costs_multiplier, 2.0)")
    op.execute("UPDATE settings SET min_trade_value_rub = COALESCE(min_trade_value_rub, 1000.0)")
    op.execute("UPDATE settings SET min_instrument_price_rub = COALESCE(min_instrument_price_rub, 10.0)")


def downgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        if _has_column('settings', 'min_instrument_price_rub'):
            batch_op.drop_column('min_instrument_price_rub')
        if _has_column('settings', 'min_trade_value_rub'):
            batch_op.drop_column('min_trade_value_rub')
        if _has_column('settings', 'min_profit_after_costs_multiplier'):
            batch_op.drop_column('min_profit_after_costs_multiplier')
        if _has_column('settings', 'min_sl_distance_pct'):
            batch_op.drop_column('min_sl_distance_pct')
