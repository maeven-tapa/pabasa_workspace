// Local Chrome verification of production read-aloud functions. The API is
// mocked with a repository MP3; no accounts, API credits, or recordings needed.
// Set CRLA_PLAYWRIGHT_PATH to an installed playwright-core directory if needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root,
  'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
const start = source.indexOf('        async function readAssessmentTextAloud(');
const end = source.indexOf('        btnToggleMic?.addEventListener(', start);
assert.ok(start >= 0 && end > start);
const functions = source.slice(start, end);
const comprehensionAudioState = source.slice(source.indexOf('        let crlaQuestionNarrating = false;'),
  source.indexOf('        function syncCRLAQuestionButtons()'));
const timerState = source.slice(source.indexOf('let storyReadingTimerId = null;'),
  source.indexOf('let liveServerTimeOffsetMs'));
const timerFunctions = source.slice(source.indexOf('function clearStoryReadingTimer()'),
  source.indexOf('function startStoryReadingCountdown()'));
const audio = fs.readFileSync(path.join(root,
  'pabasa_site/pabasa_app/static/pabasa_app/crla/words/Pito.mp3')).toString('base64');
const origin = 'http://localhost:9876';

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const requests = [], unexpected = [], errors = [];
    let responseMode = 'audio', heldRoute;
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) return route.abort();
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body:
        '<button id="read">Read Aloud</button><button id="other">Question</button>' +
        '<div id="word"><span class="is-current">dito</span></div><p id="status"></p>'});
      if (url.pathname === '/api/reading/read-aloud/') {
        requests.push(route.request());
        if (responseMode === 'hold') { heldRoute = route; return; }
        if (responseMode === 'error') return route.fulfill({status: 502,
          json: {success: false, error: 'ElevenLabs TTS HTTP 429: Please try again later.'}});
        return route.fulfill({json: {success: true, audio_content: audio, mime_type: 'audio/mpeg',
          tts_provider: 'elevenlabs', voice_id: 'Xb7hH8MSUJpSbSDYk0k2'}});
      }
      if (url.pathname !== '/favicon.ico') unexpected.push(url.pathname);
      return route.fulfill({body: ''});
    });
    await page.goto(origin);
    await page.addScriptTag({content: `
      let isCrla = true, isTemplateActivity = false, mode = 'word';
      let currentAssessmentBranch = 'words', currentMaterialLanguage = 'Filipino';
      let readAloudAudio = null, readAloudAudioUrl = '', isReadAloudLoading = false;
      let readAloudController = null, readAloudButton = null, readAloudButtonHtml = '';
      ${comprehensionAudioState}
      const crlaQuestionStartReadingBtn = null;
      let pendingSpeech = false, nextText = 'Pito';
      let liveSessionPaused = false, liveSessionEnded = false, liveSessionEndRedirecting = false;
      let isFinalizingReading = false, isSendingChunk = false, pendingAudioChunk = null;
      let crlaSpeechFailure = false, crlaLiveSpeech = null;
      const storyReadingTimer = null, storyReadingTimerProgress = {style: {}};
      const storyReadingTimeUpOverlay = null, stopReading = () => {};
      ${timerState}
      ${timerFunctions}
      const readingWord = document.getElementById('word');
      const isSpeechResponsePending = () => pendingSpeech;
      const getCsrfToken = () => 'local-test-csrf';
      const setSpeechStatus = (title, detail) => document.getElementById('status').textContent = title + ' ' + detail;
      ${functions}
      document.getElementById('read').onclick = () => readAssessmentTextAloud(nextText, document.getElementById('read'));
      window.fixture = {
        set(options) { stopReadAloud(); ({mode, currentAssessmentBranch, nextText, isCrla, pendingSpeech} =
          {mode: 'word', currentAssessmentBranch: 'words', nextText: 'Pito', isCrla: true, pendingSpeech: false, ...options});
          clearStoryReadingTimer();
          if (currentAssessmentBranch === 'story_reading') startStoryReadingTimer();
        },
        stop: stopReadAloud,
        timer: () => ({elapsed: storyReadingElapsedMs(), paused: storyReadingTimerPausedAt !== null,
          visual: storyReadingTimerProgress.style.strokeDashoffset}),
        state: () => ({loading: isReadAloudLoading, playing: Boolean(readAloudAudio && !readAloudAudio.paused), url: readAloudAudioUrl})
      };`});

    for (const [stage, mode, text, expected] of [
      ['words', 'word', 'Pito', 'Pito'],
      ['rhymes', 'word', 'pito — dito', 'dito'],
      ['sentences', 'sentence', 'Naglalaba si tatay sa palanggana.', 'Naglalaba si tatay sa palanggana.'],
      ['story_reading', 'paragraph', 'May pagong at kuneho.', 'May pagong at kuneho.'],
      ['story_comprehension', 'paragraph', 'Sino ang nanalo?', 'Sino ang nanalo?'],
    ]) {
      await page.evaluate(options => window.fixture.set(options), {mode, currentAssessmentBranch: stage, nextText: text});
      await page.locator('#read').click();
      await page.waitForFunction(() => window.fixture.state().playing);
      const request = requests.at(-1), body = request.postDataBuffer().toString();
      assert.match(body, /name="tts_profile"\r\n\r\ncrla/);
      assert.ok(body.includes('name="target_text"\r\n\r\n' + expected + '\r\n'), stage);
      assert.equal(request.headers()['x-csrftoken'], 'local-test-csrf');
      assert.ok(await page.evaluate(() => window.fixture.state().url.startsWith('blob:')));
      await page.locator('#read').click();
      assert.deepEqual(await page.evaluate(() => window.fixture.state()), {loading: false, playing: false, url: ''});
      assert.equal(await page.locator('#read').innerText(), 'Read Aloud');
    }

    // Natural end restores the button and releases the object URL.
    await page.evaluate(() => window.fixture.set({}));
    await page.locator('#read').click();
    await page.waitForFunction(() => window.fixture.state().playing);
    await page.waitForFunction(() => !window.fixture.state().playing && !window.fixture.state().url);
    assert.equal(await page.locator('#read').innerText(), 'Read Aloud');

    // The actual story timer freezes during both provider loading and audio,
    // resumes at natural end/manual stop, and is released on provider errors.
    await page.evaluate(() => window.fixture.set({mode: 'paragraph', currentAssessmentBranch: 'story_reading'}));
    responseMode = 'hold';
    await page.locator('#read').click();
    await page.waitForFunction(() => window.fixture.state().loading);
    const frozen = await page.evaluate(() => window.fixture.timer());
    assert.equal(frozen.paused, true);
    await page.waitForTimeout(300);
    assert.deepEqual(await page.evaluate(() => window.fixture.timer()), frozen);
    await heldRoute.fulfill({json: {success: true, audio_content: audio, mime_type: 'audio/mpeg'}});
    await page.waitForFunction(() => window.fixture.state().playing);
    await page.waitForTimeout(300);
    assert.deepEqual(await page.evaluate(() => window.fixture.timer()), frozen);
    await page.waitForFunction(() => !window.fixture.state().playing && !window.fixture.state().url);
    assert.equal((await page.evaluate(() => window.fixture.timer())).paused, false);
    await page.waitForTimeout(100);
    assert.ok((await page.evaluate(() => window.fixture.timer())).elapsed > frozen.elapsed);
    responseMode = 'audio';
    await page.locator('#read').click();
    await page.waitForFunction(() => window.fixture.state().playing);
    assert.equal((await page.evaluate(() => window.fixture.timer())).paused, true);
    await page.locator('#read').click();
    assert.equal((await page.evaluate(() => window.fixture.timer())).paused, false);

    responseMode = 'error';
    await page.locator('#read').click();
    await page.waitForFunction(() => document.getElementById('status').textContent.includes('ElevenLabs TTS HTTP 429'));
    assert.equal(await page.locator('#read').isEnabled(), true);
    assert.equal(await page.locator('#read').innerText(), 'Read Aloud');
    assert.equal(await page.evaluate(() => window.fixture.state().url), '');
    assert.equal((await page.evaluate(() => window.fixture.timer())).paused, false);

    // A stopped request cannot start playback when its response arrives late.
    responseMode = 'hold';
    await page.locator('#read').click();
    await page.waitForFunction(() => window.fixture.state().loading);
    await page.waitForFunction(() => document.getElementById('read').disabled);
    assert.ok(heldRoute);
    await page.evaluate(() => window.fixture.stop());
    assert.equal((await page.evaluate(() => window.fixture.timer())).paused, false);
    await heldRoute.fulfill({json: {success: true, audio_content: audio, mime_type: 'audio/mpeg'}}).catch(() => {});
    assert.deepEqual(await page.evaluate(() => window.fixture.state()), {loading: false, playing: false, url: ''});

    // Pending recording analysis blocks read aloud; regular assessments keep their profile.
    const count = requests.length;
    await page.evaluate(() => window.fixture.set({pendingSpeech: true}));
    await page.locator('#read').click();
    assert.equal(requests.length, count);
    responseMode = 'audio';
    await page.evaluate(() => window.fixture.set({isCrla: false}));
    await page.locator('#read').click();
    await page.waitForFunction(() => window.fixture.state().playing);
    assert.match(requests.at(-1).postDataBuffer().toString(), /name="tts_profile"\r\n\r\nassessment/);
    await page.evaluate(() => window.fixture.stop());
    assert.deepEqual(unexpected, []);
    assert.deepEqual(errors, []);
    console.log('CRLA browser TTS passed: 5 stages, real playback, story timer pause/resume, stop/end, errors, cancellation, speech lock, regular profile.');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
