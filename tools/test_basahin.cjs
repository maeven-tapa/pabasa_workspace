// Deterministic microphone/lifecycle tests; no Google requests or microphone needed.
// Run: node --test tools/test_basahin.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js/basahin.js'), 'utf8');

const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function environment({level = t => t % 4000 >= 800 && t % 4000 < 1500 ? 0.15 : 0, permission, fetchImpl} = {}) {
  let now = 0, sequence = 0;
  const timers = new Map(), recordings = [], contexts = [], streams = [], states = [];
  const schedule = (fn, delay) => { const id = ++sequence; timers.set(id, {at: now + delay, fn}); return id; };
  const clear = id => timers.delete(id);
  const clock = {
    async tick(ms) {
      const until = now + ms;
      await flush();
      while (true) {
        const next = [...timers.entries()].sort((a, b) => a[1].at - b[1].at)[0];
        if (!next || next[1].at > until) break;
        now = next[1].at; timers.delete(next[0]); next[1].fn(); await flush();
      }
      now = until; await flush();
    },
  };
  class Track extends EventTarget {
    stops = 0;
    stop() { this.stops++; }
  }
  function makeStream() { const track = new Track(); const stream = {getTracks: () => [track]}; streams.push(stream); return stream; }
  class Recorder {
    static isTypeSupported = type => type.startsWith('audio/webm');
    constructor(stream, options) { this.stream = stream; this.mimeType = options?.mimeType || 'audio/webm'; this.state = 'inactive'; recordings.push(this); }
    start() { this.state = 'recording'; this.startedAt = now; }
    stop() {
      if (this.state === 'inactive') return;
      this.state = 'inactive'; this.stoppedAt = now;
      this.ondataavailable?.({data: new Blob(['independent-container'], {type: this.mimeType})});
      this.onstop?.();
    }
  }
  class AudioContext {
    state = 'running';
    closed = 0;
    constructor() { contexts.push(this); }
    createMediaStreamSource() { return {connect() {}, disconnect() {}}; }
    createAnalyser() { return {fftSize: 1024, getByteTimeDomainData(buffer) { buffer.fill(128 + Math.round(level(now) * 128)); }}; }
    async close() { this.closed++; }
    async resume() { this.state = 'running'; }
  }
  const events = new EventTarget();
  const window = {
    MediaRecorder: Recorder, AudioContext,
    setTimeout: schedule, clearTimeout: clear,
    requestAnimationFrame: fn => schedule(fn, 16), cancelAnimationFrame: clear,
    addEventListener: (...args) => events.addEventListener(...args),
    dispatchEvent: event => { states.push(event.detail); return events.dispatchEvent(event); },
  };
  const sandbox = {window, navigator: {mediaDevices: {getUserMedia: permission || (async () => makeStream())}},
    Blob, FormData, AbortController, DOMException, CustomEvent, Event,
    performance: {now: () => now}, document: {cookie: 'csrftoken=test-csrf'},
    fetch: fetchImpl || (() => { throw Error('Unexpected network call'); })};
  vm.runInNewContext(source, sandbox);
  return {api: window.Basahin, clock, recordings, contexts, streams, states, timers, window, makeStream};
}

test('VAD ignores calibration and quiet audio; accepts sustained speech', () => {
  const {api} = environment(), vad = api.createVad();
  assert.equal(vad.sample(0.002, 0).calibrating, true);
  for (let t = 800; t < 1000; t += 16) assert.equal(vad.sample(0.003, t).speaking, false);
  assert.equal(vad.sample(0.15, 1000).speaking, false);
  assert.equal(vad.sample(0.15, 1016).speaking, false);
  assert.equal(vad.sample(0.15, 1032).speaking, true);
  assert.equal(vad.takeSpeech(), true);
  assert.equal(vad.takeSpeech(), false);
});

test('adaptive background threshold rejects steady room noise', () => {
  const vad = environment().api.createVad();
  for (let t = 0; t < 2400; t += 16) vad.sample(0.025, t);
  assert.equal(vad.takeSpeech(), false);
});

test('buffers the first sound and waits for a pause instead of a fixed clip', async () => {
  const e = environment({level: t => t >= 800 && t < 6000 ? 0.15 : 0});
  const promise = e.api.capture(); let resolved = false;
  promise.then(() => { resolved = true; });
  await e.clock.tick(5000);
  assert.equal(e.recordings.length, 1);
  assert.equal(e.recordings[0].startedAt, 0);
  assert.equal(resolved, false);
  await e.clock.tick(2800); const blob = await promise;
  assert.ok(blob.size); assert.equal(blob.type, 'audio/webm;codecs=opus');
  assert.ok(e.recordings[0].stoppedAt >= 7780);
  assert.equal(e.streams[0].getTracks()[0].stops, 1);
  assert.equal(e.contexts[0].closed, 1); assert.equal(e.timers.size, 0);
});

