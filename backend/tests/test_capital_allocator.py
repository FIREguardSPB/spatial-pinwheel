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
