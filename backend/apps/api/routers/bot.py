from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from apps.api.status import build_bot_status, live_capable_for, normalize_trade_mode
from core.services.runtime_tokens import load_runtime_tokens
from core.storage.repos import settings as settings_repo
from core.storage.models import Settings
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


class StartBotPayload(BaseModel):
    mode: Literal["review", "auto_paper", "auto_live", "paper", "live"] | None = None


@router.get("/status")
async def get_bot_status(db: Session = Depends(get_db)):
    return await build_bot_status(db)


@router.post("/start")
async def start_bot(payload: StartBotPayload | None = None, db: Session = Depends(get_db)):
    settings = settings_repo.get_settings(db)
    if not settings:
        settings = Settings()
        db.add(settings)

    requested_mode = normalize_trade_mode(getattr(payload, "mode", None) or settings.trade_mode)
    token_map = load_runtime_tokens(db, ["TBANK_TOKEN", "TBANK_ACCOUNT_ID"])
    if requested_mode == "auto_live" and not live_capable_for(settings, token_map):
        raise HTTPException(
            status_code=422,
            detail="Auto Live requires BROKER_PROVIDER=tbank, TBANK_TOKEN, TBANK_ACCOUNT_ID and LIVE_TRADING_ENABLED=true",
        )
    if requested_mode not in {"review", "auto_paper", "auto_live"}:
        raise HTTPException(status_code=422, detail="Unsupported trading mode")

    settings.trade_mode = requested_mode
    settings.bot_enabled = True
    db.commit()
    db.refresh(settings)
    return await build_bot_status(db)


@router.post("/stop")
async def stop_bot(db: Session = Depends(get_db)):
    settings = settings_repo.get_settings(db)
    if not settings:
        settings = Settings()
        db.add(settings)
    settings.bot_enabled = False
    db.commit()
    db.refresh(settings)
    return await build_bot_status(db)
