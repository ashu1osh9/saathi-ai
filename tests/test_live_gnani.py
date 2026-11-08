"""Opt-in real provider smoke test; no mocks. Explicitly incurs Gnani API usage."""
import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
import gnani


@unittest.skipUnless(os.getenv('SAATHI_LIVE_TEST') == '1', 'Set SAATHI_LIVE_TEST=1 and SAATHI_TEST_WAV to opt in to real billed API calls')
class TestRealGnani(unittest.TestCase):
    def test_real_speech_roundtrip(self):
        self.assertTrue(os.getenv('GNANI_API_KEY'), 'A real server key is required')
        path = Path(os.environ['SAATHI_TEST_WAV'])
        audio = path.read_bytes()
        transcript = gnani.transcribe(audio)
        self.assertTrue(transcript['transcript'].strip())
        rendered = gnani.synthesize('नमस्ते। यह साथी का वास्तविक वॉइस परीक्षण है।')
        gnani.validate_wav(rendered)
        self.assertGreater(len(rendered), 44)


if __name__ == '__main__':
    unittest.main()
