// Actual Django-rendered fixtures and local assets; provider/API results stay
// in memory. Native buttons exercise the existing client callbacks unchanged.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw = require(path.join(runtime, 'playwright-core'));
const root = path.resolve(__dirname, '..'), dir = path.join(root, 'tmp/prescribed-responsive-audit');
const assets = path.join(root, 'pabasa_site/pabasa_app/static');
const aliases = JSON.parse(fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static_image_aliases.json')));
const fixture = fs.readFileSync(path.join(dir, 'lesson9-gawain1-current.html'), 'utf8');
const config = JSON.parse(fixture.match(/<script id="lesson9-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
assert.equal(config.items.length, 11);
const url = 'http://localhost:9877/dashboard/assessment/activity/prescribed/lesson9-gawain1/';
const dpr = Number(process.env.PABASA_AUDIT_DPR || 1), results = [], errors = [], interactions = [];
const sizes = [[1366,768],[1440,900],[1680,924],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812],[320,568],[2560,1440],[1366,768]];

async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve, reject) => {
      let previous = '', stable = 0; const started = performance.now();
      function frame() {
        const value = JSON.stringify([...document.querySelectorAll('#app,#app .task,#app button,#app h1,#app .numbered-progress')].map(e => {
          const r = e.getBoundingClientRect(), s = getComputedStyle(e);
          return [r.x,r.y,r.width,r.height,s.font,s.padding];
        }));
        stable = value === previous ? stable + 1 : 0; previous = value;
        if (stable >= 6) return resolve();
        if (performance.now() - started > 15000) return reject(Error('Layout did not settle'));
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    });
  });
}

async function inspect(page) {
  return page.evaluate(() => {
    const card = document.querySelector('#app'), rect = e => e.getBoundingClientRect().toJSON();
    const visible = e => { const r=rect(e),s=getComputedStyle(e); return r.width && r.height && s.display!=='none' && s.visibility!=='hidden'; };
    const style = e => Object.fromEntries(['font','padding','margin','gap','border','borderRadius','background','color'].map(k=>[k,getComputedStyle(e)[k]]));
    const cardStyle=style(card);delete cardStyle.margin; // Outer margins change with grid centering.
    return {card:rect(card),cardStyle,nav:rect(document.querySelector('.back')),tools:rect(document.querySelector('.session3-controls-tools')),
      scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
      progress:{count:card.querySelectorAll('.numbered-progress__circle').length,current:card.querySelector('.numbered-progress')?.getAttribute('aria-valuenow')},
      parts:[...card.querySelectorAll('.eyebrow,h1,.syllables,.syllables > *, .word,.building,.tiles,button,.numbered-progress,.numbered-progress__circle')].filter(visible).map(e=>({tag:e.tagName,cls:e.className,id:e.id,text:e.textContent,rect:rect(e),style:style(e)}))};
  });
}

async function exercise(page, state, saved, completions) {
  await page.evaluate(() => {
    const original = window.Basahin;
    window.__auditReadResults = []; window.__auditReadTargets = [];
    window.Basahin = {...original, read:async options => {
      window.__auditReadTargets.push(options.target_text);
      return window.__auditReadResults.shift() || {success:true,complete:true};
    }};
  });
  if (state === 'syllables') {
    await page.locator('#listen:not(:disabled)').click(); await page.locator('#read:not(:disabled)').waitFor();
    assert.equal(await page.locator('.focus-syllable').textContent(), config.items[0].syllables[0]);
    await page.evaluate(()=>window.__auditReadResults.push({success:false}));
    await page.locator('#read').click(); await page.waitForFunction(()=>!document.querySelector('#read')?.disabled);
    assert.equal(saved.at(-1).read_attempts, 1, 'Rejected read attempts changed');
    await page.locator('#read').click(); await page.waitForFunction(()=>document.querySelector('.focus-syllable')?.textContent==='mi');
    await page.locator('#read:not(:disabled)').click(); await page.locator('#building').waitFor();
  }
  if (state !== 'word-last') {
    await page.locator('.tiles .tile:not(:disabled)').first().waitFor();
    await page.locator('.tiles .tile[data-i="1"]').click(); await page.locator('.tiles .tile[data-i="0"]').click();
    await page.locator('#combine:not(:disabled)').click(); await page.waitForFunction(()=>!document.querySelector('#reset')?.disabled);
    assert.equal(await page.locator('.word').count(), 0, 'Wrong order advanced activity');
    await page.locator('#reset').click(); assert.equal(await page.locator('#building .tile').count(), 0, 'Reset failed');
    await page.locator('.tiles .tile[data-i="0"]').click(); await page.locator('.tiles .tile[data-i="1"]').click();
    await page.locator('#combine:not(:disabled)').click(); await page.locator('.word').waitFor();
    assert.equal(await page.locator('.word').textContent(), config.items[0].word, 'Combined word changed');
    await settle(page); const r=await inspect(page);
    assert.equal(r.progress.count,11); assert.ok(r.scroll[0]<=1366 && r.scroll[1]<=768, 'Progressed activity overflow');
    await page.locator('#read:not(:disabled)').click(); await page.waitForFunction(()=>document.querySelector('.numbered-progress')?.getAttribute('aria-valuenow')==='2');
    assert.equal(saved.at(-1).current_item, 1, 'Next-item progression changed');
    interactions.push({state,listen:state==='syllables',rejected_read:state==='syllables',syllable_progression:state==='syllables',wrong_order:true,reset:true,correct_combine:true,next_item:true});
  } else {
    await page.locator('#read:not(:disabled)').click(); await page.locator('#app > .done').waitFor();
    assert.equal(completions.length,1,'Completion request changed');
    assert.equal(saved.at(-1).phase,'complete'); assert.equal(saved.at(-1).completed_items.length,11);
    interactions.push({state,completion:true,all_11_items_retained:true});
  }
}

