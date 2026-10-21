// Real Django-rendered template and local assets in Chrome. All provider,
// recording and progress responses are isolated in memory.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw=require(path.join(runtime,'playwright-core'));
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const fixture=fs.readFileSync(path.join(dir,'lesson-4-gawain-1-current.html'),'utf8');
const data=JSON.parse(fixture.match(/<script id="lesson-four-data"[^>]*>([\s\S]*?)<\/script>/)[1]);assert.equal(data.items.length,6);
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const dpr=Number(process.env.PABASA_AUDIT_DPR||1),audit=process.argv.includes('--audit');
const sizes=[[1366,768],[1440,900],[1680,920],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812]]
 .filter(([w])=>!process.env.PABASA_L4_WIDTHS||process.env.PABASA_L4_WIDTHS.split(',').includes(String(w)));
const url='http://localhost:9877/dashboard/assessment/lesson-4/gawain-1/';
const results=[],errors=[],interactions=[];
async function settle(page){
 await page.mouse.move(0,0);
 await page.evaluate(async()=>{
  await document.fonts.ready;document.activeElement?.blur();
  await Promise.all([...document.images].map(i=>i.complete?null:i.decode().catch(()=>{})));
  document.getAnimations().forEach(a=>{if(a.constructor.name==='CSSTransition')a.finish();else{a.pause();a.currentTime=0;}});
  window.scrollTo(0,0);document.querySelectorAll('html,body,.page,#app').forEach(e=>e.scrollTop=0);
  await new Promise((resolve,reject)=>{let prev='',stable=0,start=performance.now();function frame(){
   const next=JSON.stringify([...document.querySelectorAll('#app,#app *')].map(e=>{const r=e.getBoundingClientRect();return[r.x,r.y,r.width,r.height,getComputedStyle(e).font];}));
   stable=next===prev?stable+1:0;prev=next;if(stable>=6)return resolve();if(performance.now()-start>15000)return reject(Error('Unstable layout'));requestAnimationFrame(frame);
  }requestAnimationFrame(frame);});
 });
}
async function inspect(page){return page.evaluate(()=>{
 const app=document.querySelector('#app'),rect=e=>e?.getBoundingClientRect().toJSON(),visible=e=>{const r=rect(e),s=getComputedStyle(e);return r.width&&r.height&&s.visibility!=='hidden'&&s.display!=='none';};
 const style=e=>Object.fromEntries(['fontFamily','fontSize','fontWeight','lineHeight','border','borderRadius','background','color','padding','gap','boxShadow'].map(k=>[k,getComputedStyle(e)[k]]));
 const start=app.querySelector('#start'),progress=app.querySelector('.numbered-progress'),read=app.querySelector('#read'),listen=app.querySelector('#listen'),label=read?.querySelector('[data-basahin-label]');
 const region=document.querySelector('.page'),s=getComputedStyle(region),nav=document.querySelector('.page>.back');
 return{card:rect(app),cardStyle:style(app),nav:rect(nav),tools:rect(document.querySelector('.prescribed-s4-tools')),
  page:rect(region),pageStyle:Object.fromEntries(['display','height','minHeight','padding','gridTemplateRows','rowGap'].map(k=>[k,s[k]])),
  scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],progress:app.querySelectorAll('.numbered-progress__circle').length,
  startProgressGap:start&&progress?rect(progress).top-rect(start).bottom:null,
  typography:read&&listen?{read:style(read),label:style(label),listen:style(listen),labelRect:rect(label),readRect:rect(read),listenRect:rect(listen)}:null,
  parts:[...app.querySelectorAll('.head,.eyebrow,h1,.overview .wheel,.overview .wheel *,.focus-picture,.focus-picture img,.controls,.question,.lesson4-audio-actions,button,.numbered-progress,.numbered-progress__circle,.complete-card')].filter(visible)
   .map(e=>({tag:e.tagName,id:e.id,cls:e.className,text:e.textContent,src:e.getAttribute('src'),rect:rect(e),style:style(e)}))};
 });}
