"""Server-only demo authentication and bounded, single-worker request limits."""
import base64
import binascii
import hashlib
import hmac
import os
import re
import secrets
import threading
import time

MAX_BODY = 9 * 1024 * 1024
LIMITS = {'SAATHI_REQUESTS_PER_MINUTE': (120, 10000),
          'SAATHI_AUTH_FAILURES_PER_MINUTE': (20, 1000),
          'SAATHI_SPEECH_PER_MINUTE': (20, 120),
          'SAATHI_SPEECH_PER_DAY': (200, 2000)}


def production_environment():
    # A missing/mistyped SAATHI_ENV must never expose a Railway service in dev mode.
    return (os.getenv('SAATHI_ENV', 'development').casefold() == 'production'
            or bool(os.getenv('RAILWAY_ENVIRONMENT_ID')) or bool(os.getenv('RAILWAY_VOLUME_MOUNT_PATH')))


def password_hash(password):
    if not 16 <= len(password) <= 256:
        raise ValueError('Use a unique demo password of 16 to 256 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f'scrypt-v1${salt.hex()}${digest.hex()}'


def valid_password_hash(encoded):
    return bool(re.fullmatch(r'scrypt-v1\$[0-9a-f]{32}\$[0-9a-f]{64}', encoded))


def verify_basic(header, username, encoded):
    if not valid_password_hash(encoded) or len(header) > 2048:
        return False
    try:
        scheme, token = header.split(' ', 1)
        if scheme.casefold() != 'basic':
            return False
        user, password = base64.b64decode(token, validate=True).decode('utf-8').split(':', 1)
        if len(password) > 256:
            return False
    except (ValueError, UnicodeError, binascii.Error):
        return False
    _, salt, expected = encoded.split('$')
    actual = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
    user_ok = hmac.compare_digest(user.encode('utf-8'), username.encode('utf-8'))
    return hmac.compare_digest(actual, bytes.fromhex(expected)) and user_ok


class RequestLimits:
    """Only two global buckets: no spoofable IP keys or unbounded per-client state."""
    def __init__(self):
        self.lock = threading.Lock()
        self.buckets = {}

    def count(self, key, increment=False):
        window = int(time.monotonic() // 60)
        with self.lock:
            previous, count = self.buckets.get(key, (window, 0))
            count = count if previous == window else 0
            if increment:
                count += 1
            self.buckets[key] = (window, count)
            return count


class BodySizeLimit:
    """Enforce streaming and declared sizes before large multipart data reaches STT."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from fastapi import HTTPException
        from starlette.responses import JSONResponse
        if scope['type'] != 'http' or not production_environment():
            return await self.app(scope, receive, send)
        for key, value in scope['headers']:
            if key == b'content-length':
                try:
                    length = int(value)
                    if length < 0:
                        raise ValueError
                except ValueError:
                    return await JSONResponse({'detail': 'Invalid request length.'}, status_code=400)(scope, receive, send)
                if length > MAX_BODY:
                    return await JSONResponse({'detail': 'Request exceeds 9 MB.'}, status_code=413)(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                if total > MAX_BODY:
                    raise HTTPException(413, 'Request exceeds 9 MB.')
            return message

        await self.app(scope, bounded_receive, send)
