# Inspection and verification record

Date: 8 November 2026. This record distinguishes source review, executed checks and checks awaiting a working runtime/account.

## Final pre-submission inspection — latest check

- **READY:** initialized local Git branch `main` and staged **41 reviewed release files**. There was no existing tracked history. No commit, remote, GitHub repository creation, push, deployment or organizer submission was performed. A command-scoped trust setting for this exact user-owned workspace resolves the sandbox account's ownership difference; global Git trust/configuration was not changed.
- **READY:** inspected the source, example environment files, current deployment guards and submission ZIP. Local `.env`, `saathi.db`, generated recordings/logs, browser profile and runtimes are expected private/development artifacts and stay ignored. They are not public release content. The final source/Git-index/ZIP check inventories the whole tree and scans actual configured secrets plus common credential patterns without printing values or opening database records.
- **READY:** the actual staged index and rebuilt ZIP each contain the same **41 source files**, with no configured secret or common credential-pattern findings. A negative check deliberately inserted a nonsecret `.env` fixture into a separate disposable ZIP; the checker blocked it with exit code 1 while leaving the real archive unchanged. `.env`, `saathi.db` and `.env.production` are absent from the actual Git index.
- **READY:** fresh real Hindi roundtrip through the running server: `/api/tts` **HTTP 200**, `/api/stt` **HTTP 200**, generated audio **2.24 seconds**, routed intent **read**. No private inbox content was used and the probe kept its audio in memory. This is live integration evidence, not a latency or accuracy benchmark.
- **READY:** current standard regression run passed **53 Python tests**, with **8 opt-in browser/live tests skipped**, and **22 frontend tests**. Dependency compatibility passed. The previous full **83/83** run, including those opt-in tests, remains recorded below; it was not misrepresented as a newly repeated full run.
- **READY:** `connection_verified=false` remains intentional: health itself does not make a paid provider call. The frontend uses configuration presence to offer speech and handles actual request/playback outcomes separately. The false health field does not disable live functionality, as demonstrated by the fresh successful requests.
- **READY:** README/demo/submission/deployment text accurately distinguishes in-app messages, extractive summaries, local drafts, confirmed reminders, real Gnani calls, automated virtual-microphone evidence and owner-reported manual testing. Screenshots contain only disposable example data.
- **BLOCKED:** no running Docker daemon was found even in the authorized host context. No hosted container/TLS/authentication/persistence acceptance was performed. The publicly reachable evaluator demo still needs a host/domain/DNS, private production environment values, Docker runtime checks and deployment authorization.
- **BLOCKED / OWNER COMPLETION:** actual contributor details and the recorded final demo remain to be completed by the owner. No GitHub account/remote URL, identities, final video or organizer acceptance were invented.
- **OPTIONAL / NOT CLAIMED:** formal screen-reader/WCAG review, representative user studies, production load/abuse assessment and reliable background/closed-tab alarms. Current architecture remains a restricted single-user evaluator demo.

See `PRESUBMISSION_CHECK.md` for exact safe Windows PowerShell staging/check/commit/push commands, Windows recording steps and final authorization-dependent deployment steps. The checked ZIP is rebuilt from the reviewed Git index; `test-results/pre-submission-results.json` and `dist/manifest.json` record the current counts/checksum without secret values. Re-run the checker after any edit; no universal secret-scanner guarantee is claimed.

## Final submission preparation — current result

Target submission date: **November 10, 2026**, supplied by the owner. No organizer submission, deployment or GitHub push has been performed.

