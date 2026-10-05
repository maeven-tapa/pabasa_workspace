// Run with node --test tools/test_crla_story_timer.cjs.
// Exercise the actual reader timer and speech lifecycle with a controlled clock.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,
  '../pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
function section(start, end) {
  const from = source.indexOf(start), to = source.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from, `Missing reader section: ${start}`);
  return source.slice(from, to);
}
function reader(overrides = {}) {
  let now = 10000, nextId = 0, completions = 0;
  const timers = new Map(), attributes = {}, scores = [];
  const schedule = (callback, delay, interval = false) => {
    const id = ++nextId;
    timers.set(id, {callback, due: now + delay, interval: interval ? delay : 0});
    return id;
  };
  const context = vm.createContext({
    Date: class extends Date { static now() { return now; } },
    window: {setTimeout: (fn, delay) => schedule(fn, delay), clearTimeout: id => timers.delete(id),
      setInterval: (fn, delay) => schedule(fn, delay, true), clearInterval: id => timers.delete(id)},
    storyReadingTimer: {setAttribute: (key, value) => { attributes[key] = value; }},
    storyReadingTimerProgress: {style: {}}, storyReadingTimeUpOverlay: {classList: {remove() {}}},
    stopReading: async () => { completions++; },
    liveSessionPaused: false, liveSessionEnded: false, liveSessionEndRedirecting: false, isFinalizingReading: false,
    isSendingChunk: false, pendingAudioChunk: null,
    currentIndex: 0, currentSyllableIndex: 0, itemResultVersion: 0, items: ['Si Ana ay masaya.'],
    getCurrentDisplayText: () => 'Si Ana ay masaya.', isAdvancingItem: false,
    isRecording: true, isMuted: false, currentStoryState: 'story_reading', currentAssessmentBranch: 'story',
    mode: 'paragraph', isOfficialAssessmentLaunch: true, isCrla: true, sentenceDebugEnabled: false,
    currentMaterialLanguage: 'Filipino', currentSttLanguageCode: 'fil-PH', syllableStitchingContext: '',
    updateAssessmentNavigationButtons() {}, updateSpeechProcessingControls() {},
    resetSyllableStitching() {}, getCsrfToken: () => 'test', stopSpeechRecognition() {}, setSpeechStatus() {},
    handleSpeechResult: data => scores.push(data),
    FormData, AbortController, console: {warn() {}, log() {}},
    ...overrides,
  });
  vm.runInContext(
    section('let storyReadingTimerId = null;', 'let liveServerTimeOffsetMs') +
    section('function clearStoryReadingTimer()', 'function startStoryReadingCountdown()') +
    section('function currentSpeechContext()', 'function recordParagraphWordResult(') +
    section('async function sendAudioChunk(', 'function handleSpeechResult('), context);
  return {context, attributes, scores, completions: () => completions,
    tick(ms) {
      const end = now + ms;
      for (;;) {
        const next = [...timers].filter(([, timer]) => timer.due <= end)
          .sort((a, b) => a[1].due - b[1].due)[0];
        if (!next) break;
        const [id, timer] = next;
        now = timer.due;
        if (timer.interval) timer.due += timer.interval;
        else timers.delete(id);
        timer.callback();
      }
      now = end;
    },
    visual: () => context.storyReadingTimerProgress.style.strokeDashoffset,
  };
}
async function settle() { for (let turn = 0; turn < 12; turn++) await Promise.resolve(); }
const success = () => ({ok: true, status: 200, text: async () => JSON.stringify({success: true, language_code: 'fil-PH'})});

test('story timer freezes its exact visual and actual deadline throughout processing, then resumes', () => {
  const r = reader(), c = r.context;
  c.startStoryReadingTimer();
  r.tick(1000);
  c.isSendingChunk = true;
  c.syncStoryReadingTimerProcessing();
  const frozen = r.visual();
  r.tick(200000);
  assert.equal(r.visual(), frozen);
  assert.equal(r.attributes['aria-valuenow'], '178');
  assert.equal(r.attributes['data-paused'], 'true');
  assert.equal(r.completions(), 0);
  c.isSendingChunk = false;
  c.syncStoryReadingTimerProcessing();
  assert.equal(r.attributes['data-paused'], 'false');
  r.tick(177999);
  assert.equal(r.completions(), 0);
  r.tick(1);
  assert.equal(r.completions(), 1);
  assert.equal(r.visual(), '1000');
});

