import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.services.ui_runtime import build_pipeline_counters_summary, build_signal_flow_status


class _Field:
    def __ge__(self, _other):
        return self

    def in_(self, _items):
        return self

    def __eq__(self, _other):
        return self


class _SignalModel:
    created_ts = _Field()
    status = _Field()


class _TradeModel:
    ts = _Field()


class _DecisionLogModel:
    ts = _Field()
    type = _Field()


class _FakeQuery:
    def __init__(self, count_value):
        self.count_value = count_value

    def filter(self, *_args, **_kwargs):
        return self

    def count(self):
        return self.count_value


class _FakeDB:
    def __init__(self, signal_counts, trade_count, log_counts):
        self.signal_counts = list(signal_counts)
        self.trade_count = trade_count
        self.log_counts = list(log_counts)

    def query(self, model):
        if model is _SignalModel:
            return _FakeQuery(self.signal_counts.pop(0))
        if model is _TradeModel:
            return _FakeQuery(self.trade_count)
        if model is _DecisionLogModel:
            return _FakeQuery(self.log_counts.pop(0))
        raise AssertionError(f'unexpected model {model}')


class _SignalRowsQuery:
    def __init__(self, rows):
        self.rows = rows
    def filter(self, *_args, **_kwargs):
        return self
    def order_by(self, *_args, **_kwargs):
        return self
    def all(self):
        return self.rows


class _SignalRowsDB:
    def __init__(self, rows):
        self.rows = rows
    def query(self, model):
        if model is _SignalModel:
            return _SignalRowsQuery(self.rows)
        raise AssertionError(f'unexpected model {model}')


