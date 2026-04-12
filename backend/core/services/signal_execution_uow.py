from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignalExecutionUnitOfWork:
    db: Any
    signal_id: str
    trace_id: str | None = None
    started_ts: int = field(default_factory=lambda: int(time.time() * 1000))
    steps: list[dict[str, Any]] = field(default_factory=list)
    committed: bool = False

    def mark(self, stage: str, **payload: Any) -> None:
        self.steps.append({
            'stage': stage,
            'ts': int(time.time() * 1000),
            **payload,
        })

    def commit(self) -> None:
        self.db.commit()
        self.committed = True
        self.mark('commit')

    def rollback(self, *, reason: str | None = None) -> None:
        self.db.rollback()
        self.committed = False
        self.mark('rollback', reason=reason)

    def to_meta(self) -> dict[str, Any]:
        return {
            'signal_id': self.signal_id,
            'trace_id': self.trace_id,
            'started_ts': self.started_ts,
            'finished_ts': int(time.time() * 1000),
            'committed': self.committed,
            'steps': list(self.steps),
        }
