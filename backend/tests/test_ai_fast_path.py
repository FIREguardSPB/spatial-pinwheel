from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.worker.ai.fast_path import evaluate_ai_fast_path
from apps.worker.decision_engine.types import Decision, DecisionResult, Reason, ReasonCode, Severity


def _evaluation(*, decision: Decision = Decision.SKIP, reasons: list[Reason] | None = None) -> DecisionResult:
    return DecisionResult(
        decision=decision,
        score_pct=42,
        threshold_pct=70,
        score_raw=42,
        score_max=100,
        score=42,
        threshold=70,
        reasons=reasons or [],
        metrics={},
        adjustments={},
    )


class AIFastPathTests(unittest.TestCase):
    def test_fast_path_triggers_on_de_blockers(self):
        result = evaluate_ai_fast_path(
            evaluation=_evaluation(
                decision=Decision.REJECT,
                reasons=[Reason(code=ReasonCode.SESSION_CLOSED, severity=Severity.BLOCK, msg='session closed')],
            ),
            final_decision='REJECT',
            perf_governor={},
            freshness_meta={},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.final_decision, 'REJECT')
        self.assertIn('decision_engine_blockers', result.triggers)
        self.assertIn('SESSION_CLOSED', result.blocker_codes)

    def test_fast_path_triggers_on_governor_suppression_without_de_blockers(self):
        result = evaluate_ai_fast_path(
            evaluation=_evaluation(decision=Decision.SKIP, reasons=[]),
            final_decision='SKIP',
            perf_governor={'suppressed': True, 'reasons': ['profit factor 0.63 < 0.70']},
            freshness_meta={},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.final_decision, 'SKIP')
        self.assertIn('performance_governor_suppressed', result.triggers)
        self.assertIn('profit factor 0.63 < 0.70', result.reason)

    def test_fast_path_does_not_trigger_for_soft_skip_only(self):
        result = evaluate_ai_fast_path(
            evaluation=_evaluation(
                decision=Decision.SKIP,
                reasons=[Reason(code=ReasonCode.RSI_OVERHEAT, severity=Severity.WARN, msg='soft skip')],
            ),
            final_decision='SKIP',
            perf_governor={},
            freshness_meta={'blocked': False},
        )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
