"""Set ai_min_confidence default to 55 for intraday AI mode.

Revision ID: 20260315_01
Revises: 20260312_01
Create Date: 2026-03-15 21:15:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260315_01'
down_revision = '20260312_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('ai_min_confidence', existing_type=sa.Integer(), server_default='55')
    op.execute("UPDATE settings SET ai_min_confidence = 55 WHERE ai_min_confidence IS NULL OR ai_min_confidence IN (60, 70)")


def downgrade() -> None:
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('ai_min_confidence', existing_type=sa.Integer(), server_default='60')
    op.execute("UPDATE settings SET ai_min_confidence = 60 WHERE ai_min_confidence IS NULL OR ai_min_confidence = 55")
