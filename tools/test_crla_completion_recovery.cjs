const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const reader = fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
function section(start, end) {
    const at = reader.indexOf(start);
    assert.ok(at >= 0);
    return reader.slice(at, reader.indexOf(end, at));
}

test('30 students wait for their own completion save before navigating and release capture', async () => {
    const clients = Array.from({length: 30}, () => {
        let finish;
        const events = [];
        const context = vm.createContext({
            clearStoryReadingTimer() {}, isAdminPreview: false, isAssistMode: false,
            completionSavePromise: new Promise(resolve => { finish = resolve; }),
            completionSaveFailed: false, assessmentReturnPromise: null,
            URL, Math, stopSpeechRecognition() {events.push('mic-stopped');},
            stopReadAloud() {}, traceLiveCrlaRedirect() {}, setSpeechStatus() {},
            window: {location: {origin: 'https://testserver', assign(url) {events.push(url);}},
                setTimeout(fn) { fn(); }},
        });
        vm.runInContext(section('async function goBackToAssessments()', 'storyQuestionBackBtn?.addEventListener'), context);
        return {context, finish, events};
    });
    const pending = clients.map(({context}) => context.goBackToAssessments());
    clients.forEach(({events}) => assert.equal(events.length, 0));
    clients.forEach(({finish}) => finish());
    assert.deepEqual(await Promise.all(pending), Array(30).fill(true));
    clients.forEach(({events}) => assert.deepEqual(events, ['mic-stopped', 'https://testserver/dashboard/assessment/']));
});

test('failed save and duplicate clicks cannot navigate away', async () => {
    let resolve, redirects = 0, messages = 0;
    const context = vm.createContext({
        clearStoryReadingTimer() {}, isAdminPreview: false, isAssistMode: false,
        completionSavePromise: new Promise(done => {resolve = done;}),
        completionSaveFailed: true, assessmentReturnPromise: null, URL, Math,
        setSpeechStatus() {messages++;},
        window: {location: {origin: 'https://testserver', assign() {redirects++;}}},
    });
    vm.runInContext(section('async function goBackToAssessments()', 'storyQuestionBackBtn?.addEventListener'), context);
    const first = context.goBackToAssessments(), second = context.goBackToAssessments();
    resolve();
    assert.deepEqual(await Promise.all([first, second]), [false, false]);
    assert.equal(redirects, 0);
    assert.equal(messages, 1);
});

test('final live snapshot retries temporary failures and reports persistent failure honestly', async () => {
    for (const statuses of [[null, null, {status: 'completed'}], [null, null, null]]) {
        let calls = 0, waits = 0;
        const context = vm.createContext({Math, publishLiveSessionState: async () => statuses[calls++],
            window: {setTimeout(fn) {waits++;fn();}}});
        vm.runInContext(section('async function saveLiveCompletion(', 'let liveStatePendingWrites'), context);
        assert.equal(await context.saveLiveCompletion({status: 'completed'}), statuses[2]);
        assert.equal(calls, 3); assert.equal(waits, 2);
    }
});

test('busy navigation retries are bounded and tolerate unavailable storage', () => {
    const source = fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js/service_busy.js'), 'utf8');
    let saved = null, retries = 0;
    const message = {};
    const values = {Math, Date, JSON, document: {getElementById: () => message},
        sessionStorage: {getItem: () => saved, setItem(_, value) {saved = value;}},
        window: {location: {pathname: '/dashboard/assessment/', reload() {retries++;}},
            setTimeout(fn, delay) {assert.ok(delay >= 1000 && delay < 2000);fn();}}};
    for (let i = 0; i < 8; i++) vm.runInNewContext(source, values);
    assert.equal(retries, 5);
    assert.match(message.textContent, /still busy/);
    values.sessionStorage.getItem = () => {throw Error('unavailable');};
    vm.runInNewContext(source, values);
    assert.equal(retries, 5);
});
