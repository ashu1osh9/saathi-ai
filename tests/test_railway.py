"""Application authentication, paid-call budgets and Railway startup regressions.

All credentials/data are test-only. Provider failures are injected only in tests;
no real paid call or successful provider response is fabricated here.
"""
import base64
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as server
import demo_security
import serve

PASSWORD = 'unit-test-only-demo-password'
HASH = demo_security.password_hash(PASSWORD)


class TestRailwaySecurity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(server, 'DB', Path(self.temp.name) / 'saathi.db')
        self.db_patch.start()
        self.env = patch.dict(os.environ, {
            'SAATHI_ENV': 'production', 'SAATHI_AUTH_MODE': 'basic',
            'SAATHI_ALLOWED_HOSTS': 'saathi-test.up.railway.app', 'SAATHI_PROXY_TOKEN': '',
            'SAATHI_DEMO_USER': 'evaluator', 'SAATHI_APP_PASSWORD_HASH': HASH,
            'GNANI_API_KEY': 'unit-test-only-key', 'SAATHI_REQUESTS_PER_MINUTE': '120',
            'SAATHI_AUTH_FAILURES_PER_MINUTE': '20', 'SAATHI_SPEECH_PER_MINUTE': '20',
            'SAATHI_SPEECH_PER_DAY': '200'})
        self.env.start()
        self.client = TestClient(server.app, base_url='https://saathi-test.up.railway.app')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def auth(self, password=PASSWORD, user='evaluator'):
        token = base64.b64encode(f'{user}:{password}'.encode()).decode()
        return {'Authorization': 'Basic ' + token}

    def test_every_data_static_and_paid_route_requires_application_auth(self):
        with patch.object(server.gnani, 'synthesize') as tts, patch.object(server.gnani, 'transcribe') as stt:
            for path in ['/', '/static/app.js', '/api/messages', '/api/summary', '/api/drafts', '/api/reminders', '/openapi.json']:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401, path)
                self.assertIn('Basic realm=', response.headers['www-authenticate'])
                self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(self.client.post('/api/tts', json={'text': 'Namaste'}).status_code, 401)
            self.assertEqual(self.client.post('/api/stt', files={'audio': ('x.wav', b'not-a-wav')}).status_code, 401)
            tts.assert_not_called(); stt.assert_not_called()
        self.assertNotIn(HASH, self.client.get('/api/health').text)

    def test_wrong_or_malformed_credentials_and_gateway_header_do_not_bypass_auth(self):
        for header in ['Bearer abc', 'Basic !!!', 'Basic ' + base64.b64encode(b'no-colon').decode(), 'Basic ' + 'x' * 2100]:
            self.assertEqual(self.client.get('/api/messages', headers={'Authorization': header}).status_code, 401)
        self.assertEqual(self.client.get('/', headers=self.auth('wrong')).status_code, 401)
        self.assertEqual(self.client.get('/', headers=self.auth(user='wrong')).status_code, 401)
        self.assertEqual(self.client.get('/', headers={'X-Saathi-Gateway': 'x' * 64}).status_code, 401)

    def test_authenticated_actions_keep_confirmation_and_persistence(self):
        headers = {**self.auth(), 'Origin': 'https://saathi-test.up.railway.app'}
        self.assertEqual(self.client.get('/', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/static/app.js', headers=headers).status_code, 200)
        self.assertEqual(self.client.post('/api/messages', headers=headers, json={'sender': 'College', 'body': 'Kal meeting hai.'}).status_code, 201)
        self.assertEqual(self.client.get('/api/summary/latest', headers=headers).status_code, 200)
        review = self.client.post('/api/drafts', headers=headers, json={'recipient': 'Ravi', 'body': 'Main aaunga'})
        self.assertEqual(review.status_code, 202)
        self.assertEqual(self.client.get('/api/drafts', headers=headers).json(), [])
        token = review.json()['token']
        confirmed = self.client.post('/api/actions/confirm', headers=headers, json={'token': token})
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.json()['saved']); self.assertFalse(confirmed.json()['sent'])
        self.assertEqual(self.client.post('/api/actions/confirm', headers=headers, json={'token': token}).status_code, 409)
        due = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        reminder = self.client.post('/api/reminders', headers=headers, json={'note': 'paani', 'due_at': due}).json()
        self.assertEqual(self.client.get('/api/reminders', headers=headers).json(), [])
        self.assertEqual(self.client.post('/api/actions/confirm', headers=headers, json={'token': reminder['token']}).status_code, 200)
        server.init_db()  # Opening/initializing the same persistent file never clears records.
        self.assertEqual(len(self.client.get('/api/drafts', headers=headers).json()), 1)
        self.assertEqual(len(self.client.get('/api/reminders', headers=headers).json()), 1)

    def test_https_hosts_origins_and_security_headers_remain_enforced(self):
        headers = self.auth()
        self.assertEqual(self.client.get('http://saathi-test.up.railway.app/', headers={**headers, 'X-Forwarded-Proto': 'https'}).status_code, 403)
        self.assertEqual(self.client.get('https://attacker.example/', headers={**headers, 'X-Forwarded-Host': 'saathi-test.up.railway.app'}).status_code, 400)
        for origin_headers in [{'Origin': 'https://attacker.example'}, {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(self.client.post('/api/command', headers={**headers, **origin_headers}, json={'text': 'help'}).status_code, 403)
        response = self.client.get('/', headers=headers)
        self.assertEqual(response.headers['strict-transport-security'], 'max-age=31536000')
        self.assertIn("style-src 'self'", response.headers['content-security-policy'])
        self.assertIn('microphone=(self)', response.headers['permissions-policy'])
        self.assertEqual(self.client.get('http://healthcheck.railway.app/api/health').status_code, 200)
        self.assertEqual(self.client.get('https://healthcheck.railway.app/api/messages', headers=headers).status_code, 400)

    def test_configuration_fails_closed(self):
        for values in [{'SAATHI_AUTH_MODE': 'none'}, {'SAATHI_APP_PASSWORD_HASH': ''},
                       {'SAATHI_APP_PASSWORD_HASH': 'plaintext-password'}, {'SAATHI_DEMO_USER': ''},
                       {'SAATHI_ALLOWED_HOSTS': '*.up.railway.app'}, {'SAATHI_ALLOWED_HOSTS': 'https://example.org'},
                       {'SAATHI_SPEECH_PER_DAY': '0'}, {'SAATHI_SPEECH_PER_MINUTE': 'disabled'},
                       {'SAATHI_REQUESTS_PER_MINUTE': '-1'}, {'GNANI_API_KEY': ''}]:
            with self.subTest(keys=list(values)), patch.dict(os.environ, values), self.assertRaises(RuntimeError):
                server.validate_production_config()

    def test_railway_cannot_skip_volume_or_run_app_as_root(self):
        with patch.dict(os.environ, {'RAILWAY_ENVIRONMENT_ID': 'test-only-environment', 'RAILWAY_VOLUME_MOUNT_PATH': ''}), self.assertRaises(RuntimeError):
            server.validate_production_config()
        with patch.dict(os.environ, {'RAILWAY_ENVIRONMENT_ID': 'test-only-environment', 'RAILWAY_VOLUME_MOUNT_PATH': '/data', 'SAATHI_DB_PATH': '/data/saathi.db'}):
            with patch.object(os, 'geteuid', return_value=0, create=True), self.assertRaises(RuntimeError):
                server.validate_production_config()
            with patch.object(os, 'geteuid', return_value=10001, create=True):
                server.validate_production_config()

    def test_railway_cannot_fall_back_to_unprotected_development_mode(self):
        with patch.dict(os.environ, {'SAATHI_ENV': 'development', 'RAILWAY_ENVIRONMENT_ID': 'test-only-railway', 'RAILWAY_VOLUME_MOUNT_PATH': ''}):
            self.assertTrue(server.production_mode())
            with self.assertRaises(RuntimeError):
                server.validate_production_config()
            self.assertEqual(self.client.get('/api/messages').status_code, 401)

    def test_global_limits_ignore_spoofed_ip_headers(self):
        with patch.dict(os.environ, {'SAATHI_REQUESTS_PER_MINUTE': '2'}):
            for index in range(2):
                self.assertEqual(self.client.get('/', headers={**self.auth(), 'X-Forwarded-For': str(index)}).status_code, 200)
            response = self.client.get('/', headers={**self.auth(), 'X-Forwarded-For': 'different'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['retry-after'], '60')
            self.assertEqual(self.client.get('/api/health').status_code, 200)

    def test_authentication_failures_are_throttled(self):
        with patch.dict(os.environ, {'SAATHI_AUTH_FAILURES_PER_MINUTE': '2'}):
            for _ in range(2):
                self.assertEqual(self.client.get('/', headers=self.auth('incorrect')).status_code, 401)
            self.assertEqual(self.client.get('/', headers=self.auth()).status_code, 429)
            # Advancing the clock to the next fixed minute permits recovery.
            with patch('demo_security.time.monotonic', return_value=10**12):
                self.assertEqual(self.client.get('/', headers=self.auth()).status_code, 200)

    def test_speech_quotas_prevent_provider_calls_and_survive_restart(self):
        with patch.dict(os.environ, {'SAATHI_SPEECH_PER_MINUTE': '1'}), patch.object(server.gnani, 'synthesize', side_effect=HTTPException(502, 'Test provider failure')) as provider:
            response = self.client.post('/api/tts', headers=self.auth(), json={'text': 'Namaste'})
            self.assertEqual(response.status_code, 502)
            server.init_db()
            server.app.state.request_limits = demo_security.RequestLimits()
            blocked = self.client.post('/api/tts', headers=self.auth(), json={'text': 'Namaste'})
            self.assertEqual(blocked.status_code, 429)
            self.assertIn('retry-after', blocked.headers)
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(self.client.post('/api/command', headers=self.auth(), json={'text': 'help'}).status_code, 200)

    def test_daily_budget_and_concurrent_reservations_are_atomic(self):
        with patch.dict(os.environ, {'SAATHI_SPEECH_PER_DAY': '2'}), patch('app.time.time', return_value=1700000000):
            def reserve(_):
                try:
                    server.reserve_speech_request()
                    return 200
                except HTTPException as error:
                    return error.status_code
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sorted(pool.map(reserve, range(4))), [200, 200, 429, 429])
            with patch('app.time.time', return_value=1700000120), self.assertRaises(HTTPException) as error:
                server.reserve_speech_request()
            self.assertEqual(error.exception.status_code, 429)
            with patch('app.time.time', return_value=1700086400):
                server.reserve_speech_request()

    def test_database_failure_cannot_allow_paid_call(self):
        with patch.object(server, 'DB', Path(self.temp.name) / 'missing' / 'database.db'), patch.object(server.gnani, 'synthesize') as provider:
            self.assertEqual(self.client.post('/api/tts', headers=self.auth(), json={'text': 'Namaste'}).status_code, 503)
            provider.assert_not_called()

    def test_declared_and_streamed_oversized_bodies_are_rejected(self):
        response = self.client.post('/api/tts', headers={**self.auth(), 'Content-Length': str(demo_security.MAX_BODY + 1)}, content=b'x')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        def chunks():
            for _ in range(10):
                yield b'x' * (1024 * 1024)
        with patch.object(server.gnani, 'synthesize') as provider:
            response = self.client.post('/api/tts', headers={**self.auth(), 'Content-Type': 'application/json'}, content=chunks())
            self.assertEqual(response.status_code, 413)
            provider.assert_not_called()


class TestRailwayEntrypoint(unittest.TestCase):
    def test_port_single_worker_and_proxy_trust_are_explicit(self):
        with patch.dict(os.environ, {'PORT': '9182', 'FORWARDED_ALLOW_IPS': '*'}):
            command = serve.command()
            self.assertEqual(command[command.index('--port') + 1], '9182')
            self.assertEqual(command[command.index('--workers') + 1], '1')
            self.assertEqual(command[command.index('--forwarded-allow-ips') + 1], '*')
        for value in ['0', '65536', 'not-a-port']:
            with patch.dict(os.environ, {'PORT': value}), self.assertRaises(RuntimeError):
                serve.command()

    def test_root_startup_is_restricted_and_drops_all_privileges(self):
        with patch.dict(os.environ, {'RAILWAY_RUN_UID': '0', 'RAILWAY_VOLUME_MOUNT_PATH': '/data', 'SAATHI_DB_PATH': '/data/saathi.db'}), \
             patch.object(os, 'geteuid', side_effect=[0, serve.UID], create=True), \
             patch.object(serve, 'own_volume') as own, patch.object(os, 'setgroups', create=True) as groups, \
             patch.object(os, 'setgid', create=True) as gid, patch.object(os, 'setuid', create=True) as uid, \
             patch.object(os, 'access', return_value=True), patch.object(os, 'umask'):
            serve.prepare_storage()
            own.assert_called_once_with(Path('/data'))
            groups.assert_called_once_with([]); gid.assert_called_once_with(10001); uid.assert_called_once_with(10001)
        with patch.dict(os.environ, {'RAILWAY_RUN_UID': '', 'RAILWAY_VOLUME_MOUNT_PATH': '/data', 'SAATHI_DB_PATH': '/data/saathi.db'}), \
             patch.object(os, 'geteuid', return_value=0, create=True), self.assertRaises(RuntimeError):
            serve.prepare_storage()

    def test_wrong_mount_or_unwritable_storage_fails(self):
        with patch.dict(os.environ, {'RAILWAY_VOLUME_MOUNT_PATH': '/wrong', 'SAATHI_DB_PATH': '/data/saathi.db'}), self.assertRaises(RuntimeError):
            serve.prepare_storage()
        with patch.dict(os.environ, {'RAILWAY_VOLUME_MOUNT_PATH': '/data', 'SAATHI_DB_PATH': '/data/saathi.db'}), \
             patch.object(os, 'geteuid', return_value=10001, create=True), patch.object(os, 'access', return_value=False), \
             patch.object(os, 'umask'), self.assertRaises(RuntimeError):
            serve.prepare_storage()

    def test_railway_config_preserves_dockerfile_and_healthcheck(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'railway.json').read_text())
        self.assertEqual(config['build']['builder'], 'DOCKERFILE')
        self.assertEqual(config['deploy']['healthcheckPath'], '/api/health')
        self.assertNotIn('startCommand', config['deploy'])


if __name__ == '__main__':
    unittest.main()
