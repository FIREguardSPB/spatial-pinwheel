"""
P6-11: Account API — баланс, equity curve, дневная статистика.

GET /api/v1/account/summary      — баланс, equity, open PnL, day PnL
GET /api/v1/account/history      — equity curve (из account_snapshots)
GET /api/v1/account/daily-stats  — дневная статистика из trades
GET /api/v1/account/tbank/accounts — T-Bank sandbox/live accounts for UI
POST /api/v1/account/tbank/select-account
POST /api/v1/account/tbank/sandbox/open-account
POST /api/v1/account/tbank/sandbox/pay-in
POST /api/v1/account/tbank/pay-in
"""
from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from apps.api.routers.paper import reset_paper_state
from apps.broker.tbank.adapter import TBankApiError, TBankGrpcAdapter
from core.execution.tbank import TBankExecutionEngine
from core.config import get_token, settings as cfg
from core.storage.repos import settings as settings_repo
from core.storage.models import AccountSnapshot, ApiToken, Position, Settings, Trade
from core.storage.session import get_db
from core.utils.time import now_ms, start_of_day_ms

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


class SelectAccountRequest(BaseModel):
    account_id: str = Field(min_length=1)


class SandboxOpenAccountRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    activate: bool = True


class SandboxPayInRequest(BaseModel):
    account_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=8)
    activate: bool = False


class BrokerPayInRequest(BaseModel):
    from_account_id: str = Field(min_length=1)
    to_account_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=8)


class BrokerTransferRequest(BaseModel):
    from_account_id: str = Field(min_length=1)
    to_account_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=8)


def _today_ms() -> int:
    return start_of_day_ms()


async def _get_tbank_adapter() -> TBankGrpcAdapter:
    token = get_token("TBANK_TOKEN") or cfg.TBANK_TOKEN
    account_id = get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID
    if not token:
        raise HTTPException(status_code=400, detail="TBANK_TOKEN is not configured")
    return TBankGrpcAdapter(token=token, account_id=account_id, sandbox=cfg.TBANK_SANDBOX)


def _encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return ""
    try:
        from core.security.crypto import encrypt_token
        return encrypt_token(plaintext)
    except Exception:
        return plaintext


def _upsert_runtime_secret(db: Session, key_name: str, value: str, *, label: str, description: str, category: str) -> None:
    row = db.query(ApiToken).filter(ApiToken.key_name == key_name).first()
    encrypted_value = _encrypt_value(value)
    if row:
        row.value = encrypted_value
        row.label = row.label or label
        row.description = row.description or description
        row.category = row.category or category
        row.is_active = True
        row.updated_ts = now_ms()
    else:
        row = ApiToken(
            id=f"tok_{key_name.lower()}_{now_ms()}",
            key_name=key_name,
            value=encrypted_value,
            label=label,
            description=description,
            category=category,
            is_active=True,
            created_ts=now_ms(),
            updated_ts=now_ms(),
        )
        db.add(row)
    db.commit()


def _to_decimal_amount(value: float) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid money amount") from exc


def _normalize_account(item: dict[str, Any], *, selected_id: str | None = None) -> dict[str, Any]:
    account_id = item.get("id") or item.get("accountId") or item.get("bankAccountId") or ""
    return {
        "id": account_id,
        "name": item.get("name") or item.get("accountName") or item.get("displayName") or account_id,
        "type": item.get("type") or item.get("accountType") or item.get("bankAccountType") or "unknown",
        "status": item.get("status") or item.get("accountStatus") or "unknown",
        "access_level": item.get("accessLevel") or item.get("accountAccessLevel") or "unknown",
        "currency": item.get("currency") or item.get("baseCurrency") or "RUB",
        "opened_date": item.get("openedDate") or item.get("openDate"),
        "closed_date": item.get("closedDate"),
        "is_selected": bool(account_id and selected_id and account_id == selected_id),
        "raw": item,
    }


@router.get("/summary")
async def account_summary(db: Session = Depends(get_db)):
    return build_account_summary_sync(db)


