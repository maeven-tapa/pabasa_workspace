// Run: node --test tools/test_prescribed_stt.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,
  '../pabasa_site/pabasa_app/static/pabasa_app/js/prescribed_stt_settings.js'), 'utf8');

function environment({saved = null, blockedStorage = false} = {}) {
  const calls = [], panels = [];
  const storage = new Map(saved ? [['pabasa.prescribed.stt-provider', saved]] : []);
  let cancellations = 0;
  function addPanel() {
    const listeners = [];
    const toggle = {dataset: {}, checked: false, addEventListener: (_, listener) => listeners.push(listener)};
    const status = {textContent: ''};
    panels.push({toggle, status, querySelector: selector => selector.includes('toggle') ? toggle : status});
    return {toggle, status, change(value) { toggle.checked = value; listeners.forEach(fn => fn()); }};
  }
  const first = addPanel();
  const window = {
    location: new URL('https://pabasa.test/dashboard/assessment/activity/prescribed/example/'),
    Basahin: {cancelAll() { cancellations++; }},
    fetch: async (input, options) => { calls.push({input, options}); return {ok: true}; },
  };
  const context = vm.createContext({window, URL, Headers, FormData,
    document: {querySelectorAll: selector => selector.includes('toggle') ? panels.map(p => p.toggle) : panels},
    localStorage: {
      getItem(key) { if (blockedStorage) throw Error('blocked'); return storage.get(key); },
      setItem(key, value) { if (blockedStorage) throw Error('blocked'); storage.set(key, value); },
    },
  });
  const load = () => vm.runInContext(source, context);
  load();
  return {window, calls, first, addPanel, load, storage, cancellations: () => cancellations};
}

test('toggle routes recordings to Knowlez, preserves request data, and switches back', async () => {
  const env = environment();
  const body = new FormData(); body.append('audio', new Blob(['audio']));
  const signal = new AbortController().signal;
  const options = {method: 'POST', body, credentials: 'same-origin', signal, headers: {'X-CSRFToken': 'csrf'}};
  await env.window.fetch('/api/reading/transcribe/', options);
  assert.equal(env.calls.at(-1).options.headers.get('X-Pabasa-STT-Provider'), 'google');
  env.first.change(true);
  assert.match(env.first.status.textContent, /Knowlez/);
  assert.equal(env.storage.get('pabasa.prescribed.stt-provider'), 'knowlez');
  for (const url of ['/api/reading/transcribe/', '/api/reading/lesson-1-gawain-1/transcribe/',
    '/api/dashboard/assessment/activity/prescribed/aral-l22-g1-c-syllable-builder/progress/']) {
    await env.window.fetch(url, options);
    const sent = env.calls.at(-1).options;
    assert.equal(sent.headers.get('X-Pabasa-STT-Provider'), 'knowlez');
    assert.equal(sent.headers.get('X-CSRFToken'), 'csrf');
    assert.equal(sent.body, body);
    assert.equal(sent.signal, signal);
    assert.equal(sent.credentials, 'same-origin');
  }
  assert.equal(options.headers['X-Pabasa-STT-Provider'], undefined);
  env.first.change(false);
  await env.window.fetch('/api/reading/transcribe/', options);
  assert.equal(env.calls.at(-1).options.headers.get('X-Pabasa-STT-Provider'), 'google');
  assert.equal(env.cancellations(), 2);
});

test('read-aloud, other activities, external requests, and non-recording saves are untouched', async () => {
  const env = environment({saved: 'knowlez'});
  const options = {method: 'POST', body: new FormData(), headers: {'X-CSRFToken': 'csrf'}};
  for (const url of ['/api/reading/read-aloud/', '/api/template-activities/read-aloud/',
    '/api/dashboard/assessment/activity/word-decoding/transcribe/',
    '/api/dashboard/assessment/activity/prescribed/activity/progress/',
    'https://external.test/api/reading/transcribe/']) {
    await env.window.fetch(url, options);
    assert.equal(env.calls.at(-1).options, options);
  }
  await env.window.fetch('/api/reading/transcribe/');
  assert.equal(env.calls.at(-1).options, undefined);
});

test('saved preferences, repeated includes, and blocked storage work', () => {
  const env = environment({saved: 'knowlez'});
  assert.equal(env.first.toggle.checked, true);
  const second = env.addPanel(); env.load(); env.load();
  assert.equal(second.toggle.checked, true);
  second.change(false);
  assert.equal(env.first.toggle.checked, false);
  assert.equal(env.cancellations(), 1);
  const blocked = environment({blockedStorage: true});
  blocked.first.change(true);
  assert.equal(blocked.first.toggle.checked, true);
  assert.match(blocked.first.status.textContent, /Knowlez/);
});

test('Request objects preserve existing headers and method', async () => {
  const env = environment({saved: 'knowlez'});
  const request = new Request('https://pabasa.test/api/reading/transcribe/',
    {method: 'POST', headers: {'X-CSRFToken': 'csrf'}, body: 'audio'});
  await env.window.fetch(request);
  assert.equal(env.calls[0].input, request);
  assert.equal(env.calls[0].options.headers.get('X-CSRFToken'), 'csrf');
  assert.equal(env.calls[0].options.headers.get('X-Pabasa-STT-Provider'), 'knowlez');
});

test('legacy Azure preference selects the corrected Knowlez API', () => {
  const env = environment({saved: 'azure'});
  assert.equal(env.first.toggle.checked, true);
  assert.match(env.first.status.textContent, /Knowlez/);
});
