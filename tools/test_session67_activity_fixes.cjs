// Render actual Django templates. Provider, microphone and progress are synthetic;
// this test does not create accounts or touch the application database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os,sys,json
sys.path.insert(0,'pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.template.loader import render_to_string
from django.templatetags.static import static
from pabasa_app.prescribed_activity_catalog import prescribed_activity
from pabasa_app.views import _normalized_session7_missing_syllable_state, _normalized_session7_letter_ordering_state, _normalized_odd_word_state, _lesson16_gawain3_initial_state, _lesson16_gawain3_screen
fixtures=[]
names={
 'session-7-lesson-19-gawain-2':'session7_missing_syllable_page',
 'session-7-lesson-19-gawain-4':'session7_letter_ordering_page',
 'lesson-17-18-gawain-8':'prescribed_oral_odd_word_page',
 'lesson-17-18-gawain-9':'prescribed_oral_picture_word_write_page',
 'lesson-16-gawain-2':'prescribed_missing_syllable_page',
 'lesson-16-gawain-3':'lesson_16_gawain_3_page',
 'session-7-lesson-19-gawain-1':'prescribed_starting_syllable_page',
 'session-7-lesson-20-21-gawain-3':'session7_picture_word_connection_page',
 'lesson-17-18-gawain-5':'prescribed_picture_syllable_matching_page',
 'lesson-17-18-gawain-6':'prescribed_oral_missing_syllable_page',
 'session-6-lesson-16-gawain-4':'prescribed_picture_word_write_page',
}
for key,name in names.items():
 a=prescribed_activity(key)
 items=[{**i,'image_url':static(i.get('image_path','')),'read_aloud':i.get('read_aloud',i.get('word',''))} for i in a['items']]
 if key=='session-7-lesson-20-21-gawain-3':items=[item for item in items if not item.get('worked_example')]
 state={'phase':'oral_reading','current_item_index':0,'completed_oral_reads':[]}
 if key.endswith('19-gawain-2'):state=_normalized_session7_missing_syllable_state(a,state)
 if key.endswith('19-gawain-4'):state=_normalized_session7_letter_ordering_state(a,state)
 if key.endswith('gawain-8'):state=_normalized_odd_word_state(a,{})
 if key.endswith('gawain-9'):state={'phase':'written_answer','current_item_index':0,'completed_oral_reads':[0],'answers':[]}
 d={**a,'items':items,'groups':a['items'],'progress':{'state':state},'progress_url':'/progress/','completion_url':'/complete/','read_aloud_url':'/narrate/','transcribe_url':'/api/reading/transcribe/'}
 if key=='lesson-16-gawain-2':d.update(interaction='written',intro_enabled=True)
 if key=='lesson-16-gawain-3':
  state=_lesson16_gawain3_initial_state(a)
  state.update(phase='matching',oral_verified_count=5,oral_index=5)
  d['progress']['state']=state;d['screen']=_lesson16_gawain3_screen(a,state)
 fixtures.append({'key':key,'data':d,'html':render_to_string('pabasa_app/'+name+'.html',{'prescribed_activity_data':d})})
print(json.dumps(fixtures))
`], {cwd:root,encoding:'utf8',maxBuffer:4*1024*1024});
assert.equal(rendered.status,0,rendered.stderr);
const fixtures=JSON.parse(rendered.stdout);

(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});let checks=0;
 const naturalFile=path.join(app,'static/pabasa_app/prescribed/audio/SESSION_6/magaling_tama_ang_iyong_pagbasa_natural_20261014.mp3');
 const oldFile=path.join(app,'static/pabasa_app/prescribed/audio/SESSION_6/magaling_tama_ang_iyong_pagbasa.mp3');
 assert.notDeepEqual(fs.readFileSync(naturalFile),fs.readFileSync(oldFile));
 {
  const page=await browser.newPage();const asset='/static/pabasa_app/prescribed/audio/SESSION_6/magaling_tama_ang_iyong_pagbasa_natural_20261014.mp3';let served=0;
  const server=http.createServer((request,response)=>{if(request.url===asset){served++;response.writeHead(200,{'Content-Type':'audio/mpeg','Cache-Control':'public, max-age=3600'});response.end(fs.readFileSync(naturalFile));return}response.writeHead(200,{'Content-Type':'text/html'});response.end('<button id="play">Play</button><span id="result"></span><script>document.querySelector("#play").onclick=async()=>{const audio=new Audio("'+asset+'");try{await audio.play();await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=reject});document.querySelector("#result").textContent="ended"}catch(e){document.querySelector("#result").textContent="failed"}}</script>')});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{for(let replay=0;replay<2;replay++){await page.goto(`http://127.0.0.1:${server.address().port}/audio-check/`);await page.locator('#play').click();await page.locator('#result').getByText('ended').waitFor({timeout:10000});}assert.equal(served,1);checks++;}
  finally{await page.close();await new Promise(resolve=>server.close(resolve))}
 }
 async function open(key,state,viewport={width:1366,height:900},adminPreview=false){
  const fixture=fixtures.find(f=>f.key===key),page=await browser.newPage({viewport});
  let saved=structuredClone(state||fixture.data.progress.state),completed=false;
  const writes=[],errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
   window.audioMode='end';window.played=[];window.players=[];window.speechAccepted=true;window.speechFailure=false;
   window.Audio=class extends EventTarget{
    constructor(src){super();this.src=src;this.currentTime=0;this.ended=false;window.players.push(this);}
    play(){window.played.push(this.src);if(window.audioMode==='reject')return Promise.reject(Error('blocked'));
     if(window.audioMode==='hold')return Promise.resolve();
     setTimeout(()=>{const error=window.audioMode==='error';this.ended=!error;this.dispatchEvent(new Event(error?'error':'ended'));this[error?'onerror':'onended']?.();},15);return Promise.resolve();}
    pause(){this.dispatchEvent(new Event('pause'));this.onpause?.();}
   };
   window.MediaRecorder=class extends EventTarget{};
   Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}],getAudioTracks:()=>[]}),enumerateDevices:async()=>[]},configurable:true});
   window.BasahinButton={LABEL:'BASAHIN',setState:(button)=>{button.disabled=false;button.textContent='BASAHIN'}};
   window.Basahin={openMicrophone:async()=>navigator.mediaDevices.getUserMedia({audio:true}),capture:async()=>new Blob(['test'],{type:'audio/webm'}),bindActivity:(button,callback)=>button.onclick=callback,attachStreamResult(){},cancelAll(){},isCaptureError:()=>false};
  });
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/activity/'){
    let html=fixture.html.replace(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi,(tag,attrs)=>/src=.*(?:basahin|speech_debug)/.test(attrs)?'':tag);
    const data={...fixture.data,progress:{state:saved,answers:saved._answers||[],activity_completed:completed}};
    if(data.screen&&saved.choice_count)data.screen={...data.screen,picture_choices:data.screen.picture_choices.slice(0,saved.choice_count)};
    html=html.replace(/(<script[^>]*id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,head,tail)=>head+JSON.stringify(data)+tail);
    if(adminPreview)html=html.replace('</body>','<script>window.__PABASA_ADMIN_PRESCRIBED_KEY__='+JSON.stringify(key)+'</script><script src="/static/pabasa_app/js/admin_prescribed_preview.js"></script></body>');
    return route.fulfill({contentType:'text/html',body:html});
   }
   if(url.pathname==='/progress/'){
    const body=route.request().postDataJSON();writes.push(body);
    if(body.reset){saved={phase:'intro',current_item_index:0,completed_oral_reads:[],written_answers:[],stt_attempts:{},tts_plays:{},state_version:0};completed=false;}
    else if(body.state)saved=body.state;
    return route.fulfill({json:{success:true,progress:{state:saved,completed_items:0,total_items:5,activity_completed:completed}}});
   }
   if(url.pathname.includes('transcribe'))return route.fulfill({json:await page.evaluate(()=>speechFailure?{success:false,error:'Provider unavailable'}:{success:true,complete:speechAccepted})});
   if(url.pathname==='/narrate/')return route.fulfill({json:{success:true,audio_content:'AA==',tts_language:'fil-PH',voice_name:'fil-PH-Wavenet-A'}});
   if(url.pathname==='/complete/')return route.fulfill({json:{success:true}});
   if(url.pathname.startsWith('/static/')){
    const file=path.join(app,'static',decodeURIComponent(url.pathname.slice(8)));
    if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file});
    return route.fulfill({status:404,body:''});
   }
   return route.fulfill({body:''});
  });
  await page.goto('http://localhost/activity/');
  return {page,writes,errors,getState:()=>saved};
 }
 async function closeIntro(page){
  const modal=page.locator('[data-session7-start],[data-session6-start]');if(await modal.count())await modal.first().click();
 }
 for(const mode of ['end','error','reject','hold']){
  const {page,errors}=await open('session-7-lesson-19-gawain-4');await closeIntro(page);
  await page.evaluate(mode=>window.audioMode=mode,mode);await page.locator('#oral').click();
  await page.locator('[data-tile]').first().waitFor();
  await page.locator('[data-tile]').first().click();
  await page.waitForTimeout(100);
  assert.ok(await page.locator('.slot').first().textContent(),mode+' allows ordering');
  assert.deepEqual(errors,[]);checks++;await page.close();
 }
 {
  const {page,errors}=await open('session-7-lesson-19-gawain-4');await closeIntro(page);
  await page.evaluate(()=>audioMode='hold');await page.locator('#oral').click();await page.locator('[data-tile]').first().waitFor();
  await page.locator('[data-tile]').first().click();const selected=await page.locator('.slot').first().textContent();
  await page.evaluate(()=>{const player=players.findLast(player=>player.src.includes('tama_ang_pagbasa_ayusin_ang_letra'));player?.dispatchEvent(new Event('error'));player?.onerror?.()});
  assert.equal(await page.locator('.slot').first().textContent(),selected);
  await page.locator('[id$="-audio-settings-btn"]').click();await page.locator('[id$="-resume"]').click();
  assert.equal(await page.locator('.slot').first().textContent(),selected);
  await page.locator('[id$="-help-btn"]').click();await page.locator('[id$="-help-close"]').click();
  await page.locator('a.back').click();await page.locator('[id$="-leave-no"]').click();
  assert.equal(await page.locator('.slot').first().textContent(),selected);
  assert.deepEqual(errors,[]);checks++;await page.close();
 }
 {
  const {page,getState}=await open('session-7-lesson-19-gawain-4');await closeIntro(page);
  await page.evaluate(()=>speechAccepted=false);await page.locator('#oral').click();await page.waitForTimeout(100);
  assert.equal(getState().phase,'oral_reading');assert.equal(await page.locator('[data-tile]').count(),0);checks++;await page.close();
 }
 {
  const {page,getState}=await open('session-7-lesson-19-gawain-4');await closeIntro(page);
  await page.evaluate(()=>Basahin.openMicrophone=async()=>{throw new DOMException('Denied','NotAllowedError')});
  await page.locator('#oral').click();await page.waitForTimeout(100);
  assert.equal(getState().phase,'oral_reading');assert.ok(await page.locator('#oral').isEnabled());checks++;await page.close();
 }
 {
  const reading=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0});await closeIntro(reading.page);
  await reading.page.evaluate(()=>speechAccepted=false);
  for(let attempt=1;attempt<=3;attempt++){
   await reading.page.locator('#oral-action').click();
   await reading.page.waitForTimeout(100);
   assert.equal(reading.getState().stt_attempts['0'],attempt);
   assert.ok(await reading.page.evaluate(()=>played.some(src=>src.endsWith('/hindi_pa_tama_tts.mp3'))));
  }
  assert.match(await reading.page.locator('#oral-action').textContent(),/Pakinggan/);
  for(let listen=0;listen<3;listen++){await reading.page.locator('#oral-action').click();await reading.page.waitForTimeout(100)}
  assert.equal(reading.getState().stt_attempts['0'],0);
  await reading.page.locator('#oral-action').click();await reading.page.waitForTimeout(100);
  assert.equal(reading.getState().stt_attempts['0'],1);
  assert.ok(await reading.page.evaluate(()=>played.filter(src=>src.endsWith('/hindi_pa_tama_tts.mp3')).length>=4));
  assert.deepEqual(reading.errors,[]);checks++;await reading.page.close();
  const provider=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0});await closeIntro(provider.page);
  await provider.page.evaluate(()=>speechFailure=true);await provider.page.locator('#oral-action').click();await provider.page.waitForTimeout(100);
  assert.equal(provider.getState().stt_attempts?.['0']||0,0);assert.ok(await provider.page.locator('#oral-action').isEnabled());
  assert.match(await provider.page.locator('.oral-status').textContent(),/Provider unavailable/);
  assert.deepEqual(provider.errors,[]);checks++;await provider.page.close();
  const failedAudio=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0,stt_attempts:{'0':3},tts_plays:{'0':0}});await closeIntro(failedAudio.page);
  await failedAudio.page.evaluate(()=>audioMode='reject');await failedAudio.page.locator('#oral-action').click();await failedAudio.page.waitForTimeout(100);
  assert.equal(failedAudio.getState().tts_plays['0']||0,0);assert.ok(await failedAudio.page.locator('#oral-action').isEnabled());
  assert.deepEqual(failedAudio.errors,[]);checks++;await failedAudio.page.close();
  const gawain6=await open('lesson-17-18-gawain-6',{phase:'oral',reading_attempts:0});await closeIntro(gawain6.page);
  await gawain6.page.locator('#start').click();await gawain6.page.evaluate(()=>speechAccepted=false);
  await gawain6.page.locator('#oral').click();await gawain6.page.waitForTimeout(100);
  assert.equal(gawain6.getState().reading_attempts,1);assert.equal(gawain6.getState().phase,'oral');
  await gawain6.page.evaluate(()=>speechFailure=true);await gawain6.page.locator('#oral').click();await gawain6.page.waitForTimeout(100);
  assert.equal(gawain6.getState().reading_attempts,1);assert.ok(await gawain6.page.locator('#oral').isEnabled());
  assert.deepEqual(gawain6.errors,[]);checks++;await gawain6.page.close();
  const paused=await open('lesson-17-18-gawain-6',{phase:'oral',reading_attempts:0});await closeIntro(paused.page);
  await paused.page.locator('#start').click();
  await paused.page.evaluate(()=>{Basahin.capture=({signal})=>new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}))});
  await paused.page.locator('#oral').click();await paused.page.locator('[id$="-audio-settings-btn"]').click();
  await paused.page.locator('[id$="-resume"]').click();
  assert.equal(paused.getState().reading_attempts||0,0);assert.ok(await paused.page.locator('#oral').isEnabled());
  assert.deepEqual(paused.errors,[]);checks++;await paused.page.close();
 }
 for(const phase of ['oral_reading','written_answer','completion']){
  const state={phase,current_item_index:2,completed_oral_reads:[0,1,2],written_answers:['da','da'],stt_attempts:{'2':3},tts_plays:{'2':2},state_version:8};
  const {page,writes,getState}=await open('session-7-lesson-19-gawain-2',state);await closeIntro(page);
  await page.locator('[id$="-audio-settings-btn"]').click();await page.locator('[id$="-restart"]').click();await page.locator('[id$="-restart-yes"]').click();
  await page.waitForTimeout(150);assert.ok(writes.some(body=>body.reset===true));assert.equal(getState().current_item_index,0);assert.deepEqual(getState().stt_attempts,{});
  await page.reload();assert.match(await page.locator('[data-session7-start]').textContent(),/SIMULAN|Magsimula/);checks++;await page.close();
 }
 {
  const resumed=await open('lesson-17-18-gawain-8',{phase:'oral_reading',current_group_index:1,current_oral_word_index:1,oral_completed:{'1':[0]},completed_answers:{'0':1}});
  assert.equal(await resumed.page.locator('[data-session6-start]').textContent(),'IPAGPATULOY');await closeIntro(resumed.page);
  assert.equal(await resumed.page.locator('.read-target').textContent(),'palara');assert.equal(resumed.getState().current_group_index,1);checks++;await resumed.page.close();
  const word=await open('lesson-17-18-gawain-9',{phase:'written_answer',current_item_index:2,completed_oral_reads:[0,1,2],answers:['pana','pisara']});await closeIntro(word.page);
  await word.page.locator('#listen-word').click();await word.page.waitForTimeout(50);
  assert.ok(await word.page.evaluate(()=>played.some(src=>src.endsWith('/palaka_tts.mp3'))));assert.equal(word.writes.length,0);checks++;await word.page.close();
 }
 for(const viewport of [{width:1366,height:900},{width:390,height:844}]){
  const {page,errors}=await open('lesson-17-18-gawain-8',null,viewport);
  assert.equal(await page.locator('.lesson-start-backdrop').count(),1);await closeIntro(page);
  assert.ok(await page.locator('#start').isVisible());await page.locator('#start').click();await page.locator('#oral').waitFor();
  assert.equal(await page.locator('a.back').textContent(),'Bumalik sa Aking Gawain');
  const back=await page.locator('a.back').boundingBox(),help=await page.locator('[id$="-help-btn"]').boundingBox();assert.ok(back.x+back.width<=help.x);
  assert.deepEqual(errors,[]);checks++;await page.close();
  const written=await open('lesson-17-18-gawain-9',null,viewport);await closeIntro(written.page);
  await written.page.locator('#answer').fill('pana');const before=writesCopy(written.writes);
  await written.page.evaluate(()=>{audioMode='reject';played=[]});await written.page.locator('#listen-word').click();await written.page.waitForTimeout(70);
  assert.ok(await written.page.locator('#check').isEnabled());assert.match(await written.page.locator('#status').textContent(),/audio/);
  assert.equal(writesCopy(written.writes),before);assert.equal(await written.page.locator('#answer').inputValue(),'pana');
  assert.ok(await written.page.evaluate(()=>played.some(src=>src.endsWith('/pana_tts.mp3'))));checks++;await written.page.close();
  for(let count=1;count<=5;count++){
   const fixture=fixtures.find(f=>f.key==='lesson-16-gawain-3');
   const choices=await open(fixture.key,{...fixture.data.progress.state,choice_count:count},viewport);await closeIntro(choices.page);
   const boxes=await choices.page.locator('.l16g3-choice').evaluateAll(nodes=>nodes.map(node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width}}));
   assert.equal(boxes.length,count);
   for(const y of new Set(boxes.map(box=>box.y))){const row=boxes.filter(box=>box.y===y);assert.ok(Math.abs((row[0].x+row.at(-1).x+row.at(-1).width)/2-viewport.width/2)<3);}
   assert.deepEqual(choices.errors,[]);checks++;await choices.page.close();
  }
  for(let index=0;index<5;index++){
   const fixture=fixtures.find(f=>f.key==='lesson-16-gawain-2');
   const blank=await open(fixture.key,{phase:'written',_answers:fixture.data.items.slice(0,index).map(item=>item.answer)},viewport);await closeIntro(blank.page);
   assert.equal(await blank.page.locator('.blank').textContent(),'');assert.equal(await blank.page.locator('.blank').evaluate(node=>getComputedStyle(node).borderBottomStyle),'solid');
   assert.ok(await blank.page.locator('#answerInput').isEnabled());checks++;await blank.page.close();
  }
  const syllables=await open('session-7-lesson-19-gawain-1',null,viewport);await closeIntro(syllables.page);
  await syllables.page.locator('#oral,#oral-retry').first().click();await syllables.page.waitForTimeout(100);
  const choice=syllables.page.locator('.choice').first();await choice.waitFor();assert.ok(await choice.evaluate(node=>parseFloat(getComputedStyle(node).fontSize)>=23));checks++;await syllables.page.close();
  for(let index=0;index<4;index++){
   const image=await open('session-7-lesson-20-21-gawain-3',{phase:'oral_reading',current_item_index:index,completed_oral_reads:[],connected_answers:{}},viewport);await closeIntro(image.page);
   assert.equal(await image.page.locator('.s7g3-cue').filter({hasText:/Larawan \d+ sa/}).count(),0);
   const track=await image.page.locator('.s7g3-track').boundingBox(),picture=await image.page.locator('.s7g3-picture-frame').boundingBox();assert.ok(picture.y>=track.y+track.height+18);
   if(index===0)await image.page.screenshot({path:path.join(os.tmpdir(),`pabasa-session67-${viewport.width}.png`)});
   assert.deepEqual(image.errors,[]);checks++;await image.page.close();
  }
  const finalRead=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:4},viewport);await closeIntro(finalRead.page);
  await finalRead.page.waitForTimeout(150);await finalRead.page.locator('#oral-action').click();await finalRead.page.waitForTimeout(150);
  assert.ok(await finalRead.page.locator('.board').isVisible());assert.match(await finalRead.page.locator('#message').textContent(),/Magaling! Tama ang iyong pagbasa/);
   assert.ok(await finalRead.page.evaluate(()=>played.some(src=>src.endsWith('/magaling_tama_ang_iyong_pagbasa_natural_20261014.mp3'))));
  assert.deepEqual(finalRead.errors,[]);checks++;await finalRead.page.close();
  const reading=await open('session-6-lesson-16-gawain-4',{phase:'oral_reading',started:true,completed_oral_reads:[]},viewport);await closeIntro(reading.page);
  await reading.page.waitForTimeout(150);await reading.page.locator('#oral-action').click();await reading.page.waitForTimeout(150);
  assert.ok(await reading.page.locator('#answer').isVisible());assert.match(await reading.page.locator('#feedback').textContent(),/Magaling! Tama ang iyong pagbasa/);
  assert.ok(await reading.page.evaluate(()=>played.some(src=>src.endsWith('/magaling_tama_ang_iyong_pagbasa_natural_20261014.mp3'))));assert.deepEqual(reading.errors,[]);checks++;await reading.page.close();
  const gawain6=await open('lesson-17-18-gawain-6',{phase:'oral',reading_attempts:0},viewport);await closeIntro(gawain6.page);
  await gawain6.page.locator('#start').click();
  const basahin=gawain6.page.locator('#oral');await basahin.waitFor();
  assert.equal(await basahin.getAttribute('data-basahin-button'),'');
  assert.match(await basahin.textContent(),/Basahin/i);
  const bounds=await basahin.boundingBox();assert.ok(bounds&&bounds.x>=0&&bounds.x+bounds.width<=viewport.width&&bounds.y+bounds.height<=viewport.height);
  await basahin.click();await gawain6.page.locator('#answer').waitFor();
  assert.equal(gawain6.getState().phase,'written');assert.deepEqual(gawain6.errors,[]);checks++;await gawain6.page.close();
  const admin=await open('lesson-17-18-gawain-6',{phase:'oral'},viewport,true);await closeIntro(admin.page);
  await admin.page.locator('#start').click();const adminButton=admin.page.locator('#oral');await adminButton.waitFor();
  const adminBounds=await adminButton.boundingBox();assert.ok(adminBounds&&adminBounds.x>=0&&adminBounds.x+adminBounds.width<=viewport.width&&adminBounds.y+adminBounds.height<=viewport.height);
  assert.equal(await admin.page.evaluate(()=>__PABASA_ADMIN_PRESCRIBED_KEY__),'lesson-17-18-gawain-6');
  assert.deepEqual(admin.errors,[]);checks++;await admin.page.close();
 }
 {
  const page=await browser.newPage();await page.setContent('<a class="back">Original</a><script type="application/json" id="prescribed-activity-data">{"activity_key":"session-8-lesson-22-gawain-1"}</script>');
  await page.evaluate(()=>window.originalAudio=window.Audio);
  await page.addScriptTag({path:path.join(app,'static/pabasa_app/js/session67_ui.js')});
  assert.equal(await page.locator('.back').textContent(),'Original');assert.equal(await page.evaluate(()=>Audio===originalAudio),true);assert.equal(await page.locator('link').count(),0);checks++;await page.close();
 }
 function writesCopy(writes){return JSON.stringify(writes)}
 await browser.close();console.log(`${checks} Session 6/7 browser regressions passed (desktop and 390px).`);
})().catch(error=>{console.error(error);process.exit(1)});
