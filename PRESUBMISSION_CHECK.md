# Final pre-submission check — Saathi AI

Target date: **November 10, 2026**, supplied by the project owner. The owner reports creating the GitHub repository `saathi-ai`. Its owner/URL and remote contents have not been independently verified. No commit/push has been made by this check, and no deployment or organizer submission has occurred.

## READY

- Existing application, screenshots, documentation and submission source are prepared. No UI or application redesign was performed in this check.
- The previous full run passed **83 tests** (61 Python + 22 frontend, zero failures/skips). This preflight reran the standard suite: **53 Python passed, 8 optional tests skipped; 22 frontend passed; dependencies passed**. The eight are the opt-in browser/live tests, already covered by the previous full run.
- Fresh real-provider check: local `/api/tts` and `/api/stt` both returned **HTTP 200**. Genuine generated Hindi audio was transcribed and recognized as `read`; no private inbox content was accessed and no new recording was saved by that probe.
- Local `main` Git repository is initialized and only reviewed release files are staged. No author identity, remote URL or commit was invented. The key and private data stay local and ignored.
- `tools/pre_submission_check.py` inventories the whole tree, checks source/Git index/ZIP for configured secrets and common credential patterns, verifies required ignore rules and checks that ZIP/index/source agree. It never prints key values or database contents. Its scope is not a universal guarantee against every possible secret or sensitive prose.
- Production safeguards remain intact: HTTPS/password gate, private gateway header, restricted hosts, same-origin writes, one worker, non-root app and persistent SQLite/certificate volumes. No obvious new bypass was found in the source review or guard tests.

## BLOCKED / owner completion

1. **Hosted URL:** Docker daemon is unavailable here, and no approved host/domain/DNS or production gateway credentials are configured. Docker runtime, real hosted TLS/authentication and remote persistence/restore checks still need to run after authorization.
2. **Submission content:** confirm real contributor names/contributions in `SUBMISSION.md`; record the final demo video and complete the organizer's form. No identities, video URL or organizer acceptance are fabricated.
3. **Publication:** confirm the owner/URL and that the existing `saathi-ai` remote is empty, then explicitly choose when to execute the push. The local source is prepared; it has not been pushed by this check. If the remote already contains commits, stop and reconcile them without force pushing.

## OPTIONAL / beyond this submission check

Formal WCAG/screen-reader acceptance with intended users, a longer uncut reminder clip, production load/abuse testing, and a license chosen by the owner. Closed/background-tab alarms and isolated multi-user accounts are outside the current app's guarantees.

## Private files and ZIP scope

The working directory intentionally contains a configured `.env`, `saathi.db`, generated test audio/logs and local runtimes/caches. They are private/development artifacts, not submission content. They are excluded by `.gitignore`; the Docker context is allowlisted. Public screenshots come from controlled disposable test data, not the personal database.

The ZIP is rebuilt from the checked Git index and is ignored by Git under `dist/`. It contains the same reviewed source set, with no `.git`, `.env`, database, test recording, browser profile or virtual environment. The report is at `test-results/pre-submission-results.json`; the ZIP checksum is in `dist/manifest.json`.

Run the final check again after any edit. Staging does not make an ignored file safe; `.gitignore` also does not remove a secret that was already committed. This repository was created fresh and has no prior commit history. If a future check finds a real exposed credential, stop publication and rotate it rather than relying on ignore rules.

### Git release verification — November 8, 2026

- Branch `main`: **0 commits**, **41 staged files**, no unstaged source changes and no configured remote at inspection time.
- Initial inspection scanned all **43 then-existing local Git blob objects**, including unreferenced objects, for configured secret values and common credential patterns: **0 findings**. The scan is repeated after the release-documentation updates. With no commits, there is no committed file history to clean. This cannot attest to any independently created remote history.
- The ZIP contains the same **41 files** as the reviewed index, including source, frontend, dependency files, README/documentation, screenshots, Dockerfile, Compose/Caddy configuration and CI. Archive integrity and source/index/archive comparisons passed. Real `.env` files, databases, recordings, virtual environments and private artifacts are excluded.
- Redacted reports are local and ignored: `test-results/github-release-check.json` and `test-results/pre-submission-results.json`. No application code, Gnani integration or UI was changed during this release review. Automated functional test results above are prior runs, not newly rerun by this packaging check.

## Why health says `connection_verified=false`

`GET /api/health` is a lightweight app/configuration check. Its implementation deliberately returns `connection_verified: false`: it does not submit audio, synthesize speech, spend credits or continuously monitor the provider. `gnani_configured: true` only means the server has a key. The frontend enables speech using that presence flag and verifies actual success from `/api/stt`, `/api/tts` and playback. Therefore the false health field **does not prevent live functionality**. The fresh real HTTP 200 roundtrip is separate evidence that the configured services worked at check time; account/network conditions may change later.

## Exact Windows PowerShell publication steps — do not run the push until ready

