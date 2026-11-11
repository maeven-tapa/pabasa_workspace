// Real directory requests; Django owns all synthetic fixtures and mutations.
const assert = require('node:assert/strict');
const readline = require('node:readline');
const { chromium } = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const input = readline.createInterface({ input: process.stdin });
const command = name => new Promise(resolve => { input.once('line', resolve); console.log(JSON.stringify({ command: name })); });
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const base = process.env.PABASA_SYNC_SERVER;
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addCookies([{ name: 'sessionid', value: process.env.PABASA_SYNC_COOKIE, url: base }]);
    const page = await context.newPage();
    const errors = [];
    const responses = [];
    const cookieAttributes = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', async response => {
      if (response.url().includes('/students-api/')) responses.push(response.status());
      if (response.status() === 403 && response.url().startsWith(base)) {
        try { errors.push({ path: new URL(response.url()).pathname, error: (await response.json()).error }); } catch {}
      }
      const headers = await response.allHeaders();
      const cookie = headers['set-cookie'];
      if (cookie?.includes('sessionid=')) cookieAttributes.push(cookie.split('\n').map(line => line.split(';').slice(1).join(';')));
    });
    await page.goto(base + '/dashboard/students/');
    const check = async (status, label) => {
      await page.evaluate(() => refreshStudentOverview());
      try {
        await page.waitForFunction(status => document.querySelector('[data-crla-progress]')?.dataset.crlaProgress === status, status, { timeout: 10000 });
      } catch (error) {
        const cookies = (await context.cookies()).map(({ name, expires, secure }) => ({ name, expires, secure }));
        throw new Error(JSON.stringify({ expected: status, path: new URL(page.url()).pathname, errors, responses, cookies, cookieAttributes }));
      }
      assert.equal(await page.locator('[data-crla-progress]').textContent(), label);
      assert.equal(await page.locator('.student-card-row .level-pending').count(), 0);
      assert.equal(await page.locator('.student-crla-details').count(), 0);
      assert.equal(await page.getByRole('link', { name: 'Open Live Session' }).count(), 1);
      assert.equal(await page.locator('#exportStudentsBtn').getAttribute('aria-disabled'), 'true');
    };
    const reload = async () => {
      // Let in-flight fixture session writes finish before cancelling navigation.
      await page.evaluate(() => Object.defineProperty(document, 'hidden', { configurable: true, value: true }));
      await page.waitForFunction(() => !studentDirectorySyncBusy && !studentDirectorySyncQueued);
      await page.waitForLoadState('networkidle');
      await page.reload();
    };
    await check('in_progress', 'CRLA in progress');
    await command('saved');
    await check('saved', 'Saved — ready to resume');
    await reload();
    await check('saved', 'Saved — ready to resume');
    await command('resumed');
    await check('in_progress', 'CRLA in progress');
    await command('completed');
    await check('completed', 'Completed — awaiting End Session');
    await reload();
    await check('completed', 'Completed — awaiting End Session');
    await page.screenshot({ path: 'output/aral-live-progress-completed-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: 'output/aral-live-progress-completed-mobile.png', fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await command('official');
    await page.evaluate(() => refreshStudentOverview());
    try {
      await page.waitForFunction(() => document.querySelector('.student-crla-profile-badge')?.textContent === 'Low Emerging Reader', null, { timeout: 10000 });
    } catch (error) {
      throw new Error(JSON.stringify({ responses, cookieAttributes, errors, cookies: (await context.cookies()).map(({ name, expires }) => ({ name, expires })) }));
    }
    assert.equal(await page.locator('[data-crla-progress]').count(), 0);
    assert.equal(await page.getByRole('link', { name: 'Open Live Session' }).count(), 0);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: 'output/aral-live-progress-browser.png', fullPage: true });
    console.log(JSON.stringify({ result: 'passed', scenarios: 7, description: 'started; saved; saved after reload; resumed; completed awaiting finalization; completed after reload; official result replaces progress' }));
  } finally { await browser.close(); input.close(); }
})().catch(error => { console.error(error); process.exit(1); });
