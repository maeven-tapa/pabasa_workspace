// Run with node --test tools/test_crla_live.cjs. Execute the reader's actual
// functions/handlers with deterministic storage and speech lifecycle stubs.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,
  '../pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
function section(start, end) {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from, `Missing reader section: ${start}`);
  return source.slice(from, to);
}
function run(code, values) { const context = vm.createContext(values); vm.runInContext(code, context); return context; }
const copy = value => JSON.parse(JSON.stringify(value));
const storyFunctions = () =>
  section('function normalizeWords(', 'function lcsLength(') +
  section('function syncItemCorrectWordCount(', 'function renderPersistedEndState(') +
  section('function calculateFinalizedStoryMetrics(', 'function punctuationHelperForProgress(') +
  section('function resetStoryMiscueTracking(', 'function storyNormalizedSingleWord(') +
  section('function recordStoryAlignmentMiscues(', 'function storyAlignmentHasInsertionMiscue(');
function storyValues(pages = ['one two three four five'], overrides = {}) {
  return {
    isOfficialAssessmentLaunch: true, isCrla: true, currentStoryState: 'story_reading',
    currentPageIndex: 0, itemPages: [pages], items: [pages.join(' ')],
    pageCorrectWordCounts: [[]], correctWordCounts: [0], paragraphWordResults: {},
    storyMiscueCount: 0, storyWordResults: {}, storyInsertionMiscues: 0,
    storyHasReadingEvidence: false, storyMiscueResponseKeys: new Set(), pendingStorySelfCorrection: null,
    getCurrentDisplayText() { return pages[this.currentPageIndex || 0]; }, ...overrides,
  };
}

test('reconnected reader retains new branch scores, including zero, when storage fails', async () => {
  const initial = {stage: 'rhymes', task1_score: 4};
  const published = [];
  const context = run(
    section('let liveStudentEndState = null;', 'function traceLiveCrlaState') +
    section('let studentEndStateWriteQueue = Promise.resolve();', '// CRLA Official Assessment: Persist'), {
      window: {__PABASA_STUDENT_END_STATE__: initial},
      urlParams: new URLSearchParams('live_recovery=1'), isCurrentLiveAssessment: () => true,
      localStorage: {setItem() { throw Error('Storage unavailable'); }},
      sessionStorage: {}, getStudentEndStateKey: () => 'student-material',
      studentEndStateVersion: 1, officialAssessmentId: 'material-1', materialId: 'material-1',
      writeStudentEndState: async value => { published.push(copy(value)); return value; },
    });
  assert.equal(context.readStudentEndState().task1_score, 4);
  await context.updateStudentEndState({stage: 'transition_to_story', task2_rhymes_score: 8, part1_total_score: 12});
  await context.updateStudentEndState({stage: 'story_comprehension', words_read: 0, comprehension_correct: 0});
  await context.updateStudentEndState({stage: 'completed', learner_experience_rating: 3});
  assert.deepEqual(copy(context.readStudentEndState()), published.at(-1));
  assert.equal(published.at(-1).part1_total_score, 12);
  assert.equal(published.at(-1).words_read, 0);
  assert.equal(published.at(-1).comprehension_correct, 0);
  assert.deepEqual(initial, {stage: 'rhymes', task1_score: 4});
});