First complete contributor details and review the final video/README. Use the **existing repository named `saathi-ai`** under your intended account. It should be empty, without an initial README/license/gitignore commit, since this project already has its own source ([GitHub's official instructions](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)). Confirm its visibility yourself.

In your normal Windows account's PowerShell, stage the explicit source set and synchronize/check the ZIP:

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
$source = @(
    '.dockerignore', '.env.example', '.env.production.example', '.github', '.gitignore',
    'app.py', 'AUDIT.md', 'compose.yaml', 'DEMO_SCRIPT.md', 'DEPLOYMENT.md', 'Dockerfile',
    'gnani.py', 'logic.py', 'package.json', 'PRESUBMISSION_CHECK.md', 'README.md',
    'requirements-dev.txt', 'requirements-e2e.txt', 'requirements.lock', 'requirements.txt',
    'start_windows.bat', 'SUBMISSION.md', 'VOICE_TESTING.md', 'deploy', 'docs', 'static', 'tests', 'tools'
)
git add -- $source
if ($LASTEXITCODE -ne 0) { throw 'Staging failed.' }
& .\.venv\Scripts\python.exe -B .\tools\pre_submission_check.py --require-git --rebuild-zip
if ($LASTEXITCODE -ne 0) { throw 'Release check blocked publication. Review the redacted findings.' }
git diff --cached --stat
git status --short
```

Review the filenames/statistics. You should see source/docs/screenshots, not `.env`, `saathi.db`, `.venv`, recordings or caches. Do not use `git add -f` on private files. If Git reports a repository ownership mismatch, use your normal owner account; do not globally trust every directory. The checker uses a command-scoped trust setting for this exact project only.

Set your **actual** public commit identity if needed (GitHub's verified or provided noreply email), then commit locally:

```powershell
git config --local user.name (Read-Host 'Your actual commit name')
git config --local user.email (Read-Host 'Your verified GitHub email or GitHub-provided noreply email')
git commit -m 'Prepare Saathi AI internship challenge submission'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed. Do not continue to push.' }
```

When you explicitly decide to publish, connect the empty repository and push:

```powershell
$owner = Read-Host 'GitHub account or organization that owns saathi-ai'
if ($owner -notmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$') { throw 'Invalid GitHub owner name.' }
$remoteUrl = "https://github.com/$owner/saathi-ai.git"
$existingOrigin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    if ($existingOrigin -ne $remoteUrl) { throw 'Existing origin differs. Review it manually; do not overwrite it blindly.' }
} else {
    git remote add origin $remoteUrl
    if ($LASTEXITCODE -ne 0) { throw 'Could not add origin.' }
}
git remote -v
$remoteRefs = @(git ls-remote origin)
if ($LASTEXITCODE -ne 0) { throw 'Remote verification failed. Do not push.' }
if ($remoteRefs.Count -gt 0) { throw 'Remote is not empty. Review and reconcile its history without force pushing.' }
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Push failed. Resolve authentication/network errors without force pushing.' }
```

Use the Git authentication/browser prompt. Never put a GitHub token, password or Gnani key into a remote URL. These are owner-executed instructions; no push was executed by the assistant. GitHub CLI is not required.

## Simplest authentic Windows recording

On Windows 11, use the built-in **Snipping Tool**: press **Win+Shift+R**, select only the Chrome app area, enable microphone and system/PC audio where available, and start recording. First make a five-second test and play it back to ensure both your voice and Timbre are audible. If audio controls are missing, update Snipping Tool or use another recorder that captures both channels. Microsoft documents the [video shortcut](https://support.microsoft.com/en-us/windows/apps/use-snipping-tool-to-capture-screenshots) and [microphone recording support](https://www.microsoft.com/en-us/windows/learning-center/how-to-use-snipping-tool-on-windows-screenshots-shortcuts-and-screen-recordings).

Keep the real app open at `http://127.0.0.1:8000`, allow its microphone, use only the example inbox, and follow `DEMO_SCRIPT.md`. Record read → key details → draft/review/haan → reminder/review/save. Do not show terminals, environment files, authentication prompts or private data. Save the clip outside the source tree or inside ignored `recordings/`, then verify the entire video before sharing.

The sixty-second timeline is a rehearsal plan, not an observed latency promise. Never replace failed/slow calls with staged success. A saved one-minute reminder need not fire inside the same sixty-second clip; show its saved state honestly or add a longer uncut companion clip.

## Final hosted-demo steps — authorization required

1. Choose an approved Linux Docker host and owned domain; start Docker and confirm `docker version` works. Point DNS at the host and allow TCP 80/443. Keep app port 8000 private.
2. On that host, copy `.env.production.example` to private `.env.production`; set the real domain, Gnani key, evaluator username, interactively generated bcrypt password hash and a separate random gateway token. Use owner-only file access; do not publish the resolved configuration.
3. Validate/build without exposing secrets:

```powershell
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production build
```

4. **Only after authorization**, start:

```powershell
docker compose --env-file .env.production up -d
docker compose --env-file .env.production ps
```

5. Verify a browser-trusted HTTPS certificate and HTTP redirect, incognito authentication, actual deployed voice flow and microphone permission. Never bypass a browser certificate warning. Caddy's [HTTPS requirements](https://caddyserver.com/docs/automatic-https) include real DNS, reachable ports and persistent certificate storage.
6. Confirm records survive an app restart; back up/restore SQLite privately. Named volumes `saathi_data`, `caddy_data` and `caddy_config` provide persistence. Do not use `down --volumes` as routine rollback.
7. Privately give evaluators the URL and login, with a note that all authenticated demo users share this example inbox. Use the fuller acceptance/backup instructions in `DEPLOYMENT.md`.

This is an authenticated, publicly reachable evaluator demo plan, not a verified deployed URL. Public source publication and hosted deployment are separate steps and neither has been performed automatically.
