// Actual workbook UI in 30 isolated Chrome contexts; network faults are local.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const {chromium}=require(process.env.CRLA_PLAYWRIGHT_PATH||'playwright-core');
const root=path.resolve(__dirname,'..'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const render=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import os,sys,json
from types import SimpleNamespace
sys.path.insert(0,'pabasa_site');os.environ['DJANGO_SETTINGS_MODULE']='pabasa_site.settings'
import django;django.setup()
from django.template.loader import render_to_string
from pabasa_app.prescribed_workbook import get_activity,initial_s9_a1_state
request=SimpleNamespace(session={'user_id':1,'user_role':'student'},aral_draft_scope='__OWNER__:term1',path='/activity/')
print(json.dumps(render_to_string('pabasa_app/prescribed_workbook_page.html',{'request':request,'csrf_token':'synthetic-csrf','workbook_payload':{'activity':get_activity('aral-s9-a1-family-drawing'),'state':initial_s9_a1_state(),'preview':False,'progress_url':'/api/progress/','back_url':'/dashboard/assessment/'}})))
`],{cwd:root,encoding:'utf8',env:{...process.env,DB_ENGINE:'sqlite',SQLITE_PATH:':memory:',PYTHONIOENCODING:'utf-8'}});
assert.equal(render.status,0,render.stderr);const template=JSON.parse(render.stdout),origin='http://localhost:9883';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const summaries=[];
 try {
  for(let batch=0;batch<3;batch++)await Promise.all(Array.from({length:10},async(_,j)=>{
   const id=batch*10+j,context=await browser.newContext(),page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));let offline=true,release=null,saves=0;
   let server={index:0,answers:{},draft:{text:'',strokes:[]},completed:false,revision:0};
   await context.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/activity/')return route.fulfill({contentType:'text/html',body:template.replaceAll('__OWNER__',String(id)).replace(/"revision": 0/,`"revision": ${server.revision}`)});
    if(url.pathname==='/later/')return route.fulfill({contentType:'text/html',body:`<a id="lesson31a1-back" href="/dashboard/assessment/">Back</a><script src="/static/pabasa_app/js/prescribed_pending_saves.js" defer></script><script src="/static/pabasa_app/js/prescribed_leave_confirmation.js" defer></script>`});
    if(url.pathname.startsWith('/static/')){
     const file=path.resolve(assets,decodeURIComponent(url.pathname.slice(8)));
     if(file.startsWith(assets+path.sep)&&fs.existsSync(file))return route.fulfill({path:file});
     return route.fulfill({status:404,body:''});
    }
    if(url.pathname==='/api/progress/'){
     if(offline)return route.abort('internetdisconnected');
     const body=route.request().postDataJSON();saves++;
     if(release!==null)await new Promise(resolve=>release=resolve);
     if(body.revision!==server.revision)return route.fulfill({status:409,json:{success:false,error:'Conflict',state:server}});
     server={...server,draft:body.draft,revision:server.revision+1};return route.fulfill({json:{success:true,state:server}});
    }
    if(url.pathname==='/dashboard/assessment/')return route.fulfill({contentType:'text/html',body:'Saved return page'});
    return route.fulfill({status:404,body:''});
   });
   await page.goto(origin+'/activity/');await page.locator('#wb-s9-start-button').click();
   const text=`This is my family. ${id}`;await page.locator('#wb-written').fill(text);
   await page.waitForTimeout(1200);
   assert.equal(await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('pabasa_aral_draft:')).length),1);
   await page.reload();await page.locator('#wb-s9-start-button').click();
   assert.equal(await page.locator('#wb-written').inputValue(),text);
   offline=false;release=true;
   await page.locator('#wb-written').fill(text+' restored');
   await page.waitForFunction(()=>window.PabasaPrescribedPending?.pending()>0).catch(async error=>{console.error(JSON.stringify({id,saves,errors,state:await page.evaluate(()=>({pending:window.PabasaPrescribedPending?.pending(),wrapped:window.fetch.__prescribedSessionWrapped,status:document.getElementById('wb-status')?.textContent,root:Boolean(document.querySelector('[data-prescribed-session-controls]'))}))}));throw error;});
   await page.locator('[id$="-audio-settings-btn"]').click();
   // Pause must leave the progress request running.
   assert.equal(await page.evaluate(()=>window.PabasaPrescribedPending.pending()),1);
   await page.locator('[id$="-resume"]').click();
   await page.locator('#wb-back').click();
   await page.waitForTimeout(100);assert.ok(page.url().endsWith('/activity/'));
   release();release=null;
   await page.waitForURL('**/dashboard/assessment/');assert.equal(server.draft.text,text+' restored');
   assert.equal(server.revision,saves);assert.ok(saves>=1&&saves<=2);assert.equal(errors.length,0,JSON.stringify(errors));
   await page.goto(origin+'/later/');release=true;
   await page.evaluate(revision=>{fetch('/api/progress/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,draft:{text:'Later session checkpoint'}})});},server.revision);
   await page.waitForFunction(()=>window.PabasaPrescribedPending?.pending()>0);
   await page.locator('#lesson31a1-back').click();await page.locator('#lesson31a1-leave-yes').click();
   await page.waitForTimeout(100);assert.ok(page.url().endsWith('/later/'));release();release=null;
   await page.waitForURL('**/dashboard/assessment/');assert.equal(server.draft.text,'Later session checkpoint');assert.equal(errors.length,0,JSON.stringify(errors));
   summaries.push({student:id,restored:true,pause_preserved_save:true,leave_waited:true,later_leave_waited:true,saves});
   await context.close();
  }));
  console.log(JSON.stringify({contexts:summaries.length,passed:summaries.length,errors:0,scope:'30 isolated Chrome sessions; offline draft, reload, pause during save, workbook leave and Session 15 leave wait. Mock HTTP only.'}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
