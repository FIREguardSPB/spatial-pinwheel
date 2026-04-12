"""add trainable ml runtime controls and registry

Revision ID: 20260401_05
Revises: 20260401_04
Create Date: 2026-04-01 22:05:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_05'
down_revision = '20260401_04'
branch_labels = None
depends_on = None


SETTINGS_COLUMNS = [
    ('ml_enabled', sa.Boolean(), sa.true()),
    ('ml_retrain_enabled', sa.Boolean(), sa.true()),
    ('ml_lookback_days', sa.Integer(), '120'),
    ('ml_min_training_samples', sa.Integer(), '80'),
    ('ml_retrain_interval_hours', sa.Integer(), '24'),
    ('ml_retrain_hour_msk', sa.Integer(), '4'),
    ('ml_take_probability_threshold', sa.Numeric(6, 3), '0.55'),
    ('ml_fill_probability_threshold', sa.Numeric(6, 3), '0.45'),
    ('ml_risk_boost_threshold', sa.Numeric(6, 3), '0.65'),
    ('ml_risk_cut_threshold', sa.Numeric(6, 3), '0.45'),
    ('ml_pass_risk_multiplier', sa.Numeric(6, 3), '1.15'),
    ('ml_fail_risk_multiplier', sa.Numeric(6, 3), '0.75'),
    ('ml_threshold_bonus', sa.Integer(), '4'),
    ('ml_threshold_penalty', sa.Integer(), '8'),
    ('ml_execution_priority_boost', sa.Numeric(6, 3), '1.15'),
    ('ml_execution_priority_penalty', sa.Numeric(6, 3), '0.80'),
    ('ml_allocator_boost', sa.Numeric(6, 3), '1.10'),
    ('ml_allocator_penalty', sa.Numeric(6, 3), '0.85'),
    ('ml_allow_take_veto', sa.Boolean(), sa.true()),
]


def upgrade() -> None:
    for name, col_type, default in SETTINGS_COLUMNS:
        op.add_column('settings', sa.Column(name, col_type, nullable=True, server_default=sa.text(default)))

    op.create_table(
        'ml_training_runs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('target', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='completed'),
        sa.Column('source', sa.String(), nullable=False, server_default='manual'),
        sa.Column('lookback_days', sa.Integer(), nullable=True, server_default='120'),
        sa.Column('train_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('validation_rows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('artifact_path', sa.Text(), nullable=True),
        sa.Column('model_type', sa.String(), nullable=False, server_default='logistic_regression'),
        sa.Column('feature_columns', sa.JSON(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('idx_ml_training_runs_target_ts', 'ml_training_runs', ['target', 'ts'])
    op.create_index('idx_ml_training_runs_active', 'ml_training_runs', ['target', 'is_active', 'ts'])


def downgrade() -> None:
    op.drop_index('idx_ml_training_runs_active', table_name='ml_training_runs')
    op.drop_index('idx_ml_training_runs_target_ts', table_name='ml_training_runs')
    op.drop_table('ml_training_runs')
    for name, *_ in reversed(SETTINGS_COLUMNS):
        op.drop_column('settings', name)