function skipEnvironment(overrides = {}) {
  let state = {stage: 'words', task1_score: 3};
  const events = [];
  const context = run(storyFunctions() + section('async function skipCrlaReadingItem()', 'function goToNextPageOrItem'), {
    ...storyValues(),
    currentStoryState: '', currentSelectedStory: null, currentAssessmentUiMode: 'standard',
    currentIndex: 0, currentPageIndex: 0, items: ['one', 'two'], isCrla: true,
    isAdvancingItem: false, nextBtn: {}, autoAdvanceTimer: null, itemResultVersion: 0,
    itemLocked: [false, false], itemScores: [null, null], storyMiscueCount: 2,
    correctWordCounts: [0, 1], sentenceWordResults: [[], []], pendingAudioChunk: 'old audio',
    getCurrentPageCount: () => 1, clearSentenceItemTimer() {}, window: {},
    readStudentEndState: () => state,
    updateStudentEndState: async patch => { state = {...state, ...copy(patch)}; events.push('saved'); return state; },
    transitionToItem(index) { context.currentIndex = index; events.push('advanced'); },
    stopReading: async () => events.push('story-finished'),
    stopSpeechRecognition() { events.push('capture-stopped'); },
    showCompletion: async () => events.push('finished'), ...overrides,
  });
  return {context, events, state: () => state};
}
for (const branch of ['words', 'rhymes', 'sentences']) {
  test(`${branch} skip changes the cursor without scoring or locking an unanswered item`, async () => {
    const {context, events, state} = skipEnvironment({currentAssessmentBranch: branch});
    assert.equal(await context.skipCrlaReadingItem(), true);
    assert.deepEqual(copy(context.itemScores), [null, null]);
    assert.deepEqual(copy(context.itemLocked), [false, false]);
    assert.equal(context.currentIndex, 1);
    assert.equal(state().crla_question_index, 1);
    assert.equal(state().task1_score, 3);
    assert.deepEqual(events, ['saved', 'advanced']);
    assert.equal(context.pendingAudioChunk, null);
  });
}
test('last reading skip completes the branch and preserves earlier captured results', async () => {
  const captured = {correct_words: 1, completed: true};
  const {context, events} = skipEnvironment({currentIndex: 1, itemScores: [captured, null], itemLocked: [true, false]});
  await context.skipCrlaReadingItem();
  assert.deepEqual(copy(context.itemScores), [captured, null]);
  assert.deepEqual(copy(context.itemLocked), [true, false]);
  assert.deepEqual(events, ['capture-stopped', 'finished']);
});
test('last story skip counts every unread word without recording a fake spoken answer', async () => {
  const {context, events, state} = skipEnvironment({currentStoryState: 'story_reading', currentSelectedStory: {title: 'Story'}});
  await context.skipCrlaReadingItem();
  assert.equal(context.storyMiscueCount, 5);
  assert.deepEqual(copy(context.itemScores), [null, null]);
  assert.deepEqual(state().story_skipped_segments, [0]);
  assert.equal(state().miscues, 5);
  assert.equal(state().words_read, 0);
  assert.deepEqual(events, ['saved', 'capture-stopped', 'story-finished']);
});
function comprehensionEnvironment(index) {
  let handler, finished = 0, saved = 0, graded = 0;
  const context = run(section('crlaQuestionNextBtn?.addEventListener("click", async () => {',
    'crlaQuestionReadAloudBtn?.addEventListener'), {
    crlaQuestionNextBtn: {addEventListener(_, callback) { handler = callback; }},
    currentStoryQuestions: [{}, {}, {}], currentStoryQuestionIndex: index,
    currentStoryAnswers: ['spoken answer', '', ''], currentStoryResults: [true, null, null],
    crlaSpeechAttemptActive: true, crlaSpeechRecognition: {abort() {}},
    renderCRLAQuestion() {}, persistCRLAComprehensionState: async () => saved++,
    finishCRLAComprehension: async () => finished++, completeCRLASpokenAttempt: async () => graded++,
  });
  return {context, click: () => handler(), totals: () => ({finished, saved, graded})};
}
test('comprehension skip advances and leaves the unanswered result null', async () => {
  const {context, click, totals} = comprehensionEnvironment(1);
  await click();
  assert.equal(context.currentStoryQuestionIndex, 2);
  assert.deepEqual(copy(context.currentStoryResults), [true, null, null]);
  assert.deepEqual(totals(), {finished: 0, saved: 1, graded: 0});
  assert.equal(context.crlaSpeechAttemptActive, false);
});
test('last comprehension skip finishes without grading an empty answer', async () => {
  const {context, click, totals} = comprehensionEnvironment(2);
  await click();
  assert.deepEqual(copy(context.currentStoryResults), [true, null, null]);
  assert.deepEqual(totals(), {finished: 1, saved: 0, graded: 0});
});

test('callbacks from skipped speech cannot grade or cancel a subsequent attempt', async () => {
  let handler;
  const graded = [];
  class Recognition { start() {} stop() {} abort() { this.onend(); } }
  const button = () => ({classList: {add() {}}});
  const context = run(
    section('function startCRLASpokenAttempt()', 'function renderCRLAComprehensionState(') +
    section('crlaQuestionNextBtn?.addEventListener("click", async () => {', 'crlaQuestionReadAloudBtn?.addEventListener'), {
      window: {SpeechRecognition: Recognition}, currentMaterialLanguage: 'English',
      crlaQuestionNextBtn: {addEventListener(_, callback) { handler = callback; }},
      currentStoryQuestions: [{}, {}], currentStoryQuestionIndex: 0,
      currentStoryAnswers: ['', ''], currentStoryResults: [null, null],
      crlaSpeechAttemptActive: false, crlaSpeechRecognition: null, crlaAnswerFeedback: null,
      crlaQuestionStartReadingBtn: button(), crlaQuestionBackBtn: button(),
      renderCRLAQuestion() {}, persistCRLAComprehensionState: async () => {},
      finishCRLAComprehension: async () => {},
      completeCRLASpokenAttempt: (answer, index) => graded.push({answer, index}),
    });
  context.startCRLASpokenAttempt();
  const oldRecognition = context.crlaSpeechRecognition;
  await handler();
  context.startCRLASpokenAttempt();
  const newRecognition = context.crlaSpeechRecognition;
  const result = {results: [[{transcript: 'spoken answer'}]]};
  oldRecognition.onresult(result);
  oldRecognition.onerror();
  oldRecognition.onend();
  assert.deepEqual(graded, []);
  assert.equal(context.crlaSpeechRecognition, newRecognition);
  assert.equal(context.crlaSpeechAttemptActive, true);
  newRecognition.onresult(result);
  assert.deepEqual(graded, [{answer: 'spoken answer', index: 1}]);
  assert.equal(context.currentStoryResults[0], null);
});

