import unittest
from types import SimpleNamespace

from core.services.excursion_tracker import update_position_excursion


class DummyDB:
    def __init__(self):
        self.items = []
    def add(self, item):
        self.items.append(item)


class TestExcursionTracker(unittest.TestCase):
    def test_updates_mfe_and_mae(self):
        db = DummyDB()
        pos = SimpleNamespace(
            instrument_id='TQBR:SBER', trace_id='tr', opened_signal_id='sig', side='BUY',
            avg_price=100.0, qty=10.0, opened_qty=10.0, realized_pnl=0.0,
            mfe_total_pnl=None, mae_total_pnl=None, mfe_pct=None, mae_pct=None,
            best_price_seen=None, worst_price_seen=None, excursion_samples=0, excursion_updated_ts=None,
        )
        first = update_position_excursion(db, pos, 101.0, ts_ms=1, phase='tick')
        second = update_position_excursion(db, pos, 98.0, ts_ms=2, phase='tick')
        self.assertGreater(first['mfe_total_pnl'], 0)
        self.assertLess(second['mae_total_pnl'], 0)
        self.assertEqual(pos.excursion_samples, 2)
        self.assertEqual(len(db.items), 2)
