# Saathi AI — 60-second demonstration

**Purpose:** show useful Hindi/Hinglish voice interaction and user control with genuine Gnani services. The timeline is a rehearsal plan, not a measured API latency claim. Do not replace slow or failed calls with staged success.

For built-in Windows recording steps, see [PRESUBMISSION_CHECK.md](../reports/PRESUBMISSION_CHECK.md#simplest-authentic-windows-recording).

## Before recording

- Use the tested Chrome setup with working physical microphone/speakers, a valid server-side key and provider connectivity. Keep this browser tab active.
- Use a clean, separate demo database (`SAATHI_DB_PATH`) so no private messages, recipients or reminders appear. Never show `.env`, terminal environment output or credentials.
- Add the example message before recording: sender **Demo office**, body **“कल चार बजे बैठक है।”** Use only this synthetic content.
- Choose Hindi speech, normal speed and automatic responses. Place the voice space on screen. Rehearse once to check real service timing.
- Drafts are local only. A reminder created one minute into the future will not necessarily fire within this 60-second video; show its confirmed saved state honestly. A longer companion clip can show the actual due alert.

## Live sequence

| Time | Show / say | Working evidence |
| --- | --- | --- |
| 00–05 | “Saathi helps people who find screens or typing difficult use everyday tasks in Hindi and Hinglish.” | Large microphone control, transcript and response panels. |
| 05–15 | Start/stop recording: **“मेरा संदेश पढ़ो।”** Let the short real response be heard. | Prisma transcript, the actual in-app message and Timbre audio. |
| 15–22 | Choose **Get key details**. “These are extractive key details from the same message.” | Actual summary response; do not call it an LLM summary or imported phone inbox. |
| 22–40 | Speak **“Ravi ko message likho, main aaunga.”** Hear/review recipient and text, then say **“haan”** using Speak confirmation. | Review appears before saving; exactly one draft is saved, with **nothing sent** wording. |
| 40–54 | Speak **“एक मिनट बाद पानी पीना याद दिलाना।”** Review the date/time and confirm with the large button. | Real parsed future reminder and explicit confirmation; saved reminder appears. |
| 54–60 | “Real Gnani speech. Readable transcripts. Confirmation before changes. Saathi: your voice, your independence.” | Show the saved result and one accessibility preference, with no fake counters or claimed outcomes. |

Do not talk over the assistant's spoken output. If a review is long, use Stop audio only after its recipient/content or reminder time has been heard and checked; then explicitly confirm. Shorten narration first. If real network timing makes a continuous 60-second take impractical, provide an honestly edited 60-second overview plus a longer uncut working clip; do not imply an API call succeeded when it failed or invent performance metrics.

## If something fails during the take

- Misheard command: cancel the review or edit the visible transcript and rerun. Show that the user remains in control.
- Provider/network failure: show the truthful error, keep the written result, and retry only when ready. Do not switch to fake audio/API success.
- Recording permission denied: fix the site's microphone permission or show typed fallback explicitly as typed interaction.
- Never send anything externally: the demonstrated reply is a saved draft only.

## Recording deliverables

Record the final clip yourself after reviewing the team details in `SUBMISSION.md`. No final video, organizer upload or GitHub publication has been performed by this workspace session. Keep a 90–120 second uncut companion clip if judges need to see a due reminder and the complete confirmation readback.
