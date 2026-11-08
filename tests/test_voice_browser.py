"""Opt-in, billed Chrome voice acceptance tests with REAL Gnani HTTP calls.

Chrome uses a test-only virtual microphone fed genuine Timbre-generated WAVs.
MediaRecorder, browser resampling, backend STT, intents, confirmation, SQLite and
browser TTS playback are real. This does NOT verify physical microphone/speakers.
No route interception, fabricated provider responses or production demo mode.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.getenv('SAATHI_VOICE_E2E') == '1', 'Set SAATHI_VOICE_E2E=1 to opt in to billed real Gnani + Chrome virtual-microphone tests')
class TestRealVoiceChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        import gnani
        load_dotenv(ROOT / '.env')
        if not gnani.configuration()['key']:
            raise RuntimeError('GNANI_API_KEY is required in the server .env')
        cls.artifacts = ROOT / 'test-results' / 'live-voice'
        cls.artifacts.mkdir(parents=True, exist_ok=True)
        cls.fixtures = {}
        for name, text, language in [
            ('read', 'मेरा संदेश पढ़ो।', 'hi-IN'),
            ('draft', 'Ravi ko message likho, main kal aaunga.', 'hi-en'),
            ('confirm', 'हाँ।', 'hi-IN'),
            ('reminder', 'पाँच मिनट बाद पानी पीना याद दिलाना।', 'hi-IN'),
        ]:
            filename = cls.artifacts / f'chrome-input-{name}.wav'
            filename.write_bytes(gnani.synthesize(text, language))
            cls.fixtures[name] = filename
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        cls.log = (Path(cls.temp.name) / 'server.log').open('w', encoding='utf-8')
        env = {**os.environ, 'SAATHI_DB_PATH': str(Path(cls.temp.name) / 'voice.db')}
        cls.server = subprocess.Popen(
            [sys.executable, '-B', '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log,
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        cls.http = requests.Session()
        cls.http.trust_env = False
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if cls.server.poll() is not None:
                    raise RuntimeError('Voice test backend failed to start')
                try:
                    if cls.http.get(cls.base + '/api/health', timeout=1).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.05)
            else:
                raise RuntimeError('Voice backend startup timed out')
            cls.pw = sync_playwright().start()
            cls.evidence = []
        except Exception:
            cls.server.terminate()
            cls.server.wait(timeout=10)
            cls.http.close()
            cls.log.close()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.pw.stop()
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.http.close()
        cls.log.close()
        cls.temp.cleanup()
        report = cls.artifacts / 'chrome-voice-evidence.json'
        if report.exists():
            report = cls.artifacts / f'chrome-voice-evidence-{time.time_ns()}.json'
        report.write_text(json.dumps({
            'input_source': 'Genuine Gnani Timbre audio through Chrome virtual microphone',
            'physical_microphone_verified': False,
            'checks': cls.evidence,
        }, indent=2), encoding='utf-8')

    def open_voice_page(self, fixture):
        from playwright.sync_api import expect
        browser = self.pw.chromium.launch(channel=os.getenv('SAATHI_BROWSER_CHANNEL', 'chrome'), args=[
            '--use-fake-device-for-media-stream',
            f'--use-file-for-fake-audio-capture={self.fixtures[fixture]}',
        ])
        self.addCleanup(browser.close)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        context.grant_permissions(['microphone'], origin=self.base)
        page = context.new_page()
        self.page_errors = []
        page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        self.requests_seen = []
        page.on('response', lambda response: self.requests_seen.append((response.url.split('?')[0].rsplit('/', 1)[-1], response.status)) if '/api/' in response.url else None)
        page.goto(self.base)
        expect(page.locator('#apiStatus')).to_contain_text('key configured')
        return page

    def record(self, page, fixture, button='#startTalk'):
        from playwright.sync_api import expect
        with wave.open(str(self.fixtures[fixture]), 'rb') as clip:
            duration = clip.getnframes() / clip.getframerate()
        page.locator(button).click()
        expect(page.locator(button)).to_have_attribute('aria-pressed', 'true')
        # Recording real browser MediaRecorder output needs actual elapsed audio time.
        page.wait_for_timeout(int((duration + 0.3) * 1000))
        with page.expect_response(lambda response: response.url.endswith('/api/stt'), timeout=90000) as speech:
            page.locator(button).click()
        self.assertEqual(speech.value.status, 200, 'Real Prisma endpoint must succeed')
        self.assertTrue(speech.value.json()['transcript'].strip())

    def wait_spoken(self, page):
        from playwright.sync_api import expect
        expect(page.locator('#voiceStatus')).to_have_text('Spoken response finished.', timeout=90000)
        self.assertTrue(page.locator('#playback').evaluate('audio => audio.ended && audio.duration > 0'))
        expect(page.locator('#error')).to_be_hidden()
        self.assertEqual(self.page_errors, [])

    def evidence_pass(self, name):
        self.evidence.append({'name': name, 'status': 'VERIFIED', 'api_statuses': self.requests_seen})

    def test_hindi_read_and_summary_with_real_playback(self):
        from playwright.sync_api import expect
        response = self.http.post(self.base + '/api/messages', json={'sender': 'Voice acceptance test', 'body': 'कल शाम चार बजे बैठक है। कृपया जवाब दें।'}, timeout=5)
        self.assertEqual(response.status_code, 201)
        page = self.open_voice_page('read')
        self.record(page, 'read')
        expect(page.locator('#reply')).to_contain_text('Voice acceptance test', timeout=10000)
        self.wait_spoken(page)
        page.locator('#summarize').click()
        expect(page.locator('#reply')).to_contain_text('Key details', timeout=10000)
        self.wait_spoken(page)
        page.screenshot(path=str(self.artifacts / 'chrome-real-read.png'), full_page=True)
        expect(page.locator('#apiStatus')).to_contain_text('Prisma + Timbre')
        # Safe public assets: this page uses only the disposable example inbox above.
        screenshots = ROOT / 'docs' / 'screenshots'
        screenshots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshots / 'desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(screenshots / 'mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1280, 'height': 900})
        self.evidence_pass('Hindi virtual microphone → MediaRecorder → Prisma → read/summary → Timbre → Chrome playback')

    def test_hinglish_draft_requires_confirmation_before_save(self):
        from playwright.sync_api import expect
        page = self.open_voice_page('draft')
        before = len(self.http.get(self.base + '/api/drafts', timeout=5).json())
        self.record(page, 'draft')
        expect(page.locator('#confirmHeading')).to_have_text('Review your draft', timeout=10000)
        self.assertEqual(len(self.http.get(self.base + '/api/drafts', timeout=5).json()), before)
        self.wait_spoken(page)
        page.locator('#confirmAction').click()
        expect(page.locator('#confirmDialog')).not_to_be_visible()
        self.wait_spoken(page)
        self.assertEqual(len(self.http.get(self.base + '/api/drafts', timeout=5).json()), before + 1)
        self.evidence_pass('Hinglish virtual microphone → Prisma → draft preview → explicit confirmation → SQLite → Timbre playback')

    def test_hindi_reminder_and_completion(self):
        from playwright.sync_api import expect
        page = self.open_voice_page('reminder')
        before = len(self.http.get(self.base + '/api/reminders', timeout=5).json())
        self.record(page, 'reminder')
        expect(page.locator('#confirmHeading')).to_have_text('Review your reminder', timeout=10000)
        self.assertEqual(len(self.http.get(self.base + '/api/reminders', timeout=5).json()), before)
        self.wait_spoken(page)
        page.locator('#confirmAction').click()
        expect(page.locator('#confirmDialog')).not_to_be_visible()
        self.wait_spoken(page)
        self.assertEqual(len(self.http.get(self.base + '/api/reminders', timeout=5).json()), before + 1)
        page.get_by_role('button', name='Mark reminder done:', exact=False).first.click()
        expect(page.locator('#confirmHeading')).to_have_text('Complete reminder?')
        self.wait_spoken(page)
        page.locator('#confirmAction').click()
        expect(page.locator('#confirmDialog')).not_to_be_visible()
        self.wait_spoken(page)
        self.assertTrue(any(item['done'] for item in self.http.get(self.base + '/api/reminders', timeout=5).json()))
        self.evidence_pass('Hindi virtual microphone → Prisma → parsed reminder → confirmation → completion → Timbre playback')

    def test_spoken_haan_confirms_only_the_current_draft(self):
        from playwright.sync_api import expect
        page = self.open_voice_page('confirm')
        before = len(self.http.get(self.base + '/api/drafts', timeout=5).json())
        page.locator('#transcript').fill('Ravi ko message likho, main aaunga')
        page.locator('#runCommand').click()
        expect(page.locator('#confirmHeading')).to_have_text('Review your draft', timeout=10000)
        self.wait_spoken(page)
        self.record(page, 'confirm', '#confirmVoice')
        expect(page.locator('#confirmDialog')).not_to_be_visible(timeout=10000)
        self.wait_spoken(page)
        self.assertEqual(len(self.http.get(self.base + '/api/drafts', timeout=5).json()), before + 1)
        self.evidence_pass('Current draft preview → Hindi haan virtual microphone → Prisma → confirm → saved draft → Timbre playback')

    def test_timed_reminder_poll_announces_real_timbre_audio(self):
        from playwright.sync_api import expect
        page = self.open_voice_page('read')
        # User interaction enables ordinary Chrome playback; no autoplay bypass flag.
        page.locator('#stopSpeech').click()
        note = 'पानी पीने का समय है।'
        due = (datetime.now(timezone.utc) + timedelta(seconds=12)).isoformat()
        response = self.http.post(self.base + '/api/reminders', json={'note': note, 'due_at': due}, timeout=5)
        self.assertEqual(response.status_code, 202)
        response = self.http.post(self.base + '/api/actions/confirm', json={'token': response.json()['token']}, timeout=5)
        self.assertEqual(response.status_code, 200)
        expect(page.locator('#reply')).to_contain_text(note, timeout=45000)
        self.wait_spoken(page)
        self.evidence_pass('Real future reminder → actual 10-second polling → due alert → Timbre → Chrome playback')


if __name__ == '__main__':
    unittest.main()