test('double-clicking a partial story skip counts only unread words once and keeps captured credit', async () => {
  let handler, releaseSave;
  const saved = [];
  const context = run(
    storyFunctions() + section('function persistSkippedStorySegment()', 'function goToNextPageOrItem()') +
    section('nextBtn?.addEventListener("click", async () => {', 'function isInteractiveElement('), {
      ...storyValues(['one two three four five', 'six seven', 'eight nine ten'], {pageCorrectWordCounts: [[3]]}),
      nextBtn: {addEventListener(_, callback) { handler = callback; }},
      isSentenceBot: false, isAdvancingItem: false, currentStoryState: 'story_reading',
      currentSelectedStory: {title: 'Story'}, currentPageIndex: 0, currentStorySegmentIndex: 0,
      getCurrentPageCount: () => 3, itemResultVersion: 0, pendingAudioChunk: 'old',
      storyMiscueCount: 2, itemScores: [{correct_words: 3}],
      readStudentEndState: () => ({words_read: 3, miscues: 2}),
      updateStudentEndState: patch => {
        saved.push(copy(patch));
        return saved.length === 1 ? new Promise(resolve => { releaseSave = resolve; }) : Promise.resolve();
      },
      resetStorySegmentState() {}, updateUI() { context.isAdvancingItem = false; },
      renderStoryReadingState() {}, logStorySegmentInitialization() {}, animateCurrentItem() {},
    });
  const firstClick = handler();
  await handler();
  assert.equal(saved.length, 1);
  releaseSave();
  await firstClick;
  assert.equal(context.currentPageIndex, 1);
  assert.equal(context.storyMiscueCount, 2);
  assert.deepEqual(copy(context.itemScores), [{correct_words: 3}]);
  assert.equal(saved[0].miscues, 2);
  assert.equal(saved[0].words_read, 3);
  assert.deepEqual(saved[0].story_word_results[0], {0: 'correct', 1: 'correct', 2: 'correct', 3: 'omission', 4: 'omission'});
  assert.deepEqual(saved[1], {stage: 'story_reading', story_segment_index: 1});
});

test('a fresh live attempt cannot reuse cached recovery scores', () => {
  const context = run(
    section('let liveStudentEndState = null;', 'function traceLiveCrlaState') +
    section('function clearStudentEndState()', '// A dashboard Start Assessment launch'), {
      window: {__PABASA_STUDENT_END_STATE__: {stage: 'completed', task1_score: 8}},
      isCurrentLiveAssessment: () => true, urlParams: new URLSearchParams('live_recovery=1'),
      localStorage: {removeItem() {}}, sessionStorage: {setItem() {}},
      studentEndStateResetKey: 'reset', getStudentEndStateKey: () => 'state',
    });
  assert.equal(context.readStudentEndState().task1_score, 8);
  context.clearStudentEndState();
  assert.deepEqual(copy(context.readStudentEndState()), {});
});

test('story metrics count all unread words as miscues, including an entirely skipped story', () => {
  const context = run(section('function calculateFinalizedStoryMetrics(', 'function correctWordsRead()'), {
    storyHasReadingEvidence: true, isOfficialAssessmentLaunch: true, isCrla: true,
    correctWordsRead: () => 3, storyInsertionMiscues: 0,
  });
  const metrics = context.calculateFinalizedStoryMetrics(10, 1, 60);
  assert.equal(metrics.wordsRead, 3);
  assert.equal(metrics.miscues, 7);
  assert.equal(metrics.accuracy, 30);
  context.storyHasReadingEvidence = false;
  context.correctWordsRead = () => 0;
  const skipped = context.calculateFinalizedStoryMetrics(10, 0, 60);
  assert.equal(skipped.wordsRead, 0);
  assert.equal(skipped.miscues, 10);
});