test('waiting audio is buffered but not submitted until speech ends', async () => {
  const e = environment({level: t => t >= 3000 && t < 3500 ? 0.15 : 0});
  let resolved = false;
  const promise = e.api.capture().then(blob => { resolved = true; return blob; });
  await e.clock.tick(2999);
  assert.equal(e.recordings.length, 1); assert.equal(resolved, false);
  await e.clock.tick(3000); const blob = await promise;
  assert.equal(await blob.text(), 'independent-container');
  assert.ok(e.states.some(s => s.state === 'waiting'));
});

test('a pause between syllables does not submit an unfinished word', async () => {
  const e = environment({level: t => (t >= 800 && t < 1600) || (t >= 2600 && t < 4000) ? 0.15 : 0});
  let sent = 0;
  const promise = e.api.read({target_text: 'kabayo'}, {
    transcribe: async () => { sent++; return {success: true, transcript: 'kabayo', complete: true}; },
  });
  await e.clock.tick(5000); assert.equal(sent, 0);
  await e.clock.tick(800); await promise;
  assert.equal(sent, 1);
  assert.ok(e.recordings[0].stoppedAt >= 5780);
});

test('clear speech immediately after clicking is preserved and detected', async () => {
  const e = environment({level: t => t < 600 ? 0.15 : 0});
  const promise = e.api.capture();
  await e.clock.tick(2500); const blob = await promise;
  assert.ok(blob.size);
  assert.equal(e.recordings[0].startedAt, 0);
  assert.ok(e.states.some(state => state.state === 'listening'));
});

test('the recording safety limit never sends truncated speech for grading', async () => {
  const e = environment({level: () => 0.15});
  let sent = 0;
  const promise = e.api.read({target_text: 'long sentence'}, {
    maxRecordingMs: 5000,
    transcribe: async () => { sent++; return {complete: false}; },
  }).catch(error => error);
  await e.clock.tick(5000);
  const error = await promise;
  assert.equal(error.name, 'CaptureLimitError');
  assert.ok(e.api.isCaptureError(error));
  assert.equal(sent, 0); assert.equal(e.timers.size, 0);
  assert.equal(e.streams[0].getTracks()[0].stops, 1);
});

test('silence times out without transcribing or scoring', async () => {
  const e = environment({level: () => 0}); let results = 0, errors = [];
  const reader = e.api.create({getFields: () => ({target_text: 'bata'}), onResult: () => results++, onError: e => errors.push(e)});
  const promise = reader.start(); await e.clock.tick(12000); await promise;
  assert.equal(results, 0); assert.equal(errors[0].name, 'NoSpeechError');
  assert.equal(e.recordings.length, 1); assert.equal(e.streams[0].getTracks()[0].stops, 1);
  reader.destroy();
});

test('abort cancels capture without emitting a clip and preserves caller stream ownership', async () => {
  const e = environment(), stream = e.makeStream(), abort = new AbortController();
  const promise = e.api.capture({stream, keepStream: true, signal: abort.signal}).catch(e => e);
  await e.clock.tick(900); abort.abort(); const error = await promise;
  assert.equal(error.name, 'AbortError'); assert.ok(e.api.isCaptureError(error));
  assert.equal(stream.getTracks()[0].stops, 0); assert.equal(e.timers.size, 0);
  assert.equal(e.contexts[0].closed, 1);
});

test('cancel while permission is pending releases late microphone grant', async () => {
  let grant; const e = environment({permission: () => new Promise(resolve => { grant = resolve; })});
  const promise = e.api.capture().catch(error => error); await flush();
  e.api.cancelAll(); const stream = e.makeStream(); grant(stream);
  assert.equal((await promise).name, 'AbortError');
  assert.equal(stream.getTracks()[0].stops, 1); assert.equal(e.recordings.length, 0);
});

test('continuous controller prevents double start, advances fields and stops on completion', async () => {
  const e = environment(); let cursor = 0, requests = 0;
  const reader = e.api.create({getFields: () => ({current_syllable_index: cursor}),
    transcribe: async (blob, fields) => { requests++; assert.equal(fields.current_syllable_index, cursor); return {complete: requests === 2, current_syllable_index: cursor + 1}; },
    onResult: result => { cursor = result.current_syllable_index; }});
  const promise = reader.start(); await reader.start(); await e.clock.tick(8000); await promise;
  assert.equal(requests, 2); assert.equal(cursor, 2); assert.equal(e.streams.length, 1);
  assert.equal(e.streams[0].getTracks()[0].stops, 1); reader.destroy();
});

