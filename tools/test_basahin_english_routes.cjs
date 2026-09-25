// Node regression check for the actual activity handlers. Requires acorn via
// NODE_PATH or BASAHIN_ACORN_PATH; microphone/STT is replaced with cancellation.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const acorn = require(process.env.BASAHIN_ACORN_PATH || 'acorn');
const root = path.resolve(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js');
const cases = [
  ['prescribed_word_search.js', 'readWord', [], 'reading'],
  ['prescribed_fill_blank_lesson26_activity2.js', 'recordWord', ['cat', 0], 'reading'],
  ['prescribed_fill_blank_lesson26_activity2.js', 'readSentence', [], 'sentence'],
  ['prescribed_rhyming_verses_lesson27_activity1.js', 'recordVerse', ['The cat sat.'], 'sentence'],
  ['prescribed_missing_letter_lesson28_activity1.js', 'record', [{word: 'cat'}], 'reading'],
  ['prescribed_word_identifying_lesson28_activity2.js', 'record', [], 'reading'],
  ['prescribed_oral_sentence_blank_lesson29_activity1.js', 'record', [], 'reading'],
  ['prescribed_match_it_lesson30_activity1.js', 'read', ['cat'], 'reading'],
  ['prescribed_story_time_lesson30_activity2.js', 'record', [], 'sentence'],
  ['prescribed_circle_right_word_lesson31_activity1.js', 'record', [], 'reading'],
  ['prescribed_drag_blank_lesson31_activity2.js', 'record', ['cat', 'read_choice'], 'reading'],
  ['prescribed_drag_blank_lesson31_activity2.js', 'record', ['The cat sat.', 'read_sentence'], 'sentence'],
  ['prescribed_fix_sentence_lesson31_activity3.js', 'record', ['cat', 'read_word'], 'reading'],
  ['prescribed_fix_sentence_lesson31_activity3.js', 'record', ['The cat sat.', 'read_sentence'], 'sentence'],
  ['prescribed_say_circle_lesson31_activity4.js', 'record', ['cat'], 'reading'],
  ['prescribed_trace_say_lesson29_activity3.js', 'record', [], null],
];
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  visit(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => walk(child, visit));
    else if (value && typeof value === 'object') walk(value, visit);
  }
}
(async () => {
  for (const [file, name, args, mode] of cases) {
    const source = fs.readFileSync(path.join(root, file), 'utf8');
    let handler;
    walk(acorn.parse(source, {ecmaVersion: 'latest'}), node => {
      if (node.type === 'FunctionDeclaration' && node.id.name === name) handler = node;
    });
    assert.ok(handler, file);
    const noop = () => {};
    const unexpected = () => { throw Error(`${file}: cancelled attempt reached feedback or scoring`); };
    const button = {classList: {add: noop, remove: noop}, disabled: false, isConnected: true, dataset: {}, textContent: 'Read'};
    const state = {phase: 'reading_choices', current_item: 0, choice_index: 0, current_line: 0, target_word: 'cat'};
    const item = {word: 'cat', choices: ['cat'], sentence: 'The cat sat.'};
    const data = {items: [item], lines: [item.sentence], recognition_hints: 'cat dog', transcribe_url: '/api/reading/transcribe/'};
    let calls = 0;
    const cancel = () => { throw Object.assign(Error('Cancelled'), {name: 'AbortError'}); };
    const context = {
      console, Error, Boolean, String, Number,
      navigator: {mediaDevices: {getUserMedia: unexpected}},
      document: {getElementById: () => button},
      window: {
        MediaRecorder: function () { unexpected(); },
        Basahin: {
          async read(fields, options) {
            calls++;
            assert.equal(fields.language, 'English', file);
            assert.equal(fields.mode, mode, file);
            assert.ok(options.button, file);
            if (file.includes('oral_sentence_blank')) assert.equal(options.continuous, false);
            cancel();
          },
          async capture(options) { calls++; assert.ok(options.button); cancel(); },
        },
        BasahinButton: {setState: noop},
      },
      app: {querySelector: () => button}, a: {querySelector: () => button},
      busy: false, isPaused: false, isActivityPaused: false, prescribedMicMuted: false,
      isMuted: false, muted: false, paused: false, currentIndex: 0,
      generation: 0, speechGeneration: 0, selectedMicDeviceId: '', stream: null,
      words: ['cat'], state, s: state, data, d: data,
      publishDebug: noop, debug: noop, emitDebug: noop, setButtonState: noop,
      setBusyButton: noop, sentenceText: () => item.sentence,
      render: unexpected, save: unexpected, post: unexpected,
    };
    vm.createContext(context);
    vm.runInContext(source.slice(handler.start, handler.end), context);
    await context[name](...args);
    assert.equal(calls, 1, file);
    assert.equal(context.busy, false, file);
  }
  console.log(`PASS: ${cases.length} English reading paths select the correct mode and cancel without scoring.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
