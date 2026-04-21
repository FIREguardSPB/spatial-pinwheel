import unittest


class ApiHeavyReadMiddlewareTests(unittest.TestCase):
    def test_health_does_not_schedule_memory_trim_in_dev(self):
        import apps.api.main as module

        original_env = module.config.APP_ENV
        original_limit = module._RECYCLING_REQUEST_LIMIT
        original_count = module._HEAVY_READ_REQUESTS
        original_armed = module._RECYCLE_ARMED

        class _URL:
            path = '/api/v1/health'

        class _Request:
            method = 'GET'
            url = _URL()

        class _Response:
            background = None

        async def _call_next(_request):
            return _Response()

        try:
            module.config.APP_ENV = 'dev'
            module._HEAVY_READ_REQUESTS = 0
            module._RECYCLE_ARMED = False
            module._RECYCLING_REQUEST_LIMIT = 0
            response = __import__('asyncio').run(module.trim_memory_after_heavy_reads(_Request(), _call_next))
        finally:
            module.config.APP_ENV = original_env
            module._RECYCLING_REQUEST_LIMIT = original_limit
            module._HEAVY_READ_REQUESTS = original_count
            module._RECYCLE_ARMED = original_armed

        self.assertIsNone(response.background)
