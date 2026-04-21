from decimal import Decimal
from unittest.mock import patch

from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.rules import analyze_costs, score_costs, score_volume
from apps.worker.decision_engine.types import Decision, MarketSnapshot, ReasonCode
from core.storage.models import Settings


class MockSignal:
    def __init__(self, side='BUY', entry=100.0, sl=99.0, tp=110.0, size=1.0, r=2.0):
        self.side = side
        self.entry = Decimal(str(entry))
        self.sl = Decimal(str(sl))
        self.tp = Decimal(str(tp))
        self.size = Decimal(str(size))
        self.r = Decimal(str(r))


def _settings() -> Settings:
    s = Settings()
    s.decision_threshold = 40
    s.rr_min = 1.5
    s.atr_stop_hard_min = 0.3
    s.atr_stop_hard_max = 5.0
    s.atr_stop_soft_min = 0.6
    s.atr_stop_soft_max = 2.5
    s.fees_bps = 3
    s.slippage_bps = 5
    s.w_regime = 20
    s.w_volatility = 15
    s.w_momentum = 15
    s.w_levels = 20
    s.w_costs = 15
    s.w_volume = 10
    s.no_trade_opening_minutes = 0
    s.close_before_session_end_minutes = 0
    s.trading_session = 'all'
    return s


def _snapshot_with_far_level() -> MarketSnapshot:
    candles = []
    for i in range(60):
        close = 100.0 + (0.05 if i % 2 == 0 else -0.03)
        high = 100.6
        low = 99.4
        if i == 10:
            high = 111.0  # level only visible in a wider lookback window
        candles.append({
            'time': 1_700_000_000 + i * 60,
            'open': close - 0.1,
            'high': high,
            'low': low,
            'close': close,
            'volume': 1_000,
        })
    return MarketSnapshot(candles=candles, last_price=Decimal(str(candles[-1]['close'])))


def test_positive_but_subunit_net_rr_is_not_labeled_negative():
    score, reasons, breakdown = score_costs(100.0, 99.0, 101.1, fees_bps=3, slippage_bps=5, max_score=15)
    assert score > 0
    assert breakdown['net_rr'] is not None and 0 < breakdown['net_rr'] < 1
    assert any('Borderline after costs' in r.msg for r in reasons)
    assert not any('Non-positive after costs' in r.msg for r in reasons)


def test_take_survives_when_net_rr_is_borderline_but_positive():
    engine = DecisionEngine(_settings())
    snapshot = _snapshot_with_far_level()
    sig = MockSignal(entry=100.0, sl=99.0, tp=101.1, r=2.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, snapshot)
    assert result.metrics['net_rr'] is not None and 0 < result.metrics['net_rr'] < 1
    assert result.metrics['net_rr'] >= 0.75
    assert result.decision == Decision.TAKE
    assert result.metrics.get('decision_adjustment') is None


def test_take_is_capped_to_skip_when_net_rr_is_too_thin_even_if_positive():
    engine = DecisionEngine(_settings())
    snapshot = _snapshot_with_far_level()
    sig = MockSignal(entry=100.0, sl=99.0, tp=100.9, r=2.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, snapshot)
    assert result.metrics['net_rr'] is not None and 0 < result.metrics['net_rr'] < 0.75
    assert result.decision != Decision.TAKE
    assert result.metrics.get('decision_adjustment') == 'capped_take_low_net_rr'


def test_non_positive_net_rr_blocks_execution():
    engine = DecisionEngine(_settings())
    snapshot = _snapshot_with_far_level()
    sig = MockSignal(entry=100.0, sl=99.0, tp=100.1, r=2.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, snapshot)
    assert result.decision == Decision.REJECT
    assert result.metrics.get('decision_adjustment') == 'blocked_non_positive_net_rr'
    assert any(r.code == ReasonCode.COSTS_TOO_HIGH and 'blocks execution' in r.msg for r in result.reasons)


def test_wider_lookback_can_find_level_outside_21_bars():
    engine = DecisionEngine(_settings())
    snapshot = _snapshot_with_far_level()
    sig = MockSignal(entry=105.0, sl=104.0, tp=110.0, r=2.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, snapshot)
    assert result.metrics['level_lookback_bars'] == 55
    assert result.metrics['nearest_level'] == 111.0
    assert result.metrics['level_source'] in {'strict', 'tolerance'}


def test_volume_spike_threshold_is_less_noisy_than_before():
    score, reason = score_volume(7.5, max_score=10)
    assert score == 10
    assert reason.code == ReasonCode.VOLUME_OK
    score, reason = score_volume(8.5, max_score=10)
    assert score == 5
    assert reason.code == ReasonCode.VOLUME_ANOMALOUS
