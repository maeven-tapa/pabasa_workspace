// Full reader in local Chrome, with synthetic microphone input and mocked HTTP
// speech responses. Does not access student data, cloud APIs, or the database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js');
const baseline = process.argv.includes('--baseline');
const source = baseline ? spawnSync('git', ['show', 'HEAD:pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'],
    {cwd: root, encoding: 'utf8'}).stdout :
    fs.readFileSync(process.env.CRLA_READER_SOURCE_PATH || path.join(staticRoot, 'assessment_reader.js'), 'utf8');
const script = source.replace('        loadItems();', `
        window.__micTest = {startReading, stopSpeechRecognition, transitionToItem, currentSpeechContext,
            openMicTestDialog, closeMicTestDialog, runMicPlaybackTest,
            flushCurrentSpeechChunk,
            resumeCapture() { stoppingSpeechRecognition = false; startSpeechChunkRecorder(); },
            state: () => ({isRecording, recognitionActive, hasHeardSinceLastChunk,
                streamAttached: Boolean(crlaLiveSpeech), recorder: mediaRecorder?.state,
                recorderStartedAt: speechChunkStartedAt,
                stoppingSpeechRecognition, isAdvancingItem, isSendingChunk, itemResultVersion,
                tracks: mediaStream?.getTracks().map(track => track.readyState),
                currentIndex, currentPageIndex, sampleUrl: micSampleAudioUrl})};
        loadItems();`);
assert.notEqual(script, source);
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()
from django.template.loader import render_to_string
print(json.dumps({mode: render_to_string('pabasa_app/reading_' + mode + '_page.html',
    {'crla_official_assessment_id': 1, 'crla_official_assessment_data': {'assessment_kind': 'crla'}})
    for mode in ['word', 'sentence', 'para']}))
