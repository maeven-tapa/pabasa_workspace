/* Real dashboard scripts with synthetic responses; no production requests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os, sys
sys.path.insert(0, 'pabasa_site')
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from django.template.loader import render_to_string
print(render_to_string('pabasa_app/dashboard.html', {
    'nav_role': 'student', 'student_theme_slug': 'sky', 'user_full_name': 'Fixture Student',
    'email': 'fixture@example.com', 'csrf_token': 'fixture',
    'student_session_progress': [{'session': 1, 'total': 1, 'completed': 0}],
}))
`], { cwd: root, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:', PYTHONIOENCODING: 'utf-8' } });
assert.equal(rendered.status, 0, rendered.stderr);
// The Bootstrap stub intentionally differs from the CDN's signed bytes.
const fixtureHtml = rendered.stdout.replace(/ integrity="[^"]*"/g, '');

(async () => {
    const browser = await chromium.launch({ headless: true,
        executablePath: process.env.PABASA_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    try {
        const page = await browser.newPage();
        let classRequests = 0;
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.hostname !== 'pabasa.test') {
                if (url.pathname.endsWith('bootstrap.bundle.min.js')) {
                    return route.fulfill({ contentType: 'text/javascript', body: `
                        class FixtureWidget {
                            static getOrCreateInstance() { return new FixtureWidget(); }
                            static getInstance() { return null; }
                            show() {} hide() {} dispose() {} setContent() {}
                        }
                        window.bootstrap = { Modal: FixtureWidget, Tooltip: FixtureWidget, Toast: FixtureWidget, Popover: FixtureWidget };
                    ` });
                }
                return route.abort();
            }
            if (['/api/student/classes/', '/dashboard/student/classes/'].includes(url.pathname)) {
                classRequests++;
                await new Promise(resolve => setTimeout(resolve, 100));
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, classes: [{
                    id: 4, section_id: 4, code: 'FIXTURE', name: 'Synthetic Reading Class',
                    subject: 'Reading', student_count: 20, assessment_week_enabled: false,
                    official_crla_completed: false, aral_eligible: false,
                    aral_week_total: 0, aral_week_completed: 0,
                }] }) });
            }
            if (url.pathname === '/api/class/materials/') {
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
                    success: true, section_id: 4, class_name: 'Synthetic Reading Class', materials: {},
                }) });
            }
            if (url.pathname.startsWith('/static/')) {
                const file = path.join(root, 'pabasa_site/pabasa_app/static', url.pathname.slice('/static/'.length));
                if (fs.existsSync(file) && /\.(js|css)$/.test(file)) {
                    return route.fulfill({ body: fs.readFileSync(file), contentType: file.endsWith('.js') ? 'text/javascript' : 'text/css' });
                }
                return route.abort();
            }
            if (url.pathname === '/dashboard/') {
                return route.fulfill({ body: fixtureHtml, contentType: 'text/html' });
            }
            return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
                success: true, notifications: [], unread_count: 0, invitation: null,
            }) });
        });
        for (let visit = 1; visit <= 2; visit++) {
            await page.goto('http://pabasa.test/dashboard/');
            await page.waitForFunction(() => document.querySelector('[data-class-list]')?.textContent.includes('Synthetic Reading Class'));
            await page.waitForFunction(() => !document.body.classList.contains('dashboard-preloading'));
            assert.equal(classRequests, visit, 'one fresh class request per page load');
            assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pabasaStudentSectionIds'))[0]), '4');
            assert.equal(errors.length, 0, errors.join('; '));
        }
        console.log('PASS: real dashboard renders its class card and sidebar storage using one class request per page load, with no script errors.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
