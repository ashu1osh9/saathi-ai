"""Opt-in browser flows against the actual FastAPI server and a disposable SQLite DB.

No HTTP interception, provider fixtures, or simulated API success. Speech remains
honestly unavailable without credentials; real provider calls are a separate opt-in.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.getenv('SAATHI_E2E') == '1', 'Install requirements-e2e.txt and set SAATHI_E2E=1 to run actual browser flows')
class TestBrowserFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'SAATHI_DB_PATH': str(Path(cls.temp.name) / 'browser.db'), 'GNANI_API_KEY': ''}
        cls.log = open(Path(cls.temp.name) / 'server.log', 'w')
        cls.server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log, creationflags=0x08000000 if os.name == 'nt' else 0)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if cls.server.poll() is not None:
                    raise RuntimeError('Test backend failed to start')
                try:
                    if requests.get(cls.base + '/api/health', timeout=1).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError('Test backend startup timed out')
            cls.pw = sync_playwright().start()
            channel = os.getenv('SAATHI_BROWSER_CHANNEL')
            cls.browser = cls.pw.chromium.launch(**({'channel': channel} if channel else {}))
        except Exception:
            cls.server.terminate()
            cls.server.wait(timeout=10)
            cls.log.close()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.log.close()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.base)
        self.page.locator('#apiStatus').filter(has_text='Text mode').wait_for()
        self.page.locator('#autoSpeak').uncheck()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def command(self, text):
        self.page.locator('#transcript').fill(text)
        self.page.locator('#transcript').press('Control+Enter')

    def test_actual_read_summary_draft_and_reminder_flow(self):
        from playwright.sync_api import expect
        page = self.page
        page.locator('#sender').fill('College office')
        page.locator('#newMessage').fill('कल शाम 4 बजे meeting है। Please confirm attendance.')
        page.locator('#addMessage button').click()
        expect(page.locator('#inboxList')).to_contain_text('College office')
        self.command('Mera message padho')
        expect(page.locator('#reply')).to_contain_text('meeting')
        page.locator('#summarize').click()
        expect(page.locator('#status')).to_contain_text('Extractive')
        self.command('Ravi ko message likho, main kal aaunga')
        expect(page.locator('#confirmDialog')).to_be_visible()
        expect(page.locator('#cancelAction')).to_be_focused()
        page.keyboard.press('Shift+Tab')
        expect(page.locator('#dialogStop')).to_be_focused()
        page.keyboard.press('Tab')
        expect(page.locator('#cancelAction')).to_be_focused()
        self.assertEqual(requests.get(self.base + '/api/drafts', timeout=5).json(), [])
        page.locator('#cancelAction').click()
        expect(page.locator('#confirmDialog')).not_to_be_visible()
        self.command('Ravi ko message likho, main kal aaunga')
        page.locator('#confirmAction').click()
        expect(page.locator('#draftList')).to_contain_text('main kal aaunga')
        self.assertEqual(len(requests.get(self.base + '/api/drafts', timeout=5).json()), 1)
        self.command('5 minute baad paani peena yaad dilana')
        expect(page.locator('#confirmPreview')).to_contain_text('paani peena')
        page.locator('#confirmAction').click()
        expect(page.locator('#reminderList')).to_contain_text('paani peena')
        page.get_by_role('button', name='Mark reminder done: paani peena').click()
        expect(page.locator('#confirmHeading')).to_have_text('Complete reminder?')
        page.locator('#confirmAction').click()
        expect(page.locator('#reminderList')).to_contain_text('Done')

    def test_keyboard_preferences_mobile_and_honest_speech_failure(self):
        from playwright.sync_api import expect
        page = self.page
        page.reload()
        page.keyboard.press('Tab')
        expect(page.get_by_role('link', name='Skip to main content')).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#main')).to_be_focused()
        page.locator('#contrastBtn').click()
        expect(page.locator('#contrastBtn')).to_have_attribute('aria-pressed', 'true')
        page.locator('#sizeBtn').click()
        self.assertEqual(page.locator('html').evaluate('e => getComputedStyle(e).fontSize'), '20px')
        for label in ['Sender name', 'Message', 'Recipient', 'Your reply', 'Remind me about', 'Date & time on this device']:
            self.assertEqual(page.get_by_label(label, exact=True).count(), 1, f'Missing unique accessible label: {label}')
        self.assertEqual(page.get_by_role('checkbox', name='Speak responses automatically').count(), 1)
        self.assertEqual(page.locator('#playback').get_attribute('aria-label'), 'Saathi spoken response')
        for width in [320, 390, 768, 1440]:
            page.set_viewport_size({'width': width, 'height': 1000})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), f'Horizontal overflow at {width}px')
        page.reload()
        expect(page.locator('#contrastBtn')).to_have_attribute('aria-pressed', 'true')
        expect(page.locator('#sizeBtn')).to_have_attribute('aria-pressed', 'true')
        page.locator('#replay').click()
        expect(page.locator('#voiceStatus')).to_contain_text('unavailable')
        self.assertFalse(requests.get(self.base + '/api/health', timeout=5).json()['connection_verified'])
        output = ROOT / 'test-results'
        output.mkdir(exist_ok=True)
        page.screenshot(path=str(output / 'accessible-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(output / 'accessible-mobile.png'), full_page=True)


if __name__ == '__main__':
    unittest.main()