`], {cwd: path.join(root, 'pabasa_site'), encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
const templates = Object.fromEntries(Object.entries(JSON.parse(rendered.stdout)).map(([mode, html]) =>
    [mode, html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '').replace(/<link\b[^>]*>/g, '')]));
const official = {id: 1, assessment_kind: 'crla', language: 'Filipino', official_title: 'CRLA Pre-Test',
    words: ['Pito', 'Bata', 'Mata'], rhyme_pairs: [{word_a: 'pito', word_b: 'dito'}, {word_a: 'bata', word_b: 'mata'}],
    sentences: ['May pito si Ana.', 'May bata sa bahay.'],
    passages: [{title: 'Ang Pito', content: 'May pito si Ana.\n\nNarinig ni Ben ang pito.'}]};
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pabasa-microphone-test-'));
const wavPath = path.join(tempDir, 'synthetic.wav');
const rate = 48000, samples = rate * 4;
const wav = Buffer.alloc(44 + samples * 2);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(rate, 24); wav.writeUInt32LE(rate * 2, 28);
wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(samples * 2, 40);
for (let i = 0; i < samples; i++) wav.writeInt16LE(i / rate < 1.2 || i / rate > 3 ? 0 :
    Math.round(14000 * Math.sin(2 * Math.PI * 440 * i / rate)), 44 + i * 2);
fs.writeFileSync(wavPath, wav);

(async () => {
    let handler, browser;
    const server = http.createServer((req, res) => handler(req, res));
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    try {
        browser = await chromium.launch({channel: 'chrome', headless: true, args: [
            '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
            '--use-file-for-fake-audio-capture=' + wavPath]});
        for (const [branch, mode] of Object.entries({words: 'word', rhymes: 'word', sentences: 'sentence', story_reading: 'para'})) {
            if (process.env.CRLA_CAPTURE_BRANCHES && !process.env.CRLA_CAPTURE_BRANCHES.split(',').includes(branch)) continue;
            const context = await browser.newContext({permissions: ['microphone']});
            await context.route('https://**/*', route => route.abort());
            const page = await context.newPage();
            const errors = [], uploads = [];
            let ticketCount = 0;
            page.on('pageerror', error => errors.push(error.message));
            const state = {stage: branch, branch: branch === 'story_reading' ? 'sentences' : branch, material_id: '1',
                crla_question_index: 0, ...(branch === 'story_reading' ? {selected_story: 'Ang Pito',
                    story_segment_index: 0, story_reading_started_at: new Date().toISOString()} : {})};
            await context.addInitScript(({official, state}) => {
                window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
                window.__PABASA_STUDENT_END_STATE__ = state;
                window.PABASA_USER_ID = 'synthetic-test'; window.PABASA_USER_ROLE = 'student';
                window.__recordedClips = [];
                window.__clipContexts = [];
                const nativeStart = MediaRecorder.prototype.start;
                MediaRecorder.prototype.start = function (...args) {
                    window.__clipContexts.push(window.__micTest?.currentSpeechContext());
                    return nativeStart.apply(this, args);
                };
                // The fake file is shared across successive getUserMedia calls.
                // Provide a quiet initial calibration window on every capture,
                // independent of where the looping tone currently is.
                const nativeMic = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                navigator.mediaDevices.getUserMedia = async constraints => {
                    const input = await nativeMic(constraints);
                    const audio = new AudioContext();
                    await audio.resume();
                    const gain = audio.createGain(), output = audio.createMediaStreamDestination();
                    gain.gain.setValueAtTime(0, audio.currentTime);
                    gain.gain.setValueAtTime(1, audio.currentTime + 1.1);
                    audio.createMediaStreamSource(input).connect(gain).connect(output);
                    for (const track of output.stream.getTracks()) {
                        const stop = track.stop.bind(track);
                        track.stop = () => { stop(); input.getTracks().forEach(track => track.stop()); audio.close(); };
                    }
                    return output.stream;
                };
                const nativeFetch = window.fetch;
                window.fetch = (url, options) => {
                    if (url === '/api/reading/transcribe/') window.__recordedClips.push(options.body.get('audio'));
                    return nativeFetch(url, options);
                };
            }, {official, state});
            handler = async (req, res) => {
                const url = new URL(req.url, origin);
                const chunks = []; for await (const chunk of req) chunks.push(chunk);
                const body = Buffer.concat(chunks);
                const json = (value, code = 200) => { res.writeHead(code, {'Content-Type': 'application/json'}); res.end(JSON.stringify(value)); };
                if (url.pathname === '/api/reading/crla-stream/start/') {
                    ticketCount++; return json({success: false, error: 'Synthetic refused live ticket'}, 403);
                }
                if (url.pathname === '/api/reading/transcribe/') {
                    assert.ok(body.includes(Buffer.from('name="official_assessment_id"\r\n\r\n1\r\n')),
                        'fallback must identify the assessment for server authorization');
                    uploads.push(body);
                    // No recognized speech: exercise the real callback without advancing/scoring the fixture.
                    return json({success: true, transcript: '', correct_word_count: 0, matched: 0, word_results: []});
                }
                if (url.pathname.startsWith('/api/')) return json({success: true, state,
                    session: {status: 'started', student_states: {}}});
                if (url.pathname.startsWith('/static/')) {
                    const file = path.join(staticRoot, path.basename(url.pathname));
                    res.writeHead(200, {'Content-Type': 'application/javascript'});
                    res.end(fs.existsSync(file) ? fs.readFileSync(file) : ''); return;
                }
                res.writeHead(200, {'Content-Type': 'text/html'}); res.end(templates[mode]);
            };
            await page.goto(`${origin}/dashboard/assessment/reading_ui/${mode}/?official_assessment_id=1&live=1&live_session_id=synthetic-test&countdown=0&live_recovery=1&crla_stage=${branch}`);
            await page.addScriptTag({url: origin + '/static/crla_speech_stream.js'});
            await page.evaluate(() => { window.__PABASA_CRLA_PCM_WORKLET__ = '/static/crla_pcm_worklet.js'; });
            await page.addScriptTag({content: script});
            await page.evaluate(() => __micTest.openMicTestDialog());
            await page.click('#micSampleRecordBtn');
            await page.waitForFunction(() => Boolean(__micTest.state().sampleUrl));
            const sampleBytes = await page.evaluate(async () => (await (await fetch(__micTest.state().sampleUrl)).blob()).size);
            assert.ok(sampleBytes > 1000);
            await page.click('#micTestCloseBtn');
            await page.evaluate(() => __micTest.startReading());
            await page.waitForFunction(() => __micTest.state().recorder === 'recording', null, {timeout: 8000});
            assert.equal((await page.evaluate(() => __micTest.state())).streamAttached, false,
                'stopped live stream cannot retain ownership of clip flushing');
            async function captureAndFlush() {
                const before = uploads.length;
                await page.waitForFunction(() => __micTest.state().hasHeardSinceLastChunk, null, {timeout: 15000});
                // A VAD speech flag can refer to the preceding clip. Observe a
                // full synthetic silence/tone cycle before checking new audio.
                await page.waitForTimeout(4100);
                await page.evaluate(() => __micTest.flushCurrentSpeechChunk());
                await page.waitForFunction(() => __micTest.state().recorder === undefined && !__micTest.state().isSendingChunk);
                assert.ok(uploads.length > before, 'flushing submits the actual recording: ' +
                    JSON.stringify(await page.evaluate(() => ({state: __micTest.state(), contexts: __clipContexts}))));
                const energy = await page.evaluate(async before => {
                    const audio = new AudioContext();
                    try {
                        let peak = 0;
                        for (const blob of __recordedClips.slice(before)) {
                            const decoded = await audio.decodeAudioData(await blob.arrayBuffer());
                            peak = decoded.getChannelData(0).reduce((max, sample) => Math.max(max, Math.abs(sample)), peak);
                        }
                        return peak;
                    } finally { await audio.close(); }
                }, before);
                assert.ok(energy > 0.01, 'decoded recording contains non-silent microphone samples');
                await page.evaluate(() => __micTest.resumeCapture());
                await page.waitForFunction(() => __micTest.state().recorder === 'recording');
            }
            await captureAndFlush();
            const beforeTransition = (await page.evaluate(() => __micTest.state())).recorderStartedAt;
            if (branch === 'story_reading') {
                // Continuous synthetic input keeps the learner's Skip control
                // busy. Invoke its actual handler to isolate capture lifecycle
                // from that unchanged navigation/silence policy.
                await page.locator('#nextBtn').dispatchEvent('click');
                await page.waitForFunction(() => __micTest.state().currentPageIndex === 1);
                assert.equal((await page.evaluate(() => __micTest.state())).currentPageIndex, 1);
            } else {
                await page.evaluate(() => __micTest.transitionToItem(1));
                assert.equal((await page.evaluate(() => __micTest.state())).currentIndex, 1);
            }
            await page.waitForFunction(before => __micTest.state().recorderStartedAt > before,
                beforeTransition, {timeout: 1500});
            await captureAndFlush();
            await page.evaluate(() => __micTest.openMicTestDialog());
            await page.click('#micTestCloseBtn');
            await page.waitForFunction(() => __micTest.state().recorder === 'recording');
            await captureAndFlush();
            assert.equal(ticketCount, 1, 'fallback persists across recording restarts');
            assert.deepEqual(errors, []);
            console.log(`PASS ${branch}: mic sample ${sampleBytes} bytes; 403 fallback, non-silent uploaded audio, flush, transition and mic-check resume (${uploads.length} uploads)`);
            await page.evaluate(() => __micTest.stopSpeechRecognition());
            await context.close();
        }
    } finally {
        await browser?.close(); await new Promise(resolve => server.close(resolve));
        fs.unlinkSync(wavPath); fs.rmdirSync(tempDir);
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
