// Isolated browser layout audit. Run audit_prescribed_responsive_render.py first.
// Requests never reach a web service. Intro gates are dismissed in the fixture;
// recording and progression behavior are covered by test_lesson1_video.cjs.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let pw;try{pw=require('playwright-core')}catch{pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'))}
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'))),report={activities:[],desktopComparisons:[],large:[],small:[],errors:[]};
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const onlyLarge=Boolean(process.env.PABASA_AUDIT_LARGE_ONLY),reportName=onlyLarge?'large-report.json':'report.json';
const desktop=[[1366,768],[1440,900],[1536,864],[1920,1080]],large=[[2560,1440],[3440,1440]],small=[[320,568],[375,667],[390,844],[768,1024],[1024,768]];
const filter=process.env.PABASA_AUDIT_KEYS?.split(',');
if(filter&&process.env.PABASA_AUDIT_MERGE){
 Object.assign(report,JSON.parse(fs.readFileSync(path.join(dir,reportName))));
 for(const field of ['activities','desktopComparisons','large','small','errors'])report[field]=report[field].filter(r=>!filter.includes(r.key));
}
(async()=>{
 const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:process.env.PABASA_AUDIT_SOFTWARE?['--disable-gpu']:[]});
 try{
  for(const item of manifest.filter(i=>!filter||filter.includes(i.key))){
   const context=await browser.newContext({viewport:{width:1366,height:768},reducedMotion:'reduce'});
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.origin!=='http://localhost:9877')return route.abort();
    if(u.pathname.startsWith('/static/')){
     const key=decodeURIComponent(u.pathname.slice(8));
     const file=path.resolve(assets,aliases[key]||key);
     assert.ok(file.startsWith(assets+path.sep));
     return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
    }
    if(u.pathname.startsWith('/activity/'))return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(dir,item.key+'-'+u.searchParams.get('variant')+'.html'),'utf8')});
    return route.fulfill({json:{success:true,progress:{current_index:0,completed_items:0,correct_items:0,activity_completed:false,state:{}}}});
   });
   const pages={};
   for(const variant of onlyLarge?['current']:['baseline','current']){
    const page=await context.newPage();pages[variant]=page;
    page.on('pageerror',e=>report.errors.push({key:item.key,variant,error:e.message,stack:e.stack}));
    await page.addInitScript(()=>{
     let seed=45;Math.random=()=>((seed=(seed*16807)%2147483647)-1)/2147483646;
     const native=window.Audio;window.Audio=function(...args){const a=new native(...args);a.play=()=>Promise.resolve();return a};
     window.speechSynthesis?.cancel();if(window.speechSynthesis)window.speechSynthesis.speak=()=>{};
    });
    await page.goto('http://localhost:9877/activity/'+item.key+'?variant='+variant,{waitUntil:'load'});
    await page.evaluate(async()=>{
     await document.fonts.ready;
     window.__lessonStartReady=true;window.dispatchEvent(new Event('lesson-start-ready'));
     document.querySelectorAll('.lesson-start-backdrop,.lesson-one-welcome-modal').forEach(e=>e.style.display='none');
     for(const v of document.querySelectorAll('video')){v.pause();v.currentTime=0;}
     await Promise.all([...document.images].map(i=>i.complete?null:new Promise(r=>{i.onload=r;i.onerror=r})));
    });
    await page.waitForTimeout(150);
   }
   for(const [width,height] of onlyLarge?[]:desktop){
    const buffers=[],styles=[];
    for(const variant of ['baseline','current']){
     const page=pages[variant];await page.setViewportSize({width,height});await page.bringToFront();await page.evaluate(()=>document.activeElement?.blur());await page.waitForTimeout(80);
     buffers.push(await page.screenshot({path:path.join(dir,item.key+'-'+width+'-'+variant+'.png'),animations:'disabled'}));
     styles.push(await page.evaluate(()=>JSON.stringify([...document.querySelectorAll('body,body *')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return{tag:e.tagName,id:e.id,rect:[r.x,r.y,r.width,r.height],style:[...s].sort().map(k=>[k,s.getPropertyValue(k)]).filter(([,v])=>v!=='')}}))));
    }
    const identical=buffers[0].equals(buffers[1]),stylesIdentical=styles[0]===styles[1];
    const pixels=identical?{significant:0,total:width*height}:await pages.current.evaluate(async values=>{
     const data=await Promise.all(values.map(async value=>{const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0)),bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'})),canvas=new OffscreenCanvas(bitmap.width,bitmap.height),c=canvas.getContext('2d');c.drawImage(bitmap,0,0);return c.getImageData(0,0,canvas.width,canvas.height).data}));
     let significant=0;for(let i=0;i<data[0].length;i+=4)if(Math.max(...[0,1,2].map(k=>Math.abs(data[0][i+k]-data[1][i+k])))>12)significant++;
     return{significant,total:data[0].length/4};
    },buffers.map(b=>b.toString('base64')));
    // Exact layout and computed styles are required. Permit only compositor
    // noise in less than 0.1% of screenshot pixels (blurred shadow edges).
    if(!stylesIdentical&&!identical)fs.writeFileSync(path.join(dir,item.key+'-'+width+'-styles.json'),JSON.stringify(styles.map(s=>JSON.parse(s)),null,2));
    // Follow-up requests explicitly correct the rhyme pages' Read labels and
    // centering, plus the two Session 2 pages' centering/content spacing.
    // Keep those changes visible; their focused regressions check the layouts.
    const requestedCorrection=['lesson-2-gawain-1','lesson-3-gawain-1','lesson-3-gawain-2','lesson-4-gawain-1','session-2-lesson-4-gawain-2','lesson-5-gawain-1','lesson-7-gawain-1','lesson7-gawain2b','lesson7-gawain2c','lesson7-gawain3','lesson7-gawain4','lesson7-gawain4a','lesson8-gawain1','lesson9-gawain1','lesson9-gawain2','lesson9-gawain3'].includes(item.key);
    report.desktopComparisons.push({key:item.key,width,height,identical,stylesIdentical,pixels,unchanged:identical||(stylesIdentical&&pixels.significant/pixels.total<.001),requestedCorrection});
   }
   for(const [width,height] of [...large,...(onlyLarge?[]:small)]){
    const page=pages.current;await page.setViewportSize({width,height});await page.waitForTimeout(80);
    const metrics=await page.evaluate(()=>{
     const el=document.querySelector('.page > .card,.app > .game,.app .shell > .game,.page > .shell,.app > .shell,.activity-page-wrapper > .app');
     const r=el?.getBoundingClientRect();
     return {viewport:[innerWidth,innerHeight],scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],card:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null,bodyClass:document.body.className,structure:[...document.querySelectorAll('.app,.page,.shell,.game,.card,.stage')].map(e=>({tag:e.tagName,cls:e.className,parent:e.parentElement.className,rect:e.getBoundingClientRect().toJSON(),css:Object.fromEntries(['display','position','left','top','transform','width','height','minHeight','maxWidth','margin','padding','alignItems','justifyContent','gridTemplateColumns','gridTemplateRows'].map(k=>[k,getComputedStyle(e)[k]]))})),canvases:[...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,css:c.getBoundingClientRect().toJSON()}))};
    });
    const detail=await page.evaluate(()=>({pictureOverflow:[...document.querySelectorAll('.reading .lesson7-golden-picture-box > img')].some(e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return r.x<p.x||r.y<p.y||r.right>p.right||r.bottom>p.bottom}),distortedWheel:[...document.querySelectorAll('.wheel')].some(e=>{const r=e.getBoundingClientRect();return r.width>0&&Math.abs(r.width-r.height)>1})}));
    const entry={key:item.key,width,height,...metrics,...detail};
    (width>=2500?report.large:report.small).push(entry);
    if(width>=2500||width===320)await page.screenshot({path:path.join(dir,item.key+'-'+width+'-current.png'),animations:'disabled'});
   }
   report.activities.push(item);
   await context.close();
   fs.writeFileSync(path.join(dir,reportName),JSON.stringify(report,null,2));
   console.log('AUDITED '+item.key);
  }
 }finally{await browser.close()}
 for(const r of report.desktopComparisons)if(r.identical)r.unchanged=true;
 fs.writeFileSync(path.join(dir,reportName),JSON.stringify(report,null,2));
 const changed=report.desktopComparisons.filter(r=>!r.unchanged&&!r.requestedCorrection),overflow=report.large.filter(r=>r.scroll[0]>r.width||r.scroll[1]>r.height);
 console.log(JSON.stringify({activities:report.activities.length,desktopComparisons:report.desktopComparisons.length,changed,largeOverflow:overflow,errors:report.errors},null,2));
 assert.equal(changed.length,0,'Regular desktop screenshots differ from HEAD');
 assert.equal(overflow.length,0,'Large-screen document overflow');
 assert.ok(report.large.every(r=>r.card&&Math.abs(r.card.x+r.card.width/2-r.width/2)<1),'Large-screen card shifted horizontally');
 assert.ok(report.large.every(r=>!r.pictureOverflow&&!r.distortedWheel),'Picture overflow or distorted wheel');
 assert.ok(report.small.every(r=>r.scroll[0]<=r.width),'Narrow-screen document horizontal overflow');
})().catch(e=>{console.error(e);process.exitCode=1});
