from types import SimpleNamespace

from core.storage.repos import signals as signals_repo
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
