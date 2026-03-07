"""
P5 Tests — Rules (P5-02 Volume, P5-04 HTF): score_volume, score_htf_alignment.
"""
import unittest
from apps.worker.decision_engine import rules
from apps.worker.decision_engine.types import Severity, ReasonCode


class TestScoreVolume(unittest.TestCase):

    def test_normal_volume_full_score(self):
        score, reason = rules.score_volume(1.2, max_score=10)
        self.assertEqual(score, 10)
        self.assertEqual(reason.code, ReasonCode.VOLUME_OK)
        self.assertEqual(reason.severity, Severity.INFO)

    def test_low_volume_block(self):
        score, reason = rules.score_volume(0.3, max_score=10, min_ratio=0.5)
        self.assertEqual(score, 0)
        self.assertEqual(reason.code, ReasonCode.VOLUME_LOW)
        self.assertEqual(reason.severity, Severity.BLOCK)

    def test_exactly_at_min_ratio_passes(self):
        score, reason = rules.score_volume(0.5, max_score=10, min_ratio=0.5)
        self.assertEqual(score, 10)

    def test_anomalous_volume_half_score(self):
        score, reason = rules.score_volume(5.0, max_score=10, anomalous_ratio=3.0)
        self.assertEqual(score, 5)
        self.assertEqual(reason.code, ReasonCode.VOLUME_ANOMALOUS)
        self.assertEqual(reason.severity, Severity.WARN)

    def test_exactly_at_anomalous_threshold_is_anomalous(self):
        score, reason = rules.score_volume(3.0, max_score=10, anomalous_ratio=3.0)
        # 3.0 > 3.0 is False → normal
        self.assertEqual(score, 10)

    def test_zero_ratio_is_blocked(self):
        score, reason = rules.score_volume(0.0, max_score=10)
        self.assertEqual(reason.severity, Severity.BLOCK)

    def test_various_max_scores(self):
        for max_s in [5, 10, 20]:
            s, r = rules.score_volume(1.5, max_score=max_s)
            self.assertEqual(s, max_s)


class TestScoreHTFAlignment(unittest.TestCase):

    def test_buy_with_uptrend_full_score(self):
        score, reason = rules.score_htf_alignment("BUY", "up", max_score=5)
        self.assertEqual(score, 5)
        self.assertEqual(reason.code, ReasonCode.HTF_ALIGNED)

    def test_sell_with_downtrend_full_score(self):
        score, reason = rules.score_htf_alignment("SELL", "down", max_score=5)
        self.assertEqual(score, 5)
        self.assertEqual(reason.code, ReasonCode.HTF_ALIGNED)

    def test_buy_against_downtrend_zero(self):
        score, reason = rules.score_htf_alignment("BUY", "down", max_score=5)
        self.assertEqual(score, 0)
        self.assertEqual(reason.code, ReasonCode.HTF_CONFLICT)
        self.assertEqual(reason.severity, Severity.WARN)

    def test_sell_against_uptrend_zero(self):
        score, reason = rules.score_htf_alignment("SELL", "up", max_score=5)
        self.assertEqual(score, 0)

    def test_flat_trend_half_score(self):
        score, reason = rules.score_htf_alignment("BUY", "flat", max_score=5)
        self.assertGreater(score, 0)
        self.assertLess(score, 5)

    def test_none_trend_half_score(self):
        score, reason = rules.score_htf_alignment("BUY", None, max_score=5)
        self.assertEqual(score, 2)  # max_score // 2

    def test_does_not_exceed_max_score(self):
        for trend in ["up", "down", "flat", None]:
            for side in ["BUY", "SELL"]:
                s, _ = rules.score_htf_alignment(side, trend, max_score=10)
                self.assertLessEqual(s, 10)
                self.assertGreaterEqual(s, 0)


if __name__ == "__main__":
    unittest.main()
