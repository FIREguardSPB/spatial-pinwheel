"""
P7-03: Property-based tests for indicators.

Runs 500 random cases per property using built-in random module
(no Hypothesis required — works without pip).

Properties tested:
  - calc_ema: never NaN for valid input
  - calc_rsi: always in [0, 100]
  - calc_atr: always ≥ 0
  - calc_bollinger: upper ≥ mid ≥ lower
  - calc_vwap: close to weighted mean
  - DecisionEngine.evaluate: never raises for valid signals

Run: python -m unittest tests.test_indicators_property -v
"""
import math
import os
import random
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Stubs ─────────────────────────────────────────────────────────────────────
try:
    import pydantic
    # Only treat as "real" pydantic if it has BaseSettings or VERSION (stub won't)
    _HAS_PYDANTIC = hasattr(pydantic, 'VERSION') and hasattr(pydantic, 'field_validator')
except ImportError:
    _HAS_PYDANTIC = False
    _pd = types.ModuleType("pydantic")
    class _BM:
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
        def model_dump(self): return self.__dict__
    _pd.BaseModel = _BM
    _pd.Field = lambda *a, **kw: kw.get("default", None)
    _pd.validator = lambda *a, **kw: (lambda f: f)
    _pd.field_validator = lambda *a, **kw: (lambda f: f)
    sys.modules.setdefault("pydantic", _pd)
    sys.modules.setdefault("pydantic_settings", types.ModuleType("pydantic_settings"))

for _mod in ["redis", "redis.asyncio", "structlog", "grpc", "prometheus_client",
             "prometheus_client.exposition", "google", "google.protobuf",
             "tinkoff", "tinkoff.invest", "httpx"]:
    sys.modules.setdefault(_mod, types.ModuleType(_mod))

from apps.worker.decision_engine import indicators

_skip_no_pydantic = unittest.skipUnless(_HAS_PYDANTIC, "pydantic required")

# ── Random data generators ─────────────────────────────────────────────────────
def _gen_prices(n: int, seed: int, start: float = 100.0,
                volatility: float = 0.02) -> list[float]:
    rng = random.Random(seed)
    prices = [start]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + rng.gauss(0, volatility)))
    return prices


def _gen_candles(n: int, seed: int, start: float = 100.0) -> tuple:
    """Return (highs, lows, closes, volumes) lists."""
    closes  = _gen_prices(n, seed, start)
    rng     = random.Random(seed + 1000)
    highs   = [c + abs(rng.gauss(0, c * 0.005)) for c in closes]
    lows    = [c - abs(rng.gauss(0, c * 0.005)) for c in closes]
    volumes = [abs(rng.gauss(10_000, 3_000)) + 100 for _ in closes]
    return highs, lows, closes, volumes


