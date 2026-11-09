# Saathi real voice acceptance checklist

The real provider + Chrome automation now passes using a **virtual microphone fed genuine Gnani-generated audio**. The steps below verify what automation cannot establish: your physical microphone, speakers, pronunciation and screen-reader experience. Use example text rather than private messages for the demo.

## Start and check

The server was restarted with the configured key and WAV fix at **http://127.0.0.1:8000**. If it is already running, open that address in Chrome. To start after stopping the existing server:

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
& .\.venv\Scripts\python.exe -m uvicorn saathi.app:app --host 127.0.0.1 --port 8000
```

In another PowerShell window:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' | Format-List
```

`gnani_configured=True` checks presence only. `connection_verified=False` means this health route does not make a provider call; it does not contradict a successful real speech test. Never paste the API key into the browser or include it in screenshots/logs.

## Physical voice demo

1. Open Chrome at the localhost address. Leave **Speak responses automatically** enabled, select **Hindi**, and use normal speaking speed. Add sender `Demo college office`, message `कल शाम चार बजे बैठक है। कृपया जवाब दें।` in Suno.
2. Choose **Start speaking**, allow microphone access, say **“मेरा संदेश पढ़ो”**, then choose **Stop recording**. Check that the microphone indicator turns off, the transcript contains your words, the correct message appears, and audible Hindi feedback finishes. The status should reach **Spoken response finished**.
3. Say **“Message ka summary batao”**. Check the extractive key details and listen for the same appointment information. Confirm that the app says neither that it imported phone messages nor that it used a generative summary.
4. Say **“Ravi ko message likho, main kal aaunga”**. Inspect the recipient and exact draft in the review. Nothing should appear in saved drafts yet. Use **Speak confirmation**, say **“nahi”**, then stop recording. Check cancellation and no saved draft.
5. Repeat the draft command. After hearing the review, choose **Speak confirmation**, say **“haan”**, then stop recording. Check one saved draft, spoken confirmation and the explicit **nothing sent** wording. Correct recognition errors by cancelling, editing the visible command, and running it again.
6. Say **“एक मिनट बाद पानी पीना याद दिलाना”**. Check the note, device time and future timestamp before confirming. Keep the tab active until the alert appears and is heard; an active tab normally polls within about ten seconds of the due time. Background throttling can delay alerts. Mark it done and confirm the completion.
7. Try **Hear response**, the native audio controls, slower speech, and **Stop audio**. Stopping audio must stop sound without deleting the written result or falsely undoing a saved action.

## Chrome keyboard, layout and error checks

| Check | Expected result |
| --- | --- |
| Tab from a freshly loaded page | Skip link is reachable; Enter moves focus to main content. |
| Alt+M, speak, Alt+M | Starts then stops recording, with visible pressed/listening state. |
| Ctrl+Enter in command box | Runs the typed command. |
| Confirmation dialog Tab / Shift+Tab | Focus wraps inside the dialog; initial focus is Cancel; focus returns after close. |
| Escape during recording | Recording is discarded; no action is saved. |
| Escape in a review | Cancels that review; nothing is saved by the pending action. |
| High contrast and A+ Text, then reload | Both preferences persist. |
| Chrome responsive widths 320, 390, 768, 1440 pixels | No horizontal page overflow, clipped fields or unreachable controls. These widths already passed automated overflow checks. |
| NVDA or another target screen reader | Input labels, live errors, transcript, response and confirmation contents are understandable. Turn off automatic speech if it competes with the screen reader. This requires a human check. |
| Block microphone for this localhost site in Chrome settings | A truthful permission error appears; typed commands still work; no action is claimed successful. Restore permission afterwards. |
| Chrome DevTools Network: Offline, then issue a command | A visible error appears and no success is claimed. Restore Online afterwards. |
| Speech service failure while a local action succeeds | Saved action remains saved; written response remains; speech status reports failure separately. |

## Reproduce automated Chrome checks

These commands use installed Chrome, a disposable test database and a new temporary browser profile. They do not change your normal browser profile. Playwright is now installed in this workspace; on a fresh checkout install `requirements-e2e.txt` first.

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
$env:SAATHI_BROWSER_CHANNEL = 'chrome'
$env:SAATHI_E2E = '1'
try {
    & .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_browser.py -v
} finally {
    Remove-Item Env:\SAATHI_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:\SAATHI_BROWSER_CHANNEL -ErrorAction SilentlyContinue
}
```

The following opt-in checks make **real billed Gnani calls**. They generate Hindi/Hinglish input audio with Timbre, feed it through Chrome's virtual microphone, capture it with the production MediaRecorder/resampler, transcribe with Prisma, perform the actual action/confirmation, and play real Timbre output in Chrome. No API responses are intercepted or replaced. A valid `.env` key and outbound provider connectivity are required.

```powershell
Set-Location -LiteralPath 'D:\Gennai\saathi-ai'
$env:SAATHI_BROWSER_CHANNEL = 'chrome'
$env:SAATHI_VOICE_E2E = '1'
try {
    & .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_voice_browser.py -v
} finally {
    Remove-Item Env:\SAATHI_VOICE_E2E -ErrorAction SilentlyContinue
    Remove-Item Env:\SAATHI_BROWSER_CHANNEL -ErrorAction SilentlyContinue
}
```

Evidence and genuine generated WAVs are saved under `test-results/live-voice/`, which is ignored by Git. A successful virtual-microphone test is not proof of a working physical microphone or audible speaker output. If Playwright/Chrome cannot run on another machine, use the manual checklist above and record browser automation as **BLOCKED**, rather than marking it verified.
