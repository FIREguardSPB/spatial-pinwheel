from types import SimpleNamespace

from core.storage.repos import signals as signals_repo
from core.storage.repos.signals import _pending_review_priority


def test_age_decay_weight_prefers_fresher_feedback():
    fresh = signals_repo._age_decay_weight(1_990_000, 2_000_000, 24)
    stale = signals_repo._age_decay_weight(1_000_000, 2_000_000, 24)

    assert fresh > stale
    assert stale >= 0.25


def test_pending_review_priority_prefers_approval_candidates_then_queue_priority():
    strong = SimpleNamespace(
        meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99}},
        created_ts=200,
        ts=200,
    )
    medium = SimpleNamespace(
        meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 80}},
        created_ts=300,
        ts=300,
    )
    weak = SimpleNamespace(
        meta={'review_readiness': {'approval_candidate': False, 'queue_priority': 120}},
        created_ts=400,
        ts=400,
    )

    ranked = sorted([weak, medium, strong], key=_pending_review_priority, reverse=True)

    assert ranked == [strong, medium, weak]


def test_pending_review_priority_uses_confidence_bias_as_tiebreaker():
    lower = SimpleNamespace(
        meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'confidence_bias': 0}},
        created_ts=200,
        ts=200,
    )
    higher = SimpleNamespace(
        meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'confidence_bias': 20}},
        created_ts=100,
        ts=100,
    )

    ranked = sorted([lower, higher], key=_pending_review_priority, reverse=True)

    assert ranked == [higher, lower]


def test_get_top_pending_review_candidate_prefers_approval_candidate(monkeypatch):
    now_ms = 2_000_000
    weak = SimpleNamespace(meta={'review_readiness': {'approval_candidate': False, 'queue_priority': 120}}, created_ts=400, ts=400)
    strong = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99}}, created_ts=200, ts=now_ms - 1000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [weak, strong])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: now_ms / 1000)

    top = signals_repo.get_top_pending_review_candidate(object())

    assert top is strong


def test_get_top_pending_review_candidate_skips_stale_entries(monkeypatch):
    now_ms = 2_000_000
    stale = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 120}}, created_ts=100, ts=now_ms - 2_000_000)
    fresh = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 90}}, created_ts=200, ts=now_ms - 1000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [stale, fresh])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: now_ms / 1000)

    top = signals_repo.get_top_pending_review_candidate(object(), ttl_sec=900)

    assert top is fresh


def test_get_top_pending_review_candidate_uses_execution_feedback_bonus(monkeypatch):
    candidate_a = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}, created_ts=100, ts=1_999_000)
    candidate_b = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'timeframe_signal'}}, created_ts=100, ts=1_999_000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [candidate_a, candidate_b])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: 2_000_000 / 1000)
    monkeypatch.setattr(signals_repo, '_execution_feedback_bonus', lambda db, signal, lookback_hours=24: 15 if signal is candidate_b else 0)
    monkeypatch.setattr(signals_repo, '_outcome_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_instrument_fatigue_bias', lambda db, signal, lookback_hours=6: 0)
    monkeypatch.setattr(signals_repo, '_diversification_bias', lambda db, signal: 0)

    top = signals_repo.get_top_pending_review_candidate(object(), ttl_sec=900)

    assert top is candidate_b


def test_get_top_pending_review_candidate_uses_outcome_feedback_bonus(monkeypatch):
    candidate_a = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}, created_ts=100, ts=1_999_000)
    candidate_b = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}, created_ts=100, ts=1_999_000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [candidate_a, candidate_b])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: 2_000_000 / 1000)
    monkeypatch.setattr(signals_repo, '_execution_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_outcome_feedback_bonus', lambda db, signal, lookback_hours=24: 12 if signal is candidate_b else 0)
    monkeypatch.setattr(signals_repo, '_instrument_fatigue_bias', lambda db, signal, lookback_hours=6: 0)
    monkeypatch.setattr(signals_repo, '_diversification_bias', lambda db, signal: 0)

    top = signals_repo.get_top_pending_review_candidate(object(), ttl_sec=900)

    assert top is candidate_b


def test_get_top_pending_review_candidate_uses_symbol_thesis_learning_bias(monkeypatch):
    candidate_a = SimpleNamespace(instrument_id='TQBR:SBER', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}, created_ts=100, ts=1_999_000)
    candidate_b = SimpleNamespace(instrument_id='TQBR:LKOH', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}}, created_ts=100, ts=1_999_000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [candidate_a, candidate_b])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: 2_000_000 / 1000)
    monkeypatch.setattr(signals_repo, '_execution_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_outcome_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_symbol_thesis_learning_bias', lambda db, signal, lookback_hours=24: 20 if signal is candidate_b else 0)
    monkeypatch.setattr(signals_repo, '_instrument_fatigue_bias', lambda db, signal, lookback_hours=6: 0)
    monkeypatch.setattr(signals_repo, '_diversification_bias', lambda db, signal: 0)

    top = signals_repo.get_top_pending_review_candidate(object(), ttl_sec=900)

    assert top is candidate_b


