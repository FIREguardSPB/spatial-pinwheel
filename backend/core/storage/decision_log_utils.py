from __future__ import annotations

import logging
import time
from typing import Any

try:
    from sqlalchemy.exc import IntegrityError
except Exception:  # pragma: no cover
    class IntegrityError(Exception):
        pass

try:
    from core.storage.models import DecisionLog
except Exception:  # pragma: no cover
    class DecisionLog:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

try:
    from core.storage.session import SessionLocal
except Exception:  # pragma: no cover
    def SessionLocal():
        class _DummySession:
            bind = None
            def execute(self, *args, **kwargs):
                return type('R', (), {'rowcount': 1})()
            def add(self, *args, **kwargs):
                return None
            def flush(self):
                return None
            def commit(self):
                return None
            def rollback(self):
                return None
            def close(self):
                return None
        return _DummySession()
from core.utils.ids import new_prefixed_id

logger = logging.getLogger(__name__)

try:
    from sqlalchemy.dialects.postgresql import insert as _pg_insert
except Exception:  # pragma: no cover
    _pg_insert = None

try:
    from sqlalchemy.dialects.sqlite import insert as _sqlite_insert
except Exception:  # pragma: no cover
    _sqlite_insert = None


def build_decision_log_row(*, log_type: str, message: str, payload: dict[str, Any] | None = None, ts_ms: int | None = None, log_id: str | None = None) -> dict[str, Any]:
    return {
        'id': str(log_id or new_prefixed_id('log')),
        'ts': int(ts_ms or time.time() * 1000),
        'type': str(log_type),
        'message': str(message),
        'payload': dict(payload or {}),
    }


def _instantiate_decision_log(row: dict[str, Any]):
    try:
        return DecisionLog(**row)
    except TypeError:
        record = DecisionLog()
        for key, value in row.items():
            setattr(record, key, value)
        return record


def _execute_insert(session, row: dict[str, Any]) -> bool:
    bind = getattr(session, 'bind', None)
    dialect = getattr(getattr(bind, 'dialect', None), 'name', '') if bind is not None else ''
    if dialect == 'postgresql' and _pg_insert is not None:
        stmt = _pg_insert(DecisionLog).values(**row).on_conflict_do_nothing(index_elements=['id'])
        result = session.execute(stmt)
        return bool(getattr(result, 'rowcount', 0))
    if dialect == 'sqlite' and _sqlite_insert is not None:
        stmt = _sqlite_insert(DecisionLog).values(**row).on_conflict_do_nothing(index_elements=['id'])
        result = session.execute(stmt)
        return bool(getattr(result, 'rowcount', 0))
    session.add(_instantiate_decision_log(row))
    session.flush()
    return True


def append_decision_log_best_effort(*, log_type: str, message: str, payload: dict[str, Any] | None = None, ts_ms: int | None = None) -> bool:
    row = build_decision_log_row(log_type=log_type, message=message, payload=payload, ts_ms=ts_ms)
    session = SessionLocal()
    try:
        inserted = _execute_insert(session, row)
        session.commit()
        return inserted
    except IntegrityError:
        session.rollback()
        logger.warning('DecisionLog duplicate skipped id=%s type=%s', row['id'], row['type'])
        return False
    except Exception:
        session.rollback()
        logger.warning('DecisionLog best-effort write failed type=%s', row['type'], exc_info=True)
        return False
    finally:
        session.close()


def stage_decision_log(session, *, log_type: str, message: str, payload: dict[str, Any] | None = None, ts_ms: int | None = None, log_id: str | None = None) -> DecisionLog:
    row = build_decision_log_row(log_type=log_type, message=message, payload=payload, ts_ms=ts_ms, log_id=log_id)
    record = _instantiate_decision_log(row)
    session.add(record)
    return record
