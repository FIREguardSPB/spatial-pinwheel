import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.ml.runtime import evaluate_ml_overlay


class MLRuntimeTests(unittest.TestCase):
    @patch('core.ml.runtime.load_artifact')
    @patch('core.ml.runtime.get_latest_training_run')
    def test_evaluate_ml_overlay_can_veto_take(self, mocked_get_run, mocked_load):
        mocked_get_run.side_effect = [SimpleNamespace(id='outcome_run', artifact_path='a'), SimpleNamespace(id='fill_run', artifact_path='b')]
        mocked_load.side_effect = [
            {'vectorizer': None, 'model': None},
            {'vectorizer': None, 'model': None},
        ]
        settings = SimpleNamespace(
            ml_enabled=True,
            ml_allow_take_veto=True,
            ml_take_probability_threshold=0.6,
            ml_fill_probability_threshold=0.5,
            ml_risk_boost_threshold=0.7,
            ml_risk_cut_threshold=0.45,
            ml_pass_risk_multiplier=1.15,
            ml_fail_risk_multiplier=0.75,
            ml_threshold_bonus=4,
            ml_threshold_penalty=8,
            ml_execution_priority_boost=1.15,
            ml_execution_priority_penalty=0.8,
            ml_allocator_boost=1.1,
            ml_allocator_penalty=0.85,
        )
        with patch('core.ml.runtime.predict_probability', side_effect=[0.41, 0.33]):
            overlay = evaluate_ml_overlay(
                object(),
                settings,
                instrument_id='TQBR:SBER',
                side='BUY',
                entry=100.0,
                sl=99.0,
                tp=102.0,
                size=10.0,
                ts_ms=1710000000000,
                meta={'strategy_name': 'breakout', 'regime': 'trend', 'decision': {'score': 70}},
                final_decision='TAKE',
            )
        self.assertTrue(overlay.suppress_take)
        self.assertLess(overlay.risk_multiplier, 1.0)
        self.assertEqual(overlay.reason, 'ml_take_veto')
        self.assertEqual(overlay.action, 'veto')


if __name__ == '__main__':
    unittest.main()
