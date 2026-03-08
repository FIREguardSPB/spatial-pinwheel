from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import signals as repo
from core.models import schemas
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("", response_model=schemas.SignalList)
def list_signals(limit: int = 50, status: str = Query(None), db: Session = Depends(get_db)):
    items = repo.list_signals(db, limit, status)

    # Tech Lead Req: Standardize on Seconds for API
    # Convert DB ms -> API seconds
    # Note: Pydantic model might need adjustment if it enforces int/float strictly.
    # Usually it's fine.

    # We need to return a dict or object that matches schema.
    # repo returns SQLAlchemy models.

    # P3-04: ts is stored as Unix ms in DB — pass through directly (no conversion needed)
    transformed = []
    for s in items:
        s_dict = {c.name: getattr(s, c.name) for c in s.__table__.columns}
        transformed.append(s_dict)

    return {"items": transformed, "next_cursor": None}


@router.post("/{signal_id}/approve")
async def approve_signal(
    signal_id: str, payload: schemas.ApproveSignal, db: Session = Depends(get_db)
):
    signal = repo.get_signal(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if signal.status != "pending_review":
        raise HTTPException(
            status_code=409, detail=f"Signal status is {signal.status}, expected pending_review"
        )

    repo.update_signal_status(db, signal_id, "approved")

    # Try to Publish Command via Redis
    try:
        from core.events.bus import bus
        import orjson

        # Notify UI
        await bus.publish("signal_updated", {"id": signal_id, "status": "approved"})
        # Command Worker
        await bus.redis.publish(
            "cmd:execute_signal", orjson.dumps({"signal_id": signal_id}).decode()
        )

    except Exception as e:
        print(f"Redis publish failed ({e}).")

        # Check Feature Flag
        from core.config import get_token, settings

        if not settings.ALLOW_NO_REDIS:
            print("Redis fallback is DISABLED. Raising 503.")
            raise HTTPException(
                status_code=503,
                detail="Redis unavailable and fallback disabled (ALLOW_NO_REDIS=False)",
            )

        print("Falling back to direct execution (ALLOW_NO_REDIS=True).")
        from core.storage.models import Settings as _Settings
        _settings = db.query(_Settings).first()
        if not _settings or not bool(getattr(_settings, "bot_enabled", False)):
            raise HTTPException(status_code=409, detail="Bot is disabled. Start the bot before executing signals.")

        # Fallback: Execute directly in API process (for dev/local without Redis)
        from core.execution.paper import PaperExecutionEngine
        from core.execution.tbank import TBankExecutionEngine

        trade_mode = getattr(_settings, "trade_mode", "review") or "review"
        if trade_mode == "auto_live":
            engine = TBankExecutionEngine(db, token=get_token("TBANK_TOKEN") or settings.TBANK_TOKEN, account_id=get_token("TBANK_ACCOUNT_ID") or settings.TBANK_ACCOUNT_ID, sandbox=settings.TBANK_SANDBOX)
        else:
            engine = PaperExecutionEngine(db)
        await engine.execute_approved_signal(signal_id)

    return {"status": "ok"}


@router.post("/{signal_id}/reject")
async def reject_signal(
    signal_id: str, payload: schemas.RejectSignal, db: Session = Depends(get_db)
):
    signal = repo.get_signal(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if signal.status != "pending_review":
        raise HTTPException(
            status_code=409, detail=f"Signal status is {signal.status}, expected pending_review"
        )

    repo.update_signal_status(db, signal_id, "rejected")

    from core.events.bus import bus

    await bus.publish("signal_updated", {"id": signal_id, "status": "rejected"})

    return {"status": "ok"}