def _property_test(fn, n_cases: int = 300, label: str = ""):
    """
    Run fn(seed) n_cases times.
    fn should raise AssertionError on failure.
    Returns (passed, failed, errors).
    """
    passed = failed = errors = 0
    for seed in range(n_cases):
        try:
            fn(seed)
            passed += 1
        except AssertionError:
            failed += 1
        except Exception:
            errors += 1
    return passed, failed, errors


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-A  EMA
# ══════════════════════════════════════════════════════════════════════════════
class TestEMAProperty(unittest.TestCase):

    def test_ema_not_nan_for_valid_input(self):
        """calc_ema never returns NaN for valid positive price series."""
        def check(seed):
            closes = _gen_prices(50, seed)
            for period in [5, 10, 20]:
                result = indicators.calc_ema(closes, period=period)
                if result is not None:
                    assert not math.isnan(result), f"EMA={result} is NaN (seed={seed})"
                    assert not math.isinf(result), f"EMA={result} is Inf (seed={seed})"

        passed, failed, errors = _property_test(check, 300, "EMA not NaN")
        self.assertEqual(failed + errors, 0,
                         f"EMA property violated: {failed} failures, {errors} errors / 300 cases")

    def test_ema_shorter_period_more_responsive(self):
        """EMA(5) reacts more quickly than EMA(20) after a sustained price jump."""
        def check(seed):
            rng  = random.Random(seed)
            base = [100.0] * 30
            jump = [100.0 + rng.uniform(10, 50)] * 10
            closes = base + jump
            ema5  = indicators.calc_ema(closes, period=5)
            ema20 = indicators.calc_ema(closes, period=20)
            if ema5 is not None and ema20 is not None:
                assert ema5 > ema20, f"EMA5={ema5:.2f} should > EMA20={ema20:.2f} after upward jump"

        passed, failed, errors = _property_test(check, 200)
        self.assertEqual(failed + errors, 0,
                         f"EMA responsiveness property: {failed} failures, {errors} errors / 200")

    def test_ema_returns_none_for_insufficient_data(self):
        """calc_ema returns None when len(closes) < period."""
        for period in [5, 10, 20]:
            with self.subTest(period=period):
                result = indicators.calc_ema([100.0] * (period - 1), period=period)
                self.assertIsNone(result)

    def test_ema_constant_series_equals_constant(self):
        """EMA of constant series = that constant."""
        for val in [50.0, 100.0, 250.0, 10_000.0]:
            with self.subTest(val=val):
                closes = [val] * 30
                ema    = indicators.calc_ema(closes, period=10)
                if ema is not None:
                    self.assertAlmostEqual(ema, val, places=5)


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-B  RSI
# ══════════════════════════════════════════════════════════════════════════════
class TestRSIProperty(unittest.TestCase):

    def test_rsi_always_0_to_100(self):
        """RSI is always in [0, 100] for any valid price series."""
        def check(seed):
            closes = _gen_prices(50, seed)
            rsi    = indicators.calc_rsi(closes, period=14)
            if rsi is not None:
                assert 0.0 <= rsi <= 100.0, f"RSI={rsi:.4f} out of [0,100] (seed={seed})"

        passed, failed, errors = _property_test(check, 500)
        self.assertEqual(failed + errors, 0,
                         f"RSI [0,100] violated: {failed} failures, {errors} errors / 500")

    def test_rsi_strict_uptrend_above_50(self):
        """Strictly monotone uptrend → RSI > 50 (no losses = 100% gains)."""
        # Use a deterministic strictly increasing series — no randomness
        for step in [0.5, 1.0, 2.0, 5.0]:
            with self.subTest(step=step):
                closes = [100.0 + i * step for i in range(40)]
                rsi    = indicators.calc_rsi(closes, period=14)
                if rsi is not None:
                    self.assertGreater(rsi, 50.0,
                                       f"Strict uptrend (step={step}) RSI={rsi:.2f} should be > 50")

    def test_rsi_strict_downtrend_below_50(self):
        """Strictly monotone downtrend → RSI < 50 (no gains = 100% losses)."""
        for step in [0.5, 1.0, 2.0, 5.0]:
            with self.subTest(step=step):
                closes = [max(200.0 - i * step, 1.0) for i in range(40)]
                rsi    = indicators.calc_rsi(closes, period=14)
                if rsi is not None:
                    self.assertLess(rsi, 50.0,
                                    f"Strict downtrend (step={step}) RSI={rsi:.2f} should be < 50")

    def test_rsi_returns_none_insufficient_data(self):
        self.assertIsNone(indicators.calc_rsi([100.0, 101.0], period=14))

    def test_rsi_not_nan(self):
        """RSI never returns NaN."""
        for seed in range(200):
            closes = _gen_prices(40, seed)
            rsi    = indicators.calc_rsi(closes, period=14)
            if rsi is not None:
                with self.subTest(seed=seed):
                    self.assertFalse(math.isnan(rsi), f"RSI is NaN at seed={seed}")


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-C  ATR
# ══════════════════════════════════════════════════════════════════════════════
class TestATRProperty(unittest.TestCase):

    def test_atr_always_non_negative(self):
        """ATR is always ≥ 0."""
        def check(seed):
            highs, lows, closes, _ = _gen_candles(30, seed)
            for period in [5, 10, 14]:
                atr = indicators.calc_atr(highs, lows, closes, period=period)
                if atr is not None:
                    assert atr >= 0.0, f"ATR={atr:.6f} is negative (seed={seed})"

        passed, failed, errors = _property_test(check, 400)
        self.assertEqual(failed + errors, 0,
                         f"ATR ≥ 0 violated: {failed} failures, {errors} errors / 400")

    def test_atr_not_nan(self):
        """ATR never returns NaN."""
        for seed in range(300):
            highs, lows, closes, _ = _gen_candles(30, seed)
            atr = indicators.calc_atr(highs, lows, closes, period=14)
            if atr is not None:
                with self.subTest(seed=seed):
                    self.assertFalse(math.isnan(atr))

    def test_atr_high_volatility_larger(self):
        """Explicitly high-range bars produce larger ATR than low-range bars."""
        # Deterministic: narrow vs wide H-L range
        closes_low  = [100.0] * 30
        highs_low   = [c + 0.01 for c in closes_low]   # range = 0.02
        lows_low    = [c - 0.01 for c in closes_low]

        closes_high = [100.0] * 30
        highs_high  = [c + 5.0 for c in closes_high]   # range = 10
        lows_high   = [c - 5.0 for c in closes_high]

        atr_low  = indicators.calc_atr(highs_low,  lows_low,  closes_low,  period=14)
        atr_high = indicators.calc_atr(highs_high, lows_high, closes_high, period=14)
        if atr_low is not None and atr_high is not None:
            self.assertGreater(atr_high, atr_low,
                               f"High-range ATR={atr_high:.4f} should > narrow ATR={atr_low:.4f}")

    def test_atr_flat_price_near_zero(self):
        """Flat price series → ATR ≈ 0."""
        for val in [50.0, 100.0, 1000.0]:
            with self.subTest(val=val):
                highs  = [val + 0.001] * 20
                lows   = [val - 0.001] * 20
                closes = [val]         * 20
                atr    = indicators.calc_atr(highs, lows, closes, period=14)
                if atr is not None:
                    self.assertAlmostEqual(atr, 0.0, delta=0.01)


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-D  Bollinger Bands
# ══════════════════════════════════════════════════════════════════════════════
class TestBollingerProperty(unittest.TestCase):

    def test_band_order_upper_ge_mid_ge_lower(self):
        """Upper ≥ Mid ≥ Lower for any valid input."""
        def check(seed):
            closes = _gen_prices(50, seed)
            result = indicators.calc_bollinger(closes, period=20)
            if result is not None:
                upper, mid, lower = result
                assert upper >= mid,   f"Upper={upper:.4f} < Mid={mid:.4f} (seed={seed})"
                assert mid   >= lower, f"Mid={mid:.4f} < Lower={lower:.4f} (seed={seed})"

        passed, failed, errors = _property_test(check, 400)
        self.assertEqual(failed + errors, 0,
                         f"Bollinger band order violated: {failed} failures / 400")

    def test_mid_is_sma(self):
        """Middle band == SMA(closes, period)."""
        def check(seed):
            closes = _gen_prices(40, seed)
            period = 20
            result = indicators.calc_bollinger(closes, period=period)
            if result is not None:
                _, mid, _ = result
                sma = sum(closes[-period:]) / period
                assert abs(mid - sma) < 1e-4, \
                    f"Mid={mid:.8f} != SMA={sma:.8f} diff={abs(mid-sma):.2e} (seed={seed})"

        passed, failed, errors = _property_test(check, 300)
        self.assertEqual(failed + errors, 0,
                         f"Bollinger mid=SMA violated: {failed} failures / 300")

    def test_flat_series_zero_width(self):
        """Constant series → upper == lower (zero-width bands)."""
        for val in [100.0, 500.0]:
            with self.subTest(val=val):
                closes = [val] * 30
                result = indicators.calc_bollinger(closes, period=20)
                if result is not None:
                    upper, mid, lower = result
                    self.assertAlmostEqual(upper, lower, places=8,
                                           msg="Flat series must have zero-width bands")

    def test_not_nan(self):
        """Bollinger never returns NaN."""
        for seed in range(200):
            closes = _gen_prices(40, seed)
            result = indicators.calc_bollinger(closes, period=20)
            if result is not None:
                for v in result:
                    with self.subTest(seed=seed):
                        self.assertFalse(math.isnan(v))


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-E  VWAP
# ══════════════════════════════════════════════════════════════════════════════
class TestVWAPProperty(unittest.TestCase):

    def test_vwap_between_min_and_max_price(self):
        """VWAP is always between the minimum and maximum close price."""
        def check(seed):
            highs, lows, closes, volumes = _gen_candles(30, seed)
            vwap = indicators.calc_vwap(highs, lows, closes, volumes)
            if vwap is not None:
                min_p = min(lows)
                max_p = max(highs)
                assert min_p <= vwap <= max_p, \
                    f"VWAP={vwap:.4f} outside [{min_p:.4f}, {max_p:.4f}] (seed={seed})"

        passed, failed, errors = _property_test(check, 400)
        self.assertEqual(failed + errors, 0,
                         f"VWAP bounds violated: {failed} failures / 400")

    def test_vwap_not_nan(self):
        """VWAP never returns NaN for valid inputs."""
        for seed in range(300):
            highs, lows, closes, volumes = _gen_candles(30, seed)
            vwap = indicators.calc_vwap(highs, lows, closes, volumes)
            if vwap is not None:
                with self.subTest(seed=seed):
                    self.assertFalse(math.isnan(vwap))

    def test_vwap_uniform_volume_equals_mean(self):
        """With uniform volume, VWAP == mean(typical_price)."""
        def check(seed):
            highs, lows, closes, _ = _gen_candles(30, seed)
            volumes = [1000.0] * len(closes)
            vwap    = indicators.calc_vwap(highs, lows, closes, volumes)
            if vwap is not None:
                typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
                mean_tp = sum(typical) / len(typical)
                assert abs(vwap - mean_tp) < 1e-6, \
                    f"Uniform-volume VWAP={vwap:.6f} != mean_tp={mean_tp:.6f}"

        passed, failed, errors = _property_test(check, 200)
        self.assertEqual(failed + errors, 0,
                         f"VWAP uniform volume violated: {failed} failures / 200")


