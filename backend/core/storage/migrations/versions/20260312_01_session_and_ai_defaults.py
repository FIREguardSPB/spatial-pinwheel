"""Session windows and AI confidence defaults.

Revision ID: 20260312_01
Revises: 20260309_01
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '20260312_01'
down_revision = '20260309_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('ai_min_confidence', existing_type=sa.Integer(), server_default='60')
        batch_op.alter_column('trading_session', existing_type=sa.String(), server_default='all')
    op.execute("UPDATE settings SET ai_min_confidence = 60 WHERE ai_min_confidence IS NULL OR ai_min_confidence = 70")
    op.execute("UPDATE settings SET trading_session = 'all' WHERE trading_session IS NULL OR trading_session IN ('', 'main+evening')")


def downgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('ai_min_confidence', existing_type=sa.Integer(), server_default='70')
        batch_op.alter_column('trading_session', existing_type=sa.String(), server_default='main')
    op.execute("UPDATE settings SET ai_min_confidence = 70 WHERE ai_min_confidence IS NULL OR ai_min_confidence = 60")
    op.execute("UPDATE settings SET trading_session = 'main' WHERE trading_session IS NULL OR trading_session = 'all'")
