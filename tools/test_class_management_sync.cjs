// Functional browser test; launched only by its disposable Django live-server test.
const assert = require('node:assert/strict');
const readline = require('node:readline');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const input = readline.createInterface({input:process.stdin});
const command = name => new Promise(resolve => { input.once('line', resolve); console.log(JSON.stringify({command:name})); });
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const base = process.env.PABASA_SYNC_SERVER;
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addCookies([{name:'sessionid',value:process.env.PABASA_SYNC_COOKIE,url:base}]);
    const page = await context.newPage();
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.url().includes('/students-api/')) requests.push(new URL(request.url()));
    });
    await page.goto(base + process.env.PABASA_SYNC_URL);
    const waitCount = count => page.waitForFunction(n => document.querySelector('#enrolledStudentCount')?.textContent === `${n} enrolled`, count);
    const rows = page.locator('.student-table tbody tr[data-student-id]');
    const visibleRows = () => page.locator('.student-table tbody tr[data-student-id]:not([hidden])');
    const readingRow = page.locator(`.student-table tbody tr[data-student-id="${process.env.PABASA_SYNC_STUDENT}"]`);
    const waitLevel = (term, level) => page.waitForFunction(({id,term,level}) => {
      const row = document.querySelector(`.student-table tbody tr[data-student-id="${id}"]`);
      const card = document.querySelector(`.student-cards [data-student-id="${id}"]`);
      return document.querySelector('#sectionCalendar').textContent.endsWith(`Term ${term}`) &&
        row?.querySelector('.reading-level-chip').textContent === level &&
        card?.querySelector('.reading-level-chip').textContent === level;
    }, {id:process.env.PABASA_SYNC_STUDENT,term,level});
    await waitCount(12);
    assert.deepEqual(await page.locator('.section-information-students thead th').allTextContents(),
      ['Name','PABASA ID','Email','Reading Level','Year-End Outcome','Actions']);
    await waitLevel(1,'Low Emerging Reader');
    await page.waitForTimeout(1200); // Settle the initial calendar response.
    await page.locator('#enrolledStudentSearch').fill('SYNC-student');
    await page.locator('#studentSort').selectOption('reading');
    await command('term2');
    await waitLevel(2,'Pending');
    await command('term2_started');
    await page.waitForTimeout(1200);
    await waitLevel(2,'Pending');
    await command('term2_finalized');
    await waitLevel(2,'Developing Reader');
    assert.equal(await page.locator('#enrolledStudentSearch').inputValue(),'SYNC-student');
    assert.equal(await page.locator('#studentSort').inputValue(),'reading');
    assert.equal(await visibleRows().count(),1);
    await command('term3');
    await waitLevel(3,'Pending');
    await command('term3_finalized');
    await waitLevel(3,'Transitioning Reader');
    assert.match(await readingRow.locator('.student-year-end-outcome').textContent(),/Not Finalized/);
    assert.equal(await readingRow.locator('td').count(),6);
    await command('aral_exit');
    await page.waitForTimeout(1200);
    await waitLevel(3,'Transitioning Reader');
    await waitCount(12);
    await page.locator('#enrolledStudentSearch').fill('');
    await page.locator('#studentSort').selectOption('name');
    assert(requests.every(url => url.searchParams.get('section_id') === process.env.PABASA_SYNC_SECTION));
    assert(requests.length > 5, 'Existing one-second poll runs');
    assert(requests.filter(url => url.searchParams.has('include_calendar')).length <= 2, 'Calendar is throttled');
    await rows.first().evaluate(node => { window.originalStudentRow = node; });
    await page.waitForTimeout(2100);
    assert(await page.evaluate(() => originalStudentRow.isConnected), 'Unchanged snapshots preserve row identity');
    await command('enroll');
    await waitCount(13);
    const search = page.locator('#enrolledStudentSearch');
    await search.fill('newcomer');
    assert.equal(await visibleRows().count(),1);
    await page.locator('#studentSort').selectOption('pabasa');
    await page.locator('#studentSortDirection').click();
    await command('metadata');
    await page.waitForFunction(() => document.querySelector('.student-table tbody').textContent.includes('updated@sync.example.invalid'));
    assert.equal(await search.inputValue(),'newcomer');
    assert.equal(await visibleRows().count(),1);
    assert.equal(await page.locator('#studentSort').inputValue(),'pabasa');
    assert.equal(await page.locator('#studentSortDirection').getAttribute('aria-pressed'),'true');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.locator('.student-card[data-student-id]:not([hidden])').count(),1, 'Mobile filters nonmatches');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.setViewportSize({width:1440,height:1000});
    await search.fill('');
    await page.locator('#studentPagination [aria-label="Page 2"]').click();
    assert.equal(await visibleRows().count(),3);
    await page.waitForTimeout(1100);
    assert.equal(await page.locator('#studentPagination [aria-current="page"]').textContent(),'2');
    await page.waitForFunction(() => !!window.bootstrap?.Modal);
    const dropped = await visibleRows().first().getAttribute('data-student-id');
    await visibleRows().first().locator('.drop-student-btn').click();
    await page.locator('#dropStudentModal').waitFor({state:'visible'});
    await page.locator('#continueDropStudentButton').click();
    await waitCount(12);
    assert.equal(await page.locator(`.section-information-students [data-student-id="${dropped}"]`).count(),0);
    await page.locator('#dropStudentSuccessOk').click();
    await command('transfer');
    await waitCount(11);
    await command('reactivate');
    await waitCount(12);
    const ids = await rows.evaluateAll(nodes => nodes.map(node => node.dataset.studentId));
    assert.equal(new Set(ids).size,ids.length);
    assert.equal(await page.locator('.student-card[data-student-id]').count(),12);

    // Network failures preserve the last successful roster and expose a retry.
    await page.route('**/students-api/**', route => route.fulfill({status:503,contentType:'application/json',body:'{"success":false}'}));
    await page.waitForFunction(() => !document.querySelector('#studentSyncRetry').hidden);
    await waitCount(12);
    await page.unroute('**/students-api/**');
    await page.locator('#studentSyncRetry').click();
    await page.waitForFunction(() => document.querySelector('#studentSyncRetry').hidden);
    await command('no_term');
    // Explicit retry requests calendar immediately rather than waiting 15 seconds.
    await page.evaluate(() => window.dispatchEvent(new Event('studentEnrollmentChanged')));
    await page.waitForFunction(() => document.querySelector('#sectionCalendar').textContent.endsWith('No Active Term'));
    await waitCount(12);

    // Hold a request across multiple timer ticks: the poll must never overlap.
    let held = null, inFlight = 0, maximum = 0;
    await page.route('**/students-api/**', async route => {
      inFlight++; maximum = Math.max(maximum,inFlight);
      if (!held) held = route;
      else { await route.continue(); inFlight--; }
    });
    await page.evaluate(() => window.dispatchEvent(new Event('studentEnrollmentChanged')));
    await page.waitForTimeout(2300);
    assert.equal(maximum,1);
    await held.continue(); inFlight--;
    await page.unroute('**/students-api/**');
    await page.waitForTimeout(300);

    // A hidden tab aborts/pauses; visibility refreshes immediately with calendar.
    await page.evaluate(() => {
      window.testHidden = true;
      Object.defineProperty(document, 'hidden', {configurable:true,get:()=>window.testHidden});
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.waitForTimeout(200);
    const paused = requests.length;
    await page.waitForTimeout(1600);
    assert.equal(requests.length,paused);
    await page.evaluate(() => { window.testHidden=false; document.dispatchEvent(new Event('visibilitychange')); });
    await page.waitForFunction(() => document.querySelector('#studentSyncRetry').hidden);
    await page.waitForTimeout(250);
    assert(requests.length > paused);
    assert(requests.slice(paused).some(url => url.searchParams.has('include_calendar')));
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({result:'passed', scenarios:22, description:'six columns; term 1/2/3 CRLA and Pending transitions; incomplete assessment; ARAL exit; year-end status; calendar; enrollment; transfer; reactivation; counts; search; sort; pagination; Drop Student; mobile; stable DOM; retry; section scope; overlap; visibility'}));
  } finally { await browser.close(); input.close(); }
})().catch(error => { console.error(error); process.exit(1); });
