// Browser regression for reading audio posted through a progress endpoint.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.CRLA_PLAYWRIGHT_PATH||'playwright-core');
const root=path.resolve(__dirname,'..','pabasa_site/pabasa_app/static/pabasa_app/js');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();
  await page.goto('about:blank');
  await page.setContent('<div data-prescribed-session-controls data-prefix="prescribed-session-target"></div>');
  await page.evaluate(()=>{
   window.PrescribedControls={init:config=>window.__adapter=config.adapter};
   window.__pending=[];window.fetch=(input,init)=>new Promise((resolve,reject)=>{
    const job={input,init,resolve,reject};window.__pending.push(job);
    init.signal?.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
   });
   window.Basahin={cancelAll:()=>{}};
  });
  await page.addScriptTag({content:fs.readFileSync(path.join(root,'prescribed_pending_saves.js'),'utf8')});
  await page.addScriptTag({content:fs.readFileSync(path.join(root,'prescribed_session8_11_controls.js'),'utf8')});
  await page.evaluate(()=>{
   const audio=new FormData();audio.append('audio',new Blob(['synthetic'],{type:'audio/webm'}),'reading.webm');
   window.__reading=fetch('/api/activity/progress/',{method:'POST',body:audio}).then(()=> 'accepted',error=>error.name);
   window.__adapter.pause();
  });
  const cancelled=await page.evaluate(()=>window.__pending[0].init.signal.aborted);
  assert.equal(cancelled,true,'Pause must cancel speech posted to the progress endpoint');
  assert.equal(await page.evaluate(()=>window.__reading),'AbortError');
  assert.equal(await page.evaluate(()=>window.PabasaPrescribedPending.pending()),0,'A cancelled reading must not block Leave as an unsaved draft');
  await page.evaluate(()=>{
   window.__saving=fetch('/api/activity/progress/',{method:'POST',body:JSON.stringify({action:'draft'})});
   window.__adapter.pause();
  });
  assert.equal(await page.evaluate(()=>window.__pending[1].init.signal.aborted),false,'Pause must preserve a JSON progress save');
  await page.evaluate(()=>window.__pending[1].resolve(new Response(JSON.stringify({success:true,state:{revision:1}}))));
  await page.evaluate(()=>window.PabasaPrescribedPending.flush());
  await page.evaluate(()=>{
   const recording=new FormData();recording.append('audio',new Blob(['synthetic'],{type:'audio/webm'}),'saved-recording.webm');
   window.__upload=fetch('/api/activity/recording/',{method:'POST',body:recording});
   window.__adapter.pause();
  });
  assert.equal(await page.evaluate(()=>window.__pending[2].init.signal.aborted),false,'Pause must preserve an already captured recording upload');
  await page.evaluate(()=>window.__pending[2].resolve(new Response(JSON.stringify({success:true,recording_id:1}))));
  await page.evaluate(()=>window.PabasaPrescribedPending.flush());
  console.log(JSON.stringify({passed:true,reading_audio_cancelled:true,json_save_preserved:true,recording_upload_preserved:true}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
