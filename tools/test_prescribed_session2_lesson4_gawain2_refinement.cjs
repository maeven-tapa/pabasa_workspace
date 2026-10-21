// Chrome renders real Django templates. Audio, recording and saved progress
// stay in memory; no provider or account data is used by this regression.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const pw = require(path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
const root = path.resolve(__dirname, '..'), dir = path.join(root, 'tmp/prescribed-responsive-audit');
const assets = path.join(root, 'pabasa_site/pabasa_app/static');
const aliases = JSON.parse(fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static_image_aliases.json')));
const css = fs.readFileSync(path.join(assets, 'pabasa_app/css/session2_activity_spacing.css'), 'utf8');
const oldCss = css.replace(/\/\* Lesson 4 Gawain 2 already[\s\S]*?(?=\/\* Lesson 5's intro)/, '');
assert.notEqual(css, oldCss, 'Missing focused refinement rules');
const key = 'session-2-lesson-4-gawain-2';
const fixture = fs.readFileSync(path.join(dir, key + '-current.html'), 'utf8');
const data = JSON.parse(fixture.match(/<script id="activity-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
assert.equal(data.items.length, 6);
const url = 'http://localhost:9877/dashboard/assessment/activity/prescribed/' + key + '/';
const dpr = Number(process.env.PABASA_AUDIT_DPR || 1), results = [], interactions = [], errors = [], neighbors = [];
const sizes = [[320,568],[375,812],[768,1024],[1024,768],[1366,768],[1440,900],[1536,864],[1680,922],[1920,1080],[2560,1440],[3440,1440]]
  .filter(([w]) => !process.env.PABASA_S2L4G2_WIDTHS || process.env.PABASA_S2L4G2_WIDTHS.split(',').includes(String(w)));
const neighborsOnly = process.argv.includes('--neighbors-only');
if(neighborsOnly) {
  const previous=JSON.parse(fs.readFileSync(path.join(dir,`s2l4g2-refinement-dpr${dpr}.json`),'utf8'));
  for(const [width,height]of sizes)for(const variant of ['before','after']) {
    for(const state of ['disabled','enabled','playback','processing','choices'])assert.ok(previous.results.some(r=>r.variant===variant&&r.width===width&&r.height===height&&r.state===state),'Incomplete prior main-activity checks');
    assert.ok(previous.interactions.some(r=>r.variant===variant&&r.width===width&&r.height===height),'Incomplete prior interactions');
  }
  assert.ok(previous.errors.every(r=>r.errors.length===0),'Prior browser errors');
  results.push(...previous.results);interactions.push(...previous.interactions);errors.push(...previous.errors);
}
async function settle(page) {
  await page.mouse.move(0, 0);
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(i => i.complete ? null : i.decode().catch(() => {})));
    document.activeElement?.blur(); document.getAnimations().forEach(a => { a.pause(); a.currentTime = 0; });
    window.scrollTo(0, 0);
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.waitForTimeout(80);
}
async function inspect(page) { return page.evaluate(() => {
  const rect = e => e?.getBoundingClientRect().toJSON();
  const card = document.querySelector('.page>.card'), region = document.querySelector('.page');
  const style = e => Object.fromEntries(['fontFamily','fontSize','fontWeight','lineHeight','backgroundColor','color','border','borderRadius','boxShadow','padding','objectFit','opacity'].map(k => [k, getComputedStyle(e)[k]]));
  const visible = e => { const r = rect(e), s = getComputedStyle(e); return r.width && r.height && s.display !== 'none' && s.visibility !== 'hidden'; };
  const progress = card.querySelector('.numbered-progress'), picture = card.querySelector('.image-card'), actions = card.querySelector('#actions');
  const s = getComputedStyle(region);
  return {card:rect(card), cardStyle:style(card), nav:rect(document.querySelector('.page>.activity-topbar')), tools:rect(document.querySelector('.prescribed-s4-tools')),
    page:rect(region), padding:[parseFloat(s.paddingTop),parseFloat(s.paddingBottom)], gap:parseFloat(s.rowGap)||0,
    scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
    pictureButtonGap:actions&&picture?rect(actions).top-rect(picture).bottom:null,
    buttonProgressGap:progress ? rect(progress).top-rect(actions).bottom : null,
    bottomSpace:progress ? rect(card).bottom-rect(progress).bottom : null,
    parts:[...card.querySelectorAll('.eyebrow,h1,.image-card,#picture,#word,#actions>button,.numbered-progress,.numbered-progress__circle,.complete-screen')].filter(visible)
      .map(e => ({id:e.id,cls:e.className,tag:e.tagName,text:e.textContent,src:e.getAttribute('src'),disabled:e.disabled,state:e.dataset.basahinState,rect:rect(e),style:style(e)}))};
}); }
function contrast(a,b) {
  const lum = c => c.match(/[\d.]+/g).slice(0,3).map(Number).map(v => v/255).map(v => v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i) => sum+v*[.2126,.7152,.0722][i],0);
  const x=lum(a),y=lum(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
}
(async () => {
  const browser = await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try { for (const [width,height] of neighborsOnly?[]:sizes) for (const variant of ['before','after']) {
    let correct = false, holdTranscript = false, releaseTranscript; const saved = [], scriptErrors = [];
    const context = await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:'reduce'});
    context.setDefaultTimeout(10000);
    await context.route('**/*', async route => {
      const u = new URL(route.request().url()); if (u.origin !== 'http://localhost:9877') return route.abort();
      if (u.pathname.startsWith('/static/')) {
        if (u.pathname.endsWith('/session2_activity_spacing.css')) return route.fulfill({contentType:'text/css',body:variant==='before'?oldCss:css});
        const k=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[k]||k);assert.ok(file.startsWith(assets+path.sep));
        return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
      }
      if (u.href === url) return route.fulfill({contentType:'text/html',body:fixture});
      if (u.pathname.includes('/transcribe/')) { if(holdTranscript) await new Promise(r=>releaseTranscript=r);return route.fulfill({json:{success:true,complete:correct,transcript:correct?data.items[0].word:'fixture-rejected'}}); }
      if (u.pathname === new URL(data.progress_url,url).pathname && route.request().method()==='POST') {
        const body=route.request().postDataJSON(); saved.push(body);
        return route.fulfill({json:{success:true,accepted:body.action==='oral'?correct:body.choice===data.items[body.item_index].answer}});
      }
      return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}});
    });
    await context.addInitScript(() => {
      window.__holdAudio=true;
      const Native=window.Audio; window.Audio=function(...args) {const a=new Native(...args);a.play=()=>{setTimeout(()=>{if(window.__holdAudio)window.__pendingAudio=a;else a.dispatchEvent(new Event('ended'));},15);return Promise.resolve();};return a;};
      if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};
    });
    const page=await context.newPage();page.on('pageerror',e=>scriptErrors.push(e.message));await page.goto(url,{waitUntil:'load'});
    await page.evaluate(() => {window.Basahin={...window.Basahin,openMicrophone:async()=>({getTracks:()=>[{stop(){}}]}),capture:async({button})=>{window.BasahinButton.setState(button,'processing');return new Blob(['fixture'],{type:'audio/webm'});},attachStreamResult:()=>{}};});
    await page.locator('.lesson-start-actions button').first().click();await page.locator('#oral').waitFor();
    async function capture(state,w=width,h=height) {
      await settle(page);const r={variant,state,width:w,height:h,dpr,...await inspect(page)};
      const debug=page.locator('.prescribed-s4-debug-panel');const hidden=await debug.evaluate(e=>e.hidden);await debug.evaluate(e=>e.hidden=!e.hidden);
      assert.deepEqual(await page.locator('.page>.card').evaluate(e=>e.getBoundingClientRect().toJSON()),r.card,'Debug overlay moved card');await debug.evaluate((e,v)=>e.hidden=v,hidden);
      if(variant==='after') {
        const b=results.find(x=>x.variant==='before'&&x.state===state&&x.width===w&&x.height===h);assert.ok(b);
        assert.ok(r.scroll[0]<=w,'Horizontal overflow');assert.ok(Math.abs(r.card.x+r.card.width/2-w/2)<1,'Horizontal centering');
        assert.equal(r.card.width,b.card.width,'Card width changed');assert.equal(r.parts.length,b.parts.length,'Visible components changed');
        if(state!=='completion') {
          assert.ok(r.card.height<b.card.height,'Card remains stretched');assert.ok(r.bottomSpace>=24&&r.bottomSpace<=40,'Excess space beneath progress');
          if(state!=='choices')assert.ok(r.pictureButtonGap>=16&&r.pictureButtonGap<=24,'Picture/action spacing');assert.ok(r.buttonProgressGap>=10&&r.buttonProgressGap<=20,'Progress spacing');
          if(w>=768) {assert.ok(r.scroll[1]<=h,'Unnecessary desktop/tablet scrolling');const top=r.nav.bottom+r.gap,bottom=r.page.bottom-r.padding[1];assert.ok(Math.abs(r.card.y+r.card.height/2-(top+bottom)/2)<1,'Available viewport centering');}
        } else { assert.deepEqual(r.card,b.card,'Completion changed'); }
        for(let i=0;i<r.parts.length;i++) {
          const p=r.parts[i],old=b.parts[i],nowStyle={...p.style},oldStyle={...old.style};
          if(p.disabled&&p.cls.includes('oral-button')&&(!p.state||['idle','model'].includes(p.state))) {
            r.disabledContrast=contrast(nowStyle.color,nowStyle.backgroundColor);assert.ok(r.disabledContrast>=4.5,'Disabled text contrast: '+JSON.stringify(nowStyle));
            assert.ok(r.disabledContrast>contrast(oldStyle.color,oldStyle.backgroundColor));delete nowStyle.color;delete oldStyle.color;
          }
          assert.deepEqual([p.id,p.cls,p.tag,p.text,p.src,p.disabled,p.state,p.rect.width,p.rect.height,nowStyle],[old.id,old.cls,old.tag,old.text,old.src,old.disabled,old.state,old.rect.width,old.rect.height,oldStyle],'Activity component changed: '+p.id+'/'+p.cls);
          assert.ok(p.rect.x>=r.card.x-1&&p.rect.right<=r.card.right+1&&p.rect.y>=r.card.y-1&&p.rect.bottom<=r.card.bottom+1,'Clipped '+p.id);
        }
      }
      results.push(r);await page.screenshot({path:path.join(dir,`s2l4g2-refinement-${state}-${w}x${h}-dpr${dpr}-${variant}.png`),fullPage:w<1100,animations:'disabled'});
      console.log(`${variant} ${state} ${w}x${h}: card ${r.card.height.toFixed(2)}, bottom ${r.bottomSpace?.toFixed(2)}, contrast ${r.disabledContrast?.toFixed(2)}`);
    }
    const finishAudio=()=>page.evaluate(()=>{window.__holdAudio=false;window.__pendingAudio?.dispatchEvent(new Event('ended'));window.__pendingAudio=null;});
    await capture('disabled');await finishAudio();await page.locator('#oral:not(:disabled)').waitFor();await capture('enabled');
    if(width===2560) {for(const [w,h]of [[1440,900],[2560,1440]]) {await page.setViewportSize({width:w,height:h});await capture('resized',w,h);}}
    await page.evaluate(()=>window.__holdAudio=true);await page.locator('#listen').click();await page.waitForFunction(()=>!!window.__pendingAudio);await capture('playback');await finishAudio();await page.locator('#oral:not(:disabled)').waitFor();
    holdTranscript=true;await page.locator('#oral').click();await page.waitForFunction(()=>document.querySelector('#oral')?.dataset.basahinState==='processing');while(!releaseTranscript)await page.waitForTimeout(10);await capture('processing');holdTranscript=false;releaseTranscript();
    await page.locator('#oral:not(:disabled)').waitFor();assert.equal(saved.at(-1).action,'oral');assert.equal(saved.at(-1).item_index,0);
    correct=true;await page.locator('#oral').click();await page.locator('#actions button[data-v]:not(:disabled)').first().waitFor();await capture('choices');
    const right=data.items[0].answer;assert.ok(right,'Fixture choice missing');const wrong=data.items[0].choices.find(v=>v!==right);
    await page.locator('#actions button').filter({hasText:wrong}).click();await page.locator('#actions button[data-v]:not(:disabled)').first().waitFor();assert.equal(saved.at(-1).item_index,0);
    await page.locator('#actions button').filter({hasText:right}).click();await page.locator('#oral:not(:disabled)').waitFor();assert.equal(saved.at(-1).choice,right);
    assert.equal(await page.locator('#picture').getAttribute('src'),data.items[1].image_url,'Correct choice did not advance');
    if([1920,2560].includes(width)) {
      for(let i=1;i<data.items.length;i++) {
        await capture('item'+(i+1));await page.locator('#oral').click();await page.locator('#actions button[data-v]:not(:disabled)').first().waitFor();
        await page.locator('#actions button').filter({hasText:data.items[i].answer}).click();
        if(i<data.items.length-1)await page.locator('#oral:not(:disabled)').waitFor();
      }
      await page.locator('#picture[hidden]').waitFor({state:'attached'});await capture('completion');
    }
    interactions.push({variant,width,height,disabled:true,listen:true,processing:true,rejected_read:true,rejected_choice:true,correct_progression:true});
    errors.push({variant,width,height,errors:scriptErrors});assert.deepEqual(scriptErrors,[],'Browser script errors');await context.close();
  }
  // Lesson 5 is the only other consumer of this stylesheet. Its intro and
  // active layouts must remain exactly the same after the scoped additions.
  for(const [width,height]of [[1366,768],[1920,1080],[2560,1440],[375,812]]) {
    const before={};
    for(const variant of ['before','after']) {
      const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:'reduce'});context.setDefaultTimeout(10000);
      await context.route('**/*',route=>{
        const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
        if(u.pathname.endsWith('/session2_activity_spacing.css'))return route.fulfill({contentType:'text/css',body:variant==='before'?oldCss:css});
        if(u.pathname.startsWith('/static/')){const k=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[k]||k);assert.ok(file.startsWith(assets+path.sep));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});}
        if(u.pathname==='/dashboard/assessment/lesson-5/gawain-1/')return route.fulfill({contentType:'text/html',path:path.join(dir,'lesson-5-gawain-1-current.html')});
        return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}});
      });
      await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{setTimeout(()=>a.dispatchEvent(new Event('ended')),15);return Promise.resolve();};return a;};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};});
      const page=await context.newPage();await page.goto('http://localhost:9877/dashboard/assessment/lesson-5/gawain-1/',{waitUntil:'load'});await page.locator('.lesson-start-actions button').first().click();await page.locator('#start:not(:disabled)').waitFor();
      assert.equal(await page.locator('body.session2-centered-activity:has(#activity-data)').count(),0,'Refinement selector leaked to Lesson 5');
      for(const state of ['intro','active']) {
        if(state==='active'){await page.locator('#start').click();await page.locator('#identify:not(:disabled)').waitFor();await page.locator('#aloud:not(:disabled)').waitFor();}
        await settle(page);
        const snapshot=await page.evaluate(()=>new Promise((resolve,reject)=>{
          let previous='',since=performance.now(),start=since;
          function sample(){
            const rows=[...document.querySelectorAll('.page,.page *')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>({tag:e.tagName,id:e.id,cls:e.className,disabled:e.disabled,rect:e.getBoundingClientRect().toJSON(),style:Object.fromEntries(['font','color','background','padding','margin','gap','border','boxShadow','display','minHeight','maxHeight'].map(k=>[k,getComputedStyle(e)[k]]))}));
            const value=JSON.stringify(rows),ready=[...document.querySelectorAll('#app button')].every(b=>!b.disabled);
            if(value!==previous||!ready){since=performance.now();previous=value;}
            if(ready&&performance.now()-since>=500)return resolve(rows);
            if(performance.now()-start>10000)return reject(Error('Neighbor narration/layout did not settle'));
            setTimeout(sample,50);
          }sample();
        }));
        if(variant==='before')before[state]=snapshot;else{assert.deepEqual(snapshot,before[state],'Lesson 5 layout/style regression');neighbors.push({width,height,state,unchanged:true});}
      }
      await context.close();
    }
  }
  } finally {await browser.close();fs.writeFileSync(path.join(dir,`s2l4g2-refinement-dpr${dpr}.json`),JSON.stringify({results,interactions,errors,neighbors},null,2));}
  console.log(`PASS ${results.filter(r=>r.variant==='after').length} refined layouts; ${interactions.length} before/after interaction groups; ${neighbors.length} unchanged neighboring layouts`);
})().catch(e=>{console.error(e);process.exitCode=1;});
