// Real Django fixtures/local assets. Progress/completion responses stay in memory;
// controlled responses check the unchanged client flow, not backend grading.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw=require(path.join(runtime,'playwright-core'));
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const url='http://localhost:9877/dashboard/assessment/activity/prescribed/lesson7-gawain4a/';
const fixture=fs.readFileSync(path.join(dir,'lesson7-gawain4a-current.html'),'utf8');
const config=JSON.parse(fixture.match(/<script id="shape-stamp-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
assert.equal(config.cells.length,12);
const dpr=Number(process.env.PABASA_AUDIT_DPR||1),results=[],errors=[],interactions=[];
// Compare this minor refinement with the previous compact layout, reproducibly.
const refinement=process.argv.includes('--refinement'),prefix=refinement?'lesson7-g4a-refinement':'lesson7-g4a';
const compactCss=fs.readFileSync(path.join(assets,'pabasa_app/css/lesson7_gawain4a_responsive.css'),'utf8')
 .replace(/\/\* Moderate desktop refinement:[\s\S]*?\/\* End desktop refinement \*\//,'');
const sizes=[[1366,768],[1440,900],[1536,864],[1680,924],[1200,800],[1920,1080],[2560,1440],[768,1024],[375,812],[3440,1440],[320,568],[2560,1440],[1366,768]];

async function createPage(browser,variant,done=false){
 const context=await browser.newContext({viewport:{width:1366,height:768},deviceScaleFactor:dpr,reducedMotion:'reduce'});
 let placements={},completionMode='reject';
 await context.route('**/*',route=>{
  const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
  if(u.pathname.startsWith('/static/')){
   if(variant==='before'&&u.pathname.endsWith('/lesson7_gawain4a_responsive.css'))return route.fulfill({contentType:'text/css',body:refinement?compactCss:''});
   const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key);assert.ok(file.startsWith(assets+path.sep));
   return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
  }
  if(u.href===url){let html=fixture;if(done)html=html.replace(/(<script id="shape-stamp-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,json,b)=>{const data=JSON.parse(json);data.progress={...(data.progress||{}),activity_completed:true};return a+JSON.stringify(data)+b});return route.fulfill({contentType:'text/html',body:html})}
  if(u.pathname===config.progress_url){const value=route.request().postDataJSON();placements={...(value.state?.placements||{})};return route.fulfill({json:{success:true}})}
  if(u.pathname===config.completion_url)return completionMode==='accept'?route.fulfill({json:{success:true}}):route.fulfill({status:400,json:{success:false,error:'Fixture: try again'}});
  return route.fulfill({json:{success:true}});
 });
 await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const audio=new Native(...args);audio.play=()=>{setTimeout(()=>audio.dispatchEvent(new Event('ended')),15);return Promise.resolve()};return audio};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{}});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
 const gate=page.locator('.lesson-start-actions button');if(await gate.count()&&await gate.first().isVisible())await gate.first().click();if(!done)await page.locator('.tool[data-shape="square"]:not(:disabled)').waitFor();
 return{page,context,getPlacements:()=>placements,acceptCompletion:()=>completionMode='accept'};
}

async function inspect(page){return page.evaluate(()=>{
 const rect=e=>e.getBoundingClientRect().toJSON(),card=document.querySelector('#app');
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width&&r.height&&s.display!=='none'&&s.visibility!=='hidden'};
 const colors=e=>Object.fromEntries(['color','backgroundColor','borderColor','borderStyle','fontFamily','fontWeight'].map(k=>[k,getComputedStyle(e)[k]]));
 return{card:rect(card),nav:rect(document.querySelector('.back')),tools:rect(document.querySelector('.session3-controls-tools')),scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
  cells:[...card.querySelectorAll('.cell')].map(e=>({id:e.dataset.id,letter:e.querySelector('.cell-letter').textContent,rect:rect(e),glyph:rect(e.querySelector('.cell-letter')),font:getComputedStyle(e).fontSize,colors:colors(e)})),
  components:[...card.querySelectorAll('.eyebrow,h1,.toolbox,.tool,.tool .shape,.sheet,#submit,.numbered-progress')].filter(visible).map(e=>({cls:e.className,id:e.id,rect:rect(e),font:getComputedStyle(e).fontSize,colors:colors(e)})),
  containers:[card,...card.querySelectorAll('.sheet,.toolbox')].map(e=>({cls:e.className,rect:rect(e),scroll:[e.scrollWidth,e.scrollHeight],client:[e.clientWidth,e.clientHeight],overflow:[getComputedStyle(e).overflowX,getComputedStyle(e).overflowY]})),
  columns:getComputedStyle(card.querySelector('.sheet')||card).gridTemplateColumns};
})}

async function clearStamps(page){while(await page.locator('.cell .stamp').count()){const id=await page.locator('.cell:has(.stamp)').first().getAttribute('data-id');await page.locator(`.cell[data-id="${id}"]`).click();await page.locator(`.cell[data-id="${id}"] .stamp`).waitFor({state:'detached'})}}
async function drop(page,shape,id){await page.locator(`.tool[data-shape="${shape}"]`).dragTo(page.locator(`.cell[data-id="${id}"]`));await page.locator(`.cell[data-id="${id}"] .stamp.${shape}`).waitFor();const box=await page.locator(`.cell[data-id="${id}"]`).boundingBox(),stamp=await page.locator(`.cell[data-id="${id}"] .stamp`).boundingBox();assert.ok(stamp.x>=box.x&&stamp.y>=box.y&&stamp.x+stamp.width<=box.x+box.width&&stamp.y+stamp.height<=box.y+box.height,'Stamp outside tile')}

(async()=>{const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});try{
 for(const variant of ['before','after']){
  const env=await createPage(browser,variant),page=env.page;
  for(const [width,height]of sizes){
   if(variant==='after')await clearStamps(page);
   await page.setViewportSize({width,height});await page.mouse.move(0,0);await page.waitForTimeout(180);await page.evaluate(()=>window.scrollTo(0,0));
   const r={width,height,variant,dpr,...await inspect(page)};
   const debug=page.locator('.session3-controls-debug');await debug.evaluate(e=>e.hidden=false);r.debugCard=await page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate(e=>e.hidden=true);
   results.push(r);await page.screenshot({path:path.join(dir,`${prefix}-${width}x${height}-dpr${dpr}-${variant}.png`),fullPage:width<1000,animations:'disabled'});
   if(variant==='after'){
    const b=results.find(x=>x.variant==='before'&&x.width===width&&x.height===height);
    assert.deepEqual(r.cells.map(c=>[c.id,c.letter]),config.cells.map(c=>[c.id,c.letter]),'Letter tiles/order changed');assert.equal(r.columns.split(' ').length,3,'Three-column grid changed');assert.deepEqual(r.debugCard,r.card,'Debug panel moved card');assert.ok(r.scroll[0]<=width,'Horizontal page overflow');assert.ok(Math.abs(r.card.x+r.card.width/2-width/2)<1,'Card horizontal centering');
    const content=[...r.cells.map(c=>c.rect),...r.components.map(c=>c.rect)];for(const box of content)assert.ok(box.x>=r.card.x-1&&box.right<=r.card.right+1&&box.y>=r.card.y-1&&box.bottom<=r.card.bottom+1,'Activity content outside card');
    for(const c of r.containers){assert.ok(c.overflow.every(v=>v==='visible'),'Activity uses clipping or internal scrolling');assert.ok(c.scroll[0]<=c.client[0]+1&&c.scroll[1]<=c.client[1]+1,'Internal activity overflow')}
    if(width>=1000){assert.ok(r.scroll[1]<=height,'Desktop scrolling');assert.ok(Math.abs(r.card.y+r.card.height/2-height/2)<1,'Desktop vertical centering')}
    if(width===768||width===375)assert.ok(r.scroll[1]<=height,'Tablet/phone content should fit');
    for(const nav of [r.nav,r.tools])assert.ok(nav.bottom<=r.card.y+1||nav.right<=r.card.x||nav.x>=r.card.right,'Navigation overlaps activity');
    for(let i=0;i<r.cells.length;i++){assert.deepEqual(r.cells[i].colors,b.cells[i].colors,'Tile visual style changed');assert.ok(parseFloat(r.cells[i].font)>=30,'Letters too small');assert.ok(r.cells[i].rect.height>=44,'Tile hit target too short')}
    for(let i=0;i<r.components.length;i++)assert.deepEqual(r.components[i].colors,b.components[i].colors,'Component visual style changed');
    if(refinement){
     if(width>=1200&&height>=800){
      const ratio=(a,b)=>a/b;
      assert.ok(ratio(r.card.width,b.card.width)>=1.10&&ratio(r.card.width,b.card.width)<=1.15,'Card width refinement outside 10–15%');
      assert.ok(ratio(r.card.height,b.card.height)>=1.08&&ratio(r.card.height,b.card.height)<=1.15,'Card height refinement exceeds moderate growth');
      for(let i=0;i<r.cells.length;i++){
       assert.ok(Math.abs(ratio(r.cells[i].rect.height,b.cells[i].rect.height)-1.2)<.002,'Tile height did not grow 20%');
       assert.ok(Math.abs(ratio(parseFloat(r.cells[i].font),parseFloat(b.cells[i].font))-1.18)<.002,'Letter font did not grow 18%');
      }
      for(let i=0;i<r.components.length;i++){
       const now=r.components[i],old=b.components[i];
       if(now.cls.startsWith('shape '))assert.ok(Math.abs(ratio(now.rect.width,old.rect.width)-1.15)<.002,'Shape did not grow 15%');
       if(now.cls==='')assert.deepEqual([now.rect.height,now.font],[old.rect.height,old.font],'Heading typography changed');
       if(now.id==='submit')assert.deepEqual([now.rect.width,now.rect.height,now.font],[old.rect.width,old.rect.height,old.font],'Submit size changed');
      }
     }else assert.deepEqual([r.card,r.cells,r.components],[b.card,b.cells,b.components],'Compact layout changed on short/narrow viewport');
    }else if(width>=1000){const old=b.components.find(c=>c.cls==='sheet'),grid=r.components.find(c=>c.cls==='sheet');assert.ok(grid.rect.height<old.rect.height*.8,'Grid did not shrink significantly')}
    if(width>=375){
     await drop(page,'square','r1c1');assert.equal(env.getPlacements().r1c1,'square','Square placement not saved');await page.locator('.cell[data-id="r1c1"]').click();await page.locator('.cell[data-id="r1c1"] .stamp').waitFor({state:'detached'});
     await drop(page,'circle','r4c2');assert.equal(env.getPlacements().r4c2,'circle','Last-row circle placement not saved');
     await page.locator('#submit').click();await page.locator('.cell .stamp').waitFor({state:'detached'});await page.locator('#submit:not(:disabled)').waitFor();assert.equal(await page.locator('.cell').count(),12,'Retry removed letters');assert.equal(await page.locator('.done').count(),0,'Rejected answer completed activity');
     interactions.push({width,height,drag_square:true,remove_stamp:true,drag_circle_last_row:true,retry:true});
    }else{await page.locator('#submit').scrollIntoViewIfNeeded();const submit=await page.locator('#submit').boundingBox();assert.ok(submit.y>=0&&submit.y+submit.height<=height+1,'Submit inaccessible through natural scrolling')}
   }
   console.log(`${variant} ${width}x${height}: card ${r.card.width.toFixed(1)}x${r.card.height.toFixed(1)}, grid ${r.components.find(c=>c.cls==='sheet').rect.height.toFixed(1)}, tile ${r.cells[0].rect.height.toFixed(1)}, font ${r.cells[0].font}`);
  }
  if(variant==='after'){
   for(const [id,shape]of Object.entries(config.answer_mapping))await drop(page,shape,id);
   assert.deepEqual(env.getPlacements(),config.answer_mapping,'Correct placements changed');env.acceptCompletion();await page.locator('#submit').click();await page.locator('.done').waitFor();interactions.push({completion:true});
  }await env.context.close();
 }
 for(const variant of ['before','after']){
  const env=await createPage(browser,variant,true);
  for(const [width,height]of [[1366,768],[2560,1440]]){await env.page.setViewportSize({width,height});await env.page.waitForTimeout(100);const r={variant,done:true,width,height,card:await env.page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON()),doneRect:await env.page.locator('.done').evaluate(e=>e.getBoundingClientRect().toJSON())};results.push(r);if(variant==='after'){const b=results.find(x=>x.done&&x.variant==='before'&&x.width===width);assert.deepEqual([r.card,r.doneRect],[b.card,b.doneRect],'Completion layout changed')}}await env.context.close();
 }
 assert.deepEqual(errors,[],'Browser script errors');console.log(`PASS ${results.filter(r=>r.variant==='after').length} layouts, ${interactions.length} interaction scenarios`);
 }finally{await browser.close();fs.writeFileSync(path.join(dir,`${prefix}-responsive-dpr${dpr}.json`),JSON.stringify({results,interactions,errors},null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
