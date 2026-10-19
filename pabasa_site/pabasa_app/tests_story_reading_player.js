const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const playerPath = process.argv[2];
const scenario = process.argv[3] || 'auto';
const source = fs.readFileSync(playerPath, 'utf8');
const elements = new Map();
class FakeElement {
  constructor(id = '') {
    this.id = id; this.attributes = {}; this.dataset = {}; this.style = {};
    this.classNames = new Set(); this.classList = {
      add: name => this.classNames.add(name),
      remove: name => this.classNames.delete(name),
      contains: name => this.classNames.has(name),
      toggle: (name, force) => {
        const enabled = force === undefined ? !this.classNames.has(name) : Boolean(force);
        if (enabled) this.classNames.add(name); else this.classNames.delete(name);
        return enabled;
      },
    };
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  replaceChildren(...children) { this.textContent = children.map(String).join(''); }
  addEventListener() {}
  querySelectorAll() { return []; }
  querySelector() { return null; }
  appendChild() {}
  append() {}
  pause() {}
}
const ids = ['story-reading-data','storyPlayerApp','sceneImage','storySubtitle','storyTimeline','timelineFill','currentTime','durationLabel','playButton','playbackButton','previousScene','muteButton','readingStatus','storyProgressText'];
ids.forEach(id => elements.set(id, new FakeElement(id)));
elements.get('story-reading-data').textContent = JSON.stringify({
  language: 'English', title: 'Regression Story', material_id: 1,
  text: 'Ana sits on a mat.\n\nThe curious little rabbit hopped carefully across the wide green garden.\n\nEven when the rain began falling heavily, the children continued reading their favorite story together.',
});
elements.get('storyTimeline').value = '0';
const playButton = elements.get('playButton');
const previousButton = elements.get('previousScene');
const timers = new Map(); let timerId = 0;
const document = {
  getElementById: id => elements.get(id) || null,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => new FakeElement(),
  createTextNode: value => String(value),
  head: new FakeElement('head'),
  addEventListener() {},
  cookie: '',
};
const window = {
  location: {assign() {}},
  addEventListener() {},
  clearInterval() {},
  setInterval() { return ++timerId; },
  clearTimeout(id) { timers.delete(id); },
  setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
  requestAnimationFrame() { return ++timerId; },
  cancelAnimationFrame() {},
  BasahinButton: { setState() {} },
};
const localStorage = {getItem: () => null, setItem() {}, removeItem() {}};
const calls = []; let active = 0; let maxActive = 0; let firstReadPending = false;
window.Basahin = {
  read(fields, options) {
    active += 1; maxActive = Math.max(maxActive, active);
    calls.push({target: fields.target_text, pressed: playButton.getAttribute('aria-pressed'), activeClass: playButton.classList.contains('is-active'), activeSentence: elements.get('storySubtitle').classList.contains('is-reading'), markup: elements.get('storySubtitle').innerHTML});
    const finish = () => { active -= 1; };
    if (firstReadPending) {
      firstReadPending = false;
      return new Promise((resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          finish();
          const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
        }, {once: true});
      });
    }
    finish();
    return Promise.resolve({complete: true});
  },
};
global.document = document; global.window = window; global.localStorage = localStorage;
global.navigator = {mediaDevices: {}};
global.fetch = async () => ({ok: true, json: async () => ({success: true})});
global.requestAnimationFrame = window.requestAnimationFrame;
global.cancelAnimationFrame = window.cancelAnimationFrame;
global.setTimeout = window.setTimeout; global.clearTimeout = window.clearTimeout;
vm.runInThisContext(source, {filename: playerPath});
const waitFor = async predicate => {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  throw new Error('Timed out waiting for Story Reading transition');
};
(async () => {
  if (scenario === 'auto') {
    await playButton.onclick();
    await waitFor(() => calls.length === 3 && playButton.getAttribute('aria-pressed') === 'false');
    assert.deepEqual(calls.map(call => call.target), [
      'Ana sits on a mat.',
      'The curious little rabbit hopped carefully across the wide green garden.',
      'Even when the rain began falling heavily, the children continued reading their favorite story together.',
    ]);
    assert.ok(calls.every(call => call.pressed === 'true' && call.activeClass && call.activeSentence), 'Basahin and the full-sentence underline stay active at every sentence start');
    assert.ok(calls.every(call => /<\/span>\.$/.test(call.markup)), 'Sentence-ending punctuation remains rendered after its final word span');
    assert.equal(elements.get('storySubtitle').classList.contains('is-reading'), false, 'The underline clears when the story reaches its endpoint');
    process.stdout.write('Story Reading automatic advancement regression passed.\n');
  } else {
    firstReadPending = true;
    await playButton.onclick();
    await waitFor(() => calls.length === 1);
    await previousButton.onclick();
    await waitFor(() => calls.length === 3 && playButton.getAttribute('aria-pressed') === 'false');
    assert.deepEqual(calls.map(call => call.target), [
      'Ana sits on a mat.',
      'The curious little rabbit hopped carefully across the wide green garden.',
      'Even when the rain began falling heavily, the children continued reading their favorite story together.',
    ]);
    assert.ok(calls.every(call => call.pressed === 'true' && call.activeClass && call.activeSentence), 'Basahin and the full-sentence underline stay active after Laktawan');
    assert.ok(calls.every(call => /<\/span>\.$/.test(call.markup)), 'Sentence-ending punctuation remains rendered after a skip');
    assert.equal(maxActive, 1, 'A skipped sentence settles before the next recognition segment starts');
    process.stdout.write('Story Reading Laktawan regression passed.\n');
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