test('stop during STT ignores the late response and never restarts recording', async () => {
  const e = environment(); let finish, results = 0;
  const reader = e.api.create({getFields: () => ({}), transcribe: () => new Promise(resolve => { finish = resolve; }), onResult: () => results++});
  const promise = reader.start(); await e.clock.tick(3300); reader.stop(); finish({complete: false}); await promise;
  assert.equal(results, 0); assert.equal(e.recordings.length, 1); assert.equal(e.timers.size, 0); reader.destroy();
});

test('transport includes activity fields, matching extension and CSRF', async () => {
  let request; const e = environment({fetchImpl: async (url, options) => { request = {url, ...options}; return {ok: true, json: async () => ({success: true, complete: true})}; }});
  await e.api.transcribe(new Blob(['clip'], {type: 'audio/ogg'}), {target_text: 'bata', language: 'Filipino', sentence_word_results: [{result: 'pending'}]});
  assert.equal(request.credentials, 'same-origin'); assert.equal(request.headers['X-CSRFToken'], 'test-csrf');
  assert.equal(request.body.get('audio').name, 'reading.ogg'); assert.equal(request.body.get('target_text'), 'bata');
  assert.equal(request.body.get('sentence_word_results'), '[{"result":"pending"}]'); assert.equal(e.timers.size, 0);
});

test('speech evidence cannot leak into the next silent clip', () => {
  const vad = environment().api.createVad();
  vad.sample(0, 0);
  for (let t = 800; t < 2400; t += 16) vad.sample(0.15, t);
  assert.equal(vad.takeSpeech(), true);
  for (let t = 2400; t < 4800; t += 16) vad.sample(0, t);
  assert.equal(vad.takeSpeech(), false);
});

test('one sentence attempt carries cursor/context and joins clip transcripts', async () => {
  const e = environment(); let requests = 0, updates = 0;
  const promise = e.api.read({target_text: 'Uubo si Bibo.', mode: 'sentence'}, {
    transcribe: async (blob, fields) => {
      requests++;
      if (requests === 1) return {success: true, transcript: 'Uubo', current_syllable_index: 2, syllable_context: 'ubo', complete: false};
      assert.equal(fields.current_syllable_index, 2); assert.equal(fields.syllable_context, 'ubo');
      return {success: true, transcript: 'si Bibo', current_syllable_index: 5, complete: true};
    },
    onProgress: () => updates++,
  });
  await e.clock.tick(8000); const result = await promise;
  assert.equal(requests, 2); assert.equal(updates, 2);
  assert.equal(result.transcript, 'Uubo si Bibo'); assert.equal(result.complete, true);
  assert.equal(e.streams[0].getTracks()[0].stops, 1);
});

test('a real mismatch finishes one attempt without recording endlessly', async () => {
  const e = environment();
  const promise = e.api.read({target_text: 'bata'}, {
    transcribe: async () => ({success: true, transcript: 'aso', current_syllable_index: 0, complete: false}),
  });
  await e.clock.tick(3300); const result = await promise;
  assert.equal(result.complete, false); assert.equal(e.recordings.length, 1);
});

test('empty provider transcript does not become a wrong reading result', async () => {
  const e = environment();
  const promise = e.api.read({target_text: 'bata'}, {
    transcribe: async () => ({success: true, transcript: '', complete: false}),
  }).catch(error => error);
  await e.clock.tick(3300);
  assert.equal((await promise).name, 'NoSpeechError');
});

test('cancelling a multi-clip attempt rejects and discards late STT', async () => {
  const e = environment(); let finish;
  const promise = e.api.read({target_text: 'bata'}, {
    transcribe: () => new Promise(resolve => { finish = resolve; }),
  }).catch(error => error);
  await e.clock.tick(3300); e.api.cancelAll(); finish({success: true, transcript: 'bata', complete: true});
  assert.equal((await promise).name, 'AbortError'); assert.equal(e.recordings.length, 1);
});

test('permission failure restores the button and does not submit an attempt', async () => {
  const e = environment({permission: async () => { throw new DOMException('Permission denied', 'NotAllowedError'); }});
  const button = Object.assign(new EventTarget(), {textContent: '', disabled: false, querySelector: () => null, setAttribute() {}});
  let error, results = 0;
  const reader = e.api.create({button, getFields: () => ({}), onResult: () => results++, onError: value => { error = value; }});
  await reader.start();
  assert.equal(error.name, 'NotAllowedError'); assert.ok(e.api.isCaptureError(error));
  assert.equal(results, 0); assert.equal(button.disabled, false); assert.equal(button.textContent, 'Basahin');
  reader.destroy();
});

