"""Persistent candle cache for faster history bootstrap.

Revision ID: 20260321_02
Revises: 20260321_01b
Create Date: 2026-03-21 03:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260321_02'
down_revision = '20260321_01b'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    if _has_table('candle_cache'):
        return
    op.create_table(
        'candle_cache',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('instrument_id', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('open', sa.Numeric(18, 9), nullable=False),
        sa.Column('high', sa.Numeric(18, 9), nullable=False),
        sa.Column('low', sa.Numeric(18, 9), nullable=False),
        sa.Column('close', sa.Numeric(18, 9), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=True, server_default='0'),
        sa.Column('source', sa.String(), nullable=True, server_default='worker'),
        sa.Column('created_ts', sa.BigInteger(), nullable=True),
        sa.Column('updated_ts', sa.BigInteger(), nullable=True),
    )
    op.create_index('idx_candle_cache_lookup', 'candle_cache', ['instrument_id', 'timeframe', 'ts'], unique=True)


def downgrade() -> None:
    if _has_table('candle_cache'):
        op.drop_index('idx_candle_cache_lookup', table_name='candle_cache')
        op.drop_table('candle_cache')