test('strict Part 2 counts substitutions immediately, keeps them after correction, and ignores duplicate callbacks', () => {
  const context = run(storyFunctions(), storyValues(['the cat sat']));
  const data = {transcript: 'the dog sat', word_alignment: {miscues: 1}, word_results: [
    {expected_index: 0, result: 'correct', type: 'correct'},
    {expected_index: 1, result: 'miscue', type: 'substitution'},
    {expected_index: 2, result: 'correct', type: 'correct'},
  ]};
  context.recordStoryAlignmentMiscues(data, {syllableIndex: 0});
  assert.equal(context.storyMiscueCount, 1);
  assert.equal(context.pendingStorySelfCorrection, null);
  assert.equal(context.correctWordsRead(), 2);
  context.recordStoryAlignmentMiscues(data, {syllableIndex: 0});
  assert.equal(context.storyMiscueCount, 1);
  context.recordStoryAlignmentMiscues({transcript: 'cat', word_alignment: {miscues: 0},
    word_results: [{expected_index: 1, result: 'correct', type: 'correct'}]}, {syllableIndex: 3});
  assert.equal(context.storyMiscueCount, 1);
  assert.equal(context.correctWordsRead(), 2);
});

test('strict Story metrics combine substitutions, internal omissions, skipped segments and extra words exactly once', () => {
  const pages = ['the cat sat', 'on the mat'];
  const context = run(storyFunctions(), storyValues(pages));
  context.recordStoryAlignmentMiscues({transcript: 'dog sat extra', word_alignment: {miscues: 3}, word_results: [
    {expected_index: 0, result: 'miscue', type: 'omission'},
    {expected_index: 1, result: 'miscue', type: 'substitution'},
    {expected_index: 2, result: 'correct', type: 'correct'},
    {expected_index: null, result: 'miscue', type: 'insertion'},
  ]}, {syllableIndex: 0});
  assert.equal(context.storyMiscueCount, 3);
  context.finalizeStorySegment(0);
  context.finalizeStorySegment(1);
  context.finalizeStorySegment(1);
  assert.equal(context.storyMiscueCount, 6);
  const result = context.calculateFinalizedStoryMetrics(6, context.storyMiscueCount, 60);
  assert.equal(result.miscues, 6);
  assert.equal(result.wordsRead, 1);
  assert.equal(result.wpm, 1);
});

test('ending reading early counts unvisited text and recovery keeps per-word errors without counting them twice', () => {
  const context = run(storyFunctions(), storyValues(['one two three', 'four five six']));
  context.recordStoryAlignmentMiscues({transcript: 'one wrong', word_alignment: {miscues: 1}, word_results: [
    {expected_index: 0, result: 'correct', type: 'correct'},
    {expected_index: 1, result: 'miscue', type: 'substitution'},
  ]}, {syllableIndex: 0});
  const saved = copy(context.strictStoryEvidence());
  const restored = run(storyFunctions(), storyValues(['one two three', 'four five six']));
  restored.resetStoryMiscueTracking(saved.miscues, saved);
  restored.finalizeStoryReading();
  restored.finalizeStoryReading();
  assert.equal(restored.storyMiscueCount, 5);
  assert.equal(restored.correctWordsRead(), 1);
  assert.deepEqual(copy(restored.storyWordResults[0]), {0: 'correct', 1: 'substitution', 2: 'omission'});
  assert.deepEqual(copy(restored.storyWordResults[1]), {0: 'omission', 1: 'omission', 2: 'omission'});
});
test('Sentence score payload uses its own score, including zero, instead of automatic Rhymes credit', () => {
  let state;
  const context = run(section('function buildCrlaScoreData(', 'function setCompletionActionButtonsProcessing'), {
    readStudentEndState: () => state, currentAssessmentBranch: 'story', currentSelectedStory: null,
  });
  for (const score of [0, 2, 5, 7, 10]) {
    state = {task1_score: 8, task2_type: 'Task 2H / Sentences', task2_rhymes_score: 10, task2_sentences_score: score};
    assert.equal(context.buildCrlaScoreData({}).task2_score, score);
  }
});