| Status | Result |
| --- | --- |
| **VERIFIED** | Final full Python run: **61 passed, 0 failed, 0 errors, 0 skipped**, in 157.002 seconds. All opt-in browser/live flags were enabled, with the configured key and genuine generated input audio. Breakdown: 16 API/database, 2 Chrome UI, 11 Gnani adapter, 3 real HTTP, 1 real speech smoke, 15 intent/time, 8 production/release and 5 real-provider Chrome tests. |
| **VERIFIED** | Frontend: **22 passed**, with JavaScript syntax and dependency checks. Total final automated checks: **83 passing tests**. These counts are tests, not usability/performance/accuracy metrics. |
| **FAILED → FIXED → VERIFIED** | First final sweep: 59/60 passed. Prisma returned `रावी को message लाखो, मैं कल आऊँगा।`; the draft router correctly declined the unrecognized wording without saving anything. Added the observed `लाखो` variant only immediately inside the explicit drafting prefix, preserving recipient and reply for required confirmation. Added a bounded regression that rejects unrelated uses; full rerun passed 61/61. |
| **VERIFIED** | Existing UI refined in place: consistent typography/spacing, readable Hindi/Hinglish transcript/response, keyboard-scrollable long responses, restrained listening/dialog animations with reduced-motion support, and a speech badge updated only after real successful calls. No framework or architecture replacement. |
| **VERIFIED** | Chrome desktop/mobile, high contrast, larger text, unique accessible labels, skip link, keyboard submission, dialog focus wrapping, real reading/summary/draft/reminder/confirmation/audio playback and actual due alerts passed. Updated public screenshots use only disposable example data and genuine live-service results. |
| **USER-REPORTED PASS** | The owner states that all core features and real Gnani voice interactions passed manual testing. This is recorded as owner-reported acceptance, separately from automated virtual-microphone evidence. No claim of an instrumented physical-device study or screen-reader certification is inferred. |
| **VERIFIED** | Production guards reject missing gateway authorization, HTTP data/actions, unexpected hosts and incomplete startup configuration. Same-origin writes through the authorized HTTPS scope, container health and persistent database connections were checked. |
| **VERIFIED** | Real Git ignore-rule tests exclude environment files, runtimes, databases, audio, logs, caches and private folders while retaining safe example files/screenshots. Docker uses an explicit source allowlist and a non-root app. |
| **VERIFIED** | Compose configuration parsed with `config --quiet` and validation-only values. Official Caddy 2.11.8 accepted the HTTPS/auth proxy configuration. All **19 pinned Linux/Python 3.12 runtime wheels** were downloaded successfully for availability checking. |
| **BLOCKED** | Docker image build/runtime checks: Docker daemon is not running in this environment. Build-only CI configuration is prepared but has not run. No remote host/domain, TLS issuance, deployed authentication or remote-volume restart/restore check is claimed. |
| **NOT TESTED** | Human NVDA/other screen-reader review, a formal accessibility audit, representative intended-user usability, background/closed-tab notification reliability, production load/abuse resistance and hosted uptime. No metrics or testimonials are fabricated. |
| **OWNER INPUT REQUIRED** | Contributor names/actual contribution attribution remain explicitly marked for completion in `SUBMISSION.md`. Final video recording and any authorized GitHub/hosting publication are not completed. |

Submission materials: `README.md`, sanitized `docs/screenshots/`, `DEMO_SCRIPT.md`, `SUBMISSION.md`, `DEPLOYMENT.md` and `VOICE_TESTING.md`. The prepared production route is a restricted, authenticated **single-user evaluator demo**, not an unrestricted multi-user service. Production still needs an owned domain/host, private environment values, password hash, gateway token, Docker/runtime acceptance and explicit deployment authorization.

The source workspace currently has no Git repository/history. Ignore rules have been exercised in a disposable repository, but actual future tracked files/history still need review before publication. No existing personal database, key, recording, local environment or test log should be included in the source release.

## Focused real voice follow-up — latest status

This section supersedes the earlier credential/browser blockers below. The existing application and UI were retained; this was a focused real-provider and Chrome verification, not a repeat of the original audit.

