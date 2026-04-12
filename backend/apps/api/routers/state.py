import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from core.storage.session import get_db
from core.storage.repos import state as repo
from core.models import schemas
from apps.api.deps import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


def _degraded_list_response(request: Request, entity: str, exc: Exception) -> JSONResponse:
    error_id = uuid.uuid4().hex[:10]
    request_id = getattr(getattr(request, 'state', None), 'request_id', '-')
    logger.error('Failed to load %s request_id=%s error_id=%s', entity, request_id, error_id, exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={
            'items': [],
            'degraded': True,
            'error': {
                'code': f'{entity}_unavailable',
                'message': f'{entity} temporarily unavailable',
                'request_id': request_id,
                'error_id': error_id,
            },
        },
    )


@router.get('/orders', response_model=schemas.OrderList)
def get_orders(request: Request, active_only: bool = Query(False), db: Session = Depends(get_db)):
    try:
        return {'items': repo.list_orders(db, active_only=active_only), 'degraded': False, 'error': None}
    except Exception as exc:
        return _degraded_list_response(request, 'orders', exc)


@router.get('/trades', response_model=schemas.TradeList)
def get_trades(request: Request, db: Session = Depends(get_db)):
    try:
        return {'items': repo.list_trades(db), 'degraded': False, 'error': None}
    except Exception as exc:
        return _degraded_list_response(request, 'trades', exc)


@router.get('/positions', response_model=schemas.PositionList)
def get_positions(request: Request, db: Session = Depends(get_db)):
    try:
        return {'items': repo.list_positions(db), 'degraded': False, 'error': None}
    except Exception as exc:
        return _degraded_list_response(request, 'positions', exc)


from apps.api.status import build_bot_status


@router.get('')
async def get_state_summary(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await build_bot_status(db)
        payload.setdefault('degraded', False)
        payload.setdefault('error', None)
        return payload
    except Exception as exc:
        error_id = uuid.uuid4().hex[:10]
        request_id = getattr(getattr(request, 'state', None), 'request_id', '-')
        logger.error('Failed to build bot status request_id=%s error_id=%s', request_id, error_id, exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={
                'is_running': False,
                'mode': 'review',
                'is_paper': True,
                'active_instrument_id': '',
                'connection': {'market_data': 'disconnected', 'broker': 'disconnected'},
                'warnings': ['State endpoint degraded. Check backend logs for details.'],
                'degraded': True,
                'error': {
                    'code': 'state_summary_unavailable',
                    'message': 'state summary temporarily unavailable',
                    'request_id': request_id,
                    'error_id': error_id,
                },
            },
        )
