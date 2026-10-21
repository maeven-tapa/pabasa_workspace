// Render actual Django templates. Provider, microphone and progress are synthetic;
// this test does not create accounts or touch the application database.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
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
 'lesson-16-gawain-1':'prescribed_missing_syllable_page',
 'session-7-lesson-19-gawain-3':'session7_circle_word_page',
 'session-7-lesson-20-21-gawain-1':'prescribed_cluster_syllable_page',
 'session-7-lesson-20-21-gawain-2':'prescribed_cluster_syllabification_page',
 'session-7-lesson-20-21-gawain-4':'session7_cluster_word_circle_page',
 'lesson-17-18-gawain-7':'prescribed_oral_picture_word_matching_page',
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
 if key=='session-7-lesson-20-21-gawain-2':d['local_audio']={'intro':'/test-intro.mp3','prompts':{},'words':{},'feedback':{}}
 if key in ('lesson-16-gawain-1','lesson-16-gawain-2'):d.update(intro_enabled=True)
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
 async function open(key,state,viewport={width:1366,height:900},adminPreview=false){
  const fixture=fixtures.find(f=>f.key===key),page=await browser.newPage({viewport});
  let saved=structuredClone(state||fixture.data.progress.state),completed=false;
  const writes=[],errors=[];
  page.on('dialog',async dialog=>{errors.push('Native dialog: '+dialog.type());await dialog.dismiss()});
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
   const clone=Response.prototype.clone;Response.prototype.clone=function(){const copy=clone.call(this),json=copy.json.bind(copy);copy.json=async()=>{await new Promise(r=>setTimeout(r,80));return json()};return copy};
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
   window.BasahinButton={LABEL:'BASAHIN',decorate(){},setState:(button)=>{button.disabled=false;button.textContent='BASAHIN'}};
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
    if(body.reset||body.action==='restart'){saved={phase:'intro',current_item_index:0,completed_oral_reads:[],written_answers:[],stt_attempts:{},tts_plays:{},state_version:0};completed=false;}
    else if(body.state)saved=body.state;
    return route.fulfill({json:{success:true,progress:{state:saved,completed_items:0,total_items:5,activity_completed:completed}}});
   }
   if(url.pathname.includes('transcribe'))return route.fulfill({json:await page.evaluate(()=>speechFailure?{success:false,error:'Provider unavailable'}:{success:true,complete:speechAccepted,transcript:document.querySelector('[data-expected-text]')?.getAttribute('data-expected-text')||''})});
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


 const out=path.join(os.tmpdir(),'pabasa-session67-layout');fs.mkdirSync(out,{recursive:true});
 const targets=[
 ['lesson-16-gawain-1',{phase:'oral'}],['lesson-16-gawain-2',{phase:'oral'}],
 ['session-6-lesson-16-gawain-4',{phase:'oral_reading',started:true}],
 ['session-7-lesson-19-gawain-1',{phase:'oral_reading',correct_answers:[],completed_oral_reads:[]}],
 ['session-7-lesson-19-gawain-2',{phase:'oral_reading'}],
 ['session-7-lesson-19-gawain-3',{phase:'oral_reading'}],
 ['session-7-lesson-19-gawain-4',{phase:'intro'}],
 ['session-7-lesson-19-gawain-4',{phase:'oral_reading'}]
 ];
 for(const viewport of [{width:1366,height:900},{width:1366,height:768},{width:390,height:844}]){
  for(const [key,state] of targets){
   const {page,errors}=await open(key,state,viewport);await closeIntro(page);
   if(await page.locator('#startActivity').isVisible())await page.locator('#startActivity').click();
   await page.waitForTimeout(150);
   const metrics=await page.evaluate(()=>{
    const card=document.querySelector('.card'),r=card.getBoundingClientRect();
    const visible=n=>{const b=n.getBoundingClientRect();return b.width>0&&b.height>0};
    const nodes=[...card.children].filter(visible),rects=nodes.map(n=>n.getBoundingClientRect());
    const top=Math.min(...rects.map(b=>b.top)),bottom=Math.max(...rects.map(b=>b.bottom));
    return {overflow:card.scrollWidth>card.clientWidth+1,offsets:rects.map(b=>b.x+b.width/2-r.x-r.width/2),
     outside:rects.some(b=>b.left<r.left||b.right>r.right),top,bottom,cardBottom:r.bottom,
     word:card.querySelector('.reading-word')?.textContent,
     wordSize:parseFloat(getComputedStyle(card.querySelector('.reading-word,.word')||card).fontSize)};
   });
   assert.equal(metrics.overflow,false,key+' horizontal overflow');assert.equal(metrics.outside,false,key+' outside card');
   assert.ok(metrics.offsets.every(offset=>Math.abs(offset)<2),key+' content centre '+JSON.stringify(metrics));
   if(viewport.width>800)assert.ok(metrics.bottom<=metrics.cardBottom+1,key+' desktop clipping');
   if(key==='lesson-16-gawain-1'||key==='lesson-16-gawain-2'){
    assert.equal(metrics.word,'gumamela');assert.ok(metrics.wordSize>=28);
    assert.equal(await page.locator('.reading-reminder').getByText(/Basahin nang malakas/).count(),0);
   }
   assert.deepEqual(errors,[],key);
   await page.screenshot({path:path.join(out,key+'-'+state.phase+'-'+viewport.width+'x'+viewport.height+'.png')});
   checks++;await page.close();
  }
 }

 // Exercise the unchanged reading handlers with synthetic capture and provider
 // responses: provider failure must stay on reading; success advances one step.
 for(const [key,state,button,next] of [
 ['lesson-16-gawain-1',{phase:'oral'},'#oralAction','.choice'],
 ['lesson-16-gawain-2',{phase:'oral'},'#oralAction','#answerInput'],
 ['session-6-lesson-16-gawain-4',{phase:'oral_reading',started:true},'#oral-action','#answer'],
 ['session-7-lesson-19-gawain-3',{phase:'oral_reading'},'#oral','.word.active'],
 ['session-7-lesson-19-gawain-4',{phase:'oral_reading'},'#oral','[data-tile]']
 ]){
  const {page,errors,getState}=await open(key,state);await closeIntro(page);
  if(await page.locator('#startActivity').isVisible())await page.locator('#startActivity').click();
  await page.waitForTimeout(150);
  await page.evaluate(()=>speechFailure=true);await page.locator(button).click();await page.waitForTimeout(250);
  assert.equal(getState().phase,state.phase,key+' provider failure must not advance');
  await page.evaluate(()=>speechFailure=false);await page.locator(button).click();await page.locator(next).first().waitFor();
  if(key.endsWith('19-gawain-3'))assert.equal(getState().orally_completed_words['0'].length,1);
  else assert.notEqual(getState().phase,state.phase,key+' successful read advances');
  assert.deepEqual(errors,[],key+' speech flow');checks++;await page.close();
 }
 // Confirmed navigation must drain the response-clone tracker (artificially
 // delayed above) before unloading, without disabling the unsaved-work guard.
 for(const key of fixtures.map(f=>f.key).filter(k=>k.startsWith('session-7-'))){
  for(const action of ['leave','restart']){
   const {page,errors,writes,getState}=await open(key,{phase:'intro'});await closeIntro(page);
   if(action==='leave'){
    await page.locator('a.back').click();await page.locator('[id$="-leave-yes"]').click();
    await page.waitForURL('**/dashboard/assessment/');
   }else{
    await page.locator('[id$="-audio-settings-btn"]').click();await page.locator('[id$="-restart"]').click();
    await page.locator('[id$="-restart-yes"]').click();await page.waitForTimeout(400);
    assert.ok(writes.some(body=>body.reset===true||body.action==='restart'),key+' sends reset');assert.equal(getState().phase,'intro');
   }
   assert.deepEqual(errors,[],key+' '+action);checks++;await page.close();
  }
 }

 for(const key of fixtures.map(f=>f.key).filter(k=>k.startsWith('session-7-'))){
  const {page,errors,writes}=await open(key,{phase:'oral_reading',current_item_index:1,stt_attempts:{'0':1}});
  await page.locator('[data-session7-later]').click();await page.waitForTimeout(400);
  assert.ok(writes.some(body=>body.reset===true),key+' intro restart');assert.deepEqual(errors,[],key+' intro restart');
  checks++;await page.close();
 }
 {
  const {page,errors}=await open('session-7-lesson-19-gawain-1',{phase:'intro'});await closeIntro(page);
  await page.route('**/progress/',route=>route.fulfill({status:500,json:{success:false,error:'Save unavailable'}}));
  await page.locator('a.back').click();await page.locator('[id$="-leave-yes"]').click();
  await page.locator('[id$="-leave-error"]').waitFor();assert.ok(page.url().endsWith('/activity/'));
  assert.ok(await page.locator('[id$="-leave-yes"]').isEnabled());assert.deepEqual(errors,[]);
  checks++;await page.close();
 }
 await browser.close();console.log(checks+' Session 6/7 layout and navigation checks passed. Screenshots: '+out);
})().catch(error=>{console.error(error);process.exit(1)});
