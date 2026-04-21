from types import SimpleNamespace

from core.services.capital_allocator import CapitalAllocator


def test_signal_edge_respects_confidence_multiplier():
    base_signal = SimpleNamespace(meta={
        'event_adjusted_score': 80,
        'decision': {'metrics': {'net_rr': 1.5, 'vol_ratio': 1.0}},
        'conviction_profile': {'allocator_priority_bonus': 1.0},
        'performance_governor': {'allocator_priority_multiplier': 1.0, 'execution_priority': 1.0},
        'ml_overlay': {'allocator_priority_multiplier': 1.0, 'execution_priority': 1.0},
        'review_readiness': {'confidence_multiplier': 1.0},
    })
    boosted_signal = SimpleNamespace(meta={
        **base_signal.meta,
        'review_readiness': {'confidence_multiplier': 1.2},
    })

    base_edge = CapitalAllocator._signal_edge(base_signal)
    boosted_edge = CapitalAllocator._signal_edge(boosted_signal)

    assert boosted_edge > base_edge


def test_signal_confidence_multiplier_reads_review_readiness():
    signal = SimpleNamespace(meta={'review_readiness': {'confidence_multiplier': 1.2}})

    multiplier = CapitalAllocator._signal_confidence_multiplier(signal)

    assert multiplier == 1.2


def test_rotation_memory_bias_penalizes_repeat_reallocations_for_same_instrument():
    rows = [SimpleNamespace(payload={'result': {'incoming_instrument': 'TQBR:SBER'}}), SimpleNamespace(payload={'result': {'incoming_instrument': 'TQBR:SBER'}})]

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self
        def all(self):
            return rows

    class _DB:
        def query(self, _model):
            return _Query()

    allocator = CapitalAllocator(_DB(), SimpleNamespace())
    bias = allocator._rotation_memory_bias(SimpleNamespace(instrument_id='TQBR:SBER'))

    assert bias > 0


def test_hold_current_position_when_incoming_confidence_is_not_strong_enough():
    should_hold = CapitalAllocator._should_hold_current_position(
        current_edge=1.0,
        incoming_edge=1.05,
        decay_bias=0.05,
        pnl_component=1.2,
        incoming_confidence_mult=1.0,
    )

    assert should_hold is True


def test_do_not_hold_when_incoming_confidence_is_high():
    should_hold = CapitalAllocator._should_hold_current_position(
        current_edge=1.0,
        incoming_edge=1.05,
        decay_bias=0.05,
        pnl_component=1.2,
        incoming_confidence_mult=1.15,
    )

    assert should_hold is False
