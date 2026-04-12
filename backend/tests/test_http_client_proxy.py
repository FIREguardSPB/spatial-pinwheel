import os
import unittest
from unittest.mock import patch

from core.utils.http_client import get_env_http_proxy_url


class HttpClientProxyTests(unittest.TestCase):
    def test_prefers_https_proxy_and_ignores_unsupported_all_proxy(self):
        env = {
            'HTTPS_PROXY': 'http://127.0.0.1:2080',
            'ALL_PROXY': 'socks://127.0.0.1:2080/',
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(get_env_http_proxy_url('https'), 'http://127.0.0.1:2080')

    def test_returns_none_when_only_unsupported_proxy_is_present(self):
        env = {
            'HTTPS_PROXY': '',
            'https_proxy': '',
            'HTTP_PROXY': '',
            'http_proxy': '',
            'ALL_PROXY': 'socks://127.0.0.1:2080/',
            'all_proxy': 'socks5://127.0.0.1:2080',
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(get_env_http_proxy_url('https'))


if __name__ == '__main__':
    unittest.main()
