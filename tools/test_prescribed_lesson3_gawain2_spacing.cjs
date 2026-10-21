// Render the real Django template with local assets. API/provider responses
// remain in memory; no microphone, account, or student progress is accessed.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw = require(path.join(runtime, 'playwright-core'));
const root = path.resolve(__dirname, '..'), dir = path.join(root, 'tmp/prescribed-responsive-audit');
const assets = path.join(root, 'pabasa_site/pabasa_app/static');
const aliases = JSON.parse(fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static_image_aliases.json')));
const fixture = fs.readFileSync(path.join(dir, 'lesson-3-gawain-2-current.html'), 'utf8');
const pairs = JSON.parse(fixture.match(/mountLesson3RhymeActivity\(\{\s*pairs:\s*([\s\S]*?),\s*imageBase:/)[1]);
assert.equal(pairs.length, 6);
const url = 'http://localhost:9877/dashboard/assessment/activity/lesson-3-gawain-2/';
const audit = process.argv.includes('--audit'), dpr = Number(process.env.PABASA_AUDIT_DPR || 1);
const refinement = process.argv.includes('--refinement');
const prefix = refinement ? 'lesson3-g2-refinement' : 'lesson3-g2';
const previousSpacingCss = refinement ? fs.readFileSync(path.join(dir,'lesson3_gawain2_spacing-before-refinement.css'),'utf8') : '';
const sizes = (audit ? [[1366,768],[1440,900],[1920,1080],[2560,1440],[768,1024],[375,812]] :
  [[1366,768],[1440,900],[1536,864],[1680,916],[1680,924],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812],[320,568]])
  .filter(([w])=>!process.env.PABASA_RHYME_WIDTHS||process.env.PABASA_RHYME_WIDTHS.split(',').includes(String(w)));
const results = [], errors = [], interactions = [];

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(i=>i.complete?null:new Promise(r=>{i.onload=r;i.onerror=r})));
    document.activeElement?.blur();
    document.getAnimations().forEach(a=>{
      if(a.constructor.name==='CSSTransition')a.finish();
      else {a.pause();a.currentTime=0;}
    });
    await new Promise((resolve,reject)=>{
      let previous='',stable=0,started=performance.now();
      function frame(){
        const current=JSON.stringify([...document.querySelectorAll('#game,#game *, .nav')].map(e=>{
          const r=e.getBoundingClientRect();return[r.x,r.y,r.width,r.height,getComputedStyle(e).font];
        }));
        stable=current===previous?stable+1:0;previous=current;
        if(stable>=6)return resolve();
        if(performance.now()-started>15000)return reject(Error('Layout did not settle'));
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    });
  });
}

async function inspect(page) {
  return page.evaluate(()=>{
    const card=document.querySelector('#game'),rect=e=>e.getBoundingClientRect().toJSON();
    const visible=e=>{const r=rect(e),s=getComputedStyle(e);return r.width&&r.height&&s.display!=='none'&&s.visibility!=='hidden';};
    const style=e=>Object.fromEntries(['font','border','borderRadius','background','color','padding','gap','transform'].map(k=>[k,getComputedStyle(e)[k]]));
    const title=card.querySelector('h1'),pictures=card.querySelector('.pairs'),buttons=card.querySelector('.lesson3-g2-actions,.answers'),progress=card.querySelector('.progress');
    return {card:rect(card),cardStyle:style(card),scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
      wrappers:[...document.querySelectorAll('body,.app,.nav,#game,.header,.status,.progress')].map(e=>({cls:e.className,rect:rect(e),style:Object.fromEntries(['display','position','inset','height','minHeight','margin','padding','gridTemplateRows','alignSelf','gap'].map(k=>[k,getComputedStyle(e)[k]]))})),
      nav:rect(document.querySelector('.nav')),tools:rect(document.querySelector('.s1-controls-tools')),
      gaps:title&&pictures&&buttons&&progress?{heading:pictures.getBoundingClientRect().top-title.getBoundingClientRect().bottom,
        actions:buttons.getBoundingClientRect().top-pictures.getBoundingClientRect().bottom,
        progress:progress.getBoundingClientRect().top-buttons.getBoundingClientRect().bottom}:null,
      progress:card.querySelectorAll('.segments i').length,
      parts:[...card.querySelectorAll('.eyebrow,h1,.pairs,.word,.word img,.connector,.lesson3-g2-actions,.answers,button,.segments,.segments i')].filter(visible)
        .map(e=>({tag:e.tagName,cls:e.className,id:e.id,text:e.textContent,src:e.getAttribute('src'),rect:rect(e),style:style(e)})),
      layout:(innerWidth<1600||innerHeight<900||card.querySelector('.complete'))?[...document.querySelectorAll('body,body *')].filter(visible).map(e=>({tag:e.tagName,id:e.id,cls:e.className,
        rect:rect(e),styles:[...getComputedStyle(e)].sort().map(k=>[k,getComputedStyle(e).getPropertyValue(k)])})):null};
  });
}

