"""schema completion for watchlist, snapshots, ai decisions and settings columns

Revision ID: 20260308_03
Revises: 20260308_02
Create Date: 2026-03-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260308_03"
down_revision = "20260308_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    # Missing settings columns required by current backend/frontend contract.
    settings_columns = [
        sa.Column("rr_min", sa.Numeric(5, 2), nullable=True, server_default="1.5"),
        sa.Column("atr_stop_hard_min", sa.Numeric(5, 2), nullable=True, server_default="0.3"),
        sa.Column("atr_stop_hard_max", sa.Numeric(5, 2), nullable=True, server_default="5.0"),
        sa.Column("atr_stop_soft_min", sa.Numeric(5, 2), nullable=True, server_default="0.6"),
        sa.Column("atr_stop_soft_max", sa.Numeric(5, 2), nullable=True, server_default="2.5"),
        sa.Column("w_regime", sa.Integer(), nullable=True, server_default="20"),
        sa.Column("w_volatility", sa.Integer(), nullable=True, server_default="15"),
        sa.Column("w_momentum", sa.Integer(), nullable=True, server_default="15"),
        sa.Column("w_levels", sa.Integer(), nullable=True, server_default="20"),
        sa.Column("w_costs", sa.Integer(), nullable=True, server_default="15"),
        sa.Column("w_liquidity", sa.Integer(), nullable=True, server_default="5"),
        sa.Column("w_volume", sa.Integer(), nullable=True, server_default="10"),
        sa.Column("no_trade_opening_minutes", sa.Integer(), nullable=True, server_default="10"),
        sa.Column("trading_session", sa.String(), nullable=True, server_default="main"),
        sa.Column("higher_timeframe", sa.String(), nullable=True, server_default="15m"),
        sa.Column("strategy_name", sa.String(), nullable=True, server_default="breakout"),
        sa.Column("correlation_threshold", sa.Numeric(4, 2), nullable=True, server_default="0.8"),
        sa.Column("max_correlated_positions", sa.Integer(), nullable=True, server_default="2"),
        sa.Column("telegram_bot_token", sa.String(), nullable=True, server_default=""),
        sa.Column("telegram_chat_id", sa.String(), nullable=True, server_default=""),
        sa.Column("notification_events", sa.String(), nullable=True, server_default="signal_created,trade_executed,sl_hit,tp_hit"),
        sa.Column("no_notification_hours", sa.String(), nullable=True, server_default=""),
        sa.Column("account_balance", sa.Numeric(18, 4), nullable=True, server_default="100000.0"),
        sa.Column("ai_mode", sa.String(), nullable=True, server_default="off"),
        sa.Column("ai_min_confidence", sa.Integer(), nullable=True, server_default="70"),
    ]
    for column in settings_columns:
        _add_column_if_missing("settings", column)

    # Backfill NULLs in case columns were added manually without defaults.
    backfills = [
        ("rr_min", "1.5"),
        ("atr_stop_hard_min", "0.3"),
        ("atr_stop_hard_max", "5.0"),
        ("atr_stop_soft_min", "0.6"),
        ("atr_stop_soft_max", "2.5"),
        ("w_regime", "20"),
        ("w_volatility", "15"),
        ("w_momentum", "15"),
        ("w_levels", "20"),
        ("w_costs", "15"),
        ("w_liquidity", "5"),
        ("w_volume", "10"),
        ("no_trade_opening_minutes", "10"),
        ("trading_session", "'main'"),
        ("higher_timeframe", "'15m'"),
        ("strategy_name", "'breakout'"),
        ("correlation_threshold", "0.8"),
        ("max_correlated_positions", "2"),
        ("telegram_bot_token", "''"),
        ("telegram_chat_id", "''"),
        ("notification_events", "'signal_created,trade_executed,sl_hit,tp_hit'"),
        ("no_notification_hours", "''"),
        ("account_balance", "100000.0"),
        ("ai_mode", "'off'"),
        ("ai_min_confidence", "70"),
    ]
    for column_name, sql_value in backfills:
        if _column_exists("settings", column_name):
            op.execute(f"UPDATE settings SET {column_name} = {sql_value} WHERE {column_name} IS NULL")

    # Missing tables used by worker/UI.
    if not _table_exists("account_snapshots"):
        op.create_table(
            "account_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.BigInteger(), nullable=False),
            sa.Column("balance", sa.Numeric(18, 4), nullable=True, server_default="0.0"),
            sa.Column("equity", sa.Numeric(18, 4), nullable=True, server_default="0.0"),
            sa.Column("open_positions", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("day_pnl", sa.Numeric(18, 4), nullable=True, server_default="0.0"),
        )
    if not _index_exists("account_snapshots", "idx_snapshots_ts"):
        op.create_index("idx_snapshots_ts", "account_snapshots", ["ts"], unique=False)

    if not _table_exists("ai_decisions"):
        op.create_table(
            "ai_decisions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("ts", sa.BigInteger(), nullable=False),
            sa.Column("signal_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("prompt_hash", sa.String(length=64), nullable=True),
            sa.Column("response_raw", sa.Text(), nullable=True),
            sa.Column("ai_decision", sa.String(), nullable=False),
            sa.Column("ai_confidence", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("ai_reasoning", sa.Text(), nullable=True),
            sa.Column("ai_key_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
            sa.Column("final_decision", sa.String(), nullable=False),
            sa.Column("de_score", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("actual_outcome", sa.String(), nullable=True, server_default="pending"),
            sa.Column("latency_ms", sa.Integer(), nullable=True, server_default="0"),
        )
    if not _index_exists("ai_decisions", "idx_ai_decisions_ts"):
        op.create_index("idx_ai_decisions_ts", "ai_decisions", ["ts"], unique=False)

    if not _table_exists("watchlist"):
        op.create_table(
            "watchlist",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("ticker", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("exchange", sa.String(), nullable=True, server_default="TQBR"),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("added_ts", sa.BigInteger(), nullable=False),
            sa.UniqueConstraint("instrument_id"),
        )
    if not _index_exists("watchlist", "idx_watchlist_instrument_id"):
        op.create_index("idx_watchlist_instrument_id", "watchlist", ["instrument_id"], unique=False)


def downgrade() -> None:
    # Keep downgrade conservative: remove only structures introduced in this revision if present.
    if _index_exists("watchlist", "idx_watchlist_instrument_id"):
        op.drop_index("idx_watchlist_instrument_id", table_name="watchlist")
    if _table_exists("watchlist"):
        op.drop_table("watchlist")

    if _index_exists("ai_decisions", "idx_ai_decisions_ts"):
        op.drop_index("idx_ai_decisions_ts", table_name="ai_decisions")
    if _table_exists("ai_decisions"):
        op.drop_table("ai_decisions")

    if _index_exists("account_snapshots", "idx_snapshots_ts"):
        op.drop_index("idx_snapshots_ts", table_name="account_snapshots")
    if _table_exists("account_snapshots"):
        op.drop_table("account_snapshots")

    for column_name in [
        "ai_min_confidence",
        "ai_mode",
        "account_balance",
        "no_notification_hours",
        "notification_events",
        "telegram_chat_id",
        "telegram_bot_token",
        "max_correlated_positions",
        "correlation_threshold",
        "strategy_name",
        "higher_timeframe",
        "trading_session",
        "no_trade_opening_minutes",
        "w_volume",
        "w_liquidity",
        "w_costs",
        "w_levels",
        "w_momentum",
        "w_volatility",
        "w_regime",
        "atr_stop_soft_max",
        "atr_stop_soft_min",
        "atr_stop_hard_max",
        "atr_stop_hard_min",
        "rr_min",
    ]:
        if _column_exists("settings", column_name):
            op.drop_column("settings", column_name)
