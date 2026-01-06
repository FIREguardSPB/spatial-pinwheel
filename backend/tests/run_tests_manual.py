import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

# Mock pytest to avoid dependency error
from unittest.mock import MagicMock

sys.modules["pytest"] = MagicMock()

from tests import test_decision_engine  # noqa: E402


def run():
    print("Running Decision Engine Tests...")
    functions = [
        test_decision_engine.test_indicators_basic,
        test_decision_engine.test_check_invalid_signal,
        test_decision_engine.test_check_risk_reward,
        test_decision_engine.test_score_levels_logic,
        test_decision_engine.test_engine_evaluate_flow,
        test_decision_engine.test_score_normalization,
        test_decision_engine.test_score_levels_clamp,
    ]

    passed = 0
    failed = 0

    for f in functions:
        try:
            f()
            print(f"[PASS] {f.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {f.__name__}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} Passed, {failed} Failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
