// Local Chrome regression of the rendered CRLA page and complete reader.
// Synthetic recognition/answer grading; no accounts, recordings, or provider calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os, sys, json, django
sys.path.insert(0, 'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()
from django.template.loader import render_to_string
from pabasa_app.management.commands.seed_official_crla_assessments import OFFICIAL_CRLA_CONTENT
print(json.dumps({'specs': list(OFFICIAL_CRLA_CONTENT.values()), 'html': render_to_string(
    'pabasa_app/reading_para_page.html', {'crla_official_assessment_id': 1, 'is_admin_preview': True})}))
`], {cwd: root, encoding: 'utf8', env: {...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:',
  DJANGO_ENV: 'development', PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const html = fixture.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '')
  .replace(/<link\b[^>]*>/g, tag => /href=["']\/static\//.test(tag) ? tag : '');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app');
// Mock the provider response with valid audio bytes; production must use TTS,
// and must never request any repository MP3 as a narration fallback.
const ttsAudio = fs.readFileSync(path.join(staticRoot, 'crla/words/Pito.mp3')).toString('base64');
const reader = fs.readFileSync(path.join(staticRoot, 'js/assessment_reader.js'), 'utf8')
  .replace('        loadItems();', `        window.__comprehensionTest = {
    render: renderCRLAQuestion,
    pause() { liveSessionPaused = true; showLiveSessionPaused(); },
    resume() { liveSessionPaused = false; hideLiveSessionPaused(); },
    state() { return {index: currentStoryQuestionIndex, stage: currentStoryState,
      answers: currentStoryAnswers, results: currentStoryResults, narrating: crlaQuestionNarrating,
      processing: crlaSpokenAttemptProcessing}; }
  };
        loadItems();`);
const origin = 'http://localhost:9876';
const start = '#crlaQuestionStartReadingBtn', next = '#crlaQuestionNextBtn';

async function open(browser, spec, storyNumber, options = {}) {
  const context = await browser.newContext({viewport: options.viewport || (options.mobile ? {width: 390, height: 844} : {width: 1366, height: 768})});
  const page = await context.newPage(), errors = [], requests = [], audioRequests = [], ttsRequests = [], held = [];
  const ttsResponse = {success: true, audio_content: ttsAudio, mime_type: 'audio/mpeg', tts_provider: 'elevenlabs'};
  page.setDefaultTimeout(8000);
  page.on('pageerror', error => errors.push(error.message));
  const story = spec.passages[storyNumber - 1];
  const official = {...spec, id: 1, assessment_kind: 'crla', language: 'Filipino', official_title: spec.title, official_code: spec.code};
  await context.addInitScript(({official, story, storyNumber, options}) => {
    window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
    window.__PABASA_ADMIN_PREVIEW__ = true;
    window.PABASA_USER_ID = '99'; window.PABASA_USER_ROLE = 'admin';
    sessionStorage.setItem('pabasa_admin_crla_preview:narration-test', JSON.stringify({stage: 'story_comprehension',
      branch: 'story', material_id: '1', selected_story: story.title, story_number: storyNumber,
      crla_question_index: options.index || 0, story_read_percent: 90}));
    const audit = window.audit = {audio: [], recognition: [], overlap: 0};
    const nativeAudio = window.Audio;
    if (options.real) {
      window.Audio = function(url) {
        const audio = new nativeAudio(url);
        audio.addEventListener('ended', () => { audio.finished = true; });
        audit.audio.push(audio); return audio;
      };
    } else {
      window.Audio = class {
        constructor(url) { this.src = url; this.paused = true; this.currentTime = 0; audit.audio.push(this); }
        play() {
          audit.overlap += audit.audio.filter(a => a !== this && !a.paused).length;
          if (options.reject) return Promise.reject(new DOMException('Autoplay blocked', 'NotAllowedError'));
          this.paused = false; this.savedEnd = this.onended; this.savedError = this.onerror;
          return Promise.resolve();
        }
        pause() { this.paused = true; }
        end() { this.paused = true; this.onended?.(); }
        fail() { this.onerror?.(); }
      };
      if (options.timeout || options.requestTimeout) {
        const schedule = window.setTimeout;
        window.setTimeout = (fn, ms, ...args) => schedule(fn,
          (options.timeout && ms === 20000) || (options.requestTimeout && ms === 65000) ? 80 : ms, ...args);
      }
    }
    window.SpeechRecognition = class {
      constructor() { audit.recognition.push(this); }
      start() { this.started = true; }
      stop() {}
      abort() { this.aborted = true; this.onend?.(); }
      answer(text) { this.onresult?.({results: [[{transcript: text}]]}); }
    };
  }, {official, story, storyNumber, options});
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname.startsWith('/dashboard/assessment/reading_ui/')) return route.fulfill({contentType: 'text/html', body: html});
    if (url.pathname.startsWith('/static/pabasa_app/')) {
      let file = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice('/static/pabasa_app/'.length)));
      if (!fs.existsSync(file)) file = file.replace(/\.(png|jpe?g)$/i, '.webp');
      if (file.startsWith(staticRoot + path.sep) && fs.existsSync(file) && fs.statSync(file).isFile()) {
        if (file.endsWith('.mp3')) audioRequests.push(file);
        return route.fulfill({body: fs.readFileSync(file), ...(file.endsWith('.mp3') ? {contentType: 'audio/mpeg'} : {})});
      }
    }
    if (url.pathname === '/api/reading/read-aloud/') {
      const body = route.request().postDataBuffer().toString();
      const field = name => body.match(new RegExp('name="' + name + '"\\r\\n\\r\\n([\\s\\S]*?)\\r\\n--'))?.[1];
      ttsRequests.push({text: field('target_text'), profile: field('tts_profile'), language: field('language')});
      requests.push({path: url.pathname});
      if (options.hold || options.requestTimeout) { held.push(route); return; }
      if (options.apiFailure) return route.fulfill({status: 502, json: {success: false, error: 'ElevenLabs unavailable'}});
      return route.fulfill({json: {...ttsResponse, ...(options.wrongProvider ? {tts_provider: 'google'} : {})}});
    }
    if (url.pathname.startsWith('/api/')) requests.push({path: url.pathname, body: route.request().postDataJSON()});
    if (url.pathname === '/api/admin/crla-preview/score/') {
      return route.fulfill({json: {success: true, preview_only: true, student_end_assessment_state: route.request().postDataJSON()}});
    }
    if (url.pathname === '/api/assessment/story-answer/check/') return route.fulfill({json: {success: true, is_correct: true}});
    return route.fulfill({contentType: 'application/json', body: '{}'});
  });
  await page.goto(origin + '/dashboard/assessment/reading_ui/para/?official_assessment_id=1&admin_preview=1&admin_preview_token=narration-test&crla_stage=story');
  await page.addScriptTag({content: reader});
  await page.waitForFunction(() => window.__comprehensionTest?.state().stage === 'story_comprehension');
  if (!options.hold && !options.apiFailure && !options.wrongProvider && !options.requestTimeout)
    await page.waitForFunction(() => window.audit.audio.length > 0);
  return {context, page, errors, requests, audioRequests, ttsRequests, held, story,
    release: async index => held[index].fulfill({json: ttsResponse}).catch(() => {})};
}
async function locked(page) {
  assert.equal(await page.locator(start).isDisabled(), true);
  assert.equal(await page.locator(next).isDisabled(), true);
  assert.equal(await page.locator(start).evaluate(el => el.classList.contains('is-answer-ready')), false);
  for (const selector of [start, next]) {
    assert.deepEqual(await page.locator(selector).evaluate(el => {
      const style = getComputedStyle(el);
      return [style.backgroundColor, style.color, style.animationName, style.boxShadow];
    }), ['rgb(209, 213, 219)', 'rgb(75, 85, 99)', 'none', 'none']);
  }
}
async function ready(page) {
  await page.waitForFunction(() => !document.getElementById('crlaQuestionStartReadingBtn').disabled
    && !document.getElementById('crlaQuestionNextBtn').disabled);
  assert.equal(await page.locator(start).evaluate(el => el.classList.contains('is-answer-ready')), true);
  assert.equal(await page.locator(start).evaluate(el => getComputedStyle(el).animationName), 'crla-answer-pulse');
  assert.equal(await page.locator(start).evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(21, 128, 61)');
  assert.notEqual(await page.locator(start).evaluate(el => getComputedStyle(el).boxShadow), 'none');
  assert.equal(await page.locator(next).evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(250, 204, 21)');
}
async function fitsViewport(page, label) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const layout = await page.evaluate(() => {
    const root = document.documentElement;
    const stage = document.querySelector('.reader-stage');
    const stageTop = stage.getBoundingClientRect().top;
    const visible = ['.reader-top', '#counter', '#assessmentHelpBtn', '#btnToggleMic', '#btnTestMic', '#pauseBtn',
      '#crlaQuestionTitle', '#crlaQuestionText', '#crlaAnswerInput',
      '#crlaAnswerFeedback', '#crlaQuestionStartReadingBtn', '#crlaQuestionNextBtn'];
    return {width: innerWidth, height: innerHeight,
      headerHeight: document.querySelector('.reader-top').getBoundingClientRect().height,
      cardHeight: document.querySelector('.reader-card').getBoundingClientRect().height,
      questionRows: getComputedStyle(document.querySelector('#crlaQuestionPanel .story-question-shell')).gridTemplateRows,
      pageWidth: Math.max(root.scrollWidth, document.body.scrollWidth),
      pageHeight: Math.max(root.scrollHeight, document.body.scrollHeight),
      elements: visible.map(selector => {
        const el = document.querySelector(selector), rect = el.getBoundingClientRect();
        return {selector, visible: getComputedStyle(el).display !== 'none',
          left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
          width: rect.width, height: rect.height, clipped: (selector === '#crlaQuestionText'
            || selector === '#crlaAnswerInput')
            && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1),
          inHeader: Boolean(el.closest('.reader-top')),
          reachable: rect.top + stage.scrollTop >= stageTop - 1
            && rect.bottom + stage.scrollTop <= stageTop + stage.scrollHeight + 1};
      })};
  });
  assert.ok(layout.pageWidth <= layout.width + 1 && layout.pageHeight <= layout.height + 1,
    label + ' page overflow: ' + JSON.stringify(layout));
  for (const el of layout.elements.filter(el => el.visible)) {
    // The header stays in view; smaller screens and long answers may scroll
    // inside the main assessment area without clipping their text.
    assert.ok(el.width > 0 && el.height > 0 && el.left >= -1
      && el.right <= layout.width + 1 && !el.clipped
      && (el.inHeader ? el.top >= -1 && el.bottom <= layout.height + 1 : el.reachable),
      label + ' hidden or clipped content: ' + JSON.stringify(layout));
  }
}
async function close(h) {
  assert.deepEqual(h.errors, []);
  assert.equal(await h.page.evaluate(() => audit.overlap || 0), 0);
  assert.equal(h.audioRequests.length, 0, 'Never request a local narration MP3');
  assert.ok(h.ttsRequests.length > 0);
  assert.ok(h.ttsRequests.every(r => r.profile === 'crla' && r.language === 'Filipino'));
  await h.context.close();
}
(async () => {
  // Real-playback cases emulate entering comprehension after a student gesture.
  // Autoplay rejection itself is tested separately with a deterministic failure.
  const browser = await chromium.launch({channel: 'chrome', headless: true,
    args: ['--autoplay-policy=no-user-gesture-required']});
  try {
    // All three official assessment variants can swap Story 1/2 order.
    for (const spec of process.env.CRLA_LAYOUT_ONLY ? [] : fixture.specs) for (const storyNumber of [1, 2]) {
      const h = await open(browser, spec, storyNumber, {mobile: storyNumber === 2});
      const {page} = h;
      const questions = spec.story_qas.filter(q => q.story_title === h.story.title);
      assert.equal(questions.length, 6);
      assert.deepEqual((await page.locator('#crlaQuestionPanel .story-question-nav button').allTextContents()).map(text => text.trim()), ['🎙 Sumagot', 'Susunod']);
      assert.equal(await page.locator(next + ' .bi-arrow-right').getAttribute('aria-hidden'), 'true');
      assert.equal(await page.locator('#crlaQuestionReadAloudBtn').count(), 0);
      assert.equal(await page.locator(start).getAttribute('aria-label'), 'Sumagot');
      assert.equal(await page.locator(next).getAttribute('aria-label'), 'Susunod');
      assert.equal(await page.locator('#crlaAnswerInput').count(), 1, 'Retain the transcript target');
      assert.equal(await page.locator('#crlaAnswerInput').isVisible(), false, 'Transcript stays non-visible');
      assert.equal(await page.locator('#crlaQuestionPanel .story-answer-card, #crlaQuestionPanel .story-answer-label, .comprehension-audio-art').count(), 0,
        'The spoken-answer card and decorations are removed');
      assert.equal(await page.locator('#crlaAnswerFeedback').evaluate(el => el.parentElement.className), 'story-question-shell',
        'Status messages remain outside the removed card');
      for (let i = 0; i < 6; i++) {
        await page.waitForFunction(n => audit.audio.length === n, i + 1);
        await locked(page);
        await fitsViewport(page, `${spec.code} Story ${storyNumber} question ${i + 1} loading`);
        if (process.env.CRLA_PREVIEW_DIR && spec === fixture.specs[0] && i === 0) {
          fs.mkdirSync(process.env.CRLA_PREVIEW_DIR, {recursive: true});
          await page.screenshot({path: path.join(process.env.CRLA_PREVIEW_DIR, `comprehension-disabled-story-${storyNumber}.png`)});
        }
        assert.equal(await page.locator('#crlaQuestionText').textContent(), questions[i].question);
        assert.equal(h.ttsRequests.length, i + 1, 'Exactly one TTS request per loaded question');
        assert.equal(h.ttsRequests[i].text, questions[i].question);
        assert.ok(await page.evaluate(() => audit.audio.at(-1).src.startsWith('blob:')));
        // Even synthetic events cannot bypass the narration gate.
        await page.evaluate(() => {
          for (let n = 0; n < 4; n++) for (const id of ['crlaQuestionStartReadingBtn', 'crlaQuestionNextBtn'])
            document.getElementById(id).dispatchEvent(new Event('click'));
        });
        assert.equal(await page.evaluate(() => audit.recognition.length), i);
        assert.equal(await page.evaluate(() => __comprehensionTest.state().index), i);
        await page.evaluate(() => audit.audio.at(-1).end());
        await ready(page);
        await fitsViewport(page, `${spec.code} Story ${storyNumber} question ${i + 1} ready`);
        if (process.env.CRLA_PREVIEW_DIR && spec === fixture.specs[0] && i === 0)
          await page.screenshot({path: path.join(process.env.CRLA_PREVIEW_DIR, `comprehension-ready-story-${storyNumber}.png`)});
        // A pulsing button intentionally moves; click its visible center.
        await page.locator(start).evaluate(el => el.scrollIntoView({block: 'nearest'}));
        const bounds = await page.locator(start).boundingBox();
        await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
        assert.equal(await page.locator(start).evaluate(el => el.classList.contains('is-answer-ready')), false);
        assert.equal(await page.locator(start).isDisabled(), true);
        assert.equal(await page.evaluate(() => audit.recognition.at(-1).lang), 'fil-PH');
        await page.evaluate(() => audit.recognition.at(-1).answer('Sagot'));
        assert.equal(await page.locator('#crlaAnswerInput').isVisible(), false, 'Recognized text does not reappear');
      }
      await page.waitForFunction(() => __comprehensionTest.state().stage === 'learner_experience');
      assert.deepEqual(await page.evaluate(() => __comprehensionTest.state().results), Array(6).fill(true));
      assert.equal(h.requests.filter(r => r.path.includes('story-answer/check')).length, 6);
      assert.ok(h.requests.some(r => r.body?.comprehension_correct === 6 && r.body?.total_questions === 6));
      await page.locator('.rating-option[data-rating="5"]').click();
      await page.locator('#learnerExperienceContinue').click();
      await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-complete'));
      assert.ok(h.requests.some(r => r.body?.stage === 'completed' && r.body?.learner_experience_rating === 5));
      await close(h);
      console.log(`PASS: ${spec.code} Story ${storyNumber}, six narrated/answered questions`);
    }
    // Resize in place, including landscape, while narration/recording is active.
    for (const storyNumber of [1, 2]) {
      const responsive = await open(browser, fixture.specs[0], storyNumber);
      for (const [width, height] of [[1900, 936], [1366, 600], [1024, 768], [768, 1024],
        [390, 844], [320, 568], [320, 480], [844, 390], [667, 375], [568, 320]]) {
        await responsive.page.setViewportSize({width, height});
        const typography = await responsive.page.evaluate(() => ({
          title: parseFloat(getComputedStyle(document.getElementById('crlaQuestionTitle')).fontSize),
          question: parseFloat(getComputedStyle(document.getElementById('crlaQuestionText')).fontSize),
        }));
        assert(typography.question > typography.title, 'Question is larger than the story title');
        if (width >= 992) {
          assert(typography.title >= 30 && typography.title <= 34, 'Desktop title size');
          assert(typography.question >= 38 && typography.question <= 44, 'Desktop question size');
        }
        for (let index = 0; index < 6; index++) {
          if (index) {
            await responsive.page.evaluate(() => audit.audio.at(-1).end());
            await responsive.page.locator(next).click();
            await responsive.page.waitForFunction(n => __comprehensionTest.state().index === n && audit.audio.at(-1).paused === false, index);
          }
          if (process.env.CRLA_PREVIEW_DIR && width === 568 && index === 0)
            await responsive.page.screenshot({path: path.join(process.env.CRLA_PREVIEW_DIR, `comprehension-landscape-story-${storyNumber}.png`)});
          await fitsViewport(responsive.page, `Story ${storyNumber}, question ${index + 1}, ${width}x${height}`);
        }
        await responsive.page.evaluate(() => audit.audio.at(-1).end()); await ready(responsive.page);
        await responsive.page.evaluate(() => {
          document.getElementById('crlaAnswerInput').textContent = 'Isang mahabang sagot ng mag-aaral. '.repeat(80);
          document.getElementById('crlaAnswerInput').classList.remove('is-empty');
          const feedback = document.getElementById('crlaAnswerFeedback');
          feedback.textContent = 'Hindi ma-play ang tanong. Maaari ka pa ring sumagot o magpatuloy.';
          feedback.classList.remove('d-none');
        });
        await fitsViewport(responsive.page, `Long answer and feedback, Story ${storyNumber}, ${width}x${height}`);
        // Restart this isolated preview at the first question for the next size.
        await responsive.page.evaluate(() => {
          sessionStorage.removeItem('pabasa_admin_crla_preview:narration-test');
        });
        await responsive.page.reload();
        await responsive.page.addScriptTag({content: reader});
        await responsive.page.waitForFunction(() => audit.audio.length > 0);
      }
      await close(responsive);
    }
    console.log('PASS: viewport fit for all 12 questions at 10 desktop/tablet/phone sizes, including long answers and feedback.');
    if (process.env.CRLA_LAYOUT_ONLY) return;
    const h = await open(browser, fixture.specs[0], 1);
    await h.page.evaluate(() => audit.audio.at(-1).end()); await ready(h.page);
    // Next remains a skip; repeated events cannot skip the new narration.
    await h.page.evaluate(() => { for (let n = 0; n < 10; n++) document.getElementById('crlaQuestionNextBtn').dispatchEvent(new Event('click')); });
    await h.page.waitForFunction(() => audit.audio.length === 2); await locked(h.page);
    assert.deepEqual(await h.page.evaluate(() => __comprehensionTest.state().results), Array(6).fill(null));
    await h.page.evaluate(() => { audit.audio[0].savedEnd(); audit.audio[0].savedError(); }); await locked(h.page);
    await h.page.evaluate(() => __comprehensionTest.render());
    await h.page.waitForFunction(() => audit.audio.length === 3);
    await h.page.evaluate(() => audit.audio[1].savedEnd()); await locked(h.page);
    assert.equal(await h.page.evaluate(() => audit.audio[1].paused), true);
    await h.page.evaluate(() => audit.audio.at(-1).fail()); await ready(h.page);
    await h.page.evaluate(() => __comprehensionTest.pause()); await locked(h.page);
    const completedAudioCount = await h.page.evaluate(() => audit.audio.length);
    await h.page.evaluate(() => __comprehensionTest.resume()); await ready(h.page);
    assert.equal(await h.page.evaluate(() => audit.audio.length), completedAudioCount);
    await h.page.evaluate(() => __comprehensionTest.render()); await locked(h.page);
    await h.page.waitForFunction(() => audit.audio.length === 4);
    await h.page.evaluate(() => __comprehensionTest.pause()); await locked(h.page);
    await h.page.evaluate(() => __comprehensionTest.resume()); await locked(h.page);
    await h.page.waitForFunction(() => audit.audio.length === 5);
    await h.page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
    assert.equal(await h.page.evaluate(() => audit.audio.at(-1).paused), true);
    await h.page.evaluate(() => audit.audio.at(-1).savedEnd()); await locked(h.page);
    // Restoring a cached page narrates again; skipping a recording ignores its late result.
    await h.page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true})));
    await h.page.waitForFunction(() => audit.audio.length === 6);
    await locked(h.page);
    await h.page.evaluate(() => audit.audio.at(-1).end()); await ready(h.page);
    await h.page.evaluate(() => document.getElementById('crlaQuestionStartReadingBtn').click());
    await h.page.locator(next).click(); await locked(h.page);
    await h.page.evaluate(() => audit.recognition.at(-1).answer('late answer'));
    assert.deepEqual(await h.page.evaluate(() => __comprehensionTest.state().results), Array(6).fill(null));
    await close(h);
    for (const options of [{reject: true}, {timeout: true}, {apiFailure: true}, {wrongProvider: true}, {requestTimeout: true}]) {
      const failure = await open(browser, fixture.specs[0], 2, options);
      await ready(failure.page);
      assert.ok(await failure.page.locator('#crlaAnswerFeedback').isVisible());
      await close(failure);
    }
    // A canceled/late synthesis response cannot play or unlock a newer question.
    const delayed = await open(browser, fixture.specs[0], 1, {hold: true});
    await locked(delayed.page);
    await delayed.page.evaluate(() => __comprehensionTest.render());
    await delayed.page.waitForTimeout(30);
    assert.equal(delayed.held.length, 2);
    await delayed.release(0); await locked(delayed.page);
    assert.equal(await delayed.page.evaluate(() => audit.audio.length), 0);
    await delayed.release(1);
    await delayed.page.waitForFunction(() => audit.audio.length === 1);
    await locked(delayed.page);
    await delayed.page.evaluate(() => audit.audio.at(-1).end()); await ready(delayed.page);
    await close(delayed);
    // Decode and play TTS response blobs in Chrome for every question.
    for (const storyNumber of [1, 2]) {
      const real = await open(browser, fixture.specs[0], storyNumber, {real: true});
      for (let i = 0; i < 6; i++) {
        await real.page.waitForFunction(n => audit.audio.length === n, i + 1);
        await locked(real.page);
        try {
          await real.page.waitForFunction(() => audit.audio.at(-1).finished, null, {timeout: 15000});
        } catch (error) {
          console.error(await real.page.evaluate(() => {
            const a = audit.audio.at(-1);
            return {src: a.src, duration: a.duration, currentTime: a.currentTime, paused: a.paused,
              readyState: a.readyState, error: a.error?.message, feedback: document.getElementById('crlaAnswerFeedback').textContent};
          }));
          throw error;
        }
        await ready(real.page);
        if (i < 5) await real.page.locator(next).click();
      }
      assert.equal(real.ttsRequests.length, 6);
      await close(real);
    }
    console.log('PASS: ElevenLabs-only narration for all 12 questions and all 3 variants; TTS blob playback, request/playback locks, pulse, STT/grades/completion, failures and cancellation; no local MP3 requests.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
