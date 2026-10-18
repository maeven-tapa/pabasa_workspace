// Invoked only by tests_admin_calendar_browser.py with a disposable database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
(async () => {
  assert(process.env.PABASA_CALENDAR_SERVER && process.env.PABASA_CALENDAR_COOKIE);
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'pabasa-admin-calendar-'));
  const artifacts=process.env.PABASA_CALENDAR_ARTIFACTS;
  if(artifacts)fs.mkdirSync(artifacts,{recursive:true});
  const context=await chromium.launchPersistentContext(profile,{channel:'chrome',headless:!process.env.PABASA_CALENDAR_HEADED,
    viewport:null,args:['--window-size=1600,1000','--force-device-scale-factor=1']});
  let page;
  try {
    page=await context.newPage();
    const settings=await context.newPage();
    await settings.goto('chrome://settings/appearance');
    const zoomOptions=await settings.locator('#zoomLevel').evaluate(n=>[...n.options].map(o=>Number(o.value)));
    const maximum=Math.max(...zoomOptions);
    const errors=[], requests=[];
    page.on('pageerror',error=>{errors.push(error.message);console.error('Browser error:',error.message);});
    page.on('request',r=>{
      if(r.url().startsWith(process.env.PABASA_CALENDAR_SERVER)&&r.method()==='POST'){
        const body=r.postData()||'';
        requests.push(body.match(/name="action"\r?\n\r?\n([^\r\n]+)/)?.[1] || new URLSearchParams(body).get('action'));
      }
    });
    // The model stores dates only. These transient UI fixtures exercise FullCalendar's
    // timed and overnight rendering without inventing time fields in the database.
    await page.addInitScript(()=>document.addEventListener('DOMContentLoaded',()=>{
      const calendarId=window.PABASA_CALENDAR_EVENTS?.[0]?.school_calendar_id;
      if(!calendarId)return;
      window.PABASA_CALENDAR_EVENTS?.push(
        {id:'test-timed',school_calendar_id:calendarId,event_type:'other',title:'Timed meeting',start:'2026-10-12T09:00:00',end:'2026-10-12T10:30:00',allDay:false},
        {id:'test-overlap',school_calendar_id:calendarId,event_type:'other',title:'Overlapping meeting',start:'2026-10-12T09:30:00',end:'2026-10-12T11:00:00',allDay:false},
        {id:'test-overnight',school_calendar_id:calendarId,event_type:'other',title:'Overnight meeting',start:'2026-10-13T23:00:00',end:'2026-10-14T01:00:00',allDay:false});
    }));
    await context.addCookies([{name:'sessionid',value:process.env.PABASA_CALENDAR_COOKIE,url:process.env.PABASA_CALENDAR_SERVER}]);
    const url=process.env.PABASA_CALENDAR_SERVER+process.env.PABASA_CALENDAR_URL;
    const load=async()=>{await page.goto(url);await page.locator('.fc-daygrid-day').first().waitFor();};
    const view=async name=>{await page.locator('#calendar'+name+'Btn').click();await page.waitForTimeout(150);};
    const title=()=>page.locator('#calendarMonthTitle').textContent();
    const navigate=async id=>{
      const before=await title();
      await page.locator('#calendar'+id+'Btn').click();
      await page.waitForFunction(previous=>document.querySelector('#calendarMonthTitle').textContent!==previous,before);
    };
    const weekDates=()=>page.locator('#calendar .fc-col-header-cell').evaluateAll(ns=>ns.map(n=>n.dataset.date));
    const week=async()=>{await view('Week');assert.deepEqual(await weekDates(),['2026-10-11','2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16','2026-10-17']);};
    const snapshot=async label=>{
      const m=await page.evaluate(()=>{
        const rect=n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,top:r.top,bottom:r.bottom};};
        const root=document.querySelector('#calendar'),stage=document.querySelector('.calendar-stage');
        return {viewport:innerWidth,dpr:devicePixelRatio,zoom:getComputedStyle(document.querySelector('.admin-app-shell')).zoom,
          calendar:rect(root),stage:rect(stage),pageOverflow:document.documentElement.scrollWidth-innerWidth,
          mainOverflow:document.querySelector('.admin-main').scrollWidth-document.querySelector('.admin-main').clientWidth,
          headers:[...root.querySelectorAll('.fc-col-header-cell')].map(rect),
          columns:[...root.querySelectorAll('.fc-timegrid-col[data-date]')].map(rect),
          allDay:[...root.querySelectorAll('.fc-daygrid-day')].slice(0,7).map(rect),
          scrollers:[...root.querySelectorAll('.fc-scroller')].map(n=>n.scrollWidth-n.clientWidth),
          view:document.querySelector('#calendarYearBtn').getAttribute('aria-pressed')==='true'?'Year':document.querySelector('#calendarWeekBtn').getAttribute('aria-pressed')==='true'?'Week':'Month'};
      });
      assert(m.pageOverflow<=1 && m.mainOverflow<=1,label+': page overflow '+JSON.stringify(m));
      assert.equal(m.zoom,'1','Unexpected ancestor CSS zoom');
      if(m.view!=='Year'){
        assert.equal(m.headers.length,7,label);
        assert(m.headers[0].left>=m.calendar.left-1 && m.headers[6].right<=m.calendar.right+1,label+': clipped header '+JSON.stringify(m));
        // At 25%, a one-device-pixel table border occupies four CSS pixels.
        const edgeTolerance=Math.max(3,1/m.dpr+1);
        assert(Math.abs(m.headers[6].right-m.calendar.right)<edgeTolerance,label+': unused right-hand space '+JSON.stringify(m));
        assert(Math.max(...m.headers.map(r=>r.width))-Math.min(...m.headers.map(r=>r.width))<1,label+': uneven days');
        assert(m.scrollers.every(overflow=>overflow<=1),label+': horizontal calendar scrolling');
        if(m.view==='Week')assert.equal(m.columns.length,7,label);
        for(let i=0;i<7;i++)for(const row of m.view==='Week'?[m.columns,m.allDay]:[m.allDay]){
            assert(Math.abs(row[i].left-m.headers[i].left)<2 && Math.abs(row[i].right-m.headers[i].right)<2,label+': misaligned day '+i);
        }
      }
      return {label,view:m.view,viewport:m.viewport,dpr:m.dpr,calendarWidth:Math.round(m.calendar.width),pageOverflow:m.pageOverflow};
    };
    const screenshot=async name=>{
      if(!artifacts)return;
      await page.bringToFront();
      await page.locator('.calendar-stage').evaluate(n=>n.scrollIntoView({block:'start',behavior:'instant'}));
      await page.waitForTimeout(200);
      // captureScreenshot uses device-independent pixels, not cssLayoutViewport
      // coordinates. The legacy layoutViewport supplies the correctly zoomed clip.
      const cdp=await context.newCDPSession(page);
      const {layoutViewport:v}=await cdp.send('Page.getLayoutMetrics');
      const clip={x:v.pageX,y:v.pageY,width:v.clientWidth,height:v.clientHeight,scale:1};
      const capture=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false,clip});
      fs.writeFileSync(path.join(artifacts,name+'.png'),Buffer.from(capture.data,'base64'));
      await cdp.detach();
    };
    await load();await week();
    assert.match(await title(),/Oct 11.*17, 2026/);
    await snapshot('initial');
    const suspension=page.locator('.calendar-event-item').filter({hasText:'Class Suspension'});
    assert.equal(await suspension.count(),1);
    assert.equal(await page.locator('.fc-timegrid-col[data-date="2026-10-12"] .fc-timegrid-event').count(),2);
    assert.equal(await page.locator('.fc-timegrid-col[data-date="2026-10-13"] .fc-timegrid-event').count(),1);
    assert.equal(await page.locator('.fc-timegrid-col[data-date="2026-10-14"] .fc-timegrid-event').count(),1);
    const timed=await page.locator('.fc-timegrid-col[data-date="2026-10-12"] .fc-timegrid-event').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,text:n.textContent};}));
    assert(timed[0].right<=timed[1].left+1||timed[1].right<=timed[0].left+1,'Overlapping timed events hide each other');
    assert(timed.some(r=>/9/.test(r.text)),'Timed event must display time');
    const slot=await page.locator('.fc-timegrid-slot-lane[data-time="09:00:00"]').boundingBox();
    assert(Math.abs(Math.min(...timed.map(r=>r.top))-slot.y)<4,'Incorrect timed event hour');
    const spans=await page.locator('.fc-daygrid-event').filter({hasText:'Pre-Assessment Week'}).evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return [r.left,r.right];}));
    const headers=await page.locator('.fc-col-header-cell').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return [r.left,r.right];}));
    assert.equal(spans.length,2,'Suspension splits the assessment');
    assert(Math.abs(spans[0][0]-headers[0][0])<8&&Math.abs(spans[0][1]-headers[2][1])<8,'First all-day segment should span Sun–Tue');
    assert(Math.abs(spans[1][0]-headers[4][0])<8&&Math.abs(spans[1][1]-headers[6][1])<8,'Second all-day segment should span Thu–Sat');
    await navigate('Next');assert.match(await title(),/Oct 18.*24, 2026/);
    await navigate('Prev');await navigate('Prev');assert.match(await title(),/Oct 4.*10, 2026/);
    await navigate('Today');await week();
    await view('Month');await navigate('Prev');await navigate('Prev');
    assert.equal(await page.locator('.fc-daygrid-day').count(),42,'August has six rows');
    await page.locator('.fc-daygrid-day[data-date="2026-08-31"] .fc-daygrid-day-number').focus();
    await page.keyboard.press('Enter');
    await page.locator('.fc-timeGridWeek-view').waitFor();
    assert.deepEqual((await weekDates()).filter((_,i)=>i===0||i===6),['2026-08-30','2026-09-05']);
    assert.match(await title(),/Aug 30.*Sep 5/);
    await navigate('Today');await view('Month');
    await navigate('Next');await navigate('Next');
    await page.locator('.fc-daygrid-day[data-date="2026-12-31"] .fc-daygrid-day-number').click();
    await page.locator('.fc-timeGridWeek-view').waitFor();
    assert.match(await title(),/2026.*2027/);
    await navigate('Today');
    await view('Year');assert.equal(await page.locator('#calendar').isVisible(),false);
    assert.equal(await page.locator('.calendar-year-month').count(),11);
    assert.equal(await page.locator('#calendarPrevBtn').isDisabled(),true);
    await view('Week');await week();
    const literal=page.locator('.calendar-event-item').filter({hasText:'Long <b>literal</b>'});
    assert.equal(await literal.locator('b').count(),0);
    await literal.click();await page.locator('#calendarEventModal').waitFor({state:'visible'});
    assert.match(await page.locator('#eventTitle').inputValue(),/Long <b>literal<\/b>/);
    assert.equal(await page.locator('#eventStart').inputValue(),'2026-10-13');
    assert.equal(await page.locator('#eventEnd').inputValue(),'2026-10-13');
    await page.locator('#calendarEventModal [data-bs-dismiss="modal"]').first().click();
    await page.locator('#calendarEventModal').waitFor({state:'hidden'});
    // Exercise real save/edit/delete against the disposable DB, including segments.
    await page.locator('#addEventBtn').click();
    assert.equal(await page.locator('#eventType').inputValue(),'other');
    await page.locator('#eventTitle').fill('Temporary regression event');
    await page.locator('#eventStart').fill('2026-10-12');await page.locator('#eventEnd').fill('2026-10-13');
    await page.locator('#calendarEventForm [type="submit"]').click();
    await page.locator('#calendarEventModal').waitFor({state:'hidden'});
    const temp=page.locator('.calendar-event-item').filter({hasText:'Temporary regression event'});
    assert.equal(await temp.count(),1);
    await temp.click();assert.equal(await page.locator('#eventEnd').inputValue(),'2026-10-13');
    await page.locator('#eventEnd').fill('2026-10-15');
    await page.locator('#calendarEventForm [type="submit"]').click();await page.locator('#calendarEventModal').waitFor({state:'hidden'});
    assert.match(await temp.textContent(),/Oct 12.*Oct 15/);
    const canonical=await page.evaluate(()=>window.PABASA_CALENDAR_EVENTS);
    assert(canonical.every(e=>!String(e.id).includes('-segment-')&&!String(e.id).includes('-background')),'Rendered segments leaked into source events');
    assert(canonical.find(e=>e.event_type==='pre_assessment').end_date==='2026-10-20');
    await temp.click();await page.locator('#deleteEventBtn').click();
    await page.locator('#calendarConfirmButton').click();await page.locator('#calendarEventModal').waitFor({state:'hidden'});
    assert.equal(await temp.count(),0);
    assert.equal(await suspension.count(),1);
    await suspension.click();await page.locator('#calendarConfirmModal').waitFor({state:'visible'});
    await page.locator('#calendarConfirmModal [data-bs-dismiss="modal"]').first().click();
    await page.locator('#calendarConfirmModal').waitFor({state:'hidden'});
    await page.locator('#addSuspensionBtn').click();await page.locator('#suspensionModal').waitFor({state:'visible'});
    await page.locator('#suspensionModal [data-bs-dismiss="modal"]').first().click();await page.locator('#suspensionModal').waitFor({state:'hidden'});
    await page.locator('#editTermBlocksBtn').click();await page.locator('#termBlocksModal').waitFor({state:'visible'});
    await page.locator('#termBlocksModal [data-bs-dismiss="modal"]').first().click();await page.locator('#termBlocksModal').waitFor({state:'hidden'});
    const results=[];
    for(const zoom of [...new Set([.25,1,1.25,2,maximum])]){
      await settings.locator('#zoomLevel').selectOption(String(zoom));
      await load();
      assert(Math.abs(await page.evaluate(()=>devicePixelRatio)-zoom)<.02,'Expected real browser zoom '+zoom);
      for(const collapsed of [false,true]){
        // At high zoom the desktop sidebar becomes an offcanvas. Preserve both saved states.
        const toggle=page.locator('.admin-app-shell > .admin-sidebar [data-admin-collapse-btn]');
        const current=await page.locator('body').evaluate(n=>n.classList.contains('admin-sidebar-collapsed'));
        if(current!==collapsed){
          if(await toggle.isVisible())await toggle.click();
          else await page.evaluate(value=>document.body.classList.toggle('admin-sidebar-collapsed',value),collapsed);
          await page.waitForTimeout(350);
        }
        for(const name of ['Month','Week','Year']){
          await view(name);
          results.push(await snapshot(`${zoom*100}%, sidebar ${collapsed?'collapsed':'expanded'}`));
          if(!collapsed && [1,2,maximum].includes(zoom))await screenshot(`zoom-${zoom*100}-${name.toLowerCase()}`);
        }
        if(zoom>=2){
          await page.locator('.mobile-admin-menu-btn').click();
          await page.locator('#adminSidebarCanvas.show').waitFor();
          assert.equal(await page.locator('#adminSidebarCanvas').isVisible(),true);
          await page.keyboard.press('Escape');await page.locator('#adminSidebarCanvas').waitFor({state:'hidden'});
        }
      }
    }
    await settings.locator('#zoomLevel').selectOption('1');
    for(const width of [320,375,768,1024]){
      await page.setViewportSize({width,height:900});await load();
      const toggle=page.locator('.admin-app-shell > .admin-sidebar [data-admin-collapse-btn]');
      if(width===1024 && await page.locator('body').evaluate(n=>n.classList.contains('admin-sidebar-collapsed'))){
        await toggle.click();await page.waitForTimeout(350);
      }
      for(const name of ['Month','Week','Year']){await view(name);results.push(await snapshot(`narrow ${width}`));}
      if(width===320){await view('Week');await screenshot('narrow-320-week');}
      if(width===1024){
        await view('Week');
        const before=(await page.locator('#calendar').boundingBox()).width;
        await toggle.click();await page.waitForTimeout(350);
        results.push(await snapshot('1024 sidebar transition without window resize'));
        assert((await page.locator('#calendar').boundingBox()).width>before+150,'Sidebar transition did not resize calendar');
      }
    }
    // A truly empty month displays an explicit state and still allows navigation.
    await view('Month');await navigate('Prev');await navigate('Prev');await navigate('Prev');await navigate('Prev');
    assert.match(await page.locator('#calendarEmpty').textContent(),/No events scheduled/);
    assert.equal(await page.locator('#calendarEmpty').isVisible(),true);
    const years=await page.locator('#schoolYearNavigation option').evaluateAll(ns=>ns.filter(n=>/^\d+$/.test(n.value)).map(n=>({value:n.value,text:n.textContent})));
    const historical=years.find(item=>item.text.includes('2025-2026'));
    await page.locator('#schoolYearNavigation').locator('..').locator('.custom-device-trigger').click();
    await page.locator(`#schoolYearNavigation`).locator('..').locator(`.custom-device-option[data-value="${historical.value}"]`).click();
    await page.waitForURL(new RegExp('calendar_id='+historical.value));
    await page.locator('#startTermBtn').waitFor();
    assert.equal(await page.locator('#addEventBtn').isDisabled(),true);
    assert.equal(await page.locator('#addSuspensionBtn').isDisabled(),true);
    await view('Year');
    assert.equal(await page.locator('#calendarEmpty').isVisible(),true);
    assert.deepEqual(errors,[]);
    assert.deepEqual(requests,['save_event','save_event','delete_event']);
    const report={result:'passed',browser:context.browser().version(),maximumZoom:maximum*100,layoutChecks:results.length,results};
    if(artifacts)fs.writeFileSync(path.join(artifacts,'browser-results.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } catch(error) {
    if(artifacts && page)await page.screenshot({path:path.join(artifacts,'failure.png')}).catch(()=>{});
    throw error;
  } finally {
    await context.close();
    assert.equal(path.dirname(path.resolve(profile)),path.resolve(os.tmpdir()));
    assert(path.basename(profile).startsWith('pabasa-admin-calendar-'));
    fs.rmSync(profile,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exit(1);});
