import unittest

from core.services.signal_meta_compact import compact_signal_meta


class SignalsCompactMetaTests(unittest.TestCase):
    def test_compact_meta_keeps_ml_overlay_small_but_informative(self):
        payload = compact_signal_meta({
            'final_decision': 'TAKE',
            'decision': {'decision': 'TAKE', 'score': 77, 'reasons': [{'code': 'OK'}]},
            'ai_decision': {
                'provider': 'deepseek',
                'decision': 'TAKE',
                'confidence': 81,
                'reasoning': 'very long chain of reasoning that should not leak into hot path',
                'key_factors': ['a', 'b', 'c'],
            },
            'ml_overlay': {
                'target_probability': 0.78,
                'fill_probability': 0.61,
                'reason': 'ml_boost',
                'target_model_id': 'ml_target_12345678',
                'fill_model_id': 'ml_fill_87654321',
            },
        })

        self.assertEqual(payload['ml_overlay']['action'], 'boost')
        self.assertEqual(payload['ml_overlay']['target_model_id'], 'ml_target_12345678')
        self.assertEqual(payload['ml_overlay']['fill_model_id'], 'ml_fill_87654321')
        self.assertNotIn('reasoning', payload['ai_decision'])
        self.assertNotIn('key_factors', payload['ai_decision'])


if __name__ == '__main__':
    unittest.main()
