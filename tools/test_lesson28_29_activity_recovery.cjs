// Actual Django templates and browser controls; local synthetic audio/HTTP only.
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
fixtures=[]
for key,name,prefix,start in [
 ('lesson-28-gawain-1','missing_letter_lesson28_activity1','prescribed-l28a1','lesson28a1'),
 ('lesson-28-gawain-2','word_identifying_lesson28_activity2','prescribed-l28a2','lesson28a2'),
 ('lesson-29-gawain-3','trace_say_lesson29_activity3','prescribed-s13l29g3','lesson29a3')]:
 a=prescribed_activity(key)
 d={**a,'progress':{'state':{}},'progress_url':'/progress/','completion_url':'/complete/',
    'recording_url':'/recording/','submission_url':'/submit/','transcribe_url':'/transcribe/','read_aloud_url':'/narrate/'}
 d['items']=[{**i,'image_url':static(i['image_path']) if i.get('image_path') else ''} for i in a['items']]
 fixtures.append({'key':key,'name':name,'prefix':prefix,'start':start,'data':d,
   'html':render_to_string('pabasa_app/prescribed_'+name+'_page.html',{'prescribed_activity_data':d})})
print(json.dumps(fixtures))
`], {cwd:root, encoding:'utf8', maxBuffer:3*1024*1024, env:{...process.env, DB_ENGINE:'sqlite', SQLITE_PATH:':memory:'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checks = 0;
  async function open(index, initial = {}, viewport = {width:1366, height:768}, realAudio = false) {
    const fixture = fixtures[index], page = await browser.newPage({viewport});
    page.setDefaultTimeout(realAudio ? 25000 : 10000);
    const state = {phase:index===0?'reading':index===1?'choosing':'sound', current_item:0, ...initial};
    const errors = [], saves = [], uploads = [], narrations = [], resets = [];
    let holdSave = false, releaseSave, holdNarration = false, releaseNarration, saveFailure = false;
    let holdUpload = false, releaseUpload;
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.dismiss());
    await page.addInitScript(realAudio => {
      window.audios=[]; window.playbacks=[]; window.mediaEvents=[]; window.holdAudio=false; window.failAudio=false;
      window.captureCalls=0; window.readCalls=0; window.testStreams=[];
      window.readError=''; window.capturePending=false; window.permissionPending=false;
      window.MediaRecorder=function(){};
      navigator.mediaDevices.enumerateDevices=async()=>[];
      const NativeAudio=window.Audio;
      const FixtureAudio=class extends EventTarget {
        constructor(src){super();this.src=src;this.paused=true;window.audios.push(this);}
        play(){
          window.playbacks.push({src:this.src,id:window.audios.indexOf(this)});
          this.paused=false;
          if(window.failAudio){this.paused=true;return Promise.reject(Error('Audio playback failed. Try again.'));}
          if(!window.holdAudio)queueMicrotask(()=>{if(!this.paused)this.finish();});
          return Promise.resolve();
        }
        finish(){this.paused=true;this.onended?.();this.dispatchEvent(new Event('ended'));}
        pause(){if(!this.paused){this.paused=true;this.dispatchEvent(new Event('pause'));}}
      };
      window.Audio=realAudio ? function(src){
        const audio=src===undefined?new NativeAudio():new NativeAudio(src),play=audio.play.bind(audio);window.audios.push(audio);
        for(const type of ['play','pause','ended','error'])audio.addEventListener(type,()=>window.mediaEvents.push({type,src:audio.src,ended:audio.ended,time:audio.currentTime}));
        audio.play=()=>{window.playbacks.push({src:audio.src,id:window.audios.indexOf(audio)});return play();};
        return audio;
      } : FixtureAudio;
      const makeStream=()=>{
        const track={stopped:false,enabled:true,stop(){this.stopped=true;}};
        const stream={getTracks:()=>[track],getAudioTracks:()=>[track]};
        window.testStreams.push(stream);return stream;
      };
      window.Basahin={
        bindActivity(button,action){button?.addEventListener('click',action);},
        cancelAll(){},
        async read(){window.readCalls++;if(window.readError)throw Error(window.readError);return {complete:true,raw_transcript:'sun'};},
        async openMicrophone(){
          if(window.permissionPending)return new Promise(resolve=>{window.resolvePermission=()=>resolve(makeStream());});
          return makeStream();
        },
        async capture({signal}){
          window.captureCalls++;
          if(window.capturePending)return new Promise((resolve,reject)=>{
            window.finishCapture=()=>resolve(new Blob(['synthetic test audio'],{type:'audio/webm'}));
            signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
          });
          return new Blob(['synthetic test audio'],{type:'audio/webm'});
        },
      };
    }, realAudio);
    await page.route('http://localhost:9876/**', async route => {
      const url=new URL(route.request().url());
      if(url.pathname==='/activity/') {
        const data={...fixture.data,progress:{state}};
        let html=fixture.html.replace(/(<script id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,(_,a,b)=>a+JSON.stringify(data)+b);
        html=html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,(tag,attrs)=>{
          if(/application\/json/.test(attrs))return tag;
          const name=attrs.match(/src="[^"?]*\/([^/"?]+\.js)/)?.[1];
          return ['prescribed_audio_player.js','prescribed_lesson26_31_ui.js','prescribed_controls.js',
            'session13_prescribed_controls.js','session13_lesson29_activity3_bridge.js',
            'prescribed_leave_confirmation.js','prescribed_'+fixture.name+'.js'].includes(name)?tag:'';
        });
        return route.fulfill({contentType:'text/html',body:html});
      }
      if(url.pathname==='/progress/') {
        const body=route.request().postDataJSON();saves.push(body);
        if(holdSave && !body.reset)await new Promise(resolve=>{releaseSave=resolve;});
        if(saveFailure)return route.fulfill({status:503,json:{success:false,error:'Could not save your progress.'}});
        let accepted=true;
        if(body.reset){resets.push(body);Object.assign(state,{phase:index===0?'reading':index===1?'choosing':'sound',current_item:0,target_word:''});}
        if(body.action==='begin'&&!state.target_word)state.target_word=fixture.data.items[state.current_item].choices[0];
        if(body.action==='choose') {
          accepted=body.choice===state.target_word;
          if(accepted){state.current_item++;if(state.current_item===fixture.data.items.length)state.phase='complete';else state.target_word=fixture.data.items[state.current_item].choices[0];}
        }
        if(body.action==='oral_read')state.phase='letter';
        if(body.action==='letter_answer') {
          accepted=body.letter===fixture.data.items[state.current_item].answer;
          if(accepted){state.current_item++;state.phase='reading';}
        }
        if(body.action==='recorded')state.phase='recorded';
        if(body.action==='read_sound')state.phase='trace';
        if(body.action==='retry_sound')state.phase='sound';
        return route.fulfill({json:{success:true,accepted,progress:{state}}});
      }
      if(url.pathname==='/narrate/') {
        narrations.push(route.request().postData());
        if(holdNarration)await new Promise(resolve=>{releaseNarration=resolve;});
        return route.fulfill({json:{success:true,audio_content:'AA==',mime_type:'audio/mpeg'}}).catch(()=>{});
      }
      if(url.pathname==='/recording/') {
        uploads.push(route.request().postDataBuffer());
        if(holdUpload)await new Promise(resolve=>{releaseUpload=resolve;});
        return route.fulfill({json:{success:true}});
      }
      if(['/complete/','/submit/'].includes(url.pathname))return route.fulfill({json:{success:true}});
      if(url.pathname.startsWith('/static/')) {
        let file=path.join(app,decodeURIComponent(url.pathname.slice(1)));
        if(!fs.existsSync(file)&&/\.(png|jpg)$/.test(file))file=['.avif','.webp'].map(ext=>file.replace(/\.[^.]+$/,ext)).find(fs.existsSync)||file;
        if(fs.existsSync(file))return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.mp3')?'audio/mpeg':'application/octet-stream'});
      }
      return route.fulfill({status:404,body:''});
    });
    await page.goto('http://localhost:9876/activity/');
    const selector=suffix=>'#'+fixture.prefix+suffix;
    return {page,state,saves,uploads,narrations,resets,fixture,
      async start(){await page.click('#'+fixture.start+'-go');await page.waitForFunction(()=>window.audios.length&&window.audios.every(a=>a.paused));if(index===1)await page.waitForFunction(()=>!document.querySelector('#listen').disabled);},
      async pause(){await page.click(selector('-audio-settings-btn'));},
      async resume(backdrop=false){await page.evaluate(()=>window.holdAudio=false);if(backdrop)await page.locator(selector('-pause-modal')).click({position:{x:5,y:5}});else await page.click(selector('-resume'));},
      async restart(){await page.click(selector('-restart'));await page.click(selector('-restart-yes'));},
      holdSave(){holdSave=true;}, releaseSave(){holdSave=false;releaseSave?.();},
      holdNarration(){holdNarration=true;}, releaseNarration(){holdNarration=false;releaseNarration?.();},
      holdUpload(){holdUpload=true;}, releaseUpload(){holdUpload=false;releaseUpload?.();},
      failSave(value=true){saveFailure=value;},
      async finish(){assert.deepEqual(errors,[]);await page.close();checks++;},
    };
  }
  try {
    // Activity 1 keeps correctness/errors in diagnostics and audio only, as
    // requested; it must never show a status below the activity buttons.
    for(const viewport of [{width:1366,height:768},{width:390,height:844}]) {
      const h=await open(0,{},viewport);await h.start();
      await h.page.evaluate(()=>window.readError='Microphone access denied. Please allow microphone permission.');
      await h.page.click('#read');await h.page.waitForFunction(()=>document.querySelector('#prescribed-l28a1-debug-error')?.textContent.includes('Microphone access denied'));
      assert.equal(await h.page.locator('#app .status').count(),0);
      assert.match(await h.page.locator('#prescribed-l28a1-debug-error').textContent(),/Microphone access denied/);
      if(process.env.PABASA_SCREENSHOT_DIR){fs.mkdirSync(process.env.PABASA_SCREENSHOT_DIR,{recursive:true});await h.page.screenshot({path:path.join(process.env.PABASA_SCREENSHOT_DIR,`lesson28-error-${viewport.width}.png`)});}
      await h.page.evaluate(()=>window.readError='');await h.page.click('#read');await h.page.waitForSelector('#letter');
      await h.page.click('#check');assert.equal(await h.page.locator('#app .status').count(),0);
      await h.finish();
    }
    let h=await open(0);await h.start();
    await h.page.evaluate(()=>window.readError='<b>Provider unavailable</b>');await h.page.click('#read');
    await h.page.waitForFunction(()=>document.querySelector('#prescribed-l28a1-debug-error')?.textContent.includes('Provider unavailable'));
    assert.equal(await h.page.locator('#app .status').count(),0);
    await h.page.evaluate(()=>window.readError='');h.failSave();await h.page.click('#read');
    await h.page.waitForFunction(()=>document.querySelector('#prescribed-l28a1-debug-error')?.textContent.includes('Could not save'));
    await h.finish();

    // Intro completes before the target word starts, using the same media
    // element. Choices remain locked until both recordings have finished.
    h=await open(1);await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#lesson28a2-go');
    await h.page.waitForFunction(()=>window.playbacks.length===1);
    assert.match(decodeURIComponent(await h.page.evaluate(()=>window.playbacks[0].src)),/Word Identifying/);
    assert.equal(await h.page.locator('[data-choice]:enabled').count(),0);
    await h.page.evaluate(()=>window.audios[0].finish());
    await h.page.waitForFunction(()=>window.playbacks.length===2);
    const sequence=await h.page.evaluate(()=>window.playbacks);
    assert.match(sequence[1].src,/Sun\.mp3$/);assert.equal(sequence[0].id,sequence[1].id);
    assert.equal(await h.page.locator('[data-choice]:enabled').count(),0);
    await h.page.evaluate(()=>window.audios[0].finish());
    await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);await h.finish();

    h=await open(1);h.holdSave();await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#lesson28a2-go');
    await h.page.waitForFunction(()=>window.playbacks.length===1);await h.page.evaluate(()=>window.audios[0].finish());
    assert.equal(await h.page.evaluate(()=>window.playbacks.length),1);
    h.releaseSave();await h.page.waitForFunction(()=>window.playbacks.length===2);
    await h.page.evaluate(()=>window.audios[0].finish());
    await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);await h.finish();

    // Decode and play the real bundled MP3s in Chrome, not just fake ended
    // events: both clips must finish in order on the very same element.
    h=await open(1,{},undefined,true);
    try{await h.start();}catch(error){console.error(await h.page.evaluate(()=>({events:window.mediaEvents,playbacks:window.playbacks,status:document.querySelector('#status')?.textContent})));throw error;}
    const played=await h.page.evaluate(()=>({clips:window.playbacks,ended:window.audios[0].ended,time:window.audios[0].currentTime}));
    assert.equal(played.clips.length,2);assert.match(decodeURIComponent(played.clips[0].src),/Word Identifying/);
    assert.match(played.clips[1].src,/Sun\.mp3$/);assert.equal(played.clips[0].id,played.clips[1].id);
    assert.equal(played.ended,true);assert.ok(played.time>0);
    // Natural pause/ended events also occur after retry and correct feedback.
    // Exercise both answer paths using real MP3 playback, then all five rows.
    for(let index=0;index<5;index++) {
      const target=h.state.target_word;
      const wrong=h.fixture.data.items[index].choices.find(word=>word!==target);
      if(wrong) {
        const before=await h.page.evaluate(()=>window.playbacks.length);
        await h.page.click(`[data-choice="${wrong}"]`);
        await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);
        const retry=await h.page.evaluate(start=>window.playbacks.slice(start),before);
        assert.equal(retry.length,2);assert.match(decodeURIComponent(retry[0].src),/Hmm/);
        assert.equal(path.posix.basename(retry[1].src),target[0].toUpperCase()+target.slice(1)+'.mp3');
        assert.equal(retry[0].id,retry[1].id);assert.equal(h.state.current_item,index);
      }
      const before=await h.page.evaluate(()=>window.playbacks.length);
      await h.page.locator(`[data-choice="${target}"]`).first().click();
      if(index===4)await h.page.waitForSelector('.pabasa-completion-card');
      else await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);
      // Completion is displayed before its final feedback has finished.
      await h.page.waitForFunction(()=>window.audios.every(audio=>audio.paused));
      const correct=await h.page.evaluate(start=>window.playbacks.slice(start),before);
      assert.equal(correct.length,index===4?1:2);
      if(index<4){assert.match(decodeURIComponent(correct[0].src),/That/);assert.equal(correct[0].id,correct[1].id);}
      assert.equal(h.state.current_item,index+1);
    }
    await h.finish();

    // Either word can be the saved target; a wrong answer must replay the
    // server's target, not the selected word or the first displayed choice.
    h=await open(1,{target_word:'sit'});await h.start();
    await h.page.click('[data-choice="sun"]');await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);
    assert.match(await h.page.evaluate(()=>window.playbacks.at(-1).src),/Sit\.mp3$/);
    assert.equal(h.state.current_item,0);
    await h.page.click('[data-choice="sit"]');await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);
    assert.match(await h.page.evaluate(()=>window.playbacks.at(-1).src),/Set\.mp3$/);assert.equal(h.state.current_item,1);await h.finish();

    // Both Pause exits restore Lesson 28 input, including repeated playback.
    for(const index of [0,1])for(const backdrop of [false,true]) {
      h=await open(index);await h.start();
      for(let repeat=0;repeat<2;repeat++) {
        if(index===1){await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#listen');await h.page.waitForFunction(()=>window.audios.some(a=>!a.paused));}
        await h.pause();await h.resume(backdrop);
        if(index===1)await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);
        else {await h.page.click('#read');await h.page.waitForSelector('#letter');break;}
      }
      if(index===1){assert.equal(await h.page.locator('[data-choice]:enabled').count(),2);assert.equal(h.state.current_item,0);}
      await h.finish();
    }
    // Cancelling the intro still prepares and speaks the first target on resume.
    h=await open(1);await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#lesson28a2-go');
    await h.page.waitForFunction(()=>window.audios.some(a=>!a.paused));await h.pause();await h.resume();
    await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);assert.equal(h.state.target_word,'sun');await h.finish();

    // Feedback cancellation must not consume the next answer or erase a save.
    h=await open(1);await h.start();await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('[data-choice="sun"]');
    await h.page.waitForFunction(()=>window.audios.some(a=>!a.paused));await h.pause();await h.resume(true);
    await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);assert.equal(h.state.current_item,1);assert.equal(h.saves.filter(s=>s.action==='choose').length,1);await h.finish();

    h=await open(1);await h.start();h.holdSave();await h.page.click('[data-choice="sun"]');
    await h.pause();await h.resume();assert.equal(await h.page.isDisabled('#listen'),true);
    h.releaseSave();await h.page.waitForFunction(()=>!document.querySelector('#listen').disabled);assert.equal(h.state.current_item,1);await h.finish();

    // Restart waits for a previously sent answer, then resets exactly once.
    h=await open(1);await h.start();h.holdSave();await h.page.click('[data-choice="sun"]');await h.pause();await h.restart();
    assert.equal(h.resets.length,0);const reloaded=h.page.waitForEvent('domcontentloaded');h.releaseSave();await reloaded;
    assert.equal(h.resets.length,1);assert.equal(h.state.current_item,0);await h.finish();

    h=await open(1);await h.start();await h.page.evaluate(()=>window.failAudio=true);await h.page.click('#listen');
    await h.page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('Audio playback failed'));
    assert.equal(await h.page.isEnabled('#listen'),true);await h.finish();

    // Trace & Say recovers playback, capture and the original saved phase.
    for(const backdrop of [false,true]) {
      h=await open(2);await h.start();await h.page.evaluate(()=>window.holdAudio=true);await h.page.click('#listen');
      await h.page.waitForFunction(()=>window.audios.some(a=>!a.paused));await h.pause();await h.resume(backdrop);
      await h.page.click('#record');await h.page.waitForSelector('#proceed');assert.equal(h.uploads.length,1);
      await h.page.click('#proceed');await h.page.waitForSelector('#trace-board');assert.equal(h.state.phase,'trace');await h.finish();
    }
    h=await open(2);await h.start();h.holdNarration();await h.page.click('#listen');await h.pause();await h.resume();
    const count=await h.page.evaluate(()=>window.audios.length);h.releaseNarration();
    await h.page.click('#record');await h.page.waitForSelector('#proceed');
    assert.equal(await h.page.evaluate(()=>window.audios.filter(a=>a.src?.startsWith('data:')).length),1);
    assert.ok(count>=1);await h.finish();

    h=await open(2);await h.start();await h.page.evaluate(()=>window.capturePending=true);await h.page.click('#record');
    await h.page.waitForFunction(()=>window.captureCalls===1);await h.pause();await h.resume();
    assert.equal(h.uploads.length,0);assert.equal(await h.page.evaluate(()=>window.testStreams[0].getTracks()[0].stopped),true);
    await h.page.evaluate(()=>window.capturePending=false);await h.page.click('#record');await h.page.waitForSelector('#proceed');await h.finish();

    for(const interruption of ['mute','help']) {
      h=await open(2);await h.start();await h.page.evaluate(()=>window.capturePending=true);await h.page.click('#record');
      await h.page.waitForFunction(()=>window.captureCalls===1);
      await h.page.click('#prescribed-s13l29g3-'+(interruption==='mute'?'mic-toggle':'help-btn'));
      await h.page.waitForFunction(()=>window.testStreams[0].getTracks()[0].stopped);
      assert.equal(h.uploads.length,0);
      if(interruption==='mute') {
        await h.page.click('#record');assert.equal(await h.page.evaluate(()=>window.captureCalls),1);
        await h.page.click('#prescribed-s13l29g3-mic-toggle');
      } else await h.page.click('#prescribed-s13l29g3-help-close');
      await h.page.evaluate(()=>window.capturePending=false);await h.page.click('#record');await h.page.waitForSelector('#proceed');await h.finish();
    }

    // Escape dismisses Help through the same resume lifecycle as its close
    // button, whether the activity was idle or recording when Help opened.
    for(const capturing of [false,true]) {
      h=await open(2);await h.start();
      if(capturing){await h.page.evaluate(()=>window.capturePending=true);await h.page.click('#record');await h.page.waitForFunction(()=>window.captureCalls===1);}
      await h.page.click('#prescribed-s13l29g3-help-btn');await h.page.keyboard.press('Escape');
      assert.equal(await h.page.isHidden('#prescribed-s13l29g3-help-modal'),true);
      await h.page.evaluate(()=>window.capturePending=false);await h.page.click('#record');await h.page.waitForSelector('#proceed');
      assert.equal(h.uploads.length,1);assert.equal(await h.page.evaluate(()=>window.captureCalls),capturing?2:1);await h.finish();
    }

    // Once capture has finished, mute affects future captures. The upload and
    // recorded phase must still finish without requiring Pause -> Resume.
    for(const keepMuted of [false,true]) {
      h=await open(2);await h.start();h.holdUpload();
      const upload=h.page.waitForRequest(request=>request.url().endsWith('/recording/'));
      await h.page.click('#record');await upload;
      await h.page.click('#prescribed-s13l29g3-mic-toggle');
      if(!keepMuted)await h.page.click('#prescribed-s13l29g3-mic-toggle');
      h.releaseUpload();await h.page.waitForSelector('#proceed');assert.equal(h.uploads.length,1);
      if(keepMuted)await h.page.click('#prescribed-s13l29g3-mic-toggle');
      await h.page.click('#retry');await h.page.waitForSelector('#record');
      await h.page.click('#record');await h.page.waitForSelector('#proceed');
      assert.equal(h.uploads.length,2);assert.equal(await h.page.evaluate(()=>window.captureCalls),2);await h.finish();
    }

    h=await open(2);await h.start();h.holdUpload();h.failSave();
    const failedUpload=h.page.waitForRequest(request=>request.url().endsWith('/recording/'));
    await h.page.click('#record');await failedUpload;await h.page.click('#prescribed-s13l29g3-mic-toggle');h.releaseUpload();
    await h.page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('Could not save'));
    await h.page.click('#prescribed-s13l29g3-mic-toggle');h.failSave(false);
    await h.page.click('#record');await h.page.waitForSelector('#proceed');await h.finish();

    // Pausing preserves unsaved tracing; resuming does not reset its canvas.
    h=await open(2,{phase:'trace'});await h.start();
    const canvas=await h.page.locator('#trace-board').boundingBox();
    for(const fraction of [.25,.75]) {
      await h.page.mouse.move(canvas.x+canvas.width*fraction,canvas.y+canvas.height*.2);
      await h.page.mouse.down();await h.page.mouse.move(canvas.x+canvas.width*fraction,canvas.y+canvas.height*.8,{steps:5});await h.page.mouse.up();
    }
    assert.equal(await h.page.isEnabled('#submit'),true);await h.pause();await h.resume(true);
    await h.page.waitForFunction(()=>document.querySelector('#trace-count').textContent==='2 of 2 letters complete');
    assert.equal(await h.page.isEnabled('#submit'),true);await h.finish();

    h=await open(2);await h.start();await h.page.evaluate(()=>window.permissionPending=true);await h.page.click('#record');
    await h.page.waitForFunction(()=>Boolean(window.resolvePermission));await h.pause();await h.resume();
    await h.page.evaluate(()=>{window.permissionPending=false;window.resolvePermission();});
    await h.page.waitForFunction(()=>window.testStreams[0]?.getTracks()[0].stopped);assert.equal(h.uploads.length,0);
    await h.page.click('#record');await h.page.waitForSelector('#proceed');await h.finish();

    h=await open(2);await h.start();h.holdUpload();await h.page.click('#record');
    await h.page.waitForFunction(()=>window.captureCalls===1);await h.pause();await h.restart();assert.equal(h.resets.length,0);
    const reload=h.page.waitForEvent('domcontentloaded');h.releaseUpload();await reload;
    assert.equal(h.resets.length,1);assert.equal(h.state.phase,'sound');assert.equal(h.saves.filter(s=>s.action==='recorded').length,1);await h.finish();

    // Shared backdrop handling returns Restart to Pause; it never strands the
    // activity behind an invisible paused flag.
    h=await open(0);await h.start();await h.pause();await h.page.click('#prescribed-l28a1-restart');
    await h.page.locator('#prescribed-l28a1-restart-modal').click({position:{x:5,y:5}});
    assert.equal(await h.page.isVisible('#prescribed-l28a1-pause-modal'),true);await h.resume();await h.finish();
    for(const index of [1,2]) {
      h=await open(index);await h.start();await h.pause();
      const restored=h.page.waitForEvent('domcontentloaded');
      await h.page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
      await restored;assert.equal(await h.page.isVisible('#'+h.fixture.start+'-start'),true);await h.finish();
    }
    console.log(`PASS: ${checks} Lesson 28/29 error, viewport, pause, cancellation, delayed-save and restart scenarios.`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
