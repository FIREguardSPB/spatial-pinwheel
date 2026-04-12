"""symbol profiles, regime snapshots, and training runs

Revision ID: 20260330_01
Revises: 20260321_03
Create Date: 2026-03-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260330_01'
down_revision = '20260321_03'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    if not _has_table('symbol_profiles'):
        op.create_table(
            'symbol_profiles',
            sa.Column('instrument_id', sa.String(), primary_key=True),
            sa.Column('enabled', sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column('preferred_strategies', sa.String(), nullable=True, server_default='breakout,mean_reversion,vwap_bounce'),
            sa.Column('decision_threshold_offset', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('hold_bars_base', sa.Integer(), nullable=True, server_default='12'),
            sa.Column('hold_bars_min', sa.Integer(), nullable=True, server_default='4'),
            sa.Column('hold_bars_max', sa.Integer(), nullable=True, server_default='30'),
            sa.Column('reentry_cooldown_sec', sa.Integer(), nullable=True, server_default='300'),
            sa.Column('risk_multiplier', sa.Numeric(8, 4), nullable=True, server_default='1.0'),
            sa.Column('aggressiveness', sa.Numeric(8, 4), nullable=True, server_default='1.0'),
            sa.Column('autotune', sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column('session_bias', sa.String(), nullable=True, server_default='all'),
            sa.Column('regime_bias', sa.String(), nullable=True, server_default=''),
            sa.Column('preferred_side', sa.String(), nullable=True, server_default='both'),
            sa.Column('best_hours_json', sa.JSON(), nullable=True, server_default='[]'),
            sa.Column('blocked_hours_json', sa.JSON(), nullable=True, server_default='[]'),
            sa.Column('news_sensitivity', sa.Numeric(8, 4), nullable=True, server_default='1.0'),
            sa.Column('confidence_bias', sa.Numeric(8, 4), nullable=True, server_default='1.0'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('source', sa.String(), nullable=True, server_default='runtime'),
            sa.Column('profile_version', sa.Integer(), nullable=True, server_default='1'),
            sa.Column('last_regime', sa.String(), nullable=True),
            sa.Column('last_strategy', sa.String(), nullable=True),
            sa.Column('last_threshold', sa.Integer(), nullable=True),
            sa.Column('last_hold_bars', sa.Integer(), nullable=True),
            sa.Column('last_win_rate', sa.Numeric(8, 4), nullable=True),
            sa.Column('sample_size', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('last_tuned_ts', sa.BigInteger(), nullable=True, server_default='0'),
            sa.Column('created_ts', sa.BigInteger(), nullable=True),
            sa.Column('updated_ts', sa.BigInteger(), nullable=True),
        )

    if not _has_table('symbol_regime_snapshots'):
        op.create_table(
            'symbol_regime_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('instrument_id', sa.String(), nullable=False),
            sa.Column('ts', sa.BigInteger(), nullable=False),
            sa.Column('timeframe', sa.String(), nullable=False, server_default='1m'),
            sa.Column('regime', sa.String(), nullable=False, server_default='balanced'),
            sa.Column('volatility_pct', sa.Numeric(12, 6), nullable=True),
            sa.Column('trend_strength', sa.Numeric(12, 6), nullable=True),
            sa.Column('chop_ratio', sa.Numeric(12, 6), nullable=True),
            sa.Column('body_ratio', sa.Numeric(12, 6), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True, server_default='{}'),
        )
        op.create_index('idx_symbol_regime_snapshots_lookup', 'symbol_regime_snapshots', ['instrument_id', 'timeframe', 'ts'])

    if not _has_table('symbol_training_runs'):
        op.create_table(
            'symbol_training_runs',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('ts', sa.BigInteger(), nullable=False),
            sa.Column('instrument_id', sa.String(), nullable=False),
            sa.Column('mode', sa.String(), nullable=False, server_default='offline'),
            sa.Column('status', sa.String(), nullable=False, server_default='completed'),
            sa.Column('source', sa.String(), nullable=False, server_default='candle_cache'),
            sa.Column('candles_used', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('trades_used', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('recommendations', sa.JSON(), nullable=True, server_default='{}'),
            sa.Column('diagnostics', sa.JSON(), nullable=True, server_default='{}'),
            sa.Column('notes', sa.Text(), nullable=True),
        )
        op.create_index('idx_symbol_training_runs_lookup', 'symbol_training_runs', ['instrument_id', 'ts'])


def downgrade() -> None:
    if _has_table('symbol_training_runs'):
        op.drop_index('idx_symbol_training_runs_lookup', table_name='symbol_training_runs')
        op.drop_table('symbol_training_runs')
    if _has_table('symbol_regime_snapshots'):
        op.drop_index('idx_symbol_regime_snapshots_lookup', table_name='symbol_regime_snapshots')
        op.drop_table('symbol_regime_snapshots')
    if _has_table('symbol_profiles'):
        op.drop_table('symbol_profiles')
