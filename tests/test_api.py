import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from saathi import app as server


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(server, 'DB', Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.client = TestClient(server.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp.cleanup()

    def future(self):
        return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    def draft_review(self, body='Main kal aaunga'):
        response = self.client.post('/api/drafts', json={'recipient': 'Ravi', 'body': body})
        self.assertEqual(response.status_code, 202)
        return response.json()

    def confirm(self, token):
        return self.client.post('/api/actions/confirm', json={'token': token})

    def test_inbox_read_summary_flow(self):
        self.assertEqual(self.client.get('/api/messages').json(), [])
        self.assertEqual(self.client.get('/api/summary/latest').status_code, 404)
        response = self.client.post('/api/messages', json={'sender': 'College', 'body': 'कल 4 बजे meeting है। Please confirm.'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get('/api/messages').json()[0]['sender'], 'College')
        summary = self.client.get('/api/summary/latest').json()
        self.assertEqual(summary['method'], 'extractive')
        self.assertIn('4', ' '.join(summary['bullets']))
        self.assertEqual(len(self.client.get('/api/summary').json()), 1)

    def test_review_does_not_save(self):
        review = self.draft_review()
        self.assertTrue(review['requires_confirmation'])
        self.assertEqual(review['preview']['recipient'], 'Ravi')
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_confirm_draft_once_never_sent(self):
        review = self.draft_review()
        saved = self.confirm(review['token'])
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.json()['saved'])
        self.assertFalse(saved.json()['sent'])
        self.assertEqual(self.confirm(review['token']).status_code, 409)
        self.assertEqual(len(self.client.get('/api/drafts').json()), 1)

    def test_cancel_and_replay(self):
        review = self.draft_review()
        self.assertEqual(self.client.post('/api/actions/cancel', json={'token': review['token']}).status_code, 200)
        self.assertEqual(self.confirm(review['token']).status_code, 409)
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_expired_review(self):
        review = self.draft_review()
        with server.db() as connection:
            connection.execute('UPDATE pending_actions SET expires_at=?', ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
        self.assertEqual(self.confirm(review['token']).status_code, 410)
        self.assertEqual(self.client.get('/api/drafts').json(), [])

    def test_confirmation_uses_frozen_payload(self):
        review = self.draft_review('Original reply')
        tamper = self.client.post('/api/actions/confirm', json={'token': review['token'], 'body': 'Changed reply'})
        self.assertEqual(tamper.status_code, 422)
        self.assertEqual(self.confirm(review['token']).status_code, 200)
        self.assertEqual(self.client.get('/api/drafts').json()[0]['body'], 'Original reply')

    def test_concurrent_confirmation_cannot_duplicate(self):
        token = self.draft_review()['token']
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self.confirm(token).status_code, range(2)))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(len(self.client.get('/api/drafts').json()), 1)

    def test_reminder_review_confirm_complete(self):
        review = self.client.post('/api/reminders', json={'note': 'Drink water', 'due_at': self.future()}).json()
        self.assertEqual(self.client.get('/api/reminders').json(), [])
        saved = self.confirm(review['token']).json()
        items = self.client.get('/api/reminders').json()
        self.assertEqual(items[0]['done'], 0)
        complete = self.client.patch(f"/api/reminders/{saved['id']}/done").json()
        self.assertEqual(self.client.get('/api/reminders').json()[0]['done'], 0)
        self.assertEqual(self.confirm(complete['token']).status_code, 200)
        self.assertEqual(self.client.get('/api/reminders').json()[0]['done'], 1)

    def test_time_rechecked_at_confirmation(self):
        now = datetime.now(timezone.utc)
        review = self.client.post('/api/reminders', json={'note': 'Task', 'due_at': (now + timedelta(seconds=60)).isoformat()}).json()
        with patch.object(server, 'now_utc', return_value=now + timedelta(seconds=120)):
            self.assertEqual(self.confirm(review['token']).status_code, 400)
        self.assertEqual(self.client.get('/api/reminders').json(), [])

    def test_invalid_reminder_times(self):
        for due in ['2020-01-01T12:00:00Z', '2099-01-01T12:00:00', 'not a date']:
            with self.subTest(due=due):
                self.assertIn(self.client.post('/api/reminders', json={'note': 'Task', 'due_at': due}).status_code, {400, 422})

    def test_whitespace_and_extra_fields_rejected(self):
        for path, payload in [('/api/messages', {'sender': ' ', 'body': 'Hi'}), ('/api/drafts', {'recipient': 'Ravi', 'body': '  '}), ('/api/command', {'text': '  '}), ('/api/tts', {'text': ' ', 'api_key': 'forbidden'})]:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json=payload).status_code, 422)

    def test_commands_do_not_write(self):
        command = self.client.post('/api/command', json={'text': 'Ravi ko message likho main kal aaunga'}).json()
        self.assertEqual(command['intent'], 'draft')
        self.assertEqual(command['recipient'], 'Ravi')
        self.assertEqual(self.client.get('/api/drafts').json(), [])
        reminder = self.client.post('/api/command', json={'text': '5 minute baad paani peena yaad dilana'}).json()
        self.assertEqual(reminder['intent'], 'reminder')
        self.assertIsNotNone(reminder['reminder']['due_at'])
        self.assertEqual(self.client.get('/api/reminders').json(), [])

    def test_no_frontend_secrets_or_false_health(self):
        with patch.dict('os.environ', {'GNANI_API_KEY': 'private-test-key'}):
            response = self.client.get('/api/health')
            self.assertNotIn('private-test-key', response.text)
            self.assertFalse(response.json()['connection_verified'])
        self.assertEqual(self.client.get('/.env').status_code, 404)

    def test_security_headers_and_cross_origin(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn("script-src 'self'", response.headers['content-security-policy'])
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.post('/api/command', json={'text': 'help'}, headers={'Origin': 'https://other.example'}).status_code, 403)

    def test_storage_failure_not_success(self):
        import sqlite3
        with patch.object(server, 'db', side_effect=sqlite3.OperationalError('test failure')):
            response = self.client.post('/api/messages', json={'sender': 'Ravi', 'body': 'Hi'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('id', response.json())

    def test_unknown_confirmation(self):
        self.assertEqual(self.confirm('x' * 43).status_code, 409)
        self.assertEqual(self.client.patch('/api/reminders/999/done').status_code, 404)


if __name__ == '__main__':
    unittest.main()
