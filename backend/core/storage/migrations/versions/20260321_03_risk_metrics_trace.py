"""risk tuning, trade strategy/trace, and worker settings

Revision ID: 20260321_03
Revises: 20260321_02
Create Date: 2026-03-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260321_03'
down_revision = '20260321_02'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column('settings', 'strong_signal_score_threshold'):
        op.add_column('settings', sa.Column('strong_signal_score_threshold', sa.Integer(), nullable=True, server_default='80'))
    if not _has_column('settings', 'strong_signal_position_bonus'):
        op.add_column('settings', sa.Column('strong_signal_position_bonus', sa.Integer(), nullable=True, server_default='2'))
    if not _has_column('settings', 'partial_close_threshold'):
        op.add_column('settings', sa.Column('partial_close_threshold', sa.Integer(), nullable=True, server_default='80'))
    if not _has_column('settings', 'partial_close_ratio'):
        op.add_column('settings', sa.Column('partial_close_ratio', sa.Numeric(5, 2), nullable=True, server_default='0.50'))
    if not _has_column('settings', 'min_position_age_for_partial_close'):
        op.add_column('settings', sa.Column('min_position_age_for_partial_close', sa.Integer(), nullable=True, server_default='180'))
    if not _has_column('settings', 'worker_bootstrap_limit'):
        op.add_column('settings', sa.Column('worker_bootstrap_limit', sa.Integer(), nullable=True, server_default='10'))

    if not _has_column('orders', 'strategy'):
        op.add_column('orders', sa.Column('strategy', sa.String(), nullable=True))
    if not _has_column('orders', 'trace_id'):
        op.add_column('orders', sa.Column('trace_id', sa.String(), nullable=True))

    if not _has_column('trades', 'strategy'):
        op.add_column('trades', sa.Column('strategy', sa.String(), nullable=True))
    if not _has_column('trades', 'trace_id'):
        op.add_column('trades', sa.Column('trace_id', sa.String(), nullable=True))
        op.create_index('idx_trades_trace_id', 'trades', ['trace_id'], unique=False)

    if not _has_column('positions', 'strategy'):
        op.add_column('positions', sa.Column('strategy', sa.String(), nullable=True))
    if not _has_column('positions', 'trace_id'):
        op.add_column('positions', sa.Column('trace_id', sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if 'idx_trades_trace_id' in {idx['name'] for idx in insp.get_indexes('trades')}:
        op.drop_index('idx_trades_trace_id', table_name='trades')
    for table, cols in (
        ('positions', ['trace_id', 'strategy']),
        ('trades', ['trace_id', 'strategy']),
        ('orders', ['trace_id', 'strategy']),
        ('settings', ['worker_bootstrap_limit', 'min_position_age_for_partial_close', 'partial_close_ratio', 'partial_close_threshold', 'strong_signal_position_bonus', 'strong_signal_score_threshold']),
    ):
        existing = {c['name'] for c in insp.get_columns(table)}
        for col in cols:
            if col in existing:
                op.drop_column(table, col)
