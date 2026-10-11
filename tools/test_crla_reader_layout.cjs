// Run with node tools/test_crla_reader_layout.cjs and installed Chrome/Django.
// Set CRLA_PLAYWRIGHT_PATH to a bundled playwright-core path when needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '../pabasa_site');
const source = fs.readFileSync(process.env.CRLA_READER_SOURCE_PATH ||
  path.join(root, 'pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
// Expose the actual speech entry point only in this test to hold a provider
// request across the teacher's End Session action without microphone hardware.
const testSource = source.replace('        loadItems();',
  `        window.__readerTest = {sendAudioChunk, currentSpeechContext, handleSpeechResult, strictStoryEvidence,
    setFixtureHearing({speaking = false, pending = false, buffered = false} = {}) {
      isRecording = speaking || pending || buffered; recognitionActive = isRecording;
      isSendingChunk = pending; hasHeardSinceLastChunk = buffered; speechFrameCount = speaking ? 3 : 0;
      shell.classList.toggle('is-hearing', speaking); renderOfficialCrlaStatus();
    }};
        loadItems();`);
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || 'python', ['-c', `
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()
from django.template.loader import render_to_string
print(json.dumps({mode: render_to_string('pabasa_app/reading_' + mode + '_page.html',
    {'crla_official_assessment_id': 1, 'crla_official_assessment_data': {'assessment_kind': 'crla'}}) for mode in ['word', 'sentence', 'para']}))
`], {cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
// Load the complete reader separately after setting the server recovery payload.
const templates = Object.fromEntries(Object.entries(JSON.parse(rendered.stdout)).map(([mode, html]) =>
  [mode, html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '')
    .replace(/<link\b[^>]*>/g, '')
    .replace('</head>', '<link rel="stylesheet" href="/static/pabasa_app/vendor/bootstrap-icons/bootstrap-icons.css"></head>')]));
const official = {
  id: 1, assessment_kind: 'crla', official_title: 'CRLA Pre-Test', official_code: 'CRLA-BOSY',
  language: 'Filipino', words: Array(10).fill('Pito'),
  rhyme_pairs: Array(10).fill({word_a: 'pito', word_b: 'dito'}),
  sentences: Array(5).fill('May pito si Ana.'),
  passages: [{title: 'Ang Pito', content: 'May pito si Ana. Narinig ni Ben ang pito.'}],
};
const origin = 'http://localhost:9876';
const previewDir = process.env.CRLA_PREVIEW_DIR;
if (previewDir) fs.mkdirSync(previewDir, {recursive: true});
const modes = {words: 'word', rhymes: 'word', sentences: 'sentence', story_reading: 'para'};
function readerUrl(mode, branch) {
  return `${origin}/dashboard/assessment/reading_ui/${mode}/?official_assessment_id=1` +
    `&live=1&live_session_id=layout-test&countdown=0&live_recovery=1&crla_stage=${branch}`;
}
async function snapshot(page) {
  return page.evaluate(() => {
    const shell = document.querySelector('.reader-shell');
    const card = document.querySelector('.reader-card');
    const word = document.getElementById('readingWord');
    const style = getComputedStyle(word);
    return {
      shellModes: [...shell.classList].filter(name => /^reader-(word|sentence|paragraph|vowel|phrase)$/.test(name)),
      cardModes: [...card.classList].filter(name => name.startsWith('content-')),
      fontSize: style.fontSize, lineHeight: style.lineHeight, padding: style.padding,
      background: style.backgroundColor, border: style.borderWidth,
      text: word.textContent, counter: document.getElementById('counter').textContent,
    };
  });
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let checked = 0;
  try {
    const selectedWidths = process.env.CRLA_VIEWPORT_WIDTHS?.split(',').map(Number);
    for (const viewport of [{width: 1366, height: 768}, {width: 1024, height: 768},
      {width: 768, height: 1024}, {width: 844, height: 390}, {width: 390, height: 844}, {width: 320, height: 568}]
      .filter(viewport => !selectedWidths || selectedWidths.includes(viewport.width))) {
      for (const debug of [1366, 390].includes(viewport.width) ? [false, true] : [false]) {
        for (const [branch, mode] of Object.entries(modes)) {
          const context = await browser.newContext({viewport});
          const page = await context.newPage();
          const errors = [];
          page.on('pageerror', error => errors.push(error.message));
          const state = {stage: branch, branch: branch === 'story_reading' ? 'sentences' : branch,
            crla_question_index: 1, material_id: '1',
            ...(branch === 'story_reading' ? {selected_story: 'Ang Pito', story_segment_index: 0,
              story_reading_started_at: new Date().toISOString()} : {})};
          let paused = true;
          let ended = false;
          let heldSpeechRoute, signalSpeechStarted;
          let testingSpeechRetry = false;
          const retriedAudio = [];
          const speechStarted = new Promise(resolve => { signalSpeechStarted = resolve; });
          let signalStrictSnapshot;
          const strictSnapshot = new Promise(resolve => { signalStrictSnapshot = resolve; });
          // Resume through a mismatched route, including the paragraph URL in the report.
          const resumeMode = mode === 'para' ? 'word' : 'para';
          const resumedUrl = readerUrl(resumeMode, branch);
          await context.addInitScript(({official, state, debug}) => {
            window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
            window.__PABASA_STUDENT_END_STATE__ = state;
            window.PABASA_USER_ID = '1';
            window.PABASA_USER_ROLE = 'student';
            localStorage.setItem('pabasaShowSpeechDebugPanel', String(debug));
          }, {official, state, debug});
          await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== origin) return route.abort();
            if (url.pathname.startsWith('/static/pabasa_app/')) {
              const staticRoot = path.join(root, 'pabasa_app/static/pabasa_app');
              const asset = path.resolve(staticRoot, url.pathname.slice('/static/pabasa_app/'.length));
              if (asset.startsWith(staticRoot + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()) {
                const types = {'.css': 'text/css', '.woff2': 'font/woff2', '.woff': 'font/woff',
                  '.ttf': 'font/ttf', '.png': 'image/png', '.webp': 'image/webp'};
                return route.fulfill({body: fs.readFileSync(asset), contentType: types[path.extname(asset)] || 'application/octet-stream'});
              }
            }
            if (url.pathname === '/api/reading/transcribe/') {
              if (testingSpeechRetry) {
                retriedAudio.push(route.request().postDataBuffer().toString());
                if (retriedAudio.length === 1) {
                  return route.fulfill({status: 500, contentType: 'text/html', body: '<html>Internal server error</html>'});
                }
                if (branch === 'story_reading') await new Promise(resolve => setTimeout(resolve, 900));
                return route.fulfill({json: {success: true, language_code: 'fil-PH', transcript: '',
                  correct_word_count: 0, word_results: [], current_syllable_index: 0}});
              }
              heldSpeechRoute = route;
              signalSpeechStarted();
              return;
            }
            if (url.pathname.startsWith('/api/')) {
              if (route.request().method() === 'POST') {
                const payload = route.request().postDataJSON();
                if (payload?.recovery_state?.stage === 'story_comprehension') {
                  signalStrictSnapshot(payload.recovery_state);
                }
              }
              return route.fulfill({json: {success: true, state, session: {
                id: 'layout-test', status: ended ? 'ended' : paused ? 'paused' : 'started', reader_url: resumedUrl,
                student_states: {'1': {status: 'in_progress', participation_status: 'active',
                  recovery_state: state}},
              }}});
            }
            if (url.pathname.startsWith('/dashboard/assessment/reading_ui/')) {
              const templateMode = url.pathname.split('/').filter(Boolean).at(-1);
              return route.fulfill({contentType: 'text/html', body: templates[templateMode]});
            }
            return route.fulfill({body: ''});
          });
          // The real init, loader, and poll handlers run on every navigation/refresh.
          page.on('domcontentloaded', () => page.addScriptTag({content: testSource}).catch(error => errors.push(error.message)));
          await page.goto(readerUrl(mode, branch));
          await page.waitForFunction(() => !document.getElementById('pauseOverlay').classList.contains('d-none'));
          const before = await snapshot(page);
          const expectedMode = mode === 'para' ? 'paragraph' : mode;
          assert.deepEqual(before.shellModes, [`reader-${expectedMode}`]);
          assert.deepEqual(before.cardModes, [`content-${expectedMode}`]);
          if (mode !== 'para') assert.ok(parseFloat(before.fontSize) >=
            (mode === 'sentence' && viewport.width <= 1024 ? 20 : 32), JSON.stringify(before));
          paused = false;
          await page.waitForURL(resumedUrl);
          await page.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
          assert.deepEqual(await snapshot(page), before, `${branch}, ${viewport.width}px, debug=${debug}: resume`);
          await page.reload();
          await page.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
          assert.deepEqual(await snapshot(page), before, `${branch}, ${viewport.width}px, debug=${debug}: refresh`);
          assert.equal(await page.title(), 'PABASA | CRLA');
          if (!debug && viewport.width <= 1024) {
            const size = await page.evaluate(() => ({width: document.documentElement.scrollWidth,
              height: document.documentElement.scrollHeight, viewportHeight: window.innerHeight}));
            assert.ok(size.width <= viewport.width && size.height <= size.viewportHeight + 1,
              `${branch}: reading screen fits without scrolling at ${viewport.width}px: ${JSON.stringify(size)}`);
          }
          const section = {words: 'Word', rhymes: 'Rhymes', sentences: 'Sentence', story_reading: 'Story'}[branch];
          const headerSection = branch === 'rhymes' ? 'Rhyme' : section;
          assert.equal(await page.locator('.reader-top .eyebrow').textContent(), `${headerSection} Reading Assessment`,
            `${branch}: heading follows the recovered section`);
          assert.equal(await page.locator('#readingHelperText').textContent(), `Read the ${section}`,
            `${branch}: reading instruction follows the recovered section`);
          if (viewport.width === 1366 && !debug) {
            await page.evaluate(() => window.__readerTest.setFixtureHearing({speaking: true, pending: true}));
            assert.equal(await page.locator('#readingHelperText').textContent(), 'Hearing you...');
            assert.ok(!await page.locator('.official-crla-status').evaluate(el => el.classList.contains('is-status-processing')));
            await page.evaluate(() => window.__readerTest.setFixtureHearing({pending: true}));
            assert.equal(await page.locator('#readingHelperText').textContent(), 'Processing...');
            await page.evaluate(() => window.__readerTest.setFixtureHearing({buffered: true}));
            assert.equal(await page.locator('#readingHelperText').textContent(), `Read the ${section}`);
            await page.evaluate(() => window.__readerTest.setFixtureHearing());
          }
          const layout = await page.evaluate(() => {
            const card = document.querySelector('.reader-card').getBoundingClientRect();
            const word = document.getElementById('readingWord');
            const textBounds = word.getBoundingClientRect();
            return {
              headerDecoration: getComputedStyle(document.querySelector('.reader-top'), '::after').content,
              progressBackground: getComputedStyle(document.getElementById('progressFill')).backgroundImage,
              outline: getComputedStyle(document.querySelector('.reader-card')).outlineStyle,
              textAlign: getComputedStyle(word).textAlign,
              textCenterOffset: Math.abs((textBounds.left + textBounds.right - card.left - card.right) / 2),
              buttons: [...document.querySelectorAll('.reader-footer button')]
                .filter(button => button.getClientRects().length)
                .map(button => {
                  const bounds = button.getBoundingClientRect();
                  return {id: button.id, left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom,
                    card: {left: card.left, right: card.right, top: card.top, bottom: card.bottom},
                    scrollWidth: button.scrollWidth, clientWidth: button.clientWidth,
                    fitsCard: bounds.left >= card.left && bounds.right <= card.right
                    && bounds.top >= card.top && bounds.bottom <= card.bottom,
                    fitsContent: button.scrollWidth <= button.clientWidth + 1};
                }),
            };
          });
          assert.ok(['none', 'normal'].includes(layout.headerDecoration), 'No decorative stripe on the header');
          for (const color of ['36, 94, 201', '246, 201, 76', '216, 91, 96']) {
            assert.ok(layout.progressBackground.includes(color), 'Progress fill includes blue, yellow, and red');
          }
          if (branch === 'story_reading') {
            assert.equal(layout.outline, 'none', 'Story card has no dashed outline');
            assert.equal(layout.textAlign, 'center', 'Story lines are centered');
            assert.ok(layout.textCenterOffset <= 1, 'Story text shares the card center');
          }
          for (const button of layout.buttons) {
            assert.ok(button.fitsCard && button.fitsContent,
              `${branch}: ${button.id} fits its card and label at ${viewport.width}px: ${JSON.stringify(button)}`);
          }
          for (const selector of ['#pauseBtn', '#nextBtn']) {
            if (!await page.locator(selector).isVisible()) continue;
            const bounds = await page.locator(selector).boundingBox();
            assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= viewport.width,
              `${branch}: ${selector} fits within the ${viewport.width}px screen`);
          }
          const expectedHints = ['sentences', 'story_reading'].includes(branch) ? 1 : 0;
          assert.equal(await page.locator('#readingWord .is-next-word').count(), expectedHints,
            `${branch}: next-word blue highlight`);
          assert.equal(await page.locator('#readingWord .is-current').count(), expectedHints,
            `${branch}: current-word blue highlight`);
          if (previewDir && branch === 'story_reading' && !debug) {
            // Preview the normal Story URL separately from the deliberately
            // mismatched recovery URL exercised above.
            const previewPage = await context.newPage();
            previewPage.on('domcontentloaded', () => previewPage.addScriptTag({content: testSource}).catch(error => errors.push(error.message)));
            await previewPage.goto(`${origin}/dashboard/assessment/reading_ui/para/?official_assessment_id=1&crla_stage=story_reading`);
            await previewPage.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
            await previewPage.evaluate(() => document.fonts.ready);
            const pauseBounds = await previewPage.locator('#pauseBtn').boundingBox();
            assert.ok(pauseBounds && pauseBounds.x + pauseBounds.width <= viewport.width,
              'Preview pause control stays inside the screen');
            await previewPage.screenshot({path: path.join(previewDir, `crla-story-${viewport.width}.png`), fullPage: true, animations: 'disabled'});
            await previewPage.evaluate(() => document.body.classList.add('dark-theme'));
            await previewPage.screenshot({path: path.join(previewDir, `crla-story-dark-${viewport.width}.png`), fullPage: true, animations: 'disabled'});
            await previewPage.close();
          }
          if (!expectedHints) {
            // Exercise redraws after a partial speech callback as well as the
            // initial screen: Word and Rhyme tasks must never add a blue cue.
            await page.evaluate(() => {
              const context = window.__readerTest.currentSpeechContext();
              window.__readerTest.handleSpeechResult({transcript: 'pi', words: ['Pito'], syllables: ['pi', 'to'],
                word_syllable_ranges: [[0, 2]], current_word_index: 0, current_syllable_index: 1,
                correct_word_count: 0, matched: 1, complete: false}, context);
            });
            assert.equal(await page.locator('#readingWord .is-next-word, #readingWord .is-current, #readingWord .is-unread-word').count(), 0,
              `${branch}: no blue hint after recognition`);
            await page.reload();
            await page.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
          }
          if (['sentences', 'story_reading'].includes(branch) && viewport.width === 1366 && !debug) {
            testingSpeechRetry = true;
            await page.evaluate(() => {
              window.timerRetryFinished = false;
              window.__readerTest.sendAudioChunk(new Blob(['same-recorded-answer'], {type: 'audio/webm'}))
                .then(() => { window.timerRetryFinished = true; });
            });
            if (branch === 'story_reading') {
              await page.waitForFunction(() => document.getElementById('storyReadingTimer').dataset.paused === 'true');
              const timerSnapshot = () => page.evaluate(() => ({
                remaining: document.getElementById('storyReadingTimer').getAttribute('aria-valuenow'),
                border: getComputedStyle(document.getElementById('storyReadingTimerProgress')).strokeDashoffset,
              }));
              const frozen = await timerSnapshot();
              await page.waitForTimeout(600);
              assert.deepEqual(await timerSnapshot(), frozen, 'Story timer moved during processing/retry');
              console.log('PASS Story timer: computed border animation and countdown freeze while processing/retrying');
            }
            await page.waitForFunction(() => window.timerRetryFinished);
            if (branch === 'story_reading') {
              await page.waitForFunction(() => document.getElementById('storyReadingTimer').dataset.paused === 'false');
            }
            assert.equal(retriedAudio.length, 2);
            assert.ok(retriedAudio.every(body => body.includes('same-recorded-answer')));
            testingSpeechRetry = false;
            assert.ok(!page.url().includes('/auth/'));
            console.log(`PASS ${branch}: a server HTML 500 retries the same recording in Chrome`);
          }
          if (branch === 'story_reading') {
            let expectedMiscues = 9, expectedRead = 0;
            if (viewport.width === 1366) {
              const evidence = await page.evaluate(({partial}) => {
                const words = ['May', 'pito', 'si', 'Ana', 'Narinig', 'ni', 'Ben', 'ang', 'pito'];
                const attempted = partial ? words.slice(0, 2) : words;
                window.__readerTest.handleSpeechResult({
                  transcript: attempted.map((word, index) => index === 1 ? 'mali' : word).join(' '),
                  words, syllables: words, word_syllable_ranges: words.map((_, index) => [index, index + 1]),
                  current_word_index: attempted.length, current_syllable_index: attempted.length,
                  // Generic cursor credit must not override strict per-word evidence.
                  correct_word_count: 9, matched: attempted.length - 1, complete: false,
                  word_alignment: {miscues: 1},
                  word_results: attempted.map((word, index) => ({expected_index: index,
                    result: index === 1 ? 'miscue' : 'correct',
                    type: index === 1 ? 'substitution' : 'correct'})),
                });
                return window.__readerTest.strictStoryEvidence();
              }, {partial: debug});
              expectedRead = debug ? 1 : 8;
              expectedMiscues = 9 - expectedRead;
              assert.equal(evidence.words_read, expectedRead);
              assert.equal(evidence.miscues, 1);
            }
            await page.locator('#nextBtn').click();
            const saved = await Promise.race([strictSnapshot,
              new Promise((_, reject) => setTimeout(() => reject(Error('Missing strict Story snapshot')), 5000))]);
            assert.equal(saved.miscues, expectedMiscues);
            assert.equal(saved.words_read, expectedRead);
            assert.equal(saved.total_story_words, 9);
            console.log(`PASS strict Story: ${expectedRead} correct words, ${expectedMiscues} substitutions/unread miscues saved`);
          }
          if (branch === 'words' && viewport.width === 1366 && !debug) {
            await page.evaluate(() => {
              window.__readerTest.sendAudioChunk(new Blob(['audio'], {type: 'audio/webm'}))
                .then(() => { window.speechFinished = true; });
            });
            await speechStarted;
            ended = true;
            await page.locator('#liveSessionEndedTitle').waitFor({state: 'visible'});
            assert.equal(await page.locator('#liveSessionEndedTitle').textContent(), "Your teacher ended today's session");
            await heldSpeechRoute.fulfill({status: 401, json: {success: false, error: 'Authentication required'}});
            await page.waitForFunction(() => window.speechFinished);
            assert.ok(!page.url().includes('/auth/'));
            assert.equal(await page.locator('#liveSessionEndedTitle').textContent(), "Your teacher ended today's session");
            await page.waitForURL(`${origin}/dashboard/assessment/`);
            console.log('PASS teacher End Session: late speech 401 keeps the teacher-ended screen and returns to Assessment');
          }
          assert.deepEqual(errors, []);
          console.log(`PASS ${branch}: ${viewport.width}px, debug=${debug}, ${before.fontSize}, resume + refresh`);
          checked++;
          await context.close();
        }
      }
    }
    console.log(`PASS: ${checked} CRLA layout scenarios using rendered templates and the complete reader.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
