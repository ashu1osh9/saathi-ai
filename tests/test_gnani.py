import unittest
import struct
import wave
from io import BytesIO
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException

import gnani


def wav(rate=16000, channels=1, seconds=0.1):
    output = BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b'\0\0' * int(rate * seconds) * channels)
    return output.getvalue()


class TestGnaniContract(unittest.TestCase):
    """Mocked transport is test-only. Production never imports this module."""
    def setUp(self):
        self.env = patch.dict('os.environ', {'GNANI_API_KEY': 'test-key', 'GNANI_STT_MODEL': 'prisma-v3.0', 'GNANI_TTS_MODEL': 'timbre-v2.5', 'GNANI_TTS_VOICE': 'Nalini'})
        self.env.start()
        self.post = patch('gnani.requests.post')
        self.request = self.post.start()

    def tearDown(self):
        self.post.stop()
        self.env.stop()

    def response(self, data=None, content=b'', status=200):
        result = Mock(status_code=status, content=content)
        result.json.return_value = data
        self.request.return_value = result
        return result

    def test_documented_stt_multipart_contract(self):
        self.response({'success': True, 'transcript': 'मेरा संदेश पढ़ो', 'model': 'prisma-v3.0'})
        result = gnani.transcribe(wav())
        self.assertEqual(result['transcript'], 'मेरा संदेश पढ़ो')
        args, kwargs = self.request.call_args
        self.assertEqual(args[0], 'https://api.vachana.ai/stt/v3')
        self.assertEqual(kwargs['headers'], {'X-API-Key-ID': 'test-key'})
        self.assertEqual(kwargs['data'], {'model': 'prisma-v3.0', 'language_code': 'hi-IN', 'format': 'transcribe'})
        self.assertIn('audio_file', kwargs['files'])
        self.assertFalse(kwargs['allow_redirects'])

    def test_documented_tts_binary_contract(self):
        clip = wav(rate=48000)
        self.response(content=clip)
        self.assertEqual(gnani.synthesize('नमस्ते', 'hi-en', 0.85), clip)
        args, kwargs = self.request.call_args
        self.assertEqual(args[0], 'https://api.vachana.ai/api/v1/tts/inference')
        self.assertEqual(kwargs['json']['voice'], 'Nalini')
        self.assertEqual(kwargs['json']['language'], 'hi-en')
        self.assertEqual(kwargs['json']['audio_config']['container'], 'wav')

    def test_missing_key_never_calls_provider(self):
        with patch.dict('os.environ', {'GNANI_API_KEY': ''}):
            with self.assertRaises(HTTPException) as error:
                gnani.synthesize('नमस्ते')
        self.assertEqual(error.exception.status_code, 503)
        self.request.assert_not_called()

    def test_invalid_recordings_never_leave_server(self):
        for clip in [b'not wav', wav(rate=8000), wav(channels=2), wav(seconds=0), wav(seconds=31), wav()[:-2]]:
            with self.subTest(size=len(clip)), self.assertRaises(HTTPException) as error:
                gnani.transcribe(clip)
            self.assertEqual(error.exception.status_code, 400)
        self.request.assert_not_called()

    def test_provider_failures_are_sanitized(self):
        for status in [400, 401, 402, 403, 429, 500, 503, 302]:
            with self.subTest(status=status):
                self.response(status=status)
                with self.assertRaises(HTTPException) as error:
                    gnani.synthesize('नमस्ते')
                self.assertEqual(error.exception.status_code, 429 if status == 429 else 502)
                self.assertNotIn('test-key', error.exception.detail)

    def test_timeout_and_connection_failure(self):
        for cause, status in [(requests.Timeout('secret test-key'), 504), (requests.ConnectionError('secret test-key'), 502)]:
            self.request.side_effect = cause
            with self.assertRaises(HTTPException) as error:
                gnani.synthesize('नमस्ते')
            self.assertEqual(error.exception.status_code, status)
            self.assertNotIn('test-key', error.exception.detail)

    def test_empty_unsuccessful_and_malformed_stt(self):
        for data in [{'success': False, 'transcript': 'fake success'}, {'success': True, 'transcript': ''}, {'transcript': 'missing success'}, ['unexpected']]:
            self.response(data)
            with self.assertRaises(HTTPException) as error:
                gnani.transcribe(wav())
            self.assertEqual(error.exception.status_code, 502)
        self.response().json.side_effect = ValueError('not JSON')
        with self.assertRaises(HTTPException):
            gnani.transcribe(wav())

    def test_tts_requires_complete_real_audio(self):
        for content in [b'{"success":true}', b'RIFFbroken', wav()[:-4]]:
            self.response(content=content)
            with self.assertRaises(HTTPException) as error:
                gnani.synthesize('नमस्ते')
            self.assertEqual(error.exception.status_code, 502)

    def test_streamed_tts_sizes_are_finalized_without_changing_pcm(self):
        complete = wav(rate=48000)
        streamed = bytearray(complete)
        struct.pack_into('<I', streamed, 4, 0xffffffff)
        struct.pack_into('<I', streamed, 40, 0xffffffff)
        self.response(content=bytes(streamed))
        finalized = gnani.synthesize('नमस्ते')
        self.assertEqual(finalized, complete)
        gnani.validate_wav(finalized)

    def test_stream_header_cannot_hide_partial_pcm_or_a_missing_data_chunk(self):
        streamed = bytearray(wav(rate=48000))
        struct.pack_into('<I', streamed, 4, 0xffffffff)
        struct.pack_into('<I', streamed, 40, 0xffffffff)
        for content in [bytes(streamed[:-1]), bytes(streamed[:36]), bytes(streamed[:44])]:
            with self.subTest(size=len(content)), self.assertRaises(HTTPException) as error:
                gnani.finalize_tts_wav(content)
            self.assertEqual(error.exception.status_code, 502)

    def test_busy_does_not_start_second_paid_call(self):
        gnani._speech_slot.acquire()
        try:
            with self.assertRaises(HTTPException) as error:
                gnani.synthesize('नमस्ते')
            self.assertEqual(error.exception.status_code, 429)
            self.request.assert_not_called()
        finally:
            gnani._speech_slot.release()


if __name__ == '__main__':
    unittest.main()
