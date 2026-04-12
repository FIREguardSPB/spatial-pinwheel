"""Add deterministic settings controls, broker schedule fields, and position linkage.

Revision ID: 20260318_01
Revises: 20260315_02
Create Date: 2026-03-18 21:10:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260318_01'
down_revision = '20260315_02'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        if not _has_column('settings', 'max_position_notional_pct_balance'):
            batch_op.add_column(sa.Column('max_position_notional_pct_balance', sa.Numeric(5, 2), nullable=True, server_default='10.0'))
        if not _has_column('settings', 'max_total_exposure_pct_balance'):
            batch_op.add_column(sa.Column('max_total_exposure_pct_balance', sa.Numeric(5, 2), nullable=True, server_default='35.0'))
        if not _has_column('settings', 'signal_reentry_cooldown_sec'):
            batch_op.add_column(sa.Column('signal_reentry_cooldown_sec', sa.Integer(), nullable=True, server_default='300'))
        if not _has_column('settings', 'use_broker_trading_schedule'):
            batch_op.add_column(sa.Column('use_broker_trading_schedule', sa.Boolean(), nullable=True, server_default=sa.text('true')))
        if not _has_column('settings', 'trading_schedule_exchange'):
            batch_op.add_column(sa.Column('trading_schedule_exchange', sa.String(), nullable=True, server_default=''))
        if not _has_column('settings', 'ai_override_policy'):
            batch_op.add_column(sa.Column('ai_override_policy', sa.String(), nullable=True, server_default='promote_only'))
        if not _has_column('settings', 'is_active'):
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))

    with op.batch_alter_table('positions') as batch_op:
        if not _has_column('positions', 'opened_signal_id'):
            batch_op.add_column(sa.Column('opened_signal_id', sa.String(), nullable=True))
        if not _has_column('positions', 'opened_order_id'):
            batch_op.add_column(sa.Column('opened_order_id', sa.String(), nullable=True))
        if not _has_column('positions', 'closed_order_id'):
            batch_op.add_column(sa.Column('closed_order_id', sa.String(), nullable=True))
        if not _has_column('positions', 'entry_fee_est'):
            batch_op.add_column(sa.Column('entry_fee_est', sa.Numeric(18, 9), nullable=True, server_default='0.0'))
        if not _has_column('positions', 'exit_fee_est'):
            batch_op.add_column(sa.Column('exit_fee_est', sa.Numeric(18, 9), nullable=True, server_default='0.0'))
        if not _has_column('positions', 'total_fees_est'):
            batch_op.add_column(sa.Column('total_fees_est', sa.Numeric(18, 9), nullable=True, server_default='0.0'))

    op.execute("UPDATE settings SET max_position_notional_pct_balance = COALESCE(max_position_notional_pct_balance, 10.0)")
    op.execute("UPDATE settings SET max_total_exposure_pct_balance = COALESCE(max_total_exposure_pct_balance, 35.0)")
    op.execute("UPDATE settings SET signal_reentry_cooldown_sec = COALESCE(signal_reentry_cooldown_sec, 300)")
    op.execute("UPDATE settings SET use_broker_trading_schedule = COALESCE(use_broker_trading_schedule, true)")
    op.execute("UPDATE settings SET trading_schedule_exchange = COALESCE(trading_schedule_exchange, '')")
    op.execute("UPDATE settings SET ai_override_policy = COALESCE(ai_override_policy, 'promote_only')")
    op.execute("UPDATE settings SET is_active = false")
    op.execute(
        """
        UPDATE settings
        SET is_active = true
        WHERE id = (
            SELECT id FROM settings ORDER BY COALESCE(updated_ts, 0) DESC, id DESC LIMIT 1
        )
        """
    )

    op.execute("UPDATE positions SET entry_fee_est = COALESCE(entry_fee_est, 0.0)")
    op.execute("UPDATE positions SET exit_fee_est = COALESCE(exit_fee_est, 0.0)")
    op.execute("UPDATE positions SET total_fees_est = COALESCE(total_fees_est, 0.0)")



def downgrade() -> None:
    with op.batch_alter_table('positions') as batch_op:
        if _has_column('positions', 'total_fees_est'):
            batch_op.drop_column('total_fees_est')
        if _has_column('positions', 'exit_fee_est'):
            batch_op.drop_column('exit_fee_est')
        if _has_column('positions', 'entry_fee_est'):
            batch_op.drop_column('entry_fee_est')
        if _has_column('positions', 'closed_order_id'):
            batch_op.drop_column('closed_order_id')
        if _has_column('positions', 'opened_order_id'):
            batch_op.drop_column('opened_order_id')
        if _has_column('positions', 'opened_signal_id'):
            batch_op.drop_column('opened_signal_id')

    with op.batch_alter_table('settings') as batch_op:
        if _has_column('settings', 'is_active'):
            batch_op.drop_column('is_active')
        if _has_column('settings', 'ai_override_policy'):
            batch_op.drop_column('ai_override_policy')
        if _has_column('settings', 'trading_schedule_exchange'):
            batch_op.drop_column('trading_schedule_exchange')
        if _has_column('settings', 'use_broker_trading_schedule'):
            batch_op.drop_column('use_broker_trading_schedule')
        if _has_column('settings', 'signal_reentry_cooldown_sec'):
            batch_op.drop_column('signal_reentry_cooldown_sec')
        if _has_column('settings', 'max_total_exposure_pct_balance'):
            batch_op.drop_column('max_total_exposure_pct_balance')
        if _has_column('settings', 'max_position_notional_pct_balance'):
            batch_op.drop_column('max_position_notional_pct_balance')
