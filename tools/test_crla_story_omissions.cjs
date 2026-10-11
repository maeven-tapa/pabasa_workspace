// Local Chrome regression: real Django markup, reader, and alignment results.
// No real accounts, microphone, provider calls, or persistence are used.
// Set CRLA_PLAYWRIGHT_PATH and CRLA_PYTHON_PATH for local runtimes if needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || path.join(root, '.venv/Scripts/python.exe'), ['-c', [
  "import os, json, sys",
  "sys.path.insert(0, 'pabasa_site')",
  "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')",
  "import django",
  "django.setup()",
  "from django.template.loader import render_to_string",
  "from pabasa_app.reading_stt import analyze_reading, align_story_transcript",
  "text = 'May pito si Ana. Narinig ni Ben ang pito.'",
  "cases = []",
  "for spoken, skipped, complete in [",
  "    ('May pito Ana Narinig ni Ben', [2], False),",
  "    ('May pito Narinig ni Ben', [2, 3], False),",
  "    ('ni Ben', [0, 1, 2, 3, 4], False),",
  "    ('May pito Ana Narinig Ben', [2, 5], False),",
  "    ('May pito', [], False),",
  "    ('May pito Narinig ni Ben ang pito', [2, 3], True),",
  "]:",
  "    data = analyze_reading(text, 0, spoken, 'fil-PH', crla_story_reading=True)",
  "    alignment = align_story_transcript(text, spoken, 'fil-PH', start_word_index=0, crla_story_reading=True)",
  "    data.update(word_results=alignment['word_results'], word_alignment=alignment,",
  "                success=True, stt_provider='google', language_code='fil-PH')",
  "    next_index = alignment['word_results'][-1]['expected_index'] + 1",
  "    cursor = data['word_syllable_ranges'][next_index - 1][1]",
  "    remaining = ' '.join(data['words'][next_index:])",
  "    continuation = analyze_reading(text, cursor, remaining, 'fil-PH', crla_story_reading=True)",
  "    tail = align_story_transcript(text, remaining, 'fil-PH', start_word_index=next_index, crla_story_reading=True)",
  "    continuation.update(word_results=tail['word_results'], word_alignment=tail, success=True)",
  "    cases.append(dict(data=data, continuation=continuation, skipped=skipped, complete=complete))",
  "print(json.dumps(dict(html=render_to_string('pabasa_app/reading_para_page.html',",
  "                      {'crla_official_assessment_id': 1}), cases=cases)))",
].join('\n')], {cwd: root, encoding: 'utf8', env: {...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:', PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const html = fixture.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '').replace(/<link\b[^>]*>/g, '');
const source = fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8')
  .replace('        loadItems();', '        window.__readerTest = {handleSpeechResult, currentSpeechContext, strictStoryEvidence, startFixtureRecording() { isRecording = true; speechRecognitionUsed = true; startTime = Date.now() - 2000; }};\n        loadItems();');
const origin = 'http://localhost:9876';
const official = {
  id: 1, assessment_kind: 'crla', official_title: 'CRLA Pre-Test', official_code: 'CRLA-BOSY',
  language: 'Filipino', words: Array(10).fill('Pito'), sentences: Array(5).fill('May pito si Ana.'),
  passages: [{title: 'Ang Pito', content: 'May pito si Ana. Narinig ni Ben ang pito.'}],
};
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let checked = 0;
  try {
    for (const viewport of [{width: 1366, height: 768}, {width: 390, height: 844}]) {
      for (const scenario of fixture.cases) {
        const context = await browser.newContext({viewport});
        const page = await context.newPage();
        const errors = [];
        let resolveSnapshot;
        const finalSnapshot = new Promise(resolve => {resolveSnapshot = resolve;});
        page.on('pageerror', e => errors.push(e.message));
        const state = {stage: 'story_reading', branch: 'sentences', material_id: '1',
          selected_story: 'Ang Pito', story_segment_index: 0,
          story_reading_started_at: new Date().toISOString()};
        await context.addInitScript(({official, state}) => {
          window.__PABASA_OFFICIAL_ASSESSMENT__ = official;
          window.__PABASA_STUDENT_END_STATE__ = state;
          window.PABASA_USER_ID = '1'; window.PABASA_USER_ROLE = 'student';
        }, {official, state});
        await page.route('**/*', async route => {
          const url = new URL(route.request().url());
          if (url.origin !== origin) return route.abort();
          if (url.pathname.startsWith('/dashboard/assessment/reading_ui/')) {
            return route.fulfill({contentType: 'text/html', body: html});
          }
          if (url.pathname.startsWith('/api/')) {
            if (route.request().method() === 'POST') {
              const saved = route.request().postDataJSON()?.recovery_state;
              if (saved?.stage === 'story_comprehension') resolveSnapshot(saved);
            }
            return route.fulfill({json: {success: true, state, session: {
              id: 'omission-test', status: 'started', student_states: {'1': {
                status: 'in_progress', participation_status: 'active', recovery_state: state}},
            }}});
          }
          return route.fulfill({body: ''});
        });
        page.on('domcontentloaded', () => page.addScriptTag({content: source}).catch(e => errors.push(e.message)));
        await page.goto(origin + '/dashboard/assessment/reading_ui/para/?official_assessment_id=1' +
          '&live=1&live_session_id=omission-test&countdown=0&live_recovery=1&crla_stage=story_reading');
        await page.waitForFunction(() => window.__readerTest && !document.getElementById('readingWord').textContent.includes('Loading'));
        const snapshot = await page.evaluate(data => {
          window.__readerTest.startFixtureRecording();
          const originalContext = window.__readerTest.currentSpeechContext();
          window.__readerTest.handleSpeechResult(data, originalContext);
          const evidence = window.__readerTest.strictStoryEvidence();
          // A delayed duplicate must neither move the cursor nor add miscues.
          window.__readerTest.handleSpeechResult(data, originalContext);
          return {evidence, afterDuplicate: window.__readerTest.strictStoryEvidence(),
            cursor: window.__readerTest.currentSpeechContext().syllableIndex,
            words: [...document.querySelectorAll('#readingWord .syllable')].map(el => ({
              text: el.textContent, classes: [...el.classList]}))};
        }, scenario.data);
        const resolved = scenario.data.word_results.filter(r => r.expected_index !== null);
        const lastIndex = resolved.at(-1).expected_index;
        assert.equal(snapshot.cursor, scenario.data.word_syllable_ranges[lastIndex][1]);
        assert.equal(snapshot.evidence.miscues, scenario.skipped.length);
        assert.equal(snapshot.evidence.words_read, resolved.length - scenario.skipped.length);
        assert.deepEqual(snapshot.afterDuplicate, snapshot.evidence);
        for (const result of resolved) {
          const word = snapshot.words[result.expected_index];
          assert.ok(word.classes.includes(result.type === 'omission' ? 'is-wrong' : 'is-read'), JSON.stringify(word));
          assert.ok(!word.classes.includes('is-current'), JSON.stringify(word));
        }
        if (!scenario.complete) {
          assert.ok(snapshot.words[lastIndex + 1].classes.includes('is-current'));
          assert.ok(snapshot.words[lastIndex + 1].classes.includes('is-next-word'));
          assert.ok(!snapshot.words[lastIndex + 1].classes.includes('is-wrong'));
          await page.evaluate(data => window.__readerTest.handleSpeechResult(data), scenario.continuation);
        } else {
          // Generic matching stops at the omission; the aligned spoken tail finishes.
          assert.equal(scenario.data.complete, false);
        }
        await page.waitForFunction(() => document.querySelector('.reader-shell').classList.contains('is-story-comprehension'));
        const saved = await Promise.race([finalSnapshot,
          new Promise((_, reject) => setTimeout(() => reject(Error('Missing final story snapshot')), 5000))]);
        assert.equal(saved.miscues, scenario.skipped.length);
        assert.equal(saved.words_read, 9 - scenario.skipped.length);
        for (const skippedIndex of scenario.skipped) assert.equal(saved.story_word_results['0'][skippedIndex], 'omission');
        assert.deepEqual(errors, []);
        console.log('PASS ' + viewport.width + 'px: "' + scenario.data.transcript + '" (' + scenario.skipped.length + ' omissions)');
        checked++;
        await context.close();
      }
    }
    console.log('PASS: ' + checked + ' CRLA omission/highlight scenarios.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode = 1;});
