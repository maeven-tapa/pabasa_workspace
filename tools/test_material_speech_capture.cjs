const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,
    '../pabasa_site/pabasa_app/static/pabasa_app/js/material_speech_capture.js'), 'utf8');
function environment({selection = 'google', startError, activeError, empty = false} = {}) {
    const instances = [], interims = [];
    class Stream {
        constructor(options) { this.options = options; instances.push(this); }
        async start(stream) {
            this.mic = stream;
            if (startError) throw startError;
            this.options.onInterim('provisional');
        }
        async finish() {
            if (activeError) this.options.onError(activeError);
            this.resultToken = 'signed'; this.hasSpeech = !empty;
        }
        stop() { this.stopped = true; }
    }
    const window = {CrlaSpeechStream: Stream, AudioContext: class {}, AudioWorkletNode: class {},
        WebSocket: class {}, __PABASA_CRLA_PCM_WORKLET__: '/pcm.js', PrescribedSttSettings: {selection}};
    vm.runInNewContext(source, {window, document: {cookie: 'csrftoken=csrf'}, DOMException});
    const capture = window.MaterialSpeechCapture.begin({}, {
        purpose: 'practice', material_id: 12, target_text: 'cat', mode: 'word'}, text => interims.push(text));
    return {capture, api: window.MaterialSpeechCapture, instances, interims};
}
test('only a completely flushed result attaches to the original recording', async () => {
    const env = environment(), blob = new Blob(['audio']), form = new FormData();
    assert.deepEqual(env.interims, ['provisional']);
    env.api.attach(form, blob);
    assert.equal(form.has('material_stream_token'), false);
    assert.equal(await env.capture.finish(blob), blob);
    env.api.attach(form, blob);
    assert.equal(form.get('material_stream_token'), 'signed');
    assert.equal(env.instances[0].options.fields.complete_utterance, true);
    assert.equal(env.instances[0].options.startUrl, '/api/reading/material-stream/start/');
});
test('startup failure retains the full clip; access denial never falls back', async () => {
    const blob = new Blob(['audio']);
    const env = environment({startError: new Error('offline')});
    assert.equal(await env.capture.finish(blob), blob);
    assert.equal(blob.materialStreamToken, undefined);
    for (const status of [400, 401, 403]) {
        const denied = environment({startError: Object.assign(new Error('denied'), {status})});
        await assert.rejects(denied.capture.finish(blob), /denied/);
    }
});
test('active failures, empty finals, and cancellation cannot score', async () => {
    for (const options of [{activeError: new Error('interrupted')}, {empty: true}]) {
        const env = environment(options), blob = new Blob(['audio']);
        await assert.rejects(env.capture.finish(blob));
        assert.equal(blob.materialStreamToken, undefined);
    }
    const env = environment();
    env.capture.stop();
    await assert.rejects(env.capture.finish(new Blob(['audio'])), {name: 'AbortError'});
    assert.ok(env.instances[0].stopped);
});
test('selected Knowlez and Chirp 2 retain clip recognition', () => {
    for (const selection of ['knowlez', 'chirp_2']) {
        const env = environment({selection});
        assert.equal(env.capture, null);
        assert.equal(env.instances.length, 0);
    }
});
