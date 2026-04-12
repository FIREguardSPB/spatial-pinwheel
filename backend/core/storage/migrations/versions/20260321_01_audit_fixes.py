"""Audit fixes: trade linkage, opened qty, and settings observability.

Revision ID: 20260321_01
Revises: 20260318_01
Create Date: 2026-03-21 01:10:00
"""
from alembic import op
import sqlalchemy as sa

revision = '20260321_01'
down_revision = '20260318_01'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    with op.batch_alter_table('trades') as batch_op:
        if not _has_column('trades', 'signal_id'):
            batch_op.add_column(sa.Column('signal_id', sa.String(), nullable=True))

    with op.batch_alter_table('positions') as batch_op:
        if not _has_column('positions', 'opened_qty'):
            batch_op.add_column(sa.Column('opened_qty', sa.Numeric(18, 9), nullable=True, server_default='0.0'))

    op.execute("UPDATE positions SET opened_qty = COALESCE(opened_qty, qty, 0.0)")
    op.execute(
        """
        UPDATE positions p
        SET opened_qty = COALESCE(o.filled_qty, o.qty, p.opened_qty, 0.0)
        FROM orders o
        WHERE p.opened_order_id IS NOT NULL
          AND o.order_id = p.opened_order_id
        """
    )
    op.execute(
        """
        UPDATE trades t
        SET signal_id = COALESCE(t.signal_id, o.related_signal_id)
        FROM orders o
        WHERE t.order_id = o.order_id
          AND o.related_signal_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table('positions') as batch_op:
        if _has_column('positions', 'opened_qty'):
            batch_op.drop_column('opened_qty')

    with op.batch_alter_table('trades') as batch_op:
        if _has_column('trades', 'signal_id'):
            batch_op.drop_column('signal_id')
