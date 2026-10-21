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
 if key=='session-7-lesson-20-21-gawain-2':
  for item in items:item['example_division']=item.get('answer','') if item.get('worked_example') else ''
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
 screens={}
 if key=='lesson-16-gawain-3':
  for phase in ['oral_reading','matching']:
   candidate=_lesson16_gawain3_initial_state(a);candidate.update(phase=phase,oral_verified_count=5 if phase=='matching' else 0)
   screens[phase]=_lesson16_gawain3_screen(a,candidate)
 fixtures.append({'key':key,'data':d,'screens':screens,'html':render_to_string('pabasa_app/'+name+'.html',{'prescribed_activity_data':d})})
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
   window.audioMode='end';window.holdFeedback=false;window.holdEvaluation=false;window.nativeFeedback=false;window.nativeFeedbackEnded=false;window.played=[];window.players=[];window.speechAccepted=true;window.speechFailure=false;
   const NativeAudio=window.Audio;
   window.Audio=class extends EventTarget{
    constructor(src){super();if(window.nativeFeedback&&src.endsWith('/hindi_pa_tama_tts.mp3')){const player=new NativeAudio(src);player.addEventListener('ended',()=>window.nativeFeedbackEnded=true);window.players.push(player);return player;}this.src=src;this.currentTime=0;this.ended=false;window.players.push(this);}
    play(){window.played.push(this.src);if(window.audioMode==='reject')return Promise.reject(Error('blocked'));
     if(window.audioMode==='hold'||(window.holdFeedback&&this.src.endsWith('/hindi_pa_tama_tts.mp3')))return Promise.resolve();
     setTimeout(()=>{const error=window.audioMode==='error';this.ended=!error;this.dispatchEvent(new Event(error?'error':'ended'));this[error?'onerror':'onended']?.();},15);return Promise.resolve();}
    pause(){this.dispatchEvent(new Event('pause'));this.onpause?.();}
   };
   window.MediaRecorder=class extends EventTarget{};
   Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}],getAudioTracks:()=>[]}),enumerateDevices:async()=>[]},configurable:true});
   
   window.Basahin={openMicrophone:async()=>navigator.mediaDevices.getUserMedia({audio:true}),capture:async()=>new Blob(['test'],{type:'audio/webm'}),bindActivity:(button,callback)=>window.BasahinButton.bindActivity(button,callback),attachStreamResult(){},cancelAll(){},isCaptureError:()=>false};
  });
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/activity/'){
    let html=fixture.html.replace(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi,(tag,attrs)=>/src=.*(?:basahin\.js|speech_debug)/.test(attrs)?'':tag);
    const data={...fixture.data,screen:fixture.screens?.[saved.phase]||fixture.data.screen,progress:{state:saved,answers:saved._answers||[],activity_completed:completed}};
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
   if(url.pathname.includes('transcribe')){await page.waitForFunction(()=>!holdEvaluation);return route.fulfill({json:await page.evaluate(()=>speechFailure?{success:false,error:'Provider unavailable'}:{success:true,complete:speechAccepted,transcript:document.querySelector('[data-expected-text]')?.getAttribute('data-expected-text')||''})});}
   if(url.pathname==='/narrate/')return route.fulfill({json:{success:true,audio_content:'AA==',tts_language:'fil-PH',voice_name:'fil-PH-Wavenet-A'}});
   if(url.pathname==='/complete/')return route.fulfill({json:{success:true}});
   if(url.pathname.startsWith('/static/')){
    let file=path.join(app,'static',decodeURIComponent(url.pathname.slice(8)));
    if(process.env.SESSION67_BASELINE){const candidate=path.join(os.tmpdir(),'pabasa-session67-request-baseline',path.basename(file));if(fs.existsSync(candidate))file=candidate;}
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

 const out=path.join(os.tmpdir(),'pabasa-session67-requested-layout');fs.mkdirSync(out,{recursive:true});
 const viewports=[{width:1366,height:900},{width:1366,height:768},{width:960,height:640},{width:768,height:600},{width:390,height:844}];
 const targets=[
  ['lesson-16-gawain-1',{phase:'oral'}],['lesson-16-gawain-1',{phase:'written'}],
  ['lesson-16-gawain-2',{phase:'oral'}],['lesson-16-gawain-2',{phase:'written'}],
  ['lesson-16-gawain-3',{phase:'oral_reading'}],['lesson-16-gawain-3',{phase:'matching',oral_verified_count:5,oral_index:5}],
  ['session-6-lesson-16-gawain-4',{phase:'oral_reading',started:true}],
  ['session-6-lesson-16-gawain-4',{phase:'written_answer',started:true,current_item_index:0,completed_oral_reads:[0]}],
  ['lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0}],
  ['lesson-17-18-gawain-6',{phase:'oral'}],['lesson-17-18-gawain-6',{phase:'written'}],
  ['session-7-lesson-19-gawain-2',{phase:'oral_reading'}],
  ['session-7-lesson-19-gawain-2',{phase:'written_answer',completed_oral_reads:[0]}],
  ['session-7-lesson-19-gawain-3',{phase:'oral_reading'}],
  ['session-7-lesson-19-gawain-3',{phase:'feedback',completed_correct_answers:['dagat']}],
  ['session-7-lesson-19-gawain-4',{phase:'intro'}],
  ['session-7-lesson-19-gawain-4',{phase:'oral_reading'}],
  ['session-7-lesson-20-21-gawain-2',{phase:'intro'}],
  ['session-7-lesson-20-21-gawain-2',{phase:'oral_reading'}]
 ];
 const report=[],layoutFailures=[];
 for(const viewport of viewports)for(const [key,state] of targets){
  if(process.env.SESSION67_GEOMETRY_ONLY&&viewport.width!==1366)continue;
  if(process.env.SESSION67_CASE_FILTER&&!key.includes(process.env.SESSION67_CASE_FILTER))continue;
  if(process.env.SESSION67_PHASE&&state.phase!==process.env.SESSION67_PHASE)continue;
  if(process.env.SESSION67_VIEWPORT&&process.env.SESSION67_VIEWPORT!==`${viewport.width}x${viewport.height}`)continue;
  const {page,errors}=await open(key,state,viewport);await closeIntro(page);
  if(await page.locator('#startActivity').isVisible())await page.locator('#startActivity').click();
  if(key==='lesson-17-18-gawain-6')await page.locator('#start').click();
  await page.waitForTimeout(100);
  const metrics=await page.evaluate(()=>{
   const card=document.querySelector('#app,#l16g3-app'),r=card.getBoundingClientRect();
   const nodes=[...card.querySelectorAll('img,button,input,h1,.eyebrow,.reading-word,.oral-word,.partial,.l16g3-word,.status,.example,.example-word')]
    .filter(n=>n.getBoundingClientRect().width&&getComputedStyle(n).visibility!=='hidden');
   const rect=n=>{const b=n.getBoundingClientRect();return {tag:n.tagName,text:n.textContent.trim().slice(0,55),x:b.x,y:b.y,w:b.width,h:b.height}};
   return {card:{x:r.x,y:r.y,w:r.width,h:r.height},scroll:card.scrollHeight>card.clientHeight+1,scrollHeight:card.scrollHeight,clientHeight:card.clientHeight,
    pageScroll:document.documentElement.scrollHeight>innerHeight+1,
    overflow:document.documentElement.scrollWidth>innerWidth+1||card.scrollWidth>card.clientWidth+1,
    clipped:nodes.filter(n=>{const b=n.getBoundingClientRect();return b.left<r.left-1||b.right>r.right+1||b.top<r.top-1||b.bottom>Math.min(innerHeight,r.bottom)+1}).map(rect),
    covered:nodes.filter(n=>{const b=n.getBoundingClientRect();return [...document.querySelectorAll('a.back,a.l16g3-back,.s6-controls,.prescribed-session-tools')].some(tool=>{const t=tool.getBoundingClientRect();return b.left<t.right&&b.right>t.left&&b.top<t.bottom&&b.bottom>t.top})}).map(rect)};
  });
  report.push({key,phase:state.phase,viewport,...metrics});
  if(process.env.SESSION67_DIAGNOSTIC)console.log(JSON.stringify({key,state,viewport,metrics,children:await page.locator('.card,.step-card,.step-card>*').evaluateAll(ns=>ns.map(n=>{const s=getComputedStyle(n),b=n.getBoundingClientRect();return {tag:n.tagName,cls:n.className,y:b.y,h:b.height,margin:s.margin,padding:s.padding,minHeight:s.minHeight,scrollTop:n.scrollTop,scrollHeight:n.scrollHeight}})),overflowing:await page.locator('.step-card *').evaluateAll(ns=>ns.filter(n=>n.getBoundingClientRect().bottom>document.querySelector('.step-card').getBoundingClientRect().bottom).map(n=>({tag:n.tagName,cls:n.className,bottom:n.getBoundingClientRect().bottom,text:n.textContent.slice(0,30)})))},null,2));
  try {
  assert.deepEqual(errors,[],key+' script errors');
  assert.equal(metrics.overflow,false,key+' horizontal overflow');
  if(!process.env.SESSION67_BASELINE){
   assert.deepEqual(metrics.clipped,[],key+' '+state.phase+' '+JSON.stringify(viewport)+' clipped');
   assert.deepEqual(metrics.covered,[],key+' '+state.phase+' '+JSON.stringify(viewport)+' covered by tools');
   assert.equal(metrics.scroll,false,key+' '+state.phase+' '+JSON.stringify(viewport)+' card scrolling');
   assert.equal(metrics.pageScroll,false,key+' page scrolling');
   if(key==='lesson-16-gawain-2')assert.equal(await page.getByText('May tatlong pagkakataon kang basahin ang salita.',{exact:true}).count(),0);
   if(key==='lesson-17-18-gawain-6'&&state.phase==='written'){
    assert.equal(await page.getByText('Punan ang nawawalang pantig.',{exact:true}).count(),0);
    assert.equal(await page.locator('label[for="answer"]').evaluate(n=>n.getBoundingClientRect().width),1);
    const a=await page.locator('.partial').boundingBox(),b=await page.locator('#answer').boundingBox();assert.ok(b.y-a.y-a.height>=18);
   }
   if(key.endsWith('19-gawain-3')&&state.phase==='feedback'){
    const centers=await page.locator('.picture,.correct-answer,.status.good,#next').evaluateAll(ns=>ns.map(n=>{const b=n.getBoundingClientRect();return b.x+b.width/2}));
    assert.equal(centers.length,4);assert.ok(Math.max(...centers)-Math.min(...centers)<2);
    assert.equal(await page.locator('.correct-answer').innerText(),'dagat');
   }
  }
  }catch(error){layoutFailures.push(error.message)}
  if(!process.env.SESSION67_GEOMETRY_ONLY)await page.screenshot({path:path.join(out,key+'-'+state.phase+'-'+viewport.width+'x'+viewport.height+'.png')});
  checks++;await page.close();
 }
 if(report.length&&!process.env.SESSION67_CASE_FILTER)fs.writeFileSync(path.join(out,process.env.SESSION67_BASELINE?'baseline.json':'metrics.json'),JSON.stringify(report,null,2));
 assert.deepEqual(layoutFailures,[]);
 if(process.env.SESSION67_BASELINE&&process.env.SESSION67_GEOMETRY_ONLY){
  const current=JSON.parse(fs.readFileSync(path.join(out,'metrics.json'),'utf8'));
  for(const row of report){const after=current.find(r=>r.key===row.key&&r.phase===row.phase&&r.viewport.width===row.viewport.width&&r.viewport.height===row.viewport.height);assert.ok(after,row.key+' current measurements');for(const axis of ['x','y','w','h'])assert.ok(Math.abs(after.card[axis]-row.card[axis])<.05,row.key+' desktop card '+axis+': '+after.card[axis]+' vs '+row.card[axis]);}
 }
 if(!process.env.SESSION67_BASELINE&&!process.env.SESSION67_LAYOUT_ONLY){
  // Hold the real retry audio's completion event: evaluation and feedback must
  // keep the real shared Basahin button locked until feedback finishes.
  const {page,getState,errors}=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0});await closeIntro(page);await page.waitForTimeout(100);
  await page.evaluate(()=>{speechAccepted=false;holdFeedback=true});
  for(let attempt=1;attempt<=3;attempt++){
   await page.evaluate(()=>holdEvaluation=true);
   await page.locator('#oral-action').click();
   await page.waitForFunction(()=>document.querySelector('#oral-action').dataset.basahinState==='processing');
   assert.ok(await page.locator('#oral-action').isDisabled());
   await page.evaluate(()=>holdEvaluation=false);
   await page.waitForFunction(()=>players.some(p=>p.src.endsWith('/hindi_pa_tama_tts.mp3')&&!p.ended));
   assert.ok(await page.locator('#oral-action').isDisabled());
   assert.equal(getState().stt_attempts['0'],attempt);
   await page.evaluate(()=>{const p=players.findLast(p=>p.src.endsWith('/hindi_pa_tama_tts.mp3')&&!p.ended);p.ended=true;p.dispatchEvent(new Event('ended'));p.onended?.()});
   await page.waitForFunction(()=>!document.querySelector('#oral-action').disabled);
   assert.match(await page.locator('#oral-action').innerText(),attempt<3?/^Basahin$/:/Pakinggan/);
   if(attempt<3)assert.equal(await page.locator('#oral-action').getAttribute('aria-busy'),'false');
  }
  assert.deepEqual(errors,[]);checks++;await page.close();
  const native=await open('lesson-17-18-gawain-5',{phase:'oral_reading',oral_index:0});await closeIntro(native.page);await native.page.waitForTimeout(100);
  await native.page.evaluate(()=>{speechAccepted=false;nativeFeedback=true});await native.page.locator('#oral-action').click();
  await native.page.waitForFunction(()=>players.some(p=>p instanceof HTMLAudioElement&&!p.paused));
  assert.ok(await native.page.locator('#oral-action').isDisabled());
  await native.page.waitForFunction(()=>nativeFeedbackEnded);
  await native.page.waitForFunction(()=>!document.querySelector('#oral-action').disabled);
  assert.equal(await native.page.locator('#oral-action').innerText(),'Basahin');assert.equal(native.getState().stt_attempts['0'],1);assert.deepEqual(native.errors,[]);
  checks++;await native.page.close();
  // All nine items retain their original reading order and displayed progress.
  const fixture=fixtures.find(f=>f.key==='session-7-lesson-20-21-gawain-2'),scored=fixture.data.items.filter(item=>!item.worked_example);assert.equal(scored.length,9);
  for(let index=0;index<9;index++){
   const {page,errors}=await open(fixture.key,{phase:'oral_reading',current_scored_index:index,submitted_syllable_divisions:scored.slice(0,index).map(item=>item.answer),completed_oral_reads:Array.from({length:index},(_,n)=>n)},viewports[3]);await closeIntro(page);await page.waitForTimeout(100);
   assert.equal(await page.locator('.reading-card .word').innerText(),scored[index].word);
   assert.match(await page.locator('.progress').innerText(),new RegExp(`${index}.*9`));assert.ok(await page.locator('#oral').isEnabled());
   assert.equal(await page.locator('#app').evaluate(n=>n.scrollHeight>n.clientHeight+1||n.scrollWidth>n.clientWidth+1),false,scored[index].word+' reading overflow');
   assert.deepEqual(errors,[]);checks++;await page.close();
  }
  for(const phase of ['oral_reading','written_answer']){
   const {page,errors}=await open('session-6-lesson-16-gawain-4',{phase,started:true,current_item_index:0,completed_oral_reads:phase==='written_answer'?[0]:[]},viewports[3]);await closeIntro(page);await page.waitForTimeout(100);
   if(phase==='oral_reading'){await page.evaluate(()=>speechAccepted=false);await page.locator('#oral-action').click();}
   else{await page.locator('#answer').fill('mali');await page.locator('#answer-form button').click();}
   await page.waitForTimeout(200);
   const result=await page.locator('#app').evaluate(n=>{const b=n.querySelector('button[id="oral-action"],#answer-form button').getBoundingClientRect();return {scroll:n.scrollHeight>n.clientHeight+1,bottom:b.bottom}});
   assert.equal(result.scroll,false,'Lesson 16 Gawain 4 '+phase+' incorrect feedback scrolling');assert.ok(result.bottom<=600);assert.deepEqual(errors,[]);checks++;await page.close();
  }
  const resized=await open('session-7-lesson-19-gawain-2',{phase:'oral_reading'});await closeIntro(resized.page);await resized.page.waitForTimeout(100);
  const original=JSON.stringify(resized.getState());
  for(const viewport of [viewports[3],viewports[4],viewports[1],viewports[0]]){
   await resized.page.setViewportSize(viewport);await resized.page.waitForTimeout(100);
   assert.equal(await resized.page.locator('#app').evaluate(n=>n.scrollHeight>n.clientHeight+1),false,'Lesson 19 Gawain 2 resize scrolling');
   assert.equal(await resized.page.locator('.step-card .word').innerText(),'daan');assert.equal(JSON.stringify(resized.getState()),original);
  }
  assert.deepEqual(resized.errors,[]);checks++;await resized.page.close();
 }
 if(report.length&&!process.env.SESSION67_CASE_FILTER)fs.writeFileSync(path.join(out,process.env.SESSION67_BASELINE?'baseline.json':'metrics.json'),JSON.stringify(report,null,2));
 await browser.close();console.log(checks+' requested layout/retry checks passed. Screenshots: '+out);
})().catch(error=>{console.error(error);process.exit(1)});


