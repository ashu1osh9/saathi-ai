/* Test-only DOM and HTTP fixtures. Never loaded by the production app. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const audio = require('../static/audio.js');

function harness(options = {}) {
  const html = fs.readFileSync('static/index.html', 'utf8');
  const elements = new Map();
  let document;
  class Element {
    constructor(id = '') {
      this.id = id; this.value = ''; this.textContent = ''; this.children = [];
      this.hidden = true; this.checked = true; this.open = false; this.disabled = false;
      this.attributes = {}; this.listeners = {}; this.isConnected = true;
      const classes = new Set();
      this.classList = {contains: c => classes.has(c), add: c => classes.add(c), remove: c => classes.delete(c), toggle: (c, force) => {
        const enabled = force ?? !classes.has(c); enabled ? classes.add(c) : classes.delete(c); return enabled;
      }};
    }
    setAttribute(key, value) { this.attributes[key] = value; }
    removeAttribute(key) { delete this.attributes[key]; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; this.textContent = ''; }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
    focus() { document.activeElement = this; }
    reportValidity() { return options.valid !== false; }
    showModal() { this.open = true; }
    close() { this.open = false; }
    reset() { this.wasReset = true; }
    querySelector() { return new Element(); }
    pause() {}
    play() { queueMicrotask(() => this.onended?.()); return Promise.resolve(); }
  }
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], new Element(match[1]));
  document = {
    getElementById: id => { assert.ok(elements.has(id), `Missing production element ${id}`); return elements.get(id); },
    createElement: () => new Element(), querySelectorAll: () => [], addEventListener() {},
    body: new Element(), documentElement: new Element(), activeElement: new Element(), hidden: false
  };
  elements.get('reply').textContent = 'Welcome';
  const calls = []; const saved = {drafts: [], reminders: []}; let review;
  const response = (data, status = 200) => new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}});
  const fetch = async (path, request = {}) => {
    const body = request.body && typeof request.body === 'string' ? JSON.parse(request.body) : undefined;
    calls.push({path, body, method: request.method});
    if (options.fetch) { const result = await options.fetch(path, request, body); if (result) return result; }
    if (path === '/api/health') return response({gnani_configured: !!options.configured});
    if (path === '/api/messages') return response(options.messages || []);
    if (path === '/api/drafts' && request.method !== 'POST') return response(saved.drafts);
    if (path === '/api/reminders' && request.method !== 'POST') return response(saved.reminders);
    if ((path === '/api/drafts' || path === '/api/reminders') && request.method === 'POST') {
      review = {action: path.endsWith('drafts') ? 'draft' : 'reminder', preview: body, token: 'test-review-token-123456789', expires_at: new Date(Date.now() + 300000).toISOString()};
      return response(review, 202);
    }
    if (path === '/api/actions/confirm') {
      saved[review.action === 'draft' ? 'drafts' : 'reminders'].push({...review.preview, id: 1});
      return response({saved: true, sent: false, action: review.action, id: 1});
    }
    if (path === '/api/actions/cancel') return response({cancelled: true});
    if (path === '/api/command') return response(options.command || {intent: 'unknown'});
    throw new Error(`Unexpected test request: ${path}`);
  };
  const storage = new Map([['saathi.autoSpeak', String(options.autoSpeak ?? false)]]);
  const context = vm.createContext({
    document, window: {addEventListener() {}}, navigator: {}, SaathiAudio: audio, fetch,
    localStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value))},
    console, setInterval() {}, setTimeout, clearTimeout, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}},
    AbortSignal, AbortController, Blob, FormData, Date, Intl, ArrayBuffer, DataView,
  });
  vm.runInContext(fs.readFileSync('static/app.js', 'utf8'), context);
  return {context, calls, saved, elements, run: code => vm.runInContext(code, context), settle: () => new Promise(resolve => setImmediate(resolve))};
}

test('speech chunks preserve a complete long Hindi/Hinglish message', () => {
  const text = 'नमस्ते दोस्त, meeting kal shaam 4 baje hai. '.repeat(110).trim();
  const chunks = audio.splitSpeech(text);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every(chunk => chunk.length <= 850));
  assert.equal(chunks.join(' '), text);
});
test('speech chunks support unbroken Unicode text and empty input', () => {
  assert.deepEqual(audio.splitSpeech('  '), []);
  const text = '🙂'.repeat(1000);
  assert.equal(audio.splitSpeech(text).join(''), text);
});
test('WAV output has real 16 kHz mono PCM headers and clamped samples', async () => {
  const wav = new DataView(await audio.wavEncode(new Float32Array([-2, 0, 2])).arrayBuffer());
  assert.equal(wav.getUint32(24, true), 16000);
  assert.equal(wav.getUint16(22, true), 1);
  assert.equal(wav.getUint16(34, true), 16);
  assert.equal(wav.getInt16(44, true), -32768);
  assert.equal(wav.getInt16(48, true), 32767);
});
test('missing key reports text mode and does not call speech APIs', async () => {
  const h = harness(); await h.settle();
  await h.run("say('नमस्ते')");
  assert.match(h.elements.get('apiStatus').textContent, /Text mode/);
  assert.match(h.elements.get('voiceStatus').textContent, /unavailable/);
  assert.equal(h.calls.some(c => c.path === '/api/tts'), false);
});
test('read flow keeps the entire message and safely renders authored markup', async () => {
  const body = '<img src=x onerror=alert(1)> ' + 'संदेश '.repeat(300);
  const h = harness({messages: [{sender: 'Ravi', body, created_at: '2026-11-08T10:00:00Z'}]}); await h.settle();
  await h.run('readMessages()');
  assert.ok(h.elements.get('reply').textContent.endsWith(body));
  assert.equal(h.elements.get('inboxList').children[0].children[1].textContent, body);
  assert.match(h.elements.get('status').textContent, /loaded/);
});
test('failed read displays an error and never a success status', async () => {
  const h = harness({fetch: async path => path === '/api/messages' ? new Response('{"detail":"Storage unavailable"}', {status: 503}) : null}); await h.settle();
  await h.run('readMessages()');
  assert.equal(h.elements.get('error').hidden, false);
  assert.match(h.elements.get('status').textContent, /Could not complete/);
  assert.equal(h.elements.get('reply').textContent, 'Welcome');
});
test('failed speech preserves both the written result and action status', async () => {
  const h = harness({configured: true, fetch: async path => path === '/api/tts' ? new Response('{"detail":"Gnani timed out"}', {status: 504}) : null}); await h.settle();
  await h.run("reply('Draft saved'); viewStatus('Draft saved locally'); say('Draft saved')");
  assert.equal(h.elements.get('reply').textContent, 'Draft saved');
  assert.equal(h.elements.get('status').textContent, 'Draft saved locally');
  assert.match(h.elements.get('voiceStatus').textContent, /Speech unavailable/);
});
test('draft review is a separate step and defaults focus to cancel', async () => {
  const h = harness(); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Main kal aaunga';
  await h.run('reviewDraft()');
  assert.equal(h.elements.get('confirmDialog').open, true);
  assert.equal(h.run('document.activeElement.id'), 'cancelAction');
  assert.equal(h.saved.drafts.length, 0);
  assert.match(h.elements.get('confirmPreview').textContent, /Main kal aaunga/);
  await h.run('confirmAction()');
  assert.equal(h.saved.drafts.length, 1);
  assert.equal(h.elements.get('confirmDialog').open, false);
  assert.match(h.elements.get('reply').textContent, /Nothing was sent/);
});
test('voice cancel closes review without saving', async () => {
  const h = harness({command: {intent: 'cancel'}}); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()'); await h.run("processCommand('nahi')");
  assert.equal(h.saved.drafts.length, 0);
  assert.equal(h.elements.get('confirmDialog').open, false);
  assert.equal(h.calls.filter(c => c.path === '/api/actions/confirm').length, 0);
});
test('voice confirmation saves only the displayed frozen review', async () => {
  const h = harness({command: {intent: 'confirm'}}); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Original';
  await h.run('reviewDraft()'); h.elements.get('draftBody').value = 'Edited after review';
  await h.run("processCommand('haan')");
  assert.equal(h.saved.drafts[0].body, 'Original');
});
test('failed confirmation stays reviewable and does not announce saving', async () => {
  const h = harness({fetch: async path => path === '/api/actions/confirm' ? new Response('{"detail":"Disk full"}', {status: 503}) : null}); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()'); await h.run('confirmAction()');
  assert.equal(h.saved.drafts.length, 0);
  assert.equal(h.elements.get('confirmDialog').open, true);
  assert.match(h.elements.get('confirmError').textContent, /Disk full/);
  assert.doesNotMatch(h.elements.get('reply').textContent, /saved/);
});
test('parallel confirm clicks create one request', async () => {
  const h = harness(); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()'); await h.run('Promise.all([confirmAction(), confirmAction()])');
  assert.equal(h.calls.filter(c => c.path === '/api/actions/confirm').length, 1);
});
test('reminder voice flow reviews parsed note and exact time before saving', async () => {
  const due = new Date(Date.now() + 600000).toISOString();
  const h = harness({command: {intent: 'reminder', reminder: {note: 'Drink water', due_at: due, clarification: ''}}}); await h.settle();
  await h.run("processCommand('5 minute baad paani peena yaad dilana')");
  assert.equal(h.saved.reminders.length, 0);
  assert.match(h.elements.get('confirmPreview').textContent, /Drink water/);
  await h.run('confirmAction()');
  assert.equal(h.saved.reminders[0].due_at, due);
});
test('ambiguous reminder asks for time without creating a review', async () => {
  const h = harness({command: {intent: 'reminder', reminder: {note: 'Meeting', due_at: null, clarification: 'Choose a time'}}}); await h.settle();
  await h.run("processCommand('kal 4 baje reminder')");
  assert.equal(h.elements.get('reminderDate').value, '');
  assert.equal(h.elements.get('confirmDialog').open, false);
  assert.equal(h.elements.get('reply').textContent, 'Choose a time');
});
test('new draft without a recipient clears a previous recipient', async () => {
  const h = harness({command: {intent: 'draft', draft_text: 'A new reply', recipient: ''}}); await h.settle();
  h.elements.get('recipient').value = 'Previous person';
  await h.run("processCommand('reply likho A new reply')");
  assert.equal(h.elements.get('recipient').value, '');
  assert.equal(h.elements.get('confirmDialog').open, false);
});
test('unchanged reminder polling preserves existing controls and focus', async () => {
  const h = harness(); await h.settle();
  const root = h.elements.get('reminderList'); const sentinel = {};
  root.children.push(sentinel); await h.run('loadReminders()');
  assert.equal(root.children[0], sentinel);
});
test('summary flow displays extracted key details and warnings', async () => {
  const h = harness({fetch: async path => path === '/api/summary/latest' ? new Response(JSON.stringify({sender: 'College', bullets: ['Meeting at 4 PM'], warnings: ['Check the link'], method: 'extractive'})) : null});
  await h.settle(); await h.run('summarize()');
  assert.match(h.elements.get('reply').textContent, /Meeting at 4 PM/);
  assert.match(h.elements.get('reply').textContent, /Check the link/);
  assert.match(h.elements.get('status').textContent, /Extractive/);
});
test('all-message summary command requests all-message endpoint', async () => {
  const h = harness({command: {intent: 'summary', read_all: true}, fetch: async path => path === '/api/summary' ? new Response(JSON.stringify([{sender: 'Ravi', bullets: ['A'], warnings: []}, {sender: 'Meena', bullets: ['B'], warnings: []}])) : null});
  await h.settle(); await h.run("processCommand('sab message ka summary batao')");
  assert.match(h.elements.get('reply').textContent, /Ravi/);
  assert.match(h.elements.get('reply').textContent, /Meena/);
  assert.match(h.elements.get('status').textContent, /2 most recent/);
});
test('microphone denial returns controls to idle and reports the real failure', async () => {
  const h = harness({configured: true}); await h.settle();
  h.run("window.MediaRecorder = function() {}; window.AudioContext = function() {}; navigator.mediaDevices = {getUserMedia: async () => {const e = new Error('denied'); e.name = 'NotAllowedError'; throw e;}};");
  await h.run('toggleRecording()');
  assert.equal(h.run('recordState'), 'idle');
  assert.match(h.elements.get('error').textContent, /permission was denied/);
  assert.equal(h.elements.get('startTalk').disabled, false);
});
test('expired frontend review never attempts a save', async () => {
  const h = harness(); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()');
  h.run("pendingAction.expires_at = '2020-01-01T00:00:00Z'");
  await h.run('confirmAction()');
  assert.equal(h.calls.some(c => c.path === '/api/actions/confirm'), false);
  assert.match(h.elements.get('confirmError').textContent, /expired/);
});
test('closing a review after failed server cancellation does not trap keyboard users', async () => {
  const h = harness({fetch: async path => path === '/api/actions/cancel' ? new Response('{"detail":"Server unavailable"}', {status: 503}) : null}); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()'); await h.run('cancelAction()');
  assert.equal(h.elements.get('confirmDialog').open, false);
  assert.match(h.elements.get('error').textContent, /could not be verified/);
  assert.equal(h.saved.drafts.length, 0);
});
test('confirmation dialog wraps keyboard focus at both boundaries', async () => {
  const h = harness(); await h.settle();
  h.elements.get('recipient').value = 'Ravi'; h.elements.get('draftBody').value = 'Hi';
  await h.run('reviewDraft()');
  const first = h.elements.get('cancelAction'), last = h.elements.get('dialogStop');
  const dialog = h.elements.get('confirmDialog');
  dialog.querySelectorAll = () => [first, h.elements.get('confirmAction'), last];
  let prevented = 0;
  dialog.listeners.keydown[0]({key: 'Tab', shiftKey: true, preventDefault() { prevented++; }});
  assert.equal(h.run('document.activeElement.id'), 'dialogStop');
  dialog.listeners.keydown[0]({key: 'Tab', shiftKey: false, preventDefault() { prevented++; }});
  assert.equal(h.run('document.activeElement.id'), 'cancelAction');
  assert.equal(prevented, 2);
});
