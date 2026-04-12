from __future__ import annotations

from typing import Iterable

from core.config import settings as cfg
from core.security.crypto import decrypt_token
from core.storage.models import ApiToken


def load_runtime_tokens(db, keys: Iterable[str]) -> dict[str, str]:
    wanted = [str(k) for k in keys if k]
    if not wanted:
        return {}
    rows = (
        db.query(ApiToken)
        .filter(ApiToken.key_name.in_(wanted), ApiToken.is_active == True)  # noqa: E712
        .all()
    )
    mapping: dict[str, str] = {}
    for row in rows:
        raw = getattr(row, 'value', '') or ''
        if not raw:
            continue
        try:
            mapping[str(row.key_name)] = decrypt_token(raw)
        except Exception:
            mapping[str(row.key_name)] = raw
    for key in wanted:
        mapping.setdefault(key, str(getattr(cfg, key, '') or ''))
    return mapping
