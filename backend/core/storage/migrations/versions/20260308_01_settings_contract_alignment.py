"""settings contract alignment

Revision ID: 20260308_01
Revises: 818dacab6670
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = '20260308_01'
down_revision = '0660ab790b8a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('bot_enabled', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column('settings', sa.Column('ai_primary_provider', sa.String(), nullable=True, server_default='claude'))
    op.add_column('settings', sa.Column('ai_fallback_providers', sa.String(), nullable=True, server_default='deepseek,ollama,skip'))
    op.add_column('settings', sa.Column('ollama_url', sa.String(), nullable=True, server_default='http://localhost:11434'))

    op.execute("UPDATE settings SET bot_enabled = false WHERE bot_enabled IS NULL")
    op.execute("UPDATE settings SET ai_primary_provider = 'claude' WHERE ai_primary_provider IS NULL")
    op.execute("UPDATE settings SET ai_fallback_providers = 'deepseek,ollama,skip' WHERE ai_fallback_providers IS NULL")
    op.execute("UPDATE settings SET ollama_url = 'http://localhost:11434' WHERE ollama_url IS NULL")
    op.execute("UPDATE settings SET trade_mode = 'auto_paper' WHERE trade_mode = 'paper'")
    op.execute("UPDATE settings SET trade_mode = 'review' WHERE trade_mode IN ('live', 'auto_live') OR trade_mode IS NULL")


def downgrade() -> None:
    op.drop_column('settings', 'ollama_url')
    op.drop_column('settings', 'ai_fallback_providers')
    op.drop_column('settings', 'ai_primary_provider')
    op.drop_column('settings', 'bot_enabled')
