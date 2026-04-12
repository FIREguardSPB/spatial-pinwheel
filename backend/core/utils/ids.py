from __future__ import annotations

import uuid


def new_prefixed_id(prefix: str) -> str:
    prefix = str(prefix or '').strip('_')
    return f"{prefix}_{uuid.uuid4().hex}" if prefix else uuid.uuid4().hex
