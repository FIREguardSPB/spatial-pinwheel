from types import SimpleNamespace

from apps.api.routers.signals import _signal_flow_class


def test_signal_flow_class_prioritizes_rejected_status_over_take_decision():
    flow = _signal_flow_class({}, status='rejected', final_decision='TAKE')
    assert flow == 'de_rejected'


def test_signal_flow_class_marks_pending_review_as_review_candidate():
    flow = _signal_flow_class({}, status='pending_review', final_decision='TAKE')
    assert flow == 'review_candidate'
