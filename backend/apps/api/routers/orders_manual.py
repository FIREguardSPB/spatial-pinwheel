from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from apps.broker.tbank import TBankGrpcAdapter
from apps.broker.tbank.adapter import TBankApiError
from core.config import get_token, settings as config
from core.events.bus import bus
from core.models import schemas
from core.storage.repos import settings as settings_repo
from core.storage.models import Order, Position, Settings, Trade
from core.storage.session import get_db
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.utils.ids import new_prefixed_id

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


def _as_decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _require_positive(name: str, value: Decimal) -> None:
    if value <= 0:
        raise HTTPException(status_code=422, detail=f"{name} must be positive")


def _paper_balance_check(db: Session, side: str, qty: Decimal, fill_price: Decimal) -> None:
    settings = settings_repo.get_settings(db)
    balance = Decimal(str(getattr(settings, "account_balance", 100_000) or 100_000))
    cost = qty * fill_price
    if side == "BUY" and cost > balance:
        raise HTTPException(status_code=409, detail="Insufficient paper balance for this order")


def _update_position(db: Session, instrument_id: str, side: str, qty: Decimal, fill_price: Decimal):
    now_ms = int(time.time() * 1000)
    position = db.query(Position).filter(Position.instrument_id == instrument_id).first()
    if not position:
        position = Position(
            instrument_id=instrument_id,
            side=side,
            qty=qty,
            opened_qty=qty,
            avg_price=fill_price,
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            opened_ts=now_ms,
        )
        db.add(position)
        return position

    if position.side == side:
        total_qty = _as_decimal(position.qty) + qty
        if total_qty <= 0:
            total_qty = Decimal("0")
        total_cost = _as_decimal(position.qty) * _as_decimal(position.avg_price) + qty * fill_price
        position.avg_price = (total_cost / total_qty) if total_qty > 0 else fill_price
        position.qty = total_qty
        position.opened_qty = total_qty
        position.updated_ts = now_ms
        return position

    current_qty = _as_decimal(position.qty)
    if current_qty < qty:
        raise HTTPException(status_code=409, detail="Requested SELL qty exceeds current open position")

    realized = (fill_price - _as_decimal(position.avg_price)) * qty
    if position.side == "SELL":
        realized = -realized
    position.realized_pnl = _as_decimal(position.realized_pnl or 0) + realized
    position.qty = current_qty - qty
    position.updated_ts = now_ms
    if position.qty <= 0:
        position.qty = Decimal("0")
    return position


async def _simulate_manual_fill(
    db: Session,
    *,
    instrument_id: str,
    side: str,
    order_type: str,
    qty: Decimal,
    fill_price: Decimal,
    comment: str | None = None,
) -> schemas.ManualOrderResponse:
    _require_positive("qty", qty)
    _require_positive("price", fill_price)
    _paper_balance_check(db, side, qty, fill_price)

    now_ms = int(time.time() * 1000)
    order = Order(
        order_id=new_prefixed_id("ord_manual"),
        instrument_id=instrument_id,
        ts=now_ms,
        side=side,
        type=order_type,
        price=fill_price,
        qty=qty,
        filled_qty=qty,
        status="FILLED",
        related_signal_id=None,
        ai_influenced=False,
        ai_mode_used="manual",
    )
    db.add(order)

    trade = Trade(
        trade_id=new_prefixed_id("trd_manual"),
        instrument_id=instrument_id,
        ts=now_ms,
        side=side,
        price=fill_price,
        qty=qty,
        order_id=order.order_id,
    )
    db.add(trade)

    _update_position(db, instrument_id, side, qty, fill_price)
    db.commit()
    append_decision_log_best_effort(
        log_type="manual_order",
        message=f"Manual {order_type} {side} {instrument_id} x{qty} @ {fill_price}",
        payload={"order_id": order.order_id, "comment": comment or "", "instrument_id": instrument_id},
        ts_ms=now_ms,
    )
    db.refresh(order)

    await bus.publish("orders_updated", {"order_id": order.order_id, "manual": True})
    await bus.publish("trade_filled", {"trade_id": trade.trade_id, "manual": True})
    await bus.publish("positions_updated", {"instrument_id": instrument_id})

    return schemas.ManualOrderResponse(
        status="ok",
        order_id=order.order_id,
        filled_price=fill_price,
        detail="Manual order filled in application ledger",
    )


