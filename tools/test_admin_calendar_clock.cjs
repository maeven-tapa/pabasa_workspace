// Called by tests_admin_calendar_clock.py: all sessions/overrides are disposable.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');

(async () => {
  const server = process.env.PABASA_CALENDAR_SERVER;
  assert(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(server), 'Disposable local server required');
  const browser = await chromium.launch({channel:'chrome', headless:!process.env.PABASA_CALENDAR_HEADED});
  const context = await browser.newContext({timezoneId:'America/Los_Angeles', viewport:{width:1440,height:1000}});
  await context.addCookies([{name:'sessionid',value:process.env.PABASA_CALENDAR_COOKIE,url:server}]);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  let timeRequests = 0;
  page.on('request', r => { if (r.url().endsWith('/dashboard/admin/system-time/')) timeRequests++; });
  const line = page.locator('.calendar-server-now-line');
  const status = page.locator('#calendarClockStatus');
  const title = () => page.locator('#calendarMonthTitle').textContent();
  const synchronized = () => page.waitForFunction(() =>
    document.querySelector('#calendarClockStatus').textContent.includes('server time (Asia/Manila)'));
  const checkPosition = async expectedDay => {
    const result = await (await page.waitForFunction(expectedDay => {
      const n = document.querySelector('.calendar-server-now-line');
      if (!n || n.closest('[data-date]')?.dataset.date !== expectedDay) return false;
      const stamp = n.dataset.serverTime;
      const [h,m,s] = stamp.slice(11,19).split(':').map(Number);
      const row = document.querySelector(`.fc-timegrid-slot-lane[data-time="${String(h).padStart(2,'0')}:${m<30?'00':'30'}:00"]`);
      const r = row.getBoundingClientRect();
      return {stamp,day:n.closest('[data-date]').dataset.date,
        highlighted:n.closest('[data-date]').classList.contains('fc-day-today'),
        actual:n.getBoundingClientRect().top,expected:r.top+r.height*((m%30)*60+s)/1800};
    },expectedDay)).jsonValue();
    assert.equal(result.day,expectedDay);
    assert.equal(result.highlighted,true,'Today highlighting must follow the server date');
    assert(Math.abs(result.actual-result.expected)<2,JSON.stringify(result));
    return result;
  };
  const artifacts = process.env.PABASA_CALENDAR_ARTIFACTS;
  const screenshot = async name => {
    if (!artifacts) return;
    fs.mkdirSync(artifacts,{recursive:true});
    // The line deliberately moves every second; do not require a stable box.
    await line.evaluate(n => n.scrollIntoView({block:'center'}));
    await page.screenshot({path:path.join(artifacts,name+'.png')});
  };
  const settingsPage = await context.newPage();
  const setOverride = async value => {
    await settingsPage.goto(server+'/dashboard/admin/settings/');
    const token = await settingsPage.locator('[name=csrfmiddlewaretoken]').first().inputValue();
    const response = await context.request.post(server+'/dashboard/admin/settings/', {
      headers:{'X-CSRFToken':token}, form:{settings_action:'save_system_time_debug',
        ...(value ? {system_time_debug_enabled:'on',system_time_debug_value:value} : {})},
    });
    assert.equal(response.status(),200);
    await page.bringToFront();
  };
  try {
    // Mock Date while timers and performance.now continue normally.
    await page.clock.setFixedTime(new Date('2001-06-15T03:00:00Z'));
    await page.goto(server+'/dashboard/admin/calendar/');
    await synchronized();
    assert.equal(await line.count(),0,'Month should have no line');
    await page.locator('#calendarWeekBtn').click();
    const initial = await checkPosition('2040-01-02');
    assert.match(initial.stamp,/T15:20:/);
    assert.equal(await page.evaluate(() => new Date().getFullYear()),2001);
    assert.equal(await page.evaluate(() => Intl.DateTimeFormat().resolvedOptions().timeZone),'America/Los_Angeles');
    await screenshot('server-1520-client-2001-los-angeles');

    await page.waitForTimeout(2200);
    const moving = await checkPosition('2040-01-02');
    assert(Date.parse(moving.stamp)>Date.parse(initial.stamp),'Line must advance with a fixed client clock');
    await page.clock.setFixedTime(new Date('2099-12-31T23:59:00Z'));
    await page.waitForTimeout(1100);
    const skewed = await checkPosition('2040-01-02');
    assert(Date.parse(skewed.stamp)-Date.parse(moving.stamp)<5000,'Client clock jump moved line');

    const currentTitle = await title();
    await page.locator('#calendarNextBtn').click();
    await page.waitForTimeout(200);
    assert.equal(await line.count(),0,'Other weeks must have no line');
    await page.locator('#calendarPrevBtn').click();
    await checkPosition('2040-01-02');
    assert.equal(await title(),currentTitle);
    await page.locator('#calendarYearBtn').click();
    assert.equal(await line.count(),0,'Year should have no line');
    await page.locator('#calendarWeekBtn').click();
    await checkPosition('2040-01-02');

    // Real settings endpoint changes the application override while calendar stays open.
    await setOverride('2040-01-02T17:45');
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await synchronized();
    assert.match((await checkPosition('2040-01-02')).stamp,/T17:45:/);

    // Exercise the regular poll without a focus/visibility notification.
    await setOverride('2040-01-02T18:10');
    await page.waitForFunction(() => document.querySelector('.calendar-server-now-line')?.dataset.serverTime.includes('T18:10:'),null,{timeout:35000});
    await checkPosition('2040-01-02');

    // Failed requests hide an existing line and communicate the failure.
    await page.route('**/dashboard/admin/system-time/', r => r.fulfill({status:503,body:'unavailable'}));
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => document.querySelector('#calendarClockStatus').textContent.includes('unavailable'));
    assert.equal(await line.count(),0);
    // Initial load failure must also avoid falling back to midnight/client time.
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#calendarClockStatus').textContent.includes('unavailable'));
    await page.locator('#calendarWeekBtn').click();
    assert.equal(await line.count(),0);
    await page.unroute('**/dashboard/admin/system-time/');
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await synchronized();
    await checkPosition('2040-01-02');

    await context.setOffline(true);
    await page.waitForFunction(() => document.querySelector('#calendarClockStatus').textContent.includes('hidden'));
    assert.equal(await line.count(),0);
    await context.setOffline(false);
    await synchronized();
    await checkPosition('2040-01-02');

    // Simulate a suspended/background tab; discard the sample until resumed.
    await page.evaluate(() => {
      Object.defineProperty(document,'hidden',{configurable:true,value:true});
      document.dispatchEvent(new Event('visibilitychange'));
    });
    assert.equal(await line.count(),0);
    await setOverride('2040-01-09T09:30');
    await page.evaluate(() => {
      delete document.hidden;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await synchronized();
    assert.equal(await title(),currentTitle,'Resync must preserve week navigation');
    assert.equal(await line.count(),0,'Override moved to a date outside displayed week');
    await page.locator('#calendarTodayBtn').click();
    await synchronized();
    await checkPosition('2040-01-09');
    await screenshot('override-next-week-0930');

    // Cross Manila midnight and a week boundary while the page stays open.
    // Jan 7, 2040 is Saturday; advancing this anchor crosses into Sunday.
    await setOverride('2040-01-07T23:59');
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await synchronized();
    await page.locator('#calendarTodayBtn').click();
    await synchronized();
    await checkPosition('2040-01-07');
    await page.waitForTimeout(62000);
    assert.equal(await line.count(),0,'Line should leave the old week after Sunday midnight');
    await page.locator('#calendarNextBtn').click();
    const midnight = await checkPosition('2040-01-08');
    assert.match(midnight.stamp,/T00:00:/);
    await screenshot('manila-midnight');
    await setOverride(null);
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
    await synchronized();
    assert.equal(await line.count(),0,'Real clock is outside the simulated week');
    const realTime = await (await context.request.get(server+'/dashboard/admin/system-time/')).json();
    await page.locator('#calendarTodayBtn').click();
    await synchronized();
    await checkPosition(realTime.server_time.slice(0,10));
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({result:'passed',clientTimezone:'America/Los_Angeles',clientClocks:[2001,2099],
      timeRequests,initial,moving,skewed,midnight,checks:'movement, navigation, Month/Year, override polling, failure/recovery, offline/reconnect, tab resume, midnight, override disabled'}));
  } catch (error) {
    console.error(await page.evaluate(() => ({
      status:document.querySelector('#calendarClockStatus')?.textContent,
      columns:[...document.querySelectorAll('.fc-timegrid-col')].map(n=>n.dataset.date),
      rows:[...document.querySelectorAll('.fc-timegrid-slots tr')].slice(0,2).map(n=>n.outerHTML),
      containers:document.querySelectorAll('.fc-timegrid-now-indicator-container').length,
    })));
    if (artifacts) {
      fs.mkdirSync(artifacts,{recursive:true});
      await page.screenshot({path:path.join(artifacts,'clock-failure.png')});
    }
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exit(1);});
