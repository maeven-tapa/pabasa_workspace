// Actual Django templates and activity scripts; synthetic audio/provider and
// in-memory progress only. No accounts, physical microphone or live requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const root = path.resolve(__dirname, '..'), app = path.join(root, 'pabasa_site/pabasa_app');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import os,sys,json
sys.path.insert(0,'pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.template.loader import render_to_string
from pabasa_app.prescribed_activity_catalog import prescribed_activity
names={'lesson-28-gawain-2':'word_identifying_lesson28_activity2','lesson-29-gawain-2':'spot_word_lesson29_activity2','lesson-30-gawain-1':'match_it_lesson30_activity1','lesson-30-gawain-3':'comprehension_lesson30_activity3'}
fixtures=[]
for key,name in names.items():
 a=prescribed_activity(key);state={'current_item':0}
 if key=='lesson-28-gawain-2':state.update(phase='choosing',target_word=a['items'][0]['choices'][0])
 if key=='lesson-29-gawain-2':state.update(phase='spotting',selected_words=[],target_word=a['words'][0])
 if key=='lesson-30-gawain-1':state={'phase':'oral_reading','stt_attempts':{a['word_bank'][0]:3},'matches':{},'skipped_picture_words':[]}
 if key=='lesson-30-gawain-3':state.update(phase='answering')
 data={**a,'progress':{'state':state},'progress_url':'/progress/','completion_url':'/complete/','read_aloud_url':'/narrate/','transcribe_url':'/transcribe/'}
 fixtures.append({'key':key,'data':data,'html':render_to_string('pabasa_app/prescribed_'+name+'_page.html',{'prescribed_activity_data':data})})
print(json.dumps(fixtures))
`], {cwd:root, encoding:'utf8', maxBuffer:2*1024*1024});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checked = 0;
  async function open(fixture, {holdIntro=false, holdCompletion=false, completionFailure=false}={}) {
    const page = await browser.newPage(), errors=[], saves=[], narrations=[], completions=[], alerts=[];
    const completionReleases=[];
    let state = structuredClone(fixture.data.progress.state), heldNarration=false, releaseNarration;
    let heldSave=false, releaseSave, narrationFailure=false;
    let answerFailure=false, resetFailure=null, heldReset=false, releaseReset;
    const lesson=fixture.key.split('-')[1], number=fixture.key.split('-')[3];
    const prefix=lesson==='28'?'prescribed-l28a2':lesson==='29'?'prescribed-s13l29g2':'lesson30a'+number;
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', async dialog=>{alerts.push(dialog.message());await dialog.dismiss();});
    await page.addInitScript(hold => {
      window.audioPlays=[]; window.holdAudio=hold; window.audioFailure=false; window.captureCalls=0; window.readFields=[];
      window.holdSpeech=false; window.speechReplies=[];
      window.audioUrls=new Set();
      const createUrl=URL.createObjectURL.bind(URL), revokeUrl=URL.revokeObjectURL.bind(URL);
      URL.createObjectURL=blob=>{const url=createUrl(blob);window.audioUrls.add(url);return url;};
      URL.revokeObjectURL=url=>{window.audioUrls.delete(url);revokeUrl(url);};
      window.Basahin={cancelAll(){}, bindActivity(button, action){button?.addEventListener('click', action);},
        async read(fields){window.captureCalls++;window.readFields.push(fields);
          if(window.holdSpeech)return new Promise((resolve,reject)=>window.speechReplies.push({resolve,reject}));
          return {success:true, complete:true, raw_transcript:fields.target_text};}};
      navigator.mediaDevices.getUserMedia=async()=>{throw Error('Physical microphone must not be used');};
      window.Audio=class extends EventTarget {
        constructor(url){super();this.src=url;this.paused=true;window.audioPlays.push(this);}
        play(){
          if(window.audioFailure)return Promise.reject(new Error('Synthetic playback failure'));
          this.paused=false;
          if(!window.holdAudio)queueMicrotask(()=>{if(!this.paused){this.paused=true;this.onended?.();this.dispatchEvent(new Event('ended'));}});
          return Promise.resolve();
        }
        pause(){if(!this.paused){this.paused=true;this.dispatchEvent(new Event('pause'));}}
      };
    }, holdIntro);
    await page.route('http://localhost:9876/**', async route => {
      const url=new URL(route.request().url());
      if(url.pathname==='/activity/') {
        let html=fixture.html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,(tag,attrs)=>
          /application\/json/.test(attrs)||/prescribed_(audio_player|lesson26_31_ui|controls|word_identifying_lesson28_activity2|spot_word_lesson29_activity2|match_it_lesson30_activity1|comprehension_lesson30_activity3)\.js|session13_prescribed_controls\.js|lesson30_prescribed_controls\.js/.test(attrs)?tag:'');
        html=html.replace(/(<script[^>]*id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,head,tail)=>head+JSON.stringify({...fixture.data,progress:{state}})+tail);
        return route.fulfill({contentType:'text/html',body:html});
      }
      if(url.pathname==='/narrate/') {
        narrations.push(new URLSearchParams(route.request().postData()).get('target_text'));
        if(heldNarration)await new Promise(resolve=>{releaseNarration=resolve;});
        if(narrationFailure)return route.fulfill({status:503,json:{success:false,error:'Narration unavailable'}}).catch(()=>{});
        return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}}).catch(()=>{});
      }
      if(url.pathname==='/progress/') {
        const body=route.request().postDataJSON();saves.push(body);
        if(body.reset) {
          if(heldReset)await new Promise(resolve=>{releaseReset=resolve;});
          if(resetFailure==='http')return route.fulfill({status:503,json:{success:false,error:'Reset unavailable'}});
          if(resetFailure==='malformed')return route.fulfill({status:200,contentType:'text/html',body:'Invalid response'});
          if(resetFailure==='rejected')return route.fulfill({json:{success:false,error:'Reset rejected'}});
          state={};
          if(resetFailure==='lost-response')return route.abort('failed');
          return route.fulfill({json:{success:true,progress:{state}}}).catch(()=>{});
        }
        if(heldSave)await new Promise(resolve=>{releaseSave=resolve;});
        if(answerFailure)return route.fulfill({status:503,json:{success:false,error:'Answer save unavailable'}});
        if(body.state)state=structuredClone(body.state);
        if(body.action==='begin') {
          state.current_item=Number(state.current_item||0);
          if(lesson==='28')state.target_word||=fixture.data.items[state.current_item]?.choices[0];
          if(lesson==='29')state.target_word||=fixture.data.words[state.current_item];
        }
        if(body.action==='choose') {
          state.current_item++;
          if(lesson==='28')state.target_word=fixture.data.items[state.current_item]?.choices[0];
          if(lesson==='29'){state.selected_words.push(body.word);state.target_word=fixture.data.words[state.current_item];}
          if((lesson==='29'&&state.current_item===fixture.data.words.length)||(lesson==='30'&&number==='3'&&state.current_item===fixture.data.questions.length))state.phase='complete';
        }
        return route.fulfill({json:{success:true,accepted:true,progress:{state}}}).catch(()=>{});
      }
      if(url.pathname==='/complete/') {
        completions.push(route.request().postDataJSON());
        if(holdCompletion)await new Promise(resolve=>completionReleases.push(resolve));
        return route.fulfill(completionFailure?{status:503,json:{success:false,error:'Completion acknowledgement unavailable'}}:{json:{success:true}}).catch(()=>{});
      }
      if(url.pathname.startsWith('/static/')) {
        const file=path.join(app,decodeURIComponent(url.pathname.slice(1)));
        if(fs.existsSync(file))return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'text/javascript':'application/octet-stream'});
      }
      return route.fulfill({status:404,body:''});
    });
    await page.goto('http://localhost:9876/activity/');
    await page.click('#lesson'+lesson+'a'+number+'-go');
    if(holdIntro)await page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));
    else await page.waitForFunction(()=>window.audioPlays.length&&window.audioPlays.every(audio=>audio.paused)&&document.querySelector('#listen')&&!document.querySelector('#listen').disabled);
    const pause=()=>page.click('#'+prefix+'-audio-settings-btn');
    const resume=()=>page.click('#'+prefix+'-resume');
    return {page, prefix, lesson, number, saves, narrations, completions, alerts, pause, resume,
      getState:()=>state,
      holdNarration(){heldNarration=true;},
      async releaseNarration(){await page.waitForFunction(()=>true);heldNarration=false;releaseNarration?.();},
      holdSave(){heldSave=true;},
      async releaseSave(){assert.ok(releaseSave,'A save must be pending');heldSave=false;releaseSave();},
      failNarration(){narrationFailure=true;},
      failAnswer(){answerFailure=true;},
      failReset(failure){resetFailure=failure;},
      holdReset(){heldReset=true;},
      releaseReset(){assert.ok(releaseReset,'A reset must be pending');heldReset=false;releaseReset();},
      releaseCompletion(){holdCompletion=false;completionReleases.splice(0).forEach(resolve=>resolve());},
      async finish(){assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>window.audioUrls.size),0,'Temporary audio URLs must be released');await page.close();checked++;},
    };
  }
  async function ready(h){await h.page.waitForFunction(()=>window.audioPlays.every(audio=>audio.paused)&&document.querySelector('#listen')&&!document.querySelector('#listen').disabled);}
  async function correctChoice(h,fixture) {
    if(h.lesson==='30'&&h.number==='1') {
      if(await h.page.locator('#read').count()) {
        await h.page.click('#read');await h.page.waitForSelector('[data-id]');
        await h.page.waitForFunction(()=>window.audioPlays.every(audio=>audio.paused));
      }
      const target=fixture.data.word_bank[0],item=fixture.data.items.find(item=>item.word===target);
      return h.page.click('[data-id="'+item.id+'"]');
    }
    if(h.lesson==='30')return h.page.click('[data-choice="'+fixture.data.questions[0].answer+'"]');
    const target=h.getState().target_word;
    return h.page.click(h.lesson==='28'?'[data-choice="'+target+'"]':'[data-word="'+target+'"]');
  }
  try {
    for(const fixture of fixtures) {
      async function restart(h) {
        await h.pause();await h.page.click('#'+h.prefix+'-restart');await h.page.click('#'+h.prefix+'-restart-yes');
      }
      async function choosing(h) {
        if(h.lesson==='30'&&h.number==='1') {
          await h.page.click('#read');await h.page.waitForSelector('[data-id]');
          await h.page.waitForFunction(()=>window.audioPlays.every(audio=>audio.paused));
        }
      }
      // Reset follows the last submitted answer, never overtakes it. A second
      // Restart or Resume while waiting cannot issue new input or another reset.
      let h=await open(fixture);await choosing(h);h.holdSave();await correctChoice(h,fixture);
      await h.page.waitForTimeout(40);const sent=h.saves.length;await restart(h);
      await h.page.evaluate(prefix=>{
        document.getElementById(prefix+'-resume').click();
        document.getElementById(prefix+'-restart-yes').click();
        document.querySelector('#app button')?.click();
      },h.prefix);
      await h.page.waitForTimeout(40);assert.equal(h.saves.length,sent,'Restart must wait and block duplicate input');
      const loaded=h.page.waitForEvent('domcontentloaded');await h.releaseSave();await loaded;
      assert.deepEqual(h.getState(),{});assert.equal(h.saves.filter(body=>body.reset).length,1);assert.deepEqual(h.alerts,[]);
      assert.equal(await h.page.isVisible('#lesson'+h.lesson+'a'+h.number+'-start'),true);await h.finish();

      // Uncertain reset results reload the server state rather than resume the
      // cancelled activity, including a successful reset with a lost response.
      for(const failure of ['http','malformed','rejected','lost-response']) {
        h=await open(fixture);h.failReset(failure);const loaded=h.page.waitForEvent('domcontentloaded');
        await restart(h);await loaded;
        assert.equal(h.saves.filter(body=>body.reset).length,1);assert.equal(h.alerts.length,1);
        assert.match(h.alerts[0],/Reloading your saved progress/);
        assert.equal(await h.page.isVisible('#lesson'+h.lesson+'a'+h.number+'-start'),true);
        if(failure==='lost-response')assert.deepEqual(h.getState(),{});
        else assert.deepEqual(h.getState(),fixture.data.progress.state);
        await h.finish();
      }

      // A failed pending answer has uncertain persistence. Do not send reset
      // behind it; recover by reloading the authoritative progress instead.
      h=await open(fixture);await choosing(h);h.holdSave();h.failAnswer();await correctChoice(h,fixture);
      await h.page.waitForTimeout(40);await restart(h);const recovered=h.page.waitForEvent('domcontentloaded');
      await h.releaseSave();await recovered;assert.equal(h.saves.filter(body=>body.reset).length,0);
      assert.equal(h.alerts.length,1);await h.finish();

      // Restart also cancels narration that is still loading or playing.
      h=await open(fixture,{holdIntro:true});const loadedAfterAudio=h.page.waitForEvent('domcontentloaded');
      await restart(h);await loadedAfterAudio;assert.deepEqual(h.getState(),{});assert.deepEqual(h.alerts,[]);await h.finish();

      // Leaving during a pending answer must suppress the later reset/reload.
      h=await open(fixture);await choosing(h);h.holdSave();await correctChoice(h,fixture);
      await h.page.waitForTimeout(40);await restart(h);let navigations=0;
      h.page.on('domcontentloaded',()=>navigations++);
      await h.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));await h.releaseSave();await h.page.waitForTimeout(80);
      assert.equal(h.saves.filter(body=>body.reset).length,0);assert.equal(navigations,0);assert.deepEqual(h.alerts,[]);await h.finish();

      // A delayed reset response must not reload a page that has since left.
      h=await open(fixture);h.holdReset();await restart(h);await h.page.waitForTimeout(40);let resetNavigations=0;
      h.page.on('domcontentloaded',()=>resetNavigations++);
      await h.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));h.releaseReset();await h.page.waitForTimeout(80);
      assert.equal(resetNavigations,0);assert.deepEqual(h.alerts,[]);await h.finish();

      // Ordinary cached navigation must also recover the page-leaving guard,
      // even when no restart had disposed the activity before leaving.
      h=await open(fixture);
      await h.page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
      const ordinaryHistoryReload=h.page.waitForEvent('domcontentloaded');
      await h.page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
      await ordinaryHistoryReload;
      assert.equal(h.saves.filter(body=>body.reset).length,0,'Returning must preserve progress');
      assert.deepEqual(h.getState(),fixture.data.progress.state);
      assert.equal(await h.page.isVisible('#lesson'+h.lesson+'a'+h.number+'-start'),true);
      await h.page.click('#lesson'+h.lesson+'a'+h.number+'-go');await ready(h);
      const ordinaryHistoryReset=h.page.waitForEvent('domcontentloaded');
      await restart(h);await ordinaryHistoryReset;
      assert.equal(h.saves.filter(body=>body.reset).length,1,'Restart must work after cached return');
      assert.deepEqual(h.getState(),{});assert.deepEqual(h.alerts,[]);await h.finish();

      // Returning through browser history must reload a cancelled restart
      // instance instead of leaving its controls permanently disposed.
      h=await open(fixture);h.holdReset();await restart(h);await h.page.waitForTimeout(40);
      await h.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));h.releaseReset();await h.page.waitForTimeout(40);
      const historyReload=h.page.waitForEvent('domcontentloaded');
      await h.page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
      await historyReload;assert.deepEqual(h.getState(),{});
      assert.equal(h.saves.filter(body=>body.reset).length,1);assert.deepEqual(h.alerts,[]);await h.finish();

      if(fixture.key==='lesson-30-gawain-1') {
        // Even a provider that ignores cancellation cannot submit its old
        // recording while Restart is waiting for the reset response.
        h=await open(fixture);await h.page.evaluate(()=>window.holdSpeech=true);await h.page.click('#read');
        h.holdReset();await restart(h);await h.page.waitForTimeout(40);
        const before=h.narrations.length;
        await h.page.evaluate(()=>window.speechReplies[0].resolve({success:true,complete:true,raw_transcript:'pet'}));
        await h.page.waitForTimeout(40);assert.equal(h.saves.length,1);assert.ok(h.saves[0].reset);
        assert.equal(h.narrations.length,before);
        const recovered=h.page.waitForEvent('domcontentloaded');h.releaseReset();await recovered;await h.finish();
      }
    }
    // Final feedback must play while completion is acknowledged, and a late
    // acknowledgement must never replay audio cancelled by Pause or cleanup.
    for(const original of fixtures.filter(f=>['lesson-29-gawain-2','lesson-30-gawain-3'].includes(f.key))) {
      const fixture=structuredClone(original),spot=fixture.key==='lesson-29-gawain-2';
      const last=(spot?fixture.data.words:fixture.data.questions).length-1;
      fixture.data.progress.state.current_item=last;
      if(spot){fixture.data.progress.state.target_word=fixture.data.words[last];fixture.data.progress.state.selected_words=fixture.data.words.slice(0,last);}
      fixture.html=fixture.html.replace(/(<script[^>]*id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,head,tail)=>head+JSON.stringify(fixture.data)+tail);
      const feedback=spot?'Great job! You spotted all the words.':'Great job! You completed Comprehension Check.';
      // A completion acknowledgement is also a write. Restart must drain it
      // before resetting, while cancelling its audio and any further renders.
      {
        const h=await open(fixture,{holdCompletion:true});
        await h.page.evaluate(()=>window.holdAudio=true);
        await h.page.click(spot?'[data-word="'+fixture.data.words[last]+'"]':'[data-choice="'+fixture.data.questions[last].answer+'"]');
        await h.page.waitForSelector('.pabasa-completion-card');
        await h.page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));
        assert.ok(h.completions.length>0);
        // The completed screen hides the toolbar; invoke its existing restart
        // handler to exercise acknowledgement ordering directly.
        await h.page.evaluate(prefix=>document.getElementById(prefix+'-restart-yes').click(),h.prefix);
        await h.page.waitForTimeout(40);
        assert.equal(h.saves.filter(body=>body.reset).length,0,'Reset must wait for completion writes');
        assert.equal(await h.page.evaluate(()=>window.audioPlays.every(audio=>audio.paused)),true);
        const completionCount=h.completions.length;
        const loaded=h.page.waitForEvent('domcontentloaded');h.releaseCompletion();await loaded;
        assert.equal(h.saves.filter(body=>body.reset).length,1);
        assert.equal(h.completions.length,completionCount,'Disposed activity cannot submit another completion');
        assert.deepEqual(h.getState(),{});assert.deepEqual(h.alerts,[]);await h.finish();
      }
      for(const scenario of ['normal','pause','cleanup','acknowledgement-failure']) {
        const h=await open(fixture,{holdCompletion:true,completionFailure:scenario==='acknowledgement-failure'});
        await h.page.evaluate(()=>window.holdAudio=true);
        await h.page.click(spot?'[data-word="'+fixture.data.words[last]+'"]':'[data-choice="'+fixture.data.questions[last].answer+'"]');
        await h.page.waitForSelector('.pabasa-completion-card');
        await h.page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));
        assert.ok(h.completions.length>0,'Completion must still be acknowledged');
        assert.equal(h.narrations.filter(text=>text===feedback).length,1,'Final feedback must start before completion acknowledgement settles');
        assert.equal(h.getState().phase,'complete');
        assert.equal(h.saves.filter(body=>body.action==='choose').length,1);
        const played=await h.page.evaluate(()=>window.audioPlays.length);
        if(scenario==='pause') {
          // Completion hides the toolbar. Exercise its lifecycle events
          // directly rather than attempting to click hidden controls.
          await h.page.evaluate(eventPrefix=>{
            window.dispatchEvent(new Event(eventPrefix+'-pause'));
            window.dispatchEvent(new Event(eventPrefix+'-resume'));
          },(spot?'session13-':'lesson30-')+h.prefix);
        }
        else if(scenario==='cleanup')await h.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
        else await h.page.evaluate(()=>{for(const audio of window.audioPlays){if(!audio.paused){audio.paused=true;audio.onended?.();audio.dispatchEvent(new Event('ended'));}}});
        h.releaseCompletion();await h.page.waitForTimeout(80);
        assert.equal(await h.page.evaluate(()=>window.audioPlays.every(audio=>audio.paused)),true);
        assert.equal(await h.page.evaluate(()=>window.audioPlays.length),played,'Late acknowledgement cannot start another narration');
        assert.equal(h.narrations.filter(text=>text===feedback).length,1);
        assert.equal(h.getState().phase,'complete');
        await h.finish();
      }
    }
    for(const fixture of fixtures) {
      // Stopping audible playback releases its promise and permits Listen again.
      let h=await open(fixture);await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#listen');
      await h.page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));await h.pause();await h.resume();
      assert.equal(await h.page.evaluate(()=>window.audioPlays.every(audio=>audio.paused)),true);
      await h.page.evaluate(()=>window.holdAudio=false);await h.page.click('#listen');await ready(h);await h.finish();

      // Dismissing the Pause backdrop also resumes controls.
      h=await open(fixture);await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#listen');
      await h.pause();await h.page.locator('#'+h.prefix+'-pause-modal').click({position:{x:5,y:5}});
      await h.page.evaluate(()=>window.holdAudio=false);await h.page.click('#listen');await ready(h);await h.finish();

      // An interrupted introduction keeps a usable target and never chains
      // additional narration from the cancelled introduction.
      h=await open(fixture,{holdIntro:true});const introPlays=await h.page.evaluate(()=>window.audioPlays.length);
      await h.pause();await h.resume();await h.page.waitForTimeout(60);
      assert.equal(await h.page.evaluate(()=>window.audioPlays.length),introPlays);
      await h.page.evaluate(()=>window.holdAudio=false);await h.page.click('#listen');await ready(h);await h.finish();

      // Playback failures restore controls and allow a successful retry.
      h=await open(fixture);await h.page.evaluate(()=>window.audioFailure=true);await h.page.click('#listen');
      await h.page.waitForTimeout(40);assert.equal(await h.page.isEnabled('#listen'),true);
      await h.page.evaluate(()=>window.audioFailure=false);await h.page.click('#listen');await ready(h);await h.finish();

      // Pausing feedback preserves the committed answer, releases playback,
      // and prevents the old feedback from chaining another cue after Resume.
      h=await open(fixture);
      if(h.lesson==='30'&&h.number==='1') {
        await h.page.click('#read');await h.page.waitForSelector('[data-id]');
        await h.page.waitForFunction(()=>window.audioPlays.every(audio=>audio.paused));
      }
      await h.page.evaluate(()=>window.holdAudio=true);await correctChoice(h,fixture);
      await h.page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));
      const feedbackPlays=await h.page.evaluate(()=>window.audioPlays.length);
      await h.pause();await h.resume();await h.page.waitForTimeout(60);
      assert.equal(await h.page.evaluate(()=>window.audioPlays.length),feedbackPlays);
      assert.equal(h.lesson==='30'&&h.number==='1'?Object.keys(h.getState().matches).length:h.getState().current_item,1);
      await h.finish();

      if(h.lesson==='30'&&h.number==='1') {
        // Providers may reply after cancellation. Neither a late result nor a
        // late error can release the busy guard belonging to a newer recording.
        for(const lateFailure of [false,true]) {
          h=await open(fixture);await h.page.evaluate(()=>window.holdSpeech=true);
          await h.page.click('#read');await h.pause();await h.resume();await h.page.click('#read');
          assert.equal(await h.page.evaluate(()=>window.captureCalls),2);
          await h.page.evaluate(fail=>{
            const first=window.speechReplies[0];
            if(fail)first.reject(new Error('Late provider error'));
            else first.resolve({success:true,complete:true,raw_transcript:window.readFields[0].target_text});
          },lateFailure);
          await h.page.waitForTimeout(30);await h.page.click('#read',{force:true});
          assert.equal(await h.page.evaluate(()=>window.captureCalls),2);
          assert.equal(h.saves.length,0);
          await h.page.evaluate(()=>window.speechReplies[1].resolve({success:true,complete:true,raw_transcript:window.readFields[1].target_text}));
          await h.page.waitForSelector('[data-id]');await h.page.waitForTimeout(50);await h.finish();
        }
      }

      // Leaving while playback is active must settle and release that audio.
      h=await open(fixture);await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#listen');
      await h.page.waitForFunction(()=>window.audioPlays.some(audio=>!audio.paused));
      await h.page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));await h.page.waitForTimeout(40);
      assert.equal(await h.page.evaluate(()=>window.audioPlays.every(audio=>audio.paused)),true,fixture.key+' cleanup must stop every audio');await h.finish();

      if(h.lesson!=='28') {
        // Delayed network replies cannot start audio while paused or after a
        // rapid Resume starts a fresh Listen request.
        for(const resumeEarly of [false,true]) {
          h=await open(fixture);h.holdNarration();const initial=await h.page.evaluate(()=>window.audioPlays.length);
          await h.page.click('#listen');await h.page.waitForTimeout(40);await h.pause();
          if(resumeEarly)await h.resume();
          await h.releaseNarration();await h.page.waitForTimeout(50);
          assert.equal(await h.page.evaluate(()=>window.audioPlays.length),initial);
          if(!resumeEarly)await h.resume();
          await h.page.click('#listen');await ready(h);await h.finish();
        }
        h=await open(fixture);h.failNarration();await h.page.click('#listen');
        await h.page.waitForTimeout(40);assert.equal(await h.page.isEnabled('#listen'),true);await h.finish();
      }

      // Already sent choices commit once during Pause. Resume cannot issue
      // another answer until that save settles; its saved phase stays usable.
      h=await open(fixture);
      if(h.lesson==='30'&&h.number==='1') {
        await h.page.click('#read');await h.page.waitForSelector('[data-id]');
        await h.page.waitForFunction(()=>window.audioPlays.every(audio=>audio.paused));
      }
      h.holdSave();await correctChoice(h,fixture);await h.page.waitForTimeout(40);
      const sent=h.saves.length;await h.pause();await h.resume();
      const buttons=h.page.locator('#app button');await buttons.first().click({force:true});
      assert.equal(h.saves.length,sent);
      await h.releaseSave();await h.page.waitForTimeout(80);
      assert.equal(h.lesson==='30'&&h.number==='1'?Object.keys(h.getState().matches).length:h.getState().current_item,1);
      assert.equal(await h.page.evaluate(()=>window.audioPlays.every(audio=>audio.paused)),true);
      await h.finish();

      // Normal choice progression and the speech request's provider fields
      // remain intact after the audio lifecycle changes.
      h=await open(fixture);await correctChoice(h,fixture);await h.page.waitForTimeout(100);
      assert.equal(h.lesson==='30'&&h.number==='1'?Object.keys(h.getState().matches).length:h.getState().current_item,1);
      if(h.lesson==='30'&&h.number==='1') {
        const fields=await h.page.evaluate(()=>window.readFields[0]);
        assert.equal(fields.language,'English');assert.equal(fields.mode,'reading');assert.equal(fields.prescribed_activity_key,fixture.key);
        assert.ok(h.narrations.includes('Correct! Read the next word.'),'Normal deferred feedback must still play');
      }
      await h.finish();
    }
    console.log(`PASS: ${checked} Lesson 28/29/30 audio interruption, resume, delayed save, failure and progression scenarios.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
