"""portfolio optimizer controls and excursion tracking

Revision ID: 20260401_02
Revises: 20260401_01
Create Date: 2026-04-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260401_02'
down_revision = '20260401_01'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    settings_columns = [
        ('portfolio_optimizer_enabled', sa.Boolean(), 'true'),
        ('portfolio_optimizer_lookback_bars', sa.Integer(), '180'),
        ('portfolio_optimizer_min_history_bars', sa.Integer(), '60'),
        ('portfolio_optimizer_max_pair_corr', sa.Numeric(5, 2), '0.85'),
        ('portfolio_optimizer_regime_risk_off_multiplier', sa.Numeric(6, 3), '0.70'),
        ('portfolio_optimizer_target_weight_buffer_pct', sa.Numeric(5, 2), '2.50'),
    ]
    for name, col_type, default in settings_columns:
        if not _has_column('settings', name):
            op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=default))

    position_columns = [
        ('mfe_total_pnl', sa.Numeric(18, 9), None),
        ('mae_total_pnl', sa.Numeric(18, 9), None),
        ('mfe_pct', sa.Numeric(10, 4), None),
        ('mae_pct', sa.Numeric(10, 4), None),
        ('best_price_seen', sa.Numeric(18, 9), None),
        ('worst_price_seen', sa.Numeric(18, 9), None),
        ('excursion_samples', sa.Integer(), '0'),
        ('excursion_updated_ts', sa.BigInteger(), None),
    ]
    for name, col_type, default in position_columns:
        if not _has_column('positions', name):
            kwargs = {'nullable': True}
            if default is not None:
                kwargs['server_default'] = default
            op.add_column('positions', sa.Column(name, col_type, **kwargs))

    if not _has_table('position_excursions'):
        op.create_table(
            'position_excursions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('trace_id', sa.String(), nullable=True),
            sa.Column('signal_id', sa.String(), nullable=True),
            sa.Column('instrument_id', sa.String(), nullable=False),
            sa.Column('ts', sa.BigInteger(), nullable=False),
            sa.Column('phase', sa.String(), nullable=False, server_default='tick'),
            sa.Column('bar_index', sa.Integer(), nullable=True),
            sa.Column('mark_price', sa.Numeric(18, 9), nullable=False),
            sa.Column('unrealized_pnl', sa.Numeric(18, 9), nullable=True),
            sa.Column('realized_pnl', sa.Numeric(18, 9), nullable=True),
            sa.Column('lifecycle_pnl', sa.Numeric(18, 9), nullable=True),
            sa.Column('mfe_total_pnl', sa.Numeric(18, 9), nullable=True),
            sa.Column('mae_total_pnl', sa.Numeric(18, 9), nullable=True),
            sa.Column('mfe_pct', sa.Numeric(10, 4), nullable=True),
            sa.Column('mae_pct', sa.Numeric(10, 4), nullable=True),
            sa.Column('is_new_mfe', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('is_new_mae', sa.Boolean(), nullable=True, server_default='false'),
        )
        op.create_index('idx_position_excursions_trace_ts', 'position_excursions', ['trace_id', 'ts'])
        op.create_index('idx_position_excursions_instrument_ts', 'position_excursions', ['instrument_id', 'ts'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    settings_existing = {c['name'] for c in insp.get_columns('settings')}
    positions_existing = {c['name'] for c in insp.get_columns('positions')}
    if _has_table('position_excursions'):
        op.drop_index('idx_position_excursions_instrument_ts', table_name='position_excursions')
        op.drop_index('idx_position_excursions_trace_ts', table_name='position_excursions')
        op.drop_table('position_excursions')
    for name in ['excursion_updated_ts', 'excursion_samples', 'worst_price_seen', 'best_price_seen', 'mae_pct', 'mfe_pct', 'mae_total_pnl', 'mfe_total_pnl']:
        if name in positions_existing:
            op.drop_column('positions', name)
    for name in ['portfolio_optimizer_target_weight_buffer_pct', 'portfolio_optimizer_regime_risk_off_multiplier', 'portfolio_optimizer_max_pair_corr', 'portfolio_optimizer_min_history_bars', 'portfolio_optimizer_lookback_bars', 'portfolio_optimizer_enabled']:
        if name in settings_existing:
            op.drop_column('settings', name)
