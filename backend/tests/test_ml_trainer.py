import unittest

from core.ml.dataset import TrainingDataset, TrainingRow
from core.ml.trainer import predict_probability, train_classifier


class MLTrainerTests(unittest.TestCase):
    def test_train_classifier_and_predict(self):
        rows = []
        for idx in range(120):
            positive = idx % 2 == 0
            rows.append(TrainingRow(
                signal_id=f's{idx}',
                instrument_id='TQBR:SBER',
                target='trade_outcome',
                label=1 if positive else 0,
                features={
                    'strategy': 'breakout' if positive else 'mean_reversion',
                    'regime': 'trend' if positive else 'range',
                    'de_score': 80 if positive else 42,
                    'rr_multiple': 2.0 if positive else 0.8,
                    'ai_confidence': 75 if positive else 35,
                    'msk_hour': 10 if positive else 18,
                },
                meta={},
            ))
        dataset = TrainingDataset(target='trade_outcome', rows=rows, lookback_days=120, stats={})
        artifact = train_classifier(dataset, min_rows=40)
        self.assertGreaterEqual(artifact.metrics['roc_auc'], 0.8)
        proba_good = predict_probability(artifact, {
            'strategy': 'breakout', 'regime': 'trend', 'de_score': 82, 'rr_multiple': 2.1, 'ai_confidence': 78, 'msk_hour': 10,
        })
        proba_bad = predict_probability(artifact, {
            'strategy': 'mean_reversion', 'regime': 'range', 'de_score': 38, 'rr_multiple': 0.7, 'ai_confidence': 25, 'msk_hour': 18,
        })
        self.assertGreater(proba_good, proba_bad)


if __name__ == '__main__':
    unittest.main()
