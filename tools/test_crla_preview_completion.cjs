// Local Chrome checks with real Django markup/reader and synthetic speech.
// No accounts, microphone recordings, external providers, or student writes.
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
from pabasa_app.reading_stt import analyze_reading, align_story_transcript
text = 'May pito si Ana. Narinig ni Ben ang pito.'
responses = {}
for name, spoken in [('correct', text), ('ending_substitution', 'May pito si Ana Narinig ni Ben ang bata')]:
    data = analyze_reading(text, 0, spoken, 'fil-PH', crla_story_reading=True)
    alignment = align_story_transcript(text, spoken, 'fil-PH', crla_story_reading=True)
    data.update(word_results=alignment['word_results'], word_alignment=alignment, success=True)
    responses[name] = data
for name, expected in [('word', 'Pito'), ('sentence', 'May pito si Ana.'), ('rhymes', 'pito dito')]:
    responses[name] = dict(analyze_reading(expected, 0, expected, 'fil-PH'), success=True)
html = render_to_string('pabasa_app/reading_para_page.html', {
    'crla_official_assessment_id': 1, 'crla_official_assessment_data': {'assessment_kind': 'crla'},
    'is_admin_preview': True,
})
print(json.dumps({'html': html, 'responses': responses}))
`], {cwd: root, encoding: 'utf8', env: {...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:', PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const html = fixture.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '').replace(/<link\b[^>]*>/g, '');
const source = fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8')
  .replace('        loadItems();', `        window.__readerTest = {handleSpeechResult, currentSpeechContext, strictStoryEvidence, completeCRLASpokenAttempt,
    startFixtureRecording() { isRecording = true; speechRecognitionUsed = true; startTime = Date.now() - 2000; },
    getState() { return readStudentEndState(); },
    beginFixtureStory() {
      const capture = startSpeechRecognition; startSpeechRecognition = () => {};
      try { startReading({fromStoryReadingCountdown: true}); } finally { startSpeechRecognition = capture; }
    }};
        loadItems();`);
const origin = 'http://localhost:9876';
const stateKey = 'pabasa_admin_crla_preview:flow-test';
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app');
const previewDir = process.env.CRLA_PREVIEW_DIR;
if (previewDir) fs.mkdirSync(previewDir, {recursive: true});
const baseStory = 'May pito si Ana. Narinig ni Ben ang pito.';
const scenarios = ['correct', 'ending_substitution', 'multiple_segments', 'no_questions', 'restored_complete',
  'restored_segment', 'quit', 'score_failure', 'answered_score_failure', 'final_score_failure', 'long_story',
  'story_selection', 'story_ready', 'section_complete', 'full_flow', 'rhyme_flow', 'preview_live_parameters'];
async function fitsScreen(page, label) {
  await page.waitForFunction(() => !document.getElementById('readingWord').classList.contains('is-changing'));
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const layout = await page.evaluate(() => {
    const root = document.documentElement;
    const card = document.querySelector('.reader-card');
    const word = document.getElementById('readingWord');
    const bounds = word.getBoundingClientRect();
    const stage = word.closest('.word-stage').getBoundingClientRect();
    return {width: root.scrollWidth, height: root.scrollHeight, viewportWidth: innerWidth, viewportHeight: innerHeight,
      cardHeight: card.clientHeight, cardContentHeight: card.scrollHeight,
      headerHeight: document.querySelector('.reader-top').getBoundingClientRect().height,
      footerHeight: document.querySelector('.reader-footer').getBoundingClientRect().height,
      stageHeight: stage.height, fontSize: getComputedStyle(word).fontSize, wordHeight: bounds.height,
      wordTop: bounds.top, wordBottom: bounds.bottom, stageTop: stage.top, stageBottom: stage.bottom,
      stageChildren: [...word.closest('.word-stage').children].map(child => ({id: child.id,
        display: getComputedStyle(child).display, height: child.getBoundingClientRect().height,
        margin: getComputedStyle(child).margin, position: getComputedStyle(child).position})),
      headerControls: [...document.querySelectorAll('.header-actions button')].map(button => ({id: button.id,
        width: button.getBoundingClientRect().width, minWidth: getComputedStyle(button).minWidth})),
      wordVisible: word.hidden || (bounds.top >= stage.top && bounds.bottom <= stage.bottom + 1 && bounds.bottom <= innerHeight)};
  });
  if (previewDir && (layout.height > layout.viewportHeight + 1 || !layout.wordVisible)) {
    await page.screenshot({path: path.join(previewDir, 'crla-fit-failure.png'), fullPage: true});
  }
  assert.ok(layout.width <= layout.viewportWidth && layout.height <= layout.viewportHeight + 1 && layout.wordVisible,
    label + ': ' + JSON.stringify(layout));
}
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let checked = 0;
  try {
    const selectedWidths = process.env.CRLA_VIEWPORT_WIDTHS?.split(',').map(Number);
    for (const viewport of [{width: 1900, height: 936}, {width: 1366, height: 600}, {width: 1366, height: 768}, {width: 1024, height: 768}, {width: 768, height: 1024},
      {width: 844, height: 390}, {width: 390, height: 844}, {width: 320, height: 568}]
      .filter(viewport => !selectedWidths || selectedWidths.includes(viewport.width))) {
      for (const scenario of scenarios.filter(scenario => !process.env.CRLA_SCENARIOS
        || process.env.CRLA_SCENARIOS.split(',').includes(scenario))) {
        if (viewport.width === 1366 && scenario === 'long_story') continue;
        const context = await browser.newContext({viewport});
        const page = await context.newPage();
        page.setDefaultTimeout(15000);
        const errors = [], posts = [];
        let rejectScoring = ['score_failure', 'answered_score_failure'].includes(scenario);
        let rejectFinalScore = scenario === 'final_score_failure';
        page.on('pageerror', error => errors.push(error.message));
        const multipleSegments = ['multiple_segments', 'restored_segment'].includes(scenario);
        const content = scenario === 'long_story'
          ? 'Sa umaga, naglakad si Ana kasama si Ben papunta sa paaralan at nakita nila ang kanilang guro sa tabi ng isang malaking puno. '.repeat(8)
          : multipleSegments ? baseStory + '\n\n' + baseStory : baseStory;
        const official = {id: 1, assessment_kind: 'crla', official_title: 'CRLA Pre-Test', official_code: 'CRLA-BOSY',
          language: 'Filipino', words: Array(10).fill('Pito'), sentences: Array(5).fill('May pito si Ana.'),
          rhyme_pairs: Array(10).fill({word_a: 'pito', word_b: 'dito'}), passages: [{title: 'Ang Pito', content}],
          story_qas: scenario === 'no_questions' ? [] : [{story_title: 'Ang Pito', questions: [{question: 'Sino ang may pito?'}]}]};
        if (scenario === 'story_selection') official.passages = [{title: 'Isang Kakaibang Araw', content: baseStory.repeat(3)},
          {title: 'Ang Pagong at ang Kuneho', content: baseStory.repeat(3)}];
        const flow = ['full_flow', 'rhyme_flow'].includes(scenario);
        const initialStage = scenario === 'full_flow' ? 'words' : scenario === 'rhyme_flow' ? 'rhymes' : 'story_reading';
        const state = {stage: flow ? initialStage : scenario === 'section_complete' ? 'transition_to_sentence'
          : ['story_selection', 'story_ready'].includes(scenario) ? scenario : 'story_reading',
          branch: flow ? initialStage : scenario === 'section_complete' ? 'words' : 'story', material_id: '1', story_number: 1,
          selected_story: 'Ang Pito', story_segment_index: 0, part1_total_score: 28,
          task1_score: 10, task2_sentences_score: 8, story_reading_started_at: new Date().toISOString(),
          ...(['restored_complete', 'restored_segment'].includes(scenario) ? {story_word_results: {'0': Object.fromEntries(Array.from({length: 9}, (_, i) => [i, 'correct']))},
            words_read: 9, miscues: 0, story_reading_elapsed_ms: 2000} : {})};
        await context.addInitScript(({official, state, stateKey}) => {
          window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
          window.__PABASA_ADMIN_PREVIEW__ = true;
          window.__PABASA_ADMIN_PREVIEW_RETURN__ = '/dashboard/admin/official-reading-assessments/';
          window.PABASA_USER_ID = '99'; window.PABASA_USER_ROLE = 'admin';
          if (location.pathname.includes('/assessment/reading_ui/') && !sessionStorage.getItem(stateKey)) sessionStorage.setItem(stateKey, JSON.stringify(state));
          localStorage.setItem('student-work-sentinel', 'unchanged');
        }, {official, state, stateKey});
        await context.route('**/*', async route => {
          const url = new URL(route.request().url());
          if (url.origin !== origin) return route.abort();
          if (url.pathname.startsWith('/static/pabasa_app/')) {
            let asset = path.resolve(staticRoot, url.pathname.slice('/static/pabasa_app/'.length));
            // Match the app's legacy-image fallback to its committed WebP assets.
            if (!fs.existsSync(asset)) asset = asset.replace(/\.(png|jpe?g)$/i, '.webp');
            if (asset.startsWith(staticRoot + path.sep) && fs.existsSync(asset) && fs.statSync(asset).isFile()) {
              return route.fulfill({body: fs.readFileSync(asset)});
            }
          }
          if (url.pathname.startsWith('/dashboard/assessment/reading_ui/')) return route.fulfill({contentType: 'text/html', body: html});
          if (url.pathname === '/api/admin/crla-preview/score/') {
            const payload = route.request().postDataJSON(); posts.push({path: url.pathname, payload});
            if (rejectScoring || (rejectFinalScore && payload.stage === 'completed')) return route.fulfill({status: 500, json: {success: false}});
            return route.fulfill({json: {success: true, preview_only: true,
              student_end_assessment_state: {...payload, classification: 'High Emerging Reader'},
              reader_classification: 'High Emerging Reader'}});
          }
          if (url.pathname === '/api/assessment/story-answer/check/') {
            posts.push({path: url.pathname});
            return route.fulfill({json: {success: true, is_correct: true}});
          }
          if (url.pathname.startsWith('/api/')) posts.push({path: url.pathname});
          return route.fulfill({contentType: 'application/json', body: '{}'});
        });
        page.on('domcontentloaded', async () => {
          if (!new URL(page.url()).pathname.startsWith('/dashboard/assessment/reading_ui/')) return;
          try {
            await page.evaluate(() => {
              window.__firstPaintTheme = {
                crla: document.body.classList.contains('is-crla-reader'),
                logo: Boolean(document.querySelector('.level-mark-deped img')),
                legacyIcons: document.querySelectorAll('.completion-mark').length,
                background: getComputedStyle(document.body).backgroundImage,
                card: getComputedStyle(document.querySelector('.completion-card')).backgroundColor,
              };
            });
            await page.addScriptTag({content: source});
          } catch (error) { errors.push(error.message); }
        });
        await page.goto(origin + `/dashboard/assessment/reading_ui/${flow ? 'word' : 'para'}/?official_assessment_id=1&admin_preview=1&admin_preview_token=flow-test&crla_stage=${initialStage}`
          + (scenario === 'preview_live_parameters' ? '&live=1&live_session_id=preview-test&countdown=0' : ''));
        await page.waitForFunction(() => window.__readerTest && (!document.getElementById('readingWord').textContent.includes('Loading')
          || document.querySelector('.reader-shell').classList.contains('is-complete')));
        assert.equal(await page.title(), 'PABASA | CRLA');
        assert.deepEqual(await page.evaluate(() => ({...window.__firstPaintTheme,
          background: window.__firstPaintTheme.background === getComputedStyle(document.body).backgroundImage,
          card: window.__firstPaintTheme.card === getComputedStyle(document.querySelector('.completion-card')).backgroundColor})),
          {crla: true, logo: true, legacyIcons: 0, background: true, card: true}, 'The CRLA theme is present before reader initialization');
        if (flow) {
          const branches = scenario === 'full_flow' ? ['words', 'sentences'] : ['rhymes'];
          for (const branch of branches) {
            console.log(`CHECK ${scenario}: ${branch} at ${viewport.width}px`);
            await page.waitForFunction(() => window.__readerTest && !document.querySelector('.reader-shell').classList.contains('is-complete'));
            const total = branch === 'sentences' ? 5 : 10;
            assert.deepEqual(await page.locator('#progressFill').evaluate(el => ({
              total: el.parentElement.getAttribute('aria-valuemax'), finished: el.style.getPropertyValue('--crla-finished'),
              current: el.style.getPropertyValue('--crla-current-end')})),
              {total: String(total), finished: '0%', current: `${100 / total}%`}, branch + ' starts with one yellow item and red remaining');
            for (let index = 0; index < total; index++) {
              await page.evaluate(data => {
                window.__readerTest.startFixtureRecording(); window.__readerTest.handleSpeechResult(data);
              }, fixture.responses[branch === 'words' ? 'word' : branch === 'sentences' ? 'sentence' : 'rhymes']);
              if (index < total - 1) {
                await page.waitForFunction(count => document.getElementById('counter').textContent.includes(`${count}/`), index + 2);
                assert.equal(await page.locator('#progressFill').evaluate(el => el.parentElement.getAttribute('aria-valuenow')), String(index + 1), branch + ' finished items turn blue');
              }
            }
            await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-section-complete'));
            assert.equal(await page.locator('#progressFill').evaluate(el => el.style.getPropertyValue('--crla-finished')), '100%', branch + ' completes in blue');
            assert.ok(!await page.locator('.completion-kicker').isVisible(), 'Section kicker is hidden');
            assert.ok(!await page.locator('#completionClassificationPanel').isVisible(), 'Section is not a final result');
            assert.ok(!await page.locator('#sentenceItemCountdown').isVisible(), 'No reading countdown covers completion');
            if (viewport.width <= 1024) await fitsScreen(page, branch + ' completion');
            if (previewDir) await page.screenshot({path: path.join(previewDir, `crla-${branch}-complete-${viewport.width}.png`), animations: 'disabled'});
            await page.waitForTimeout(1200);
            assert.ok(await page.locator('#finishBtn').isVisible(), 'Completion waits for Continue');
            await page.reload();
            await page.waitForFunction(() => window.__readerTest && document.querySelector('.reader-shell').classList.contains('is-section-complete'));
            assert.ok(!await page.locator('.completion-kicker').isVisible(), 'Refresh keeps the section card');
            await page.locator('#finishBtn').click();
            await page.waitForURL(url => url.searchParams.get('crla_stage') === (branch === 'words' ? 'sentences' : 'story_selection'));
          }
          await page.waitForFunction(() => window.__readerTest && !document.getElementById('storySelectionPanel').classList.contains('d-none'));
          await page.locator('.story-selection-cta').first().click();
          await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-story-ready-state'));
          await page.evaluate(() => window.__readerTest.beginFixtureStory());
        }
        if (scenario === 'section_complete') {
          await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-complete'));
          assert.ok((await page.locator('#finishBtn').textContent()).includes('Sentence'));
          assert.equal(await page.locator('.completion-mark').count(), 0, 'No legacy CRLA completion icon');
          assert.ok(!await page.locator('.completion-kicker').isVisible(), 'Section kicker is hidden');
          await page.waitForFunction(() => document.querySelector('.completion-card .crla-brand-logo').naturalWidth > 0);
          if (viewport.width <= 1024) await fitsScreen(page, 'Word section completion');
          if (previewDir) await page.screenshot({path: path.join(previewDir, `crla-word-complete-${viewport.width}-${viewport.height}.png`), animations: 'disabled'});
        } else if (scenario === 'quit') {
          await page.locator('#pauseBtn').click();
          assert.ok(await page.locator('#quitBtn').isVisible(), 'Admin Quit is visible in pause menu');
          await page.locator('#quitBtn').click();
          await page.waitForURL(origin + '/dashboard/admin/official-reading-assessments/');
          assert.equal(await page.evaluate(key => sessionStorage.getItem(key), stateKey), null);
        } else if (['story_selection', 'story_ready'].includes(scenario)) {
          await fitsScreen(page, scenario + ' at ' + viewport.width);
          const selector = scenario === 'story_selection' ? '#storySelectionGrid .story-selection-cta' : '#btnStartReading';
          const buttons = await page.locator(selector).all();
          assert.ok(buttons.length);
          for (const button of buttons) {
            const bounds = await button.boundingBox();
            assert.ok(bounds && bounds.y >= 0 && bounds.y + bounds.height <= viewport.height + 1, scenario + ': ' + JSON.stringify(bounds));
          }
          if (previewDir) await page.screenshot({path: path.join(previewDir, `crla-${scenario}-${viewport.width}.png`), animations: 'disabled'});
          if (scenario === 'story_selection') await page.waitForFunction(() => [...document.querySelectorAll('.story-choice-illustration')]
            .every(img => img.complete && img.naturalWidth > 0));
          if (scenario === 'story_ready') {
            await page.locator('#btnStartReading').click();
            await page.waitForFunction(() => !document.getElementById('storyReadingInstructionOverlay').classList.contains('d-none'));
            const overlay = page.locator('#storyReadingInstructionOverlay');
            assert.match(await overlay.evaluate(el => getComputedStyle(el).backdropFilter), /blur/);
            assert.ok(!await overlay.locator('.story-reading-modal-icon').isVisible());
            await page.waitForFunction(() => document.querySelector('#storyReadingInstructionOverlay .crla-brand-logo').naturalWidth > 0);
            const bounds = await overlay.locator('.story-reading-timer-dialog').boundingBox();
            assert.ok(bounds && bounds.y >= 0 && bounds.y + bounds.height <= viewport.height + 1, 'Ready dialog fits: ' + JSON.stringify(bounds));
            if (previewDir) await page.screenshot({path: path.join(previewDir, `crla-ready-dialog-${viewport.width}.png`), animations: 'disabled'});
          }
        } else if (scenario === 'long_story') {
          await fitsScreen(page, 'Long story reading at ' + viewport.width);
          assert.equal(await page.locator('#progressFill').evaluate(el => el.parentElement.getAttribute('aria-valuenow')), '0');
        } else {
          if (scenario !== 'restored_complete') {
            const response = fixture.responses[scenario === 'ending_substitution' ? scenario : 'correct'];
            if (scenario === 'ending_substitution') assert.equal(response.complete, false);
            if (multipleSegments) {
              if (scenario === 'multiple_segments') {
                await page.evaluate(data => {
                  window.__readerTest.startFixtureRecording();
                  window.__firstSpeechContext = window.__readerTest.currentSpeechContext();
                  window.__readerTest.handleSpeechResult(data);
                }, response);
              }
              await page.waitForFunction(() => document.getElementById('counter').textContent.includes('2/2'));
              const progress = await page.locator('#progressFill').evaluate(el => el.parentElement.getAttribute('aria-valuenow'));
              assert.equal(progress, '9', 'Finished progress counts the completed first segment');
              if (scenario === 'multiple_segments') {
                await page.evaluate(data => window.__readerTest.handleSpeechResult(data, window.__firstSpeechContext), response);
                assert.ok(await page.locator('#crlaQuestionPanel').evaluate(el => el.classList.contains('d-none')),
                  'Late response from the first segment cannot finish the next segment');
              }
            }
            await page.evaluate(data => {
              window.__readerTest.startFixtureRecording();
              window.__readerTest.handleSpeechResult(data);
            }, response);
          }
          await page.waitForFunction(() => !document.getElementById('crlaQuestionPanel').classList.contains('d-none'));
          if (viewport.width <= 1024) await fitsScreen(page, 'Comprehension at ' + viewport.width);
          assert.equal(await page.locator('#crlaQuestionPanel .story-question-kicker, #crlaQuestionCounter, .crla-progress-legend:visible').count(), 0);
          assert.equal(await page.locator('#counter').textContent(), scenario === 'no_questions'
            ? 'No comprehension questions' : 'Story Comprehension 1/1');
          if (scenario === 'answered_score_failure') {
            await page.evaluate(() => window.__readerTest.completeCRLASpokenAttempt('Ana', 0));
          } else await page.locator('#crlaQuestionNextBtn').click();
          if (rejectScoring) {
            await page.waitForFunction(() => document.getElementById('crlaAnswerFeedback').textContent.includes('could not prepare'));
            assert.equal(await page.evaluate(() => window.__readerTest.getState().stage), 'story_comprehension');
            rejectScoring = false;
            await page.locator('#crlaQuestionNextBtn').click();
          }
          await page.waitForFunction(() => !document.getElementById('learnerExperiencePage').classList.contains('d-none'));
          await page.waitForFunction(() => [...document.querySelectorAll('#learnerExperiencePage .rating-option img')]
            .every(img => img.complete && img.naturalWidth > 0));
          if (viewport.width <= 1024) {
            await fitsScreen(page, 'Learner rating at ' + viewport.width);
            const bounds = await page.locator('#learnerExperienceContinue').boundingBox();
            if (previewDir && bounds && bounds.y + bounds.height > viewport.height + 1) {
              await page.screenshot({path: path.join(previewDir, 'crla-rating-fit-failure.png')});
            }
            assert.ok(bounds && bounds.y + bounds.height <= viewport.height + 1, 'Rating controls fit the screen: ' + JSON.stringify(bounds));
          }
          if (previewDir && scenario === 'correct') await page.screenshot({path: path.join(previewDir, `crla-rating-${viewport.width}.png`), animations: 'disabled'});
          await page.locator('.rating-option[data-rating="4"]').click();
          await page.locator('#learnerExperienceContinue').click();
          if (rejectFinalScore) {
            await page.waitForFunction(() => document.getElementById('learnerExperienceFeedback').textContent.includes('could not save'));
            assert.equal(await page.evaluate(() => window.__readerTest.getState().stage), 'learner_experience');
            assert.ok(!await page.locator('.reader-shell').evaluate(el => el.classList.contains('is-complete')),
              'Failed final scoring cannot show a successful completion');
            rejectFinalScore = false;
            await page.locator('#learnerExperienceContinue').click();
          }
          await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-complete'));
          await page.waitForFunction(() => document.getElementById('completionClassificationValue').textContent.includes('High Emerging Reader'));
          assert.ok(await page.locator('#completionClassificationPanel').isVisible(), 'Admin shows final assessment results');
          assert.ok(await page.locator('.completion-kicker').isVisible(), 'Final results kicker is preserved');
          if (viewport.width <= 1024) await fitsScreen(page, 'Results at ' + viewport.width);
          const completed = posts.filter(post => post.payload?.stage === 'completed').at(-1)?.payload;
          assert.ok(completed, 'Admin final scoring requested');
          assert.equal(completed.miscues, scenario === 'ending_substitution' ? 1 : 0);
          assert.equal(completed.words_read, scenario === 'ending_substitution' ? 8 : multipleSegments ? 18 : 9);
          if (scenario === 'answered_score_failure') assert.equal(completed.correct_answers, 1, 'The answer survives a scoring retry');
          if (scenario === 'restored_complete') assert.ok(completed.duration_seconds >= 2, 'Recorded reading duration survives completion recovery');
          assert.equal(await page.evaluate(() => localStorage.getItem('student-work-sentinel')), 'unchanged');
          if (previewDir && scenario === 'correct') await page.screenshot({path: path.join(previewDir, `crla-admin-results-${viewport.width}.png`), animations: 'disabled'});
          if (flow) {
            await page.reload();
            await page.waitForFunction(() => window.__readerTest && document.querySelector('.reader-shell').classList.contains('is-complete'));
            assert.ok(await page.locator('#completionClassificationPanel').isVisible(), 'Admin result survives refresh');
            assert.ok(await page.locator('.completion-kicker').isVisible());
          }
        }
        assert.ok(posts.every(post => ['/api/admin/crla-preview/score/', '/api/assessment/story-answer/check/'].includes(post.path)),
          'Preview uses no student persistence endpoints: ' + JSON.stringify(posts.map(post => post.path)));
        assert.deepEqual(errors, []);
        console.log(`PASS ${scenario}: ${viewport.width}px`);
        checked++;
        await context.close();
      }
    }
    console.log(`PASS: ${checked} CRLA admin completion, recovery, Quit, and viewport scenarios.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
