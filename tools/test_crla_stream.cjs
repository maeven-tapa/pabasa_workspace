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
        constructor() { this.state = 'running'; this.audioWorklet = {addModule: async () => {}}; }
        createMediaStreamSource() { return {connect: target => target, disconnect() {}}; }
        createGain() { return {gain: {}, connect() {}, disconnect() {}}; }
        async suspend() { this.state = 'suspended'; }
        async resume() { this.state = 'running'; }
        async close() {}
    }
    const context = {window: {location: {href: 'https://test/reader/'}, AudioContext: Audio,
        __PABASA_CRLA_PCM_WORKLET__: '/static/pcm.js'}, WebSocket: Socket, AudioWorkletNode: Worklet,
        URL, Blob, DataView, AbortController, setTimeout: (callback, ms) => ms > 200000 ? 0 : setTimeout(callback, ms), clearTimeout,
        fetch: async () => ({ok: true, json: async () => ({success: true, ticket: 'ticket', path: '/ws/reading/crla/'})})};
    vm.runInNewContext(fs.readFileSync(path.join(js, 'crla_speech_stream.js'), 'utf8'), context);
    let release, stream;
    stream = new context.window.CrlaSpeechStream({csrf: () => 'csrf', fields: {material_id: 12},
        onInterim: text => interims.push(text),
        onFinal: async message => {
            await stream.pauseCapture();
            if (message.id === 'first') await new Promise(resolve => { release = resolve; });
            finals.push(message.id);
            await stream.resumeCapture();
        },
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
    assert.equal(stream.capturePaused, true, 'final evaluation pauses the live capture graph');
    stream.sendAudio(new ArrayBuffer(6400));
    assert.equal(firstSocket.sent.some(data => data instanceof ArrayBuffer && data.byteLength === 6400), false,
        'audio is not sent while the final is being evaluated');
    release();
    await stream.queue;
    assert.deepEqual(finals, ['first', 'second']);
    assert.equal(stream.pending, false);
    assert.equal(stream.capturePaused, false, 'capture resumes after final evaluation');
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

    const pausedFinish = new context.window.CrlaSpeechStream({csrf: () => 'csrf', fields: {}, onFinal() {}, onInterim() {}, onError: error => errors.push(error.message)});
    await pausedFinish.start({});
    await pausedFinish.pauseCapture();
    await pausedFinish.finish();
    assert.equal(pausedFinish.active, false, 'finalization closes a paused stream without waiting for a suspended worklet flush');
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

function statusTest() {
    const source = fs.readFileSync(path.join(js, 'assessment_reader.js'), 'utf8');
    const template = fs.readFileSync(path.join(__dirname,
        '../pabasa_site/pabasa_app/templates/pabasa_app/reading_assessment_base.html'), 'utf8');
    const stageEnd = template.indexOf('</section>', template.indexOf('<section class="word-stage"'));
    const overlayIndex = template.indexOf('id="crlaProcessingOverlay"');
    const articleStart = template.lastIndexOf('<article class="reader-card', overlayIndex);
    const articleEnd = template.indexOf('</article>', overlayIndex);
    assert.ok(stageEnd >= 0 && overlayIndex > stageEnd && articleStart >= 0 && articleEnd > overlayIndex,
        'overlay is a card-level child outside the word-stage');
    assert.match(template, /\.reader-card\s*\{[\s\S]*?border-radius:\s*clamp\(24px, 4vw, 34px\);[\s\S]*?overflow:\s*hidden;/,
        'the existing reading card supplies rounded boundaries and clipping');
    assert.match(template, /\.crla-processing-overlay\s*\{[\s\S]*?position:\s*absolute;[\s\S]*?inset:\s*0;[\s\S]*?border-radius:\s*inherit;[\s\S]*?background:\s*rgba\(15, 45, 69, 0\.65\);[\s\S]*?color:\s*#fff;[\s\S]*?pointer-events:\s*none;/,
        'overlay covers the full rounded reading card without blocking controls');
    assert.match(template, /\.reader-card:has\(> #crlaProcessingOverlay:not\(\[hidden\]\)\) \.word-stage > :is\([\s\S]*?\.reading-word[\s\S]*?opacity:\s*0\.4;/,
        'visible processing fades reading text and its word highlighting');
    assert.match(template, /\.crla-processing-spinner\s*\{[\s\S]*?width:\s*30px;[\s\S]*?height:\s*30px;[\s\S]*?border:\s*3px solid rgba\(255, 255, 255, 0\.42\);[\s\S]*?border-top-color:\s*#fff;/,
        '30px spinner uses white colors that contrast with the navy overlay');
    assert.doesNotMatch(template, /Sandali lang! Hintaying matapos bago magsalita muli\./,
        'the longer helper instruction has been removed');
    const start = source.indexOf('        function renderOfficialCrlaStatus() {');
    const end = source.indexOf('\n        function syncPhraseMicrophoneButton()', start);
    assert.ok(start >= 0 && end > start, 'the official CRLA status renderer is available');
    const elements = {
        status: {textContent: ''}, dot: {setAttribute() {}}, overlay: {hidden: true},
        helper: {hidden: true, classList: {toggle() {}}, querySelector: selector => ({
            '.helper-dot': elements.dot,
        })[selector]},
    };
    const context = vm.createContext({
        document: {
            querySelector: () => elements.helper,
            getElementById: id => id === 'crlaProcessingOverlay' ? elements.overlay : elements.status,
        },
        isOfficialAssessmentLaunch: true, isCrla: true,
        isSendingChunk: false, pendingAudioChunk: null, crlaLiveSpeech: null,
        isRecording: true, isMuted: false, recognitionActive: true,
        currentAssessmentBranch: 'words',
        shell: {classList: {contains: name => name === 'is-hearing'}}, speechFrameCount: 3,
        readingWord: null, itemLocked: [], currentIndex: 0, getCurrentSectionLabel: () => 'Word',
    });
    vm.runInContext(source.slice(start, end), context);
    const render = vm.runInContext('renderOfficialCrlaStatus', context);

    context.isSendingChunk = true;
    render();
    assert.equal(elements.status.textContent, '', 'top helper does not duplicate the overlay message');
    assert.equal(elements.overlay.hidden, false, 'overlay appears during fallback evaluation');
    context.isSendingChunk = false;
    context.crlaLiveSpeech = {pending: true, capturePaused: true};
    render();
    assert.equal(elements.status.textContent, '', 'live pending state does not duplicate overlay text');
    assert.equal(elements.overlay.hidden, false, 'overlay remains visible for a pending live final');
    context.crlaLiveSpeech = null;
    render();
    assert.equal(elements.status.textContent, 'Hearing you...', 'normal live speech still reports detected audio');
    assert.equal(elements.overlay.hidden, true, 'overlay disappears after evaluation');
    context.speechFrameCount = 0;
    context.shell.classList.contains = () => false;
    render();
    assert.equal(elements.status.textContent, 'Listening...', 'active capture with no detected speech reports Listening');
    context.currentAssessmentBranch = 'rhymes';
    context.recognitionActive = false;
    render();
    assert.equal(elements.status.textContent, 'Read the Rhyme', 'the rhyme branch shows its singular reading prompt');
    for (const [branch, section, label] of [
        ['words', 'Word', 'Read the Word'],
        ['sentences', 'Sentence', 'Read the Sentence'],
        ['story', 'Story', 'Read the Story'],
    ]) {
        context.currentAssessmentBranch = branch;
        context.getCurrentSectionLabel = () => section;
        render();
        assert.equal(elements.status.textContent, label, `${branch} branch starts with its reading prompt`);
    }
    context.currentAssessmentBranch = 'words';
    context.recognitionActive = true;
    context.isSendingChunk = true;
    render();
    assert.equal(elements.status.textContent, '', 'microphone activity cannot replace genuine Processing');
    assert.equal(elements.overlay.hidden, false, 'the overlay remains visible during genuine Processing');
    context.isSendingChunk = false;
    context.recognitionActive = false;
    context.currentAssessmentBranch = 'words';
    context.getCurrentSectionLabel = () => 'Word';
    render();
    assert.equal(elements.status.textContent, 'Read the Word', 'idle state returns to its assessment prompt');
}

async function fallbackSilenceTest() {
    const source = fs.readFileSync(path.join(js, 'assessment_reader.js'), 'utf8');
    const start = source.indexOf('        function startSpeechChunkRecorder() {');
    const end = source.indexOf('        function finishCurrentAudioChunk(force = false)', start);
    assert.ok(start >= 0 && end > start, 'fallback recorder lifecycle is available');
    const submitted = [];
    class Recorder {
        constructor(stream) { this.stream = stream; this.state = 'inactive'; this.mimeType = 'audio/webm'; }
        start() { this.state = 'recording'; }
        requestData() {}
        stop() { this.state = 'inactive'; }
    }
    const context = vm.createContext({
        window: {MediaRecorder: Recorder}, MediaRecorder: Recorder, Blob,
        mediaStream: {}, stoppingSpeechRecognition: false, isMuted: false, isRecording: true,
        isAdvancingItem: false, sentenceCountdownTimer: null, mediaRecorder: null,
        canStreamCrla: () => false, currentSpeechContext: () => ({itemText: 'bata'}),
        pickAudioMimeType: () => '',
        isOfficialAssessmentLaunch: true, mode: 'word', currentIndex: 0,
        sentenceWordResults: [],
        isCurrentSpeechContext: () => true,
        sendAudioChunk: async blob => submitted.push(blob),
        hasHeardSinceLastChunk: false,
        audioAnalyser: {}, lastHeardAt: 0, speechChunkMs: 10000, Date,
    });
    vm.runInContext(source.slice(start, end), context);
    const sendCheckStart = source.indexOf('        function shouldSendAudioChunk() {');
    const sendCheckEnd = source.indexOf('        function isSpeechResponsePending()', sendCheckStart);
    vm.runInContext(source.slice(sendCheckStart, sendCheckEnd), context);
    const startRecorder = vm.runInContext('startSpeechChunkRecorder', context);
    const stopWithChunk = async () => {
        const recorder = context.mediaRecorder;
        recorder.ondataavailable({data: new Blob(['audio frame'])});
        recorder.stop();
        await recorder.onstop();
    };

    startRecorder();
    await stopWithChunk();
    assert.equal(submitted.length, 0, 'a nonempty silent MediaRecorder chunk is not submitted when VAD has no speech evidence');

    context.hasHeardSinceLastChunk = true;
    await stopWithChunk();
    assert.equal(submitted.length, 1, 'a MediaRecorder chunk is submitted when the existing VAD detects speech');
    assert.equal(context.hasHeardSinceLastChunk, false, 'speech evidence is consumed once per fallback chunk');
}

async function readerTest() {
    const source = fs.readFileSync(path.join(js, 'assessment_reader.js'), 'utf8');
    const extracted = source.slice(source.indexOf('        function canStreamCrla()'), source.indexOf('        async function startSpeechRecognition()'));
    let stream, calls = 0, scoring = 0, fallback = 0, recovered = 0, timerSyncs = 0, releaseEvaluation, holdEvaluation = false;
    const preview = {};
    class Stream {
        constructor(options) { this.options = options; this.active = true; stream = this; }
        async start() {}
        async pauseCapture() { this.capturePaused = true; }
        async resumeCapture() { this.capturePaused = false; }
        stop() { this.active = false; }
    }
    const context = vm.createContext({
        window: {CrlaSpeechStream: Stream, AudioWorkletNode: true, WebSocket: true, SpeechDebug: {format: data => data.transcript}},
        document: {getElementById: () => preview},
        crlaStreamStarting: false, stoppingSpeechRecognition: false, isRecording: true, isMuted: false, isFinalizingReading: false,
        sentenceCountdownTimer: null,
        crlaLiveSpeech: null, crlaLiveContext: null, crlaStreamingUnavailable: false, crlaSpeechFailure: false,
        isSendingChunk: false, hasHeardSinceLastChunk: false,
        isOfficialAssessmentLaunch: true, isCrla: true, mode: 'word', officialAssessmentId: '12',
        customMaterialData: null, isTemplateActivity: false,
        currentIndex: 0, itemResultVersion: 1, isAdvancingItem: false, currentSyllableIndex: 0,
        items: ['bata', 'bato'], getCurrentDisplayText: () => context.items[context.currentIndex],
        liveSessionPaused: false, liveSessionEnded: false, liveSessionEndRedirecting: false,
        currentMaterialLanguage: 'Filipino', currentAssessmentBranch: 'words', currentStoryState: '',
        currentSttLanguageCode: '', syllableStitchingContext: '', syllableStitchingContextAt: 0, syllableStitchingWindowMs: 15000,
        currentSpeechContext: () => ({index: context.currentIndex, version: context.itemResultVersion,
            syllableIndex: context.currentSyllableIndex, itemText: context.items[context.currentIndex]}),
        isCurrentSpeechContext: c => c.index === context.currentIndex && c.version === context.itemResultVersion && c.syllableIndex === context.currentSyllableIndex,
        getCsrfToken: () => '', mediaStream: {}, sentenceWordResults: [],
        updateAssessmentNavigationButtons() {}, updateSpeechProcessingControls() {}, renderOfficialCrlaStatus() {},
        syncStoryReadingTimerProcessing() { timerSyncs++; },
        setSpeechStatus: message => { context.lastStatus = message; }, appendRawMicInput() {}, resetSyllableStitching() {}, stopSpeechRecognition() {},
        startSpeechChunkRecorder: () => { fallback++; },
        sendAudioChunk: async (blob, item) => { assert.equal(item.itemText, 'bato'); assert.equal(blob.size, 8); recovered++; },
        handleSpeechResult: () => { scoring++; context.currentSyllableIndex++; },
        Date, setTimeout, clearTimeout, AbortController,
        fetch: async url => {
            assert.equal(url, '/api/reading/crla-stream/evaluate/'); calls++;
            if (holdEvaluation) await new Promise(resolve => { releaseEvaluation = resolve; });
            return {ok: true, json: async () => ({success: true, transcript: 'bata', language_code: 'fil-PH'})};
        },
    });
    vm.runInContext(extracted, context);
    vm.runInContext(source.slice(source.indexOf('        function finishCurrentAudioChunk(force = false)'),
        source.indexOf('        async function flushCurrentSpeechChunk(')), context);
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(stream.options.fields.material_id, '12');
    stream.options.onInterim('ba');
    assert.equal(preview.textContent, 'Hearing: ba');
    assert.equal(scoring, 0);
    holdEvaluation = true;
    const firstEvaluation = stream.options.onFinal({final_token: 'signed'});
    await tick();
    assert.equal(stream.capturePaused, true, 'capture is suspended while the evaluation request is pending');
    assert.equal(context.lastStatus, 'Processing...', 'Processing is displayed only after capture is suspended');
    assert.equal(context.isSendingChunk, true);
    releaseEvaluation();
    await firstEvaluation;
    holdEvaluation = false;
    assert.equal(scoring, 1);
    assert.equal(preview.hidden, true);
    assert.equal(stream.capturePaused, false, 'capture resumes only after evaluation completes');
    assert.ok(timerSyncs >= 2, 'the Story Reading timer synchronizes to capture pause and resume');
    await stream.options.onFinal({final_token: 'signed2'});
    assert.equal(scoring, 2, 'cursor changes within the same item remain eligible');
    const completedStream = stream;
    for (const flag of ['isAdvancingItem', 'isFinalizingReading']) {
        context[flag] = true;
        context.crlaLiveContext = null;
        context.finishCurrentAudioChunk();
        await context.startCrlaLiveSpeech();
        assert.equal(stream, completedStream, flag + ' must prevent reconnecting the speech stream');
        assert.equal(completedStream.active, true, flag + ' must preserve the original stream for final flush');
        context[flag] = false;
    }
    context.currentIndex = 1;
    await stream.options.onFinal({final_token: 'stale'});
    assert.equal(calls, 2, 'finals from the previous item never reach scoring');
    Stream.prototype.start = async function () { this.fallbackAudio = new Blob(['captured']); throw new Error('unavailable'); };
    context.hasHeardSinceLastChunk = true;
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(fallback, 1);
    assert.equal(recovered, 1, 'startup audio is evaluated before fallback recording resumes');
    assert.equal(context.crlaStreamingUnavailable, true);

    context.hasHeardSinceLastChunk = false;
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(fallback, 2, 'fallback recorder is ready after live startup fails');
    assert.equal(recovered, 1, 'silent startup PCM is not submitted for evaluation');

    Stream.prototype.start = async function () { throw Object.assign(new Error('assessment access changed'), {status: 403}); };
    context.crlaStreamingUnavailable = false;
    context.crlaSpeechFailure = false;
    await vm.runInContext('startCrlaLiveSpeech()', context);
    assert.equal(context.crlaStreamingUnavailable, true, 'a refused live ticket switches to clip capture');
    assert.equal(fallback, 3, 'clip capture continues after a refused live ticket');
    assert.equal(context.crlaLiveSpeech, null, 'clip fallback must release the stopped stream so flush drains the recorder');
}

(async () => {
    pcmTest();
    statusTest();
    await fallbackSilenceTest();
    await transportTest();
    await readerTest();
    console.log('PASS: PCM capture, interim-only display, serialized finals, rotation/finalization, stale-item rejection, silent-startup rejection, fallback, and branch-aware CRLA status lifecycle');
})().catch(error => { console.error(error); process.exitCode = 1; });