| Status | Check | Evidence / limit |
| --- | --- | --- |
| **VERIFIED** | Credential configuration | A nonempty, non-placeholder `GNANI_API_KEY` is now present in server `.env`. It was not printed, put in command arguments, exposed to the frontend or committed. Real requests authenticated successfully. |
| **VERIFIED** | Current official REST contracts | Rechecked [Prisma REST](https://docs.gnani.ai/api/STT/speech-to-text), [Timbre REST](https://docs.gnani.ai/api/TTS/tts-inference) and [quick start](https://docs.gnani.ai/api/introduction/quick-start). Endpoint URLs, `X-API-Key-ID`, STT multipart fields / Hindi hint / transcribe format, Timbre v2.5 Nalini, Hindi/Hinglish languages and PCM WAV output settings match the published contract. |
| **FAILED → FIXED → VERIFIED** | Genuine Timbre WAV rejected as truncated | Real HTTP 200 returned complete PCM with RIFF/data length fields set to `0xffffffff`. Observed 199,724 response bytes and 199,680 actual PCM bytes at 48 kHz. Added finalization of those streaming length fields only; compared PCM before/after byte-for-byte. Ordinary sized truncated WAVs, missing data chunks, empty PCM and partial samples remain rejected. Real synthesis and Chrome playback passed after the fix. |
| **VERIFIED** | Real Hindi generation + transcription | Generated actual Hindi WAV through Timbre; Prisma transcribed genuine provider-generated speech and the existing router recognized `read`. No fake provider response or browser speech-provider fallback was used. |
| **VERIFIED** | Chrome full recording path with real services | Four opt-in voice-flow tests passed in installed Chrome in 103.113 seconds, and a separate targeted timed-reminder test passed in 32.191 seconds: **5 real-provider Chrome tests passed**. Input was genuine Timbre-generated audio fed through a test-only virtual microphone; production MediaRecorder capture → browser WAV resampling → backend Prisma → intent/action → backend Timbre → Chrome `audio.ended` all ran. No request interception or fabricated API response. |
| **VERIFIED** | Hindi reading and summarization | Chrome voice command read a real disposable-inbox message and played the real Hindi output. Extractive summary displayed the message details and real playback completed. |
| **VERIFIED** | Hinglish drafting and confirmation | Genuine Hinglish speech through Chrome/Prisma opened the correct review; database stayed unchanged before confirmation; one draft was saved after confirmation, followed by real playback. A separate spoken Hindi `haan` virtual-microphone test confirmed only the current pending draft. |
| **VERIFIED** | Hindi reminder and completion | Real Chrome/Prisma input parsed a future reminder; confirmation was required before creation and completion; persisted results and real spoken responses were checked. |
| **VERIFIED** | Actual due-reminder announcement | Created and confirmed a real future reminder in the disposable database, waited for actual wall-clock time and the unchanged 10-second polling loop, and verified the due alert and genuine Timbre playback in active Chrome. No fake clock or API response. Background-tab scheduling and physical speaker audibility remain untested. |
| **FAILED → FIXED → VERIFIED** | Dialog keyboard focus boundary | A Chrome Shift+Tab boundary check failed. Added explicit Tab/Shift+Tab wrap at the confirmation controls; focused regression and Chrome retest passed. No visual redesign. |
| **VERIFIED** | Chrome keyboard, labels, contrast, layout | Two Chrome tests passed after the fix, covering skip link, Ctrl+Enter, cancel-first focus and modal wrapping, unique accessible field labels, audio label, persisted high contrast and 20-pixel root text, and no horizontal overflow at 320 / 390 / 768 / 1440 pixels. Desktop/mobile screenshots were inspected. |
| **VERIFIED** | Focused regressions | 11 provider-adapter tests and 22 frontend tests passed, plus JavaScript syntax checks. Existing backend/HTTP results below are retained rather than re-audited. |
| **BLOCKED → RESOLVED** | Sandbox outbound access and Playwright | First sandbox TTS attempt could not reach Gnani. With allowed network execution, real service calls worked and Playwright was installed in the project environment. No credential or Playwright blocker remains for this setup. |
| **NOT TESTED** | Physical microphone, acoustic conditions, speakers, subjective voice quality | Virtual audio capture and decoded Chrome playback do not prove device permission behavior on your normal browser profile, room/noise performance, actual speaker audibility or natural pronunciation. Use [VOICE_TESTING.md](VOICE_TESTING.md). |
| **NOT TESTED** | Human screen-reader acceptance and background-tab reminders | Labels/focus and an actual active-tab due alert were checked in Chrome, but NVDA/other screen-reader operation, physical audibility and background-tab reminder scheduling still need manual review. |

Reproducible evidence: `test-results/live-voice/chrome-voice-evidence*.json` (separate reports preserve each run), genuine generated WAVs in that directory, `chrome-real-read.png`, and desktop/mobile screenshots in `test-results/`. These are local ignored artifacts, not production fixtures. Automated voice tests are opt-in via `SAATHI_VOICE_E2E=1` and incur real API usage.

The existing localhost server was restarted with the configured key and corrected audio handling. Use `http://127.0.0.1:8000`. Its real `/api/tts` route was checked again: HTTP 200, valid Hindi WAV, duration 2.08 seconds. Health's `connection_verified=false` is intentionally a configuration-only response; that route itself does not make a real provider call.

Exact automated and manual next steps are in [VOICE_TESTING.md](VOICE_TESTING.md). No **unresolved** reproducible API/playback or keyboard failure remained in the checks above, and no missing-credential blocker remains. Physical-device, screen-reader and background-tab scheduling checks are explicitly not claimed as passed.

## Previous inspection and verification pass (historical)

The following records the earlier pass before the key was configured and network execution was allowed. Its original blockers have been superseded by the focused results above.

## Existing project inspected

Read every original source/configuration file: `app.py`, `logic.py`, all three `static/` assets, `tests/test_logic.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md` and `start_windows.bat`. No applicable `AGENTS.md` was present in the project or its parent directories. This workspace has no `.git` directory, so Git diff/status history was unavailable.

The existing architecture and stored-data schema were retained: FastAPI, SQLite, browser MediaRecorder/WAV conversion, server-side Gnani REST requests, an in-app inbox, extractive summaries, saved drafts and tab-open reminders. No replacement framework or external message transport was introduced.

## Findings and changes

| Inspected issue | Resulting change |
| --- | --- |
| Loose substring routing could mistake `prototype` for a draft and `already` for read | Token-aware Hindi/Hinglish matching, negation handling and exact confirmation phrases |
| A draft mentioning a reminder/summary could be routed as that other action | Parse the drafting prefix first; preserve authored content and extract recipient |
| Voice reminder commands copied the whole command into a form and did not parse time | Bounded relative/explicit Hindi/Hinglish time grammar, device offset and clarification for ambiguous/past times |
| Draft/reminder saves had no separate confirmation; reminder completion was immediate | Frozen server-side reviews, hashed one-use tokens, five-minute expiry, confirm/cancel and transactional replay protection |
| Long messages silently stopped at 900 characters | Sequential full-text TTS chunks, explicit 900-character server limit |
| Read flows could overwrite speech errors with a success status | Separate action result and spoken-playback status; preserve written outcomes on speech failure |
| Provider errors could reflect raw upstream content and only a RIFF prefix was checked | Sanitized error mapping, complete WAV validation, response-shape checks, timeouts and concurrency guard |
| Async STT called blocking `requests` directly | Run server speech work in FastAPI's thread pool |
| Repeated reminder polling rebuilt focused buttons | Only rerender a changed reminder list, with queued announcements and retry after refresh failure |
| Microphone permission, recorder and object-URL lifecycle had incomplete cleanup | Release tracks on every exit, discard stale recordings, abort superseded playback and revoke URLs |
| Small controls and fixed-pixel sizes limited the original large-text option | 48-pixel targets, rem-based type, persistent contrast/type, reduced motion, forced colors and a native confirmation dialog |
| Initial microphone label mixed hold-to-record and toggle instructions | Clear start/stop behavior, visible transcript, keyboard shortcuts and spoken guidance |
| Health said a configured key was ready without a provider test | Explicit configured-but-unverified service status |
| Only five routing/digest unit tests existed | Frontend, API/database, Gnani contract/error, optional real-browser and opt-in live-provider test suites plus CI |
| Windows setup could continue after Python environment creation failed | Stop with a clear runtime installation message |

## Executed locally

- **42 Python tests passed; 3 opt-in tests skipped** (45 discovered). Command: `.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v`.
- The 42 passing tests comprise **16 API/database tests, 14 Hindi/Hinglish logic tests, 9 Gnani transport-contract/error tests and 3 real HTTP acceptance tests**.
- The HTTP tests start an actual Uvicorn process with a disposable SQLite database, exercise messages, extractive summaries, draft cancellation/confirmation, reminder creation/completion and one-use token replay protection, then stop the process. They also verify static assets/security headers and real 503 responses for missing speech credentials. No HTTP/provider success is fabricated in these acceptance tests.
- **21 frontend regression checks passed** with Node 22.17 using `node --test tests/frontend.test.cjs`. These execute production UI functions against a test-only DOM and HTTP fixtures; they do not establish browser rendering or microphone behavior.
- `node --check static/app.js`, `node --check static/audio.js` and `node --check tests/static_preview.cjs` passed.
- **`pip check` passed**, and `pip install --no-index -r requirements.txt` confirmed that all application requirements are satisfied in the prepared local environment.
- The real app was started on **http://127.0.0.1:8000**. Its health endpoint returned HTTP 200 with `status=ok`, `gnani_configured=false` and `connection_verified=false`. App data was not populated with automated demo fixtures; acceptance tests used a separate disposable database.
- README PowerShell command blocks were parsed with PowerShell's parser; setup/test file references exist.

## Local environment recovery

The normal `py` launcher still reports no globally installed Python. A follow-up search found bundled installed Python runtimes and compatible installed dependencies. A working **project-local Python 3.12.2 runtime (`.python`) and virtual environment (`.venv`)** were prepared entirely inside the workspace, without changing the source applications/environments. SSL, SQLite and asyncio imports were checked after resolving a local SSL DLL lookup issue. Runtime and environment artifacts are ignored by Git and are not portable source files.

The HTTP-only app now depends on base Uvicorn, avoiding unnecessary optional compiled `standard` extras. The Windows launcher disables pip's version lookup so an already prepared environment can start without that extra network request.

One non-failing Starlette test-client warning recommends `httpx2`; the installed `httpx` compatibility path passed all tests. No extra dependency was added solely to remove that warning.

## Verification limits

- **Credentials:** `GNANI_API_KEY` in `.env` is blank and no key is present in the process environment. Real Prisma transcription, Timbre synthesis and microphone-to-provider-to-spoken-response testing remain blocked. A consented test WAV is also needed for the opt-in roundtrip test. No keys were copied from unrelated projects or fabricated.
- **Browser environment:** an explicit `SAATHI_E2E=1` browser-suite attempt stopped at setup with `ModuleNotFoundError: playwright`; no browser test actually ran. Installing Playwright could not resolve/download a package in the restricted environment. Earlier browser/native automation hosts were unavailable; headless Chrome attempts failed or stalled under sandbox graphics restrictions. The spawned test Chrome process was stopped. No screenshots, visual pass or screen-reader verification are claimed.
- **Network:** an official Python download probe could not connect. Outbound access from the app environment is restricted; provider connectivity will also need checking when credentials are supplied.
- The official current Gnani STT, TTS and quick-start documentation was read. The transport contract tests are tests of implementation against that published contract, not evidence of a successful live account call.
- The GitHub Actions workflow has been added but not run from this session. Live Gnani tests remain opt-in and may incur API charges. Normal discovery intentionally skips the 2 browser tests and 1 live-provider test.

## Remaining acceptance checks

1. Configure a valid key directly in the local `.env`, verify outbound provider connectivity, and restart the server. Supply a consented recording and run the opt-in real speech smoke test.
2. Run the Playwright suite once its dependency and a usable browser are available; inspect desktop/mobile screenshots and resolve any rendering issues it exposes.
3. Test the actual microphone → Prisma → intent → review → confirmation → Timbre flow. Verify Hindi/Hinglish audio quality, keyboard-only use with NVDA or another target screen reader, and reminders in active/background tabs.

This app remains a single-user local MVP. It does not send messages, import phone notifications, generate LLM summaries, provide reliable closed-tab alarms or claim accessibility certification.
