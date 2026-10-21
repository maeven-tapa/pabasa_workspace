// Session 1-3 layout regression against the immediately preceding UI.
// Django fixtures/local assets only; providers, media and saves are in memory.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'));
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'))),aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const audit=process.argv.includes('--audit'),extra=process.argv.includes('--extra'),dpr=Number(process.env.PABASA_AUDIT_DPR||1),results=[],errors=[],label=process.env.PABASA_SCALE_LABEL?'-'+process.env.PABASA_SCALE_LABEL:'';
const sizes=(audit?[[2560,1440]]:[[1366,768],[1440,900],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812]])
 .filter(([w])=>!process.env.PABASA_SCALE_WIDTHS||process.env.PABASA_SCALE_WIDTHS.split(',').includes(String(w)));
const selected=manifest.filter(x=>(!process.env.PABASA_SCALE_KEYS||process.env.PABASA_SCALE_KEYS.split(',').includes(x.key))&&(!extra||['lesson-2-gawain-1','lesson-3-gawain-1','lesson-3-gawain-2','lesson9-gawain1','session-2-lesson-4-gawain-2'].includes(x.key)));
const cardSelector='.activity-page-wrapper>.app,.app>.game,.app>.shell>.game,.stage>.card,.page>.card,body>.shell>.card,.page>.shell';
async function settle(page){await page.mouse.move(0,0);await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.complete?null:i.decode().catch(()=>{})));document.activeElement?.blur();document.getAnimations().forEach(a=>{a.pause();a.currentTime=0;});window.scrollTo(0,0);await new Promise((resolve,reject)=>{let previous='',since=performance.now(),start=since;function sample(){const now=performance.now(),value=JSON.stringify([...document.querySelectorAll('.card,.game,.stage,button,img,canvas,h1')].map(e=>{const r=e.getBoundingClientRect();return[r.x,r.y,r.width,r.height,e.disabled,getComputedStyle(e).font];}));if(value!==previous||window.__auditAudioPending||now-(window.__auditAudioTime||0)<300){previous=value;since=now;}if(now-since>=300)return resolve();if(now-start>12000)return reject(Error('Layout/audio did not settle'));setTimeout(sample,50);}sample();});});}
async function inspect(page){return page.evaluate(selector=>{
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width&&r.height&&s.display!=='none'&&s.visibility!=='hidden';};
 const rect=e=>e?.getBoundingClientRect().toJSON(),card=[...document.querySelectorAll(selector)].find(e=>visible(e)&&!(e.matches('.shell')&&e.querySelector('.card')));
 const props=['fontSize','fontFamily','fontWeight','lineHeight','width','height','minWidth','minHeight','maxWidth','maxHeight','padding','margin','gap','rowGap','columnGap','borderWidth','borderRadius','color','backgroundColor','boxShadow','display','position','transform','overflowX','overflowY','gridTemplateColumns','gridTemplateRows','alignItems','justifyContent','flex','objectFit','backgroundPosition','backgroundSize'];
 const snapshot=e=>({tag:e.tagName,id:e.id,cls:typeof e.className==='string'?e.className:'svg',text:e.children.length||parseFloat(getComputedStyle(e).fontSize)===0?null:e.textContent,natural:e.tagName==='IMG'?[e.naturalWidth,e.naturalHeight]:null,rect:rect(e),style:Object.fromEntries(props.map(k=>[k,getComputedStyle(e)[k]]))});
 return{card:rect(card),cardClass:card?.className,scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],bodyClass:document.body.className,parts:card?[card,...card.querySelectorAll('*')].filter(visible).map(snapshot):[],nav:rect(document.querySelector('.back')),zoom:getComputedStyle(document.body).zoom,
  panels:card?[...card.querySelectorAll('.controls')].filter(visible).map(e=>({rect:rect(e),buttons:[...e.querySelectorAll('button')].filter(visible).map(rect)})):[],
  all:[...document.querySelectorAll('.page,.app,.shell,.game,.card,.back,.numbered-progress,.progress,.session3-controls-tools,.prescribed-s4-tools')].filter(visible).map(snapshot)};
},cardSelector);}
function fixture(key,state){let html=fs.readFileSync(path.join(dir,key+'-current.html'),'utf8');
 if(state==='lower')html=html.replace(/(<script id="handwriting-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,j,b)=>{const d=JSON.parse(j);d.progress={...d.progress,current_index:1,completed_items:1};return a+JSON.stringify(d)+b;});
 if(state==='selection')html=html.replace(/(<script id="(?:activity-data|lesson9-g2-data)"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,j,b)=>{const d=JSON.parse(j);d.progress={...d.progress,state:{...d.progress?.state,phase:'selection',oral_reading_completed:true,oral_index:15,selection_index:0,selections:d.rows?.map(()=>null)}};return a+JSON.stringify(d)+b;});
 if(state==='combine')html=html.replace(/(<script id="lesson9-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,j,b)=>{const d=JSON.parse(j);d.progress={...d.progress,state:{...d.progress?.state,phase:'combine',current_item:0,selected_syllables:[]}};return a+JSON.stringify(d)+b;});
 if(state==='word')html=html.replace(/(<script id="lesson9-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,j,b)=>{const d=JSON.parse(j);d.progress={...d.progress,state:{...d.progress?.state,phase:'oral_word',current_item:0,selected_syllables:[]}};return a+JSON.stringify(d)+b;});
 if(state==='choices')html=html.replace(/(<script id="activity-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,j,b)=>{const d=JSON.parse(j);d.progress={...d.progress,state:{...d.progress?.state,phase:'identify'}};return a+JSON.stringify(d)+b;});
 return html;
}
(async()=>{const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});try{
 for(const item of selected)for(const state of extra?[item.key==='lesson9-gawain1'?'word':item.key==='session-2-lesson-4-gawain-2'?'choices':'answers']:['initial',...(['lesson7-gawain2c','lesson7-gawain4','lesson8-gawain1'].includes(item.key)?['lower']:[]),...(['lesson7-gawain2b','lesson8-gawain1a','lesson9-gawain2'].includes(item.key)?['selection']:[]),...(item.key==='lesson9-gawain1'?['combine']:[])])for(const variant of audit?['before']:['before','after']){
  const context=await browser.newContext({viewport:{width:2560,height:1440},deviceScaleFactor:dpr,reducedMotion:'reduce'});context.setDefaultTimeout(10000);const scriptErrors=[];
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();if(u.pathname.startsWith('/static/')){
   if(u.pathname.endsWith('/prescribed_session123_large.css')&&variant==='before')return route.fulfill({contentType:'text/css',body:''});
   const k=decodeURIComponent(u.pathname.slice(8)),f=path.resolve(assets,aliases[k]||k);assert.ok(f.startsWith(assets+path.sep));return fs.existsSync(f)?route.fulfill({path:f}):route.fulfill({status:404});
  }if(u.pathname==='/activity/'+item.key)return route.fulfill({contentType:'text/html',body:fixture(item.key,state)});return route.fulfill({json:{success:true,accepted:true,complete:true,transcript:'fixture response',audio_content:'AA==',mime_type:'audio/mpeg'}});});
  await context.addInitScript(()=>{document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='@layer audit-freeze { *,*::before,*::after { animation: none !important; transition: none !important; } }';document.head.append(s);},{once:true});let seed=45;Math.random=()=>((seed=seed*16807%2147483647)-1)/2147483646;window.__auditAudioPending=0;const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{window.__auditAudioPending++;window.__auditAudioTime=performance.now();setTimeout(()=>{window.__auditAudioPending--;window.__auditAudioTime=performance.now();a.dispatchEvent(new Event('ended'));},15);return Promise.resolve();};return a;};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};});
  const page=await context.newPage();page.on('pageerror',e=>scriptErrors.push(e.message));await page.goto('http://localhost:9877/activity/'+item.key,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
  const gate=page.locator('.lesson-start-actions button').first();if(await gate.count()&&await gate.isVisible())await gate.click();
  await page.evaluate(()=>{window.__lessonStartReady=true;window.dispatchEvent(new Event('lesson-start-ready'));document.querySelectorAll('.lesson-start-backdrop,.lesson-one-welcome-modal').forEach(e=>e.style.display='none');document.querySelectorAll('video').forEach(v=>v.pause());});
  if(state==='answers'){
   if(['lesson-2-gawain-1','lesson-3-gawain-2'].includes(item.key)){
    // Enter the closed-over answer phase through the existing Read actions.
    // Only microphone/provider boundaries are fulfilled in memory.
    await page.evaluate(()=>{window.Basahin={...window.Basahin,openMicrophone:async()=>({getTracks:()=>[{stop(){}}]}),capture:async({button})=>{window.BasahinButton.setState(button,'processing');return new Blob(['fixture'],{type:'audio/webm'});},attachStreamResult:()=>{}};});
    for(let i=0;i<2;i++){await page.locator('#read:not(:disabled)').waitFor();await page.locator('#read').click();await settle(page);}
    await page.locator('.answers').waitFor();
   }else await page.evaluate(()=>{wi=2;render();});
   await page.locator('.answers').waitFor();
  }
  async function capture(phase,width,height){await settle(page);const r={key:item.key,state:phase,variant,width,height,dpr,...await inspect(page)};results.push(r);
   if(variant==='after'){
    const b=results.find(x=>x.variant==='before'&&x.key===r.key&&x.state===phase&&x.width===width&&x.height===height);assert.ok(b,'Missing baseline');
    if(width<2500||height<1200){
     // Chromium exposes different used auto margins in identical centered
     // flex boxes. Exact rectangles already cover their visible placement.
     const normalized=rows=>rows.map(p=>{const style={...p.style};delete style.margin;return{...p,style};});
     if(JSON.stringify(normalized(r.parts))!==JSON.stringify(normalized(b.parts))){fs.writeFileSync(path.join(dir,'scale125-failure.html'),await page.content());fs.writeFileSync(path.join(dir,'scale125-failure-wheel.json'),JSON.stringify(await page.locator('.wheel').evaluateAll(es=>es.map(e=>[e,e.parentElement,...[e.parentElement.parentElement]].filter(Boolean).map(x=>({html:x.outerHTML.slice(0,400),rect:x.getBoundingClientRect().toJSON(),style:[...getComputedStyle(x)].map(k=>[k,getComputedStyle(x)[k]])})))),null,2));}
     assert.deepEqual(normalized(r.parts),normalized(b.parts),'Regular/small viewport activity changed: '+r.key+' '+phase+' '+width);assert.deepEqual(normalized(r.all),normalized(b.all),'Regular/small viewport layout changed: '+r.key+' '+width);
    }
    else {assert.ok(r.card,'Missing activity card '+r.key);assert.ok(r.scroll[0]<=width,'Horizontal overflow '+r.key);assert.ok(Math.abs(r.card.x+r.card.width/2-width/2)<2,'Card horizontal centering '+r.key);
     assert.ok(r.card.width/b.card.width>=1.20&&r.card.width/b.card.width<=1.30,'Card width not proportionally enlarged '+r.key);
     if(r.card.height<=height-220){assert.ok(Math.abs(r.card.y+r.card.height/2-height/2)<2,'Card vertical centering '+r.key);assert.ok(r.scroll[1]<=height+1,'Unnecessary scrolling '+r.key);}
     const important=r.parts.filter(p=>['BUTTON','IMG','CANVAS','H1','H2','VIDEO'].includes(p.tag)||/numbered-progress|eyebrow|wheel|^cell$/.test(p.cls));
     for(const p of important)assert.ok(p.rect.x>=r.card.x-2&&p.rect.right<=r.card.right+2&&p.rect.y>=r.card.y-2&&p.rect.bottom<=r.card.bottom+2,'Clipped '+r.key+' '+p.id+'/'+p.cls);
     for(const panel of r.panels)for(const button of panel.buttons)assert.ok(button.x>=panel.rect.x-2&&button.right<=panel.rect.right+2&&button.y>=panel.rect.y-2&&button.bottom<=panel.rect.bottom+2,'Button outside instruction panel '+r.key);
     const previousButtons=b.parts.filter(p=>p.tag==='BUTTON'),currentButtons=r.parts.filter(p=>p.tag==='BUTTON');
     if(previousButtons.length===currentButtons.length)for(let i=1;i<previousButtons.length;i++){
      const center=p=>p.rect.y+p.rect.height/2;
      if(Math.abs(center(previousButtons[i])-center(previousButtons[i-1]))<2)assert.ok(Math.abs(center(currentButtons[i])-center(currentButtons[i-1]))<4,'Buttons unexpectedly wrapped '+r.key);
     }
    }
   }
   if(width>=1000||variant==='after')await page.screenshot({path:path.join(dir,`scale125-${item.key}-${phase}-${width}-dpr${dpr}-${variant}.png`),fullPage:true,animations:'disabled'});
  }
  for(const [width,height]of sizes){await page.setViewportSize({width,height});await capture(state,width,height);}
  if(state==='initial'){
   const start=page.locator('#start,#lesson7Start').first();
   if(await start.count()&&await start.isVisible()){
    await start.click();if(item.key==='lesson-7-gawain-1'){await page.locator('#app .layout').waitFor();await page.locator('.lesson7-focus-picture.is-visible').waitFor();}else await page.waitForTimeout(150);for(const [width,height]of sizes){await page.setViewportSize({width,height});await capture('active',width,height);}
   }
   if(item.key==='lesson7-gawain2a'){await page.evaluate(()=>window.lesson7G2ARender({oral_reading_completed:true,current_phase:'handwriting'}));for(const [width,height]of sizes){await page.setViewportSize({width,height});await capture('handwriting',width,height);}}
  }
  errors.push({key:item.key,state,variant,errors:scriptErrors});await context.close();console.log('CHECKED '+item.key+' '+state+' '+variant);
 }
}finally{await browser.close();fs.writeFileSync(path.join(dir,`scale125-${audit?'audit':'report'}-dpr${dpr}${label}.json`),JSON.stringify({results,errors},null,2));}
console.log('PASS '+results.length+' rendered scaling comparisons');})().catch(e=>{console.error(e);process.exitCode=1;});
