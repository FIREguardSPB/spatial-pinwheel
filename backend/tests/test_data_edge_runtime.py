import unittest
from types import SimpleNamespace

from core.services.data_edge_runtime import build_data_edge_runtime_summary


class _Field:
    def __ge__(self, _other):
        return self

    def in_(self, _items):
        return self

    def desc(self):
        return self


class _DecisionLogModel:
    ts = _Field()
    type = _Field()


class _CandleCacheModel:
    ts = _Field()


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeDB:
    def __init__(self, mapping):
        self.mapping = dict(mapping)

    def query(self, model):
        return _FakeQuery(self.mapping.get(model, []))


class DataEdgeRuntimeTests(unittest.TestCase):
    def test_build_data_edge_runtime_summary_returns_unified_bundle(self):
        now_ms = 1_710_000_000_000
        import core.services.data_edge_runtime as module
        orig_now = module._now_ms
        orig_decision_log = module.DecisionLog
        orig_candle = module.CandleCache
        module._now_ms = lambda: now_ms
        module.DecisionLog = _DecisionLogModel
        module.CandleCache = _CandleCacheModel
        try:
            db = _FakeDB({
                _DecisionLogModel: [SimpleNamespace(type='stream_reconnect', ts=now_ms - 1000, payload={'streaming': True}, message='stream reconnect ok')],
                _CandleCacheModel: [SimpleNamespace(ts=now_ms - 60_000)],
            })
            settings = SimpleNamespace(sentiment_collection_enabled=True)
            with unittest.mock.patch('core.services.data_edge_runtime.build_collection_status', return_value={'status': 'ready', 'enabled': True, 'total_messages': 14, 'top_instruments': [{'instrument_id': 'TQBR:SBER'}]}), \
                 unittest.mock.patch('core.services.data_edge_runtime.build_source_analytics', return_value=[{'source': 'src1', 'enabled': True}, {'source': 'src2', 'enabled': True, 'last_error': 'timeout'}]):
                payload = build_data_edge_runtime_summary(db, settings)
        finally:
            module._now_ms = orig_now
            module.DecisionLog = orig_decision_log
            module.CandleCache = orig_candle

        self.assertEqual(payload['status'], 'ready')
        self.assertEqual(payload['market_data']['freshness'], 'fresh')
        self.assertEqual(payload['streaming']['status'], 'shadow_ready')
        self.assertEqual(payload['news_sources']['healthy_sources'], 1)
        self.assertEqual(payload['summary_cards'][0]['key'], 'market_data_freshness')

    def test_build_data_edge_runtime_summary_normalizes_second_timestamps(self):
        now_ms = 1_710_000_000_000
        now_sec = now_ms // 1000
        import core.services.data_edge_runtime as module
        orig_now = module._now_ms
        orig_decision_log = module.DecisionLog
        orig_candle = module.CandleCache
        module._now_ms = lambda: now_ms
        module.DecisionLog = _DecisionLogModel
        module.CandleCache = _CandleCacheModel
        try:
            db = _FakeDB({
                _DecisionLogModel: [],
                _CandleCacheModel: [SimpleNamespace(ts=now_sec - 60)],
            })
            settings = SimpleNamespace(sentiment_collection_enabled=True)
            with unittest.mock.patch('core.services.data_edge_runtime.build_collection_status', return_value={'status': 'ready', 'enabled': True, 'total_messages': 0, 'top_instruments': []}), \
                 unittest.mock.patch('core.services.data_edge_runtime.build_source_analytics', return_value=[]):
                payload = build_data_edge_runtime_summary(db, settings)
        finally:
            module._now_ms = orig_now
            module.DecisionLog = orig_decision_log
            module.CandleCache = orig_candle

        self.assertEqual(payload['market_data']['freshness'], 'fresh')
        self.assertLess(payload['market_data']['candle_age_ms'], 3 * 60 * 1000)


if __name__ == '__main__':
    unittest.main()
