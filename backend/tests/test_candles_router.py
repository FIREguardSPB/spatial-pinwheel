import unittest
from datetime import datetime, timezone
from types import SimpleNamespace


class CandlesRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_candles_refreshes_stale_cache_when_remote_fetch_available(self):
        import apps.api.routers.candles as module

        stale_ts = int(datetime(2026, 4, 21, 4, 0, tzinfo=timezone.utc).timestamp())
        fresh_ts = int(datetime(2026, 4, 21, 6, 15, tzinfo=timezone.utc).timestamp())
        cached = [{'time': stale_ts, 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1, 'is_complete': True}]
        remote = [{'time': fresh_ts, 'open': 2, 'high': 2, 'low': 2, 'close': 2, 'volume': 2, 'is_complete': True}]

        original_list = module.candle_repo.list_candles
        original_upsert = module.candle_repo.upsert_candles
        original_allow = module._allow_remote_fetch
        original_tf_seconds = module._tf_seconds
        original_get_token = module.get_token if hasattr(module, 'get_token') else None
        original_settings = None
        upserts = []

        class _Adapter:
            def __init__(self, *args, **kwargs):
                pass

            async def get_candles(self, ticker, from_dt, to_dt, interval_str='1m'):
                return list(remote)

            async def close(self):
                return None

        try:
            module.candle_repo.list_candles = lambda _db, _ticker, _tf, limit=500: list(cached)
            module.candle_repo.upsert_candles = lambda _db, instrument_id, timeframe, candles, source='api': upserts.append((instrument_id, timeframe, list(candles), source))
            module._allow_remote_fetch = lambda _key: True
            module._tf_seconds = lambda _tf: 60

            from core.config import settings as cfg
            original_settings = (cfg.TBANK_TOKEN, cfg.TBANK_ACCOUNT_ID, cfg.TBANK_SANDBOX)
            cfg.TBANK_TOKEN = 'token'
            cfg.TBANK_ACCOUNT_ID = 'acct'
            cfg.TBANK_SANDBOX = True

            import apps.broker.tbank as tbank_module
            original_adapter = tbank_module.TBankGrpcAdapter
            tbank_module.TBankGrpcAdapter = _Adapter
            try:
                result = await module.get_candles('TQBR:SBER', tf='1m', db=SimpleNamespace())
            finally:
                tbank_module.TBankGrpcAdapter = original_adapter
        finally:
            module.candle_repo.list_candles = original_list
            module.candle_repo.upsert_candles = original_upsert
            module._allow_remote_fetch = original_allow
            module._tf_seconds = original_tf_seconds
            if original_settings is not None:
                from core.config import settings as cfg
                cfg.TBANK_TOKEN, cfg.TBANK_ACCOUNT_ID, cfg.TBANK_SANDBOX = original_settings

        self.assertEqual(result[-1]['time'], fresh_ts)
        self.assertTrue(upserts)
