from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _make_sa_stub():
    sa = types.ModuleType('sqlalchemy')
    sa_orm = types.ModuleType('sqlalchemy.orm')
    sa.func = MagicMock()
    sa.func.sum = MagicMock(return_value=MagicMock())
    sa_orm.Session = object
    sa.orm = sa_orm
    return sa, sa_orm


_sa, _sa_orm = _make_sa_stub()
sys.modules.setdefault('sqlalchemy', _sa)
sys.modules.setdefault('sqlalchemy.orm', _sa_orm)
sys.modules.setdefault('sqlalchemy.ext', types.ModuleType('sqlalchemy.ext'))
sys.modules.setdefault('sqlalchemy.ext.asyncio', types.ModuleType('sqlalchemy.ext.asyncio'))

from core.services.symbol_adaptive import _select_execution_timeframe


class ExecutionTimeframePolicyTests(unittest.TestCase):
    def test_execution_matches_higher_analysis_timeframe(self):
        settings = SimpleNamespace(execution_timeframe_floor='1m')
        self.assertEqual(
            _select_execution_timeframe(
                analysis_timeframe='15m',
                session_floor='1m',
                settings=settings,
                regime='trend',
            ),
            '15m',
        )

    def test_execution_respects_session_floor_for_5m_analysis(self):
        settings = SimpleNamespace(execution_timeframe_floor='1m')
        self.assertEqual(
            _select_execution_timeframe(
                analysis_timeframe='5m',
                session_floor='5m',
                settings=settings,
                regime='balanced',
            ),
            '5m',
        )

    def test_execution_floor_does_not_exceed_analysis_timeframe(self):
        settings = SimpleNamespace(execution_timeframe_floor='15m')
        self.assertEqual(
            _select_execution_timeframe(
                analysis_timeframe='5m',
                session_floor='1m',
                settings=settings,
                regime='trend',
            ),
            '5m',
        )


if __name__ == '__main__':
    unittest.main()
