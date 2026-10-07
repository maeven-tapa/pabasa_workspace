const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(__dirname + '/static/pabasa_app/js/prescribed_l22_g2_reading.js', 'utf8');

async function flush(count = 12) {
  for (let index = 0; index < count; index += 1) await Promise.resolve();
}

function load({preview = true, playMode = 'complete', micFailure = false, phase = 'help'} = {}) {
  const audios = [];
  const requests = [];
  const buttons = {read: {disabled: false, textContent: '', onclick: null}};
  const payload = {
    preview,
    activity: {activity_key: 'aral-l22-g2-c-word-reading', items: [{text: 'cactus'}]},
    state: {sequence_index: 0, completed_words: [], reading_phase: phase, revision: 0},
    progress_url: '/progress', read_aloud_url: '/read-aloud', back_url: '/',
    local_audio: {
      startup: '/startup.mp3', instruction: '/instruction.mp3', words: {cactus: '/word.mp3'},
      feedback: {'Pakinggan ang tamang pagbigkas, pagkatapos ay subukan mong basahin.': '/help.mp3'},
      completion: {}
    }
  };
  const modal = {isConnected: true};
  let appHTML = '';
  const app = {
    get innerHTML() { return appHTML; },
    set innerHTML(value) {
      appHTML = value;
      const match = value.match(/<button class="button" id="read"[^>]*>([^<]*)<\/button>/);
      if (match) buttons.read.textContent = match[1];
    }
  };
  const document = {
    cookie: '',
    body: {classList: {add() {}, remove() {}}},
    getElementById(id) {
      if (id === 'workbook-payload') return {textContent: JSON.stringify(payload)};
      if (id === 'l22g2-app') return app;
      if (id === 'read') return buttons.read;
      if (id === 'retry') return {onclick: null};
      if (id === 'restart') return {onclick: null};
      if (id === 'instruction') return null;
      if (id === 'wb-l22-g2-start') return modal;
      if (id === 'wb-l22-g2-start-button') return {disabled: false, addEventListener() {}};
      if (id === 'wb-l22-g2-later-button') return {disabled: false, addEventListener() {}};
      return null;
    }
  };
  class AudioDouble {
    constructor(url) {
      this.url = url;
      this.onended = null;
      this.onerror = null;
      this.paused = false;
      this.playDeferred = {};
      this.playPromise = new Promise((resolve, reject) => {
        this.playDeferred.resolve = resolve;
        this.playDeferred.reject = reject;
      });
      audios.push(this);
    }
    play() {
      if (playMode === 'reject' && this.url === '/word.mp3') return Promise.reject(Error('play rejected'));
      return this.playPromise;
    }
    pause() { this.paused = true; }
    resolvePlay() { this.playDeferred.resolve(); }
    rejectPlay() { this.playDeferred.reject(Error('play rejected')); }
    finish(ok = true) { (ok ? this.onended : this.onerror)?.(); }
  }
  const context = {
    console: {warn() {}}, document, Audio: AudioDouble,
    MutationObserver: class {observe() {}}, setTimeout, clearTimeout,
    navigator: {mediaDevices: {getUserMedia: micFailure ? async () => { throw Error('mic denied'); } : async () => ({getTracks: () => []})}},
    window: {addEventListener() {}, PabasaLessonStart({onStart}) {context.start = onStart; return {}; }},
    fetch: async (_url, options) => {
      const body = options.body && typeof options.body === 'string' ? JSON.parse(options.body) : {};
      requests.push(body.action);
      return {ok: true, json: async () => ({success: true, state: payload.state})};
    }
  };
  vm.runInNewContext(source, context);
  return {audios, buttons, context, payload, requests};
}

test('cancellation settles before play resolves and stale startup cannot affect instruction', async () => {
  const harness = load({preview: false});
  await flush();
  const startup = harness.audios[0];
  harness.context.start();
  await flush();
  const instruction = harness.audios.find(audio => audio.url === '/instruction.mp3');
  assert.ok(instruction);
  assert.equal(startup.onended, null);
  assert.equal(startup.onerror, null);
  startup.resolvePlay();
  await flush();
  assert.equal(typeof instruction.onended, 'function');
  instruction.resolvePlay();
  instruction.finish();
});

for (const [name, action] of [
  ['rejection', audio => audio.rejectPlay()],
  ['media error', audio => { audio.resolvePlay(); audio.finish(false); }],
  ['normal completion', audio => { audio.resolvePlay(); audio.finish(true); }]
]) {
  test(`help word playback ${name} leaves the action recoverable`, async () => {
    const harness = load({playMode: name === 'rejection' ? 'reject' : 'complete'});
    const click = harness.buttons.read.onclick();
    await flush();
    const word = harness.audios.find(audio => audio.url === '/word.mp3');
    assert.ok(word);
    if (name !== 'rejection') action(word);
    await flush(30);
    if (name === 'normal completion') {
      const help = harness.audios.find(audio => audio.url === '/help.mp3');
      assert.ok(help);
      help.resolvePlay();
      help.finish();
    }
    await click;
    assert.equal(harness.requests.includes('read_aloud'), name === 'normal completion');
    assert.equal(harness.buttons.read.disabled, false);
  });
}

test('failed help playback does not acknowledge and Basahin recovers after microphone failure', async () => {
  const harness = load({micFailure: true, phase: 'read'});
  await flush();
  harness.buttons.read.onclick();
  await flush(30);
  assert.equal(harness.requests.includes('read_aloud'), false);
  assert.equal(harness.buttons.read.disabled, false);
  assert.equal(harness.buttons.read.textContent, 'Basahin');
});
