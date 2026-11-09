"""Local/CI-only Docker acceptance with disposable data and non-billed credentials.

Never deploys, publishes an image, uses real keys, or contacts Gnani.
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from saathi.demo_security import password_hash


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


def container_base_url(name):
    # Docker may allocate a different ephemeral host port after a restart.
    address, port = docker('port', name, '8080/tcp').rsplit(':', 1)
    if address != '127.0.0.1' or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise RuntimeError('Expected one loopback-only published container port.')
    return f'http://127.0.0.1:{port}'


def report_failure(name):
    # Inspect only runtime state, not Config/Env or credentials. This container
    # contains exclusively the disposable data and test credentials below.
    for label, args in [('Container state', ['inspect', '--format', '{{json .State}}', name]),
                        ('Container logs', ['logs', '--tail', '80', name])]:
        result = subprocess.run(['docker', *args], capture_output=True, text=True)
        print(f'{label}:\n{result.stdout}{result.stderr}', file=sys.stderr)


def check_storage(name):
    code = "import json, os; from pathlib import Path; print(json.dumps([(p.stat().st_uid, p.stat().st_gid, p.stat().st_mode & 0o777) for p in [Path('/data'), Path('/data/saathi.db')]]))"
    metadata = json.loads(docker('exec', '--user', '10001:10001', name, 'python', '-c', code))
    assert metadata == [[10001, 10001, 0o700], [10001, 10001, 0o600]], 'Storage must remain private and owned by the app user'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='saathi-ai:ci')
    options = parser.parse_args()
    name = 'saathi-smoke-' + uuid.uuid4().hex[:12]
    volume = name + '-data'
    password = 'test-only-container-password'
    auth = 'Basic ' + base64.b64encode(('test-evaluator:' + password).encode()).decode()
    docker('volume', 'create', volume)
    try:
        docker('run', '-d', '--name', name, '--user', '0:0', '-p', '127.0.0.1::8080',
               '--mount', f'type=volume,src={volume},dst=/data',
               '-e', 'PORT=8080', '-e', 'FORWARDED_ALLOW_IPS=*',
               '-e', 'RAILWAY_RUN_UID=0', '-e', 'RAILWAY_VOLUME_MOUNT_PATH=/data',
               '-e', 'SAATHI_ENV=production', '-e', 'SAATHI_AUTH_MODE=basic',
               '-e', 'SAATHI_ALLOWED_HOSTS=127.0.0.1', '-e', 'SAATHI_DEMO_USER=test-evaluator',
               '-e', 'SAATHI_APP_PASSWORD_HASH=' + password_hash(password),
               '-e', 'GNANI_API_KEY=test-only-no-provider-calls', options.image)
        base = container_base_url(name)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, payload=None, authenticated=True, forwarded=True):
            headers = {}
            if authenticated:
                headers['Authorization'] = auth
            if forwarded:
                headers['X-Forwarded-Proto'] = 'https'
            data = None if payload is None else json.dumps(payload).encode()
            if data:
                headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(base + path, data=data, headers=headers)
            try:
                response = opener.open(req, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, response.read()

        def ready(phase):
            deadline = time.monotonic() + 45
            last_result = 'no response'
            while time.monotonic() < deadline:
                try:
                    status_code = request('/api/health', authenticated=False, forwarded=False)[0]
                    last_result = f'HTTP {status_code}'
                    if status_code == 200:
                        return
                except (OSError, urllib.error.URLError) as error:
                    last_result = type(error).__name__
                time.sleep(0.2)
            raise RuntimeError(f'Test container did not become ready {phase} at {base}: {last_result}.')

        ready('after initial startup')
        status = docker('exec', name, 'cat', '/proc/1/status')
        assert any(line.startswith('Uid:') and line.split()[1:] == ['10001'] * 4 for line in status.splitlines()), 'Application must drop root'
        check_storage(name)
        assert request('/', authenticated=False)[0] == 401
        assert request('/', forwarded=False)[0] == 403
        assert request('/', authenticated=True)[0] == 200
        assert request('/api/tts', {'text': 'Namaste'}, authenticated=False)[0] == 401
        assert request('/api/messages', {'sender': 'Demo', 'body': 'Persistent container example'})[0] == 201
        code, body = request('/api/drafts', {'recipient': 'Ravi', 'body': 'Main aaunga'})
        assert code == 202
        review = json.loads(body)
        assert json.loads(request('/api/drafts')[1]) == []
        docker('restart', name)
        base = container_base_url(name)
        ready('after restart')
        check_storage(name)
        status = docker('exec', name, 'cat', '/proc/1/status')
        assert any(line.startswith('Uid:') and line.split()[1:] == ['10001'] * 4 for line in status.splitlines()), 'Application must drop root after restart'
        assert json.loads(request('/api/messages')[1])[0]['body'] == 'Persistent container example'
        code, body = request('/api/actions/confirm', {'token': review['token']})
        assert code == 200 and json.loads(body)['saved'] and not json.loads(body)['sent']
        print('PASS: root-owned volume, UID 10001, dynamic PORT, proxy HTTPS, authentication, confirmation and restart persistence.')
    except Exception:
        report_failure(name)
        raise
    finally:
        # Only the uniquely named disposable container/volume created above.
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)


if __name__ == '__main__':
    main()
