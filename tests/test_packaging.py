"""Package imports and filesystem behavior outside the repository working directory."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPackageLayout(unittest.TestCase):
    def run_outside_checkout(self, script, directory, **overrides):
        env = {**os.environ, 'GNANI_API_KEY': '', **overrides}
        if 'SAATHI_DB_PATH' not in overrides:
            env.pop('SAATHI_DB_PATH', None)
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=directory, env=env,
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_editable_install_retains_root_environment_and_default_database_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_outside_checkout('''import json
from saathi import app
print(json.dumps({'root': str(app.ROOT), 'database': str(app.DB),
                  'assets': str(app.PACKAGE_ROOT / 'static')}))
''', directory)
        self.assertEqual(Path(result['root']), ROOT)
        self.assertEqual(Path(result['database']), ROOT / 'saathi.db')
        self.assertEqual(Path(result['assets']), ROOT / 'src' / 'saathi' / 'static')

    def test_installed_package_serves_assets_with_a_disposable_database_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_outside_checkout('''import json
from fastapi.testclient import TestClient
from saathi.app import app
with TestClient(app) as client:
    page = client.get('/')
    asset = client.get('/static/audio.js')
    print(json.dumps({'page': page.status_code, 'asset': asset.status_code,
                      'has_title': '<title>Saathi' in page.text,
                      'missing_key': not client.get('/api/health').json()['gnani_configured']}))
''', directory, SAATHI_DB_PATH=str(Path(directory) / 'temporary.db'))
        self.assertEqual(result, {'page': 200, 'asset': 200, 'has_title': True, 'missing_key': True})