test('recovery item scores cannot lock a different branch or override the server with stale local scores', () => {
  let recovered = {stage: 'transition_to_sentence', branch: 'sentences', live_item_branch: 'words',
    live_item_scores: [{correct_words: 1}]};
  const context = run(section('function restoreOfficialCrlaItemResults()', 'function persistOfficialCrlaReaderProgress()'), {
    isOfficialAssessmentLaunch: true, isCrla: true, isCurrentLiveAssessment: () => true,
    urlParams: new URLSearchParams('live_recovery=1'),
    localStorage: {getItem: () => JSON.stringify({'sentences:0': {correct_words: 99}})},
    officialCrlaItemResultsStorageKey: 'results', readStudentEndState: () => recovered,
    items: ['a sentence'], currentAssessmentBranch: 'sentences',
    getOfficialCrlaItemResultKey: (branch, index) => `${branch}:${index}`,
    itemLocked: [false], itemScores: [null], correctWordCounts: [0], pageCorrectWordCounts: [[]], sentenceWordResults: [[]],
    console,
  });
  context.restoreOfficialCrlaItemResults();
  assert.deepEqual(copy(context.itemLocked), [false]);
  assert.deepEqual(copy(context.itemScores), [null]);
  recovered = {stage: 'sentences', live_item_branch: 'sentences', live_item_scores: [{correct_words: 0, completed: true}]};
  context.restoreOfficialCrlaItemResults();
  assert.equal(context.correctWordCounts[0], 0);
  assert.equal(context.itemLocked[0], true);
});

test('skipped reading items are excluded from attempted and incorrect counts', () => {
  const context = run(section('function calculateScores()', 'function calculateFinalizedStoryMetrics('), {
    items: ['read', 'wrong', 'skipped'], correctWordCounts: [1, 0, 0],
    itemScores: [{correct_words: 1, completed: true}, {correct_words: 0, completed: true}, null],
    itemLocked: [true, true, false], spokenTranscript: 'read different',
    isOfficialAssessmentLaunch: true, isCrla: true, mode: 'word', currentStoryState: '',
    normalizeWords: text => text.split(/\s+/), readableWordCount: text => text.split(/\s+/).length,
    getAssessmentElapsedSeconds: () => 60, correctWordsRead: () => 1,
  });
  const result = context.calculateScores();
  assert.equal(result.items_completed, 2);
  assert.equal(result.incorrect_words, 1);
  assert.equal(result.correct_words, 1);
  assert.equal(result.raw_metrics.items_completed, 2);
  assert.equal(result.raw_metrics.incorrect_words, 1);
});

for (const failure of ['401', 'AbortError', 'invalid response']) {
  test(`a late ${failure} speech failure after teacher End Session cannot show timeout UI or redirect to login`, async () => {
    let settle;
    const statuses = [], redirects = [];
    const context = run(
      section('function currentSpeechContext()', 'function recordParagraphWordResult(') +
      section('async function sendAudioChunk(', 'function handleSpeechResult('), {
        currentIndex: 0, currentSyllableIndex: 0, itemResultVersion: 0, items: ['Pito'],
        getCurrentDisplayText: () => 'Pito', isAdvancingItem: false,
        liveSessionEnded: false, liveSessionEndRedirecting: false,
        isRecording: true, isMuted: false, isSendingChunk: false, pendingAudioChunk: null,
        currentStoryState: 'words', currentAssessmentBranch: 'words', mode: 'word',
        isOfficialAssessmentLaunch: true, isCrla: true, sentenceDebugEnabled: false,
        currentMaterialLanguage: 'English', currentSttLanguageCode: 'en-US', syllableStitchingContext: '',
        updateAssessmentNavigationButtons() {}, updateSpeechProcessingControls() {},
        resetSyllableStitching() {}, getCsrfToken: () => 'test', stopSpeechRecognition() {},
        setSpeechStatus: (...args) => statuses.push(args),
        FormData, AbortController, console: {warn() {}, log() {}},
        fetch: () => new Promise((resolve, reject) => { settle = {resolve, reject}; }),
        window: {setTimeout(callback, delay) { if (delay === 900) callback(); }, clearTimeout() {},
          location: {pathname: '/reader/', search: '', assign: url => redirects.push(url)}},
      });
    const pending = context.sendAudioChunk(new Blob(['audio'], {type: 'audio/webm'}));
    context.liveSessionEnded = true;
    context.liveSessionEndRedirecting = true;
    context.itemResultVersion++;
    if (failure === 'AbortError') settle.reject(Object.assign(new Error('aborted'), {name: 'AbortError'}));
    else settle.resolve({ok: false, status: failure === '401' ? 401 : 500,
      text: async () => failure === '401' ? JSON.stringify({success: false, error: 'Authentication required'}) : '<html>Server error</html>'});
    await pending;
    assert.deepEqual(statuses, []);
    assert.deepEqual(redirects, []);
    assert.equal(context.pendingAudioChunk, null);
  });
}
