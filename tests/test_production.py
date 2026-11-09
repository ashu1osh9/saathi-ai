"""Production gateway guards, persistence and release hygiene; no live API calls."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from saathi import app as server


class TestProductionGateway(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(server, 'DB', Path(self.temp.name) / 'persistent' / 'saathi.db')
        self.db_patch.start()
        self.env = patch.dict(os.environ, {'SAATHI_ENV': 'production', 'SAATHI_ALLOWED_HOSTS': 'demo.example.org',
                                           'SAATHI_PROXY_TOKEN': 'unit-test-gateway-' + 'x' * 32, 'GNANI_API_KEY': 'unit-test-only'})
        self.env.start()
        self.client = TestClient(server.app, base_url='https://demo.example.org')
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def headers(self):
        return {'X-Saathi-Gateway': os.environ['SAATHI_PROXY_TOKEN']}

    def test_startup_fails_closed_for_incomplete_config(self):
        for override in [{'SAATHI_ALLOWED_HOSTS': ''}, {'SAATHI_ALLOWED_HOSTS': '*'}, {'SAATHI_PROXY_TOKEN': ''}, {'GNANI_API_KEY': ''}]:
            with self.subTest(keys=list(override)), patch.dict(os.environ, override), self.assertRaises(RuntimeError):
                server.validate_production_config()

    def test_direct_backend_cannot_read_or_use_paid_speech(self):
        for path in ['/', '/static/app.js', '/api/messages', '/api/drafts', '/api/reminders']:
            self.assertEqual(self.client.get(path).status_code, 403)
        response = self.client.post('/api/tts', json={'text': 'नमस्ते'})
        self.assertEqual(response.status_code, 403)

    def test_https_gateway_preserves_same_origin_mutations(self):
        response = self.client.post('/api/messages', headers={**self.headers(), 'Origin': 'https://demo.example.org'}, json={'sender': 'Demo', 'body': 'Namaste'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers['strict-transport-security'], 'max-age=31536000')
        self.assertIn('microphone=(self)', response.headers['permissions-policy'])
        self.assertEqual(self.client.get('/api/messages', headers=self.headers()).json()[0]['body'], 'Namaste')
        self.assertEqual(self.client.post('/api/command', headers={**self.headers(), 'Origin': 'https://other.example'}, json={'text': 'help'}).status_code, 403)

    def test_insecure_transport_and_unexpected_hosts_are_rejected(self):
        self.assertEqual(self.client.get('http://demo.example.org/api/messages', headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.get('https://other.example/api/messages', headers=self.headers()).status_code, 400)
        self.assertEqual(self.client.get('/api/messages', headers={'X-Saathi-Gateway': 'wrong'}).status_code, 403)

    def test_private_database_survives_a_second_connection(self):
        self.assertTrue(server.DB.parent.is_dir())
        with server.db() as connection:
            connection.execute("INSERT INTO messages(sender,body,created_at) VALUES ('Demo','Persistent','2026-11-08T00:00:00Z')")
        with server.db() as connection:
            self.assertEqual(connection.execute('SELECT body FROM messages').fetchone()[0], 'Persistent')

    def test_health_is_available_for_container_check_without_secrets(self):
        response = self.client.get('http://127.0.0.1/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(os.environ['SAATHI_PROXY_TOKEN'], response.text)
        self.assertNotIn(os.environ['GNANI_API_KEY'], response.text)


@unittest.skipUnless(shutil.which('git'), 'Git is required to verify ignore rules')
class TestReleaseExclusions(unittest.TestCase):
    def test_real_git_ignore_rules_exclude_private_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            subprocess.run(['git', 'init', '--quiet', str(directory)], check=True, capture_output=True)
            shutil.copy2(root / '.gitignore', directory / '.gitignore')
            private = ['.env', '.env.production', '.venv/Lib/private.py', '.python/python.exe', 'saathi.db', 'personal.sqlite3', 'data/inbox.json', 'backups/private.db', 'recordings/command.wav', 'test-results/live-voice/audio.wav', 'logs/server.log', '.cache/data', 'private/messages.json', 'uploads/audio.webm', 'build/lib/saathi/app.py', 'src/saathi_ai.egg-info/PKG-INFO', 'dist/package.whl']
            result = subprocess.run(['git', '-C', str(directory), 'check-ignore', '--no-index', '-z', '--stdin'], input=('\0'.join(private) + '\0').encode(), capture_output=True)
            self.assertEqual(set(result.stdout.decode().rstrip('\0').split('\0')), set(private))
            public = ['.env.example', '.env.production.example', 'README.md', 'Dockerfile', 'docs/screenshots/desktop.png', 'pyproject.toml', 'src/saathi/app.py', 'src/saathi/static/index.html']
            result = subprocess.run(['git', '-C', str(directory), 'check-ignore', '--no-index', '-z', '--stdin'], input=('\0'.join(public) + '\0').encode(), capture_output=True)
            self.assertEqual(result.stdout, b'')

    def test_docker_copies_only_explicit_application_source(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / 'Dockerfile').read_text(encoding='utf-8')
        self.assertNotIn('COPY . ', dockerfile)
        self.assertIn('USER 10001:10001', dockerfile)
        self.assertIn('!requirements.lock', (root / '.dockerignore').read_text())
        self.assertIn('COPY src/ ./src/', dockerfile)
        self.assertIn('"saathi.serve"', dockerfile)
        self.assertNotIn('env_file:', (root / 'compose.yaml').read_text())


if __name__ == '__main__':
    unittest.main()
