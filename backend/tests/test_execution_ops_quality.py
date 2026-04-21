import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.execution.fill_quality import build_fill_quality
from core.execution.paper import PaperExecutionEngine
from core.execution.ops import close_all_positions, close_symbol_positions
from core.storage.models import Position


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)


class _FakeDB:
    def __init__(self, positions):
        self.positions = list(positions)

    def query(self, _model):
        return _FakeQuery(self.positions)


class ExecutionOpsQualityTests(unittest.TestCase):
    def test_execution_quality_seed_carries_conviction_and_review_context(self):
        signal = SimpleNamespace(meta={
            'thesis_timeframe': '15m',
            'review_readiness': {'approval_candidate': True, 'queue_priority': 109},
            'conviction_profile': {'tier': 'B', 'net_rr': 1.6},
            'high_conviction_promotion': {'promoted': True},
        })
        seed = PaperExecutionEngine._execution_quality_seed(signal, {'status': 'ok'})
        self.assertEqual(seed['thesis_timeframe'], '15m')
        self.assertTrue(seed['review_readiness']['approval_candidate'])
        self.assertEqual(seed['conviction_profile']['tier'], 'B')
        self.assertTrue(seed['high_conviction_promotion']['promoted'])
        self.assertEqual(seed['fill_quality_status'], 'ok')

    def test_fill_quality_marks_adverse_anomaly(self):
        payload = build_fill_quality(
            requested_price=100.0,
            actual_price=100.25,
            side='BUY',
            qty=10,
            expected_slippage_bps=5,
            end_to_end_ms=180,
        )

        self.assertEqual(payload['status'], 'anomaly')
        self.assertTrue(payload['adverse'])
        self.assertGreater(payload['slippage_bps'], payload['anomaly_threshold_bps'])

    def test_fill_quality_marks_better_fill_as_ok(self):
        payload = build_fill_quality(
            requested_price=100.0,
            actual_price=99.98,
            side='BUY',
            qty=10,
            expected_slippage_bps=5,
            end_to_end_ms=20,
        )

        self.assertEqual(payload['status'], 'ok')
        self.assertFalse(payload['adverse'])
        self.assertLess(payload['signed_slippage_bps'], 0)

    def test_close_symbol_positions_uses_monitor_in_non_live_mode(self):
        position = Position(
            instrument_id='TQBR:SBER',
            side='BUY',
            qty=Decimal('2'),
            avg_price=Decimal('100'),
            last_mark_price=Decimal('101'),
            opened_ts=1,
        )
        db = _FakeDB([position])

        with patch('core.execution.ops.settings_repo.get_settings', return_value=SimpleNamespace(trade_mode='auto_paper')), \
             patch('core.execution.ops.PositionMonitor') as monitor_mock:
            monitor_mock.return_value._close_position = AsyncMock()
            result = asyncio.run(close_symbol_positions(db, 'TQBR:SBER', reason='OPERATOR_CLOSE_SYMBOL'))

        self.assertEqual(result['closed'], 1)
        monitor_mock.return_value._close_position.assert_awaited()

    def test_close_all_positions_groups_by_instrument(self):
        positions = [
            Position(instrument_id='TQBR:SBER', side='BUY', qty=Decimal('1'), avg_price=Decimal('100'), last_mark_price=Decimal('100'), opened_ts=1),
            Position(instrument_id='TQBR:GAZP', side='BUY', qty=Decimal('1'), avg_price=Decimal('200'), last_mark_price=Decimal('200'), opened_ts=1),
        ]
        db = _FakeDB(positions)

        with patch('core.execution.ops.close_symbol_positions', new=AsyncMock(side_effect=[
            {'requested': 1, 'closed': 1, 'skipped': [], 'instrument_id': 'TQBR:GAZP'},
            {'requested': 1, 'closed': 1, 'skipped': [], 'instrument_id': 'TQBR:SBER'},
        ])) as close_mock:
            result = asyncio.run(close_all_positions(db, reason='OPERATOR_CLOSE_ALL'))

        self.assertEqual(result['requested_instruments'], 2)
        self.assertEqual(result['closed_positions'], 2)
        self.assertEqual(close_mock.await_count, 2)


if __name__ == '__main__':
    unittest.main()
