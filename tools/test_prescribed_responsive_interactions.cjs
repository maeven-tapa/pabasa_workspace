// Local fixtures only: verify pointer geometry after layout resizing.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let pw;try{pw=require('playwright-core')}catch{pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'))}
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
const dpr=Number(process.env.PABASA_AUDIT_DPR||1);
(async()=>{
 const browser=await pw.chromium.launch({channel:'chrome',headless:true});
 try{
  for(const key of ['lesson7-gawain2a','lesson7-gawain2c','lesson7-gawain4','lesson8-gawain1','lesson7-gawain4a']){
   const page=await browser.newPage({viewport:{width:2560,height:1440},deviceScaleFactor:dpr,reducedMotion:'reduce'});
   await page.route('**/*',route=>{
    const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
    if(u.pathname.startsWith('/static/')){const k=decodeURIComponent(u.pathname.slice(8)),f=path.resolve(assets,aliases[k]||k);assert.ok(f.startsWith(assets+path.sep));return fs.existsSync(f)?route.fulfill({path:f}):route.fulfill({status:404})}
    if(u.pathname==='/activity/'+key)return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(dir,key+'-current.html'),'utf8')});
    return route.fulfill({json:{success:true}});
   });
   await page.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>{setTimeout(()=>{a.dispatchEvent(new Event('ended'))},20);return Promise.resolve()};return a};window.speechSynthesis.speak=()=>{}});
   await page.goto('http://localhost:9877/activity/'+key,{waitUntil:'load'});
   await page.evaluate(async()=>{await document.fonts.ready;window.__lessonStartReady=true;window.dispatchEvent(new Event('lesson-start-ready'));document.querySelectorAll('.lesson-start-backdrop').forEach(e=>e.style.display='none')});
   if(key==='lesson7-gawain2a')await page.evaluate(()=>window.lesson7G2ARender({oral_reading_completed:true,current_phase:'handwriting'}));
   await page.waitForTimeout(300);
   for(const [width,height] of [[2560,1440],[3440,1440],[390,844],[1440,900]]){
    await page.setViewportSize({width,height});await page.waitForTimeout(100);
    if(key==='lesson7-gawain4a'){
     const cell=page.locator('.cell').first();
     if(await cell.locator('.stamp').count())await cell.click();
     await page.locator('.tool[data-shape="square"]').dragTo(page.locator('.cell').first());
     await page.locator('.cell .stamp.square').first().waitFor();
     console.log('PASS drag target '+width+' '+key);
    }else{
     const canvas=page.locator('canvas').first();await canvas.scrollIntoViewIfNeeded();
     await canvas.evaluate(c=>c.getContext('2d').clearRect(0,0,c.width,c.height));
     const r=await canvas.boundingBox();assert.ok(r&&r.width>0&&r.height>0);
     await page.mouse.move(r.x+r.width*.6,r.y+r.height*.55);await page.mouse.down();await page.mouse.move(r.x+r.width*.7,r.y+r.height*.55,{steps:6});await page.mouse.up();
     const ink=await canvas.evaluate(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height);let minX=c.width,maxX=0,minY=c.height,maxY=0;for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++)if(d.data[(y*c.width+x)*4+3]>30){minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y)}return{left:minX/c.width,right:maxX/c.width,top:minY/c.height,bottom:maxY/c.height}});
     assert.ok(Math.abs((ink.left+ink.right)/2-.65)<.06&&Math.abs((ink.top+ink.bottom)/2-.55)<.06,JSON.stringify({key,width,ink}));
     console.log('PASS canvas alignment '+width+' '+key);
    }
    if(width>=2500&&dpr===1)await page.screenshot({path:path.join(dir,key+'-interaction-'+width+'.png'),animations:'disabled'});
   }
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
