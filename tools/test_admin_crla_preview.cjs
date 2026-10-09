// Exercise the actual reader persistence functions with student storage forbidden.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8').replace(/\r\n/g, '\n');
function pick(start, end) {
    const offset = source.indexOf(start);
    assert.ok(offset >= 0, start);
    const endOffset = source.indexOf(end, offset);
    assert.ok(endOffset > offset, end);
    return source.slice(offset, endOffset);
}
const storage = new Map();
const requests = [];
const renderedStates = [];
const destinations = [];
const noop = () => {};
const context = vm.createContext({
    isAdminPreview: true, adminPreviewStateKey: 'test-tab', adminPreviewEndState: {},
    materialId: '1', officialAssessmentId: '1', studentEndStateVersion: 'crla_grade2_v1',
    urlParams: new URLSearchParams('admin_student_id=48'),
    sessionStorage: { getItem: k => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    localStorage: {
        getItem: () => { throw Error('Student storage read'); },
        setItem: () => { throw Error('Student storage write'); },
        removeItem: () => { throw Error('Student storage cleared'); },
    },
    Promise, URL, encodeURIComponent, console, Date,
    storyReadingTimerRecoveryState: () => ({}), getCsrfToken: () => '',
    fetch: async (url, options) => {
        requests.push(url);
        assert.ok(url.startsWith('/api/admin/crla-preview/score/'));
        const state = JSON.parse(options.body);
        return { ok: true, json: async () => ({
            success: true, preview_only: true,
            student_end_assessment_state: { ...state, classification: 'Canonical preview result' },
        }) };
    },
    window: { location: {
        href: 'https://test/dashboard/assessment/reading_ui/word/?official_assessment_id=1&admin_preview=1&admin_student_id=48&admin_preview_token=test-tab',
        assign: url => destinations.push(url),
    } },
    traceOfficialCrlaCompletion: noop, traceEndSession: noop, traceLiveCrlaState: noop,
    stopReadAloud: noop, stopSpeechRecognition: noop, closePauseMenu: noop,
    shell: { classList: { add: noop } }, completionCount: null, completionLevel: null,
    completionSubmitted: false, isReviewMode: false, isRetakeMode: false, isMyMaterials: false,
    latestScores: null, currentAssessmentBranch: 'words', items: ['test'], currentStoryQuestions: [],
    testCode: 'CRLA', mode: 'word', document: { getElementById: () => null, querySelector: () => null },
    calculateScores: () => ({ correct_words: 8 }), correctWordsRead: () => 8,
    normalizeCompletionScores: scores => scores, resolveClassificationLabel: () => '',
    getCrlaSentenceScore: () => 10, getCrlaGrade2Part1Level: () => 'Grade Ready',
    renderLearnerExperienceState: noop, renderScoreSummary: noop,
    renderPersistedEndState: state => renderedStates.push(state),
    renderLiveCompletionWaitingState: noop, setCompletionLoadingState: noop,
    setCompletionActionButtonsProcessing: noop,
});
const chunks = [
    pick('function readStudentEndState()', 'function traceLiveCrlaState('),
    pick('function writeStudentEndState(', 'let studentEndStateWriteQueue'),
    pick('function updateStudentEndState(', '// CRLA Official Assessment: Persist'),
    pick('function persistLockedItemResult(', 'function restoreOfficialCrlaItemResults('),
    pick('function restoreOfficialCrlaItemResults(', 'function persistOfficialCrlaReaderProgress('),
    pick('function clearStudentEndState()', '// A dashboard Start Assessment'),
    pick('async function submitStoryResponse()', 'async function showStoryCompletionScreen('),
    pick('function buildCrlaStageUrl(', 'function syncItemCorrectWordCount('),
    pick('async function showCompletion(', 'function startAssessmentTimer('),
];
vm.runInContext(chunks.join('\n') + '\nlet studentEndStateWriteQueue = Promise.resolve();', context);
(async () => {
    vm.runInContext('clearStudentEndState(); persistLockedItemResult(0); restoreOfficialCrlaItemResults();', context);
    await vm.runInContext('updateStudentEndState({stage:"transition_to_sentence",task1_score:8,correct_words:8})', context);
    assert.equal(requests.length, 0);
    for (const [stage, surface] of [['rhymes', 'word'], ['sentences', 'sentence'], ['story_selection', 'para']]) {
        const url = new URL(vm.runInContext(`buildCrlaStageUrl("${stage}")`, context));
        assert.equal(url.searchParams.get('official_assessment_id'), '1');
        assert.equal(url.searchParams.get('admin_preview'), '1');
        assert.equal(url.searchParams.get('admin_student_id'), '48');
        assert.equal(url.searchParams.get('admin_preview_token'), 'test-tab');
        assert.ok(url.pathname.endsWith(`/${surface}/`));
    }
    await vm.runInContext('updateStudentEndState({stage:"completed",part1_total_score:28})', context);
    assert.equal(requests.length, 1);
    const state = vm.runInContext('readStudentEndState()', context);
    assert.equal(state.task1_score, 8);
    assert.equal(state.classification, 'Canonical preview result');
    assert.equal(await vm.runInContext('submitStoryResponse()', context), null);
    vm.runInContext('clearStudentEndState()', context);
    assert.equal(storage.size, 0);

    // Run the real completion handler through the word/sentence handoff and
    // final story result. Any student storage or persistence request fails.
    await vm.runInContext('showCompletion(true)', context);
    assert.equal(renderedStates.at(-1).stage, 'transition_to_sentence');
    assert.equal(context.completionSubmitted, false);
    context.currentAssessmentBranch = 'sentences';
    context.latestScores = { correct_sentences: 4 };
    await vm.runInContext('showCompletion(true)', context);
    assert.equal(destinations.length, 1);
    assert.equal(new URL(destinations[0]).searchParams.get('admin_preview'), '1');
    context.currentAssessmentBranch = 'story';
    context.latestScores = { story_read_percent: 70, correct_answers: 4, total_story_words: 100, words_read: 70 };
    await vm.runInContext('updateStudentEndState({stage:"completed",story_number:1,learner_experience_rating:5})', context);
    await vm.runInContext('showCompletion(true)', context);
    assert.equal(renderedStates.at(-1).stage, 'completed');
    assert.equal(renderedStates.at(-1).classification, 'Canonical preview result');
    assert.equal(context.completionSubmitted, true);
    assert.ok(requests.every(url => url.startsWith('/api/admin/crla-preview/score/')));
    vm.runInContext('clearStudentEndState()', context);
    console.log('PASS: preview storage and scoring isolated; same CRLA retained across stages; no recording submission; preview state cleared');
})().catch(error => { console.error(error); process.exitCode = 1; });
