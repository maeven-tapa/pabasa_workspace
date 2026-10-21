// Real Django template fixtures and local assets; API requests remain in memory.
// The before variant omits only this activity's new spacing stylesheet.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let pw;try{pw=require('playwright-core')}catch{pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'))}
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const url='http://localhost:9877/dashboard/assessment/activity/prescribed/lesson7-gawain3/';
const sizes=[[1366,768],[1440,900],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812],[320,568]];
const results=[],errors=[];
(async()=>{
 const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
 try{
  for(const state of ['reading-first','reading-middle','reading-last','selection-first','selection-last','done']) for(const variant of ['before','after']){
   const context=await browser.newContext({viewport:{width:1366,height:768},reducedMotion:'reduce'});
   await context.route('**/*',route=>{
    const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
    if(u.pathname.startsWith('/static/')){
     if(variant==='before'&&u.pathname.endsWith('/lesson7_gawain3_spacing.css'))return route.fulfill({contentType:'text/css',body:''});
     const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key);assert.ok(file.startsWith(assets+path.sep));
     return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
    }
    if(u.href===url){
     let html=fs.readFileSync(path.join(dir,'lesson7-gawain3-current.html'),'utf8');
     html=html.replace(/(<script id="activity-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,json,b)=>{
      const data=JSON.parse(json);assert.equal(data.items.length,15,'Original 15 reading items');data.progress={...(data.progress||{}),activity_completed:state==='done',state:{...(data.progress?.state||{}),current_reading_item:state==='reading-last'?14:state==='reading-middle'?7:0,oral_reading_completed:state.startsWith('selection'),current_target:state==='selection-last'?4:0,selections:{},completed_reading_items:[]}};
      return a+JSON.stringify(data)+b;
     });return route.fulfill({contentType:'text/html',body:html});
    }return route.fulfill({json:{success:true}});
   });
   await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const audio=new Native(...args);audio.play=()=>{setTimeout(()=>audio.dispatchEvent(new Event('ended')),15);return Promise.resolve()};return audio};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{}});
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
   const gate=page.locator('.lesson-start-actions button');if(await gate.count()&&await gate.first().isVisible())await gate.first().click();await page.waitForTimeout(150);
   for(const [width,height]of (state==='done'?[[1366,768],[2560,1440]]:[...sizes,[2560,1440],[1366,768]])){
    await page.setViewportSize({width,height});await page.mouse.move(0,0);await page.waitForTimeout(180);await page.evaluate(()=>window.scrollTo(0,0));
    const data=await page.evaluate(()=>{
     const card=document.querySelector('#app'),rect=e=>e.getBoundingClientRect().toJSON(),style=getComputedStyle(card);
     const old=card.getAttribute('style');card.style.setProperty('min-height','0','important');card.style.setProperty('height','auto','important');card.style.setProperty('flex','0 0 auto','important');const natural=rect(card);old===null?card.removeAttribute('style'):card.setAttribute('style',old);
     const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
     return{card:rect(card),naturalCard:natural,page:rect(document.querySelector('.page')),nav:rect(document.querySelector('.back')),tools:rect(document.querySelector('.session3-controls-tools')),
      progress:{count:card.querySelectorAll('.numbered-progress__circle').length,current:card.querySelector('.numbered-progress')?.getAttribute('aria-valuenow'),rect:card.querySelector('.numbered-progress')?.getBoundingClientRect().toJSON()},navText:{lineHeight:parseFloat(getComputedStyle(document.querySelector('.back')).lineHeight),whiteSpace:getComputedStyle(document.querySelector('.back')).whiteSpace},scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],cardStyles:Object.fromEntries(['padding','border','background','font','borderRadius','gap'].map(k=>[k,style[k]])),
      parts:[...card.querySelectorAll('.eyebrow,h1,.instruction,.lesson7-golden-picture-box,img,button,.numbered-progress,.numbered-progress__circle')].filter(visible).map(e=>({tag:e.tagName,id:e.id,cls:e.className,rect:rect(e),styles:Object.fromEntries(['font','padding','margin','gap','objectFit'].map(k=>[k,getComputedStyle(e)[k]]))}))};
    });
    const debug=page.locator('.session3-controls-debug');await debug.evaluate(e=>{e.hidden=false});const debugCard=await page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate(e=>{e.hidden=true});
    const r={width,height,state,variant,...data,debugCard};results.push(r);
    await page.screenshot({path:path.join(dir,`lesson7-g3-${state}-${width}x${height}-${variant}.png`),fullPage:width<1000,animations:'disabled'});
    if(variant==='after'){
     const b=results.find(x=>x.variant==='before'&&x.state===state&&x.width===width&&x.height===height);
     if(state==='done'){assert.deepEqual(r.card,b.card,'Completion layout changed');continue}
     assert.ok(Math.abs(r.card.x+r.card.width/2-width/2)<1,`${state} ${width}: horizontal centering`);
     assert.equal(r.card.width,b.card.width,'Card width changed');assert.ok(Math.abs(r.card.height-b.naturalCard.height)<1||width<1000,'Unexpected natural card height');assert.deepEqual(r.cardStyles,b.cardStyles,'Card design changed');
     assert.deepEqual(r.debugCard,r.card,'Debug panel affected the card');assert.equal(r.progress.count,state.startsWith('reading')?15:5,'Progress items changed');assert.equal(Number(r.progress.current),state==='reading-last'?15:state==='reading-middle'?8:state==='selection-last'?5:1,'Active progress changed');if(width>=1000)assert.equal(r.navText.whiteSpace,'nowrap','Desktop back label wraps');assert.ok(r.scroll[0]<=width,'Horizontal overflow');
     if(width>=1000){assert.ok(r.scroll[1]<=height,`${state} ${width}: desktop scrolling`);assert.ok(Math.abs(r.card.y+r.card.height/2-height/2)<1,`${state} ${width}: vertical centering`)}
     for(const nav of [r.nav,r.tools])assert.ok(nav.bottom<=r.card.y+1||nav.right<=r.card.x||nav.x>=r.card.right,`${state} ${width}: navigation overlap`);
     assert.equal(r.parts.length,b.parts.length,'Activity elements changed');const buttonsBottom=Math.max(...r.parts.filter(p=>p.tag==='BUTTON').map(p=>p.rect.bottom));assert.ok(r.progress.rect.y>=buttonsBottom-1,'Progress overlaps buttons');assert.ok(r.progress.rect.y-buttonsBottom<25,'Excessive progress gap');
     for(let i=0;i<r.parts.length;i++){
      const p=r.parts[i],old=b.parts[i],c=r.card;
      assert.ok(p.rect.x>=c.x-1&&p.rect.right<=c.right+1&&p.rect.y>=c.y-1&&p.rect.bottom<=c.bottom+1,'Clipped activity element');
      if(p.cls.includes('numbered-progress__circle')&&width<1000){assert.ok(p.rect.width>=28&&p.rect.height>=28,'Progress circle shrank');continue}
      assert.deepEqual([p.tag,p.id,p.cls,p.styles,...(p.cls==='numbered-progress'?[]:[p.rect.width,p.rect.height])],[old.tag,old.id,old.cls,old.styles,...(old.cls==='numbered-progress'?[]:[old.rect.width,old.rect.height])],'Content sizing/styling changed');
     }
    }
    console.log(`${variant} ${state} ${width}x${height}: card ${r.card.width.toFixed(2)}x${r.card.height.toFixed(2)}, center Y ${(r.card.y+r.card.height/2).toFixed(2)}`);
   }
   await context.close();
  }
  assert.deepEqual(errors,[],'Browser script errors');console.log('PASS '+results.filter(r=>r.variant==='after').length+' rendered Gawain 3 layouts');
 }finally{await browser.close();fs.writeFileSync(path.join(dir,'lesson7-g3-centering.json'),JSON.stringify({results,errors},null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