async def _submit_tbank_order(
    *,
    instrument_id: str,
    side: str,
    qty: Decimal,
    qty_mode: str,
    order_type: str,
    limit_price: Decimal | None = None,
) -> schemas.ManualOrderResponse:
    adapter = TBankGrpcAdapter(
        token=get_token("TBANK_TOKEN") or config.TBANK_TOKEN,
        account_id=get_token("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID,
        sandbox=config.TBANK_SANDBOX,
    )
    try:
        details = await adapter.ensure_instrument_tradable(instrument_id, side)
        qty_units = qty if qty_mode == 'units' else qty * Decimal(str(details.get('lot') or 1))
        lots = adapter.normalize_signal_qty_to_lots(qty_units, int(details.get('lot') or 1))
        order_id = str(uuid.uuid4())

        if order_type == 'MARKET':
            resp = await adapter.post_market_order(
                instrument_id=details['uid'],
                quantity_lots=lots,
                direction=side,
                order_id=order_id,
            )
        else:
            if limit_price is None:
                raise HTTPException(status_code=422, detail='price is required for limit order')
            resp = await adapter.post_limit_order(
                instrument_id=details['uid'],
                quantity_lots=lots,
                direction=side,
                limit_price=limit_price,
                order_id=order_id,
            )

        broker_order_id = resp.get('orderId') or resp.get('order_id') or order_id
        return schemas.ManualOrderResponse(
            status='submitted',
            order_id=new_prefixed_id('manual'),
            broker_order_id=broker_order_id,
            detail='Submitted to T-Bank via REST order endpoint',
        )
    except TBankApiError as exc:
        logger.warning('T-Bank manual order rejected: %s', exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        try:
            await adapter.close()
        except Exception:
            pass


@router.post('/market', response_model=schemas.ManualOrderResponse)
async def place_market_order(payload: schemas.ManualMarketOrderRequest, db: Session = Depends(get_db)):
    qty = _as_decimal(payload.qty)
    _require_positive('qty', qty)
    reference_price = _as_decimal(payload.reference_price or 0)

    if config.BROKER_PROVIDER == 'tbank' and (get_token('TBANK_TOKEN') or config.TBANK_TOKEN):
        return await _submit_tbank_order(
            instrument_id=payload.instrument_id,
            side=payload.side,
            qty=qty,
            qty_mode=payload.qty_mode,
            order_type='MARKET',
        )

    if reference_price <= 0:
        raise HTTPException(status_code=422, detail='reference_price is required for manual market orders in paper mode')
    return await _simulate_manual_fill(
        db,
        instrument_id=payload.instrument_id,
        side=payload.side,
        order_type='MARKET',
        qty=qty,
        fill_price=reference_price,
        comment=payload.comment,
    )


@router.post('/limit', response_model=schemas.ManualOrderResponse)
async def place_limit_order(payload: schemas.ManualLimitOrderRequest, db: Session = Depends(get_db)):
    qty = _as_decimal(payload.qty)
    price = _as_decimal(payload.price)
    _require_positive('qty', qty)
    _require_positive('price', price)

    if config.BROKER_PROVIDER == 'tbank' and (get_token('TBANK_TOKEN') or config.TBANK_TOKEN):
        return await _submit_tbank_order(
            instrument_id=payload.instrument_id,
            side=payload.side,
            qty=qty,
            qty_mode=payload.qty_mode,
            order_type='LIMIT',
            limit_price=price,
        )

    return await _simulate_manual_fill(
        db,
        instrument_id=payload.instrument_id,
        side=payload.side,
        order_type='LIMIT',
        qty=qty,
        fill_price=price,
        comment=payload.comment,
    )
