// Navigation regression checks against Django-rendered session 10–15 pages.
// Set PABASA_PLAYWRIGHT_PATH to a Playwright module path when needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const venvPython = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.PABASA_PYTHON || (fs.existsSync(venvPython) ? venvPython : 'python');
const rendered = spawnSync(python, ['-c', `
import json, os, sys
from pathlib import Path
sys.path.insert(0, 'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from django.template.loader import render_to_string
pages = []
for file in sorted(Path('pabasa_site/pabasa_app/templates/pabasa_app').glob('prescribed*page.html')):
    if 'prescribed_lesson26_31_ui.js' not in file.read_text(encoding='utf-8'):
        continue
    variants = {}
    for completed in (False, True):
        data = {'progress': {'activity_completed': completed, 'state': {}}}
        variants[str(completed)] = render_to_string('pabasa_app/' + file.name, {'prescribed_activity_data': data})
    pages.append({'file': file.name, 'variants': variants})
print(json.dumps(pages))
`], {cwd: root, encoding: 'utf8', maxBuffer: 5 * 1024 * 1024});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);
assert.equal(fixtures.length, 15);
const scripts = new Set([
  'prescribed_controls.js', 'session13_prescribed_controls.js',
  'lesson30_prescribed_controls.js', 'session15_prescribed_controls.js',
  'prescribed_lesson26_activity1_tools.js', 'prescribed_lesson26_activity2_tools.js',
  'prescribed_leave_confirmation.js', 'prescribed_lesson26_31_ui.js',
]);

// Preserve navigation scripts in template order, including their defer behavior.
// Speech recognition, grading and activity APIs are outside this navigation check.
function navigationHtml(html) {
  return html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi, (tag, attrs) => {
    if (/type="application\/json"/.test(attrs)) return tag;
    const src = attrs.match(/src="([^"]+)"/)?.[1];
    return src && scripts.has(path.posix.basename(src.split('?')[0])) ? tag : '';
  });
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let checks = 0;
  try {
    for (const fixture of fixtures) {
      for (const scenario of ['activity', 'pause', 'completion', 'completed-reload']) {
        const page = await browser.newPage();
        const errors = [];
        const adapterCalls = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.exposeFunction('navigationAdapterCall', name => adapterCalls.push(name));
        const html = fixture.variants[scenario === 'completed-reload' ? 'True' : 'False'];
        await page.route('http://localhost:9876/**', async route => {
          const url = new URL(route.request().url());
          if (url.pathname === '/activity') {
            return route.fulfill({contentType: 'text/html', body: navigationHtml(html)});
          }
          if (url.pathname === '/dashboard/assessment/') {
            return route.fulfill({contentType: 'text/html', body: '<h1>My Lessons</h1>'});
          }
          if (url.pathname.startsWith('/static/pabasa_app/')) {
            const file = path.join(app, url.pathname.slice(1));
            if (fs.existsSync(file)) {
              const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'application/octet-stream';
              return route.fulfill({contentType, body: fs.readFileSync(file)});
            }
          }
          return route.fulfill({status: 404, body: ''});
        });
        await page.goto('http://localhost:9876/activity');
        await page.evaluate(() => {
          // Model an activity that has already passed its Start dialog.
          document.querySelectorAll('body > div[id$="-start"]').forEach(modal => {
            modal.hidden = true;
            modal.style.display = 'none';
          });
          document.querySelectorAll('[id$="-stage"]').forEach(stage => {
            stage.classList.remove('waiting', 'is-waiting');
          });
        });
        const stateBefore = await page.locator('#prescribed-activity-data').textContent();
        if (scenario === 'activity' || scenario === 'pause') {
          const ids = await page.evaluate(() => {
            const back = document.querySelector('a[id$="-back"]');
            const leave = document.querySelector('[id$="-leave-modal"]');
            const prefix = leave.id.slice(0, -'-leave-modal'.length);
            window.__prescribedLeaveAdapters = {
              [prefix]: {
                saveCurrentProgress: () => window.navigationAdapterCall('save'),
                cleanup: () => window.navigationAdapterCall('cleanup'),
              },
            };
            return {back: back.id, leave: leave.id, pause: `${prefix}-pause-modal`};
          });
          const backSelector = scenario === 'activity'
            ? `a[id="${ids.back}"]` : `#${ids.pause} button[id$="-back"]`;
          if (scenario === 'pause') {
            await page.evaluate(id => { document.getElementById(id).hidden = false; }, ids.pause);
          }
          await page.locator(backSelector).click();
          assert.equal(await page.locator(`#${ids.leave}`).isVisible(), true, fixture.file);
          assert.equal(new URL(page.url()).pathname, '/activity');
          await page.locator(`#${ids.leave} button[id$="-leave-no"]`).click();
          assert.equal(await page.locator(`#${ids.leave}`).isVisible(), false);
          assert.deepEqual(adapterCalls, []);
          if (scenario === 'pause') assert.equal(await page.locator(`#${ids.pause}`).isVisible(), true);
          await page.locator(backSelector).click();
          await page.locator(`#${ids.leave} button[id$="-leave-yes"]`).click();
          await page.waitForURL('**/dashboard/assessment/', {timeout: 3000});
          assert.deepEqual(adapterCalls, ['save', 'cleanup']);
        } else {
          if (fixture.file === 'prescribed_match_it_lesson30_activity1_page.html') {
            // Exercise Match It's existing completion renderer as well.
            const source = fs.readFileSync(path.join(app, 'static/pabasa_app/js/prescribed_match_it_lesson30_activity1.js'), 'utf8');
            const renderer = source.slice(source.indexOf('function showCompletion(){'), source.indexOf('function announce('));
            await page.addScriptTag({content: `(() => {const app=document.getElementById('app'),d={},esc=x=>String(x);${renderer};showCompletion();})();`});
          } else if (scenario === 'completion') {
            await page.evaluate(() => {
              window.PrescribedLessonUi.showCompletion();
              // Completion renders can run again after a saved response.
              window.PrescribedLessonUi.showCompletion();
            });
          }
          const completion = page.locator('a.pabasa-completion-button, a.l30a1-completion-button');
          assert.equal(await completion.count(), 1, fixture.file);
          assert.equal(await completion.isVisible(), true, fixture.file);
          assert.equal(new URL(await completion.getAttribute('href'), page.url()).pathname, '/dashboard/assessment/');
          assert.equal(await page.locator('#prescribed-activity-data').textContent(), stateBefore);
          await completion.click();
          await page.waitForURL('**/dashboard/assessment/', {timeout: 3000});
          assert.deepEqual(adapterCalls, []);
        }
        assert.deepEqual(errors, [], `${fixture.file}: ${scenario}`);
        await page.close();
        checks++;
      }
      console.log(`PASS: ${fixture.file}`);
    }
    console.log(`PASS: ${checks} navigation checks across ${fixtures.length} session 10–15 activities.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
