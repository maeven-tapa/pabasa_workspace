const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const js = path.join(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js');
const tick = () => new Promise(resolve => setImmediate(resolve));

async function transportTest() {
    const sockets = [], finals = [], interims = [], errors = [];
    class Socket {
        static OPEN = 1;
        constructor() {
            this.readyState = 1;
            this.bufferedAmount = 0;
            this.sent = [];
            sockets.push(this);
            queueMicrotask(() => { this.onopen(); this.message({type: 'ready'}); });
        }
        message(message) { this.onmessage({data: JSON.stringify(message)}); }
        send(data) {
            this.sent.push(data);
            if (data === '{"type":"finish"}') queueMicrotask(() => this.message({type: 'finished'}));
        }
        close() { this.readyState = 3; queueMicrotask(() => this.onclose?.()); }
    }
    class Worklet {
        constructor() {
            this.port = {postMessage: value => {
                assert.equal(value, 'flush');
                this.port.onmessage({data: {audio: new ArrayBuffer(128)}});
                this.port.onmessage({data: {flushed: true}});
            }};
        }
        connect(target) { return target; }
        disconnect() {}
    }
    class Audio {
        constructor() { this.audioWorklet = {addModule: async () => {}}; }
        createMediaStreamSource() { return {connect: target => target, disconnect() {}}; }
        createGain() { return {gain: {}, connect() {}, disconnect() {}}; }
        async resume() {}
        async close() {}
    }
    const context = {window: {location: {href: 'https://test/reader/'}, AudioContext: Audio,
        __PABASA_CRLA_PCM_WORKLET__: '/static/pcm.js'}, WebSocket: Socket, AudioWorkletNode: Worklet,
        URL, Blob, DataView, AbortController, setTimeout: (callback, ms) => ms > 200000 ? 0 : setTimeout(callback, ms), clearTimeout,
        fetch: async () => ({ok: true, json: async () => ({success: true, ticket: 'ticket', path: '/ws/reading/crla/'})})};
    vm.runInNewContext(fs.readFileSync(path.join(js, 'crla_speech_stream.js'), 'utf8'), context);
    let release;
    const stream = new context.window.CrlaSpeechStream({csrf: () => 'csrf', fields: {material_id: 12},
        onInterim: text => interims.push(text),
        onFinal: async message => { if (message.id === 'first') await new Promise(resolve => { release = resolve; }); finals.push(message.id); },
        onError: error => errors.push(error.message)});
    await stream.start({});
    const startupWave = Buffer.from(await stream.wavBlob([new Uint8Array([1, 2, 3, 4]).buffer]).arrayBuffer());
    assert.equal(startupWave.toString('ascii', 0, 4), 'RIFF');
    assert.equal(startupWave.readUInt32LE(24), 16000);
    assert.deepEqual([...startupWave.subarray(44)], [1, 2, 3, 4], 'startup fallback retains the captured PCM');
    const firstSocket = sockets[0];
    firstSocket.message({type: 'interim', transcript: 'ba'});
    assert.deepEqual(interims, ['ba']);
    assert.equal(finals.length, 0, 'interims must never score');
    firstSocket.message({type: 'final', id: 'first'});
    firstSocket.message({type: 'final', id: 'first'});
    firstSocket.message({type: 'final', id: 'second'});
    await tick();
    assert.equal(stream.pending, true);
    stream.sendAudio(new ArrayBuffer(6400));
    assert.ok(firstSocket.sent.some(data => data instanceof ArrayBuffer), 'capture continues during final evaluation');
    release();
    await stream.queue;
    assert.deepEqual(finals, ['first', 'second']);
    assert.equal(stream.pending, false);
    const rotating = stream.rotate();
    stream.sendAudio(new ArrayBuffer(256));
    await rotating;
    await tick();
    assert.equal(stream.active, true, 'old socket close must not kill rotated connection');
    assert.equal(sockets.length, 2);
    assert.ok(sockets[1].sent.some(data => data instanceof ArrayBuffer && data.byteLength === 256), 'rotation preserves audio captured during reconnect');
    await stream.finish();
    assert.ok(sockets[1].sent.some(data => data instanceof ArrayBuffer && data.byteLength === 128), 'flush sends the trailing partial audio frame');
    assert.equal(stream.active, false);
    assert.deepEqual(errors, []);

    const interrupted = new context.window.CrlaSpeechStream({csrf: () => 'csrf', fields: {}, onFinal() {}, onInterim() {}, onError: error => errors.push(error.message)});
    await interrupted.start({});
    sockets.at(-1).bufferedAmount = 128001;
    interrupted.sendAudio(new ArrayBuffer(10));
    assert.equal(interrupted.active, false);
    assert.equal(errors.length, 1, 'overflow must be explicit instead of silently losing speech');
}

function pcmTest() {
    for (const rate of [8000, 16000, 44100, 48000]) {
        const frames = [];
        let Processor;
        class Base { constructor() { this.port = {postMessage: value => { if (value.audio) frames.push(value.audio); }}; } }
        vm.runInNewContext(fs.readFileSync(path.join(js, 'crla_pcm_worklet.js'), 'utf8'), {
            AudioWorkletProcessor: Base, Int16Array, sampleRate: rate,
            registerProcessor: (_, klass) => { Processor = klass; },
        });
        const processor = new Processor();
        // A deliberately awkward block size detects resampling resets between callbacks.
        for (let offset = 0; offset < rate; offset += 127) {
            processor.process([[new Float32Array(Math.min(127, rate - offset)).fill(0.5)]]);
        }
        processor.port.onmessage({data: 'flush'});
        assert.equal(frames.reduce((total, frame) => total + frame.byteLength / 2, 0), 16000);
        for (const frame of frames) {
            assert.ok(frame.byteLength <= 6400);
            assert.equal(new Int16Array(frame)[0], 16384);
        }
    }
}

async function readerTest() {
    const source = fs.readFileSync(path.join(js, 'assessment_reader.js'), 'utf8');
    const extracted = source.slice(source.indexOf('        function canStreamCrla()'), source.indexOf('        async function startSpeechRecognition()'));
    let stream, calls = 0, scoring = 0, fallback = 0, recovered = 0;
    const preview = {};
    class Stream {
        constructor(options) { this.options = options; this.active = true; stream = this; }
        async start() {}
        stop() { this.active = false; }
    }
    const context = vm.createContext({
        window: {CrlaSpeechStream: Stream, AudioWorkletNode: true, WebSocket: true, SpeechDebug: {format: data => data.transcript}},
        document: {getElementById: () => preview},
        crlaStreamStarting: false, stoppingSpeechRecognition: false, isRecording: true, isMuted: false,
        crlaLiveSpeech: null, crlaLiveContext: null, crlaStreamingUnavailable: false, crlaSpeechFailure: false,
        isOfficialAssessmentLaunch: true, isCrla: true, mode: 'word', officialAssessmentId: '12',
        currentIndex: 0, itemResultVersion: 1, isAdvancingItem: false, currentSyllableIndex: 0,
        items: ['bata', 'bato'], getCurrentDisplayText: () => context.items[context.currentIndex],
        liveSessionEnded: false, liveSessionEndRedirecting: false,
        currentMaterialLanguage: 'Filipino', currentAssessmentBranch: 'words', currentStoryState: '',
        currentSttLanguageCode: '', syllableStitchingContext: '', syllableStitchingContextAt: 0, syllableStitchingWindowMs: 15000,
        currentSpeechContext: () => ({index: context.currentIndex, version: context.itemResultVersion,
            syllableIndex: context.currentSyllableIndex, itemText: context.items[context.currentIndex]}),
        isCurrentSpeechContext: c => c.index === context.currentIndex && c.version === context.itemResultVersion && c.syllableIndex === context.currentSyllableIndex,
        getCsrfToken: () => '', mediaStream: {}, sentenceWordResults: [],
        updateAssessmentNavigationButtons() {}, updateSpeechProcessingControls() {},
        setSpeechStatus() {}, appendRawMicInput() {}, resetSyllableStitching() {}, stopSpeechRecognition() {},
        startSpeechChunkRecorder: () => { fallback++; },
        sendAudioChunk: async (blob, item) => { assert.equal(item.itemText, 'bato'); assert.equal(blob.size, 8); recovered++; },
        handleSpeechResult: () => { scoring++; context.currentSyllableIndex++; },
        Date, setTimeout, clearTimeout, AbortController,
        fetch: async url => {
            assert.equal(url, '/api/reading/crla-stream/evaluate/'); calls++;
            return {ok: true, json: async () => ({success: true, transcript: 'bata', language_code: 'fil-PH'})};
        },
    });
    vm.runInContext(extracted, context);
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(stream.options.fields.material_id, '12');
    stream.options.onInterim('ba');
    assert.equal(preview.textContent, 'Hearing: ba');
    assert.equal(scoring, 0);
    await stream.options.onFinal({final_token: 'signed'});
    assert.equal(scoring, 1);
    assert.equal(preview.hidden, true);
    await stream.options.onFinal({final_token: 'signed2'});
    assert.equal(scoring, 2, 'cursor changes within the same item remain eligible');
    context.currentIndex = 1;
    await stream.options.onFinal({final_token: 'stale'});
    assert.equal(calls, 2, 'finals from the previous item never reach scoring');
    Stream.prototype.start = async function () { this.fallbackAudio = new Blob(['captured']); throw new Error('unavailable'); };
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(fallback, 1);
    assert.equal(recovered, 1, 'startup audio is evaluated before fallback recording resumes');
    assert.equal(context.crlaStreamingUnavailable, true);
}

(async () => {
    pcmTest();
    await transportTest();
    await readerTest();
    console.log('PASS: continuous PCM capture, interim-only display, ordered/deduplicated finals, rotation, final flush, stale-item rejection, and clip fallback');
})().catch(error => { console.error(error); process.exitCode = 1; });
