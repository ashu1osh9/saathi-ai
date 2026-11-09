# Professional structure refactor

Branch: `refactor/professional-structure`, based on `b1b5e29`.

## Inspection and implementation plan

The original 50 tracked files comprise five root Python modules, four frontend
assets, backend/frontend/browser/security tests, three operator tools, deployment
configuration and competition/verification documents. Imports, subprocess commands,
mock patch targets, static filesystem paths and documentation links were mapped
before moving code. A baseline OpenAPI schema, source hashes, assertion counts and
private-file fingerprints are retained locally under ignored `test-results/`.

1. Move the existing modules/assets with `git mv` into `src/saathi`; retain API URLs,
   schemas, business logic, provider contracts and security behavior.
2. Define setuptools packaging and include static assets in installed wheels. Use
   editable installs for development and a normal package install in Docker.
3. Keep checkout-root `.env` and default `saathi.db` discovery independent of CWD.
   Installed wheels use the working directory for optional local configuration/data;
   deployed services retain their explicit environment and `/data/saathi.db`.
4. Update tests, tools, startup commands, Docker copies and CI to package imports.
   Move competition, deployment and historical reports into their corresponding
   docs folders and repair links. Preserve old verification entries as history.
5. Verify API/asset equivalence, existing assertions, package/wheel operation,
   browser/security suites, real Docker smoke acceptance, Railway schema, release
   exclusions and the ZIP. Compare private fingerprints without displaying values.

## Move map

| Previous path | New path |
| --- | --- |
| `app.py`, `gnani.py`, `logic.py`, `demo_security.py`, `serve.py` | `src/saathi/` |
| `static/` | `src/saathi/static/` |
| `../demo/DEMO_SCRIPT.md`, `../demo/SUBMISSION.md`, `../demo/VOICE_TESTING.md` | `docs/demo/` |
| `../deployment/DEPLOYMENT.md`, `../deployment/RAILWAY_DEPLOYMENT.md` | `docs/deployment/` |
| `AUDIT.md`, `PRESUBMISSION_CHECK.md` | `docs/reports/` |

Infrastructure, dependency files, README, operator tools, tests and screenshots
remain in place. No database, environment file or recording is moved or deleted.

## Verification

| Check | Executed result |
| --- | --- |
| Windows Python + Playwright | **85 discovered; 79 passed, 6 skipped; 0 failures/errors**, 32.825s |
| Ubuntu Python + Playwright | **85 discovered; 79 passed, 6 skipped; 0 failures/errors**, 73.982s |
| Frontend / JavaScript | **22 passed**; `npm.cmd run check` passed |
| Dependencies | Editable installations on Windows/Ubuntu and Windows `pip check` passed; pinned runtime versions unchanged |
| API / implementation equivalence | Exact OpenAPI schema match; `gnani.py`, `logic.py`, `demo_security.py` and all four frontend assets remain byte-identical; existing assertion counts preserved or increased |
| Package distribution | Wheel built and installed normally into an isolated target; from another CWD it loaded local test configuration, served bundled assets and completed a real disposable database action |
| Docker / Railway mode | Image built; real root-owned-volume/UID 10001/auth/PORT/restart acceptance passed from Windows and with the CI-style command from Ubuntu |
| Compose-style backend | Read-only root, `/tmp`, default port 8000, gateway authorization, non-root startup and restart persistence passed in a disposable container |
| Configuration | Current official Railway JSON schema, workflow YAML and Compose `config --quiet` passed with nonsecret values |
| Documentation / private files | 33 local links/images checked; package imports valid; `.env` and `saathi.db` fingerprints unchanged at their original paths; `main` still points to `b1b5e29` |
| Source release / ZIP | **READY:** all 55 staged files match the rebuilt ZIP; archive integrity, configured-secret/common-pattern scan and private artifact exclusions pass with zero findings |

There are **101 unique passing Python/frontend tests**, without counting repeated
platform or container runs again. The same six billed provider tests remain opt-in;
no additional tests were disabled or skipped. No real Gnani call was made during
the structural refactor. Physical microphone/speakers, human screen-reader review,
hosted Railway TLS/edge behavior and remote backup/restore are not newly verified.

