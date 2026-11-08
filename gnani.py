"""Server-only Gnani REST adapter; no fallback or fabricated provider responses.

Contract: docs.gnani.ai/api/STT/speech-to-text and /api/TTS/tts-inference.
"""
import os
import struct
import threading
import wave
from io import BytesIO

import requests
from fastapi import HTTPException

STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
MAX_UPLOAD = 8 * 1024 * 1024
_speech_slot = threading.BoundedSemaphore(1)


def configuration():
    return {
        "key": os.getenv("GNANI_API_KEY", "").strip(),
        "stt_model": os.getenv("GNANI_STT_MODEL", "prisma-v3.0"),
        "tts_model": os.getenv("GNANI_TTS_MODEL", "timbre-v2.5"),
        "voice": os.getenv("GNANI_TTS_VOICE", "Nalini"),
    }


def validate_wav(content: bytes, *, input_audio: bool = False):
    try:
        with wave.open(BytesIO(content), "rb") as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getcomptype() != "NONE":
                raise ValueError("Expected uncompressed 16-bit mono WAV.")
            if not frames or not rate:
                raise ValueError("Audio is empty.")
            if input_audio and (rate != 16000 or frames / rate > 30):
                raise ValueError("Use 16 kHz audio, up to 30 seconds.")
            if len(audio.readframes(frames)) != frames * 2:
                raise ValueError("Audio file is truncated.")
    except (wave.Error, EOFError, ValueError) as exc:
        raise HTTPException(400 if input_audio else 502, f"Invalid {'recording' if input_audio else 'Gnani audio response'}: {exc}") from exc


def finalize_tts_wav(content: bytes) -> bytes:
    """Finalize Gnani's streamed RIFF sizes without changing a single PCM byte.

    Observed REST responses use 0xffffffff for both RIFF and data lengths even
    after the entire HTTP body has arrived. Ordinary sized WAVs stay strict:
    genuinely truncated files are never repaired or accepted as successful audio.
    """
    if len(content) < 12 or content[:4] != b'RIFF' or content[8:12] != b'WAVE':
        validate_wav(content)
    if struct.unpack_from('<I', content, 4)[0] != 0xffffffff:
        validate_wav(content)
        return content
    offset = 12
    result = bytearray(content)
    while offset + 8 <= len(content):
        tag = content[offset:offset + 4]
        size = struct.unpack_from('<I', content, offset + 4)[0]
        if tag == b'data':
            available = len(content) - offset - 8
            if size == 0xffffffff:
                if not available or available % 2:
                    raise HTTPException(502, 'Gnani returned incomplete PCM audio.')
                struct.pack_into('<I', result, offset + 4, available)
            struct.pack_into('<I', result, 4, len(content) - 8)
            finalized = bytes(result)
            validate_wav(finalized)
            return finalized
        if size > len(content) - offset - 8:
            break
        offset += 8 + size + (size % 2)
    raise HTTPException(502, 'Gnani WAV response has no complete audio data chunk.')


def _post(url, **kwargs):
    config = configuration()
    if not config["key"]:
        raise HTTPException(503, "Voice is unavailable. Set GNANI_API_KEY in the server .env and restart. Text commands still work.")
    if not _speech_slot.acquire(blocking=False):
        raise HTTPException(429, "Another speech request is running. Please wait and try again.")
    try:
        response = requests.post(url, headers={"X-API-Key-ID": config["key"]},
                                 timeout=(10, 65), allow_redirects=False, **kwargs)
        if response.status_code != 200:
            errors = {
                400: "Gnani rejected the speech settings. Check the model, language and voice in .env.",
                401: "Gnani authentication failed. Check the server API key.",
                402: "Gnani account credits are insufficient.",
                403: "Gnani denied access. Check API key permissions and account credits.",
                429: "Gnani is busy or rate limited. Wait a moment before trying again.",
            }
            response.close()
            raise HTTPException(429 if response.status_code == 429 else 502,
                                errors.get(response.status_code, "Gnani speech service is unavailable. Please try again later."))
        return response
    except requests.Timeout as exc:
        raise HTTPException(504, "Gnani speech request timed out. Please try again.") from exc
    except requests.RequestException as exc:
        # Never echo upstream text, headers, recordings or credentials.
        raise HTTPException(502, "Could not reach Gnani. Check the server connection and try again.") from exc
    finally:
        _speech_slot.release()


def transcribe(content: bytes):
    validate_wav(content, input_audio=True)
    config = configuration()
    if config["stt_model"] not in {"prisma-v3.0", "prisma-v2.5"}:
        raise HTTPException(503, "Unsupported GNANI_STT_MODEL in server configuration.")
    response = _post(STT_URL, files={"audio_file": ("command.wav", content, "audio/wav")},
                     data={"model": config["stt_model"], "language_code": "hi-IN", "format": "transcribe"})
    try:
        data = response.json()
        transcript = data.get("transcript") if isinstance(data, dict) else None
        if not isinstance(data, dict) or data.get("success") is not True or not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Empty or unsuccessful response")
        if len(transcript) > 4000:
            raise ValueError("Transcript exceeds command limit")
        return {"transcript": transcript.strip(), "model": data.get("model", config["stt_model"])}
    except ValueError as exc:
        raise HTTPException(502, "Gnani returned no usable transcript. Please record again, or type your command.") from exc
    finally:
        response.close()


def synthesize(text: str, language: str = "hi-IN", speed: float = 1.0):
    config = configuration()
    if config["tts_model"] not in {"timbre-v2.5", "timbre-v3.0"}:
        raise HTTPException(503, "Unsupported GNANI_TTS_MODEL in server configuration.")
    response = _post(TTS_URL, json={"text": text, "voice": config["voice"],
        "model": config["tts_model"], "language": language, "speed": speed,
        "audio_config": {"encoding": "linear_pcm", "container": "wav", "num_channels": 1,
                         "sample_rate": 48000, "sample_width": 2}})
    try:
        if len(response.content) > 12 * 1024 * 1024:
            raise HTTPException(502, "Gnani returned an oversized audio response.")
        return finalize_tts_wav(response.content)
    finally:
        response.close()
