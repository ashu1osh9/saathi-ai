'use strict';
const $ = id => document.getElementById(id);
const {splitSpeech, wavEncode, localDateValue} = SaathiAudio;
const notedReminders = new Set();
const preferences = {
  get(key, fallback) { try { return localStorage.getItem(`saathi.${key}`) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(`saathi.${key}`, value); } catch {} }
};
let gnaniReady = false;
const verifiedSpeech = new Set();
let lastReply = $('reply').textContent;
let recorder = null;
let mediaStream = null;
let recordState = 'idle';
let recordTimer = null;
let recordingVersion = 0;
let commandBusy = false;
let speechVersion = 0;
let speechAbort = null;
let finishPlayback = null;
let audioUrl = null;
let pendingAction = null;
let confirming = false;
let returnFocus = null;
let remindersLoading = false;
let reminderSignature = '';
const viewStatus = text => { $('status').textContent = text; };
const voiceStatus = text => { $('voiceStatus').textContent = text; if ($('confirmDialog').open) $('confirmStatus').textContent = text; };
const reply = text => { lastReply = text; $('reply').textContent = text; };
function speechSucceeded(service) {
  verifiedSpeech.add(service);
  $('apiStatus').textContent = verifiedSpeech.size === 2 ? '● Prisma + Timbre · verified this session' : `● ${service} · last call succeeded`;
  $('apiStatus').classList.remove('bad'); $('apiStatus').classList.add('good');
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = String(text ?? '');
  if (className) element.className = className;
  return element;
}
function clearError() { $('error').hidden = true; $('confirmError').hidden = true; }
function showError(error) {
  if (error?.name === 'AbortError') return;
  const message = error?.message || String(error);
  $('error').textContent = message; $('error').hidden = false;
  if ($('confirmDialog').open) { $('confirmError').textContent = message; $('confirmError').hidden = false; }
  viewStatus('Could not complete this request. Please review the error.');
}
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, signal: options.signal || AbortSignal.timeout(80000) });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please try again.`;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map(e => `${e.loc?.slice(1).join(' ')}: ${e.msg}`).join('. ');
    } catch {}
    const error = new Error(message); error.status = response.status; throw error;
  }
  return response;
}
const json = body => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
async function getJson(path, options) { return (await api(path, options)).json(); }
async function feedback(text) {
  reply(text);
  if ($('autoSpeak').checked) await say(text);
}
function stopSpeech() {
  speechVersion++;
  speechAbort?.abort(); speechAbort = null;
  $('playback').pause();
  if (finishPlayback) { finishPlayback(false); finishPlayback = null; }
  if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
  $('playback').removeAttribute('src');
  voiceStatus('Audio stopped. The written response is still available.');
}
async function say(text) {
  if (!text?.trim()) { voiceStatus('There is no text to read yet.'); return false; }
  stopSpeech();
  if (!gnaniReady) { voiceStatus('Spoken feedback unavailable: no server speech key. Your written response is available above.'); return false; }
  const version = speechVersion;
  const chunks = splitSpeech(text);
  speechAbort = new AbortController();
  try {
    for (let i = 0; i < chunks.length; i++) {
      if (version !== speechVersion) return false;
      voiceStatus(`Preparing Timbre audio ${i + 1} of ${chunks.length}…`);
      const response = await api('/api/tts', {...json({text: chunks[i], language: $('voiceLanguage').value, speed: Number($('voiceSpeed').value)}), signal: speechAbort.signal});
      const blob = await response.blob();
      if (version !== speechVersion) return false;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(blob);
      const audio = $('playback'); audio.src = audioUrl;
      const played = await new Promise((resolve, reject) => {
        finishPlayback = resolve;
        audio.onended = () => resolve(true);
        audio.onerror = () => reject(new Error('Audio playback failed. Use Hear response to retry.'));
        Promise.resolve(audio.play()).then(() => { if (version === speechVersion) voiceStatus(`Speaking with Timbre · part ${i + 1} of ${chunks.length}`); }).catch(() => reject(new Error('Browser blocked audio playback. Use Hear response or the audio player to listen.')));
      });
      finishPlayback = null;
      if (!played || version !== speechVersion) return false;
    }
    voiceStatus('Spoken response finished.');
    speechSucceeded('Timbre');
    return true;
  } catch (error) {
    if (version === speechVersion) {
      voiceStatus(`Speech unavailable: ${error.message}. The written response has been kept.`);
    }
    return false;
  } finally {
    if (version === speechVersion) { speechAbort = null; finishPlayback = null; }
  }
}
async function toWav(blob) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const context = new AudioContextClass();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    if (!decoded.length || decoded.duration > 30) throw new Error('Recording must contain audio and be under 30 seconds.');
    const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
    const source = offline.createBufferSource(); source.buffer = decoded;
    source.connect(offline.destination); source.start();
    const rendered = await offline.startRendering();
    return wavEncode(rendered.getChannelData(0));
  } finally { await context.close(); }
}
function updateRecordControls() {
  const active = recordState === 'recording';
  document.body.classList.toggle('listening', active);
  const busy = recordState === 'permission' || recordState === 'transcribing';
  for (const id of ['startTalk', 'confirmVoice']) {
    const button = $(id);
    button.disabled = busy || confirming;
    button.setAttribute('aria-pressed', String(active));
    button.classList.toggle('recording', active);
    button.textContent = active ? '■ Stop recording / रोकिए' : busy ? (recordState === 'permission' ? 'Waiting for microphone…' : 'Transcribing…') : id === 'startTalk' ? '◉ Start speaking · बोलिए' : '◉ Speak confirmation';
  }
}
function releaseMicrophone() { mediaStream?.getTracks().forEach(track => track.stop()); mediaStream = null; }
function discardRecording() {
  recordingVersion++;
  clearTimeout(recordTimer);
  if (recorder?.state === 'recording') recorder.stop();
  releaseMicrophone(); recordState = 'idle'; updateRecordControls();
}
async function toggleRecording() {
  if (recordState === 'recording') { recorder.stop(); return; }
  // A new recording may interrupt spoken feedback after a command has finished.
  if (recordState !== 'idle' || confirming || (commandBusy && !speechAbort)) return;
  clearError(); stopSpeech();
  if (!gnaniReady) { await feedback('Voice input is unavailable until a Gnani API key is configured on the server. You can type a command or use the task buttons.'); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !(window.AudioContext || window.webkitAudioContext)) {
    showError(new Error('Microphone recording needs a supported browser on localhost or HTTPS. You can still type commands.')); return;
  }
  const version = ++recordingVersion;
  recordState = 'permission'; updateRecordControls(); voiceStatus('Allow microphone access in your browser to continue.');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true, channelCount: 1}});
    if (version !== recordingVersion) { stream.getTracks().forEach(t => t.stop()); return; }
    mediaStream = stream;
    const type = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm'].find(t => MediaRecorder.isTypeSupported(t));
    const activeRecorder = new MediaRecorder(stream, type ? {mimeType: type} : {});
    recorder = activeRecorder;
    const parts = [];
    activeRecorder.ondataavailable = event => { if (event.data.size) parts.push(event.data); };
    activeRecorder.onerror = () => { discardRecording(); showError(new Error('Microphone recording failed. Please try again.')); };
    activeRecorder.onstop = async () => {
      clearTimeout(recordTimer); stream.getTracks().forEach(t => t.stop());
      if (version !== recordingVersion) return;
      mediaStream = null; recordState = 'transcribing'; updateRecordControls();
      try {
        voiceStatus('Converting your recording to 16 kHz WAV…');
        const wav = await toWav(new Blob(parts, {type: activeRecorder.mimeType}));
        if (version !== recordingVersion) return;
        const form = new FormData(); form.append('audio', wav, 'command.wav');
        voiceStatus('Gnani Prisma is transcribing…');
        const data = await getJson('/api/stt', {method: 'POST', body: form});
        if (version !== recordingVersion) return;
        $('transcript').value = data.transcript;
        speechSucceeded('Prisma');
        voiceStatus(`Transcribed with ${data.model}.`);
        recordState = 'idle'; updateRecordControls();
        await processCommand(data.transcript);
      } catch (error) { if (version === recordingVersion) showError(error); }
      finally { if (version === recordingVersion) { recordState = 'idle'; updateRecordControls(); } }
    };
    activeRecorder.start(); recordState = 'recording'; updateRecordControls();
    voiceStatus('Listening. Press Stop recording when you finish.');
    recordTimer = setTimeout(() => { if (activeRecorder.state === 'recording') activeRecorder.stop(); }, 25000);
  } catch (error) {
    if (version === recordingVersion) {
      releaseMicrophone(); recordState = 'idle'; updateRecordControls();
      showError(new Error(error.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow access in browser settings, or type your command.' : error.name === 'NotFoundError' ? 'No microphone was found. Connect one, or type your command.' : `Could not start recording: ${error.message}`));
    }
  }
}
async function processCommand(text) {
  if (commandBusy || confirming) return;
  if (!text?.trim()) { await feedback('कृपया बोलिए या लिखिए। Please speak or type a command.'); return; }
  commandBusy = true; $('runCommand').disabled = true; clearError(); viewStatus('Understanding your command…');
  try {
    const data = await getJson('/api/command', json({text, utc_offset_minutes: -new Date().getTimezoneOffset()}));
    if (pendingAction) {
      if (data.intent === 'confirm') return await confirmAction();
      if (data.intent === 'cancel') return await cancelAction();
      if (data.intent === 'stop') { stopSpeech(); return; }
      await say('पहले इस कार्रवाई की पुष्टि करें या रद्द करें। Say haan to confirm, or nahi to cancel this review.'); return;
    }
    if (data.intent === 'confirm') { await feedback('There is no action waiting for confirmation. Nothing was saved.'); return; }
    if (data.intent === 'cancel') { discardRecording(); await feedback('No action is waiting for confirmation.'); return; }
    if (data.intent === 'stop') { stopSpeech(); viewStatus('Stopped'); return; }
    if (data.intent === 'read') return await readMessages(Boolean(data.read_all));
    if (data.intent === 'summary') return await summarize(Boolean(data.read_all));
    if (data.intent === 'draft') {
      $('draftBody').value = data.draft_text;
      $('recipient').value = data.recipient || '';
      if (data.draft_text && data.recipient) return await reviewDraft();
      viewStatus('Draft needs details');
      ($('recipient').value ? $('draftBody') : $('recipient')).focus();
      await feedback('आपका ड्राफ्ट तैयार कर सकते हैं। Add the recipient and reply in the draft form, then choose Review draft. Nothing has been saved or sent.'); return;
    }
    if (data.intent === 'reminder') {
      const reminder = data.reminder;
      $('reminderNote').value = reminder.note;
      $('reminderDate').value = reminder.due_at ? localDateValue(reminder.due_at) : '';
      if (reminder.note && reminder.due_at && !reminder.clarification) return await reviewReminder(reminder.due_at);
      viewStatus('Reminder needs details');
      (reminder.note ? $('reminderDate') : $('reminderNote')).focus();
      await feedback(reminder.clarification || 'Please add a reminder note and choose a future time, then select Review reminder.'); return;
    }
    viewStatus(data.intent === 'help' ? 'Available commands' : 'Command not recognized');
    await feedback('मैं संदेश पढ़ सकती हूँ, ज़रूरी बातें बता सकती हूँ, जवाब का ड्राफ्ट और रिमाइंडर बना सकती हूँ। Try “mera message padho”, “summary batao”, “Ravi ko message likho, main aaunga”, or “5 minute baad paani peena yaad dilana”.');
  } catch (error) { showError(error); }
  finally { commandBusy = false; $('runCommand').disabled = false; }
}
async function loadMessages() {
  try {
    const items = await getJson('/api/messages'); const root = $('inboxList'); root.replaceChildren();
    if (!items.length) { root.textContent = 'A little quiet here. Add your first message above.'; return; }
    for (const item of items) {
      const card = node('div', undefined, 'entry');
      card.append(node('strong', item.sender), node('p', item.body));
      const time = node('time', new Date(item.created_at).toLocaleString()); time.dateTime = item.created_at; card.append(time); root.append(card);
    }
  } catch (error) { $('inboxList').textContent = `Could not load messages: ${error.message}`; }
}
async function readMessages(all = false) {
  clearError();
  try {
    const items = await getJson('/api/messages');
    if (!items.length) { viewStatus('Inbox empty'); await feedback('आपका इनबॉक्स खाली है। Your Saathi inbox is empty. Add a message first.'); return; }
    const selected = all ? items : items.slice(0, 1);
    viewStatus(all ? `Showing ${selected.length} most recent messages` : 'Latest message loaded');
    await feedback(selected.map((item, i) => `${all ? `${i + 1}. ` : 'Latest message. '}From ${item.sender}: ${item.body}`).join('\n\n'));
  } catch (error) { showError(error); }
}
async function summarize(all = false) {
  clearError();
  try {
    const result = await getJson(all ? '/api/summary' : '/api/summary/latest');
    const items = all ? result : [result];
    viewStatus(all ? `Extractive key details from ${items.length} most recent messages` : 'Extractive summary of the latest message');
    await feedback(items.map(data => `Key details from ${data.sender}:\n${data.bullets.map(t => `• ${t}`).join('\n')}${data.warnings.length ? '\nSafety note: ' + data.warnings.join(' ') : ''}`).join('\n\n'));
  } catch (error) { showError(error); }
}
async function loadDrafts() {
  try {
    const items = await getJson('/api/drafts'); const root = $('draftList'); root.replaceChildren();
    if (!items.length) { root.textContent = 'Your saved drafts will appear here.'; return; }
    for (const item of items) { const card = node('div', undefined, 'entry'); card.append(node('strong', `For ${item.recipient} · Draft, not sent`), node('p', item.body)); root.append(card); }
  } catch (error) { $('draftList').textContent = `Could not load drafts: ${error.message}`; }
}
function reviewText(action) {
  const data = action.preview;
  if (action.action === 'draft') return `Save a draft for ${data.recipient}?\n\n${data.body}\n\nThis stays in Saathi. It will not be sent.`;
  if (action.action === 'reminder') return `Create this reminder?\n\n${data.note}\n\n${new Date(data.due_at).toLocaleString(undefined, {dateStyle: 'full', timeStyle: 'long'})}\n\nAlerts work while this app is open. Background tabs may delay alerts.`;
  return `Mark this reminder as done?\n\n${data.note}`;
}
async function openReview(action) {
  stopSpeech(); clearError();
  pendingAction = action; returnFocus = document.activeElement;
  $('confirmHeading').textContent = action.action === 'draft' ? 'Review your draft' : action.action === 'reminder' ? 'Review your reminder' : 'Complete reminder?';
  $('confirmPreview').textContent = reviewText(action);
  $('confirmStatus').textContent = 'Nothing has been saved yet.';
  $('confirmDialog').showModal(); $('cancelAction').focus();
  viewStatus('Waiting for your confirmation');
  if ($('autoSpeak').checked) await say(`${reviewText(action)} Say haan to confirm, or nahi to cancel.`);
}
let reviewBusy = false;
async function requestReview(path, body, method = 'POST') {
  if (pendingAction || reviewBusy || confirming) return;
  reviewBusy = true; clearError();
  try { const action = await getJson(path, {...json(body), method}); await openReview(action); }
  catch (error) { showError(error); }
  finally { reviewBusy = false; }
}
async function reviewDraft() {
  if (!$('draftForm').reportValidity()) return;
  await requestReview('/api/drafts', {recipient: $('recipient').value.trim(), body: $('draftBody').value.trim()});
}
async function reviewReminder(iso) {
  if (!$('reminderForm').reportValidity()) return;
  const date = new Date(iso || $('reminderDate').value);
  if (!Number.isFinite(date.getTime()) || date <= new Date()) { showError(new Error('Choose a valid future reminder time.')); return; }
  await requestReview('/api/reminders', {note: $('reminderNote').value.trim(), due_at: date.toISOString()});
}
function closeReview() {
  pendingAction = null; stopSpeech(); $('confirmDialog').close();
  if (returnFocus?.isConnected) returnFocus.focus();
}
function setConfirming(value) {
  confirming = value;
  for (const id of ['confirmAction', 'cancelAction', 'confirmVoice']) $(id).disabled = value;
  $('confirmAction').textContent = value ? 'Saving…' : 'Confirm / हाँ';
  updateRecordControls();
}
async function confirmAction() {
  if (!pendingAction || confirming) return;
  discardRecording(); stopSpeech(); clearError();
  if (Date.parse(pendingAction.expires_at) <= Date.now()) { showError(new Error('This review expired. Cancel and review the action again.')); return; }
  setConfirming(true);
  const action = pendingAction;
  try {
    const result = await getJson('/api/actions/confirm', json({token: action.token}));
    if (result.saved !== true) throw new Error('The server did not confirm that the action was saved. Please check the saved list.');
    closeReview();
    if (action.action === 'draft') { $('draftForm').reset(); await loadDrafts(); }
    else { if (action.action === 'reminder') $('reminderForm').reset(); await loadReminders(); }
    viewStatus(action.action === 'draft' ? 'Draft saved locally' : action.action === 'reminder' ? 'Reminder saved' : 'Reminder completed');
    setConfirming(false);
    await feedback(action.action === 'draft' ? 'ड्राफ्ट सेव हो गया। Your draft is saved in Saathi. Nothing was sent.' : action.action === 'reminder' ? 'रिमाइंडर सेव हो गया। Keep this app open for the reminder alert.' : 'Reminder marked as done.');
  } catch (error) {
    showError(error);
    if (!error.status) {
      $('confirmError').textContent += ' The connection ended before confirmation. Check the saved list before trying again; this token cannot save twice.';
      await Promise.allSettled([loadDrafts(), loadReminders()]);
    }
  } finally { setConfirming(false); }
}
async function cancelAction() {
  if (!pendingAction || confirming) return;
  discardRecording(); stopSpeech();
  const action = pendingAction;
  try { await getJson('/api/actions/cancel', json({token: action.token})); }
  catch (error) {
    closeReview();
    showError(new Error(`Review closed without confirmation. Server cancellation could not be verified: ${error.message}. The unused review expires automatically.`));
    return;
  }
  closeReview(); clearError(); viewStatus('Action cancelled'); await feedback('रद्द कर दिया। The pending action was cancelled.');
}
async function loadReminders() {
  if (remindersLoading) return;
  remindersLoading = true;
  try {
    const items = await getJson('/api/reminders');
    const signature = JSON.stringify(items);
    // Do not destroy focused controls on each poll.
    if (signature !== reminderSignature) {
      reminderSignature = signature;
      const root = $('reminderList'); root.replaceChildren();
      if (!items.length) root.textContent = 'Make room for what matters. Add your first reminder.';
      for (const item of items) {
        const card = node('div', undefined, 'entry'); card.append(node('strong', item.note));
        const time = node('time', `${new Date(item.due_at).toLocaleString()} · ${item.done ? 'Done' : 'Pending'}`); time.dateTime = item.due_at; card.append(time);
        if (!item.done) {
          const button = node('button', 'Mark done'); button.type = 'button'; button.setAttribute('aria-label', `Mark reminder done: ${item.note}`);
          button.addEventListener('click', () => requestReview(`/api/reminders/${item.id}/done`, {}, 'PATCH')); card.append(button);
        }
        root.append(card);
      }
    }
    const due = items.filter(item => !item.done && !notedReminders.has(item.id) && Date.parse(item.due_at) <= Date.now());
    // Keep review/recording uninterrupted; queued reminders are announced next poll.
    if (due.length && !pendingAction && recordState === 'idle' && !commandBusy && !speechAbort) {
      due.forEach(item => notedReminders.add(item.id));
      await feedback(`याद दिलाना है। Reminder${due.length > 1 ? 's' : ''}: ${due.map(item => item.note).join('. ')}`);
    }
  } catch (error) { $('reminderList').textContent = `Could not refresh reminders: ${error.message}`; reminderSignature = ''; }
  finally { remindersLoading = false; }
}
function applyPreferences() {
  const contrast = preferences.get('contrast', 'false') === 'true';
  const large = preferences.get('large', 'false') === 'true';
  document.body.classList.toggle('contrast', contrast); document.documentElement.classList.toggle('large', large);
  $('contrastBtn').setAttribute('aria-pressed', String(contrast)); $('sizeBtn').setAttribute('aria-pressed', String(large));
  $('contrastBtn').textContent = contrast ? 'Standard contrast' : 'High contrast'; $('sizeBtn').textContent = large ? 'Standard text' : 'A+ Text';
  $('autoSpeak').checked = preferences.get('autoSpeak', 'true') === 'true';
  $('voiceLanguage').value = preferences.get('language', 'hi-IN'); $('voiceSpeed').value = preferences.get('speed', '1');
}
$('startTalk').addEventListener('click', toggleRecording);
$('confirmVoice').addEventListener('click', toggleRecording);
$('runCommand').addEventListener('click', () => processCommand($('transcript').value));
$('speakText').addEventListener('click', () => say($('transcript').value));
$('replay').addEventListener('click', () => say(lastReply));
$('stopSpeech').addEventListener('click', stopSpeech); $('dialogStop').addEventListener('click', stopSpeech);
$('readReview').addEventListener('click', () => pendingAction && say(reviewText(pendingAction)));
$('confirmAction').addEventListener('click', confirmAction); $('cancelAction').addEventListener('click', cancelAction);
$('confirmDialog').addEventListener('cancel', event => { event.preventDefault(); cancelAction(); });
$('confirmDialog').addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const controls = Array.from($('confirmDialog').querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'));
  if (!controls.length) return;
  const first = controls[0], last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
$('transcript').addEventListener('keydown', event => { if (event.ctrlKey && event.key === 'Enter') { event.preventDefault(); processCommand($('transcript').value); } });
$('contrastBtn').addEventListener('click', () => { preferences.set('contrast', String(!document.body.classList.contains('contrast'))); applyPreferences(); });
$('sizeBtn').addEventListener('click', () => { preferences.set('large', String(!document.documentElement.classList.contains('large'))); applyPreferences(); });
for (const [id, key] of [['autoSpeak', 'autoSpeak'], ['voiceLanguage', 'language'], ['voiceSpeed', 'speed']]) {
  $(id).addEventListener('change', () => { preferences.set(key, id === 'autoSpeak' ? String($(id).checked) : $(id).value); if (id === 'autoSpeak' && !$(id).checked) stopSpeech(); });
}
for (const button of document.querySelectorAll('[data-command]')) button.addEventListener('click', () => { $('transcript').value = button.dataset.command; processCommand(button.dataset.command); });
$('readLatest').addEventListener('click', () => readMessages()); $('summarize').addEventListener('click', () => summarize());
$('readDraft').addEventListener('click', () => say(`Draft for ${$('recipient').value || 'recipient'}: ${$('draftBody').value}`));
$('draftForm').addEventListener('submit', event => { event.preventDefault(); reviewDraft(); });
$('reminderForm').addEventListener('submit', event => { event.preventDefault(); reviewReminder(); });
$('addMessage').addEventListener('submit', async event => {
  event.preventDefault(); clearError(); const button = event.currentTarget.querySelector('button[type="submit"]'); button.disabled = true;
  try {
    await getJson('/api/messages', json({sender: $('sender').value.trim(), body: $('newMessage').value.trim()}));
    $('addMessage').reset(); await loadMessages(); viewStatus('Message saved locally'); await feedback('Message saved in your Saathi inbox. You can read it or ask for key details.');
  } catch (error) { showError(error); } finally { button.disabled = false; }
});
document.addEventListener('keydown', event => {
  if (event.altKey && event.code === 'KeyM') { event.preventDefault(); toggleRecording(); }
  if (event.key === 'Escape') { stopSpeech(); if (recordState !== 'idle') discardRecording(); }
});
window.addEventListener('pagehide', () => { discardRecording(); stopSpeech(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) loadReminders(); });
async function init() {
  applyPreferences();
  $('timezoneHint').textContent = `Time zone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}.`;
  try {
    const state = await getJson('/api/health'); gnaniReady = state.gnani_configured;
    $('apiStatus').textContent = gnaniReady ? '● Speech key configured · not yet verified' : '● Text mode · speech key needed';
    $('apiStatus').classList.add(gnaniReady ? 'good' : 'bad');
  } catch {
    $('apiStatus').textContent = '● Server unavailable'; $('apiStatus').classList.add('bad');
  }
  await Promise.allSettled([loadMessages(), loadDrafts(), loadReminders()]);
}
setInterval(loadReminders, 10000);
init();