test('a real speech request pauses the timer immediately and resumes after its response', async () => {
  let finish;
  const r = reader({fetch: () => new Promise(resolve => { finish = resolve; })}), c = r.context;
  c.startStoryReadingTimer();
  r.tick(2300);
  const pending = c.sendAudioChunk(new Blob(['recorded reading'], {type: 'audio/webm'}));
  const frozen = r.visual(), elapsed = c.storyReadingElapsedMs();
  r.tick(6000);
  assert.equal(r.visual(), frozen);
  assert.equal(c.storyReadingElapsedMs(), elapsed);
  finish(success());
  await pending;
  assert.equal(r.scores.length, 1);
  assert.equal(c.storyReadingElapsedMs(), elapsed);
  r.tick(1000);
  assert.equal(c.storyReadingElapsedMs(), elapsed + 1000);
});

test('the timer stays frozen across a failed request, retry backoff and retried processing', async () => {
  let finish, requests = 0;
  const r = reader({fetch: () => {
    requests++;
    if (requests === 1) return Promise.resolve({ok: false, status: 503,
      text: async () => JSON.stringify({success: false, retryable: true})});
    return new Promise(resolve => { finish = resolve; });
  }}), c = r.context;
  c.startStoryReadingTimer();
  r.tick(4000);
  const pending = c.sendAudioChunk(new Blob(['audio']));
  const frozen = r.visual();
  await settle();
  r.tick(1000);
  await settle();
  assert.equal(requests, 2);
  r.tick(6000);
  assert.equal(r.visual(), frozen);
  assert.equal(c.storyReadingElapsedMs(), 4000);
  finish(success());
  await pending;
  assert.equal(c.storyReadingElapsedMs(), 4000);
  assert.equal(r.attributes['data-paused'], 'false');
});

test('processing begun with one millisecond left prevents time-up until reading resumes', () => {
  const r = reader(), c = r.context;
  c.startStoryReadingTimer();
  r.tick(178999);
  c.isSendingChunk = true;
  c.syncStoryReadingTimerProcessing();
  r.tick(5000);
  assert.equal(r.completions(), 0);
  c.isSendingChunk = false;
  c.syncStoryReadingTimerProcessing();
  r.tick(1);
  assert.equal(r.completions(), 1);
});

test('queued audio and teacher pause do not briefly restart the story clock', () => {
  const r = reader(), c = r.context;
  c.startStoryReadingTimer();
  r.tick(3000);
  c.pendingAudioChunk = {blob: 'next recording'};
  c.syncStoryReadingTimerProcessing();
  r.tick(5000);
  c.pendingAudioChunk = null;
  c.liveSessionPaused = true;
  c.syncStoryReadingTimerProcessing();
  r.tick(5000);
  assert.equal(c.storyReadingElapsedMs(), 3000);
  c.liveSessionPaused = false;
  c.syncStoryReadingTimerProcessing();
  r.tick(1000);
  assert.equal(c.storyReadingElapsedMs(), 4000);
});

test('recovery records active reading time and cleared timers cannot restart after a late response', () => {
  const r = reader(), c = r.context;
  c.startStoryReadingTimer();
  r.tick(8000);
  c.isSendingChunk = true;
  c.syncStoryReadingTimerProcessing();
  r.tick(12000);
  const saved = c.storyReadingTimerRecoveryState();
  assert.equal(saved.story_reading_elapsed_ms, 8000);
  assert.equal(c.Date.now() - c.Date.parse(saved.story_reading_started_at), 8000);
  c.clearStoryReadingTimer();
  c.isSendingChunk = false;
  c.syncStoryReadingTimerProcessing();
  r.tick(200000);
  assert.equal(r.completions(), 0);
  assert.deepEqual(JSON.parse(JSON.stringify(c.storyReadingTimerRecoveryState())), {});
});

test('a failed speech check releases the timer without charging its processing time', async () => {
  let finish;
  const r = reader({fetch: () => new Promise(resolve => { finish = resolve; })}), c = r.context;
  c.startStoryReadingTimer();
  r.tick(1000);
  const pending = c.sendAudioChunk(new Blob(['audio']));
  r.tick(5000);
  finish({ok: false, status: 502, text: async () => JSON.stringify({success: false, retryable: false})});
  await pending;
  assert.equal(r.scores.length, 0);
  assert.equal(c.storyReadingElapsedMs(), 1000);
  assert.equal(r.attributes['data-paused'], 'false');
  r.tick(1000);
  assert.equal(c.storyReadingElapsedMs(), 2000);
});

test('teacher End Session during processing keeps the timer stopped after a late response', async () => {
  let finish;
  const r = reader({fetch: () => new Promise(resolve => { finish = resolve; })}), c = r.context;
  c.startStoryReadingTimer();
  r.tick(3000);
  const pending = c.sendAudioChunk(new Blob(['audio']));
  c.liveSessionEnded = true;
  r.tick(5000);
  finish(success());
  await pending;
  r.tick(200000);
  assert.equal(r.scores.length, 0);
  assert.equal(c.storyReadingElapsedMs(), 3000);
  assert.equal(r.attributes['data-paused'], 'true');
  assert.equal(r.completions(), 0);
});
