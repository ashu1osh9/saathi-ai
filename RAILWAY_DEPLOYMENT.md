# Railway HTTPS evaluator demo

Prepared for owner review on November 9, 2026; **not deployed**. The owner reports green GitHub Actions on base commit `493627f`. These new changes still need review, commit/push and a green run. No Railway account setting, paid resource or deployment was created by this preparation.

## Architecture and boundaries

```text
Chrome → Railway HTTPS edge → FastAPI application password gate → SQLite /data/saathi.db
                                             └──────────────→ real Gnani Prisma / Timbre
```

This is one shared evaluator inbox, not isolated user accounts. Use example data and give the login only to trusted evaluators. Basic authentication uses the browser's native login dialog over HTTPS; no password, Gnani key or gateway token is embedded in frontend files. The server stores only a salted scrypt password hash in Railway variables. Browsers cache the login; close the private browsing window to end the demo session, and rotate the hash to revoke old passwords.

Local `uvicorn app:app` remains unchanged. Compose explicitly keeps `SAATHI_AUTH_MODE=gateway` and Caddy authentication. Railway uses `SAATHI_AUTH_MODE=basic`, with no Caddy service and no `X-Saathi-Gateway` header requirement. Authentication cannot be disabled in production.

## Generate your private login hash locally

Use a password manager to choose a unique password of at least 16 characters. In your normal PowerShell, from the prepared project:

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
& .\.venv\Scripts\python.exe -B .\tools\hash_demo_password.py
```

Type the password twice at the hidden prompts. Copy the entire resulting `scrypt-v1$...` hash privately into `SAATHI_APP_PASSWORD_HASH`. It is sensitive configuration: do not commit it, include it in screenshots or paste it into a public issue. Do not use the Caddy bcrypt hash in this variable. The plaintext password goes only to your password manager and the private evaluator login.

## Exact service variables

Set these in the **application service → Variables**, not in Git or client JavaScript. Dashboard values are literal: do not add surrounding quotes to the hash. Leave Railway's provided variables managed by Railway.

| Variable | Value |
| --- | --- |
| `SAATHI_ENV` | `production` |
| `SAATHI_AUTH_MODE` | `basic` |
| `SAATHI_ALLOWED_HOSTS` | Your exact generated hostname, e.g. `YOUR-SERVICE.up.railway.app`; no scheme, port, path or wildcard |
| `SAATHI_DEMO_USER` | Your chosen evaluator username; 1–64 ASCII letters/digits, `.`, `_`, `-` |
| `SAATHI_APP_PASSWORD_HASH` | Entire private hash from the generator above |
| `GNANI_API_KEY` | Your real Gnani speech key, pasted privately; never set it as a build argument |
| `GNANI_STT_MODEL` | `prisma-v3.0` |
| `GNANI_TTS_MODEL` | `timbre-v2.5` |
| `GNANI_TTS_VOICE` | `Nalini` |
| `SAATHI_DB_PATH` | `/data/saathi.db` |
| `PORT` | `8080` (use the same target port in Networking) |
| `FORWARDED_ALLOW_IPS` | `*` **only for this Railway service behind its HTTP edge** |
| `RAILWAY_RUN_UID` | `0`, only for the startup ownership repair described below |
| `SAATHI_REQUESTS_PER_MINUTE` | `120` |
| `SAATHI_AUTH_FAILURES_PER_MINUTE` | `20` |
| `SAATHI_SPEECH_PER_MINUTE` | `20` |
| `SAATHI_SPEECH_PER_DAY` | `200` |

Do not set `SAATHI_PROXY_TOKEN`, `SAATHI_DOMAIN` or `SAATHI_DEMO_PASSWORD_HASH` for this service; those belong to Compose/Caddy. Railway supplies `RAILWAY_VOLUME_MOUNT_PATH=/data` when the volume is attached; **do not fabricate that variable to imitate a missing volume**.

## Dashboard setup — owner-executed, only after approving costs and deployment

Creating services/volumes and deploying can incur charges. Review your Railway plan, resource limits and usage controls first. This document does not authorize or perform spending.

1. Create an empty Railway project and an empty application service. Disable automatic deployments before connecting the repository. Do not import `compose.yaml`: this Railway path uses one FastAPI container.
2. Add a persistent Volume to that service, mount it at **`/data`**, and choose an approved capacity. Keep one region and **one replica**. Do not add another service/replica that writes to the same database.
3. In service Settings → Networking → Public Networking, generate a Railway domain with target port **8080**. Record the actual hostname. If the dashboard requires an initial build before generating a domain, temporarily use the exact reserved hostname `pending.invalid` in the host allowlist, keep authentication enabled, and let the HTTP health probe succeed. Then generate the domain and replace `pending.invalid` with the actual hostname before evaluator access. Never use `*` to bootstrap hosting.
4. Add the variables above, using that exact hostname. Paste the real Gnani key and generated hash privately; seal sensitive variables if your dashboard offers it. No real secret is needed at build time.
5. Connect **`ashu1osh9/saathi-ai`**, branch `main`, repository root `/`. Use the reviewed deployment commit, after its Actions checks pass. Connecting a GitHub source may itself stage or trigger deployment; keep autodeploy disabled and review staged changes before applying them.
6. Confirm the Dockerfile builder and `/railway.json` config. Leave custom Build, Start and Pre-deploy commands **empty**. The Dockerfile runs `python serve.py`; overriding it can skip privilege handling. `railway.json` specifies the Dockerfile, one replica, required `/data` mount, disabled sleeping, `/api/health`, a 120-second startup check and at most three failure restarts.
7. Review all staged changes. **Only when you authorize deployment**, deploy the reviewed commit. Inspect startup/build logs privately. No secret values should be printed. The app must fail closed on missing login/key/volume, invalid hosts or root execution.
8. Use the generated **HTTPS** URL. Railway provisions TLS; do not expose a TCP proxy or add direct backend access. `FORWARDED_ALLOW_IPS=*` is appropriate only while all public ingress passes through Railway's edge. Raw forwarded headers are not accepted by the application itself; Uvicorn processes them from the configured proxy boundary. Hosts remain checked against the actual Host header, not a browser-supplied forwarded-host value. See [Railway networking](https://docs.railway.com/networking/public-networking) and its [documented headers](https://docs.railway.com/networking/public-networking/specs-and-limits).

Railway's HTTP edge supplies `X-Forwarded-Proto=https`. Health probes use `healthcheck.railway.app`, accepted **only** for GET/HEAD `/api/health`; that hostname cannot access data routes. `/api/health` is deliberately unauthenticated and performs no paid call. Its `connection_verified=false` still means that health has not tested Gnani. See [Railway health checks](https://docs.railway.com/deployments/healthchecks).

## Volume permissions and persistence

Railway mounts volumes as root and documents `RAILWAY_RUN_UID=0` for non-root images. This image retains `USER 10001:10001` for Compose. On Railway, `serve.py` briefly starts as root, opens the `/data` directory without following symlinks, repairs ownership/modes only on the mount and known SQLite files, clears supplementary groups, and switches to UID/GID **10001** before executing Uvicorn. The long-running app never needs root. Existing database records are preserved; initialization only creates missing tables. [Railway volume documentation](https://docs.railway.com/volumes).

The startup repair does not recursively change backups or arbitrary volume files. Unsafe symlinks/hardlinks or unwritable storage cause startup to fail. Do not run a privileged pre-deploy command: Railway mounts the volume at container startup, not pre-deploy time. Do not replace this with `chmod 777` or run Uvicorn permanently as root.

Back up before deploying this schema addition (`speech_usage`) or rolling back. On the running service's private Railway shell, as the app user, a consistent SQLite backup can be created with:

```bash
python -c "import sqlite3; a=sqlite3.connect('/data/saathi.db'); b=sqlite3.connect('/data/saathi.backup.db'); a.backup(b); b.close(); a.close()"
```

If the shell defaults to root because of `RAILWAY_RUN_UID`, use Railway's volume backup feature or run the backup as UID 10001; do not leave root-owned replacement database files. Download/store backups privately using approved Railway tooling, and test restore while the app is stopped. Never remove the volume to redeploy; ephemeral container storage is not persistence. Volume-backed deployments can have brief redeploy downtime; do not promise zero downtime.

## Abuse safeguards and operational limits

- All UI/static/data/speech routes require authentication except the minimal health probe. Wrong credentials return 401; HTTPS, exact-host, same-origin mutation checks, restrictive CSP, no-store and microphone policies remain enforced.
- Global fixed-minute request and failed-login limits do not trust spoofable IP headers. Excessive requests return **429** and `Retry-After`. A global lockout can temporarily affect legitimate evaluators after an attack; this is a restricted demo, not a comprehensive DDoS solution. General/login counters reset with the process or next minute.
- Combined STT/TTS attempts are limited per minute and per UTC day in SQLite. These counters survive restart, are atomically reserved before provider use and include failed/invalid attempts conservatively. A chunked long spoken response can consume several attempts. Exceeding speech quota leaves typed workflows available, subject to the general request cap. These are request caps, **not a monetary spending guarantee**; configure provider account controls and monitor usage separately.
- Production request bodies are capped at 9 MiB, including streaming/chunked uploads. Existing WAV/STT size/duration/format checks, 900-character TTS chunks, timeouts and one-call concurrency protection remain intact.
- Keep one Uvicorn worker/replica. Credentials are shared; all authenticated evaluators can see the same example inbox. Reminders need the open browser, and background throttling can delay announcements. Sleeping is disabled in the prepared config; review the resulting resource usage before deploying.

## Acceptance checklist after authorized deployment

1. Open an incognito Chrome window. Confirm a valid HTTPS certificate and a login challenge before the app/static/API is accessible; test a wrong password. Health alone may return 200 without login.
2. Log in privately. Confirm no key/hash/gateway token in frontend assets or browser responses. Check the actual process UID through private runtime inspection; it must be 10001.
3. Allow microphone access to this HTTPS origin. Test real Hindi/Hinglish transcription, reading, key details, draft cancel/confirm, reminder save/complete and real Timbre playback. Never replace a failed provider result with a staged success.
4. Verify keyboard-only navigation, Cancel focus, high contrast, large text and 320/390px reflow. Human screen-reader acceptance is still a separate check.
5. Create an example record, restart/redeploy the same service with its existing volume, and confirm records persist. Verify quota state survives restart. Create and restore a private backup before relying on persistence.
6. Confirm 401 for unauthenticated speech/data, 403 for cross-origin actions and 429 when configured limits are reached. Do not deliberately exhaust paid provider credits to test limits.
7. Privately share the HTTPS URL and login with evaluators. Revoke/rotate the password and stop public access after the challenge according to your data/billing decision.

## Verification status and release commands

Exact local outcomes are recorded in `AUDIT.md`. The Dockerfile build and corrected disposable container acceptance now pass locally, including the exact CI smoke command from Ubuntu. The harness refreshes Docker's ephemeral host port after restart; all authentication and persistence assertions remain. The reviewed fix still needs a fresh green GitHub Actions run after the owner pushes it. Railway TLS, real mounted-volume behavior, edge routing, hosted microphone permissions and hosted Gnani account connectivity remain unverified until an authorized deployment.

Before pushing, ensure Railway autodeploy is disconnected/disabled; a Git push must not silently become a deployment. Review and execute in PowerShell:

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed.' }
git add -- .dockerignore .github/workflows/tests.yml Dockerfile app.py compose.yaml demo_security.py serve.py railway.json RAILWAY_DEPLOYMENT.md DEPLOYMENT.md README.md AUDIT.md tests/test_railway.py tests/test_railway_http.py tests/test_container_smoke.py tools/hash_demo_password.py tools/container_smoke.py
if ($LASTEXITCODE -ne 0) { throw 'Staging failed.' }
& .\.venv\Scripts\python.exe -B .\tools\pre_submission_check.py --require-git --rebuild-zip
if ($LASTEXITCODE -ne 0) { throw 'Release check failed.' }
git diff --cached --stat
git commit -m "Prepare secure Railway deployment with persistent SQLite"
if ($LASTEXITCODE -ne 0) { throw 'Commit failed.' }
git push origin main
```

Wait for green unit/browser/container checks on that new commit before authorizing the separate Railway deployment. No push/deployment command above was executed by the assistant.
