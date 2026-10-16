import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';

const template = readFileSync(
  new URL('../pabasa_site/pabasa_app/templates/pabasa_app/lesson_4_gawain_1_page.html', import.meta.url),
  'utf8',
);
const marker = '<script type="text/plain" data-lesson4-g1-bootstrap>\n(function(){\n  const retryAudioUrl =';
const start = template.indexOf(marker);
assert.ok(start >= 0, 'retry handler must be present');
const end = template.indexOf('</script>', start);
const source = template.slice(start + '<script type="text/plain" data-lesson4-g1-bootstrap>'.length, end);

function activity({verdicts = [false], failPlay = [], failLoad = []} = {}) {
  const plays = [];
  const errors = [];
  const renders = [];
  const button = {
    disabled: false,
    textContent: 'Basahin',
    classList: {add() {}, remove() {}},
  };
  const status = {textContent: ''};
  const app = {};
  let transcription = 0;
  class AudioClip {
    constructor(url) { this.url = url; }
    play() {
      plays.push(this.url);
      if (failPlay.includes(plays.length)) return Promise.reject(new Error('playback rejected'));
      if (failLoad.includes(plays.length)) {
        queueMicrotask(() => this.onerror?.());
        return Promise.resolve();
      }
      queueMicrotask(() => this.onended?.());
      return Promise.resolve();
    }
    pause() {}
  }
  const context = vm.createContext({
    Audio: AudioClip, Blob, FormData, Promise, setTimeout, clearTimeout,
    console: {error: (...args) => errors.push(args)},
    document: {
      getElementById: id => ({read: button, status, app})[id],
      querySelector: () => button,
    },
    window: {
      Basahin: {
        openMicrophone: async () => ({getTracks: () => [{stop() {}}]}),
        capture: async () => new Blob(['speech'], {type: 'audio/webm'}),
        attachStreamResult() {},
        getActivity: () => null,
        bindActivity() {},
      },
    },
    MutationObserver: class {observe() {}},
    addEventListener() {},
    fetch: async () => ({json: async () => ({success: true, complete: verdicts[transcription++] ?? false})}),
    token: () => 'test',
    items: [{word: 'manok'}], index: 0, phase: 'read', tries: 0, busy: false, introReady: true,
    render() { renders.push({tries: context.tries, phase: context.phase}); },
  });
  vm.runInContext(source, context);
  return {context, button, status, plays, errors, renders, record: context.window.lesson4RetryRecord};
}

test('every incorrect reading narrates, including the third attempt', async () => {
  const page = activity({verdicts: [false, false, false]});
  for (let attempt = 1; attempt <= 3; attempt++) {
    await page.record();
    assert.equal(page.context.tries, attempt);
    assert.equal(page.plays.length, attempt);
    assert.equal(page.status.textContent, `Subukan muli (${attempt}/3)`);
    assert.equal(page.context.busy, false);
  }
  assert.equal(page.context.phase, 'listen');
  assert.deepEqual(page.renders.map(({tries}) => tries), [1, 2, 3]);
});

test('a rejected playback is logged and retried automatically', async () => {
  const page = activity({verdicts: [false], failPlay: [1]});
  await page.record();
  assert.equal(page.context.tries, 1);
  assert.equal(page.plays.length, 2);
  assert.equal(page.errors.length, 1);
  assert.match(page.errors[0][0], /retry feedback narration failed/);
  assert.equal(page.status.textContent, 'Subukan muli (1/3)');
});

test('third incorrect reading also retries a failed narration', async () => {
  const page = activity({verdicts: [false, false, false], failPlay: [3]});
  await page.record();
  await page.record();
  await page.record();
  assert.equal(page.context.tries, 3);
  assert.equal(page.context.phase, 'listen');
  assert.equal(page.plays.length, 4);
  assert.equal(page.errors.length, 1);
});

test('an audio load error is logged and retried without changing the verdict', async () => {
  const page = activity({verdicts: [false], failLoad: [1]});
  await page.record();
  assert.equal(page.context.tries, 1);
  assert.equal(page.plays.length, 2);
  assert.equal(page.errors.length, 1);
  assert.equal(page.context.phase, 'read');
});

test('correct reading keeps its scoring transition without retry narration', async () => {
  const page = activity({verdicts: [true]});
  await page.record();
  assert.equal(page.context.phase, 'classify');
  assert.equal(page.context.tries, 0);
  assert.equal(page.plays.length, 0);
});

test('a correct reading after two failures resets the attempt count', async () => {
  const page = activity({verdicts: [false, false, true]});
  await page.record();
  await page.record();
  await page.record();
  assert.equal(page.context.phase, 'classify');
  assert.equal(page.context.tries, 0);
  assert.equal(page.plays.length, 2);
});

test('page uses the unified handler without a competing counter reset or third-only narrator', () => {
  assert.match(template, /record=window\.lesson4RetryRecord;aloud=/);
  assert.doesNotMatch(template, /try\{tries=0\}catch\(error\)\{\}/);
  assert.doesNotMatch(template, /let played=false;render=function/);
});
