"""final trader engine settings and event regimes

Revision ID: 20260330_02
Revises: 20260330_01
Create Date: 2026-03-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260330_02'
down_revision = '20260330_01'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c['name'] == column for c in insp.get_columns(table))


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    settings_columns = [
        ('capital_allocator_enabled', sa.Boolean(), sa.true()),
        ('capital_allocator_min_score_gap', sa.Integer(), '12'),
        ('capital_allocator_min_free_cash_pct', sa.Numeric(5, 2), '8.0'),
        ('capital_allocator_max_reallocation_pct', sa.Numeric(5, 2), '0.65'),
        ('event_regime_enabled', sa.Boolean(), sa.true()),
        ('event_regime_block_severity', sa.Numeric(5, 2), '0.82'),
        ('adaptive_exit_enabled', sa.Boolean(), sa.true()),
        ('adaptive_exit_extend_bars_limit', sa.Integer(), '8'),
        ('adaptive_exit_tighten_sl_pct', sa.Numeric(6, 3), '0.35'),
    ]
    for name, coltype, default in settings_columns:
        if _has_column('settings', name):
            continue
        server_default = default if isinstance(default, str) else default
        op.add_column('settings', sa.Column(name, coltype, nullable=True, server_default=server_default))

    if not _has_table('symbol_event_regimes'):
        op.create_table(
            'symbol_event_regimes',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('instrument_id', sa.String(), nullable=False),
            sa.Column('ts', sa.BigInteger(), nullable=False),
            sa.Column('regime', sa.String(), nullable=False, server_default='calm'),
            sa.Column('severity', sa.Numeric(8, 4), nullable=True, server_default='0.0'),
            sa.Column('direction', sa.String(), nullable=True),
            sa.Column('score_bias', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('hold_bias', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('risk_bias', sa.Numeric(8, 4), nullable=True, server_default='1.0'),
            sa.Column('action', sa.String(), nullable=True, server_default='observe'),
            sa.Column('payload', sa.JSON(), nullable=True, server_default='{}'),
        )
        op.create_index('idx_symbol_event_regimes_lookup', 'symbol_event_regimes', ['instrument_id', 'ts'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table('symbol_event_regimes'):
        if 'idx_symbol_event_regimes_lookup' in {idx['name'] for idx in insp.get_indexes('symbol_event_regimes')}:
            op.drop_index('idx_symbol_event_regimes_lookup', table_name='symbol_event_regimes')
        op.drop_table('symbol_event_regimes')
    existing = {c['name'] for c in insp.get_columns('settings')}
    for col in [
        'adaptive_exit_tighten_sl_pct',
        'adaptive_exit_extend_bars_limit',
        'adaptive_exit_enabled',
        'event_regime_block_severity',
        'event_regime_enabled',
        'capital_allocator_max_reallocation_pct',
        'capital_allocator_min_free_cash_pct',
        'capital_allocator_min_score_gap',
        'capital_allocator_enabled',
    ]:
        if col in existing:
            op.drop_column('settings', col)
