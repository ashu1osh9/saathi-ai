import hashlib
import json
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .logic import contains, decide_command, digest_message, normalize, parse_draft, parse_reminder
from .demo_security import BodySizeLimit, LIMITS, RequestLimits, production_environment, valid_password_hash, verify_basic

PACKAGE_ROOT = Path(__file__).resolve().parent
_checkout = PACKAGE_ROOT.parents[1]
# Editable/source installs retain the existing checkout-root credentials and DB.
# Wheels use the working directory, never writable state inside site-packages.
ROOT = _checkout if (_checkout / 'pyproject.toml').is_file() and PACKAGE_ROOT.parent == _checkout / 'src' else Path.cwd()
load_dotenv(ROOT / '.env')
from . import gnani

DB = Path(os.getenv('SAATHI_DB_PATH', str(ROOT / 'saathi.db')))


@contextmanager
def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    DB.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, note TEXT NOT NULL, due_at TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS pending_actions (token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, expires_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS speech_usage (bucket TEXT PRIMARY KEY, window INTEGER NOT NULL, used INTEGER NOT NULL)')


@asynccontextmanager
async def lifespan(application):
    validate_production_config()
    application.state.request_limits = RequestLimits()
    init_db()
    yield


def production_mode():
    return production_environment()


def validate_production_config():
    if not production_mode():
        return
    hosts = [host.strip() for host in os.getenv('SAATHI_ALLOWED_HOSTS', '').split(',') if host.strip()]
    if not hosts or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', host) or '..' in host for host in hosts):
        raise RuntimeError('Production requires explicit SAATHI_ALLOWED_HOSTS.')
    mode = os.getenv('SAATHI_AUTH_MODE', 'gateway')
    if mode == 'gateway':
        if len(os.getenv('SAATHI_PROXY_TOKEN', '')) < 32:
            raise RuntimeError('Production requires a strong SAATHI_PROXY_TOKEN of at least 32 characters.')
    elif mode == 'basic':
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', os.getenv('SAATHI_DEMO_USER', '')) or not valid_password_hash(os.getenv('SAATHI_APP_PASSWORD_HASH', '')):
            raise RuntimeError('Application authentication requires SAATHI_DEMO_USER and a valid SAATHI_APP_PASSWORD_HASH.')
    else:
        raise RuntimeError('SAATHI_AUTH_MODE must be gateway or basic; production authentication cannot be disabled.')
    if os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('RAILWAY_VOLUME_MOUNT_PATH'):
        if mode != 'basic' or os.getenv('RAILWAY_VOLUME_MOUNT_PATH') != '/data' or os.getenv('SAATHI_DB_PATH') != '/data/saathi.db':
            raise RuntimeError('Railway requires application authentication and persistent storage at /data/saathi.db.')
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            raise RuntimeError('Railway app must run as non-root. Keep the Dockerfile startup command.')
    for name, (default, maximum) in LIMITS.items():
        try:
            value = int(os.getenv(name, str(default)))
            if not 1 <= value <= maximum:
                raise ValueError
        except ValueError:
            raise RuntimeError(f'{name} must be an integer from 1 to {maximum}.') from None
    if not gnani.configuration()['key']:
        raise RuntimeError('Production requires GNANI_API_KEY on the server.')


app = FastAPI(title='Saathi AI', version='0.3.0', lifespan=lifespan,
              docs_url=None if production_mode() else '/docs',
              redoc_url=None if production_mode() else '/redoc')
app.mount('/static', StaticFiles(directory=PACKAGE_ROOT / 'static'), name='static')
app.add_middleware(BodySizeLimit)


@app.middleware('http')
async def browser_security(request: Request, call_next):
    response = await secure_request(request, call_next)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'microphone=(self), camera=(), geolocation=()'
    if production_mode() and request.url.scheme == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


async def secure_request(request: Request, call_next):
    health_probe = request.url.path == '/api/health' and request.method in {'GET', 'HEAD'}
    if production_mode():
        hosts = {host.strip().casefold() for host in os.getenv('SAATHI_ALLOWED_HOSTS', '').split(',') if host.strip()}
        if health_probe:
            hosts.update({'127.0.0.1', 'localhost', '::1', 'healthcheck.railway.app'})
        if request.url.hostname not in hosts:
            return JSONResponse({'detail': 'Host is not allowed.'}, status_code=400)
        if not health_probe and request.url.scheme != 'https':
            return JSONResponse({'detail': 'HTTPS is required in production.'}, status_code=403)
    origin = request.headers.get('origin')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and (urlsplit(origin).netloc != request.url.netloc or urlsplit(origin).scheme != request.url.scheme)):
            return JSONResponse({'detail': 'Cross-origin actions are not allowed.'}, status_code=403)
    if production_mode() and not health_probe:
        limits = request.app.state.request_limits
        if limits.count('requests', increment=True) > int(os.getenv('SAATHI_REQUESTS_PER_MINUTE', '120')):
            return JSONResponse({'detail': 'Demo request limit reached. Wait a minute and retry.'}, status_code=429, headers={'Retry-After': '60'})
        mode = os.getenv('SAATHI_AUTH_MODE', 'gateway')
        if mode == 'basic':
            failure_limit = int(os.getenv('SAATHI_AUTH_FAILURES_PER_MINUTE', '20'))
            if limits.count('failures') >= failure_limit:
                return JSONResponse({'detail': 'Too many authentication failures. Wait a minute and retry.'}, status_code=429, headers={'Retry-After': '60'})
            verified = await run_in_threadpool(verify_basic, request.headers.get('authorization', ''), os.getenv('SAATHI_DEMO_USER', ''), os.getenv('SAATHI_APP_PASSWORD_HASH', ''))
            if not verified:
                limits.count('failures', increment=True)
                return JSONResponse({'detail': 'Demo authentication required.'}, status_code=401,
                                    headers={'WWW-Authenticate': 'Basic realm="Saathi demo", charset="UTF-8"'})
        elif mode == 'gateway':
            expected = os.getenv('SAATHI_PROXY_TOKEN', '')
            if len(expected) < 32 or not hmac.compare_digest(request.headers.get('x-saathi-gateway', '').encode(), expected.encode()):
                return JSONResponse({'detail': 'Use the authenticated HTTPS demo gateway.'}, status_code=403)
        else:
            return JSONResponse({'detail': 'Production authentication is not configured.'}, status_code=503)
    return await call_next(request)