test('STT timeout is reported and its timer is cleaned up', async () => {
  const e = environment({fetchImpl: (url, {signal}) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  })});
  const promise = e.api.transcribe(new Blob(['clip'], {type: 'audio/webm'}), {}).catch(error => error);
  await e.clock.tick(35000);
  assert.equal((await promise).name, 'TimeoutError'); assert.equal(e.timers.size, 0);
});

test('microphone permission timeout releases a grant that arrives later', async () => {
  let grant;
  const e = environment({permission: () => new Promise(resolve => { grant = resolve; })});
  const promise = e.api.openMicrophone({audio: true}, {timeoutMs: 8000}).catch(error => error);
  await e.clock.tick(8000);
  assert.ok(e.api.isCaptureError(await promise));
  const stream = e.makeStream(); grant(stream); await flush();
  assert.equal(stream.getTracks()[0].stops, 1); assert.equal(e.timers.size, 0);
});

test('stop restores the button immediately while permission remains unanswered', async () => {
  let grant;
  const e = environment({permission: () => new Promise(resolve => { grant = resolve; })});
  const button = Object.assign(new EventTarget(), {textContent: '', disabled: false, querySelector: () => null, setAttribute() {}});
  const reader = e.api.create({button, getFields: () => ({})});
  const promise = reader.start(); await flush(); reader.stop(); await promise;
  assert.equal(button.disabled, false); assert.equal(e.recordings.length, 0);
  const stream = e.makeStream(); grant(stream); await flush();
  assert.equal(stream.getTracks()[0].stops, 1); reader.destroy();
});

test('abort while waiting discards buffered audio and releases the microphone', async () => {
  const e = environment({level: () => 0}), controller = new AbortController();
  const promise = e.api.capture({signal: controller.signal}).catch(error => error);
  await e.clock.tick(2000); controller.abort();
  assert.equal((await promise).name, 'AbortError');
  assert.equal(e.recordings.length, 1); assert.equal(e.timers.size, 0);
  assert.equal(e.streams[0].getTracks()[0].stops, 1);
});

test('each continuous clip waits for fresh speech after an STT response', async () => {
  const e = environment({level: t => (t >= 800 && t < 1500) || (t >= 7000 && t < 7600) ? 0.15 : 0});
  let requests = 0;
  const reader = e.api.create({getFields: () => ({}), transcribe: async () => ({complete: ++requests === 2})});
  const promise = reader.start();
  await e.clock.tick(6900);
  assert.equal(requests, 1); assert.equal(e.recordings.length, 2);
  await e.clock.tick(2700); await promise;
  assert.equal(requests, 2); assert.ok(e.recordings[1].stoppedAt >= 9380);
  reader.destroy();
});

test('steady room noise is discarded without a transcription', async () => {
  const e = environment({level: () => 0.025});
  const promise = e.api.capture().catch(error => error);
  await e.clock.tick(12000);
  assert.equal((await promise).name, 'NoSpeechError'); assert.equal(e.recordings.length, 1);
});

test('English sentence clips retain language, mode and reading cursor', async () => {
  const e = environment(), requests = [];
  const promise = e.api.read({target_text: 'The cat sat.', language: 'English', mode: 'sentence'}, {
    transcribe: async (blob, fields) => {
      requests.push({...fields});
      return {success: true, transcript: requests.length === 1 ? 'The cat' : 'sat',
        current_syllable_index: requests.length === 1 ? 2 : 3, complete: requests.length === 2};
    },
  });
  await e.clock.tick(9000);
  const result = await promise;
  assert.equal(result.complete, true); assert.equal(result.transcript, 'The cat sat');
  assert.equal(requests.length, 2);
  assert.ok(requests.every(fields => fields.language === 'English' && fields.mode === 'sentence'));
  assert.equal(requests[1].current_syllable_index, 2);
});

test('open-ended missing-word recognition ends after one voiced response', async () => {
  const e = environment(); let requests = 0;
  const promise = e.api.read({target_text: 'cat dog', language: 'English', mode: 'reading'}, {
    continuous: false,
    transcribe: async () => { requests++; return {success: true, transcript: 'cat', current_syllable_index: 1, complete: false}; },
  });
  await e.clock.tick(4000);
  assert.equal((await promise).transcript, 'cat'); assert.equal(requests, 1);
});
