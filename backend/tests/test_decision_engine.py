import unittest
from decimal import Decimal
from apps.worker.decision_engine import indicators, rules
from apps.worker.decision_engine.types import ReasonCode, Severity
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

class TestDecisionEngine(unittest.TestCase):

    # --- Indicator Tests ---

    def test_indicators_basic(self):
        prices = [float(i) for i in range(100)] # 0..99
        
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
        self.assertEqual(len(macd), 3) # line, signal, hist

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
        self.assertEqual(r.code, ReasonCode.RR_TOO_LOW) # Confirms P0.1 Fix
        
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
            candles.append({
                "time": 1000 + i*60,
                "open": base_price,
                "high": base_price + 5,
                "low": base_price - 5,
                "close": base_price + (1 if i % 2 == 0 else -1), # Choppy
                "volume": 100
            })
        
        snapshot = MarketSnapshot(
            candles=candles,
            last_price=Decimal(base_price)
        )
        
        # 1. Test Low R Reject
        sig_bad_r = MockSignal(entry=1000, sl=999, tp=1001, r=1.0) # R=1
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
        
        settings.atr_stop_hard_min = 0.0 # Prevent hard reject due to mock data
        settings.decision_threshold = 50 # 50%
        
        engine = DecisionEngine(settings)
        
        # Create snapshot...
        # Make price wavy to ensure indicators (RSI) are valid
        candles = [{"close": 100 + (i%5), "high": 110, "low": 90, "time": i, "volume": 100} for i in range(100)]
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
        self.assertEqual(s, 20) # Not 40

if __name__ == '__main__':
    unittest.main()
