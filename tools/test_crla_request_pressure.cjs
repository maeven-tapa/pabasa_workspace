// Deterministic checks of the actual reader code; no network or student data.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,
    '../pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function section(start, end) {
    const from = source.indexOf(start), to = source.indexOf(end, from + start.length);
    assert.ok(from >= 0 && to > from, start);
    return source.slice(from, to);
}
function fixture(extra = {}) {
    let now = 10000, next = 0;
    const timers = new Map();
    const schedule = (callback, delay) => {
        const id = ++next;
        timers.set(id, {callback, delay});
        return id;
    };
    const c = vm.createContext({
        window: {setTimeout: schedule, clearTimeout: id => timers.delete(id),
            setInterval: schedule, clearInterval: id => timers.delete(id)},
        Date: class extends Date { static now() { return now; } },
        console: {debug() {}, warn() {}}, AbortController,
        traceEndSession() {}, liveSessionId: 'synthetic', liveSessionStateUrl: '/state',
        liveSessionPollTimer: null, liveSessionHeartbeatTimer: null,
        liveSessionLastHeartbeatAt: 0, ...extra,
    });
    return {c, timers, advance: ms => { now += ms; }};
}

test('20 simultaneous state consumers share one request and release it for the next poll', async () => {
    let requests = 0, resolve;
    const f = fixture({fetch: () => { requests++; return new Promise(r => { resolve = r; }); }});
    vm.runInContext(section('        let liveStateFetchPromise', '        async function publishLiveSessionStateNow'), f.c);
    const pending = Array.from({length: 20}, () => f.c.fetchLiveSessionState());
    assert.equal(requests, 1);
    resolve({ok: true, status: 200, json: async () => ({success: true, session: {status: 'started'}})});
    assert.ok((await Promise.all(pending)).every(s => s.status === 'started'));
    const next = f.c.fetchLiveSessionState();
    assert.equal(requests, 2);
    resolve({ok: false, status: 503});
    assert.equal(await next, null);
    assert.equal(f.timers.size, 0, 'request deadline is cleared on either outcome');
});

test('polling waits for completion, backs off on failures, and resets after recovery', async () => {
    let calls = 0, resolve;
    const f = fixture({fetchLiveSessionState: () => {
        calls++; return new Promise(r => { resolve = r; });
    }, handleLiveSessionState: async () => {}});
    vm.runInContext(section('        let liveSessionPolling', '        async function startLiveCountdown'), f.c);
    f.c.startLiveSessionPolling();
    assert.equal(calls, 1);
    assert.equal(f.timers.size, 0, 'no polling timer while the request is pending');
    for (const delay of [4000, 8000, 15000, 15000, 2000]) {
        resolve(delay === 2000 ? {status: 'started'} : null);
        await tick();
        const timer = [...f.timers.values()].at(-1);
        assert.equal(timer.delay, delay);
        f.timers.clear(); timer.callback();
    }
    f.c.stopLiveSessionPolling();
    resolve(null); await tick();
    assert.equal(f.timers.size, 0);
});

test('stopped polling ignores a late response and cannot resurrect a timer', async () => {
    let resolve, handled = 0;
    const f = fixture({fetchLiveSessionState: () => new Promise(r => { resolve = r; }),
        handleLiveSessionState: async () => { handled++; }});
    vm.runInContext(section('        let liveSessionPolling', '        async function startLiveCountdown'), f.c);
    f.c.startLiveSessionPolling();
    f.c.stopLiveSessionPolling();
    resolve({status: 'started'}); await tick();
    assert.equal(handled, 0); assert.equal(f.timers.size, 0);
});

