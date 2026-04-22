from types import SimpleNamespace

from core.execution.monitor import PositionMonitor


def test_signal_feedback_context_reads_signal_meta_fields():
    signal = SimpleNamespace(meta={
        'conviction_profile': {'tier': 'B'},
        'high_conviction_promotion': {'promoted': True},
        'review_readiness': {'approval_candidate': True},
        'execution_quality_seed': {'fill_quality_status': 'ok'},
    })

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self
        def first(self):
            return signal

    class _DB:
        def query(self, _model):
            return _Query()

    monitor = PositionMonitor(_DB())
    payload = monitor._signal_feedback_context('sig_1')

    assert payload['conviction_profile']['tier'] == 'B'
    assert payload['high_conviction_promotion']['promoted'] is True
    assert payload['review_readiness']['approval_candidate'] is True
    assert payload['execution_quality_seed']['fill_quality_status'] == 'ok'