def test_get_top_pending_review_candidate_uses_regime_aware_learning_bias(monkeypatch):
    candidate_a = SimpleNamespace(instrument_id='TQBR:LKOH', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}, 'conviction_profile': {'regime': 'trend'}}, created_ts=100, ts=1_999_000)
    candidate_b = SimpleNamespace(instrument_id='TQBR:LKOH', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99, 'thesis_timeframe': '15m', 'thesis_type': 'continuation'}, 'conviction_profile': {'regime': 'trend'}}, created_ts=100, ts=1_999_000)

    monkeypatch.setattr(signals_repo, 'list_signals', lambda db, limit=50, status=None: [candidate_a, candidate_b])
    monkeypatch.setattr(signals_repo.time, 'time', lambda: 2_000_000 / 1000)
    monkeypatch.setattr(signals_repo, '_execution_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_outcome_feedback_bonus', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_symbol_thesis_learning_bias', lambda db, signal, lookback_hours=24: 0)
    monkeypatch.setattr(signals_repo, '_regime_aware_learning_bias', lambda db, signal, lookback_hours=24: 10 if signal is candidate_b else 0)
    monkeypatch.setattr(signals_repo, '_instrument_fatigue_bias', lambda db, signal, lookback_hours=6: 0)
    monkeypatch.setattr(signals_repo, '_diversification_bias', lambda db, signal: 0)

    top = signals_repo.get_top_pending_review_candidate(object(), ttl_sec=900)

    assert top is candidate_b


def test_instrument_fatigue_bias_penalizes_recent_overtrading(monkeypatch):
    rows = [
        SimpleNamespace(type='trade_filled', payload={'instrument_id': 'TQBR:SBER'}),
        SimpleNamespace(type='trade_filled', payload={'instrument_id': 'TQBR:SBER'}),
        SimpleNamespace(type='position_closed', payload={'instrument_id': 'TQBR:SBER', 'net_pnl': -1.0}),
        SimpleNamespace(type='position_closed', payload={'instrument_id': 'TQBR:SBER', 'net_pnl': 1.0}),
    ]

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self
        def all(self):
            return rows

    class _DB:
        def query(self, _model):
            return _Query()

    monkeypatch.setattr(signals_repo.time, 'time', lambda: 2_000_000 / 1000)

    bias = signals_repo._instrument_fatigue_bias(_DB(), SimpleNamespace(instrument_id='TQBR:SBER'), lookback_hours=6)

    assert bias < 0


def test_diversification_bias_rewards_less_crowded_instrument():
    rows = [
        SimpleNamespace(instrument_id='TQBR:SBER', status='pending_review'),
        SimpleNamespace(instrument_id='TQBR:GAZP', status='pending_review'),
    ]

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self
        def all(self):
            return rows

    class _DB:
        def query(self, _model):
            return _Query()

    bias = signals_repo._diversification_bias(_DB(), SimpleNamespace(instrument_id='TQBR:LKOH'))

    assert bias > 0


def test_apply_confidence_shaping_writes_multiplier_into_review_readiness(monkeypatch):
    signal = SimpleNamespace(meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 99}})

    monkeypatch.setattr(signals_repo, '_confidence_shaping_bias', lambda db, signal: 20)

    signals_repo._apply_confidence_shaping(object(), signal)

    review = signal.meta['review_readiness']
    assert review['confidence_bias'] == 20
    assert review['confidence_multiplier'] > 1.0


def test_replace_weaker_pending_signal_replaces_lower_priority(monkeypatch):
    weaker = SimpleNamespace(status='pending_review', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 80}})
    stronger = SimpleNamespace(status='pending_review', meta={'review_readiness': {'approval_candidate': True, 'queue_priority': 100}})

    class _Query:
        def filter(self, *args, **kwargs):
            return self
        def all(self):
            return [weaker, stronger]

    class _DB:
        def query(self, *args, **kwargs):
            return _Query()
        def commit(self):
            pass

    monkeypatch.setattr(signals_repo, 'expire_stale_pending_signals', lambda db, instrument_id, ttl_sec=900: 0)

    replaced = signals_repo.replace_weaker_pending_signal(_DB(), 'TQBR:SBER', incoming_priority=120, ttl_sec=900)

    assert replaced is True
    assert weaker.status == 'expired'
    assert weaker.meta['pending_replaced_by_stronger_candidate'] is True