The layout follows the [Python packaging src-layout guidance](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
and bundles runtime assets through [setuptools package data](https://setuptools.pypa.io/en/latest/userguide/datafiles.html).
No additional backend framework, agent layer, ML directory or UI redesign was introduced.

## Final source tree

```text
saathi-ai/
├── src/saathi/
│   ├── __init__.py
│   ├── app.py
│   ├── gnani.py
│   ├── logic.py
│   ├── demo_security.py
│   ├── serve.py
│   └── static/{index.html,app.js,audio.js,styles.css}
├── tests/                      # Existing suites plus package/CWD regressions
├── tools/                      # Password, Docker and release-check tools
├── docs/
│   ├── README.md
│   ├── screenshots/{desktop.png,mobile.png}
│   ├── demo/{DEMO_SCRIPT.md,SUBMISSION.md,VOICE_TESTING.md}
│   ├── deployment/{DEPLOYMENT.md,RAILWAY_DEPLOYMENT.md}
│   └── reports/{AUDIT.md,PRESUBMISSION_CHECK.md,STRUCTURE_REFACTOR.md}
├── deploy/Caddyfile
├── .github/workflows/tests.yml
├── README.md
├── pyproject.toml
├── Dockerfile
├── compose.yaml
├── railway.json
├── requirements.lock
├── requirements.txt
├── requirements-dev.txt
├── requirements-e2e.txt
├── package.json
├── start_windows.bat
├── .env.example
├── .env.production.example
├── .gitignore
└── .dockerignore
```

Local ignored credentials, database, runtimes, caches and test artifacts are omitted
from this public-source tree; they remain on disk.

## Exact Windows PowerShell review and test commands

Use the existing branch; do not switch to or push main to review this work.

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
git branch --show-current
git diff HEAD --stat
git diff --cached --summary
& .\.venv\Scripts\python.exe -m pip install -r .\requirements-e2e.txt
if ($LASTEXITCODE -ne 0) { throw 'Installation failed.' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.browser-test\chromium'
& .\.venv\Scripts\python.exe -m playwright install chromium
$env:SAATHI_E2E = '1'
try {
    & .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Python/browser tests failed.' }
} finally {
    Remove-Item Env:\SAATHI_E2E -ErrorAction SilentlyContinue
}
node --test tests/frontend.test.cjs
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
npm.cmd run check
& .\.venv\Scripts\python.exe -m pip check
docker build --tag saathi-ai:refactor .
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed.' }
& .\.venv\Scripts\python.exe -B .\tools\container_smoke.py --image saathi-ai:refactor
if ($LASTEXITCODE -ne 0) { throw 'Container acceptance failed.' }
& .\.venv\Scripts\python.exe -B .\tools\pre_submission_check.py --require-git
if ($LASTEXITCODE -ne 0) { throw 'Source/ZIP check failed.' }
```

Start the existing local UI:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn saathi.app:app --host 127.0.0.1 --port 8000
```

After any further edit, restage the explicit source set and rebuild/check the ZIP:

```powershell
if ((git branch --show-current) -ne 'refactor/professional-structure') {
    throw 'Use the refactor branch; do not stage this work on main.'
}
git add -- .dockerignore .env.example .env.production.example .github .gitignore Dockerfile README.md compose.yaml railway.json pyproject.toml package.json requirements.lock requirements.txt requirements-dev.txt requirements-e2e.txt start_windows.bat src docs deploy tests tools
if ($LASTEXITCODE -ne 0) { throw 'Staging failed.' }
& .\.venv\Scripts\python.exe -B .\tools\pre_submission_check.py --require-git --rebuild-zip
if ($LASTEXITCODE -ne 0) { throw 'Release check failed.' }
git diff --cached --stat
```

The branch changes may be staged for release comparison, but are not committed,
pushed, merged or deployed by this task. GitHub Actions still needs to run on an
owner-reviewed commit; keep Railway autodeploy disabled during review. The demo
and submission content are preserved, including owner contribution/video fields.
