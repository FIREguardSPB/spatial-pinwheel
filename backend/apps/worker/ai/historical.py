from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import Position, Signal


@dataclass
class HistoricalPattern:
    score: float
    source: str
    summary: str
    outcome: str | None = None
    reference: str | None = None


class HistoricalContextAnalyzer:
    """Lightweight historical-pattern retriever.

    It uses two grounded sources:
    1) recent DB signals/closed positions for the same instrument/strategy;
    2) optional markdown memory files from HISTORICAL_CONTEXT_DIR.
    """

    def __init__(self, db: Session, memory_dir: str | None = None):
        self.db = db
        self.memory_dir = Path(memory_dir or os.getenv('HISTORICAL_CONTEXT_DIR', '/home/master/.openclaw/workspace/memory'))

    def analyze(self, instrument_id: str, side: str, strategy_name: str | None, de_metrics: dict[str, Any] | None = None, limit: int = 4) -> dict[str, Any]:
        patterns: list[HistoricalPattern] = []
        patterns.extend(self._from_db(instrument_id, side, strategy_name, de_metrics or {}, limit=limit))
        patterns.extend(self._from_memory_files(instrument_id, strategy_name, limit=limit))
        patterns.sort(key=lambda item: item.score, reverse=True)
        top = patterns[:limit]
        return {
            'patterns': [
                {
                    'score': round(p.score, 3),
                    'source': p.source,
                    'summary': p.summary,
                    'outcome': p.outcome,
                    'reference': p.reference,
                } for p in top
            ],
            'summary': ' | '.join(p.summary for p in top[:3]) if top else '',
        }

    def _from_db(self, instrument_id: str, side: str, strategy_name: str | None, de_metrics: dict[str, Any], limit: int) -> list[HistoricalPattern]:
        results: list[HistoricalPattern] = []
        signals = (
            self.db.query(Signal)
            .filter(Signal.instrument_id == instrument_id)
            .order_by(Signal.created_ts.desc())
            .limit(100)
            .all()
        )
        for signal in signals:
            meta = signal.meta or {}
            signal_strategy = str((meta.get('multi_strategy') or {}).get('selected') or meta.get('strategy') or meta.get('strategy_name') or '')
            if strategy_name and signal_strategy and strategy_name not in signal_strategy:
                continue
            decision = meta.get('decision') or {}
            hist_score = float(decision.get('score') or 0)
            hist_metrics = decision.get('metrics') or {}
            sim = 0.0
            if str(signal.side) == str(side):
                sim += 0.35
            if signal_strategy == (strategy_name or signal_strategy):
                sim += 0.25
            if de_metrics:
                for key in ('vol_ratio', 'net_rr', 'stop_atr_ratio'):
                    cur = de_metrics.get(key)
                    prev = hist_metrics.get(key)
                    if cur is None or prev is None:
                        continue
                    try:
                        diff = abs(float(cur) - float(prev))
                        sim += max(0.0, 0.15 - min(diff, 1.5) * 0.08)
                    except Exception:
                        pass
            pos = None
            if signal.id:
                pos = self.db.query(Position).filter(Position.opened_signal_id == signal.id).order_by(Position.updated_ts.desc()).first()
            outcome = None
            pnl = None
            if pos and int(float(pos.qty or 0)) == 0:
                pnl = float(pos.realized_pnl or 0)
                outcome = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'flat'
                sim += 0.15
            if sim <= 0:
                continue
            summary = f"{instrument_id} {signal.side} {signal_strategy or 'unknown'} score={hist_score:.0f}"
            if pnl is not None:
                summary += f" pnl={pnl:+.2f}"
            results.append(HistoricalPattern(sim, 'db', summary, outcome=outcome, reference=signal.id))
            if len(results) >= limit:
                break
        return results

    def _from_memory_files(self, instrument_id: str, strategy_name: str | None, limit: int) -> list[HistoricalPattern]:
        if not self.memory_dir.exists():
            return []
        code = instrument_id.split(':')[-1]
        files = sorted(self.memory_dir.glob('*.md'))[-5:]
        results: list[HistoricalPattern] = []
        for path in reversed(files):
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            if code not in text and instrument_id not in text:
                continue
            matches = [m.group(0).strip() for m in re.finditer(rf'.{{0,80}}(?:{re.escape(code)}|{re.escape(instrument_id)}).{{0,180}}', text, re.IGNORECASE)]
            if not matches:
                continue
            for match in matches[:2]:
                score = 0.2
                low = match.lower()
                if strategy_name and strategy_name.lower() in low:
                    score += 0.1
                if 'take' in low or 'tp' in low or 'profit' in low:
                    score += 0.08
                if 'loss' in low or 'sl' in low:
                    score += 0.05
                results.append(HistoricalPattern(score, 'memory', re.sub(r'\s+', ' ', match)[:220], reference=str(path.name)))
                if len(results) >= limit:
                    return results
        return results