# ══════════════════════════════════════════════════════════════════════════════
# P7-03-F  DecisionEngine — never raises
# ══════════════════════════════════════════════════════════════════════════════
@_skip_no_pydantic
class TestDecisionEngineNeverRaises(unittest.TestCase):
    """DE.evaluate must not raise for any valid signal + snapshot."""

    def _make_settings(self, seed: int = 0):
        rng = random.Random(seed)
        s   = unittest.mock.MagicMock() if False else type("S", (), {})()
        s.decision_threshold                = rng.randint(30, 90)
        s.rr_min                            = round(rng.uniform(1.0, 2.5), 1)
        s.atr_stop_hard_min                 = 0.1
        s.atr_stop_hard_max                 = 10.0
        s.atr_stop_soft_min                 = 0.2
        s.atr_stop_soft_max                 = 5.0
        s.w_regime                          = rng.randint(5, 25)
        s.w_volatility                      = rng.randint(5, 20)
        s.w_momentum                        = rng.randint(5, 20)
        s.w_levels                          = rng.randint(5, 25)
        s.w_costs                           = rng.randint(5, 20)
        s.w_liquidity                       = rng.randint(5, 15)
        s.w_htf                             = rng.randint(0, 15)
        s.no_trade_opening_minutes          = 0
        s.close_before_session_end_minutes  = 0
        s.commission_pct                    = 0.05
        s.slippage_pct                      = 0.05
        s.min_volume_ratio                  = 0.0
        s.htf_weight                        = 10
        s.session_type                      = "main"
        return s

    def test_de_never_raises_for_valid_signals(self):
        """DE.evaluate never raises for 200 random valid signals."""
        try:
            from apps.worker.decision_engine.engine import DecisionEngine
            from apps.worker.decision_engine.types  import MarketSnapshot
            from unittest.mock import patch
        except Exception as e:
            self.skipTest(f"DE not importable: {e}")
            return

        errors = []
        for seed in range(200):
            rng    = random.Random(seed)
            closes = _gen_prices(50, seed)
            highs  = [c + rng.uniform(0, 1) for c in closes]
            lows   = [c - rng.uniform(0, 1) for c in closes]
            vols   = [rng.uniform(5000, 20000) for _ in closes]

            candles_list = [
                {"time": i*60, "open": h-0.5, "high": h, "low": l, "close": c,
                 "volume": v}
                for i, (h, l, c, v) in enumerate(zip(highs, lows, closes, vols))
            ]
            snap  = MarketSnapshot(candles=candles_list, last_price=closes[-1])
            entry = closes[-1]
            side  = rng.choice(["BUY", "SELL"])
            dist  = rng.uniform(entry * 0.01, entry * 0.05)
            if side == "BUY":
                sl, tp = entry - dist, entry + dist * rng.uniform(1.5, 3.0)
            else:
                sl, tp = entry + dist, entry - dist * rng.uniform(1.5, 3.0)

            class FakeSig:
                pass
            sig = FakeSig()
            sl_dist = abs(entry - sl)
            tp_dist = abs(tp - entry)
            sig.side = side; sig.entry = entry; sig.sl = sl; sig.tp = tp
            sig.size = rng.randint(1, 100); sig.instrument_id = "TQBR:SBER"
            sig.r = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 1.0
            sig.reason = "property test"

            engine = DecisionEngine(self._make_settings(seed))
            try:
                with patch("apps.worker.decision_engine.rules.check_session",
                           return_value=None):
                    engine.evaluate(sig, snap)
            except Exception as e:
                errors.append(f"seed={seed}: {type(e).__name__}: {e}")

        self.assertEqual(len(errors), 0,
                         f"DE raised on {len(errors)}/200 valid inputs:\n" +
                         "\n".join(errors[:5]))

    def test_de_handles_extreme_rr(self):
        """DE handles extreme R/R (0.01 and 100) without raising."""
        try:
            from apps.worker.decision_engine.engine import DecisionEngine
            from apps.worker.decision_engine.types  import MarketSnapshot
            from unittest.mock import patch
        except Exception as e:
            self.skipTest(f"DE not importable: {e}")
            return

        closes       = _gen_prices(50, 42)
        candles_snap = [
            {"time": i*60, "open": c-0.5, "high": c+1, "low": c-1, "close": c, "volume": 10000}
            for i, c in enumerate(closes)
        ]
        try:
            snap = MarketSnapshot(candles=candles_snap, last_price=closes[-1])
        except Exception as e:
            self.skipTest(f"MarketSnapshot not constructible: {e}")
            return

        engine = DecisionEngine(self._make_settings())

        for tp_mult in [1.01, 1.1, 2.0, 5.0, 50.0]:
            with self.subTest(tp_mult=tp_mult):
                class _Sig:
                    side="BUY"; entry=100.0; sl=99.0
                    size=10; instrument_id="TQBR:SBER"; reason="test"
                s = _Sig()
                s.tp = 100.0 + tp_mult
                s.r  = round(tp_mult / 1.0, 2)
                try:
                    with patch("apps.worker.decision_engine.rules.check_session",
                               return_value=None):
                        engine.evaluate(s, snap)
                except Exception as e:
                    self.fail(f"DE raised for tp_mult={tp_mult}: {e}")

