// Actual Lesson 26 markup and backend recognition, with isolated local fixtures.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import json, os, sys
sys.path.insert(0,'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django
django.setup()
from django.template.loader import render_to_string
from pabasa_app.prescribed_activity_catalog import prescribed_activity
from pabasa_app.lesson26_reading import analyze_sentence_continuation
activity=prescribed_activity('lesson-26-gawain-2')
clips=[]
for i,item in enumerate(activity['items']):
    text=''.join(part+(' '+item['answers'][j]+' ' if j<len(item['answers']) else '') for j,part in enumerate(item['parts']))
    words=text.split()
    prefix=' '.join(words[:2])
    partial=analyze_sentence_continuation(text,0,prefix,'en-PH')
    clips.append({'index':i,'placements':dict((str(j),w) for j,w in enumerate(item['answers'])),
       'partial':partial,'wrong':analyze_sentence_continuation(text,partial['current_syllable_index'],prefix+' banana','en-PH'),
       'rest':analyze_sentence_continuation(text,partial['current_syllable_index'],' '.join(words[2:]),'en-PH'),
       'full':analyze_sentence_continuation(text,0,text,'en-PH')})
data={'activity_key':'lesson-26-gawain-2','choices':activity['choices'],
      'items':[{'id':item['id'],'parts':item['parts'],'blank_count':len(item['answers'])} for item in activity['items']],
      'progress':{'state':{}},'progress_url':'/progress/','transcribe_url':'/transcribe/','completion_url':'/complete/'}
html=render_to_string('pabasa_app/prescribed_fill_blank_lesson26_activity2_page.html',{'prescribed_activity_data':data})
print(json.dumps({'html':html,'data':data,'clips':clips}))
`], {cwd:root,encoding:'utf8',maxBuffer:2*1024*1024});
assert.equal(rendered.status,0,rendered.stderr);
const fixture=JSON.parse(rendered.stdout);
const scripts=new Set(['basahin_button.js','prescribed_controls.js','prescribed_lesson26_31_ui.js',
 'prescribed_fill_blank_lesson26_activity2.js','prescribed_leave_confirmation.js']);
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 async function open(clip,viewport={width:1366,height:768},realCapture=false){
  const page=await browser.newPage({viewport});
  const errors=[],saves=[],requests=[];
  let state={phase:'sentence',current_item:clip.index,completed_items:clip.index,choice_index:4,
   sentence_read:true,placements:clip.placements,sentence_attempts:0,sentence_syllable_index:0,sentence_word_index:0};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://localhost:9876/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/activity/'){
    const data={...fixture.data,progress:{state}};
    let html=fixture.html.replace(/(<script id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,a,b)=>a+JSON.stringify(data)+b);
    html=html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,(tag,attrs)=>{
     if(/application\/json/.test(attrs))return tag;
     const src=attrs.match(/src="([^"]+)"/)?.[1];
     const name=src&&path.posix.basename(src.split('?')[0]);
     return src&&(scripts.has(name)||realCapture&&name==='basahin.js')?tag:'';
    });
    return route.fulfill({contentType:'text/html',body:html});
   }
   if(url.pathname==='/progress/'){
    const payload=route.request().postDataJSON();saves.push(payload);
    if(await page.evaluate(()=>window.progressFailures>0)){
     await page.evaluate(()=>window.progressFailures--);
     return route.fulfill({status:503,json:{success:false,error:'Temporary save failure'}});
    }
    if(payload.action==='sentence_progress'){
     state.sentence_syllable_index=payload.current_syllable_index;
     state.sentence_word_index=clip.rest.word_syllable_ranges.filter(r=>r[1]<=payload.current_syllable_index).length;
    }else if(payload.action==='sentence_reading'){
     if(payload.success){state.completed_items++;state.current_item++;state.placements={};state.sentence_read=false;
      state.sentence_syllable_index=state.sentence_word_index=state.sentence_attempts=0;
      if(state.completed_items===4)state.phase='complete';
     }else state.sentence_attempts++;
    }else if(payload.action==='sentence_read')state.sentence_read=true;
    return route.fulfill({json:{success:true,progress:{state}}});
   }
   if(url.pathname==='/complete/')return route.fulfill({json:{success:true}});
   if(url.pathname==='/transcribe/'){
    requests.push(route.request().postDataBuffer().toString());
    return route.fulfill({json:{success:true,...await page.evaluate(()=>window.clips.shift())}});
   }
   if(url.pathname.startsWith('/static/pabasa_app/')){
    const file=path.join(app,decodeURIComponent(url.pathname.slice(1)));
    if(fs.existsSync(file))return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.mp3')?'audio/mpeg':'application/octet-stream'});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.addInitScript(real=>{
   window.clips=[];window.playedAudio=[];window.readingFields=[];window.readingOptions=[];
   window.Audio=class extends EventTarget{
    constructor(url){super();this.url=decodeURIComponent(url);}
    play(){window.playedAudio.push(this.url);queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();}
    pause(){this.dispatchEvent(new Event('pause'));}
   };
   navigator.mediaDevices.enumerateDevices=async()=>[];
   if(real){
    window.testStreams=[];
    navigator.mediaDevices.getUserMedia=async()=>{
     const context=new AudioContext(),tone=context.createOscillator(),gain=context.createGain(),output=context.createMediaStreamDestination();
     gain.gain.value=0;tone.connect(gain).connect(output);tone.start();
     gain.gain.setValueAtTime(0.2,context.currentTime+1.5);gain.gain.setValueAtTime(0,context.currentTime+2.7);
     window.testStreams.push(output.stream);return output.stream;
    };
   }else{
    window.MediaRecorder=function(){};const readers=new Set();
    window.Basahin={bindActivity(button,action){window.BasahinButton.bindActivity(button,action);},cancelAll(){readers.forEach(r=>r.stop());},create(options){
     window.readingOptions.push({silenceMs:options.silenceMs});let wake;
     const reader={async start(){
      window.readingFields.push({...options.getFields()});window.lateResult=options.onResult;
      if(!window.clips.length){await new Promise(resolve=>{wake=resolve;});return;}
      const clip=window.clips.shift();
      try{if(clip.error)throw new Error(clip.error);await options.onResult(clip);}catch(error){options.onError(error);}
     },stop(){wake?.();},destroy(){this.stop();readers.delete(reader);}};
     readers.add(reader);return reader;
    }};
   }
  },realCapture);
  await page.goto('http://localhost:9876/activity/');
  await page.evaluate(()=>{document.getElementById('lesson26-start').hidden=true;document.getElementById('lesson26-stage').classList.remove('is-waiting');});
  return{page,errors,saves,requests,getState:()=>state};
 }
 async function speak(page,clip){await page.evaluate(clip=>{window.clips=[clip];},clip);await page.locator('#read-sentence').click();}
 try{
  for(const viewport of [{width:1366,height:768},{width:390,height:844}])for(const clip of fixture.clips){
   const{page,errors,saves}=await open(clip,viewport);
   assert.equal(await page.locator('.lesson26-reading-word').count(),clip.rest.word_syllable_ranges.length);
   assert.deepEqual(await page.locator('.lesson26-unread .lesson26-reading-word').allTextContents(), await page.locator('.lesson26-reading-word').allTextContents());
   await speak(page,clip.partial);
   await page.waitForFunction(()=>window.playedAudio.some(url=>url.includes('read the rest of the sentence')));
   assert.equal(saves.filter(p=>p.action==='sentence_reading').length,0);
   assert.equal((await page.evaluate(()=>window.readingOptions))[0].silenceMs,3000);
   assert.deepEqual(await page.locator('.is-read').allTextContents(),clip.partial.words.slice(0,2));
   assert.equal(await page.locator('[aria-current="true"]').getAttribute('data-word-index'),'2');
   assert.equal(await page.locator('.lesson26-unread .is-read').count(),0);
   assert.equal(await page.locator('.lesson26-unread .lesson26-reading-word').count(),clip.rest.word_syllable_ranges.length-2);
   await page.reload();
   await page.evaluate(()=>{document.getElementById('lesson26-start').hidden=true;document.getElementById('lesson26-stage').classList.remove('is-waiting');});
   assert.deepEqual(await page.locator('.is-read').allTextContents(),clip.partial.words.slice(0,2));
   await speak(page,clip.wrong);
   await page.waitForFunction(()=>window.playedAudio.some(url=>url.includes('try that again')));
   assert.deepEqual(await page.locator('.is-read').allTextContents(),clip.partial.words.slice(0,2));
   assert.equal(saves.filter(p=>p.action==='sentence_reading').at(-1).success,false);
   const next=page.locator('[aria-current="true"]');
   assert.equal(await next.getAttribute('data-word-index'),'2');
   if(clip.index===0)await page.screenshot({path:path.join(process.env.TEMP,`lesson26-highlight-${viewport.width}.png`)});
   await speak(page,clip.rest);
   await page.waitForFunction(()=>document.querySelector('.pabasa-completion-card')||!document.getElementById('read-sentence'));
   assert.equal(saves.filter(p=>p.action==='sentence_reading').at(-1).success,true);
   const fields=await page.evaluate(()=>window.readingFields);
   assert.equal(fields.at(-1).current_syllable_index,clip.partial.current_syllable_index);
   assert.deepEqual(errors,[]);await page.close();
  }
  const clip=fixture.clips[0];
  {
   const{page,saves,errors,getState}=await open(clip);
   await page.evaluate(()=>window.progressFailures=1);
   await speak(page,clip.full);
   await page.waitForFunction(()=>window.playedAudio.length>0);
   assert.equal(getState().current_item,0,'A failed save must not complete the item');
   await speak(page,clip.full);
   await page.waitForFunction(()=>!document.getElementById('read-sentence'));
   await page.evaluate(()=>window.__prescribedLeaveAdapters['prescribed-l26a2'].saveCurrentProgress());
   // Completing this item can automatically narrate the next sentence and
   // acknowledge its playback before Leave saves the current state.
   assert.deepEqual(saves.filter(p=>p.action!=='sentence_read').map(p=>p.action),['sentence_progress','sentence_progress','sentence_reading','state_sync']);
   assert.ok(saves.filter(p=>p.action==='sentence_read').length<=1);
   assert.equal(getState().current_item,1,'Successful rereading must clear the failed previous-item save');
   assert.deepEqual(errors,[]);await page.close();
  }
  {
   const{page,saves,errors,getState}=await open(clip);
   await page.evaluate(()=>window.progressFailures=1);
   await speak(page,clip.partial);
   await page.waitForFunction(()=>window.playedAudio.length>0);
   assert.equal(getState().sentence_syllable_index,0);
   assert.equal(await page.locator('.is-read').count(),2);
   await page.evaluate(()=>window.progressFailures=1);
   const failure=await page.evaluate(async()=>{
    try{await window.__prescribedLeaveAdapters['prescribed-l26a2'].saveCurrentProgress();return '';}
    catch(error){return error.message;}
   });
   assert.equal(failure,'Temporary save failure','Leave must remain blocked while saving still fails');
   assert.equal(saves.filter(p=>p.action==='state_sync').length,0);
   await page.evaluate(()=>window.__prescribedLeaveAdapters['prescribed-l26a2'].saveCurrentProgress());
   assert.deepEqual(saves.map(p=>p.action),['sentence_progress','sentence_progress','sentence_progress','state_sync']);
   assert.equal(getState().sentence_syllable_index,clip.partial.current_syllable_index);
   await page.reload();
   await page.evaluate(()=>{document.getElementById('lesson26-start').hidden=true;document.getElementById('lesson26-stage').classList.remove('is-waiting');});
   assert.equal(await page.locator('.is-read').count(),2,'Recovered saves retain the highlighted prefix on reload');
   await speak(page,clip.rest);
   await page.waitForFunction(()=>!document.getElementById('read-sentence'));
   assert.deepEqual(errors,[]);await page.close();
  }
  {
   const{page,errors,saves}=await open(clip);
   await page.evaluate(()=>{
    window.Audio=class extends EventTarget{
     constructor(url){super();this.url=decodeURIComponent(url);}
     play(){window.playedAudio.push(this.url);return Promise.resolve();}
     pause(){this.dispatchEvent(new Event('pause'));}
    };
   });
   await speak(page,clip.partial);
   await page.waitForFunction(()=>window.playedAudio.some(url=>url.includes('read the rest of the sentence')));
   assert.equal(await page.locator('#read-sentence').isDisabled(),true);
   await page.evaluate(()=>{window.PrescribedLesson26Activity.pause();window.PrescribedLesson26Activity.resume();});
   await page.waitForFunction(()=>!document.getElementById('read-sentence').disabled);
   assert.equal(await page.locator('.is-read').count(),2);
   await page.evaluate(()=>window.Audio.prototype.play=function(){window.playedAudio.push(this.url);queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();});
   await speak(page,clip.rest);
   await page.waitForFunction(()=>!document.getElementById('read-sentence'));
   assert.equal(saves.filter(p=>p.action==='sentence_reading').at(-1).success,true);
   assert.deepEqual(errors,[]);await page.close();
  }
  {
   const{page,errors,saves,getState}=await open(clip);
   await page.evaluate(()=>{
    // Start the listen phase with unfilled blanks; pausing its audio must
    // neither mark it heard nor unlock word placement prematurely.
    window.Audio=class extends EventTarget{
     constructor(url){super();this.url=decodeURIComponent(url);}
     play(){window.playedAudio.push(this.url);return Promise.resolve();}
     pause(){this.dispatchEvent(new Event('pause'));}
    };
   });
   Object.assign(getState(),{sentence_read:false,placements:{}});
   await page.reload();
   await page.evaluate(()=>{
    document.getElementById('lesson26-start').hidden=true;document.getElementById('lesson26-stage').classList.remove('is-waiting');
    window.Audio=class extends EventTarget{
     constructor(url){super();this.url=decodeURIComponent(url);}
     play(){window.playedAudio.push(this.url);return Promise.resolve();}
     pause(){this.dispatchEvent(new Event('pause'));}
    };
   });
   await page.locator('#listen').click();
   await page.waitForFunction(()=>window.playedAudio.length>0);
   await page.evaluate(()=>{window.PrescribedLesson26Activity.pause();window.PrescribedLesson26Activity.resume();});
   await page.waitForFunction(()=>!document.getElementById('listen').disabled);
   assert.equal(saves.length,0,'Interrupted listening cannot save sentence_read');
   assert.equal(getState().sentence_read,false);
   await page.evaluate(()=>window.Audio.prototype.play=function(){window.playedAudio.push(this.url);queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();});
   await page.locator('#listen').click();
   await page.waitForFunction(()=>document.querySelector('[data-blank]'));
   await page.waitForFunction(()=>window.playedAudio.length===2);
   assert.equal(saves.at(-1).action,'sentence_read');
   assert.equal(getState().sentence_read,true);
   assert.deepEqual(errors,[]);await page.close();
  }
  for(const result of [{error:'Provider unavailable'},{transcript:'',complete:false}]){
   const{page,errors,saves}=await open(clip);await speak(page,result);
   await page.waitForFunction(()=>window.playedAudio.length===1);
   assert.equal(await page.locator('.is-read').count(),0);assert.equal(saves.length,0);assert.deepEqual(errors,[]);await page.close();
  }
  {
   const{page,saves,errors}=await open(clip);
   await page.locator('#read-sentence').click();
   await page.evaluate(()=>window.PrescribedLesson26Activity.pause());
   await page.evaluate(clip=>window.lateResult(clip),clip.partial);
   assert.equal(saves.length,0);assert.equal(await page.locator('.is-read').count(),0);
   assert.deepEqual(errors,[]);await page.close();
  }
  {
   const{page,requests,saves,errors}=await open(clip,undefined,true);
   await speak(page,clip.partial);
   await page.waitForFunction(()=>window.playedAudio.some(url=>url.includes('read the rest of the sentence')),null,{timeout:15000});
   assert.equal(requests.length,1);assert.equal(saves.filter(p=>p.action==='sentence_reading').length,0);
   assert.ok(await page.evaluate(()=>window.testStreams[0].getTracks().every(t=>t.readyState==='ended')));
   await speak(page,clip.rest);
   await page.waitForFunction(()=>!document.getElementById('read-sentence'),null,{timeout:15000});
   assert.equal(requests.length,2);
   assert.match(requests[1],new RegExp('name="current_syllable_index"\\r\\n\\r\\n'+clip.partial.current_syllable_index));
   assert.ok(requests.every(r=>r.includes('lesson-26-gawain-2')&&r.includes('English')));
   assert.deepEqual(errors,[]);await page.close();
  }
  {
   const page=await browser.newPage();
   const asset=path.join(app,"static/pabasa_app/prescribed/audio/SESSION_10/LESSON_26/GAWAIN_2/Great! now let's read the rest of the sentence..mp3");
   await page.route('http://localhost:9876/audio',route=>route.fulfill({body:fs.readFileSync(asset),contentType:'audio/mpeg'}));
   await page.route('http://localhost:9876/',route=>route.fulfill({contentType:'text/html',body:'<button id="play">Play</button>'}));
   await page.goto('http://localhost:9876/');
   await page.evaluate(()=>document.getElementById('play').onclick=()=>{const a=new Audio('/audio');window.sound=a;a.onended=()=>window.audioEnded=true;a.play();});
   await page.locator('#play').click();await page.waitForFunction(()=>window.audioEnded,null,{timeout:15000});
   assert.ok(await page.evaluate(()=>window.sound.duration>0));await page.close();
  }
  console.log('PASS: all four sentences at desktop/mobile; prefix highlights, retry, continuation, reload, failed-save recovery, audio pause/resume, interrupted listen, provider errors, actual recording/mic release and supplied audio playback.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
