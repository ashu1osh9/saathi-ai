"""Smoke-harness unit regressions; actual container acceptance remains in CI.

These isolated Docker/HTTP fixtures test the harness's lifecycle, not Gnani or
application API success. No server, container or provider is mocked in production.
"""
import io
import itertools
import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from tools import container_smoke as smoke


class TestContainerSmoke(unittest.TestCase):
    def test_restart_requeries_dynamic_port_before_readiness(self):
        state = {'port': 41001, 'restarted': False}
        lookups = []
        calls = []

        def docker(*args):
            if args[0] == 'port':
                lookups.append(state['port'])
                return f"127.0.0.1:{state['port']}"
            if args[0] == 'restart':
                state.update(port=41002, restarted=True)
            if args[:2] == ('exec', '--user'):
                return json.dumps([[10001, 10001, 0o700], [10001, 10001, 0o600]])
            if args[0] == 'exec':
                return 'Uid:\t10001\t10001\t10001\t10001'
            return 'test-only-container'

        replies = iter([
            (200, {}), (401, {}), (403, {}), (200, {}), (401, {}), (201, {}),
            (202, {'token': 'test-only-review'}), (200, []), (200, {}),
            (200, [{'body': 'Persistent container example'}]),
            (200, {'saved': True, 'sent': False}),
        ])

        def open_request(request, timeout):
            port = urlsplit(request.full_url).port
            calls.append((state['restarted'], port))
            if port != state['port']:
                raise urllib.error.URLError('Old Docker port is closed')
            status, body = next(replies)
            response = io.BytesIO(json.dumps(body).encode())
            response.status = status
            return response

        with patch.object(smoke, 'docker', side_effect=docker), \
             patch.object(smoke.urllib.request, 'build_opener', return_value=SimpleNamespace(open=open_request)), \
             patch.object(smoke.subprocess, 'run') as cleanup, \
             patch.object(smoke.time, 'monotonic', side_effect=itertools.count(0, 20)), \
             patch.object(smoke.time, 'sleep'), patch.object(smoke, 'report_failure') as failure, \
             patch('sys.argv', ['container_smoke.py', '--image', 'test-only-image']), patch('sys.stdout', new_callable=io.StringIO):
            smoke.main()
        self.assertEqual(lookups, [41001, 41002])
        self.assertTrue(any(restarted for restarted, _ in calls))
        self.assertTrue(all(port == 41002 for restarted, port in calls if restarted))
        self.assertEqual(cleanup.call_count, 2)
        failure.assert_not_called()

    def test_discovered_endpoint_must_remain_loopback_only(self):
        for mapping in ['0.0.0.0:41001', '[::]:41001', '127.0.0.1:0', '127.0.0.1:70000', '127.0.0.1:not-a-port']:
            with self.subTest(mapping=mapping), patch.object(smoke, 'docker', return_value=mapping), self.assertRaises(RuntimeError):
                smoke.container_base_url('test-only-container')


if __name__ == '__main__':
    unittest.main()
