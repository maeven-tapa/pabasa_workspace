// Rendered layout regression for the two Session 1 rhyming activities.
// Uses the isolated Django fixtures: API requests stay in memory, with no
// student data, recording, or progress writes to a running service.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
let pw; try { pw = require('playwright-core'); } catch {
  pw = require(path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
}
const root = path.resolve(__dirname, '..'), dir = path.join(root, 'tmp/prescribed-responsive-audit');
const assets = path.join(root, 'pabasa_site/pabasa_app/static');
const aliases = JSON.parse(fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static_image_aliases.json')));
const sizes = [[320,568],[375,667],[390,844],[768,1024],[1024,768],[1366,768],[1440,900],[1536,864],[1680,925],[1920,1080],[2560,1440],[3440,1440]]
  .filter(([w])=>!process.env.PABASA_RHYME_WIDTHS||process.env.PABASA_RHYME_WIDTHS.split(',').includes(String(w)));
const report = [];
const desktopComparisons = [];
const desktopLayout = () => [...document.querySelectorAll('body,body *')]
  .filter(e => e.getBoundingClientRect().width && e.getBoundingClientRect().height && (!e.closest('#read') || e.id==='read'))
  .map(e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {
    tag:e.tagName,id:e.id,rect:[r.x,r.y,r.width,r.height],
    typography:e.id==='read'?null:[s.fontFamily,s.fontSize,s.fontWeight,s.lineHeight]
  };});
(async () => {
  const browser = await pw.chromium.launch({channel:'chrome', headless:true});
  try {
    for (const key of ['lesson-2-gawain-1','lesson-3-gawain-1']) {
      for (const [width,height] of sizes) {
        const context = await browser.newContext({viewport:{width,height}, reducedMotion:'reduce'});
        const page = await context.newPage();
        await context.route('**/*', route => {
          const u = new URL(route.request().url());
          if (u.origin !== 'http://localhost:9877') return route.abort();
          if (u.pathname.startsWith('/static/')) {
            const name = decodeURIComponent(u.pathname.slice(8)), file = path.resolve(assets, aliases[name] || name);
            assert.ok(file.startsWith(assets + path.sep));
            return fs.existsSync(file) ? route.fulfill({path:file}) : route.fulfill({status:404});
          }
          if (u.pathname.startsWith('/activity/')) return route.fulfill({contentType:'text/html', path:path.join(dir,key+'-'+(u.searchParams.get('variant')||'current')+'.html')});
          return route.fulfill({json:{success:true,progress:{current_index:0,completed_items:0,correct_items:0,activity_completed:false,state:{}}}});
        });
        await context.addInitScript(() => {
          let seed=45; Math.random=()=>((seed=seed*16807%2147483647)-1)/2147483646;
          const Native=window.Audio;
          window.Audio=function(...args){const a=new Native(...args);a.play=()=>Promise.resolve();return a;};
          if(window.speechSynthesis) window.speechSynthesis.speak=()=>{};
        });
        await page.goto('http://localhost:9877/activity/'+key,{waitUntil:'load'});
        await page.evaluate(()=>document.fonts.ready);
        await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important}'});
        for (const state of ['intro','reading','answers','completion']) {
          if(state==='reading') await page.locator('.lesson-start-actions button').first().click();
          // Exercise the existing renderers with each visual state. Do not
          // simulate a successful recording or send a progress submission.
          if(state==='answers') await page.evaluate(()=>{wi=2;render();});
          if(state==='completion') await page.evaluate(()=>{pi=pairs.length;render();});
          await page.waitForTimeout(150);
          const entry = await page.evaluate(({key,state}) => {
            const rect = e => {const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
            const visible = e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width&&r.height&&s.display!=='none'&&s.visibility!=='hidden';};
            const panel = document.querySelector('.activity-page-wrapper > .app,#game');
            const parts = [...document.querySelectorAll('.activity-title,#game .header,.pair,.pairs,#read,#listen,#prescribed-listen,.answers,.progress')].filter(visible);
            const bounds = parts.map(rect);
            const group = bounds.length ? {top:Math.min(...bounds.map(r=>r.y)),bottom:Math.max(...bounds.map(r=>r.bottom)),left:Math.min(...bounds.map(r=>r.x)),right:Math.max(...bounds.map(r=>r.right))} : null;
            const read=document.querySelector('#read'),label=read?.querySelector('[data-basahin-label]');
            return {key,state,width:innerWidth,height:innerHeight,scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],panel:rect(panel),group,
              labelSize:label?parseFloat(getComputedStyle(label).fontSize):null,
              buttons:[...document.querySelectorAll('#read,#listen,#prescribed-listen,.answers button')].filter(visible).map(rect),
              completed:!!document.querySelector('.complete,.completion-card'),
              modalOpen:document.body.classList.contains('lesson-start-open')};
          },{key,state});
          report.push(entry);
          if ([1680,2560,3440].includes(width)) await page.screenshot({path:path.join(dir,`${key}-${width}-rhyme-${state}.png`),animations:'disabled'});
          assert.ok(entry.scroll[0]<=width,`${key} ${width} ${state}: horizontal overflow`);
          if (state==='reading') {
            assert.equal(entry.modalOpen,false,'Introduction must be closed through its actual button');
            assert.ok(entry.labelSize>=16,`${key}: Basahin label too small`);
            if([1366,1440,1536].includes(width)) {
              const baseline=await context.newPage();
              await baseline.goto('http://localhost:9877/activity/'+key+'?variant=baseline',{waitUntil:'load'});
              await baseline.evaluate(()=>document.fonts.ready);
              await baseline.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important}'});
              await baseline.locator('.lesson-start-actions button').first().click();
              await baseline.waitForTimeout(150);
              const layouts=await Promise.all([page.evaluate(desktopLayout),baseline.evaluate(desktopLayout)]);
              const unchanged=JSON.stringify(layouts[0])===JSON.stringify(layouts[1]);
              if(!unchanged)fs.writeFileSync(path.join(dir,`${key}-${width}-rhyme-desktop-diff.json`),JSON.stringify(layouts,null,2));
              desktopComparisons.push({key,width,height,unchanged,exception:'Basahin label typography'});
              assert.ok(unchanged,`${key} ${width}: unrelated desktop layout changed`);
              await baseline.close();
            }
          }
          if(width>=1600 && height>=900 && state!=='completion') {
            assert.ok(entry.scroll[1]<=height,`${key} ${width} ${state}: unnecessary page scrolling`);
            assert.ok(Math.abs(entry.panel.x+entry.panel.width/2-width/2)<1,'Panel shifted horizontally');
            assert.ok(Math.abs((entry.group.top+entry.group.bottom)/2-(entry.panel.y+entry.panel.height/2))<20,
              `${key} ${width} ${state}: composition shifted vertically`);
            for(const b of entry.buttons) assert.ok(b.y>=entry.panel.y&&b.bottom<=entry.panel.bottom&&b.x>=entry.panel.x&&b.right<=entry.panel.right,'Control outside panel');
          }
          if(state==='completion') assert.ok(entry.completed,'Existing completion renderer failed');
        }
        await context.close();
        console.log(`CHECKED ${key} ${width}x${height}`);
      }
    }
  } finally {
    fs.writeFileSync(path.join(dir,'rhyme-regression.json'),JSON.stringify({states:report,desktopComparisons},null,2));
    await browser.close();
  }
  console.log(`Passed ${report.length} rendered rhyme states at ${sizes.length} viewport sizes.`);
})().catch(e=>{console.error(e);process.exitCode=1;});
