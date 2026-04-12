"""manual orders and AI influence flags

Revision ID: 20260309_01
Revises: 20260308_03
Create Date: 2026-03-09 22:40:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260309_01'
down_revision = '20260308_03'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    if not _has_column('signals', 'ai_influenced'):
        op.add_column('signals', sa.Column('ai_influenced', sa.Boolean(), nullable=True, server_default=sa.false()))
    if not _has_column('signals', 'ai_mode_used'):
        op.add_column('signals', sa.Column('ai_mode_used', sa.String(), nullable=True, server_default='off'))
    if not _has_column('signals', 'ai_decision_id'):
        op.add_column('signals', sa.Column('ai_decision_id', sa.String(), nullable=True))

    if not _has_column('orders', 'ai_influenced'):
        op.add_column('orders', sa.Column('ai_influenced', sa.Boolean(), nullable=True, server_default=sa.false()))
    if not _has_column('orders', 'ai_mode_used'):
        op.add_column('orders', sa.Column('ai_mode_used', sa.String(), nullable=True, server_default='off'))


def downgrade() -> None:
    if _has_column('orders', 'ai_mode_used'):
        op.drop_column('orders', 'ai_mode_used')
    if _has_column('orders', 'ai_influenced'):
        op.drop_column('orders', 'ai_influenced')
    if _has_column('signals', 'ai_decision_id'):
        op.drop_column('signals', 'ai_decision_id')
    if _has_column('signals', 'ai_mode_used'):
        op.drop_column('signals', 'ai_mode_used')
    if _has_column('signals', 'ai_influenced'):
        op.drop_column('signals', 'ai_influenced')
