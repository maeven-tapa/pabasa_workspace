// Only invoked by tests_admin_calendar_events_browser.py against its disposable DB.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');

(async () => {
  const server = process.env.PABASA_CALENDAR_SERVER;
  assert(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(server), 'Disposable local server required');
  const browser = await chromium.launch({channel:'chrome', headless:!process.env.PABASA_CALENDAR_HEADED});
  const context = await browser.newContext({viewport:{width:1600,height:1000}});
  let page;
  try {
    await context.addCookies([{name:'sessionid',value:process.env.PABASA_CALENDAR_COOKIE,url:server}]);
    page = await context.newPage();
    const errors = [], posts = [], checks = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.url().startsWith(server) && request.method() === 'POST') posts.push(request.url());
    });
    await page.goto(server + process.env.PABASA_CALENDAR_URL);
    await page.locator('.fc-daygrid-day').first().waitFor();
    assert.deepEqual(errors, []);
    const list = page.locator('#calendarEventList');
    const details = page.locator('#yearViewDetailModal');
    const edit = page.locator('#calendarEventModal');
    const view = async name => {
      await page.locator(`#calendar${name}Btn`).click();
      await page.waitForFunction(name => document.querySelector(`#calendar${name}Btn`).getAttribute('aria-pressed') === 'true', name);
      assert.equal(await list.isVisible(), name === 'Week', `${name} list visibility`);
      assert.equal(await list.locator('h2').count(), name === 'Week' ? 1 : 0);
      if (name === 'Week') assert.equal(await list.locator('h2').textContent(), 'Events this week');
    };
    const close = async modal => {
      await modal.locator('.modal-footer [data-bs-dismiss="modal"]').click();
      await modal.waitFor({state:'hidden'});
    };
    const navigate = async (name, date) => {
      await view('Year');
      await page.locator(`.calendar-year-month[data-year-date="${date.slice(0,7)}-01"] .calendar-year-month-name`).click();
      await page.locator('.fc-dayGridMonth-view').waitFor();
      assert.equal(await list.isVisible(), false);
      if (name === 'Week') {
        await page.locator(`.fc-daygrid-day[data-date="${date}"] .fc-daygrid-day-number`).click();
        await page.locator('.fc-timeGridWeek-view').waitFor();
        assert.equal(await list.isVisible(), true);
        assert.equal(await list.locator('h2').textContent(), 'Events this week');
      }
    };
    const novemberOverlap = ['Closing Block', 'Holiday <b>literal</b>', 'ARAL 2'];
    const expectedByDate = {
      '2026-10-07':['Opening Block'],
      '2026-10-21':['Pre-Assessment Week'],
      '2026-10-28':['ARAL 1'],
      '2026-11-01':['Holiday <b>literal</b>'],
      '2026-11-02':novemberOverlap,
      '2026-11-04':[...novemberOverlap, 'Custom event <b>literal</b>'],
      '2026-11-08':['Holiday <b>literal</b>'],
      '2026-11-09':['Holiday <b>literal</b>', 'Midline Assessment Week'],
      '2026-11-10':['Holiday <b>literal</b>', 'Midline Assessment Week'],
      '2026-11-11':['Midline Assessment Week'],
      '2026-11-19':['Overflow A', 'Overflow B', 'Overflow C', 'Overflow Holiday'],
      '2026-12-09':['Post-Assessment Week'],
      '2026-12-16':['Examination Week'],
    };
    const expectDetails = async date => {
      await details.waitFor({state:'visible',timeout:5000});
      const label = new Intl.DateTimeFormat('en-US',{month:'long',day:'numeric',year:'numeric'}).format(new Date(`${date}T12:00:00`));
      assert.equal(await page.locator('#yearViewDetailTitle').textContent(), label);
      assert.equal(await details.locator('.modal-header .text-secondary').textContent(), 'Event schedule for this date.');
      assert.deepEqual(await page.locator('.modal.show').evaluateAll(ns => ns.map(n => n.id)), ['yearViewDetailModal']);
      assert.equal(await details.locator('input, textarea, select, [type="submit"]').count(), 0);
      assert.deepEqual(await details.locator('.modal-footer button').allTextContents(), ['Close']);
      const expected = [...expectedByDate[date]].sort();
      const actual = await details.locator('.calendar-year-detail-item strong').allTextContents();
      assert.deepEqual(actual.sort(), expected, `All events on ${date}`);
      assert.equal(await details.locator('.calendar-year-detail-list b, .calendar-year-detail-list script').count(), 0);
    };
    // Real pointer clicks, including middle days, clipped weeks and wrapped month rows.
    const clickEvent = async (name, title, date) => {
      const header = page.locator(name === 'Week'
        ? `.fc-col-header-cell[data-date="${date}"]` : `.fc-daygrid-day[data-date="${date}"]`);
      const dayBox = await header.boundingBox();
      // Backgrounds have a title attribute but no text content.
      const nodes = /^(Opening|Closing) Block$/.test(title)
        ? page.locator(`#calendar ${name === 'Week' ? '.fc-timegrid-col ' : ''}.fc-bg-event[title="${title}"]`)
        : page.locator('#calendar .fc-event').filter({has:page.locator('.event-pill')}).filter({hasText:title});
      await nodes.first().waitFor({state:'visible',timeout:5000});
      for (const node of await nodes.all()) {
        await node.scrollIntoViewIfNeeded();
        const b = await node.boundingBox();
        const day = await header.boundingBox();
        const x = day.x + day.width / 2;
        if (!b || x < b.x || x >= b.x + b.width) continue;
        if (name === 'Month' && (b.y + b.height <= day.y || b.y >= day.y + day.height)) continue;
        const background = /^(Opening|Closing) Block$/.test(title);
        await node.click({position:{x:x-b.x,y:background ? 8 : Math.min(b.height-2, Math.max(2,b.height/2))},timeout:5000});
        return;
      }
      throw new Error(`No ${name} event ${title} on ${date}; day ${JSON.stringify(dayBox)}`);
    };
    assert.equal(await list.isVisible(), false, 'Initial Month hides list');
    const cases = [
      ['Opening Block','2026-10-07'],
      ['Pre-Assessment Week','2026-10-21'],
      ['ARAL 1','2026-10-28'],
      ['Closing Block','2026-11-04'],
      ['Holiday <b>literal</b>','2026-11-04'],
      ['ARAL 2','2026-11-04'],
      ['Midline Assessment Week','2026-11-11'],
      ['Post-Assessment Week','2026-12-09'],
      ['Examination Week','2026-12-16'],
      ['Holiday <b>literal</b>','2026-11-09'],
      ['Holiday <b>literal</b>','2026-11-10'],
    ];
    for (const name of ['Month','Week']) {
      for (const [title,date] of cases) {
        try {
          await navigate(name,date);
          await clickEvent(name,title,date);
          await expectDetails(date);
        } catch (error) {
          throw new Error(`${name}: ${title} on ${date}: ${error.message}`, {cause:error});
        }
        checks.push(`${name}: ${title} on ${date}`);
        if (process.env.PABASA_CALENDAR_ARTIFACTS && title === 'ARAL 2') {
          fs.mkdirSync(process.env.PABASA_CALENDAR_ARTIFACTS,{recursive:true});
          await page.waitForFunction(() => getComputedStyle(document.querySelector('#yearViewDetailModal')).opacity === '1');
          await page.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,`calendar-${name.toLowerCase()}-details.png`)});
        }
        await close(details);
      }
      await navigate(name,'2026-11-04');
      await clickEvent(name,'Custom event <b>literal</b>','2026-11-04');
      await edit.waitFor({state:'visible'});
      assert.equal(await page.locator('#calendarEventModalTitle').textContent(), 'Edit Event');
      assert.equal(await page.locator('#eventTitle').inputValue(), 'Custom event <b>literal</b>');
      assert.equal(await page.locator('#eventStart').inputValue(), '2026-11-03');
      assert.equal(await page.locator('#eventEnd').inputValue(), '2026-11-05');
      assert.equal(await page.locator('#deleteEventBtn').isVisible(), true);
      assert.equal(await edit.locator('[type="submit"]').isVisible(), true);
      assert.equal(await details.isVisible(), false);
      await close(edit);
      checks.push(`${name}: custom event editing`);
      // Keyboard activation on a clipped segment uses its first visible day.
      await navigate(name,'2026-11-09');
      const holiday = page.locator('#calendar .fc-daygrid-event').filter({hasText:'Holiday <b>literal</b>'});
      await holiday.last().focus();
      await page.keyboard.press('Enter');
      await expectDetails('2026-11-08');
      await close(details);
    }
    // A popover may float above a different column; its own date takes priority.
    await navigate('Month','2026-11-19');
    await page.locator('.fc-daygrid-day[data-date="2026-11-19"] .fc-daygrid-more-link').click();
    await page.locator('.fc-popover .fc-daygrid-event').filter({hasText:'Overflow Holiday'}).click();
    await expectDetails('2026-11-19');
    await close(details);
    // Week list shares the same routing; switching views must remove stale entries.
    await navigate('Week','2026-11-04');
    for (const title of ['Closing Block','Holiday <b>literal</b>','ARAL 2']) {
      await list.locator('button').filter({hasText:title}).click();
      await expectDetails(title === 'Holiday <b>literal</b>' ? '2026-11-01' : '2026-11-02');
      await close(details);
    }
    await list.locator('button').filter({hasText:'Custom event <b>literal</b>'}).click();
    await edit.waitFor({state:'visible'});
    await close(edit);
    await view('Month'); await view('Week'); await view('Year'); await view('Week'); await view('Month');
    await view('Year');
    await page.locator('[data-year-date="2026-11-04"].calendar-year-day').click();
    await expectDetails('2026-11-04');
    await close(details);
    assert.deepEqual(errors, []);
    assert.deepEqual(posts, [], 'Read-only interactions must not mutate events');
    console.log(JSON.stringify({result:'passed',protectedClicks:cases.length*2,customEditViews:2,
      checks,keyboardViews:2,popoverDetails:true,weekListRouting:true,viewSwitches:true,
      yearDetails:true,browser:browser.version()}));
  } catch (error) {
    if (page) {
      if (process.env.PABASA_CALENDAR_ARTIFACTS) {
        fs.mkdirSync(process.env.PABASA_CALENDAR_ARTIFACTS,{recursive:true});
        await page.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'failure.png')});
      }
    }
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exit(1);});
