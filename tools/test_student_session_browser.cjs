// Run with Node, installed Chrome, and playwright-core (or SESSION_PLAYWRIGHT_PATH).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.SESSION_PLAYWRIGHT_PATH || 'playwright-core');
const source = fs.readFileSync(path.join(__dirname,
  '../pabasa_site/pabasa_app/static/pabasa_app/js/student_session.js'), 'utf8');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    for (const enabled of [false, true]) {
      const page = await browser.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://localhost:9876/**', route => route.fulfill({
        contentType: 'text/html', body: '<main>Dashboard</main>',
      }));
      await page.goto('http://localhost:9876/dashboard/');
      await page.clock.install();
      await page.evaluate(enabled => {
        const config = {channel: 'browser-policy-test', csrf_token: 'test',
          heartbeat_url: '/heartbeat', login_url: '/auth/', logout_url: '/logout/',
          timeouts_enabled: enabled, remaining_seconds: 0, warning_seconds: 120,
          learning_page: false, protected: false};
        const node = document.createElement('script');
        node.id = 'student-session-config'; node.type = 'application/json';
        node.textContent = JSON.stringify(config); document.body.append(node);
        window.sessionStatus = config; window.responseStatus = 200; window.cancelled = 0;
        window.Basahin = {cancelAll() { window.cancelled++; }};
        window.fetch = async () => ({status: window.responseStatus, ok: window.responseStatus === 200,
          json: async () => ({success: true, ...window.sessionStatus})});
      }, enabled);
      await page.addScriptTag({content: source});
      await page.evaluate(() => window.PabasaStudentSession.check());
      await page.clock.fastForward(31 * 60 * 1000);
      await page.evaluate(() => window.PabasaStudentSession.check());
      if (enabled) {
        assert.equal(await page.locator('dialog').evaluate(node => node.open), true);
        assert.equal(await page.locator('dialog h2').textContent(), 'Still there?');
        // An already open idle warning closes when the new server policy arrives.
        await page.evaluate(async () => {
          window.sessionStatus = {...window.sessionStatus, timeouts_enabled: false};
          await window.PabasaStudentSession.check();
        });
        assert.equal(await page.locator('dialog').evaluate(node => node.open), false);
      } else {
        assert.equal(await page.locator('dialog').count(), 0);
      }
      assert.equal(await page.evaluate(() => window.cancelled), 0);
      // A revoked/replaced auth session must still stop recording and require login.
      await page.evaluate(async () => { window.responseStatus = 401; await window.PabasaStudentSession.check(); });
      assert.equal(await page.locator('dialog h2').textContent(), 'Your session has ended');
      assert.equal(await page.evaluate(() => window.cancelled), 1);
      assert.deepEqual(errors, []);
      console.log(`PASS timeouts=${enabled}: idle warning policy and revoked-session handling`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