test('slow heartbeats do not queue duplicates or drop explicit terminal/recovery writes', async () => {
    const calls = [], releases = [];
    const f = fixture({
        publishLiveSessionStateNow: values => {
            calls.push(values); return new Promise(r => releases.push(r));
        },
        isCurrentLiveAssessment: () => true, isRecording: true,
        liveSessionPaused: false, liveSessionEnded: false,
        getAssessmentElapsedSeconds: () => 5, correctWordsRead: () => 0,
        currentIndex: 0, items: ['bata'],
    });
    vm.runInContext(section('        // Keep live recovery writes ordered.', '        function disableReaderInteractions'), f.c);
    f.c.startLiveSessionHeartbeat();
    const heartbeat = [...f.timers.values()][0].callback;
    f.advance(2000); heartbeat(); await tick();
    for (let i = 0; i < 20; i++) { f.advance(2000); heartbeat(); }
    assert.equal(calls.length, 1);
    const terminal = f.c.publishLiveSessionState({status: 'completed', recovery_state: {stage: 'completed'}});
    releases.shift()({status: 'started'}); await tick();
    assert.equal(calls.length, 2); assert.equal(calls[1].status, 'completed');
    assert.equal(calls[1].recovery_state.stage, 'completed');
    releases.shift()({status: 'ended'}); await terminal;
    f.c.stopLiveSessionHeartbeat();
});

test('failed heartbeat backs off while explicit recovery writes can still proceed', async () => {
    let calls = 0;
    const f = fixture({publishLiveSessionStateNow: async () => { calls++; return null; },
        isCurrentLiveAssessment: () => true, isRecording: true,
        liveSessionPaused: false, liveSessionEnded: false,
        getAssessmentElapsedSeconds: () => 5, correctWordsRead: () => 0,
        currentIndex: 0, items: ['bata']});
    vm.runInContext(section('        // Keep live recovery writes ordered.', '        function disableReaderInteractions'), f.c);
    f.c.startLiveSessionHeartbeat();
    const heartbeat = [...f.timers.values()][0].callback;
    f.advance(2000); heartbeat(); await tick();
    f.advance(2000); heartbeat(); await tick();
    assert.equal(calls, 1);
    await f.c.publishLiveSessionState({recovery_state: {stage: 'transition_to_sentence'}});
    assert.equal(calls, 2);
    f.c.stopLiveSessionHeartbeat();
});

test('late recorder events cannot mix clips or detach a new recorder after navigation', async () => {
    const recorders = [], uploads = [];
    class Recorder {
        constructor() { this.mimeType = 'audio/webm'; recorders.push(this); }
        start() { this.state = 'recording'; }
    }
    const f = fixture({MediaRecorder: Recorder, Blob, mediaStream: {}, mediaRecorder: null,
        stoppingSpeechRecognition: false, isMuted: false, isRecording: true,
        isAdvancingItem: false, sentenceCountdownTimer: null, isOfficialAssessmentLaunch: false,
        mode: 'word', currentIndex: 0, version: 0, canStreamCrla: () => false,
        pickAudioMimeType: () => 'audio/webm', shouldSendAudioChunk: () => true,
        hasHeardSinceLastChunk: true, speechChunkStartedAt: 0,
        setSpeechStatus() {},
    });
    f.c.currentSpeechContext = () => ({version: f.c.version});
    f.c.isCurrentSpeechContext = ctx => ctx.version === f.c.version;
    f.c.sendAudioChunk = async blob => { uploads.push(await blob.text()); f.c.stoppingSpeechRecognition = true; };
    vm.runInContext(section('        function startSpeechChunkRecorder', '        function finishCurrentAudioChunk'), f.c);
    f.c.startSpeechChunkRecorder();
    const old = recorders[0];
    old.ondataavailable({data: new Blob(['old-header'])});
    f.c.mediaRecorder = null; f.c.version++;
    f.c.startSpeechChunkRecorder();
    const current = recorders[1];
    f.c.startSpeechChunkRecorder();
    assert.equal(recorders.length, 2, 'an active recorder cannot be replaced by another start');
    current.ondataavailable({data: new Blob(['new-header'])});
    old.ondataavailable({data: new Blob(['old-late-frame'])});
    await old.onstop();
    assert.equal(f.c.mediaRecorder, current);
    current.ondataavailable({data: new Blob(['new-frame'])});
    await current.onstop();
    assert.deepEqual(uploads, ['new-headernew-frame']);
});