def build_account_summary_sync(db: Session):
    """
    Account balance + equity overview.
    Paper mode: reads from Settings.account_balance + open positions unrealized PnL.
    Live mode: reads from T-Bank portfolio when available.
    """
    try:
        s = settings_repo.get_settings(db)

        trade_mode = getattr(s, "trade_mode", "review") if s else "review"
        mode = "tbank" if cfg.BROKER_PROVIDER == "tbank" and trade_mode == "auto_live" else cfg.BROKER_PROVIDER
        balance = float(getattr(s, "account_balance", 100_000) or 100_000)

        positions = db.query(Position).filter(Position.qty > 0).all()
        open_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)
        equity = balance + open_pnl

        # UI/account snapshot must stay non-blocking. Live portfolio refresh happens in dedicated broker paths.
        if mode == "tbank":
            logger.info("Account summary uses cached/local values in UI snapshot mode")

        day_pnl = db.query(func.sum(Position.realized_pnl)).filter(
            Position.updated_ts >= _today_ms()
        ).scalar() or 0.0

        total_pnl = db.query(func.sum(Position.realized_pnl)).scalar() or 0.0

        snapshots = db.query(AccountSnapshot).order_by(AccountSnapshot.ts).limit(5000).all()
        max_dd = 0.0
        if snapshots:
            peak = float(snapshots[0].equity or equity)
            for snap in snapshots:
                eq = float(snap.equity or 0)
                peak = max(peak, eq)
                dd = (peak - eq) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)

        return {
            "mode":            mode,
            "balance":         round(balance, 2),
            "equity":          round(equity, 2),
            "open_pnl":        round(open_pnl, 2),
            "day_pnl":         round(float(day_pnl), 2),
            "total_pnl":       round(float(total_pnl), 2),
            "open_positions":  len(positions),
            "max_drawdown_pct": round(max_dd, 2),
            "degraded": False,
            "broker_info": {
                "name":   "T-Bank Invest" if mode == "tbank" else "Paper Trading",
                "type":   "broker" if mode == "tbank" else "virtual",
                "status": "active",
            },
        }
    except Exception as exc:
        logger.error("Account summary failed", exc_info=exc)
        return {
            "mode": cfg.BROKER_PROVIDER,
            "balance": 0.0,
            "equity": 0.0,
            "open_pnl": 0.0,
            "day_pnl": 0.0,
            "total_pnl": 0.0,
            "open_positions": 0,
            "max_drawdown_pct": 0.0,
            "degraded": True,
            "broker_info": {"name": "Unavailable", "type": "unknown", "status": "degraded"},
        }


@router.get("/history")
async def account_history(
    period_days: int = Query(30, ge=1, le=365),
    db: Session      = Depends(get_db),
):
    return build_account_history_sync(db, period_days)


def build_account_history_sync(db: Session, period_days: int = 30):
    try:
        from_ts = int((dt.datetime.now() - dt.timedelta(days=period_days)).timestamp() * 1000)
        snapshots = (
            db.query(AccountSnapshot)
            .filter(AccountSnapshot.ts >= from_ts)
            .order_by(AccountSnapshot.ts)
            .all()
        )
        points = [
            {
                "ts":      snap.ts,
                "balance": float(snap.balance or 0),
                "equity":  float(snap.equity or 0),
                "day_pnl": float(snap.day_pnl or 0),
            }
            for snap in snapshots
        ]
        flat_equity = len({round(float(p.get('equity') or 0), 2) for p in points}) <= 1 if points else True
        return {
            "period_days": period_days,
            "points": points,
            "meta": {
                "points_count": len(points),
                "latest_ts": points[-1]["ts"] if points else None,
                "flat_equity": flat_equity,
                "note": "equity has not changed yet" if flat_equity and points else None,
            },
        }
    except Exception as exc:
        logger.error("Account history failed", exc_info=exc)
        return {"period_days": period_days, "points": []}


@router.get("/daily-stats")
async def daily_stats(db: Session = Depends(get_db)):
    return build_daily_stats_sync(db)


def build_daily_stats_sync(db: Session):
    try:
        today_ms = _today_ms()
        trades_count = db.query(Trade).filter(Trade.ts >= today_ms).count()
        closed_today = (
            db.query(Position)
            .filter(Position.qty == 0, Position.updated_ts >= today_ms)
            .all()
        )
        pnls = [float(p.realized_pnl or 0) for p in closed_today]
        wins = [p for p in pnls if p > 0]

        open_positions = db.query(Position).filter(Position.qty > 0).count()

        losses = [p for p in pnls if p < 0]
        best  = round(max(wins), 2) if wins else 0.0
        worst = round(min(losses), 2) if losses else 0.0

        return {
            "day_pnl":        round(sum(pnls), 2),
            "trades_count":   trades_count,
            "win_rate":       round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
            "best_trade":     best,
            "worst_trade":    worst,
            "wins_count":     len(wins),
            "losses_count":   len(losses),
            "open_positions": open_positions,
            "degraded": False,
        }
    except Exception as exc:
        logger.error("Daily stats failed", exc_info=exc)
        return {
            "day_pnl": 0.0,
            "trades_count": 0,
            "win_rate": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "wins_count": 0,
            "losses_count": 0,
            "open_positions": 0,
            "degraded": True,
        }


@router.get("/tbank/accounts")
async def tbank_accounts(db: Session = Depends(get_db)):
    token = get_token("TBANK_TOKEN") or cfg.TBANK_TOKEN
    selected_account_id = get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID or ""

    if not token:
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": "TBANK_TOKEN is not configured",
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
        }

    adapter = await _get_tbank_adapter()
    try:
        broker_accounts_raw = await adapter.get_accounts()
        bank_accounts_raw = await adapter.get_bank_accounts() if not cfg.TBANK_SANDBOX else []
        return {
            "available": True,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "live_trading_enabled": bool(cfg.LIVE_TRADING_ENABLED),
            "selected_account_id": selected_account_id,
            "broker_accounts": [_normalize_account(item, selected_id=selected_account_id) for item in broker_accounts_raw],
            "bank_accounts": [_normalize_account(item) for item in bank_accounts_raw],
        }
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }


