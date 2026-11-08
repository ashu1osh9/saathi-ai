"""Release check. Prints paths/counts, never secret values or DB content.

Run before committing/pushing. Local artifact folders may contain private data;
they are inventoried but deliberately excluded from release-content inspection.
Read-only by default; --rebuild-zip packages the checked Git index locally.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {'.env.example', '.env.production.example'}
PRIVATE_DIRS = {'.git', '.venv', '.python', '.browser-test', 'test-results', 'node_modules',
                'data', 'backups', 'private', 'recordings', 'uploads', 'logs', '.cache', '.docker',
                '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist'}
PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.wav', '.webm', '.mp3', '.mp4', '.mov',
                    '.m4a', '.ogg', '.flac', '.aac', '.avi', '.mkv',
                    '.pem', '.key', '.log', '.pyc', '.pyo'}
TEXT_SUFFIXES = {'.py', '.js', '.css', '.html', '.md', '.txt', '.lock', '.yaml', '.yml', '.json', '.bat'}


def git(*args, check=True):
    # Trust only the user-authorized workspace, for this command; no global change.
    return subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}', '-C', str(ROOT), *args],
                          capture_output=True, check=check)


def private_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        return True
    if name in EXAMPLES:
        return False
    return (bool(set(path.parts) & PRIVATE_DIRS) or path.suffix.casefold() in PRIVATE_SUFFIXES
            or path.name == '.env' or path.name.startswith('.env.')
            or path.name.endswith(('.db-wal', '.db-shm', '.db-journal')))


def secrets():
    result = []
    for name in ['.env', '.env.production', '.env.local']:
        path = ROOT / name
        if path.is_file():
            for key, value in dotenv_values(path).items():
                if value and len(value) >= 8 and any(word in key.upper() for word in ['KEY', 'TOKEN', 'PASSWORD', 'SECRET']):
                    result.append(value.encode())
    return result


def inspect_content(name, data, known, findings):
    if any(value in data for value in known):
        findings.append({'path': name, 'issue': 'Configured secret found; value withheld'})
    # These patterns supplement, rather than replace, checking the actual .env values.
    patterns = [rb'AKIA[0-9A-Z]{16}', rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}',
                rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----']
    if any(re.search(pattern, data) for pattern in patterns):
        findings.append({'path': name, 'issue': 'Credential/private-key pattern; value withheld'})


def same_release_content(name, left, right):
    if PurePosixPath(name).suffix in TEXT_SUFFIXES or PurePosixPath(name).name.startswith('.'):
        return left.replace(b'\r\n', b'\n') == right.replace(b'\r\n', b'\n')
    return left == right


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', default='dist/saathi-ai-submission.zip')
    parser.add_argument('--require-git', action='store_true')
    parser.add_argument('--rebuild-zip', action='store_true')
    parser.add_argument('--output', default='test-results/pre-submission-results.json')
    options = parser.parse_args()
    known = secrets()
    findings = []
    inventory = Counter()
    candidates = []
    # Inventory every file without following symlinked directories or opening DBs/audio.
    for directory, subdirs, filenames in os.walk(ROOT, followlinks=False):
        subdirs[:] = [name for name in subdirs if not (Path(directory) / name).is_symlink()]
        for filename in filenames:
            path = Path(directory) / filename
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                inventory['symlinks_not_followed'] += 1
            elif private_path(relative):
                inventory['private_or_development_artifacts'] += 1
            else:
                inventory['release_candidates'] += 1
                candidates.append(relative)
                inspect_content(relative, path.read_bytes(), known, findings)

    for name in EXAMPLES:
        for key, value in dotenv_values(ROOT / name).items():
            if value and any(word in key.upper() for word in ['API_KEY', 'PROXY_TOKEN', 'PASSWORD_HASH']):
                findings.append({'path': name, 'issue': 'Example environment contains a secret value'})

    tracked = []
    repository = (ROOT / '.git').exists()
    if repository:
        tracked = [item.decode('utf-8') for item in git('ls-files', '-z').stdout.split(b'\0') if item]
        for name in tracked:
            if private_path(name):
                findings.append({'path': name, 'issue': 'Private/development artifact is tracked or staged'})
            staged = git('show', ':' + name).stdout
            inspect_content('git-index:' + name, staged, known, findings)
            current = ROOT / name
            if not current.is_file() or not same_release_content(name, current.read_bytes(), staged):
                findings.append({'path': name, 'issue': 'Working file differs from Git index; review and restage'})
        ignored = ['.env', 'saathi.db', '.env.production', '.venv/pyvenv.cfg', '.python/python.exe',
                   'test-results/private.json', 'recordings/private.wav', 'private/data.json']
        for name in ignored:
            if git('check-ignore', '--no-index', '--quiet', name, check=False).returncode != 0:
                findings.append({'path': name, 'issue': 'Required ignore rule is missing'})
        for name in candidates:
            if name not in tracked and git('check-ignore', '--no-index', '--quiet', name, check=False).returncode != 0:
                findings.append({'path': name, 'issue': 'Untracked release candidate: stage or explicitly exclude it'})
    elif options.require_git:
        findings.append({'path': '.git', 'issue': 'Git repository has not been prepared'})

    archive = ROOT / options.zip
    if options.rebuild_zip:
        if not tracked:
            findings.append({'path': '.git', 'issue': 'Stage reviewed source before rebuilding ZIP'})
        if not findings:
            archive.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
                for name in sorted(tracked):
                    bundle.writestr(name, git('show', ':' + name).stdout)
    zip_entries = []
    if not archive.is_file():
        findings.append({'path': options.zip, 'issue': 'Submission ZIP is missing'})
    else:
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                findings.append({'path': options.zip, 'issue': 'ZIP CRC/integrity failed'})
            zip_entries = bundle.namelist()
            if len(zip_entries) != len(set(zip_entries)):
                findings.append({'path': options.zip, 'issue': 'ZIP contains duplicate entries'})
            for name in zip_entries:
                if private_path(name):
                    findings.append({'path': 'zip:' + name, 'issue': 'Private artifact or unsafe path in ZIP'})
                    continue
                data = bundle.read(name)
                inspect_content('zip:' + name, data, known, findings)
                source = ROOT / name
                if not source.is_file() or not same_release_content(name, source.read_bytes(), data):
                    findings.append({'path': 'zip:' + name, 'issue': 'ZIP is stale or differs from current source'})
            if tracked and set(zip_entries) != set(tracked):
                findings.append({'path': options.zip, 'issue': 'ZIP file set differs from reviewed Git index'})

    summary = {'status': 'READY' if not findings else 'BLOCKED', 'inventory': dict(inventory),
               'git_repository': repository, 'tracked_or_staged_files': len(tracked),
               'zip_files': len(zip_entries), 'findings': findings,
               'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest() if archive.is_file() else None,
               'scope': 'Known configured secrets + common credential patterns; no universal secret-detection guarantee',
               'pushed': False, 'deployed': False}
    destination = ROOT / options.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    if options.rebuild_zip and not findings:
        (archive.parent / 'manifest.json').write_text(json.dumps({
            'archive': archive.name, 'files': len(zip_entries), 'bytes': archive.stat().st_size,
            'sha256': summary['zip_sha256'], 'private_artifacts_included': False,
            'published': False,
        }, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
