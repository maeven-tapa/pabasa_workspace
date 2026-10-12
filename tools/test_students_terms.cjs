// Functional tests only; the Django harness owns the disposable database and session.
const assert = require('node:assert/strict');
const readline = require('node:readline');
const { chromium } = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const input = readline.createInterface({ input: process.stdin });
const command = name => new Promise(resolve => { input.once('line', resolve); console.log(JSON.stringify({ command: name })); });
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const base = process.env.PABASA_SYNC_SERVER;
    const materials = JSON.parse(process.env.PABASA_STUDENTS_MATERIALS);
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addCookies([{ name: 'sessionid', value: process.env.PABASA_SYNC_COOKIE, url: base }]);
    const page = await context.newPage();
    const errors = [], requests = [], navigations = [], responses = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('framenavigated', frame => { if (frame === page.mainFrame()) navigations.push(frame.url()); });
    page.on('request', request => { if (request.url().includes('/students-api/')) requests.push(new URL(request.url())); });
    page.on('response', response => {
      if (response.url().includes('/students-api/')) responses.push({ status: response.status(), type: response.headers()['content-type'] });
    });
    await page.addInitScript(() => {
      // Shorten the existing timer only in this browser test; no additional polling timer.
      const originalInterval = window.setInterval;
      window.setInterval = (callback, interval, ...args) => originalInterval(callback, interval === 30000 ? 500 : interval, ...args);
      const originalFetch = window.fetch;
      window.termTestRequests = { active: 0, maximum: 0 };
      window.fetch = async (...args) => {
        const tracked = String(args[0]).includes('/students-api/');
        if (tracked) {
          window.termTestRequests.active++;
          window.termTestRequests.maximum = Math.max(window.termTestRequests.maximum, window.termTestRequests.active);
        }
        try { return await originalFetch(...args); }
        finally { if (tracked) window.termTestRequests.active--; }
      };
    });
    const crla = page.locator('#assessmentPeriodFilterWrap');
    const aral = page.locator('#aralTermSelect');
    const choose = async (id, term) => {
      await page.locator(`#${id} .student-filter-trigger`).click();
      await page.locator(`#${id} .student-filter-option[data-value="${term}"]`).click();
    };
    const waitTerms = async (crlaTerm, aralTerm) => {
      try {
        await page.waitForFunction(([c, a]) =>
          document.querySelector('#assessmentPeriodFilterWrap')?.dataset.value === String(c) &&
          document.querySelector('#aralTermSelect')?.dataset.value === String(a), [crlaTerm, aralTerm], { timeout: 10000 });
      } catch (error) {
        const state = await page.evaluate(() => ({
          crla: { ...document.querySelector('#assessmentPeriodFilterWrap')?.dataset },
          aral: { ...document.querySelector('#aralTermSelect')?.dataset },
          calendar: studentDirectoryCalendar, busy: studentDirectorySyncBusy, queued: studentDirectorySyncQueued,
          status: document.querySelector('#crlaFinalizationStatus')?.textContent,
        }));
        throw new Error(`${error.message}: ${JSON.stringify({ state, errors, expected: [crlaTerm, aralTerm] })}`);
      }
    };
    const waitLevel = async level => {
      try {
        await page.waitForFunction(level => document.querySelector('.student-crla-profile-badge')?.textContent === level, level, { timeout: 10000 });
      } catch (error) {
        const state = await page.evaluate(() => ({
          crla: { ...document.querySelector('#assessmentPeriodFilterWrap')?.dataset },
          level: document.querySelector('.student-crla-profile-badge')?.textContent,
          status: document.querySelector('#crlaFinalizationStatus')?.textContent,
          busy: studentDirectorySyncBusy, queued: studentDirectorySyncQueued,
        }));
        throw new Error(`${error.message}: ${JSON.stringify({ state, errors, expected: level, requests: requests.slice(-3).map(url => url.search), responses: responses.slice(-3) })}`);
      }
    };
    const waitIdle = () => page.waitForFunction(() => !studentDirectorySyncBusy && !studentDirectorySyncQueued);
    const exportTerm = async term => {
      await page.waitForFunction(materialId => {
        const button = document.querySelector('#exportStudentsBtn');
        return button?.getAttribute('aria-disabled') === 'false' &&
          new URL(button.href).searchParams.get('material_id') === String(materialId);
      }, materials[term], { timeout: 10000 });
      assert.equal(await page.locator('#exportStudentsBtn').getAttribute('aria-disabled'), 'false');
      const href = await page.locator('#exportStudentsBtn').getAttribute('href');
      assert.equal(new URL(href, base).searchParams.get('material_id'), String(materials[term]));
    };
    const prepareNavigation = async () => {
      await page.evaluate(() => Object.defineProperty(document, 'hidden', { configurable: true, value: true }));
      await waitIdle();
    };
    await page.goto(base + process.env.PABASA_STUDENTS_URL);
    await waitTerms(3, 3);
    await waitLevel('Transitioning Reader');
    await exportTerm(3);
    assert.equal(await crla.getAttribute('data-manual'), 'false');
    assert.equal(await aral.getAttribute('data-manual'), 'false');
    await choose('assessmentPeriodFilterWrap', 1);
    await waitTerms(1, 3);
    await waitLevel('Low Emerging Reader');
    await exportTerm(1);
    await page.waitForTimeout(1200);
    await waitTerms(1, 3);
    await command('term2');
    await waitTerms(1, 2);
    await waitLevel('Low Emerging Reader');
    assert.equal(navigations.length, 1);
    await choose('assessmentPeriodFilterWrap', 2);
    await waitLevel('Developing Reader');
    await exportTerm(2);
    await choose('aralTermSelect', 1);
    await waitTerms(2, 1);
    await waitIdle();
    assert.equal(await page.locator('.aral-review-all-action').isDisabled(), true);
    await page.locator('.aral-bar-group[data-performance-index="0"]').click();
    await page.waitForFunction(() => document.querySelector('#aralStoryPerformanceModalBody').textContent.includes('4/5'));
    await page.locator('#aralStoryPerformanceModal .btn-close').click();
    await page.waitForTimeout(400);
    await command('term3');
    await page.waitForTimeout(1200);
    await waitTerms(2, 1);
    await waitLevel('Developing Reader');
    assert.equal(navigations.length, 1);
    assert.equal(await page.locator('#aralStoryPerformanceModal').count(), 1);
    await prepareNavigation();
    await page.reload();
    await waitTerms(3, 3);
    await waitLevel('Transitioning Reader');
    await prepareNavigation();
    await page.goto(base + process.env.PABASA_STUDENTS_URL + '?term=1&aral_term=2');
    await waitTerms(1, 2);
    await waitLevel('Low Emerging Reader');
    await prepareNavigation();
    await page.reload();
    await waitTerms(1, 2);
    await waitLevel('Low Emerging Reader');
    await prepareNavigation();
    await page.goto(base + process.env.PABASA_STUDENTS_URL);
    await waitTerms(3, 3);
    await command('term1');
    await waitTerms(1, 1);
    await waitLevel('Low Emerging Reader');
    await command('no_term');
    await waitTerms('', '');
    await page.waitForFunction(() => document.querySelector('#crlaFinalizationStatus').textContent === 'No Active Term');
    assert.equal(await page.locator('#exportStudentsBtn').getAttribute('aria-disabled'), 'true');
    assert.equal(await page.locator('.student-card-row').count(), 0);
    await command('term3');
    await waitTerms(3, 3);
    await waitLevel('Transitioning Reader');
    let failed = false;
    await page.route('**/students-api/**', async route => { failed = true; await route.abort(); }, { times: 1 });
    await page.evaluate(() => refreshStudentOverview());
    assert(failed);
    assert.match(await page.locator('#crlaFinalizationStatus').textContent(), /unavailable/);
    assert.equal(await page.locator('#exportStudentsBtn').getAttribute('aria-disabled'), 'true');
    await waitLevel('Transitioning Reader');
    await exportTerm(3);
    await page.route('**/students-api/**', async route => {
      await new Promise(resolve => setTimeout(resolve, 900));
      await route.continue();
    }, { times: 1 });
    await page.evaluate(() => { refreshStudentOverview(); });
    await choose('assessmentPeriodFilterWrap', 1);
    await choose('assessmentPeriodFilterWrap', 2);
    await waitTerms(2, 3);
    await waitLevel('Developing Reader');
    await exportTerm(2);
    assert.equal(await page.evaluate(() => window.termTestRequests.maximum), 1);
    await page.locator('#studentSearchInput').fill('missing learner');
    assert.equal(await page.locator('.student-card-row').count(), 0);
    await page.locator('#studentSearchInput').fill('student');
    assert.equal(await page.locator('.student-card-row').count(), 1);
    assert(requests.some(url => url.searchParams.get('term') === '1' && url.searchParams.get('term_mode') === 'manual'));
    assert(requests.some(url => url.searchParams.get('term_mode') === 'auto'));
    await page.evaluate(() => {
      window.termTestHidden = true;
      Object.defineProperty(document, 'hidden', { configurable: true, get: () => window.termTestHidden });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await waitIdle();
    const paused = requests.length;
    await page.waitForTimeout(1100);
    assert.equal(requests.length, paused);
    await page.evaluate(() => { window.termTestHidden = false; document.dispatchEvent(new Event('visibilitychange')); });
    await page.waitForFunction(() => !studentDirectorySyncBusy);
    await page.waitForTimeout(200);
    assert(requests.length > paused);
    await waitTerms(2, 3);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'passed', scenarios: 19, description: 'active defaults; independent manual terms; historical CRLA and ARAL; export targets; auto calendar changes; no reloads; explicit query terms; fresh reload; no active term; network retry; stale-response protection; no overlapping requests; search; hidden-tab pause; historical records preserved' }));
  } finally { await browser.close(); input.close(); }
})().catch(error => { console.error(error); process.exit(1); });