class PipelineCountersRuntimeTests(unittest.TestCase):
    def test_pipeline_counters_include_cooldown_aware_proceeds(self):
        from core.services import ui_runtime as module

        orig_signal = module.Signal
        orig_trade = module.Trade
        orig_log = module.DecisionLog
        module.Signal = _SignalModel
        module.Trade = _TradeModel
        module.DecisionLog = _DecisionLogModel
        try:
            db = _FakeDB(signal_counts=[12, 3, 2, 1], trade_count=2, log_counts=[4, 7, 5])
            payload = build_pipeline_counters_summary(db, 24)
        finally:
            module.Signal = orig_signal
            module.Trade = orig_trade
            module.DecisionLog = orig_log

        self.assertEqual(payload['signals_created'], 12)
        self.assertEqual(payload['signals_progressed'], 3)
        self.assertEqual(payload['pending_review'], 2)
        self.assertGreater(payload['progression_rate'], 0)
        self.assertEqual(payload['execution_errors'], 1)
        self.assertEqual(payload['risk_blocks'], 4)
        self.assertEqual(payload['cooldown_aware_proceeds'], 7)
        self.assertEqual(payload['execution_stage_rejects'], 5)

    def test_signal_flow_status_explains_frozen_mode_silence(self):
        from core.services import ui_runtime as module

        orig_signal = module.Signal
        orig_log = module.DecisionLog
        module.Signal = _SignalModel
        module.DecisionLog = _DecisionLogModel
        try:
            db = _FakeDB(signal_counts=[1, 0, 0, 0], trade_count=0, log_counts=[0, 1, 2])
            payload = build_signal_flow_status(db, 60)
        finally:
            module.Signal = orig_signal
            module.DecisionLog = orig_log

        self.assertTrue(payload['degraded_throughput'])
        self.assertEqual(payload['suspected_cause'], 'frozen_mode_pressure')

    def test_signal_flow_status_detects_reject_storm_under_frozen_mode(self):
        from core.services import ui_runtime as module

        orig_signal = module.Signal
        orig_log = module.DecisionLog
        module.Signal = _SignalModel
        module.DecisionLog = _DecisionLogModel
        try:
            db = _FakeDB(signal_counts=[12, 0, 0, 11], trade_count=0, log_counts=[0, 0, 8])
            payload = build_signal_flow_status(db, 60)
        finally:
            module.Signal = orig_signal
            module.DecisionLog = orig_log

        self.assertTrue(payload['degraded_throughput'])
        self.assertEqual(payload['suspected_cause'], 'reject_storm_frozen_mode')

    def test_ai_runtime_summary_exposes_recent_shadow_agent_decision(self):
        from core.services import ui_runtime as module

        original_ai_repo = module.ai_repo.list_decisions
        original_tokens = module.load_runtime_tokens
        module.ai_repo.list_decisions = lambda _db, limit=1: [SimpleNamespace(provider='openai', decision='TAKE', confidence=81, reasoning='shadow trader liked the setup')]
        module.load_runtime_tokens = lambda _db, _keys: {}
        try:
            payload = module.build_ai_runtime_summary(object(), SimpleNamespace(ai_primary_provider='openai', ai_fallback_providers='claude,deepseek,skip'))
        finally:
            module.ai_repo.list_decisions = original_ai_repo
            module.load_runtime_tokens = original_tokens

        self.assertEqual(payload['primary_provider'], 'openai')
        self.assertTrue(payload['last_decision']['available'])

    def test_ai_runtime_summary_exposes_agent_divergence_metrics(self):
        from core.services import ui_runtime as module

        original_ai_repo = module.ai_repo.list_decisions
        original_tokens = module.load_runtime_tokens
        module.ai_repo.list_decisions = lambda _db, limit=5: [
            SimpleNamespace(provider='openai', decision='TAKE', confidence=81, reasoning='shadow trader liked the setup', meta={'challenger_agent_shadow': {'stance': 'approve'}, 'agent_merge_shadow': {'consensus_action': 'take'}}),
            SimpleNamespace(provider='claude', decision='REJECT', confidence=84, reasoning='challenger objected', meta={'challenger_agent_shadow': {'stance': 'challenge'}, 'agent_merge_shadow': {'consensus_action': 'review'}}),
        ]
        module.load_runtime_tokens = lambda _db, _keys: {}
        try:
            payload = module.build_ai_runtime_summary(object(), SimpleNamespace(ai_primary_provider='openai', ai_fallback_providers='claude,deepseek,skip'))
        finally:
            module.ai_repo.list_decisions = original_ai_repo
            module.load_runtime_tokens = original_tokens

        self.assertEqual(payload['agent_shadow']['recent_calls'], 2)
        self.assertEqual(payload['agent_shadow']['challenger_challenges'], 1)

    def test_agent_shadow_runtime_summary_counts_consensus_and_execution_followthrough(self):
        from core.services import ui_runtime as module

        orig_signal = module.Signal
        module.Signal = _SignalModel
        try:
            rows = [
                SimpleNamespace(status='executed', created_ts=1, meta={'agent_merge_shadow': {'consensus_action': 'take', 'challenger_stance': 'approve'}, 'agent_thesis_shadow': {'thesis_state': 'alive', 'reentry_allowed': True, 'winner_management_intent': 'preserve'}}),
                SimpleNamespace(status='rejected', created_ts=2, meta={'agent_merge_shadow': {'consensus_action': 'review', 'challenger_stance': 'challenge'}, 'agent_thesis_shadow': {'thesis_state': 'fragile', 'reentry_allowed': False, 'winner_management_intent': 'neutral'}}),
            ]
            payload = module.build_agent_shadow_runtime_summary(_SignalRowsDB(rows), 24)
        finally:
            module.Signal = orig_signal

        self.assertEqual(payload['recent_signals'], 2)
        self.assertEqual(payload['consensus_take'], 1)
        self.assertEqual(payload['challenger_challenges'], 1)
        self.assertEqual(payload['executed_after_consensus_take'], 1)

    def test_settings_runtime_snapshot_exposes_market_block(self):
        from core.services import ui_runtime as module

        original_get_settings = module.settings_repo.get_settings
        original_watchlist = module.get_watchlist_items
        original_sector_distribution = module.sector_distribution
        original_bot_status = __import__('apps.api.status', fromlist=['build_bot_status_sync']).build_bot_status_sync
        original_schedule = __import__('core.services.trading_schedule', fromlist=['get_schedule_snapshot']).get_schedule_snapshot
        original_trade_mgmt = __import__('core.services.trade_management_runtime', fromlist=['build_trade_management_runtime_summary']).build_trade_management_runtime_summary

        module.settings_repo.get_settings = lambda _db: SimpleNamespace(trading_session='all')
        module.get_watchlist_items = lambda _db: []
        module.sector_distribution = lambda _items: {}
        import apps.api.status as status_module
        import core.services.trading_schedule as schedule_module
        import core.services.trade_management_runtime as trade_mgmt_module
        status_module.build_bot_status_sync = lambda _db: {'ok': True}
        schedule_module.get_schedule_snapshot = lambda **_kwargs: {
            'is_open': True,
            'source': 'static',
            'exchange': 'MOEX',
            'current_session': 'evening',
            'trading_day': '2026-04-20',
            'start_at': '2026-04-20T19:00:00+03:00',
            'end_at': '2026-04-20T23:50:00+03:00',
            'minutes_until_close': 120.0,
            'warning': None,
            'error': None,
        }
        trade_mgmt_module.build_trade_management_runtime_summary = lambda _db, _hours: {}
        module.build_ai_runtime_summary = lambda _db, _settings: {}
        module.build_telegram_runtime_summary = lambda _db, _settings: {}
        module.build_policy_runtime_summary = lambda _db, _settings: {}
        module.get_execution_control_snapshot = lambda _settings: {}
        module.evaluate_execution_anomaly_breaker = lambda _db, _settings: {}
        module.build_governor_review_runtime_summary = lambda _db, settings=None: {}
        module.build_slice_review_runtime_summary = lambda _db, settings=None: {}
        module.build_data_edge_runtime_summary = lambda _db, _settings: {}
        module.build_cognitive_runtime_summary = lambda _db: {}
        module.build_research_runtime_summary = lambda _db, _settings: {}
        module.build_ml_runtime_summary = lambda _db, _settings: {}
        module.build_sentiment_runtime_summary = lambda _db, _settings: {}
        module.build_pipeline_counters_summary = lambda _db, _hours=24: {}
        try:
            payload = module.build_settings_runtime_snapshot(object())
        finally:
            module.settings_repo.get_settings = original_get_settings
            module.get_watchlist_items = original_watchlist
            module.sector_distribution = original_sector_distribution
            status_module.build_bot_status_sync = original_bot_status
            schedule_module.get_schedule_snapshot = original_schedule
            trade_mgmt_module.build_trade_management_runtime_summary = original_trade_mgmt

        self.assertIn('market', payload)
        self.assertTrue(payload['market']['is_open'])
        self.assertEqual(payload['market']['current_session'], 'evening')
        self.assertEqual(payload['market']['session_type'], 'all')


