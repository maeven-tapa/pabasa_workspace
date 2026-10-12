// Run through the disposable Django browser test, never against a real student.
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
(async()=>{
  assert(process.env.PABASA_CALENDAR_SERVER && process.env.PABASA_CALENDAR_COOKIE);
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    const base=process.env.PABASA_CALENDAR_SERVER;
    const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1.2});
    const errors=[], mutations=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(request.url().startsWith(base)&&!['GET','HEAD'].includes(request.method()))mutations.push(request.method()+' '+new URL(request.url()).pathname);});
    await page.context().addCookies([{name:'sessionid',value:process.env.PABASA_CALENDAR_COOKIE,url:base}]);
    await page.goto(base+process.env.PABASA_CALENDAR_URL);
    await page.waitForFunction(()=>!!window.bootstrap?.Modal);
    const modal=page.locator('#studentCalendarModal'), date=iso=>modal.locator(`[data-calendar-date="${iso}"]`);
    const open=async()=>{
      await modal.evaluate(node=>{node.dataset.testOpened='false';node.addEventListener('shown.bs.modal',()=>{node.dataset.testOpened='true';},{once:true});});
      await page.locator('[data-bs-target="#studentCalendarModal"]').click();
      await modal.waitFor({state:'visible'});
      await page.waitForFunction(()=>document.querySelector('#studentCalendarModal').dataset.testOpened==='true');
    };
    await open();
    assert.equal((await modal.locator('#studentCalendarModalLabel').textContent()).trim(),'Aking Kalendaryo');
    assert.equal(await modal.locator('#studentCalendarModalLabel .bi-calendar3').count(),1);
    assert.equal(await modal.locator('.student-calendar-mini-legend i.bi').count(),5);
    assert.equal(await modal.locator('.student-calendar-date-grid').evaluate(node=>getComputedStyle(node).gridTemplateRows.split(' ').length),6);
    assert.equal(await modal.locator('.student-gantt-bar').count(),0);
    assert.equal(await date('2026-10-12').getAttribute('aria-current'),'date');
    assert.equal(await date('2026-10-12').getAttribute('aria-pressed'),'true');
    assert.equal(await date('2026-10-12').locator('.student-calendar-more').textContent(),'+3 pa');
    assert.equal(await date('2026-10-12').locator('[data-calendar-kind="assessment"]').count(),1);
    assert.equal(await modal.locator('.student-calendar-detail-card').count(),4);
    assert((await date('2026-10-12').getAttribute('aria-label')).includes('Holiday "Masayang Araw"'));
    assert.equal(await modal.locator('.student-calendar-detail-card b').count(),0);
    assert((await modal.locator('[data-student-calendar-details]').textContent()).includes('<b>Test description</b>'));
    await date('2026-10-18').click();
    assert((await modal.locator('[data-student-calendar-details]').textContent()).includes('Walang nakatakdang gawain sa araw na ito!'));
    await date('2026-10-17').click();
    assert.equal(await modal.locator('.student-calendar-detail-card').count(),1);
    assert((await modal.locator('[data-student-calendar-details]').textContent()).includes('Saturday Holiday'));
    await date('2026-10-16').click();
    assert((await modal.locator('[data-student-calendar-details]').textContent()).includes('Assessment crosses weekend'));
    await date('2026-10-20').click();
    assert((await modal.locator('[data-student-calendar-details]').textContent()).includes('Assessment crosses weekend'));
    await date('2026-10-21').click();
    assert.equal(await modal.locator('.student-calendar-detail-card').count(),0);
    await modal.locator('[data-calendar-nav="prev"]').click();
    await modal.locator('[data-calendar-nav="prev"]').click();
    assert.equal(await modal.locator('[data-calendar-date]').count(),42); // August: six weeks.
    const measure=()=>modal.evaluate(element=>{
      const content=element.querySelector('.modal-content'),body=element.querySelector('.modal-body'),grid=element.querySelector('.student-calendar-date-grid'),legend=element.querySelector('.student-calendar-mini-legend');
      const c=content.getBoundingClientRect(),g=grid.getBoundingClientRect(),l=legend.getBoundingClientRect(),b=body.getBoundingClientRect();
      const cells=[...grid.children].map(node=>node.getBoundingClientRect());
      const scrollable=[...element.querySelectorAll('*')].filter(node=>['auto','scroll'].includes(getComputedStyle(node).overflowY)&&node.scrollHeight>node.clientHeight+2).map(node=>node.className);
      return {viewport:[innerWidth,innerHeight],content:[c.left,c.top,c.right,c.bottom],body:[body.clientHeight,body.scrollHeight],grid:[g.top,g.bottom],legend:[l.top,l.bottom],bodyBounds:[b.top,b.bottom],widths:cells.map(r=>r.width),heights:cells.map(r=>r.height),scrollable,locked:getComputedStyle(document.body).overflow,horizontal:body.scrollWidth<=body.clientWidth+1};
    });
    const desktop=await measure();
    assert(desktop.content[0]>=0&&desktop.content[1]>=0&&desktop.content[2]<=1600&&desktop.content[3]<=900,JSON.stringify(desktop));
    assert(desktop.body[1]<=desktop.body[0]+2,'Six-week calendar must fit at 1920×1080 / 120%: '+JSON.stringify(desktop));
    assert(desktop.legend[1]<=desktop.bodyBounds[1]+1);
    assert(Math.max(...desktop.widths)-Math.min(...desktop.widths)<1);
    assert(Math.max(...desktop.heights)-Math.min(...desktop.heights)<1);
    assert.equal(desktop.locked,'hidden');
    await modal.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'desktop-six-weeks.png')});
    const backgroundBefore=await page.evaluate(()=>[scrollY,document.querySelector('.dashboard-main')?.scrollTop||0]);
    await page.mouse.move(20,850);await page.mouse.wheel(0,500);await page.waitForTimeout(100);
    assert.deepEqual(await page.evaluate(()=>[scrollY,document.querySelector('.dashboard-main')?.scrollTop||0]),backgroundBefore);
    await modal.locator('[data-calendar-nav="next"]').click();
    assert.equal(await modal.locator('[data-calendar-date="2026-09-01"]').count(),1);
    assert((await modal.locator('#studentCalendarExpandedMonth').textContent()).includes('Setyembre'));
    await modal.locator('[data-calendar-nav="today"]').click();
    assert.equal(await date('2026-10-12').getAttribute('aria-pressed'),'true');
    const monthLayout=()=>modal.evaluate(element=>{
      const rect=selector=>element.querySelector(selector).getBoundingClientRect();
      const content=rect('.modal-content'),grid=rect('.student-calendar-date-grid');
      const body=element.querySelector('.modal-body');
      return {width:content.width,height:content.height,gridHeight:grid.height,
        navTop:rect('.student-calendar-navigation').top,detailsTop:rect('.student-calendar-day-details').top,
        bodyOverflow:body.scrollHeight-body.clientHeight};
    });
    const monthWeeks=[['Nobyembre',35],['Disyembre',35],['Enero',42],['Pebrero',35]];
    let stableLayout;
    for(const [month,days] of monthWeeks){
      await modal.locator('[data-calendar-nav="next"]').click();
      assert((await modal.locator('#studentCalendarExpandedMonth').textContent()).includes(month));
      assert.equal(await modal.locator('[data-calendar-date]').count(),days);
      const layout=await monthLayout();
      assert(layout.bodyOverflow<=2,JSON.stringify(layout));
      if(stableLayout)assert.deepEqual(layout,stableLayout,'Modal shifted in '+month);
      stableLayout=layout;
    }
    assert.equal(/[\u{1F300}-\u{1FAFF}]/u.test(await modal.textContent()),false);
    await modal.locator('[data-calendar-nav="today"]').click();
    await modal.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'desktop-events.png')});
    await date('2026-10-12').focus();await page.keyboard.press('ArrowRight');
    assert.equal(await date('2026-10-13').getAttribute('aria-pressed'),'true');
    assert.equal(await date('2026-10-13').evaluate(node=>node===document.activeElement),true);
    await page.keyboard.press('ArrowDown');
    assert.equal(await date('2026-10-20').getAttribute('aria-pressed'),'true');
    for(const viewport of [{width:1366,height:768},{width:390,height:844},{width:320,height:568}]){
      await page.setViewportSize(viewport);
      const layout=await measure();
      assert(layout.content[0]>=0&&layout.content[1]>=0&&layout.content[2]<=viewport.width+1&&layout.content[3]<=viewport.height+1,JSON.stringify(layout));
      assert(layout.horizontal,JSON.stringify(layout));
      assert(layout.scrollable.every(name=>name==='modal-body'),JSON.stringify(layout));
      assert(Math.min(...layout.widths)>=35,JSON.stringify(layout));
      if(viewport.width===390){
        await modal.locator('[data-calendar-nav="today"]').click();
        await date('2026-10-12').click();
        await modal.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'mobile-calendar.png')});
        await modal.locator('.student-calendar-day-details').scrollIntoViewIfNeeded();
        assert.equal(await modal.locator('.student-calendar-detail-card').count(),4);
        await modal.screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'mobile-details.png')});
      }
    }
    await page.setViewportSize({width:1600,height:900});
    await modal.locator('.student-calendar-close-btn').click();
    await modal.waitFor({state:'hidden'});
    await page.waitForFunction(()=>!document.body.classList.contains('student-calendar-open'));
    assert.notEqual(await page.evaluate(()=>getComputedStyle(document.body).overflow),'hidden');
    await open();await page.keyboard.press('Escape');await modal.waitFor({state:'hidden'});
    const touch=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    await touch.addCookies([{name:'sessionid',value:process.env.PABASA_CALENDAR_COOKIE,url:base}]);
    const phone=await touch.newPage();
    phone.on('pageerror',error=>errors.push(error.message));
    await phone.goto(base+process.env.PABASA_CALENDAR_URL);
    await phone.locator('#studentCalendarModal').evaluate(node=>{node.addEventListener('shown.bs.modal',()=>{node.dataset.testOpened='true';},{once:true});});
    await phone.locator('[data-bs-target="#studentCalendarModal"]').waitFor({state:'visible'});
    await phone.locator('[data-bs-target="#studentCalendarModal"]').tap();
    await phone.waitForFunction(()=>document.querySelector('#studentCalendarModal').dataset.testOpened==='true');
    assert.equal(await phone.evaluate(()=>matchMedia('(hover: none)').matches),true);
    await phone.locator('[data-calendar-date="2026-10-18"]').tap();
    assert((await phone.locator('[data-student-calendar-details]').textContent()).includes('Walang nakatakdang gawain sa araw na ito!'));
    await phone.locator('.student-calendar-day-details').scrollIntoViewIfNeeded();
    await phone.locator('#studentCalendarModal .modal-content').screenshot({path:path.join(process.env.PABASA_CALENDAR_ARTIFACTS,'touch-mobile-details.png')});
    await phone.locator('.student-calendar-close-btn').tap();
    await phone.waitForFunction(()=>!document.body.classList.contains('student-calendar-open'));
    await touch.close();
    assert.deepEqual(errors,[]);
    assert.deepEqual(mutations,[]);
    console.log('PASS opened student calendar: scaled desktop/six weeks/laptop/mobile/touch, equal cells, details/multiple/empty dates, inclusive ranges/weekend rules, previous/next/today, keyboard, close/reopen, one internal scrollbar, unchanged event records; no student writes.');
    console.log('Screenshots: '+process.env.PABASA_CALENDAR_ARTIFACTS);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
