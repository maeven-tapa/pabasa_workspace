// Isolated tests of the rendered activity controller. No microphone or student writes.
const assert = require('node:assert/strict');
const vm = require('node:vm');

function environment(source, options = {}) {
  const calls = [], feedback = [], results = [], paused = [];
  const words = ['lola', 'Koko', 'kala', 'ulo', 'keso', 'kili', 'lata', 'luma', 'kuko'];
  const element = () => ({hidden: false, style: {}, textContent: '', disabled: false,
    classList: {add() {}, remove() {}}, removeAttribute() {}});
  const read = element(), listen = element(), label = element(), status = element(), shownWord = element();
  read.querySelector = listen.querySelector = () => label;
  const start = element(), later = element(), modal = element(), toolbar = element(), debug = element();
  modal.querySelector = () => element();
  const app = {innerHTML: '', querySelector(selector) {
    if (this.innerHTML.includes('lesson-13-completion')) return null;
    return {'#speak': read, '#listen': listen, '.lesson-13-word': shownWord,
      '.lesson-13-status': status}[selector] || null;
  }};
  const progress = options.progress || {current_index: options.index || 0, activity_completed: false};
  const data = {columns: [words.slice(0, 3), words.slice(3, 6), words.slice(6)],
    progress, has_incomplete_progress: Boolean(progress.current_index),
    progress_url: '/test/progress/', completion_url: '/test/complete/'};
  const ids = {'lesson-13-app': app, 'lesson-13-start': modal,
    'lesson13-gawain2-data': {textContent: JSON.stringify(data)},
    'lesson-13-start-button': start, 'lesson-13-later-button': later,
    'prescribed-s5l13g2-debug-panel': debug};
  const classes = new Set();
  const document = {cookie: '', body: {classList: {add: c => classes.add(c)}},
    getElementById: id => ids[id] || null, querySelector: () => toolbar};
  class Audio {
    constructor(src) {this.src = src;}
    play() {feedback.push(this.src); queueMicrotask(() => this.onended?.()); return Promise.resolve();}
    pause() {paused.push(this.src);}
  }
  const window = {Basahin: {openMicrophone: async () => ({getTracks: () => [{stop() {}}]}),
    capture: async () => new Blob(['disposable-test']), cancelAll() {}}};
  const fetch = async (url, request) => {
    calls.push({url, request});
    if (url === data.progress_url) return {ok: true, clone: () => ({json: async () => ({success: options.saveSuccess !== false})})};
    if (url === data.completion_url) {
      if (options.completionGate) await options.completionGate;
      if (options.networkError) throw Error('Network unavailable');
      return {ok: options.httpOk !== false, json: async () => ({success: options.success !== false})};
    }
    const target = request.body.get('target_text');
    const transcript = options.transcript ?? (target === 'kuko' ? 'Cuckoo!' : target);
    const result = {success: options.sttSuccess !== false, complete: false,
      transcript, raw_transcript: transcript};
    results.push(result);
    return {json: async () => result};
  };
  vm.runInNewContext(source, {document, window, fetch, Audio, FormData, Blob, console,
    location: {reload() {}}, queueMicrotask});
  return {calls, feedback, results, paused, ids, classes, app, read, listen, start, status, modal, toolbar, debug, shownWord, window};
}

async function run(source) {
  const matching = source.match(/targetNorm=norm\(word\(\)\),transcriptNorm=norm\(r\.transcript\|\|r\.raw_transcript\),targetAliases=(\{.*?\}),accepted=/)[1];
  const normalize = source.match(/norm=v=>(.*?),save=state=>/)[1];
  const accepted = vm.runInNewContext(`(target, transcript) => {
    const norm=v=>${normalize}, aliases=${matching};
    return aliases[norm(target)]?.includes(norm(transcript)) || norm(target)===norm(transcript);
  }`);
  for (const transcript of ['kuko', 'cuckoo', 'Cuckoo!', '  CUCKOO.  ', '\tKUKO\n'])
    assert.equal(accepted('kuko', transcript), true, transcript);
  for (const transcript of ['unrelated word', 'a cuckoo', 'cuckoo bird', 'cuckoos'])
    assert.equal(accepted('kuko', transcript), false, transcript);
  for (const target of ['lola', 'Koko', 'kala', 'ulo', 'keso', 'kili', 'lata', 'luma'])
    assert.equal(accepted(target, 'cuckoo'), false, target);
  for (const [target, transcript] of [['Koko', 'coco'], ['keso', 'queso'], ['kuko', 'coco']])
    assert.equal(accepted(target, transcript), true);

  const full = environment(source);
  assert.ok(!full.classes.has('g2-complete'));
  await full.start.onclick();
  for (let index = 0; index < 9; index++) {
    await full.read.onclick();
    assert.equal(full.classes.has('g2-complete'), index === 8);
  }
  assert.equal(full.calls.filter(c => c.url === '/test/complete/').length, 1);
  assert.deepEqual(JSON.parse(full.calls.filter(c => c.url === '/test/progress/').at(-1).request.body),
    {state: {current_index: 8, completed_items: 9, phase: 'complete'}});
  assert.equal(full.results.at(-1).transcript, 'Cuckoo!');
  assert.equal(full.results.at(-1).raw_transcript, 'Cuckoo!');
  assert.match(full.app.innerHTML, /Tapos na ang gawain! 🎉/);
  assert.match(full.app.innerHTML, /Mahusay! Nakumpleto mo na ang aktibidad\./);
  assert.equal(full.toolbar.hidden, true);
  assert.equal(full.debug.hidden, true);

  for (const failure of [{success: false}, {httpOk: false}, {networkError: true}]) {
    const env = environment(source, {index: 8, ...failure});
    await env.start.onclick(); await env.read.onclick();
    assert.ok(!env.classes.has('g2-complete'));
    assert.equal(env.read.disabled, false, 'Failed completion must be retryable');
  }
  let release;
  const completionGate = new Promise(resolve => { release = resolve; });
  const pending = environment(source, {index: 8, completionGate});
  await pending.start.onclick(); const reading = pending.read.onclick();
  for (let n = 0; n < 20; n++) await Promise.resolve();
  assert.ok(pending.calls.some(c => c.url === '/test/complete/'));
  assert.ok(!pending.classes.has('g2-complete'), 'Wait for confirmation');
  release(); await reading;
  assert.ok(pending.classes.has('g2-complete'));

  const wrong = environment(source, {index: 8, transcript: 'cuckoo bird'});
  await wrong.start.onclick(); await wrong.read.onclick();
  assert.ok(!wrong.classes.has('g2-complete'));
  assert.equal(wrong.calls.filter(c => c.url === '/test/complete/').length, 0);
  const failedStt = environment(source, {index: 8, sttSuccess: false});
  await failedStt.start.onclick(); await failedStt.read.onclick();
  assert.ok(!failedStt.classes.has('g2-complete'));
  const refreshed = environment(source, {progress: {current_index: 9, completed_items: 9, activity_completed: true}});
  assert.ok(refreshed.classes.has('g2-complete'));
  assert.equal(refreshed.modal.hidden, true);
  assert.equal(refreshed.calls.length, 0);
  console.log('PASS: scoped aliases, full progression, confirmed completion, failures, raw transcript, refresh');
}
module.exports = {run, environment};