@router.post("/tbank/select-account")
async def tbank_select_account(body: SelectAccountRequest, db: Session = Depends(get_db)):
    adapter = await _get_tbank_adapter()
    try:
        resolved = await adapter.resolve_account_id(body.account_id)
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }

    _upsert_runtime_secret(
        db,
        "TBANK_ACCOUNT_ID",
        resolved,
        label="T-Bank Account ID",
        description="Идентификатор активного счёта T-Bank для торговли через UI.",
        category="broker",
    )
    return {"ok": True, "selected_account_id": resolved, "sandbox": cfg.TBANK_SANDBOX}


@router.post("/tbank/sandbox/open-account")
async def tbank_open_sandbox_account(body: SandboxOpenAccountRequest, db: Session = Depends(get_db)):
    if not cfg.TBANK_SANDBOX:
        raise HTTPException(status_code=400, detail="Sandbox actions require TBANK_SANDBOX=true")

    adapter = await _get_tbank_adapter()
    try:
        created = await adapter.open_sandbox_account(body.name)
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }

    account_id = created.get("accountId") or created.get("account_id")
    if body.activate and account_id:
        _upsert_runtime_secret(
            db,
            "TBANK_ACCOUNT_ID",
            account_id,
            label="T-Bank Account ID",
            description="Идентификатор активного песочного счёта T-Bank для торговли через UI.",
            category="broker",
        )

    return {
        "ok": True,
        "sandbox": True,
        "created_account_id": account_id,
        "selected_account_id": account_id if body.activate else (get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID or ""),
        "raw": created,
    }


@router.post("/tbank/sandbox/pay-in")
async def tbank_sandbox_pay_in(body: SandboxPayInRequest, db: Session = Depends(get_db)):
    if not cfg.TBANK_SANDBOX:
        raise HTTPException(status_code=400, detail="Sandbox actions require TBANK_SANDBOX=true")

    adapter = await _get_tbank_adapter()
    amount = _to_decimal_amount(body.amount)
    try:
        result = await adapter.sandbox_pay_in(account_id=body.account_id, amount=amount, currency=body.currency)
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }

    if body.activate:
        _upsert_runtime_secret(
            db,
            "TBANK_ACCOUNT_ID",
            body.account_id,
            label="T-Bank Account ID",
            description="Идентификатор активного песочного счёта T-Bank для торговли через UI.",
            category="broker",
        )

    return {
        "ok": True,
        "sandbox": True,
        "account_id": body.account_id,
        "amount": str(amount),
        "currency": body.currency.upper(),
        "balance": result.get("balance"),
        "raw": result,
    }


@router.post("/tbank/pay-in")
async def tbank_pay_in(body: BrokerPayInRequest):
    if cfg.TBANK_SANDBOX:
        raise HTTPException(status_code=400, detail="Use /sandbox/pay-in when TBANK_SANDBOX=true")

    adapter = await _get_tbank_adapter()
    amount = _to_decimal_amount(body.amount)
    try:
        result = await adapter.pay_in(
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=amount,
            currency=body.currency,
        )
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }

    return {
        "ok": True,
        "sandbox": False,
        "from_account_id": body.from_account_id,
        "to_account_id": body.to_account_id,
        "amount": str(amount),
        "currency": body.currency.upper(),
        "raw": result,
    }


@router.post("/tbank/transfer")
async def tbank_transfer_between_broker_accounts(body: BrokerTransferRequest):
    if cfg.TBANK_SANDBOX:
        raise HTTPException(status_code=400, detail="Broker account transfers are not available in sandbox mode")

    adapter = await _get_tbank_adapter()
    amount = _to_decimal_amount(body.amount)
    try:
        result = await adapter.currency_transfer(
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=amount,
            currency=body.currency,
        )
    except TBankApiError as exc:
        logger.warning("T-Bank accounts fetch failed: %s", exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }
    except Exception as exc:
        logger.error("Unexpected T-Bank accounts fetch failure", exc_info=exc)
        return {
            "available": False,
            "provider": cfg.BROKER_PROVIDER,
            "sandbox": cfg.TBANK_SANDBOX,
            "message": str(exc),
            "selected_account_id": selected_account_id,
            "broker_accounts": [],
            "bank_accounts": [],
            "degraded": True,
        }

    return {
        "ok": True,
        "sandbox": False,
        "from_account_id": body.from_account_id,
        "to_account_id": body.to_account_id,
        "amount": str(amount),
        "currency": body.currency.upper(),
        "raw": result,
    }


@router.post("/paper/reset")
async def reset_paper_account(db: Session = Depends(get_db)):
    return await reset_paper_state(db)