async function record(page){await page.locator('#read:not(:disabled)').waitFor();await page.locator('#read').click();}
(async()=>{const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});try{
 for(const [width,height]of sizes)for(const variant of audit?['before']:['before','after']){
  const saved=[],scriptErrors=[];let correct=true,held=false,release=null;
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:'reduce'});
  await context.route('**/*',async route=>{const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
   if(u.pathname.startsWith('/static/')){
    if(variant==='before'&&u.pathname.endsWith('/lesson4_gawain1_spacing.css'))return route.fulfill({contentType:'text/css',body:''});
    const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key);assert.ok(file.startsWith(assets+path.sep));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
   }
   if(u.href===url)return route.fulfill({contentType:'text/html',body:fixture});
   if(u.pathname.includes('/transcribe/')){if(held)await new Promise(resolve=>release=resolve);return route.fulfill({json:{success:true,complete:correct,transcript:'fixture'}});}
   if(u.pathname.includes('activity-progress')&&route.request().method()==='POST')saved.push(route.request().postDataJSON());
   return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}});
  });
  await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{setTimeout(()=>a.dispatchEvent(new Event('ended')),15);return Promise.resolve();};return a;};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};});
  const page=await context.newPage();page.on('pageerror',e=>scriptErrors.push(e.message));await page.goto(url,{waitUntil:'load'});
  await page.evaluate(()=>{window.Basahin={...window.Basahin,openMicrophone:async()=>({getTracks:()=>[{stop(){}}]}),capture:async({button})=>{window.BasahinButton.setState(button,'processing');return new Blob(['fixture'],{type:'audio/webm'});},attachStreamResult:()=>{}};});
  await page.locator('.lesson-start-actions button').first().click();await page.locator('#start:not(:disabled)').waitFor();
  async function capture(state,w=width,h=height){
   await settle(page);const r={variant,state,width:w,height:h,dpr,...await inspect(page)};
   const debug=page.locator('.prescribed-s4-debug-panel');assert.equal(await debug.count(),1);const old=await debug.evaluate(e=>e.hidden);await debug.evaluate(e=>e.hidden=!e.hidden);
   r.debugCard=await page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate((e,v)=>e.hidden=v,old);assert.deepEqual(r.debugCard,r.card);
   const b=results.find(b=>b.variant==='before'&&b.state===state&&b.width===w&&b.height===h);
   if(variant==='after'){
    fs.writeFileSync(path.join(dir,'lesson4-g1-spacing-latest.json'),JSON.stringify(r,null,2));
    assert.ok(r.scroll[0]<=w,'Horizontal overflow');assert.equal(r.card.width,b.card.width,'Outer card width changed');
    if(state.startsWith('intro')){
     assert.ok(r.card.height<b.card.height,'Intro card remains stretched');assert.equal(r.progress,6);
     assert.ok(Math.abs(r.card.x+r.card.width/2-w/2)<1,'Intro horizontal centering');
     const availableTop=r.page.y+parseFloat(r.pageStyle.padding)+parseFloat(r.pageStyle.gridTemplateRows)+(parseFloat(r.pageStyle.rowGap)||0),availableBottom=r.page.bottom-parseFloat(getComputedBottom(r));
     if(w>=768){assert.ok(r.scroll[1]<=h,'Intro desktop/tablet scrolling');assert.ok(Math.abs(r.card.y+r.card.height/2-(availableTop+availableBottom)/2)<2,'Intro available-viewport centering');}
     assert.ok(r.startProgressGap>=12&&r.startProgressGap<=28,'Progress remains separated from Magsimula');
    }else if(w<=480){assert.deepEqual([r.card.width,r.card.height],[b.card.width,b.card.height],'Phone card dimensions changed');}
    else assert.deepEqual(r.card,b.card,'Main activity card geometry changed');
    if(r.tools&&r.nav)assert.ok(r.nav.bottom<=r.tools.y||r.nav.y>=r.tools.bottom||r.nav.right<=r.tools.x||r.nav.x>=r.tools.right,'Navigation covered by tools');
    assert.equal(r.parts.length,b.parts.length,'Activity elements changed');
    for(let i=0;i<r.parts.length;i++){
     const p=r.parts[i],old=b.parts[i],read=p.id==='read',isLabel=p.tag==='SPAN'&&p.cls.includes('basahin');
     const now={...p.style},prev={...old.style};if(read||isLabel)for(const k of ['fontFamily','fontSize','fontWeight','lineHeight']){delete now[k];delete prev[k];}
     assert.deepEqual([p.tag,p.id,p.cls,p.text,p.src,p.rect.width,p.rect.height,now],[old.tag,old.id,old.cls,old.text,old.src,old.rect.width,old.rect.height,prev],`Changed component: ${p.cls}/${p.id}`);
     if(!state.startsWith('intro')){
      if(w<=480){assert.ok(Math.abs((p.rect.y-old.rect.y)-(r.card.y-b.card.y))<1&&Math.abs((p.rect.x-old.rect.x)-(r.card.x-b.card.x))<1,'Phone content arrangement changed');}
      else assert.deepEqual(p.rect,old.rect,`Main activity shifted: ${p.cls}`);
     }
     assert.ok(p.rect.x>=r.card.x-1&&p.rect.right<=r.card.right+1&&p.rect.y>=r.card.y-1&&p.rect.bottom<=r.card.bottom+1,`Clipped ${p.cls}`);
    }
    if(r.typography){
     for(const k of ['fontFamily','fontSize','fontWeight','lineHeight'])assert.equal(r.typography.read[k],r.typography.listen[k],`Read/Listen mismatch: ${k}`);
     for(const k of ['fontFamily','fontSize','fontWeight','lineHeight'])assert.equal(r.typography.label[k],r.typography.listen[k],`Nested label mismatch: ${k}`);
     assert.ok(r.typography.labelRect.x>=r.typography.readRect.x&&r.typography.labelRect.right<=r.typography.readRect.right,'Label clipped');
    }
   }
   results.push(r);await page.screenshot({path:path.join(dir,`lesson4-g1-spacing-${state}-${w}x${h}-dpr${dpr}-${variant}.png`),fullPage:w<1000,animations:'disabled'});
   console.log(`${variant} ${state} ${w}x${h}: card ${r.card.width.toFixed(2)}x${r.card.height.toFixed(2)}, progress gap ${r.startProgressGap}, fonts ${r.typography?.read.fontSize}/${r.typography?.listen.fontSize}`);
  }
  await capture('intro');
  if(!audit&&width===2560){for(const [w,h]of [[1440,900],[2560,1440]]){await page.setViewportSize({width:w,height:h});await capture('intro-resized',w,h);}}
  await page.locator('#start').click();await page.locator('#read:not(:disabled)').waitFor();await capture('active0');
  if(!audit){
   await page.locator('#listen:not(:disabled)').click();await page.locator('#read:not(:disabled)').waitFor();
   correct=false;held=true;await record(page);await page.waitForFunction(()=>document.querySelector('#read')?.dataset.basahinState==='processing');while(!release)await page.waitForTimeout(10);await capture('processing');held=false;release();release=null;
   await page.locator('#read:not(:disabled)').waitFor();assert.equal(await page.evaluate(()=>index),0,'Wrong reading advanced');correct=true;
   await record(page);await page.locator('.choice:not(:disabled)').first().waitFor();await capture('classify');
   await page.locator('.choice[data-answer="no"]').click();await page.locator('.choice:not(:disabled)').first().waitFor();assert.equal(await page.evaluate(()=>index),0,'Wrong classification advanced');
   await page.locator('.choice[data-answer="yes"]').click();await page.locator('#read:not(:disabled)').waitFor();assert.equal(await page.evaluate(()=>index),1,'Correct classification failed');assert.ok(saved.some(s=>s.current_index===1));
   interactions.push({variant,width,height,start:true,listen:true,processing:true,rejected_read:true,rejected_classification:true,progression:true});
   if([1920,2560].includes(width))for(let i=1;i<6;i++){
    await page.evaluate(i=>{index=i;started=true;phase='read';render();},i);await page.locator('#read:not(:disabled)').waitFor();await capture('active'+i);
   }
   if([1366,2560].includes(width)){
    await page.evaluate(()=>{index=total;render();});await page.locator('.complete-card').waitFor();await capture('completion');
   }
  }
  errors.push({variant,width,height,errors:scriptErrors});await context.close();
 }
 if(!audit)for(const r of errors.filter(r=>r.variant==='after'))assert.deepEqual(r.errors,errors.find(b=>b.variant==='before'&&b.width===r.width&&b.height===r.height).errors,'New browser errors');
 console.log(`PASS ${results.filter(r=>r.variant==='after').length} current layouts; ${interactions.filter(r=>r.variant==='after').length} native interaction groups`);
 }finally{await browser.close();fs.writeFileSync(path.join(dir,`lesson4-g1-spacing-${audit?'audit':`dpr${dpr}`}.json`),JSON.stringify({results,errors,interactions},null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});
function getComputedBottom(r){const p=r.pageStyle.padding.split(' ').map(parseFloat);return p.length>2?p[2]:p[0];}
