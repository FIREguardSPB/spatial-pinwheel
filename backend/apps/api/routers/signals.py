from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import signals as repo
from core.models import schemas

router = APIRouter()


@router.get("", response_model=schemas.SignalList)
def list_signals(limit: int = 50, status: str = Query(None), db: Session = Depends(get_db)):
    items = repo.list_signals(db, limit, status)

    # Tech Lead Req: Standardize on Seconds for API
    # Convert DB ms -> API seconds
    # Note: Pydantic model might need adjustment if it enforces int/float strictly.
    # Usually it's fine.

    # We need to return a dict or object that matches schema.
    # repo returns SQLAlchemy models.

    transformed = []
    for s in items:
        # Create a dict copy
        s_dict = {c.name: getattr(s, c.name) for c in s.__table__.columns}
        # Convert TS
        if s_dict.get("ts"):
            # Auto-detect MS vs Seconds
            ts_val = s_dict["ts"]
            if ts_val > 10000000000:  # It's MS
                s_dict["ts"] = int(ts_val / 1000)
            else:
                s_dict["ts"] = ts_val

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
        from core.config import settings

        if not settings.ALLOW_NO_REDIS:
            print("Redis fallback is DISABLED. Raising 503.")
            raise HTTPException(
                status_code=503,
                detail="Redis unavailable and fallback disabled (ALLOW_NO_REDIS=False)",
            )

        print("Falling back to direct execution (ALLOW_NO_REDIS=True).")
        # Fallback: Execute directly in API process (for dev/local without Redis)
        from core.execution.paper import PaperExecutionEngine

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
