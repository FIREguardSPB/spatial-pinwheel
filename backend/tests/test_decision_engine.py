import unittest
from decimal import Decimal
from unittest.mock import patch
from apps.worker.decision_engine import indicators, rules
from apps.worker.decision_engine.types import ReasonCode, Reason, Severity
from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import MarketSnapshot, Decision
from core.storage.models import Settings

# --- Engine Tests ---


class MockSignal:
    def __init__(self, side="BUY", entry=100, sl=99, tp=110, size=1, r=2.0):
        self.side = side
        self.entry = Decimal(entry)
        self.sl = Decimal(sl)
        self.tp = Decimal(tp)
        self.size = Decimal(size)
        self.r = Decimal(r)
        self.meta = {}


class TestDecisionEngine(unittest.TestCase):

    # --- Indicator Tests ---

    def test_indicators_basic(self):
        prices = [float(i) for i in range(100)]  # 0..99

        # EMA
        ema = indicators.calc_ema(prices, 10)
        self.assertIsNotNone(ema)
        self.assertGreater(ema, 0)

        # RSI
        # Monotonic up -> RSI should be 100 or close
        rsi = indicators.calc_rsi(prices, 14)
        self.assertGreater(rsi, 90)

        # ATR
        highs = [p + 1 for p in prices]
        lows = [p - 1 for p in prices]
        atr = indicators.calc_atr(highs, lows, prices, 14)
        self.assertGreater(atr, 0)

        # MACD
        macd = indicators.calc_macd(prices)
        self.assertIsNotNone(macd)
        self.assertEqual(len(macd), 3)  # line, signal, hist

    # --- Rule Tests ---

    def test_check_invalid_signal(self):
        # Invalid SL (BUY)
        r = rules.check_invalid_signal("BUY", Decimal(100), Decimal(101), Decimal(110), Decimal(1))
        self.assertIsNotNone(r)
        self.assertEqual(r.code, ReasonCode.INVALID_SIGNAL)

        # Valid
        r = rules.check_invalid_signal("BUY", Decimal(100), Decimal(99), Decimal(110), Decimal(1))
        self.assertIsNone(r)

    def test_check_risk_reward(self):
        # R = 1.0 (Target 1.5)
        r = rules.check_risk_reward(1.0, 1.5)
        self.assertIsNotNone(r)
        self.assertEqual(r.code, ReasonCode.RR_TOO_LOW)  # Confirms P0.1 Fix

        # R = 2.0
        r = rules.check_risk_reward(2.0, 1.5)
        self.assertIsNone(r)

    def test_score_levels_logic(self):
        # BUY. Entry 100. TP 110. Dist 10.
        # Level at 105. Dist 5.
        # Ratio = 0.5 -> Level too close -> Low Score
        s, reasons = rules.score_levels(100.0, 110.0, 105.0, "BUY")
        self.assertLess(s, 20)
        self.assertEqual(reasons[0].code, ReasonCode.LEVEL_TOO_CLOSE)

        # Level at 108. Dist 8. Ratio 0.8 -> Good
        s, reasons = rules.score_levels(100.0, 110.0, 108.0, "BUY")
        # P0.6 Update: Score is now strictly linear. 0.8 * 20 = 16.
        self.assertEqual(s, 16)
        # Reason should be OK because ratio >= 0.7
        self.assertEqual(reasons[0].code, ReasonCode.LEVEL_CLEARANCE_OK)

        # No level (None) -> Neutral Score (10) + LEVEL_UNKNOWN (P0 Fix)
        s, reasons = rules.score_levels(100.0, 110.0, None, "BUY")
        self.assertEqual(s, 10)
        self.assertEqual(reasons[0].code, ReasonCode.LEVEL_UNKNOWN)

    def test_engine_evaluate_flow(self):
        settings = Settings()
        # Mock defaults manually as SQLA doesn't apply them on plain init
        settings.decision_threshold = 70
        settings.rr_min = 1.5
        settings.atr_stop_hard_min = 0.3
        settings.atr_stop_hard_max = 5.0
        settings.atr_stop_soft_min = 0.6
        settings.atr_stop_soft_max = 2.5
        settings.fees_bps = 3
        settings.slippage_bps = 5
        # P7 Weights
        settings.w_regime = 20
        settings.w_volatility = 15
        settings.w_momentum = 15
        settings.w_levels = 20
        settings.w_costs = 15
        settings.w_liquidity = 5

        engine = DecisionEngine(settings)

        # Create Snapshot with 60 candles (enough data)
        candles = []
        base_price = 1000.0
        for i in range(60):
            candles.append(
                {
                    "time": 1000 + i * 60,
                    "open": base_price,
                    "high": base_price + 5,
                    "low": base_price - 5,
                    "close": base_price + (1 if i % 2 == 0 else -1),  # Choppy
                    "volume": 100,
                }
            )

        snapshot = MarketSnapshot(candles=candles, last_price=Decimal(base_price))

        # 1. Test Low R Reject
        sig_bad_r = MockSignal(entry=1000, sl=999, tp=1001, r=1.0)  # R=1
        res = engine.evaluate(sig_bad_r, snapshot)
        self.assertEqual(res.decision, Decision.REJECT)
        self.assertTrue(any(r.code == ReasonCode.RR_TOO_LOW for r in res.reasons))

        # 2. Test Good Signal (Stub)
        sig_ok = MockSignal(entry=1000, sl=990, tp=1020, r=2.0)
        res = engine.evaluate(sig_ok, snapshot)
        self.assertIn(res.decision, [Decision.TAKE, Decision.SKIP])
        self.assertGreaterEqual(res.score, 0)
        # Check metrics populated
        self.assertIn("ema50", res.metrics)
        self.assertIn("macd_hist", res.metrics)
        # P0 Verification: nearest_level should be None (not found in small window)
        # Case: Entry 2000 (above all highs) -> No Resistance -> None
        sig_ath = MockSignal(entry=2000, sl=1990, tp=2020, r=2.0)
        res_ath = engine.evaluate(sig_ath, snapshot)
        self.assertIsNone(res_ath.metrics["nearest_level"])

        # Case: Entry 1000 -> Resistance found
        self.assertIsNotNone(res.metrics["nearest_level"])

    def test_higher_tf_signal_does_not_hard_fail_at_43_candles(self):
        settings = Settings()
        settings.decision_threshold = 40
        settings.rr_min = 1.1
        settings.atr_stop_hard_min = 0.1
        settings.atr_stop_hard_max = 10.0
        settings.atr_stop_soft_min = 0.1
        settings.atr_stop_soft_max = 5.0
        settings.fees_bps = 3
        settings.slippage_bps = 5
        settings.w_regime = 20
        settings.w_volatility = 15
        settings.w_momentum = 15
        settings.w_levels = 20
        settings.w_costs = 15
        settings.w_liquidity = 5
        settings.no_trade_opening_minutes = 0
        settings.close_before_session_end_minutes = 0
        settings.trading_session = 'all'

        engine = DecisionEngine(settings)
        sig = MockSignal(side='BUY', entry=100, sl=99, tp=103, size=10, r=2.0)
        sig.meta = {'thesis_timeframe': '15m', 'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}
        candles = []
        for i in range(43):
            close = 100.0 + i * 0.12
            candles.append({
                'time': 1000 + i * 900,
                'open': close - 0.08,
                'high': close + 0.2,
                'low': close - 0.2,
                'close': close,
                'volume': 1000,
            })
        snapshot = MarketSnapshot(candles=candles, last_price=Decimal('105'))

        res = engine.evaluate(sig, snapshot)

        self.assertFalse(any(r.code == ReasonCode.NO_MARKET_DATA for r in res.reasons))

    def test_requested_15m_signal_does_not_hard_fail_at_39_candles(self):
        settings = Settings()
        settings.decision_threshold = 40
        settings.rr_min = 1.1
        settings.atr_stop_hard_min = 0.1
        settings.atr_stop_hard_max = 10.0
        settings.atr_stop_soft_min = 0.1
        settings.atr_stop_soft_max = 5.0
        settings.fees_bps = 3
        settings.slippage_bps = 5
        settings.w_regime = 20
        settings.w_volatility = 15
        settings.w_momentum = 15
        settings.w_levels = 20
        settings.w_costs = 15
        settings.w_liquidity = 5
        settings.no_trade_opening_minutes = 0
        settings.close_before_session_end_minutes = 0
        settings.trading_session = 'all'

        engine = DecisionEngine(settings)
        sig = MockSignal(side='BUY', entry=100, sl=99, tp=103, size=10, r=2.0)
        sig.meta = {'thesis_timeframe': '15m', 'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}
        candles = []
        for i in range(39):
            close = 100.0 + i * 0.12
            candles.append({
                'time': 1000 + i * 900,
                'open': close - 0.08,
                'high': close + 0.2,
                'low': close - 0.2,
                'close': close,
                'volume': 1000,
            })
        snapshot = MarketSnapshot(candles=candles, last_price=Decimal('104.5'))

        res = engine.evaluate(sig, snapshot)

        self.assertFalse(any(r.code == ReasonCode.NO_MARKET_DATA for r in res.reasons))

    def test_requested_15m_signal_is_not_hard_rejected_only_for_low_volume(self):
        settings = Settings()
        settings.decision_threshold = 40
        settings.rr_min = 1.1
        settings.atr_stop_hard_min = 0.1
        settings.atr_stop_hard_max = 10.0
        settings.atr_stop_soft_min = 0.1
        settings.atr_stop_soft_max = 5.0
        settings.fees_bps = 3
        settings.slippage_bps = 5
        settings.w_regime = 20
        settings.w_volatility = 15
        settings.w_momentum = 15
        settings.w_levels = 20
        settings.w_costs = 15
        settings.w_liquidity = 5
        settings.no_trade_opening_minutes = 0
        settings.close_before_session_end_minutes = 0
        settings.trading_session = 'all'

        engine = DecisionEngine(settings)
        sig = MockSignal(side='SELL', entry=100, sl=101, tp=97, size=10, r=2.0)
        sig.meta = {'thesis_timeframe': '15m', 'timeframe_selection_reason': 'requested', 'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}
        candles = []
        for i in range(60):
            close = 100.0 - i * 0.08
            candles.append({'time': 1000 + i * 900, 'open': close + 0.05, 'high': close + 0.2, 'low': close - 0.2, 'close': close, 'volume': 1000})
        snapshot = MarketSnapshot(candles=candles, last_price=Decimal('95.5'))

        with patch('apps.worker.decision_engine.rules.score_volume', return_value=(0, Reason(code=ReasonCode.VOLUME_LOW, severity=Severity.BLOCK, msg='Volume too low'))):
            res = engine.evaluate(sig, snapshot)

        self.assertFalse(any(r.code == ReasonCode.VOLUME_LOW and r.severity == Severity.BLOCK for r in res.reasons))

    def test_score_normalization(self):
        # Test that score is normalized to 0-100 even if weights sum != 100
        settings = Settings()
        # Weights sum = 60 (20+20+20)
        settings.w_regime = 20
        settings.w_volatility = 20
        settings.w_momentum = 20
        settings.w_levels = 0
        settings.w_costs = 0
        settings.w_liquidity = 0

        settings.atr_stop_hard_min = 0.0  # Prevent hard reject due to mock data
        settings.decision_threshold = 50  # 50%

        engine = DecisionEngine(settings)

        # Create snapshot...
        # Make price wavy to ensure indicators (RSI) are valid
        candles = [
            {"close": 100 + (i % 5), "high": 110, "low": 90, "time": i, "volume": 100}
            for i in range(100)
        ]
        snapshot = MarketSnapshot(candles=candles, last_price=Decimal(100))

        # Perfect Signal (should get max score from active weights)
        sig = MockSignal(entry=100, sl=99, tp=110)
        res = engine.evaluate(sig, snapshot)

        self.assertLessEqual(res.score_pct, 100)
        self.assertEqual(res.score_max, 60)
        # If it got e.g. 40 points raw, pct should be 67.
        if res.score_raw > 0:
            self.assertEqual(res.score_pct, int(round(res.score_raw / 60 * 100)))

    def test_score_levels_clamp(self):
        # Test that ratio > 1.0 is clamped
        # entry 100, tp 110 (dist 10). Level at 120 (dist 20).
        # ratio = 2.0. Should be clamped to 1.0.
        # Score = max_score * 1.0
        s, reasons = rules.score_levels(100.0, 110.0, 120.0, "BUY", max_score=20)
        self.assertEqual(s, 20)  # Not 40



    # ── P5-01: New indicator tests ──────────────────────────────────────────────

    def test_bollinger_bands_basic(self):
        closes = [float(100 + (i % 5)) for i in range(30)]
        bb = indicators.calc_bollinger(closes, period=20)
        self.assertIsNotNone(bb)
        upper, middle, lower = bb
        self.assertGreater(upper, middle)
        self.assertGreater(middle, lower)

    def test_stochastic_range(self):
        import random; random.seed(1)
        closes = [100 + random.uniform(-3, 3) for _ in range(30)]
        highs  = [c + 1 for c in closes]
        lows   = [c - 1 for c in closes]
        result = indicators.calc_stochastic(highs, lows, closes)
        self.assertIsNotNone(result)
        k, d = result
        self.assertGreaterEqual(k, 0); self.assertLessEqual(k, 100)

    def test_volume_ratio_constant(self):
        vols = [100.0] * 25
        ratio = indicators.calc_volume_ratio(vols, period=20)
        self.assertAlmostEqual(ratio, 1.0, places=3)

    def test_vwap_equal_volume(self):
        closes = [10.0, 20.0, 30.0]
        highs  = [11.0, 21.0, 31.0]
        lows   = [ 9.0, 19.0, 29.0]
        vols   = [100.0] * 3
        vwap = indicators.calc_vwap(highs, lows, closes, vols)
        expected = sum((h+l+c)/3 for h,l,c in zip(highs,lows,closes)) / 3
        self.assertAlmostEqual(vwap, expected, places=4)

    # ── P5-02: Volume score test ────────────────────────────────────────────────

    def test_volume_score_block_on_low_volume(self):
        score, reason = rules.score_volume(0.2, max_score=10)
        self.assertEqual(score, 0)
        from apps.worker.decision_engine.types import Severity
        self.assertEqual(reason.severity, Severity.BLOCK)

    # ── P5-04: HTF alignment ────────────────────────────────────────────────────

    def test_htf_alignment_buy_uptrend_full(self):
        score, reason = rules.score_htf_alignment("BUY", "up", max_score=5)
        self.assertEqual(score, 5)

    def test_htf_alignment_conflict_zero(self):
        score, reason = rules.score_htf_alignment("BUY", "down", max_score=5)
        self.assertEqual(score, 0)

if __name__ == "__main__":
    unittest.main()
