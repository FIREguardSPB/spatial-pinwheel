from decimal import Decimal
from unittest.mock import patch

from apps.worker.ai.prompts import build_user_prompt
from apps.worker.ai.types import AIContext
from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import Decision, MarketSnapshot, ReasonCode
from core.risk.economic import EconomicFilter, EconomicFilterConfig
from core.storage.models import Settings


class MockSignal:
    def __init__(self, side='BUY', entry=100.0, sl=99.0, tp=102.0, size=100.0, r=2.0):
        self.side = side
        self.entry = Decimal(str(entry))
        self.sl = Decimal(str(sl))
        self.tp = Decimal(str(tp))
        self.size = Decimal(str(size))
        self.r = Decimal(str(r))


def _settings() -> Settings:
    s = Settings()
    s.decision_threshold = 40
    s.rr_min = 1.1
    s.atr_stop_hard_min = 0.1
    s.atr_stop_hard_max = 10.0
    s.atr_stop_soft_min = 0.1
    s.atr_stop_soft_max = 5.0
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
    s.min_sl_distance_pct = 0.5
    s.min_profit_after_costs_multiplier = 2.0
    s.min_trade_value_rub = 1000.0
    s.min_instrument_price_rub = 10.0
    s.min_tick_floor_rub = 0.0
    s.commission_dominance_warn_ratio = 0.30
    s.volatility_sl_floor_multiplier = 0.0
    s.sl_cost_floor_multiplier = 0.0
    return s


def _snapshot() -> MarketSnapshot:
    candles = []
    for i in range(80):
        close = 100.0 + (0.2 if i % 2 == 0 else -0.1)
        candles.append({
            'time': 1_700_000_000 + i * 60,
            'open': close - 0.2,
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': 10_000,
        })
    return MarketSnapshot(candles=candles, last_price=Decimal(str(candles[-1]['close'])))


def test_economic_filter_blocks_low_price_instrument():
    filt = EconomicFilter(EconomicFilterConfig(min_instrument_price_rub=10.0))
    result = filt.evaluate(entry=0.45, sl=0.4488, tp=0.4524, qty=5_000_000, fees_bps=3, slippage_bps=5, atr14=0.001)
    assert result.is_valid is False
    assert result.block_reason is not None
    assert result.block_reason.code == ReasonCode.ECONOMIC_LOW_PRICE
    assert 'LOW_PRICE_WARNING' in result.metrics['economic_warning_flags']


def test_economic_filter_blocks_micro_levels_even_when_price_is_allowed():
    filt = EconomicFilter(EconomicFilterConfig(min_instrument_price_rub=0.0, min_sl_distance_pct=0.5))
    result = filt.evaluate(entry=12.0, sl=11.982, tp=12.036, qty=200, fees_bps=3, slippage_bps=5, atr14=0.03)
    assert result.is_valid is False
    assert result.block_reason is not None
    assert result.block_reason.code == ReasonCode.ECONOMIC_MICRO_LEVELS
    assert 'MICRO_LEVELS_WARNING' in result.metrics['economic_warning_flags']


def test_decision_engine_rejects_signal_on_economic_filter():
    settings = _settings()
    settings.atr_stop_hard_min = 0.0
    settings.atr_stop_soft_min = 0.0
    engine = DecisionEngine(settings)
    sig = MockSignal(entry=12.0, sl=11.982, tp=12.036, size=200, r=2.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, _snapshot())
    assert result.decision == Decision.REJECT
    assert result.metrics.get('decision_adjustment') == 'blocked_economic_filter'
    assert any(r.code == ReasonCode.ECONOMIC_MICRO_LEVELS for r in result.reasons)


def test_prompt_includes_economic_context_and_warnings():
    ctx = AIContext(
        signal_id='sig_hydr',
        instrument_id='TQBR:HYDR',
        side='BUY',
        entry=0.45,
        sl=0.4488,
        tp=0.4524,
        size=5_000_000,
        r=2.0,
        de_score=28,
        de_decision='REJECT',
        de_reasons=[{'severity': 'block', 'code': 'ECONOMIC_MICRO_LEVELS', 'msg': 'micro levels'}],
        de_metrics={
            'vol_ratio': 1.6,
            'vwap': 0.4498,
            'net_rr': 1.2,
            'gross_rr': 2.0,
            'costs_fee_bps': 3,
            'costs_slippage_bps': 5,
            'entry_price_rub': 0.45,
            'position_qty': 5_000_000,
            'position_value_rub': 2_250_000,
            'sl_distance_rub': 0.0012,
            'sl_distance_pct': 0.2667,
            'tp_distance_rub': 0.0024,
            'tp_distance_pct': 0.5333,
            'round_trip_cost_rub': 0.00072,
            'round_trip_cost_pct': 0.16,
            'min_required_sl_pct': 0.5,
            'min_required_sl_rub': 0.01,
            'min_required_profit_pct': 0.32,
            'min_required_profit_rub': 0.00144,
            'expected_profit_after_costs_rub': 0.00168,
            'breakeven_move_pct': 0.16,
            'commission_dominance_ratio': 0.6,
            'economic_warning_flags': ['MICRO_LEVELS_WARNING', 'COMMISSION_DOMINANCE_WARNING', 'LOW_PRICE_WARNING'],
        },
        candles_summary={'last_close': 0.45, 'ema50': 0.448, 'atr14': 0.001, 'rsi14': 55.0, 'macd_hist': 0.0001},
        internet=None,
    )
    prompt = build_user_prompt(ctx)
    assert 'ЭКОНОМИКА СДЕЛКИ' in prompt
    assert 'MICRO_LEVELS_WARNING' in prompt
    assert 'Цена бумаги: 0.4500 RUB' in prompt
    assert 'Round-trip cost: 0.0007 RUB (0.1600%)' in prompt


def test_decision_engine_uses_runtime_economic_floor_settings_without_falling_back_to_code_defaults():
    settings = _settings()
    settings.atr_stop_hard_min = 0.0
    settings.atr_stop_soft_min = 0.0
    settings.min_sl_distance_pct = 0.001
    settings.min_trade_value_rub = 10.0
    settings.min_profit_after_costs_multiplier = 1.0
    settings.min_tick_floor_rub = 0.0
    settings.volatility_sl_floor_multiplier = 0.0
    settings.sl_cost_floor_multiplier = 0.0
    engine = DecisionEngine(settings)
    sig = MockSignal(entry=100.0, sl=99.999, tp=100.004, size=1, r=4.0)
    with patch('apps.worker.decision_engine.rules.check_session', return_value=None):
        result = engine.evaluate(sig, _snapshot())
    assert result.metrics['config_min_sl_distance_pct'] == 0.001
    assert result.metrics['config_min_tick_floor_rub'] == 0.0
    assert result.metrics['config_volatility_sl_floor_multiplier'] == 0.0
    assert result.metrics['config_sl_cost_floor_multiplier'] == 0.0
    assert result.metrics['min_required_sl_pct'] == 0.001