class PaperExecutionStageBlockTests(unittest.IsolatedAsyncioTestCase):
    async def test_execution_risk_block_sets_signal_meta(self):
        from core.execution import paper as module

        class _Query:
            def __init__(self, signal):
                self.signal = signal

            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return self.signal

        engine = object.__new__(module.PaperExecutionEngine)
        signal = SimpleNamespace(
            id='sig_1',
            instrument_id='TQBR:TEST',
            status='approved',
            meta={},
            size=1,
            entry=100.0,
            side='BUY',
        )
        engine.db = SimpleNamespace(query=lambda _model: _Query(signal), commit=lambda: None)
        engine.risk = SimpleNamespace(
            check_new_signal=lambda _signal: (False, 'Breakout below 20-bar range'),
            last_check_details={'blocked_by': 'breakout_range_invalidated'},
        )
        engine._eligible_partial_close_candidate = lambda *_args, **_kwargs: (None, None, None)
        original_get_settings = module.settings_repo.get_settings
        original_append = module.append_decision_log_best_effort
        original_bus = module.bus
        module.settings_repo.get_settings = lambda _db: SimpleNamespace()
        module.append_decision_log_best_effort = lambda **_kwargs: None
        module.bus = SimpleNamespace(publish=AsyncMock())
        try:
            await module.PaperExecutionEngine.execute_approved_signal(engine, 'sig_1')
        finally:
            module.settings_repo.get_settings = original_get_settings
            module.append_decision_log_best_effort = original_append
            module.bus = original_bus

        self.assertEqual(signal.status, 'rejected')
        self.assertEqual(signal.meta['execution_stage_block']['code'], 'execution_risk_block')
        self.assertEqual(signal.meta['execution_stage_block']['stage'], 'paper_execution')


