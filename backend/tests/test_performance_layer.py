import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.services.performance_layer import _bucket_table, _walk_forward_status


class PerformanceLayerTests(unittest.TestCase):
    def test_bucket_table_computes_pf_expectancy_and_status(self):
        rows = {
            'breakout | trend': {
                'pnls': [120.0, -40.0, 60.0],
                'captures': [0.7, 0.5],
                'trades': 3,
                'wins': 2,
                'losses': 1,
            }
        }
        table = _bucket_table(rows, key_name='slice')
        self.assertEqual(len(table), 1)
        row = table[0]
        self.assertEqual(row['slice'], 'breakout | trend')
        self.assertAlmostEqual(row['profit_factor'], 4.5, places=3)
        self.assertAlmostEqual(row['expectancy_per_trade'], 46.6667, places=3)
        self.assertEqual(row['status'], 'pass')

    def test_walk_forward_status_requires_breadth_and_oos_quality(self):
        self.assertEqual(_walk_forward_status(instruments=0, pass_rate_pct=0.0, avg_oos_score=0.0, avg_oos_pf=0.0), 'insufficient_data')
        self.assertEqual(_walk_forward_status(instruments=4, pass_rate_pct=70.0, avg_oos_score=13.0, avg_oos_pf=1.2), 'pass')
        self.assertEqual(_walk_forward_status(instruments=4, pass_rate_pct=45.0, avg_oos_score=5.5, avg_oos_pf=0.98), 'partial')
        self.assertEqual(_walk_forward_status(instruments=4, pass_rate_pct=20.0, avg_oos_score=1.0, avg_oos_pf=0.6), 'fail')


if __name__ == '__main__':
    unittest.main()
