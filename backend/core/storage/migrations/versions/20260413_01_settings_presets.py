"""add settings presets table and seed system presets

Revision ID: 20260413_01
Revises: 20260401_05
Create Date: 2026-04-13 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260413_01'
down_revision = '20260401_05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'settings_presets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('settings_json', JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('idx_settings_presets_name', 'settings_presets', ['name'], unique=False)
    op.create_index('idx_settings_presets_system', 'settings_presets', ['is_system', 'updated_at'], unique=False)

    ts_ms = 1776039600000
    preset_table = sa.table(
        'settings_presets',
        sa.column('id', sa.String()),
        sa.column('name', sa.String()),
        sa.column('description', sa.Text()),
        sa.column('settings_json', JSONB(astext_type=sa.Text())),
        sa.column('created_at', sa.BigInteger()),
        sa.column('updated_at', sa.BigInteger()),
        sa.column('is_system', sa.Boolean()),
    )
    op.bulk_insert(preset_table, [
        {'id': 'preset_system_sniper', 'name': 'Sniper', 'description': 'Жёсткие фильтры, высокий RR и низкая частота сделок.', 'settings_json': {'risk_profile': 'conservative', 'risk_per_trade_pct': 0.15, 'daily_loss_limit_pct': 1.0, 'max_concurrent_positions': 2, 'max_trades_per_day': 20, 'decision_threshold': 78, 'rr_min': 1.8, 'rr_target': 1.9, 'signal_reentry_cooldown_sec': 600, 'time_stop_bars': 8, 'ai_mode': 'advisory', 'ml_take_probability_threshold': 0.62, 'ml_fill_probability_threshold': 0.52, 'ml_allow_take_veto': True, 'watchlist': []}, 'created_at': ts_ms, 'updated_at': ts_ms, 'is_system': True},
        {'id': 'preset_system_machine_gunner', 'name': 'Machine-gunner', 'description': 'Более мягкие фильтры, больше сделок и агрессивный контур.', 'settings_json': {'risk_profile': 'aggressive', 'risk_per_trade_pct': 0.4, 'daily_loss_limit_pct': 2.5, 'max_concurrent_positions': 6, 'max_trades_per_day': 220, 'decision_threshold': 62, 'rr_min': 1.25, 'rr_target': 1.3, 'signal_reentry_cooldown_sec': 120, 'time_stop_bars': 16, 'trade_mode': 'auto_paper', 'ai_mode': 'override', 'ml_take_probability_threshold': 0.5, 'ml_fill_probability_threshold': 0.38, 'ml_allow_take_veto': False, 'watchlist': []}, 'created_at': ts_ms, 'updated_at': ts_ms, 'is_system': True},
        {'id': 'preset_system_balanced', 'name': 'Balanced', 'description': 'Сбалансированный baseline для production-like paper режима.', 'settings_json': {'risk_profile': 'balanced', 'trade_mode': 'auto_paper', 'ai_mode': 'advisory', 'decision_threshold': 70, 'rr_min': 1.5, 'rr_target': 1.4, 'ml_enabled': True, 'ml_take_probability_threshold': 0.55, 'ml_fill_probability_threshold': 0.45, 'max_trades_per_day': 120, 'watchlist': []}, 'created_at': ts_ms, 'updated_at': ts_ms, 'is_system': True},
    ])


def downgrade() -> None:
    op.drop_index('idx_settings_presets_system', table_name='settings_presets')
    op.drop_index('idx_settings_presets_name', table_name='settings_presets')
    op.drop_table('settings_presets')
