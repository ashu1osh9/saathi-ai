# Saathi AI — Final submission draft

**Challenge:** Gnani AI Internship Challenge 2026  
**Target submission date:** November 10, 2026, as requested by the project owner  
**Project:** Saathi AI — Your voice. Your independence.  
**Status:** working implementation and submission materials prepared; owner details, final video and publication require owner completion/authorization.

## Problem and target users

Reading messages, interpreting details, composing a reply and remembering a task often require accurate pointing, sustained screen reading or typing. These interactions can be difficult for visually impaired users and people with limited mobility. A useful assistant should support their language, expose what it heard, explain its results and ask before making changes.

Saathi focuses on Hindi/Hinglish-speaking users who benefit from voice input, spoken feedback, readable transcripts, large controls and keyboard operation. It does not assume every user has the same visual, motor or screen-reader needs.

## Solution

Saathi offers four connected workflows in its own inbox: read messages, extract important sentences, compose a local reply draft, and create reminders. Voice and typed input use the same bounded command router. Users see an editable transcript and hear feedback, then review a frozen recipient/body or reminder timestamp before confirming a save. A failed API request is reported as a failure; a saved draft is never described as a sent message.

The app preserves user control through cancel-first modal focus, spoken confirmation, large buttons, clear labels, persistent high contrast/text preferences and reduced-motion behavior. These features are implemented and tested within the documented scope; no accessibility certification or universal usability claim is made.

## Gnani AI technology

**Prisma STT** receives real browser-recorded WAV audio through the server and returns the Hindi/Hinglish transcript. **Timbre TTS** generates real spoken feedback, including review and saved-action responses. Keys remain in server environment variables; the browser never receives them.

The integration uses the official REST endpoints with authenticated requests, timeouts, validated response shapes and complete audio checks. A real interoperability issue was fixed: streamed Timbre WAV length sentinels are finalized without changing the returned PCM samples. Hindi/Hinglish routing also handles the observed `message लाखो` draft-prefix transcription variant in that specific command context, without rewriting the authored reply.

## Architecture and technologies

- FastAPI/Pydantic backend with server-only Gnani HTTP integration.
- Existing vanilla HTML, CSS and JavaScript frontend; no framework rewrite.
- Browser MediaRecorder and Web Audio conversion to 16 kHz, 16-bit mono WAV.
- SQLite for messages, drafts, reminders and expiring one-use action reviews.
- Python unittest, Node test runner and Playwright/Chrome acceptance tests.
- Prepared non-root Docker app, authenticated Caddy HTTPS gateway and persistent volume configuration; no deployment performed.

## Verification and real-world impact

The owner reports that core features and real Gnani voice interactions have passed manual testing. Automated evidence covers real Prisma/Timbre calls, Chrome recording through a virtual microphone fed genuine generated speech, intent routing, actual database actions, confirmation, playback and a due-reminder announcement. The final exact test counts and remaining limitations are recorded in `AUDIT.md`; they are engineering verification, not user-study or impact metrics.

The intended benefit is less dependence on precise typing/pointing for these everyday in-app tasks, with language choice and explicit user control. No adoption numbers, time savings, recognition accuracy, WER, satisfaction scores, testimonials or measured accessibility outcomes have been collected or claimed. Evaluation with intended users remains a next step.

## Honest boundaries

- Reads Saathi's inbox only; does not import SMS, WhatsApp, Gmail, OS notifications or screen contents.
- Replies are local drafts, never sent to a recipient.
- Summaries select existing sentences; there is no generative LLM summary.
- Reminders persist, but announcements require the open app; background timers can be delayed.
- Recognition may make mistakes; review recipient/content/time before confirmation.
- Automated virtual-microphone tests do not replace physical-device or human screen-reader acceptance. The owner's manual pass is reported separately.
- Deployment is prepared for a restricted single-user evaluator demo, not a public multi-user service. Remote TLS, authentication and storage acceptance checks remain to be run after authorization.

## Team contributions — owner confirmation required

No contributor identities were supplied in the request. Complete this table with actual names before submitting; do not infer identity from filesystem/account names.

| Contributor | Contribution that can be stated accurately |
| --- | --- |
| **Project owner: NAME TO CONFIRM** | Provided project requirements and reported manual acceptance of core features and real voice interactions. Add actual design/development ownership details. |
| **Other human contributors: CONFIRM OR REMOVE** | Add only named contributors and the work they actually performed. |
| AI-assisted engineering tooling | OpenAI Codex assisted with implementation iteration, regression tests, deployment configuration and document drafts in this workspace. The submitter must review and own the final submission. |

## Submission checklist

- [ ] Confirm contributor names and contribution descriptions.
- [ ] Review `README.md`, sanitized screenshots and `AUDIT.md`.
- [ ] Record the real demo using `DEMO_SCRIPT.md`; add its final link if required.
- [ ] Decide whether an authorized private HTTPS deployment is needed and complete `DEPLOYMENT.md` acceptance checks if so.
- [ ] Authorize and perform the GitHub push/publication; review tracked files for secrets and private data first.
- [ ] Review the organizer's current submission form/rules and submit by the owner's target date.

Nothing has been pushed, deployed or submitted to the organizer from this session.
