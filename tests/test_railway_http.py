"""Real Uvicorn proxy/authentication/restart acceptance; no real Gnani calls."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import requests
from demo_security import password_hash

ROOT = Path(__file__).resolve().parents[1]


class TestRailwayHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        cls.password = 'test-only-private-demo-password'
        cls.env = {**os.environ, 'PORT': str(port), 'SAATHI_ENV': 'production', 'SAATHI_AUTH_MODE': 'basic',
                   'SAATHI_ALLOWED_HOSTS': '127.0.0.1', 'SAATHI_DEMO_USER': 'test-evaluator',
                   'SAATHI_APP_PASSWORD_HASH': password_hash(cls.password), 'FORWARDED_ALLOW_IPS': '127.0.0.1',
                   'SAATHI_DB_PATH': str(Path(cls.temp.name) / 'persistent.db'), 'GNANI_API_KEY': 'test-only-no-provider-calls'}
        cls.env.pop('RAILWAY_VOLUME_MOUNT_PATH', None)
        cls.env.pop('RAILWAY_RUN_UID', None)
        cls.log = (Path(cls.temp.name) / 'server.log').open('w', encoding='utf-8')
        cls.http = requests.Session()
        cls.http.trust_env = False
        try:
            cls.start_server()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def start_server(cls):
        cls.server = subprocess.Popen([sys.executable, '-B', 'serve.py'], cwd=ROOT, env=cls.env,
                                      stdout=cls.log, stderr=cls.log,
                                      creationflags=0x08000000 if os.name == 'nt' else 0)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError('Railway acceptance server failed to start; inspect test configuration.')
            try:
                if cls.http.get(cls.base + '/api/health', timeout=1).ok:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.05)
        raise RuntimeError('Railway acceptance server startup timed out.')

    @classmethod
    def stop_server(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            cls.server.wait(timeout=10)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.http.close()
        cls.log.close()
        cls.temp.cleanup()

    def request(self, method, path, **kwargs):
        # Loopback is a configured trusted proxy in this test; this is not TLS.
        return self.http.request(method, self.base + path,
                                 headers={'X-Forwarded-Proto': 'https', **kwargs.pop('headers', {})},
                                 auth=('test-evaluator', self.password), timeout=5, **kwargs)

    def test_proxy_headers_and_basic_auth_with_actual_uvicorn(self):
        self.assertEqual(self.http.get(self.base + '/', timeout=5).status_code, 403)
        self.assertEqual(self.http.get(self.base + '/', headers={'X-Forwarded-Proto': 'https'}, timeout=5).status_code, 401)
        self.assertEqual(self.http.post(self.base + '/api/tts', headers={'X-Forwarded-Proto': 'https'}, json={'text': 'Namaste'}, timeout=5).status_code, 401)
        response = self.request('GET', '/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Strict-Transport-Security'], 'max-age=31536000')
        self.assertEqual(self.request('GET', '/', headers={'Host': 'attacker.example', 'X-Forwarded-Host': '127.0.0.1'}).status_code, 400)
        self.assertEqual(self.request('POST', '/api/command', headers={'Origin': self.base.replace('http:', 'https:')}, json={'text': 'Mera message padho'}).status_code, 200)
        self.assertEqual(self.request('POST', '/api/command', headers={'Origin': 'https://attacker.example'}, json={'text': 'help'}).status_code, 403)

    def test_database_and_pending_confirmation_survive_process_restart(self):
        response = self.request('POST', '/api/messages', json={'sender': 'Demo', 'body': 'Persistent example'})
        self.assertEqual(response.status_code, 201)
        review = self.request('POST', '/api/drafts', json={'recipient': 'Ravi', 'body': 'Main aaunga'})
        self.assertEqual(review.status_code, 202)
        self.assertEqual(self.request('GET', '/api/drafts').json(), [])
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request('GET', '/api/messages').json()[0]['body'], 'Persistent example')
        confirmed = self.request('POST', '/api/actions/confirm', json={'token': review.json()['token']})
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()['saved'])
        self.assertFalse(confirmed.json()['sent'])
        self.assertEqual(len(self.request('GET', '/api/drafts').json()), 1)


if __name__ == '__main__':
    unittest.main()