def reserve_speech_request():
    """Persist conservative attempt quotas before any production provider call."""
    if not production_mode():
        return
    timestamp = int(time.time())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        for bucket, seconds, variable in [('minute', 60, 'SAATHI_SPEECH_PER_MINUTE'), ('day', 86400, 'SAATHI_SPEECH_PER_DAY')]:
            window = timestamp // seconds
            limit = int(os.getenv(variable, str(LIMITS[variable][0])))
            row = c.execute('SELECT window, used FROM speech_usage WHERE bucket=?', (bucket,)).fetchone()
            used = row['used'] if row and row['window'] == window else 0
            if used >= limit:
                raise HTTPException(429, f'Demo speech {bucket} limit reached. Written commands remain available.',
                                    headers={'Retry-After': str(seconds - timestamp % seconds)})
            c.execute('INSERT INTO speech_usage VALUES (?, ?, ?) ON CONFLICT(bucket) DO UPDATE SET window=excluded.window, used=excluded.used',
                      (bucket, window, used + 1))


@app.exception_handler(sqlite3.Error)
async def database_error(request, exc):
    return JSONResponse({'detail': 'Local storage is unavailable. The action could not be completed. Please retry.'}, status_code=503)


class CleanModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class NewMessage(CleanModel):
    sender: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=3000)


class NewDraft(CleanModel):
    recipient: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=2000)


class NewReminder(CleanModel):
    note: str = Field(min_length=1, max_length=500)
    due_at: datetime


class InputText(CleanModel):
    text: str = Field(min_length=1, max_length=4000)
    utc_offset_minutes: int = Field(default=330, ge=-840, le=840)


class SpeechText(CleanModel):
    text: str = Field(min_length=1, max_length=900)
    language: Literal['hi-IN', 'hi-en', 'en-IN', 'auto'] = 'hi-IN'
    speed: float = Field(default=1.0, ge=0.85, le=1.15)


class ActionToken(CleanModel):
    token: str = Field(min_length=20, max_length=100)


def now_utc():
    return datetime.now(timezone.utc)


def future_time(due: datetime):
    if due.tzinfo is None or due.utcoffset() is None:
        raise HTTPException(400, 'Reminder time must include a timezone offset.')
    if due <= now_utc():
        raise HTTPException(400, 'Reminder time must be in the future.')
    return due.astimezone(timezone.utc).isoformat()


def review(kind: str, payload: dict):
    token = secrets.token_urlsafe(32)
    expires = (now_utc() + timedelta(minutes=5)).isoformat()
    with db() as c:
        c.execute('DELETE FROM pending_actions WHERE expires_at <= ?', (now_utc().isoformat(),))
        c.execute('INSERT INTO pending_actions VALUES (?, ?, ?, ?)',
                  (hashlib.sha256(token.encode()).hexdigest(), kind, json.dumps(payload, ensure_ascii=False), expires))
    return {'requires_confirmation': True, 'token': token, 'action': kind, 'preview': payload, 'expires_at': expires}


@app.get('/')
def index():
    return FileResponse(PACKAGE_ROOT / 'static' / 'index.html')


@app.get('/api/health')
def health():
    config = gnani.configuration()
    return {'status': 'ok', 'gnani_configured': bool(config['key']), 'connection_verified': False,
            'stt_model': config['stt_model'], 'tts_model': config['tts_model']}


