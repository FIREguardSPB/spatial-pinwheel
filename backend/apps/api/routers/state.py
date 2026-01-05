from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import state as repo
from core.models import schemas

router = APIRouter()

@router.get("/orders", response_model=schemas.OrderList)
def get_orders(db: Session = Depends(get_db)):
    return {"items": repo.list_orders(db)}

@router.get("/trades", response_model=schemas.TradeList)
def get_trades(db: Session = Depends(get_db)):
    return {"items": repo.list_trades(db)}

@router.get("/positions", response_model=schemas.PositionList)
def get_positions(db: Session = Depends(get_db)):
    return {"items": repo.list_positions(db)}
