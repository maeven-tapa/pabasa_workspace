// Native Chrome page zoom, using a disposable profile and local-only fixtures.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
let pw;try{pw=require('playwright-core')}catch{pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'))}
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const items=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'))),aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json')));
(async()=>{
 const extension=path.join(dir,'zoom-extension');fs.mkdirSync(extension,{recursive:true});
 fs.writeFileSync(path.join(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Local PABASA zoom audit',version:'1.0',permissions:['tabs'],background:{service_worker:'background.js'}}));
 fs.writeFileSync(path.join(extension,'background.js'),'chrome.runtime.onInstalled.addListener(() => {});');
 const profile=fs.mkdtempSync(path.join(dir,'zoom-profile-')),results=[];
 const context=await pw.chromium.launchPersistentContext(profile,{channel:'chrome',headless:true,ignoreDefaultArgs:['--disable-extensions'],args:['--enable-unsafe-extension-debugging'],viewport:{width:2560,height:1440},reducedMotion:'reduce'});
 try{
  const cdp=await context.browser().newBrowserCDPSession();await cdp.send('Extensions.loadUnpacked',{path:extension});
  const worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');
  for(const {key} of items){
   const page=await context.newPage();
   await page.route('**/*',route=>{
    const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();
    if(u.pathname.startsWith('/static/')){const k=decodeURIComponent(u.pathname.slice(8)),f=path.resolve(assets,aliases[k]||k);assert.ok(f.startsWith(assets+path.sep));return fs.existsSync(f)?route.fulfill({path:f}):route.fulfill({status:404})}
    if(u.pathname==='/activity/'+key)return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(dir,key+'-current.html'),'utf8')});
    return route.fulfill({json:{success:true}});
   });
   await page.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const a=new Native(...args);a.play=()=>Promise.resolve();return a};window.speechSynthesis.speak=()=>{}});
   await page.goto('http://localhost:9877/activity/'+key,{waitUntil:'load'});
   await page.evaluate(async()=>{await document.fonts.ready;window.__lessonStartReady=true;window.dispatchEvent(new Event('lesson-start-ready'));document.querySelectorAll('.lesson-start-backdrop,.lesson-one-welcome-modal').forEach(e=>e.style.display='none')});
   for(const zoom of [.75,1.25,1.5]){
    const actual=await worker.evaluate(async({key,zoom})=>{const t=(await chrome.tabs.query({})).find(t=>t.url?.includes('/activity/'+key));await chrome.tabs.setZoom(t.id,zoom);return chrome.tabs.getZoom(t.id)},{key,zoom});
    await page.waitForTimeout(120);
    const result=await page.evaluate(()=>({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth}));
    assert.ok(Math.abs(actual-zoom)<.001&&Math.abs(result.dpr-zoom)<.01,JSON.stringify({key,zoom,actual,...result}));
    assert.ok(Math.abs(result.width-2560/zoom)<2&&result.scrollWidth<=result.width,JSON.stringify({key,zoom,...result}));
    results.push({key,zoom,actual,...result});
   }
   await worker.evaluate(async key=>{const t=(await chrome.tabs.query({})).find(t=>t.url?.includes('/activity/'+key));await chrome.tabs.setZoom(t.id,1)},key);
   await page.close();console.log('PASS native zoom 75%, 125%, 150% '+key);
  }
  fs.writeFileSync(path.join(dir,'zoom-report.json'),JSON.stringify(results,null,2));
  console.log('PASS '+results.length+' native Chrome zoom layouts');
 }finally{
  await context.close();
  // Delete only this test's freshly created profile, inside the audit folder.
  assert.ok(profile.startsWith(dir+path.sep));fs.rmSync(profile,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);process.exitCode=1});
