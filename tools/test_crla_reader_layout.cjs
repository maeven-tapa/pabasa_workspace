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
const rendered = spawnSync(process.env.CRLA_PYTHON_PATH || 'python', ['-c', `
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()
from django.template.loader import render_to_string
print(json.dumps({mode: render_to_string('pabasa_app/reading_' + mode + '_page.html',
    {'crla_official_assessment_id': 1}) for mode in ['word', 'sentence', 'para']}))
`], {cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}});
assert.equal(rendered.status, 0, rendered.stderr);
// Load the complete reader separately after setting the server recovery payload.
const templates = Object.fromEntries(Object.entries(JSON.parse(rendered.stdout)).map(([mode, html]) =>
  [mode, html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '')
    .replace(/<link\b[^>]*>/g, '')]));
const official = {
  id: 1, assessment_kind: 'crla', official_title: 'CRLA Pre-Test', official_code: 'CRLA-BOSY',
  language: 'Filipino', words: Array(10).fill('Pito'),
  rhyme_pairs: Array(10).fill({word_a: 'pito', word_b: 'dito'}),
  sentences: Array(5).fill('May pito si Ana.'),
  passages: [{title: 'Ang Pito', content: 'May pito si Ana. Narinig ni Ben ang pito.'}],
};
const origin = 'http://localhost:9876';
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
    for (const viewport of [{width: 1366, height: 768}, {width: 390, height: 844}]) {
      for (const debug of [false, true]) {
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
          await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== origin) return route.abort();
            if (url.pathname.startsWith('/api/')) {
              return route.fulfill({json: {success: true, state, session: {
                id: 'layout-test', status: paused ? 'paused' : 'started', reader_url: resumedUrl,
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
          page.on('domcontentloaded', () => page.addScriptTag({content: source}).catch(error => errors.push(error.message)));
          await page.goto(readerUrl(mode, branch));
          await page.waitForFunction(() => !document.getElementById('pauseOverlay').classList.contains('d-none'));
          const before = await snapshot(page);
          const expectedMode = mode === 'para' ? 'paragraph' : mode;
          assert.deepEqual(before.shellModes, [`reader-${expectedMode}`]);
          assert.deepEqual(before.cardModes, [`content-${expectedMode}`]);
          if (mode !== 'para') assert.ok(parseFloat(before.fontSize) >= 32, JSON.stringify(before));
          paused = false;
          await page.waitForURL(resumedUrl);
          await page.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
          assert.deepEqual(await snapshot(page), before, `${branch}, ${viewport.width}px, debug=${debug}: resume`);
          await page.reload();
          await page.waitForFunction(() => !document.getElementById('readingWord').textContent.includes('Loading'));
          assert.deepEqual(await snapshot(page), before, `${branch}, ${viewport.width}px, debug=${debug}: refresh`);
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
