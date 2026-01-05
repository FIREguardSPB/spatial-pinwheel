from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import state as repo
from core.models import schemas

router = APIRouter()

@router.get("", response_model=schemas.LogList)
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    items = repo.list_logs(db, limit)
    return {"items": items, "next_cursor": None}
