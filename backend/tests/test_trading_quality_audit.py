import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.services.trading_quality_audit import _journey_stage


class _Signal:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TradingQualityAuditTests(unittest.TestCase):
    def test_journey_stage_prefers_closed_then_filled(self):
        signal = _Signal(status='executed', meta={'final_decision': 'TAKE'})
        self.assertEqual(_journey_stage(signal=signal, fills_count=1, closed_count=1), 'closed')
        self.assertEqual(_journey_stage(signal=signal, fills_count=1, closed_count=0), 'filled')

    def test_journey_stage_marks_take_without_fill(self):
        signal = _Signal(status='pending_review', meta={'final_decision': 'TAKE'})
        self.assertEqual(_journey_stage(signal=signal, fills_count=0, closed_count=0), 'take_not_filled')
        signal2 = _Signal(status='rejected', meta={'final_decision': 'TAKE'})
        self.assertEqual(_journey_stage(signal=signal2, fills_count=0, closed_count=0), 'risk_rejected')


if __name__ == '__main__':
    unittest.main()
