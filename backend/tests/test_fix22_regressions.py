from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import MarketSnapshot, Decision
from core.storage.models import Settings
import core.utils.session as session_mod


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
    s.decision_threshold = 70
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


def _snapshot() -> MarketSnapshot:
    candles = []
    base = 100.0
    for i in range(60):
        close = base + (0.2 if i % 2 == 0 else -0.1)
        candles.append({
            'time': 1_700_000_000 + i * 60,
            'open': close - 0.1,
            'high': close + 0.6,
            'low': close - 0.6,
            'close': close,
            'volume': 1_000,
        })
    return MarketSnapshot(candles=candles, last_price=Decimal(str(candles[-1]['close'])))


def test_buy_signal_above_recent_high_has_no_fake_zero_ratio_level():
    engine = DecisionEngine(_settings())
    snapshot = _snapshot()
    sig = MockSignal(entry=200.0, sl=199.0, tp=205.0, r=5.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, snapshot)
    assert result.metrics['nearest_level'] is None
    assert result.metrics['level_clearance_ratio'] is None
    assert not any('0.00 of TP path' in r.msg for r in result.reasons)


def test_morning_session_is_open_for_default_all_mode():
    fake_now = datetime(2026, 3, 16, 5, 0, tzinfo=timezone.utc)  # 08:00 MSK
    with patch.object(session_mod, '_msk_now', return_value=fake_now.astimezone(timezone.utc).replace(tzinfo=timezone.utc) + session_mod._MSK_OFFSET):
        assert session_mod.is_trading_session('all') is True
        assert session_mod.is_trading_session('main') is True
        assert session_mod.is_trading_session('main_only') is False


def test_minutes_until_end_uses_full_day_for_all_mode():
    fake_now = datetime(2026, 3, 16, 5, 0, tzinfo=timezone.utc)  # 08:00 MSK
    with patch.object(session_mod, '_msk_now', return_value=fake_now + session_mod._MSK_OFFSET):
        mins = session_mod.minutes_until_session_end('all')
        assert mins > 900  # much more than a single morning session tail
