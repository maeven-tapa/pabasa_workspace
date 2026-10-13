// Local Chrome regression using the real reader, stream transport, and Django alignment.
// Microphone/Google/WebSocket responses are synthetic. All HTTP is intercepted;
// Django uses in-memory SQLite and no accounts or persisted student data are used.
// Run: node tools/test_crla_story_completion.cjs (CRLA_PLAYWRIGHT_PATH if needed).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os, json, sys, django
sys.path.insert(0, 'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()
from django.template.loader import render_to_string
from pabasa_app.management.commands.seed_official_crla_assessments import OFFICIAL_CRLA_CONTENT
from pabasa_app.reading_stt import analyze_reading, align_story_transcript
cases = []
for spec in OFFICIAL_CRLA_CONTENT.values():
    for story_number, story in enumerate(spec['passages'], 1):
        target = story['content'].split('\\n\\n')[-1]
        responses = {}
        def response(spoken, cursor=0, start=0):
            data = analyze_reading(target, cursor, spoken, 'fil-PH', crla_story_reading=True)
            alignment = align_story_transcript(target, spoken, 'fil-PH', start_word_index=start, crla_story_reading=True)
            return dict(data, word_results=alignment['word_results'], word_alignment=alignment,
                        success=True, stt_provider='google', language_code='fil-PH')
        responses['correct'] = response(target)
        words = responses['correct']['words']
        responses['partial'] = response(' '.join(words[:2]))
        cursor = responses['partial']['current_syllable_index']
        responses['remaining'] = response(' '.join(words[2:]), cursor, 2)
        responses['ending_miscue'] = response(' '.join(words[:-1] + ['mali']))
        official = dict(spec, id=1, assessment_kind='crla', language='Filipino',
                        official_title=spec['title'], official_code=spec['code'])
        cases.append(dict(official=official, story=story, story_number=story_number,
                          target=target, responses=responses))
print(json.dumps(dict(cases=cases, html=render_to_string('pabasa_app/reading_para_page.html',
    {'crla_official_assessment_id': 1, 'is_admin_preview': True}))))
`], {cwd: root, encoding: 'utf8', env: {...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:',
    DJANGO_ENV: 'development', PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const html = fixture.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '').replace(/<link\b[^>]*>/g, '');
const jsRoot = path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js');
// The optional source override lets the same regression check a prior revision.
const reader = fs.readFileSync(process.env.CRLA_READER_SOURCE_PATH || path.join(jsRoot, 'assessment_reader.js'), 'utf8')
    .replace('        loadItems();', `        window.__readerTest = {
        async begin() {
            isRecording = true; startTime = Date.now() - 2000;
            currentPageIndex = itemPages[0].length - 1;
            currentStorySegmentIndex = currentPageIndex;
            for (let page = 0; page < currentPageIndex; page++) {
                storyWordResults[page] = Object.fromEntries(Array.from(
                    {length: readableWordCount(itemPages[0][page])}, (_, word) => [word, 'correct']));
            }
            syncStrictStoryCounts(); updateUI(); renderStoryReadingState(currentSelectedStory);
            startStoryReadingTimer(Date.now() - 2000);
            await startSpeechRecognition();
        },
        state() { return {stage: currentStoryState, advancing: isAdvancingItem, finalizing: isFinalizingReading,
            speechFailure: crlaSpeechFailure, recording: isRecording, starting: crlaStreamStarting,
            elapsed: storyReadingElapsedMs(), timerPaused: storyReadingTimerPausedAt !== null,
            text: getCurrentDisplayText(), questions: currentStoryQuestions.length,
            evidence: strictStoryEvidence(), saved: readStudentEndState()}; }
    };
        loadItems();`);
const transport = fs.readFileSync(path.join(jsRoot, 'crla_speech_stream.js'), 'utf8');
const origin = 'http://localhost:9876';
const previewKey = 'pabasa_admin_crla_preview:story-completion-test';

async function scenario(browser, sample, name) {
    const context = await browser.newContext({viewport: {width: 1366, height: 768}});
    try {
        const page = await context.newPage();
        page.setDefaultTimeout(6000);
        const errors = [], evaluated = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.addInitScript(({official, story, story_number, previewKey}) => {
            window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
            window.__PABASA_ADMIN_PREVIEW__ = true;
            window.PABASA_USER_ID = '99'; window.PABASA_USER_ROLE = 'admin';
            sessionStorage.setItem(previewKey, JSON.stringify({stage: 'story_reading', branch: 'story',
                material_id: '1', selected_story: story.title, story_number, story_segment_index: 0}));
            const mock = window.__speechFixture = {sockets: [], tracks: [], failFinish: false, tail: null,
                nextReadyDelay: 1000, finishDelay: 0, finishRequests: 0, sequence: 0};
            class Socket {
                static OPEN = 1;
                constructor() {
                    this.readyState = 1; this.bufferedAmount = 0;
                    const delay = mock.sockets.length ? mock.nextReadyDelay : 0;
                    mock.sockets.push(this);
                    this.readyTimer = setTimeout(() => { if (this.readyState === 1) {
                        this.onopen(); this.message({type: 'ready'});
                    } }, delay);
                }
                message(data) { this.onmessage({data: JSON.stringify(data)}); }
                send(data) {
                    if (data !== '{"type":"finish"}') return;
                    mock.finishRequests++;
                    if (mock.failFinish) { queueMicrotask(() => this.close()); return; }
                    if (mock.tail) {
                        this.message({type: 'final', id: String(++mock.sequence), final_token: mock.tail});
                        mock.tail = null;
                    }
                    setTimeout(() => { if (this.readyState === 1) this.message({type: 'finished'}); }, mock.finishDelay);
                }
                close() {
                    if (this.readyState === 3) return;
                    clearTimeout(this.readyTimer); this.readyState = 3;
                    queueMicrotask(() => this.onclose?.());
                }
            }
            class Worklet {
                constructor() { this.port = {postMessage: () => this.port.onmessage({data: {flushed: true}})}; }
                connect(target) { return target; }
                disconnect() {}
            }
            class Audio {
                constructor() { this.audioWorklet = {addModule: async () => {}}; }
                createMediaStreamSource() { return {connect: target => target, disconnect() {}}; }
                createGain() { return {gain: {}, connect() {}, disconnect() {}}; }
                createAnalyser() { return {fftSize: 1024, getByteTimeDomainData: samples => samples.fill(128)}; }
                async resume() {}
                async close() {}
            }
            window.WebSocket = Socket; window.AudioWorkletNode = Worklet; window.AudioContext = Audio;
            window.SpeechDebug = {format: data => data.transcript};
            Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
                const track = {stopped: false, stop() { this.stopped = true; }};
                mock.tracks.push(track); return {getTracks: () => [track]};
            }});
        }, {...sample, previewKey});
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== origin) return route.abort();
            if (url.pathname.startsWith('/dashboard/assessment/reading_ui/')) {
                return route.fulfill({contentType: 'text/html', body: html});
            }
            if (url.pathname === '/api/reading/crla-stream/start/') {
                const fields = route.request().postDataJSON();
                assert.equal(fields.language, 'Filipino');
                assert.equal(fields.mode, 'paragraph');
                return route.fulfill({json: {success: true, ticket: 'synthetic', path: '/synthetic-ws/'}});
            }
            if (url.pathname === '/api/reading/crla-stream/evaluate/') {
                const token = route.request().postDataJSON().final_token;
                evaluated.push(token);
                return route.fulfill({json: sample.responses[token]});
            }
            // Preview stories store progress in sessionStorage; never call a student write endpoint.
            assert.ok(!['/api/assessment/end-state/', '/record-assessment-completion/'].includes(url.pathname));
            return route.fulfill({body: ''});
        });
        await page.goto(origin + '/dashboard/assessment/reading_ui/para/?official_assessment_id=1' +
            '&admin_preview=1&admin_preview_token=story-completion-test&crla_stage=story_reading');
        await page.addScriptTag({content: transport});
        await page.addScriptTag({content: reader});
        await page.waitForFunction(() => window.__readerTest && document.querySelector('.reader-shell').classList.contains('is-story-reading'));
        await page.evaluate(() => window.__readerTest.begin());
        const initial = await page.evaluate(() => window.__readerTest.state());
        assert.equal(initial.text, sample.target);
        const priorWordsRead = initial.evidence.words_read;
        const finalWordCount = sample.responses.correct.words.length;
        const emit = token => page.evaluate(token => {
            const mock = window.__speechFixture;
            mock.sockets.at(-1).message({type: 'final', id: String(++mock.sequence), final_token: token});
        }, token);
        const skipping = name.startsWith('skip');
        const failure = name.endsWith('failure');
        if (failure) await page.evaluate(() => { window.__speechFixture.failFinish = true; });
        await emit(skipping ? 'partial' : name === 'ending_miscue' ? name : 'correct');
        await page.waitForFunction(() => window.__readerTest.state().advancing ||
            (!window.__readerTest.state().starting && !document.getElementById('nextBtn').disabled));
        if (skipping) {
            await page.waitForFunction(() => !document.getElementById('nextBtn').disabled);
            if (name === 'skip_pending_final') await page.evaluate(() => { window.__speechFixture.tail = 'remaining'; });
            if (name === 'skip_repeated') await page.evaluate(() => { window.__speechFixture.finishDelay = 300; });
            await page.locator('#nextBtn').click();
            if (name === 'skip_repeated') {
                assert.equal(await page.locator('#nextBtn').isEnabled(), false);
                await page.evaluate(() => document.getElementById('nextBtn').click());
            }
        }
        if (failure) {
            await page.waitForFunction(() => window.__readerTest.state().speechFailure && !window.__readerTest.state().finalizing);
            const failed = await page.evaluate(() => window.__readerTest.state());
            assert.equal(failed.stage, 'story_reading');
            assert.equal(failed.advancing, false, 'Failed finalization must release Skip');
            assert.equal(failed.recording, true, 'Microphone recovery must preserve the reading attempt');
            assert.ok(failed.elapsed >= 2000 && failed.timerPaused, 'Failed speech keeps the original timer paused');
            assert.equal(failed.evidence.words_read, priorWordsRead + (skipping ? 2 : finalWordCount));
            assert.equal(await page.locator('#nextBtn').isEnabled(), true);
            await page.evaluate(() => { window.__speechFixture.failFinish = false; window.__speechFixture.nextReadyDelay = 0; });
            await page.locator('#btnToggleMic').click();
            await page.locator('#btnToggleMic').click();
            await page.waitForFunction(() => !window.__readerTest.state().speechFailure && !window.__readerTest.state().starting);
            await page.locator('#nextBtn').click();
        }
        await page.waitForFunction(() => window.__readerTest.state().stage === 'story_comprehension');
        const completed = await page.evaluate(() => ({...window.__readerTest.state(),
            sockets: window.__speechFixture.sockets.length,
            finishRequests: window.__speechFixture.finishRequests,
            allTracksStopped: window.__speechFixture.tracks.every(track => track.stopped)}));
        const skippedWords = skipping && name !== 'skip_pending_final' ? finalWordCount - 2 : 0;
        const miscues = name === 'ending_miscue' ? 1 : skippedWords;
        assert.equal(completed.saved.words_read, priorWordsRead + finalWordCount - miscues);
        assert.equal(completed.saved.miscues, miscues);
        assert.equal(completed.saved.story_number, sample.story_number);
        assert.equal(completed.questions, 6);
        assert.equal(await page.locator('#counter').textContent(), 'Story Comprehension 1/6');
        assert.equal(await page.locator('#crlaQuestionPanel .story-question-kicker, #crlaQuestionCounter, .crla-progress-legend:visible').count(), 0);
        for (let question = 2; question <= 6; question++) {
            await page.locator('#crlaQuestionNextBtn').click();
            assert.equal(await page.locator('#counter').textContent(), `Story Comprehension ${question}/6`);
        }
        assert.equal(completed.recording, false);
        assert.equal(completed.allTracksStopped, true);
        assert.equal(completed.sockets, failure ? 2 : 1, 'Completion must not open a replacement speech connection');
        if (name === 'skip_pending_final') assert.deepEqual(evaluated, ['partial', 'remaining']);
        if (name === 'skip_repeated') assert.equal(completed.finishRequests, 1, 'Repeated Skip cannot flush the same stream twice');
        assert.deepEqual(errors, []);
        console.log('PASS ' + sample.official.period + ': ' + sample.story.title + ' / ' + name);
    } finally { await context.close(); }
}

(async () => {
    const browser = await chromium.launch({channel: 'chrome', headless: true});
    let checked = 0;
    try {
        for (const sample of fixture.cases) {
            for (const name of ['automatic', 'ending_miscue', 'skip', 'skip_pending_final', 'skip_repeated', 'automatic_failure', 'skip_failure']) {
                await scenario(browser, sample, name); checked++;
            }
        }
        console.log('PASS: ' + checked + ' story streaming/comprehension scenarios across all CRLA phases.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