class BotStatusRuntimeConsistencyTests(unittest.TestCase):
    def test_bot_status_marks_running_false_when_worker_offline(self):
        import apps.api.status as module

        original_get_settings = module.settings_repo.get_settings
        original_load_runtime_tokens = module.load_runtime_tokens
        original_controls = module.get_execution_control_snapshot
        original_breaker = module.evaluate_execution_anomaly_breaker
        original_trade_mgmt = module.build_trade_management_runtime_summary
        original_governor = module.build_governor_review_runtime_summary
        original_slice = module.build_slice_review_runtime_summary
        original_data_edge = module.build_data_edge_runtime_summary
        original_cognitive = module.build_cognitive_runtime_summary
        original_research = module.build_research_runtime_summary
        original_schedule = module.get_schedule_snapshot
        original_live_capable = module.live_capable_for
        original_read_worker_status = getattr(module, 'read_worker_status', None)

        module.settings_repo.get_settings = lambda _db: SimpleNamespace(bot_enabled=True, trade_mode='auto_paper', trading_session='all')
        module.load_runtime_tokens = lambda _db, _keys: {}
        module.get_execution_control_snapshot = lambda _settings: {}
        module.evaluate_execution_anomaly_breaker = lambda _db, _settings: {'action': 'idle', 'controls': {}}
        module.build_trade_management_runtime_summary = lambda _db, _hours: {}
        module.build_governor_review_runtime_summary = lambda _db, settings=None: {'status': 'ok'}
        module.build_slice_review_runtime_summary = lambda _db, settings=None: {'status': 'ok'}
        module.build_data_edge_runtime_summary = lambda _db, _settings: {'market_data': {'freshness': 'fresh'}}
        module.build_cognitive_runtime_summary = lambda _db: {'contradiction_breakdown': {}}
        module.build_research_runtime_summary = lambda _db, _settings: {'challenger_registry': {'candidate_slices_count': 0}}
        module.get_schedule_snapshot = lambda session_type='all': {
            'exchange': 'MOEX',
            'trading_day': '2026-04-21',
            'source': 'dynamic',
            'is_open': True,
            'current_session_start': '2026-04-21T06:50:00+03:00',
            'current_session_end': '2026-04-21T18:59:59+03:00',
            'next_open': '2026-04-21T19:00:00+03:00',
        }
        module.live_capable_for = lambda _settings, _tokens: False
        module.read_worker_status = AsyncMock(return_value={'ok': False, 'phase': 'offline', 'message': 'Worker status is unavailable'})

        class _FakeDB:
            def execute(self, *_args, **_kwargs):
                return None

            def query(self, *_args, **_kwargs):
                class _Query:
                    def filter(self, *_args, **_kwargs):
                        return self

                    def order_by(self, *_args, **_kwargs):
                        return self

                    def first(self):
                        return None

                return _Query()

        try:
            payload = module.build_bot_status_sync(_FakeDB())
        finally:
            module.settings_repo.get_settings = original_get_settings
            module.load_runtime_tokens = original_load_runtime_tokens
            module.get_execution_control_snapshot = original_controls
            module.evaluate_execution_anomaly_breaker = original_breaker
            module.build_trade_management_runtime_summary = original_trade_mgmt
            module.build_governor_review_runtime_summary = original_governor
            module.build_slice_review_runtime_summary = original_slice
            module.build_data_edge_runtime_summary = original_data_edge
            module.build_cognitive_runtime_summary = original_cognitive
            module.build_research_runtime_summary = original_research
            module.get_schedule_snapshot = original_schedule
            module.live_capable_for = original_live_capable
            if original_read_worker_status is not None:
                module.read_worker_status = original_read_worker_status

        self.assertFalse(payload['is_running'])
        self.assertIn('worker', ' '.join(payload.get('warnings') or []).lower())


class DashboardUiCacheTests(unittest.TestCase):
    def test_cached_payload_returns_stale_value_if_builder_fails(self):
        import apps.api.routers.ui as module

        module._UI_CACHE.clear()
        first = module._cached_payload('ui:test', 10.0, lambda: {'ok': True})
        self.assertEqual(first, {'ok': True})

        second = module._cached_payload('ui:test', 10.0, lambda: (_ for _ in ()).throw(RuntimeError('boom')))
        self.assertEqual(second, {'ok': True})


if __name__ == '__main__':
    unittest.main()