@app.post('/api/stt')
async def speech_to_text(audio: UploadFile = File(...)):
    try:
        content = await audio.read(gnani.MAX_UPLOAD + 1)
    finally:
        await audio.close()
    if len(content) > gnani.MAX_UPLOAD:
        raise HTTPException(413, 'Recording exceeds 8 MB.')
    await run_in_threadpool(reserve_speech_request)
    return await run_in_threadpool(gnani.transcribe, content)


@app.post('/api/tts')
def text_to_speech(payload: SpeechText):
    reserve_speech_request()
    content = gnani.synthesize(payload.text, payload.language, payload.speed)
    return Response(content=content, media_type='audio/wav')


@app.get('/api/messages')
def get_messages():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 30')]


@app.post('/api/messages', status_code=201)
def add_message(data: NewMessage):
    with db() as c:
        cur = c.execute('INSERT INTO messages(sender, body, created_at) VALUES (?, ?, ?)',
                        (data.sender, data.body, now_utc().isoformat()))
        return {'id': cur.lastrowid}


@app.get('/api/summary/latest')
def summary_latest():
    with db() as c:
        row = c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 1').fetchone()
    if not row:
        raise HTTPException(404, 'Inbox is empty. Add an in-app message first.')
    return {'sender': row['sender'], **digest_message(row['body'])}


@app.get('/api/summary')
def summary_inbox():
    items = get_messages()
    if not items:
        raise HTTPException(404, 'Inbox is empty. Add an in-app message first.')
    return [{'sender': item['sender'], **digest_message(item['body'])} for item in items]


@app.get('/api/drafts')
def get_drafts():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM drafts ORDER BY id DESC LIMIT 15')]


@app.post('/api/drafts', status_code=202)
def add_draft(data: NewDraft):
    return review('draft', data.model_dump())


@app.get('/api/reminders')
def get_reminders():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM reminders ORDER BY done ASC, due_at ASC LIMIT 100')]


@app.post('/api/reminders', status_code=202)
def add_reminder(data: NewReminder):
    return review('reminder', {'note': data.note, 'due_at': future_time(data.due_at)})


@app.patch('/api/reminders/{reminder_id}/done', status_code=202)
def mark_done(reminder_id: int):
    with db() as c:
        row = c.execute('SELECT * FROM reminders WHERE id=? AND done=0', (reminder_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Pending reminder not found.')
    return review('complete_reminder', {'id': reminder_id, 'note': row['note']})


@app.post('/api/actions/confirm')
def confirm_action(data: ActionToken):
    with db() as c:
        # Lock before reading: concurrent confirmations cannot create duplicate actions.
        c.execute('BEGIN IMMEDIATE')
        token_hash = hashlib.sha256(data.token.encode()).hexdigest()
        row = c.execute('SELECT * FROM pending_actions WHERE token_hash=?', (token_hash,)).fetchone()
        if not row:
            raise HTTPException(409, 'Review is no longer available. Please review the action again.')
        if datetime.fromisoformat(row['expires_at']) <= now_utc():
            raise HTTPException(410, 'Review expired. Please review the action again.')
        payload = json.loads(row['payload'])
        kind = row['kind']
        if kind == 'draft':
            cur = c.execute('INSERT INTO drafts(recipient, body, created_at) VALUES (?, ?, ?)',
                            (payload['recipient'], payload['body'], now_utc().isoformat()))
        elif kind == 'reminder':
            future_time(datetime.fromisoformat(payload['due_at']))
            cur = c.execute('INSERT INTO reminders(note, due_at) VALUES (?, ?)', (payload['note'], payload['due_at']))
        elif kind == 'complete_reminder':
            cur = c.execute('UPDATE reminders SET done=1 WHERE id=? AND done=0', (payload['id'],))
            if not cur.rowcount:
                raise HTTPException(409, 'Reminder was already completed or removed.')
        else:
            raise HTTPException(400, 'Unsupported action.')
        c.execute('DELETE FROM pending_actions WHERE token_hash=?', (token_hash,))
        return {'id': payload['id'] if kind == 'complete_reminder' else cur.lastrowid, 'action': kind, 'saved': True, 'sent': False}


@app.post('/api/actions/cancel')
def cancel_action(data: ActionToken):
    with db() as c:
        c.execute('DELETE FROM pending_actions WHERE token_hash=?', (hashlib.sha256(data.token.encode()).hexdigest(),))
    return {'cancelled': True}


@app.post('/api/command')
def command(payload: InputText):
    intent = decide_command(payload.text)
    result = {'intent': intent, 'draft_text': '', 'recipient': '', 'read_all': False}
    if intent == 'draft':
        draft = parse_draft(payload.text)
        result.update(draft_text=draft['body'], recipient=draft['recipient'])
    if intent == 'reminder':
        result['reminder'] = parse_reminder(payload.text, utc_offset_minutes=payload.utc_offset_minutes)
    if intent in {'read', 'summary'}:
        result['read_all'] = contains(normalize(payload.text), ('all', 'sab', 'saare', 'सभी', 'सब', 'सारे'))
    return result
