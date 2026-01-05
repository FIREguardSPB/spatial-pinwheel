"""init

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-01-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Settings
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('risk_profile', sa.String(), nullable=True),
        sa.Column('risk_per_trade_pct', sa.Float(), nullable=True),
        sa.Column('daily_loss_limit_pct', sa.Float(), nullable=True),
        sa.Column('max_concurrent_positions', sa.Integer(), nullable=True),
        sa.Column('max_trades_per_day', sa.Integer(), nullable=True),
        sa.Column('rr_target', sa.Float(), nullable=True),
        sa.Column('time_stop_bars', sa.Integer(), nullable=True),
        sa.Column('close_before_session_end_minutes', sa.Integer(), nullable=True),
        sa.Column('cooldown_losses', sa.Integer(), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=True),
        sa.Column('updated_ts', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Signals
    op.create_table('signals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('instrument_id', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('entry', sa.Float(), nullable=False),
        sa.Column('sl', sa.Float(), nullable=False),
        sa.Column('tp', sa.Float(), nullable=False),
        sa.Column('size', sa.Float(), nullable=False),
        sa.Column('r', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_ts', sa.BigInteger(), nullable=True),
        sa.Column('updated_ts', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_signals_lookup', 'signals', ['instrument_id', 'status', 'ts'], unique=False)

    # Orders
    op.create_table('orders',
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('instrument_id', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('filled_qty', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('related_signal_id', sa.String(), nullable=True),
        sa.Column('created_ts', sa.BigInteger(), nullable=True),
        sa.Column('updated_ts', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('order_id'),
        sa.UniqueConstraint('related_signal_id')
    )

    # Trades
    op.create_table('trades',
        sa.Column('trade_id', sa.String(), nullable=False),
        sa.Column('instrument_id', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('trade_id')
    )
    op.create_index('idx_trades_instrument_ts', 'trades', ['instrument_id', 'ts'], unique=False)

    # Positions
    op.create_table('positions',
        sa.Column('instrument_id', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=True),
        sa.Column('avg_price', sa.Float(), nullable=True),
        sa.Column('sl', sa.Float(), nullable=True),
        sa.Column('tp', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=True),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('opened_ts', sa.BigInteger(), nullable=False),
        sa.Column('updated_ts', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('instrument_id')
    )

    # Decision Log
    op.create_table('decision_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_decision_log_ts', 'decision_log', ['ts'], unique=False)


def downgrade() -> None:
    op.drop_table('decision_log')
    op.drop_table('positions')
    op.drop_table('trades')
    op.drop_table('orders')
    op.drop_table('signals')
    op.drop_table('settings')
