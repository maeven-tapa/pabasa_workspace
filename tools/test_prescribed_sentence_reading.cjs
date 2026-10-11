// Isolated browser fixtures: actual templates, scripts, catalog and matcher.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import json,os,sys
sys.path.insert(0,'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.template.loader import render_to_string
from django.templatetags.static import static
from pabasa_app.prescribed_activity_catalog import prescribed_activity
from pabasa_app.prescribed_sentence_reading import continue_sentence
from pabasa_app.views import _sentence_continuation_aliases
names={'lesson-29-gawain-1':'oral_sentence_blank_lesson29_activity1','lesson-30-gawain-2':'story_time_lesson30_activity2','lesson-31-gawain-2':'drag_blank_lesson31_activity2','lesson-31-gawain-3':'fix_sentence_lesson31_activity3'}
fixtures=[]
for key,name in names.items():
 a=prescribed_activity(key);story=key=='lesson-30-gawain-2'
 data={**a,'progress':{'state':{}},'progress_url':'/progress/','transcribe_url':'/transcribe/','completion_url':'/complete/','read_aloud_url':'/narrate/'}
 if not story:data['items']=[{**item,'image_url':static(item['image_path']) if item.get('image_path') else '','word_length':len(item.get('answer',''))} for item in a['items']]
 cases=[]
 for i,item in enumerate(a['lines'] if story else a['items']):
  text=item if story else (item['before']+item['answer']+item['after'] if key=='lesson-29-gawain-1' else item['sentence'])
  state={'phase':'reading' if story else 'sentence_reading' if key=='lesson-29-gawain-1' else 'reading_sentence','current_line' if story else 'current_item':i,'completed_items':i}
  if key=='lesson-31-gawain-2':state.update(placed_word=item['answer'],choice_index=len(a['word_choices']))
  if key=='lesson-31-gawain-3':state.update(placements=item['ordered_words'],word_index=len(item['jumbled_words']))
  clips=[];old=state
  for heard in (' '.join(text.split()[:2]),'banana '+' '.join(text.split()[2:]),' '.join(text.split()[2:])):
   old,reading,prompt=continue_sentence(a,key,old,{'item_index':i,'heard':heard},_sentence_continuation_aliases(key))
   clips.append({'heard':heard,'success':True,**reading,'response':{'success':True,'accepted':reading['complete'],'continue_prompt':prompt,'reading':reading,'progress':{'state':old,'completed_items':old.get('completed_items',i)}}})
  cases.append({'index':i,'text':text,'state':state,'clips':clips})
 fixtures.append({'key':key,'name':name,'data':data,'cases':cases,'html':render_to_string('pabasa_app/prescribed_'+name+'_page.html',{'prescribed_activity_data':data})})
print(json.dumps(fixtures))
`], {cwd:root,encoding:'utf8',maxBuffer:3*1024*1024});
assert.equal(rendered.status,0,rendered.stderr);
const fixtures=JSON.parse(rendered.stdout);
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 let checked=0;
 async function open(fixture,clip,viewport={width:1366,height:768},real=false,fullControls=false,options={}){
  const page=await browser.newPage({viewport});const errors=[],saves=[],requests=[],narrations=[];
  const csrfToken='a'.repeat(32);
  await page.context().addCookies([{name:'csrftoken',value:csrfToken,url:'http://localhost:9876/'}]);
  let state=structuredClone(clip.state),failSave=false,committed=null,releasePlayback=null,playbackSaves=0,releaseContinuation=null,continuationSaves=0;
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://localhost:9876/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/activity/'){
    const data={...fixture.data,progress:{state}};
    let html=fixture.html.replace(/(<script id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,a,b)=>a+JSON.stringify(data)+b);
    html=html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,(tag,attrs)=>{
     if(/application\/json/.test(attrs))return tag;
     const name=path.posix.basename(attrs.match(/src="([^"]+)"/)?.[1]?.split('?')[0]||'');
     return [fixture.name&&'prescribed_'+fixture.name+'.js','prescribed_sentence_reading.js','prescribed_lesson26_31_ui.js','basahin_button.js',...(real?['basahin.js']:[])].includes(name)||(fullControls&&name&&name!=='basahin.js')?tag:'';
    });
    return route.fulfill({contentType:'text/html',body:html});
   }
   if(url.pathname==='/progress/'){
    const payload=route.request().postDataJSON();saves.push(payload);
    let result;
    if(payload.action==='sentence_continuation'){
     const selected=clip.clips.find(c=>c.heard===payload.heard);
     assert.ok(selected,payload.heard);result=structuredClone(selected.response);state=result.progress.state;
     continuationSaves++;
     if(options.holdContinuationSave&&continuationSaves===1)await new Promise(resolve=>releaseContinuation=resolve);
     if(failSave){failSave=false;committed={id:payload.request_id,result};return route.fulfill({status:503,json:{success:false,error:'Temporary save failure'}});}
     if(committed?.id===payload.request_id)result=committed.result;
    }else if(payload.action==='read_choice'){
     assert.equal(payload.heard,fixture.data.word_choices[state.choice_index]);
     state.choice_index++;state.phase='sentence_listen';result={success:true,accepted:true,progress:{state}};
    }else if(payload.action==='sentence_played'){
     playbackSaves++;
     assert.equal(typeof payload.request_id,'string');
     if(options.failPlaybackSaveOnce&&playbackSaves===1)
      return route.fulfill({status:503,json:{success:false,error:'Could not save playback.'}});
     const receipt=state.sentence_played_request;
     if(receipt?.id===payload.request_id){
      assert.equal(receipt.item_index,payload.item_index);
     }else{
      if(state.phase!=='sentence_listen'||state.current_item!==payload.item_index)
       return route.fulfill({status:400,json:{success:false,error:'Listen to the sentence first.'}});
      state.phase='dragging';state.sentence_played_request={id:payload.request_id,item_index:payload.item_index};
     }
     result={success:true,accepted:true,progress:{state:structuredClone(state)}};
     if(options.holdPlaybackSave&&playbackSaves===1)await new Promise(resolve=>releasePlayback=resolve);
     if(options.losePlaybackAck&&playbackSaves===1)return route.abort('failed');
    }
    else result={success:true,progress:{state}};
    return route.fulfill({json:result});
   }
   if(url.pathname==='/narrate/'){
    // Match Django's CSRF requirement; an audio fixture must not accept a
    // request the real read-aloud endpoint would reject.
    assert.equal(route.request().headers()['x-csrftoken'],csrfToken);
    narrations.push(new URLSearchParams(route.request().postData()).get('target_text'));
    if(narrations.length===options.failNarrationAt)return route.fulfill({status:503,json:{success:false,error:'Audio unavailable'}});
    return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}});
   }
   if(url.pathname==='/complete/')return route.fulfill({json:{success:true}});
   if(url.pathname==='/transcribe/'){requests.push(route.request().postDataBuffer().toString());return route.fulfill({json:await page.evaluate(()=>window.clips.shift())});}
   if(url.pathname.startsWith('/static/pabasa_app/')){
    const file=path.join(app,decodeURIComponent(url.pathname.slice(1)));
    if(fs.existsSync(file))return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.mp3')?'audio/mpeg':'application/octet-stream'});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.addInitScript(({real,holdNarration})=>{
   window.clips=[];window.readingFields=[];window.readingOptions=[];window.played=[];window.holdPrompt=false;
   window.holdNarration=holdNarration;
   navigator.mediaDevices.enumerateDevices=async()=>[];
   window.Audio=class extends EventTarget{
    constructor(url){super();this.url=decodeURIComponent(url);}
    play(){window.played.push(this.url);if(window.holdPrompt&&this.url.includes('rest of the sentence'))window.promptAudio=this;else if(window.holdNarration&&this.url.startsWith('blob:'))window.heldNarration=this;else queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();}
    pause(){this.dispatchEvent(new Event('pause'));}
   };
   if(real){
    window.testStreams=[];navigator.mediaDevices.getUserMedia=async()=>{
     const context=new AudioContext(),tone=context.createOscillator(),gain=context.createGain(),output=context.createMediaStreamDestination();
     tone.connect(gain).connect(output);gain.gain.value=0;tone.start();gain.gain.setValueAtTime(.2,context.currentTime+1.5);gain.gain.setValueAtTime(0,context.currentTime+2.7);
     window.testStreams.push(output.stream);return output.stream;
    };
   }else{
    window.MediaRecorder=function(){};
    window.Basahin={bindActivity(button,action){window.BasahinButton.bindActivity(button,action);},cancelAll(){window.activeReader?.stop();},create(options){
     let wake;window.readingOptions.push({silenceMs:options.silenceMs,continuous:options.continuous});
     const reader={async start(){window.readingFields.push(options.getFields());window.lateResult=options.onResult;if(!window.clips.length){await new Promise(resolve=>wake=resolve);return;}const clip=window.clips.shift();if(clip.error)options.onError(new Error(clip.error));else await options.onResult(clip);},stop(){wake?.();},destroy(){this.stop();}};
     window.activeReader=reader;return reader;
    },async read(){return window.clips.shift();}};
   }
  },{real,holdNarration:Boolean(options.holdNarration)});
  await page.goto('http://localhost:9876/activity/');
  if(fullControls&&!options.manualStart){await page.click('[id$="-go"]');await page.waitForFunction(()=>!document.querySelector('[id$="-start"]').hidden===false);}
  else if(fullControls){/* Keep the real Start gate visible for startup checks. */}
  else await page.evaluate(()=>{document.querySelector('[id$="-start"]').hidden=true;document.querySelector('.stage').classList.remove('waiting');});
  const selector=fixture.key==='lesson-31-gawain-2'?'#sentence':fixture.key==='lesson-31-gawain-3'?'#read-sentence':'#read';
  const prefix=fixture.key==='lesson-29-gawain-1'?'session13-prescribed-s13l29g1':fixture.key==='lesson-30-gawain-2'?'lesson30-lesson30a2':fixture.key==='lesson-31-gawain-2'?'session15-lesson31a2':'session15-lesson31a3';
  async function read(value){await page.evaluate(value=>window.clips.push(value),value);await page.click(selector);}
  return {page,selector,prefix,errors,saves,requests,narrations,read,fail(){failSave=true;},releasePlayback(){assert.ok(releasePlayback);releasePlayback();},releaseContinuation(){assert.ok(releaseContinuation);releaseContinuation();},state:()=>state};
 }
 const visualOnly=process.env.PABASA_SENTENCE_VISUAL_ONLY==='1';
 if(!visualOnly){
  let restoredCases=0;
  async function waitForReadingSave(h){
   for(let attempt=0;attempt<100&&!h.saves.some(save=>save.action==='sentence_continuation');attempt++)await h.page.waitForTimeout(10);
   assert.ok(h.saves.some(save=>save.action==='sentence_continuation'));
  }
  async function pause(h){await h.page.click('[id$="-audio-settings-btn"]');}
  async function resume(h){await h.page.click('[id$="-resume"]');}
  for(const fixture of fixtures){
   for(const releaseBeforeResume of [false,true]){
    const clip=structuredClone(fixture.cases[0]);clip.state=structuredClone(clip.clips[1].response.progress.state);
    const h=await open(fixture,clip,undefined,false,true,{holdContinuationSave:true});
    await h.read(clip.clips[2]);await waitForReadingSave(h);await pause(h);
    if(releaseBeforeResume){h.releaseContinuation();await h.page.waitForTimeout(50);}
    await resume(h);
    if(!releaseBeforeResume){assert.equal(await h.page.locator(h.selector).isEnabled(),false);h.releaseContinuation();}
    await h.page.waitForFunction(()=>document.querySelector('.step.active')?.textContent==='2');
    assert.equal(h.state().current_item??h.state().current_line,1);
    assert.equal(h.saves.filter(save=>save.action==='sentence_continuation').length,1);
    if(fixture.key==='lesson-31-gawain-2'){
     await h.page.waitForSelector('.choices');assert.equal(h.narrations.at(-1),fixture.cases[1].text);
     assert.equal(h.saves.filter(save=>save.action==='sentence_played').length,1);
    }else if(fixture.key==='lesson-31-gawain-3')assert.equal(await h.page.locator('#read-word').count(),1);
    else if(fixture.key==='lesson-29-gawain-1')assert.equal(await h.page.locator('.prescribed-reading-sentence').count(),0);
    else{await h.page.waitForFunction(text=>document.querySelector('.line.current').textContent===text,fixture.cases[1].text);assert.equal(h.narrations.at(-1),fixture.cases[1].text);}
    assert.deepEqual(h.errors,[]);await h.page.close();restoredCases++;
   }
   // Partial progress keeps its green prefix and plays the continuation cue
   // only after resume. Pausing again while the save is pending cannot eat it.
   const clip=fixture.cases[0],partial=await open(fixture,clip,undefined,false,true,{holdContinuationSave:true});
   await partial.page.evaluate(()=>window.holdPrompt=true);
   await partial.read(clip.clips[0]);await waitForReadingSave(partial);await pause(partial);await resume(partial);
   await pause(partial);partial.releaseContinuation();await partial.page.waitForTimeout(50);
   assert.equal(await partial.page.evaluate(()=>window.promptAudio!==undefined),false);
   await resume(partial);await partial.page.waitForFunction(()=>window.promptAudio);
   const active=partial.page.locator(fixture.key==='lesson-30-gawain-2'?'.line.current':'#app');
   assert.equal(await active.locator('.prescribed-reading-word.is-read').count(),2);
   assert.equal(await partial.page.locator(partial.selector).isEnabled(),false);
   await partial.page.evaluate(()=>window.promptAudio.dispatchEvent(new Event('ended')));
   await partial.page.waitForFunction(selector=>!document.querySelector(selector).disabled,partial.selector);
   assert.equal(partial.state().sentence_word_index,2);assert.equal(partial.saves.length,1);
   assert.deepEqual(partial.errors,[]);await partial.page.close();restoredCases++;
   // Failed acknowledgement on resume remains recoverable with the same
   // request, without losing the saved prefix or sending a new recording.
   const failed=await open(fixture,clip,undefined,false,true,{holdContinuationSave:true});failed.fail();
   await failed.read(clip.clips[0]);await waitForReadingSave(failed);await pause(failed);await resume(failed);
   failed.releaseContinuation();await failed.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('Temporary save failure'));
   await pause(failed);await resume(failed);await failed.page.waitForFunction(()=>document.querySelector('.prescribed-reading-word.is-read'));
   assert.equal(failed.saves.length,2);assert.equal(failed.saves[0].request_id,failed.saves[1].request_id);
   assert.deepEqual(failed.errors,[]);await failed.page.close();restoredCases++;
   // Muting does not emit resume, so the late successful result must also
   // synchronize the visible highlights without starting audio or a new mic.
   const muted=await open(fixture,clip,undefined,false,true,{holdContinuationSave:true});
   await muted.read(clip.clips[0]);await waitForReadingSave(muted);
   await muted.page.evaluate(prefix=>window.dispatchEvent(new CustomEvent(prefix+'-mute',{detail:{muted:true}})),muted.prefix);
   const narrationCount=muted.narrations.length;muted.releaseContinuation();
   await muted.page.waitForFunction(()=>document.querySelector('.prescribed-reading-word.is-read'));
   assert.equal(muted.narrations.length,narrationCount);assert.equal(muted.saves.length,1);
   assert.deepEqual(muted.errors,[]);await muted.page.close();restoredCases++;
   // Cleanup must never revive the old screen, completion request or audio.
   const disposed=await open(fixture,clip,undefined,false,true,{holdContinuationSave:true});
   await disposed.read(clip.clips[0]);await waitForReadingSave(disposed);
   await disposed.page.evaluate(prefix=>window.dispatchEvent(new Event(prefix+'-cleanup')),disposed.prefix);
   const html=await disposed.page.locator('#app').innerHTML(),before=disposed.narrations.length;
   disposed.releaseContinuation();await disposed.page.waitForTimeout(100);
   assert.equal(await disposed.page.locator('#app').innerHTML(),html);assert.equal(disposed.narrations.length,before);
   assert.deepEqual(disposed.errors,[]);await disposed.page.close();restoredCases++;
   // A delayed final sentence still renders completion after resume.
   const last=structuredClone(fixture.cases.at(-1));last.state=structuredClone(last.clips[1].response.progress.state);
   const final=await open(fixture,last,undefined,false,true,{holdContinuationSave:true});
   await final.read(last.clips[2]);await waitForReadingSave(final);await pause(final);await resume(final);
   final.releaseContinuation();await final.page.waitForSelector('.pabasa-completion-card');
   assert.equal(final.state().phase,'complete');assert.equal(final.saves.length,1);
   assert.deepEqual(final.errors,[]);await final.page.close();restoredCases++;
  }
  console.log(`Passed ${restoredCases} delayed reading-save recovery, partial cue, failure retry, mute, cleanup and completion scenarios.`);
 }
 if(!visualOnly){
  const fixture=fixtures.find(value=>value.key==='lesson-31-gawain-2');
  const listeningClip=index=>{const clip=structuredClone(fixture.cases[index]);clip.state.phase='sentence_listen';clip.state.placed_word='';return clip;};
  async function finishNarration(page,nextCount){
   await page.evaluate(()=>{const audio=window.heldNarration;window.heldNarration=null;audio.dispatchEvent(new Event('ended'));});
   if(nextCount)await page.waitForFunction(count=>window.played.length===count,nextCount);
  }
  // A resumed listening phase must remain behind Start. Each real audio end
  // gates the next clip; rendering or clicking Start cannot mark it played.
  const startup=await open(fixture,listeningClip(0),undefined,false,true,{holdNarration:true,manualStart:true});
  assert.equal(startup.narrations.length,0);assert.equal(startup.saves.length,0);
  await startup.page.click('#lesson31a2-go');await startup.page.waitForFunction(()=>window.heldNarration);
  assert.equal(startup.narrations.length,1);assert.equal(startup.state().phase,'sentence_listen');
  await finishNarration(startup.page,2);
  assert.equal(startup.saves.length,0);assert.equal(await startup.page.locator('#retry-sentence').isEnabled(),false);
  await finishNarration(startup.page,3);
  assert.equal(startup.narrations.at(-1),fixture.cases[0].text);assert.equal(startup.saves.length,0);
  await finishNarration(startup.page);await startup.page.waitForSelector('.choices');
  assert.equal(startup.state().phase,'dragging');assert.equal(startup.saves.length,1);
  assert.deepEqual(startup.errors,[]);await startup.page.close();
  // A failed sentence request stays in its phase without automatic retries.
  // The learner's retry starts a fresh attempt, with one phase save on success.
  const failure=await open(fixture,listeningClip(1),undefined,false,true,{failNarrationAt:2});
  await failure.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('Audio unavailable'));
  await failure.page.evaluate(()=>new Promise(resolve=>setTimeout(resolve,150)));
  assert.equal(failure.narrations.length,2);assert.equal(failure.saves.length,0);
  assert.equal(failure.state().phase,'sentence_listen');
  await failure.page.click('#retry-sentence');await failure.page.waitForSelector('.choices');
  assert.equal(failure.narrations.length,3);assert.equal(failure.saves.length,1);
  assert.deepEqual(failure.errors,[]);await failure.page.close();
  // Pausing a playing sentence cannot unlock dragging; resume must replay it.
  const pause=await open(fixture,listeningClip(1),undefined,false,true,{holdNarration:true});
  await pause.page.waitForFunction(()=>window.heldNarration);await finishNarration(pause.page,2);
  await pause.page.click('#lesson31a2-audio-settings-btn');
  assert.equal(pause.state().phase,'sentence_listen');assert.equal(pause.saves.length,0);
  await pause.page.click('#lesson31a2-resume');await pause.page.waitForFunction(()=>window.played.length===3);
  assert.equal(pause.saves.length,0);assert.equal(pause.narrations.at(-1),fixture.cases[1].text);
  await finishNarration(pause.page);await pause.page.waitForSelector('.choices');
  assert.equal(pause.saves.length,1);assert.deepEqual(pause.errors,[]);await pause.page.close();
  // Finishing the choice-reading gate still narrates the first sentence.
  const choiceClip=listeningClip(0);choiceClip.state.phase='reading_choices';choiceClip.state.choice_index=fixture.data.word_choices.length-1;
  const choice=await open(fixture,choiceClip,undefined,false,true);
  await choice.page.waitForFunction(()=>document.querySelector('#read')&&!document.querySelector('#read').disabled);
  await choice.page.evaluate(word=>window.clips.push({raw_transcript:word}),fixture.data.word_choices.at(-1));
  await choice.page.click('#read');await choice.page.waitForSelector('.choices');
  assert.equal(choice.narrations.at(-1),fixture.cases[0].text);
  assert.equal(choice.saves.filter(save=>save.action==='sentence_played').length,1);
  assert.deepEqual(choice.errors,[]);await choice.page.close();
  // Completing a partly read sentence must also wait for the next sentence's
  // narration before enabling its drag choices.
  const nextClip=structuredClone(fixture.cases[0]);nextClip.state=structuredClone(nextClip.clips[1].response.progress.state);
  const next=await open(fixture,nextClip,undefined,false,true,{holdNarration:true});
  await next.page.waitForFunction(()=>window.heldNarration);await finishNarration(next.page);
  await next.read(nextClip.clips[2]);await next.page.waitForFunction(()=>window.played.length===2);
  assert.equal(next.state().current_item,1);assert.equal(next.state().phase,'sentence_listen');
  await finishNarration(next.page,3);
  assert.equal(next.narrations.at(-1),fixture.cases[1].text);
  assert.equal(next.saves.filter(save=>save.action==='sentence_played').length,0);
  await finishNarration(next.page);await next.page.waitForSelector('.choices');
  assert.equal(next.saves.filter(save=>save.action==='sentence_played').length,1);
  assert.deepEqual(next.errors,[]);await next.page.close();
  // Pause after playback, while its save response is still pending. Resume
  // shares that save; a late acknowledgement must render the drag choices.
  for(const releaseWhilePaused of [false,true]){
   const delayed=await open(fixture,listeningClip(1),undefined,false,true,{holdPlaybackSave:true});
   await delayed.page.waitForFunction(()=>window.played.length===2);
   for(let attempt=0;attempt<100&&!delayed.saves.some(save=>save.action==='sentence_played');attempt++)await delayed.page.waitForTimeout(10);
   assert.ok(delayed.saves.some(save=>save.action==='sentence_played'));
   await delayed.page.click('#lesson31a2-audio-settings-btn');
   if(releaseWhilePaused){delayed.releasePlayback();await delayed.page.waitForTimeout(100);}
   await delayed.page.click('#lesson31a2-resume');
   if(!releaseWhilePaused){
    await delayed.page.waitForTimeout(100);
    assert.equal(delayed.narrations.length,2);assert.equal(await delayed.page.locator('.choices').count(),0);
    delayed.releasePlayback();
   }
   await delayed.page.waitForSelector('.choices');
   assert.equal(delayed.narrations.length,2);
   assert.equal(delayed.saves.filter(save=>save.action==='sentence_played').length,1);
   assert.deepEqual(delayed.errors,[]);await delayed.page.close();
  }
  // Mute cancels playback ownership without opening the pause modal. A save
  // already sent for finished audio must still update the visible phase.
  const mutedSave=await open(fixture,listeningClip(1),undefined,false,true,{holdPlaybackSave:true});
  for(let attempt=0;attempt<100&&!mutedSave.saves.some(save=>save.action==='sentence_played');attempt++)await mutedSave.page.waitForTimeout(10);
  assert.ok(mutedSave.saves.some(save=>save.action==='sentence_played'));
  await mutedSave.page.click('#lesson31a2-mic-toggle');mutedSave.releasePlayback();
  await mutedSave.page.waitForSelector('.choices');
  assert.equal(mutedSave.narrations.length,2);assert.equal(mutedSave.saves.length,1);
  assert.deepEqual(mutedSave.errors,[]);await mutedSave.page.close();
  // The server committed the save, but its acknowledgement was lost. Retry
  // sends the same receipt without replaying audio or rejecting the phase.
  const lost=await open(fixture,listeningClip(1),undefined,false,true,{losePlaybackAck:true});
  await lost.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('retry'));
  assert.equal(lost.state().phase,'dragging');assert.equal(await lost.page.locator('.choices').count(),0);
  await lost.page.click('#retry-sentence');await lost.page.waitForSelector('.choices');
  const receipts=lost.saves.filter(save=>save.action==='sentence_played');
  assert.equal(receipts.length,2);assert.deepEqual(receipts[0],receipts[1]);assert.equal(lost.narrations.length,2);
  assert.deepEqual(lost.errors,[]);await lost.page.close();
  // A failed save before any server commit is equally retryable. The sentence
  // has already finished playing, so retry only saves that completed playback.
  const unsaved=await open(fixture,listeningClip(1),undefined,false,true,{failPlaybackSaveOnce:true});
  await unsaved.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('Could not save playback'));
  assert.equal(unsaved.state().phase,'sentence_listen');
  await unsaved.page.click('#retry-sentence');await unsaved.page.waitForSelector('.choices');
  assert.equal(unsaved.saves.length,2);assert.deepEqual(unsaved.saves[0],unsaved.saves[1]);assert.equal(unsaved.narrations.length,2);
  assert.deepEqual(unsaved.errors,[]);await unsaved.page.close();
  // Leaving also flushes a pending playback receipt, like reading progress.
  const leaving=await open(fixture,listeningClip(1),undefined,false,true,{losePlaybackAck:true});
  await leaving.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('retry'));
  await leaving.page.evaluate(()=>window.__prescribedLeaveAdapters.lesson31a2.saveCurrentProgress());
  assert.equal(leaving.saves.length,2);assert.deepEqual(leaving.saves[0],leaving.saves[1]);
  assert.deepEqual(leaving.errors,[]);await leaving.page.close();
  console.log('Passed eleven Lesson 31 Activity 2 startup, playback, retry, cancellation, next-sentence and save-recovery scenarios.');
 }
 for(const fixture of fixtures){
  for(const viewport of [{width:1366,height:768},{width:390,height:844}])for(const clip of visualOnly?fixture.cases.slice(0,1):fixture.cases){
   const h=await open(fixture,clip,viewport);
   assert.equal(await h.page.locator('.prescribed-reading-unread').count(),1);
   const style=await h.page.locator('.prescribed-reading-unread').evaluate(el=>({decoration:getComputedStyle(el).textDecorationLine,border:getComputedStyle(el).borderTopWidth}));
   assert.equal(style.decoration,'none');assert.equal(style.border,'2px');
   assert.equal(await h.page.locator('.blank,.slots').count(),0);
   if(clip.index===0&&viewport.width===1366)await h.page.screenshot({path:path.join(process.env.TEMP,fixture.key+'-sentence-highlight.png')});
   await h.read(clip.clips[0]);
   await h.page.waitForFunction(()=>document.querySelector('.prescribed-reading-word.is-read'));
   // Story paragraphs already completed also have green words.
   const active=h.page.locator(fixture.key==='lesson-30-gawain-2'?'.line.current':'#app');
   assert.equal(await active.locator('.prescribed-reading-word.is-read').count(),2);
   assert.ok((await h.page.evaluate(()=>window.played)).some(url=>url.includes('rest of the sentence..mp3')));
   assert.equal(h.state().completed_items,clip.index);
   await h.page.reload();
   await h.page.evaluate(()=>{document.querySelector('[id$="-start"]').hidden=true;document.querySelector('.stage').classList.remove('waiting');});
   assert.equal(await active.locator('.prescribed-reading-word.is-read').count(),2);
   await h.read(clip.clips[1]);
   await h.page.waitForFunction(()=>/try again|again|another try/i.test(document.querySelector('.status').textContent));
   assert.equal(await active.locator('.prescribed-reading-word.is-read').count(),2);
   assert.equal(h.state().completed_items,clip.index);
   await h.read(clip.clips[2]);
   await h.page.waitForFunction(text=>!document.querySelector('.prescribed-reading-unread')||document.querySelector('.line.current')?.textContent.trim()!==text.trim(),clip.text);
   assert.equal(h.state().completed_items,clip.index+1);
   assert.equal(h.state().sentence_syllable_index,0);
   assert.deepEqual(h.errors,[]);
   await h.page.close();checked++;
  }
 }
 for(const fixture of visualOnly?[]:fixtures){
  const clip=fixture.cases[0],h=await open(fixture,clip);
  // A provider failure or empty speech must not write progress.
  await h.read({error:'Provider unavailable'});await h.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('Provider unavailable'));
  await h.read({success:true,transcript:''});await h.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('No speech'));
  assert.equal(h.saves.length,0);
  // Pause during capture; a late result must be ignored.
  await h.page.click(h.selector);await h.page.waitForFunction(()=>window.lateResult);
  await h.page.evaluate(prefix=>window.dispatchEvent(new Event(prefix+'-pause')),h.prefix);
  await h.page.evaluate(value=>window.lateResult(value),clip.clips[0]);assert.equal(h.saves.length,0);
  await h.page.evaluate(prefix=>window.dispatchEvent(new Event(prefix+'-resume')),h.prefix);
  // Pause the actual continuation prompt and resume with an enabled Read button.
  await h.page.evaluate(()=>window.holdPrompt=true);await h.read(clip.clips[0]);
  await h.page.waitForFunction(()=>window.promptAudio);
  await h.page.evaluate(prefix=>window.dispatchEvent(new Event(prefix+'-pause')),h.prefix);
  await h.page.evaluate(prefix=>window.dispatchEvent(new Event(prefix+'-resume')),h.prefix);
  assert.equal(await h.page.locator(h.selector).isEnabled(),true);
  await h.page.evaluate(()=>window.holdPrompt=false);
  h.fail();await h.read(clip.clips[1]);await h.page.waitForFunction(()=>document.querySelector('.status').textContent.includes('Temporary save failure'));
  const adapter=fixture.key==='lesson-29-gawain-1'?'prescribed-s13l29g1':fixture.key==='lesson-30-gawain-2'?'lesson30a2':fixture.key==='lesson-31-gawain-2'?'lesson31a2':'lesson31a3';
  await h.page.evaluate(adapter=>window.__prescribedLeaveAdapters[adapter].saveCurrentProgress(),adapter);
  assert.equal(h.saves.at(-1).request_id,h.saves.at(-2).request_id);
  assert.deepEqual(h.errors,[]);await h.page.close();
  // Actual shared Basahin capture: silence ends the clip and releases all tracks.
  const real=await open(fixture,clip,{width:1366,height:768},true);
  await real.read(clip.clips[0]);await real.page.waitForFunction(()=>document.querySelector('.prescribed-reading-word.is-read'),null,{timeout:15000});
  assert.equal(await real.page.evaluate(()=>window.testStreams.every(stream=>stream.getTracks().every(track=>track.readyState==='ended'))),true);
  assert.equal(real.requests.length,1);assert.ok(real.requests[0].includes(fixture.key));
  assert.deepEqual(real.errors,[]);await real.page.close();
  // Keep the actual activity controls loaded: Help must cancel cleanly and
  // closing it must restore an operational sentence reader.
  const controls=await open(fixture,clip,{width:1366,height:768},false,true);
  await controls.page.click(controls.selector);await controls.page.waitForFunction(()=>window.lateResult);
  await controls.page.click('[id$="-help-btn"]');
  await controls.page.evaluate(value=>window.lateResult(value),clip.clips[0]);
  assert.equal(controls.saves.length,0);
  await controls.page.click('[id$="-help-close"]');
  await controls.read(clip.clips[0]);
  await controls.page.waitForFunction(()=>document.querySelector('.prescribed-reading-word.is-read'));
  assert.equal(controls.state().sentence_word_index,2);
  assert.deepEqual(controls.errors,[]);await controls.page.close();
 }
 // Decode the supplied prompt bytes, independently of the playback fixture.
 const page=await browser.newPage();await page.setContent('<!doctype html><title>Audio decode</title>');
 const audio=fs.readFileSync(path.join(app,'static/pabasa_app/prescribed/audio/SESSION_10/LESSON_26/GAWAIN_2/Great! now let\'s read the rest of the sentence..mp3'));
 const duration=await page.evaluate(async bytes=>{const context=new AudioContext();const buffer=await context.decodeAudioData(Uint8Array.from(bytes).buffer);await context.close();return buffer.duration;},[...audio]);
 assert.ok(duration>1);await page.close();await browser.close();
 console.log(`Passed ${checked} sentence/viewport cases across all four activities${visualOnly?' (visual pass).':', plus provider failure, pause, save retry and microphone lifecycle checks.'}`);
})().catch(error=>{console.error(error);process.exit(1);});