(async()=>{
  const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try {
    for (const state of ['syllables','combine','word-last','done']) for (const variant of ['before','after']) {
      const saved=[],completions=[];
      const context=await browser.newContext({viewport:{width:1366,height:768},deviceScaleFactor:dpr,reducedMotion:'reduce'});
      await context.route('**/*',route=>{
        const u=new URL(route.request().url()); if(u.origin!=='http://localhost:9877') return route.abort();
        if(u.pathname.startsWith('/static/')){
          if(variant==='before'&&u.pathname.endsWith('/lesson9_gawain1_spacing.css')) return route.fulfill({contentType:'text/css',body:''});
          const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key); assert.ok(file.startsWith(assets+path.sep));
          return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
        }
        if(u.href===url){
          const html=fixture.replace(/(<script id="lesson9-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,json,b)=>{
            const d=JSON.parse(json); d.progress={...d.progress,activity_completed:state==='done',state:{current_item:state==='word-last'?10:0,phase:state==='combine'?'combine':state==='word-last'?'oral_word':'oral_syllables',syllable_index:0,selected_syllables:[],completed_items:state==='word-last'?Array.from({length:10},(_,i)=>i):[]}};
            return a+JSON.stringify(d)+b;
          }); return route.fulfill({contentType:'text/html',body:html});
        }
        if(u.pathname===config.progress_url) saved.push(route.request().postDataJSON().state);
        if(u.pathname===config.completion_url) completions.push(true);
        return route.fulfill({json:{success:true,audio_content:'',mime_type:'audio/mpeg'}});
      });
      await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{setTimeout(()=>a.dispatchEvent(new Event('ended')),15);return Promise.resolve()};return a};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{}});
      const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url,{waitUntil:'load'});
      const gate=page.locator('.lesson-start-actions button');if(await gate.count()&&await gate.first().isVisible()) await gate.first().click();
      if(state!=='done') await page.locator('.numbered-progress__circle').last().waitFor();
      for(const [width,height] of (state==='done'?[[1366,768],[2560,1440]]:sizes)){
        await page.setViewportSize({width,height});await page.mouse.move(0,0);await settle(page);await page.evaluate(()=>window.scrollTo(0,0));
        const r={state,variant,width,height,dpr,...await inspect(page)};
        const debug=page.locator('.session3-controls-debug');await debug.evaluate(e=>e.hidden=false);r.debugCard=await page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate(e=>e.hidden=true);
        results.push(r);await page.screenshot({path:path.join(dir,`lesson9-g1-${state}-${width}x${height}-dpr${dpr}-${variant}.png`),fullPage:width<1000,animations:'disabled'});
        if(variant==='after'){
          const b=results.find(x=>x.state===state&&x.variant==='before'&&x.width===width&&x.height===height);
          if(state==='done'){assert.deepEqual(r.card,b.card,'Completion changed');continue;}
          assert.deepEqual(r.debugCard,r.card,'Debug moved card');assert.equal(r.card.width,b.card.width,'Card width changed');assert.deepEqual(r.cardStyle,b.cardStyle,'Card visual design changed');
          assert.ok(Math.abs(r.card.x+r.card.width/2-width/2)<1,'Horizontal centering');assert.ok(r.scroll[0]<=width,'Horizontal overflow');
          if(width>=1000){assert.ok(Math.abs(r.card.y+r.card.height/2-height/2)<1,'Vertical centering');assert.ok(r.scroll[1]<=height,'Desktop scrolling');assert.ok(r.card.height<b.card.height,'Card still stretched');}
          assert.equal(r.progress.count,11,'11 indicators changed');assert.equal(Number(r.progress.current),state==='word-last'?11:1);
          assert.equal(r.parts.length,b.parts.length,'Activity components changed');
          for(let i=0;i<r.parts.length;i++){
            const p=r.parts[i],old=b.parts[i],isProgress=p.cls==='numbered-progress',circle=p.cls.includes('numbered-progress__circle');
            if(circle&&width<1000){assert.ok(p.rect.width>=28&&p.rect.height>=28,'Progress hit area shrank');}
            else assert.deepEqual([p.tag,p.cls,p.id,p.text,p.style,...(isProgress?[]:[p.rect.width,p.rect.height])],[old.tag,old.cls,old.id,old.text,old.style,...(isProgress?[]:[old.rect.width,old.rect.height])],'Component sizing/design changed');
            assert.ok(p.rect.x>=r.card.x-1&&p.rect.right<=r.card.right+1&&p.rect.y>=r.card.y-1&&p.rect.bottom<=r.card.bottom+1,'Clipped component');
          }
          for(const nav of [r.nav,r.tools])assert.ok(nav.bottom<=r.card.y+1||nav.right<=r.card.x||nav.x>=r.card.right,'Navigation overlaps card');
        }
        console.log(`${variant} ${state} ${width}x${height}: card ${r.card.width.toFixed(2)}x${r.card.height.toFixed(2)}`);
      }
      if(variant==='after'&&state!=='done') await exercise(page,state,saved,completions);
      await context.close();
    }
    assert.deepEqual(errors,[],'Browser script errors');console.log(`PASS ${results.filter(r=>r.variant==='after').length} layouts, ${interactions.length} interaction scenarios`);
  } finally {await browser.close();fs.writeFileSync(path.join(dir,`lesson9-g1-spacing-dpr${dpr}.json`),JSON.stringify({results,interactions,errors},null,2));}
})().catch(e=>{console.error(e);process.exitCode=1});
