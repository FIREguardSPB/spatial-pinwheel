from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.deps import verify_token
from core.services.worker_status import read_worker_status

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/stats')
async def get_tbank_stats():
    status = await read_worker_status()
    stats = status.get('tbank_stats') if isinstance(status, dict) else None
    if not stats:
        return {
            'available': False,
            'message': 'T-Bank runtime stats are unavailable',
            'requests_per_sec': 0.0,
            'by_method': {},
            'recommendations': ['Start worker polling to collect T-Bank stats.'],
        }
    stats.setdefault('available', True)
    return stats
