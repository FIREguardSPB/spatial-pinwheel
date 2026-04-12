from __future__ import annotations

import io
import time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.services.forensic_export import build_forensic_export
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get('/export')
async def export_forensics(
    days: int = Query(30, ge=3, le=365),
    instrument_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    payload, summary = build_forensic_export(db, days=days, instrument_id=instrument_id)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    suffix = instrument_id.replace(':', '_') if instrument_id else 'all'
    filename = f'spatial_pinwheel_forensics_{suffix}_{stamp}.zip'
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'X-Forensic-Summary': str(summary.get('counts', {})),
    }
    return StreamingResponse(io.BytesIO(payload), media_type='application/zip', headers=headers)