async function read(page) {
  await page.locator('#read:not(:disabled)').waitFor();
  await page.locator('#read').click();
}

(async()=>{
  const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try {
    for(const [width,height] of sizes)for(const variant of audit?['before']:['before','after']) {
      const saved=[],reads=[],browserErrors=[];
      let verdict=true;
      let releaseVerdict=null, holdVerdict=false;
      const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:dpr,reducedMotion:'reduce'});
      await context.route('**/*',async route=>{
        const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
        if(u.pathname.startsWith('/static/')){
          if(variant==='before'&&u.pathname.endsWith('/lesson3_gawain2_spacing.css'))return route.fulfill({contentType:'text/css',body:previousSpacingCss});
          const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key);assert.ok(file.startsWith(assets+path.sep));
          return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
        }
        if(u.href===url)return route.fulfill({contentType:'text/html',body:fixture});
        if(u.pathname.includes('transcribe')){
          reads.push(route.request().postData());if(holdVerdict)await new Promise(resolve=>releaseVerdict=resolve);
          return route.fulfill({json:{success:true,complete:verdict,transcript:'fixture response'}});
        }
        if(route.request().method()==='POST')saved.push(route.request().postDataJSON());
        return route.fulfill({json:{success:true,progress:{current_index:0,completed_items:0,correct_items:0,activity_completed:false,state:{}}}});
      });
      await context.addInitScript(()=>{
        let seed=45;Math.random=()=>((seed=seed*16807%2147483647)-1)/2147483646;
        window.__auditAudio=[];
        const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{
          window.__auditAudio.push(String(args[0]));setTimeout(()=>a.dispatchEvent(new Event('ended')),15);return Promise.resolve();
        };return a;};
        if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};
      });
      const page=await context.newPage();page.on('pageerror',e=>browserErrors.push(e.message));await page.goto(url,{waitUntil:'load'});
      await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important}'});
      await page.evaluate(()=>{window.Basahin={...window.Basahin,openMicrophone:async()=>({getTracks:()=>[{stop(){}}]}),capture:async({button})=>{
        window.BasahinButton.setState(button,'processing');return new Blob(['fixture'],{type:'audio/webm'});
      },attachStreamResult:()=>{}};});
      const start=page.locator('.lesson-start-actions button').first();if(await start.isVisible())await start.click();
      await page.locator('#read:not(:disabled)').waitFor();

      async function capture(state,w=width,h=height) {
        await page.mouse.move(0,0);
        await page.evaluate(()=>{window.scrollTo(0,0);document.querySelectorAll('html,body,.app,#game').forEach(e=>{e.scrollTop=0;e.scrollLeft=0;});});
        await settle(page);
        const r={width:w,height:h,dpr,variant,state,...await inspect(page)};
        const debug=page.locator('.s1-controls-debug');
        assert.equal(await debug.count(),1,'Actual speech debug panel missing');
        {
          const old=await debug.evaluate(e=>e.hidden);await debug.evaluate(e=>e.hidden=!e.hidden);
          r.debugCard=await page.locator('#game').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate((e,hidden)=>e.hidden=hidden,old);
          assert.deepEqual(r.debugCard,r.card,'Debug panel influences card');
        }
        const before=results.find(b=>b.variant==='before'&&b.width===w&&b.height===h&&b.state===state);
        if(variant==='after'){
          const diagnostic={...r};delete diagnostic.layout;
          fs.writeFileSync(path.join(dir,`${prefix}-latest-layout.json`),JSON.stringify(diagnostic,null,2));
        }
        if(variant==='after'){
          assert.ok(r.scroll[0]<=w,'Horizontal overflow');
          if(w<1600||h<900){
            assert.deepEqual(r.layout,before.layout,`Existing layout changed: ${w} ${state}`);
          }else if(state!=='done'){
            assert.ok(Math.abs(r.card.x+r.card.width/2-w/2)<1,'Horizontal centering');
            assert.ok(Math.abs(r.card.y+r.card.height/2-h/2)<1,'Vertical centering');
            assert.ok(r.scroll[1]<=h,'Unnecessary large-screen scrolling');
            assert.equal(r.card.width,before.card.width,'Card width changed');
            for(const nav of [r.nav,r.tools])assert.ok(nav.bottom<=r.card.y||nav.right<=r.card.x||nav.x>=r.card.right,'Navigation overlaps card');
            assert.ok(state==='answers'?r.card.height<=before.card.height:r.card.height<before.card.height,'Card still oversized');
            assert.equal(r.progress,6,'Six indicators changed');
            assert.equal(r.parts.length,before.parts.length);
            for(let i=0;i<r.parts.length;i++){
              const p=r.parts[i],b=before.parts[i];
              assert.deepEqual([p.tag,p.cls,p.id,p.text,p.src,p.rect.width,p.rect.height,p.style],
                [b.tag,b.cls,b.id,b.text,b.src,b.rect.width,b.rect.height,b.style],`Component dimensions/styles changed: ${p.cls}`);
              assert.ok(p.rect.x>=r.card.x-1&&p.rect.right<=r.card.right+1&&p.rect.y>=r.card.y-1&&p.rect.bottom<=r.card.bottom+1,`Clipped component: ${p.cls}`);
            }
            if(state==='answers'){
              assert.equal(r.gaps.actions,before.gaps.actions,'Existing answer spacing changed');
              assert.equal(r.gaps.progress,before.gaps.progress,'Existing answer progress spacing changed');
            }else{
              assert.ok(r.gaps.heading<before.gaps.heading&&r.gaps.heading>=24,'Heading spacing');
              if(refinement&&w>=2500)assert.ok(r.card.height/before.card.height>=.8&&r.card.height/before.card.height<=.85,'Reading card height refinement exceeds 15–20%');
              assert.ok(r.gaps.actions<before.gaps.actions&&r.gaps.actions>=18,'Picture/button spacing');
              assert.ok(r.gaps.progress<before.gaps.progress&&r.gaps.progress>=18,'Progress spacing');
            }
          }else assert.deepEqual(r.layout,before.layout,'Completion changed');
        }
        const screenshot=await page.screenshot({path:path.join(dir,`${prefix}-${state}-${w}x${h}-dpr${dpr}-${variant}.png`),fullPage:w<1000,animations:'disabled'});
        if(variant==='after'&&(w<1600||h<900||state==='done'))r.screenshotIdentical=screenshot.equals(fs.readFileSync(path.join(dir,`${prefix}-${state}-${w}x${h}-dpr${dpr}-before.png`)));
        results.push(r);
        console.log(`${variant} ${state} ${w}x${h}: ${r.card.width.toFixed(2)}x${r.card.height.toFixed(2)}, ${JSON.stringify(r.gaps)}`);
      }
      await capture('first');
      if(!audit&&width===2560){
        for(const [w,h] of [[1440,900],[2560,1440]]){
          await page.setViewportSize({width:w,height:h});await capture('resized-first',w,h);
        }
      }
      if(!audit){
        await page.locator('#listen:not(:disabled)').click();await page.locator('#read:not(:disabled)').waitFor();
        verdict=false;holdVerdict=true;await read(page);
        await page.waitForFunction(()=>document.querySelector('#read')?.dataset.basahinState==='processing');
        while(!releaseVerdict)await page.waitForTimeout(10);
        assert.equal(await page.locator('#read [data-basahin-label]').textContent(),'Sinusuri...');
        await capture('processing');holdVerdict=false;releaseVerdict();releaseVerdict=null;
        await page.locator('#read:not(:disabled)').waitFor();
        assert.equal(await page.locator('.word.active img').getAttribute('alt'),pairs[0].a,'Rejected read advanced');verdict=true;
        await read(page);await page.waitForFunction(()=>document.querySelectorAll('.word')[1]?.classList.contains('active'));
        await page.locator('#read:not(:disabled)').waitFor();await capture('second');
        await read(page);await page.locator('.answer:not(:disabled)').first().waitFor();await capture('answers');
        const wrong=pairs[0].yes?'no':'yes';await page.locator(`.answer[data-v="${wrong}"]`).click();await page.locator('.answer:not(:disabled)').first().waitFor();
        assert.equal(await page.locator('.pairs .word img').first().getAttribute('alt'),pairs[0].a,'Wrong rhyme advanced');
        await page.locator(`.answer[data-v="${pairs[0].yes?'yes':'no'}"]`).click();await page.locator('#read:not(:disabled)').waitFor();
        assert.equal(await page.locator('.pairs .word img').first().getAttribute('alt'),pairs[1].a,'Correct rhyme did not advance');
        interactions.push({variant,width,height,processing_label:true,rejected_read:true,second_word:true,rejected_rhyme:true,next_pair:true,pakinggan:true});
        if(width===2560){
          for(let i=1;i<pairs.length;i++){
            assert.equal(await page.locator('.word img').first().getAttribute('alt'),pairs[i].a);
            await capture(`pair${i+1}`);
            await read(page);await page.waitForFunction(()=>document.querySelectorAll('.word')[1]?.classList.contains('active'));
            await page.locator('#read:not(:disabled)').waitFor();await read(page);await page.locator('.answer:not(:disabled)').first().waitFor();
            await page.locator(`.answer[data-v="${pairs[i].yes?'yes':'no'}"]`).click();
            if(i<pairs.length-1)await page.locator('#read:not(:disabled)').waitFor();
          }
          await page.locator('.complete').waitFor();await capture('done');
          assert.ok(saved.some(s=>s.activity_key==='lesson-3-gawain-2'&&s.current_index===6),'Final pair progress missing');
          interactions.at(-1).all_six_pairs=true;
        }
      }
      errors.push({variant,width,height,errors:browserErrors});await context.close();
    }
    if(!audit)for(const e of errors.filter(e=>e.variant==='after')){
      const b=errors.find(b=>b.variant==='before'&&b.width===e.width&&b.height===e.height);
      assert.deepEqual(e.errors,b.errors,'New browser error');
    }
    console.log(`PASS ${results.filter(r=>r.variant==='after').length} rendered layouts, ${interactions.filter(i=>i.variant==='after').length} interaction groups`);
  }finally{
    await browser.close();for(const r of results)delete r.layout;
    fs.writeFileSync(path.join(dir,`${prefix}-spacing-${audit?'audit':`dpr${dpr}`}.json`),JSON.stringify({results,interactions,errors},null,2));
  }
})().catch(e=>{console.error(e);process.exitCode=1});
