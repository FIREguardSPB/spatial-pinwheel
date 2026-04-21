from types import SimpleNamespace

from core.storage.repos.signals import _pending_review_priority


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
