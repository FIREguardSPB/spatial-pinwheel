from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.deps import verify_token
from core.services.worker_status import read_worker_status

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/status')
async def get_worker_status():
    return await read_worker_status()
