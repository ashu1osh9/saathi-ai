"""Demo acceptance checks against a real local HTTP server and disposable database.

No provider fixtures: missing-key speech operations must return honest errors.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


class TestDemoHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            cls.port = probe.getsockname()[1]
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.log_path = Path(cls.temp.name) / 'server.log'
        cls.log = cls.log_path.open('w', encoding='utf-8')
        env = {**os.environ, 'GNANI_API_KEY': '', 'SAATHI_DB_PATH': str(Path(cls.temp.name) / 'demo.db')}
        cls.server = subprocess.Popen(
            [sys.executable, '-B', '-m', 'uvicorn', 'saathi.app:app', '--host', '127.0.0.1', '--port', str(cls.port)],
            cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log,
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        cls.session = requests.Session()
        cls.session.trust_env = False
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if cls.server.poll() is not None:
                    raise RuntimeError('Demo server failed to start: ' + cls.log_path.read_text(encoding='utf-8'))
                try:
                    if cls.session.get(cls.base + '/api/health', timeout=1).ok:
                        return
                except requests.RequestException:
                    pass
                time.sleep(0.05)
            raise RuntimeError('Demo server did not become ready within 20 seconds')
        except Exception:
            cls.cleanup_server()
            raise

    @classmethod
    def cleanup_server(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
            cls.server.wait(timeout=10)
        cls.session.close()
        cls.log.close()
        cls.temp.cleanup()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_server()

    def call(self, method, path, expected=200, **kwargs):
        response = self.session.request(method, self.base + path, timeout=10, **kwargs)
        self.assertEqual(response.status_code, expected, f'{method} {path}: {response.text[:500]}')
        return response

    def test_demo_message_summary_draft_confirmation_and_reminder(self):
        message = 'कल शाम 4 बजे बैठक है। Please confirm attendance.'
        self.call('POST', '/api/messages', expected=201, json={'sender': 'Demo college office', 'body': message})
        intent = self.call('POST', '/api/command', json={'text': 'मेरा संदेश पढ़ो'}).json()
        self.assertEqual(intent['intent'], 'read')
        self.assertEqual(self.call('GET', '/api/messages').json()[0]['body'], message)
        summary = self.call('GET', '/api/summary/latest').json()
        self.assertEqual(summary['method'], 'extractive')
        self.assertIn('4', ' '.join(summary['bullets']))

        draft = self.call('POST', '/api/command', json={'text': 'Ravi ko message likho, main kal aaunga'}).json()
        self.assertEqual(draft['intent'], 'draft')
        review = self.call('POST', '/api/drafts', expected=202, json={'recipient': draft['recipient'], 'body': draft['draft_text']}).json()
        self.assertEqual(self.call('GET', '/api/drafts').json(), [])
        self.call('POST', '/api/actions/cancel', json={'token': review['token']})
        self.call('POST', '/api/actions/confirm', expected=409, json={'token': review['token']})
        review = self.call('POST', '/api/drafts', expected=202, json={'recipient': draft['recipient'], 'body': draft['draft_text']}).json()
        confirmation = self.call('POST', '/api/command', json={'text': 'हाँ'}).json()
        self.assertEqual(confirmation['intent'], 'confirm')
        saved = self.call('POST', '/api/actions/confirm', json={'token': review['token']}).json()
        self.assertTrue(saved['saved'])
        self.assertFalse(saved['sent'])
        self.assertEqual(self.call('GET', '/api/drafts').json()[0]['body'], 'main kal aaunga')

        reminder = self.call('POST', '/api/command', json={'text': '5 minute baad paani peena yaad dilana'}).json()['reminder']
        self.assertEqual(reminder['note'], 'paani peena')
        self.assertGreater(datetime.fromisoformat(reminder['due_at']), datetime.now(timezone.utc))
        review = self.call('POST', '/api/reminders', expected=202, json={'note': reminder['note'], 'due_at': reminder['due_at']}).json()
        self.assertEqual(self.call('GET', '/api/reminders').json(), [])
        saved = self.call('POST', '/api/actions/confirm', json={'token': review['token']}).json()
        self.call('POST', '/api/actions/confirm', expected=409, json={'token': review['token']})
        self.assertEqual(len(self.call('GET', '/api/reminders').json()), 1)
        complete = self.call('PATCH', f"/api/reminders/{saved['id']}/done", expected=202).json()
        self.call('POST', '/api/actions/confirm', json={'token': complete['token']})
        self.assertEqual(self.call('GET', '/api/reminders').json()[0]['done'], 1)

    def test_real_server_serves_frontend_and_security_headers(self):
        response = self.call('GET', '/')
        self.assertIn('id="startTalk"', response.text)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        for path in ['/static/app.js', '/static/audio.js', '/static/styles.css']:
            self.assertGreater(len(self.call('GET', path).content), 100)
        self.call('GET', '/.env', expected=404)
        self.call('POST', '/api/command', expected=403, json={'text': 'help'}, headers={'Origin': 'https://other.example'})

    def test_speech_without_credentials_reports_unavailable_not_success(self):
        health = self.call('GET', '/api/health').json()
        self.assertFalse(health['gnani_configured'])
        self.assertFalse(health['connection_verified'])
        response = self.call('POST', '/api/tts', expected=503, json={'text': 'नमस्ते'})
        self.assertIn('GNANI_API_KEY', response.json()['detail'])
        output = BytesIO()
        with wave.open(output, 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b'\0\0' * 1600)
        response = self.call('POST', '/api/stt', expected=503, files={'audio': ('test.wav', output.getvalue(), 'audio/wav')})
        self.assertNotIn('transcript', response.json())


if __name__ == '__main__':
    unittest.main()
