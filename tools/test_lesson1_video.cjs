// Local-only browser regression suite: no live service, accounts or stored audio.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
let pw;try{pw=require(process.env.PABASA_PLAYWRIGHT_PATH||'playwright-core')}catch{pw=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'))}
const root=path.resolve(__dirname,'..'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const rendered=spawnSync(process.env.PABASA_PYTHON||'python',['-c',[
'import json,os,sys',"sys.path.insert(0,'pabasa_site')","os.environ['DJANGO_SETTINGS_MODULE']='pabasa_site.settings'",
'import django','django.setup()','from django.template.loader import render_to_string','pages={}',
"for status in ('ready','submitted','retry','checked'):",
" data={'submission_url':'/api/lesson-1-gawain-1/submit/','submission_status':status,'progress':{'activity_completed':status=='checked','state':{'retry_requested':status=='retry'}}}",
" pages[status]=render_to_string('pabasa_app/lesson_1_gawain_1_page.html',{'lesson_1_data':data})",
'print(json.dumps(pages))'].join('\n')],{cwd:root,encoding:'utf8'});
assert.equal(rendered.status,0,rendered.stderr);const html=JSON.parse(rendered.stdout);
(async()=>{
const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const passed=[];
async function open(mode='',status='ready'){
 const context=await browser.newContext({viewport:{width:1440,height:900},permissions:['microphone']}),page=await context.newPage(),errors=[];
 let posts=0,persisted=status,failSubmit=mode.endsWith('submit-failure');page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({mode})=>{
  window.audit={streams:[],recorders:[],micRequests:0,counts:[],starts:[],stops:0,narrations:[]};
  if(mode==='narration-timeout'){
   const timer=window.setTimeout.bind(window);
   window.setTimeout=(fn,delay,...args)=>timer(fn,delay===60000&&audit.narrations.length===0?100:delay,...args);
  }
  const A=window.Audio;window.Audio=function(...args){
   const a=new A(...args),url=String(args[0]);
   if(url.includes('hello_ka-basa')||url.includes('alpabeto_recording_reminder')){
    const nativePlay=a.play.bind(a),nativePause=a.pause.bind(a);
    let entry;
    a.pause=()=>{if(entry)entry.playing=false;return nativePause()};
    a.addEventListener('playing',()=>{entry.playing=true});
    a.addEventListener('ended',()=>{entry.playing=false;entry.ended=true;entry.endedAt=performance.now()});
    a.play=()=>{
     entry={url,playing:false,ended:false,at:performance.now(),audio:a,
      message:document.querySelector('[data-welcome-message]').textContent,
      disabled:[...document.querySelectorAll('[data-welcome-choice]')].map(b=>b.disabled),
      previousActive:audit.narrations.filter(n=>n.playing).length,savedEnd:a.onended,
      finish:()=>{entry.playing=false;entry.ended=true;entry.endedAt=performance.now();a.onended?.()},
      fail:()=>a.onerror?.()};
     audit.narrations.push(entry);
     audit.modal ||= document.querySelector('.lesson-one-welcome-modal');
     if(mode==='narration-denied'&&audit.narrations.length===1)return Promise.reject(new DOMException('Blocked','NotAllowedError'));
     if(mode==='narration-real')return nativePlay().catch(error=>{entry.failed=true;throw error});
     entry.playing=true;
     if(!mode.startsWith('narration-'))queueMicrotask(entry.finish);
     return Promise.resolve();
    };
   }
   return a;
  };
  const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{
   audit.micRequests++;if(mode==='denied'&&audit.micRequests===1)throw new DOMException('Denied','NotAllowedError');
   if(mode==='delayed')await new Promise(r=>audit.allowMic=r);
   const s=await gum(c);audit.streams.push(s);return s};
  const R=window.MediaRecorder;window.MediaRecorder=class extends R{
   constructor(...args){super(...args);audit.recorders.push(this);if(mode==='empty')this.addEventListener('dataavailable',e=>e.stopImmediatePropagation());this.addEventListener('stop',()=>audit.stops++)}
   start(...args){audit.starts.push({time:document.querySelector('video').currentTime,muted:document.querySelector('video').muted});if(mode==='recorder-error')throw Error('Recorder failed');return super.start(...args)}
  };
  const fetchNative=window.fetch;window.fetch=(url,init)=>{if(init?.body instanceof FormData)audit.blob=init.body.get('audio');return fetchNative(url,init)};
  document.addEventListener('DOMContentLoaded',()=>{
   if(!document.getElementById('lesson-one-feedback'))return;
   new MutationObserver(()=>{const o=document.getElementById('lesson-one-feedback');if(/^[1-5]$/.test(o.textContent))audit.counts.push({n:o.textContent,paused:document.querySelector('video').paused,indicatorHidden:document.getElementById('lesson-one-recording-indicator').hidden,at:performance.now()})}).observe(document.getElementById('lesson-one-feedback'),{childList:true});
   if(mode==='playback-error')document.querySelector('video').play=()=>Promise.reject(Error('Playback failed'));
  });
 },{mode});
 await page.route('http://localhost:9876/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(p.startsWith('/static/')){const file=path.resolve(assets,decodeURIComponent(p.slice(8)));assert.ok(file.startsWith(assets+path.sep));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404})}
  if(p==='/activity')return route.fulfill({contentType:'text/html',body:html[persisted]});
  if(p==='/api/lesson-1-gawain-1/submit/'){posts++;assert.ok(route.request().postDataBuffer().length>100);if(failSubmit){failSubmit=false;return route.fulfill({status:503,json:{success:false}})}persisted='submitted';return route.fulfill({json:{success:true,submission_id:1,status:'submitted'}})}
  return route.fulfill({contentType:'text/html',body:'<p>Local navigation destination</p>'});
 });
 await page.goto('http://localhost:9876/activity');
 assert.equal(await page.locator('#lesson-one-recording-indicator').isVisible(),false);
 const confirm=async()=>{await page.locator('[data-welcome-choice="yes"]:enabled').waitFor();await page.locator('[data-welcome-choice="yes"]').click()};
 const playing=()=>page.waitForFunction(()=>document.querySelector('video').currentTime>0&&audit.recorders.at(-1)?.state==='recording'&&!document.getElementById('lesson-one-recording-indicator').hidden);
 const finish=async()=>{await playing();await page.evaluate(()=>{document.querySelector('video').playbackRate=16})};
 const stopped=async()=>{assert.ok(await page.evaluate(()=>audit.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))));assert.equal(await page.locator('#lesson-one-recording-indicator').isVisible(),false)};
 const close=async name=>{assert.deepEqual(errors,[]);passed.push(name);console.log('PASS: '+name);await context.close()};
 return{page,confirm,playing,finish,stopped,close,posts:()=>posts,status:s=>persisted=s};
}
try{
 if(process.env.PABASA_VIDEO_NARRATION_ONLY){
  const first='Sabay nating panuorin at pakinggan ang Awiting Alpabeto ng Filipino. Handa ka na ba?';
  const second='Magsisimula ang pag-record ng iyong boses kasabay ng pagtugtog ng Awiting Alpabeto ng Filipino. Kaya ihanda ang iyong sarili at sabayan ang awitin!';
  const choices=r=>r.page.locator('[data-welcome-choice]');
  const disabled=async r=>assert.deepEqual(await choices(r).evaluateAll(buttons=>buttons.map(b=>b.disabled)),[true,true]);
  const finish=async(r,index)=>r.page.evaluate(i=>audit.narrations[i].finish(),index);
  const count=async(r,n)=>r.page.waitForFunction(n=>audit.narrations.length===n,n);
  const blocked=async r=>{
   await disabled(r);
   await r.page.evaluate(()=>document.querySelectorAll('[data-welcome-choice]').forEach(b=>{b.click();b.dispatchEvent(new MouseEvent('click',{bubbles:true}));b.onclick()}));
   assert.equal(await r.page.evaluate(()=>audit.micRequests),0);assert.equal(r.page.url(),'http://localhost:9876/activity');
  };
  {
   const r=await open('narration-controlled');await count(r,1);await blocked(r);
   assert.equal(await r.page.locator('[data-welcome-message]').textContent(),first);
   await finish(r,0);await count(r,2);await blocked(r);
   assert.equal(await r.page.locator('[data-welcome-message]').textContent(),second);
   fs.mkdirSync(path.join(root,'tmp'),{recursive:true});
   for(const viewport of [{width:1440,height:900},{width:390,height:844},{width:844,height:390}]){
    await r.page.setViewportSize(viewport);
    const bounds=await r.page.locator('.lesson-one-welcome-card').boundingBox();
    assert.ok(bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=viewport.width&&bounds.y+bounds.height<=viewport.height);
    await r.page.screenshot({path:path.join(root,'tmp/lesson1-reminder-modal-'+viewport.width+'.png')});
   }
   assert.ok(await r.page.evaluate(()=>audit.narrations.every(n=>n.previousActive===0&&n.disabled.every(Boolean))));
   await finish(r,1);await r.page.locator('[data-welcome-choice="yes"]:enabled').waitFor();
   assert.deepEqual(await choices(r).evaluateAll(bs=>bs.map(b=>b.disabled)),[false,false]);
   await r.confirm();await r.page.waitForFunction(()=>audit.counts.length>0);
   await r.page.evaluate(()=>window.lessonOneVideoFlow.interrupt());await count(r,3);await disabled(r);
   assert.equal(await r.page.locator('[data-welcome-message]').textContent(),first);
   assert.ok(await r.page.evaluate(()=>audit.modal===document.querySelector('.lesson-one-welcome-modal')));
   await r.page.evaluate(()=>{audit.narrations[0].savedEnd();audit.narrations[1].savedEnd()});await disabled(r);
   assert.equal(await r.page.evaluate(()=>audit.narrations.length),3);
   await finish(r,2);await count(r,4);await disabled(r);await finish(r,3);
   await r.page.locator('[data-welcome-choice="no"]:enabled').click();await r.page.waitForURL('**/dashboard/assessment/');
   assert.equal(r.posts(),0);await r.close('two ordered messages, no intermediate enablement/overlap, disabled/direct clicks blocked, same-modal reopen/reset and Hindi navigation');
  }
  for(const failure of ['play-rejection','second-audio-error','timeout']){
   const r=await open(failure==='play-rejection'?'narration-denied':failure==='timeout'?'narration-timeout':'narration-controlled');await count(r,1);
   if(failure==='second-audio-error'){await finish(r,0);await count(r,2);await r.page.evaluate(()=>audit.narrations[1].fail())}
   await r.page.locator('[data-welcome-retry]:visible').waitFor();await blocked(r);
   const before=await r.page.evaluate(()=>audit.narrations.length);
   await r.page.locator('[data-welcome-retry]').click();await count(r,before+1);
   await r.page.evaluate(()=>document.querySelector('[data-welcome-retry]').onclick());await count(r,before+1);await disabled(r);
   assert.equal(await r.page.locator('[data-welcome-message]').textContent(),first);
   if(failure==='second-audio-error'){await r.page.evaluate(()=>audit.narrations[1].savedEnd());await disabled(r)}
   await finish(r,before);await count(r,before+2);await disabled(r);await finish(r,before+1);
   await r.page.locator('[data-welcome-choice="yes"]:enabled').waitFor();await r.confirm();await r.playing();
   assert.equal(r.posts(),0);await r.close(failure+' keeps choices disabled, retries full sequence once, then continues microphone/countdown/video/recording');
  }
  {
   const r=await open('narration-submit-failure');await count(r,1);await finish(r,0);await count(r,2);await finish(r,1);
   await r.confirm();await r.finish();await r.page.locator('.lesson-one-welcome-modal').waitFor({timeout:12000});await count(r,3);
   await disabled(r);assert.equal(r.posts(),1);
   assert.equal(await r.page.locator('[data-welcome-retry]').isVisible(),false);
   await finish(r,2);await count(r,4);await disabled(r);await finish(r,3);
   await r.page.locator('[data-welcome-retry]:visible').waitFor();
   assert.deepEqual(await choices(r).evaluateAll(bs=>bs.map(b=>b.disabled)),[true,false]);
   await r.page.locator('[data-welcome-retry]').click();await r.page.locator('#completion.show').waitFor();
   assert.equal(r.posts(),2);assert.equal(await r.page.evaluate(()=>audit.recorders.length),1);await r.stopped();
   await r.close('upload retry also narrates before enabling choices and reuses finalized audio without rerecording');
  }
  for(const close of ['first-pagehide','second-pagehide','second-modal-remove']){
   const r=await open('narration-controlled');await count(r,1);
   const index=close.startsWith('second')?1:0;
   if(index){await finish(r,0);await count(r,2)}
   await r.page.evaluate(close=>{if(close.endsWith('modal-remove'))document.querySelector('.lesson-one-welcome-modal').remove();else window.dispatchEvent(new Event('pagehide'))},close);
   await r.page.waitForFunction(i=>!audit.narrations[i].playing,index);
   await r.page.evaluate(i=>audit.narrations[i].savedEnd(),index);
   assert.equal(await r.page.evaluate(()=>audit.narrations.length),index+1);
   assert.deepEqual(await r.page.evaluate(()=>[...audit.modal.querySelectorAll('[data-welcome-choice]')].map(b=>b.disabled)),[true,true]);
   assert.equal(await r.page.evaluate(()=>audit.micRequests),0);await r.close(close+' stops narration and ignores stale completion');
  }
  {
   const r=await open('narration-real');await count(r,1);
   await r.page.waitForFunction(()=>audit.narrations[0].failed||audit.narrations[0].playing);
   if(await r.page.evaluate(()=>audit.narrations[0].failed))await r.page.locator('[data-welcome-retry]:visible').click();
   await r.page.locator('[data-welcome-choice="yes"]:enabled').waitFor({timeout:60000});
   const completed=await r.page.evaluate(()=>audit.narrations.filter(n=>n.ended).map(n=>({url:n.url,at:n.at,end:n.endedAt,disabled:n.disabled,overlap:n.previousActive})));
   assert.equal(completed.length,2);assert.ok(completed[0].url.includes('hello_ka-basa'));assert.ok(completed[1].url.includes('alpabeto_recording_reminder'));
   assert.ok(completed[1].at>=completed[0].end);assert.ok(completed.every(n=>n.overlap===0&&n.disabled.every(Boolean)));
   assert.equal(await r.page.evaluate(()=>audit.micRequests),0);await r.close('both actual local MP3s play to natural completion in order under normal browser autoplay policy');
  }
  console.log('PASS: '+passed.length+' narration scenarios.');return;
 }
 {
  const r=await open();await r.confirm();await r.playing();
  const badge=r.page.locator('#lesson-one-recording-indicator');
  assert.equal(await badge.locator('[data-recording-label]').textContent(),'Nagre-record…');
  assert.ok((await r.page.evaluate(()=>audit.counts)).every(count=>count.indicatorHidden),'Countdown must not claim recording is active');
  fs.mkdirSync(path.join(root,'tmp'),{recursive:true});
  for(const viewport of[{width:1440,height:900},{width:390,height:844},{width:844,height:390}]){
   await r.page.setViewportSize(viewport);
   const card=await r.page.locator('.shell').boundingBox(),bounds=await badge.boundingBox();
   assert.ok(bounds.x>=card.x&&bounds.y>=card.y&&bounds.x+bounds.width<=card.x+card.width&&bounds.y+bounds.height<=card.y+card.height);
   assert.ok(await r.page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight&&document.documentElement.scrollWidth<=innerWidth));
   await r.page.screenshot({path:path.join(root,'tmp/lesson1-recording-indicator-'+viewport.width+'.png')});
  }
  await r.page.evaluate(()=>document.querySelector('video').dispatchEvent(new Event('waiting')));
  await badge.locator('[data-recording-label]').filter({hasText:'Naka-pause ang recording'}).waitFor();
  assert.equal(await r.page.evaluate(()=>audit.recorders[0].state),'paused');
  assert.equal(await badge.locator('.lesson-one-recording-dot').evaluate(dot=>getComputedStyle(dot).animationName),'none');
  await r.page.evaluate(()=>document.querySelector('video').dispatchEvent(new Event('playing')));await r.playing();
  assert.equal(await badge.locator('[data-recording-label]').textContent(),'Nagre-record…');
  await r.page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await badge.locator('.lesson-one-recording-dot').evaluate(dot=>getComputedStyle(dot).animationName),'none');
  await r.finish();await r.page.locator('#completion.show').waitFor({timeout:12000});await r.stopped();assert.equal(r.posts(),1);
  await r.close('main-area recording indicator follows capture, buffering/resume and natural stop; responsive and reduced-motion layouts');
  if(process.env.PABASA_VIDEO_INDICATOR_ONLY)return;
 }
 if(process.env.PABASA_VIDEO_LAYOUT_ONLY){
  const r=await open();await r.confirm();await r.playing();
  await r.page.setViewportSize({width:844,height:390});
  const tools=await r.page.locator('.s1-controls-tools').boundingBox(),card=await r.page.locator('.shell').boundingBox();
  assert.ok(tools.y+tools.height<=card.y);
  await r.page.screenshot({path:path.join(root,'tmp/lesson1-video-844.png')});
  await r.close('landscape controls remain above the video card');return;
 }
 if(!process.env.PABASA_VIDEO_QUICK){
 const r=await open();await r.page.waitForFunction(()=>document.querySelector('video').readyState>=2);
 assert.equal(await r.page.locator('.lesson-one-welcome-modal').count(),1);assert.equal(await r.page.locator('.lesson-start-backdrop').count(),0);
 assert.deepEqual(await r.page.locator('.shell').evaluate(e=>[...e.children].map(c=>c.tagName)),['VIDEO','OUTPUT']);
 await r.confirm();await r.playing();const counts=await r.page.evaluate(()=>audit.counts);
 assert.deepEqual(counts.map(c=>c.n),['5','4','3','2','1']);assert.ok(counts.every(c=>c.paused&&c.indicatorHidden));assert.ok(counts[4].at-counts[0].at>=3900);
 assert.ok(await r.page.evaluate(()=>audit.starts[0].time<.2&&!audit.starts[0].muted));assert.equal(r.posts(),0);
 fs.mkdirSync(path.join(root,'tmp'),{recursive:true});await r.page.screenshot({path:path.join(root,'tmp/lesson1-video-desktop.png')});
 for(const viewport of[{width:390,height:844},{width:844,height:390}]){
  await r.page.setViewportSize(viewport);assert.ok(await r.page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight&&document.documentElement.scrollWidth<=innerWidth));
  assert.equal(await r.page.locator('video').evaluate(e=>getComputedStyle(e).objectFit),'contain');await r.page.screenshot({path:path.join(root,'tmp/lesson1-video-'+viewport.width+'.png')});
 }
 await r.page.locator('#completion.show').waitFor({timeout:100000});assert.equal(r.posts(),1);assert.match(await r.page.locator('#completion').innerText(),/Naghihintay sa guro/);
 assert.deepEqual(await r.page.evaluate(()=>({recorders:audit.recorders.length,stops:audit.stops})),{recorders:1,stops:1});
 const duration=await r.page.evaluate(async()=>{const c=new AudioContext();try{return(await c.decodeAudioData(await audit.blob.arrayBuffer())).duration}finally{await c.close()}});
 assert.ok(duration>85&&duration<92,'Recorded duration '+duration);await r.stopped();r.status('retry');
 await r.page.locator('.lesson-one-welcome-modal').waitFor({timeout:7000});assert.equal(await r.page.locator('.lesson-one-welcome-modal').count(),1);
 await r.close('real 88-second playback/capture, countdown, natural end, auto-submit, responsive layout, teacher retry');
 }
 for(const mode of(process.env.PABASA_VIDEO_MODES?.split(',')||['denied','playback-error','recorder-error','empty','submit-failure'])){
  console.log('Checking '+mode);const r=await open(mode);await r.confirm();if(mode==='empty'||mode==='submit-failure')await r.finish();
  await r.page.locator('.lesson-one-welcome-modal').waitFor({timeout:12000}).catch(async e=>{console.log(await r.page.evaluate(()=>({time:document.querySelector('video').currentTime,ended:document.querySelector('video').ended,paused:document.querySelector('video').paused,recorders:audit.recorders.map(r=>r.state),stops:audit.stops,output:document.querySelector('#lesson-one-feedback').textContent,completion:document.querySelector('#completion').className})));throw e});assert.equal(await r.page.locator('#completion.show').count(),0);await r.stopped();
  if(mode==='denied'){await r.confirm();await r.playing();assert.equal(await r.page.evaluate(()=>audit.micRequests),2)}
  else if(mode==='submit-failure'){assert.equal(r.posts(),1);await r.page.locator('[data-welcome-retry]').click();await r.page.locator('#completion.show').waitFor();assert.equal(r.posts(),2);assert.equal(await r.page.evaluate(()=>audit.recorders.length),1)}
  else assert.equal(r.posts(),0);await r.close(mode);
 }
 const d=await open('delayed');await d.confirm();assert.equal(await d.page.locator('#lesson-one-feedback').innerText(),'Inihahanda ang mikropono…');assert.equal(await d.page.evaluate(()=>audit.counts.length),0);
 await d.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));await d.page.evaluate(()=>audit.allowMic());await d.page.waitForFunction(()=>audit.streams.length===1);await d.stopped();assert.equal(d.posts(),0);await d.close('late permission after exit');
 for(const phase of['countdown','playback']){
  const r=await open();await r.confirm();if(phase==='playback')await r.playing();else await r.page.waitForFunction(()=>audit.counts.length>0);
  await r.page.locator('.back').click();await r.page.locator('#prescribed-s1l1g1-leave-no').click();assert.equal(await r.page.locator('.lesson-one-welcome-modal').count(),0);
  await r.page.locator('.back').click();await r.page.locator('#prescribed-s1l1g1-leave-yes').click();await r.page.waitForURL('**/dashboard/assessment/');assert.equal(r.posts(),0);await r.close('leave/stay '+phase);
 }
 for(const action of ['pause','mute','unexpected-stop']){
  const r=await open();await r.confirm();await r.playing();
  if(action==='pause'){
   await r.page.locator('#prescribed-s1l1g1-audio-settings-btn').click();
   await r.page.locator('#prescribed-s1l1g1-resume').click();
  }else if(action==='mute')await r.page.locator('#prescribed-s1l1g1-mic-toggle').click();
  else await r.page.evaluate(()=>audit.recorders[0].stop());
  await r.page.locator('.lesson-one-welcome-modal').waitFor();await r.stopped();assert.equal(r.posts(),0);
  await r.confirm();await r.playing();assert.equal(await r.page.evaluate(()=>audit.micRequests),2);
  await r.close(action+' interrupts without submission and can retry');
 }
 const x=await open();await x.page.waitForFunction(()=>!document.querySelector('[data-welcome-choice="yes"]').disabled);
 await x.page.evaluate(()=>{const b=document.querySelector('[data-welcome-choice="yes"]');b.onclick();b.onclick()});await x.finish();await x.page.locator('#completion.show').waitFor();
 await x.page.evaluate(()=>document.querySelector('video').dispatchEvent(new Event('ended')));assert.equal(x.posts(),1);assert.equal(await x.page.evaluate(()=>audit.micRequests),1);
 x.status('checked');await x.page.waitForFunction(()=>document.querySelector('#completion h2').textContent.includes('Tapos na'),null,{timeout:7000});await x.close('duplicate confirm/end and teacher approval');
 console.log('PASS: '+passed.length+' browser scenarios. '+passed.join('; ')+'.');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
