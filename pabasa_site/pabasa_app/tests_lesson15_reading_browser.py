"""Real browser UI/endpoints in a disposable DB; capture and STT are simulated."""
import base64
import io
import json
import math
import os
import struct
import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from . import tests_lesson15_reading as fixtures


class Lesson15ReadingBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for
    current = fixtures.Lesson15ReadingTests.current

    def test_student_and_teacher_ui(self):
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as recording:
            recording.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            recording.writeframes(b''.join(struct.pack('<h', int(1500 * math.sin(n * 2 * math.pi * 220 / 16000))) for n in range(32000)))
        environment = dict(os.environ, L15_SERVER=self.live_server_url,
            L15_STUDENT_COOKIE=self.student_client.cookies['sessionid'].value,
            L15_TEACHER_COOKIE=self.teacher_client.cookies['sessionid'].value,
            L15_STUDENT_ID=str(self.student.pk), L15_AUDIO=base64.b64encode(audio.getvalue()).decode())
        script = r"""
const assert = require('node:assert/strict');
const {chromium} = require('C:/Users/Prince/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
 const base=process.env.L15_SERVER, url=base+'/dashboard/assessment/activity/prescribed/lesson-15-gawain-3/';
 const student=await browser.newContext(), teacher=await browser.newContext();
 for(const [context,cookie] of [[student,process.env.L15_STUDENT_COOKIE],[teacher,process.env.L15_TEACHER_COOKIE]])await context.addCookies([{name:'sessionid',value:cookie,url:base}]);
 await student.addInitScript(()=>{const NativeAudio=window.Audio;window.__l15PlayedAudios=[];window.Audio=class extends EventTarget{constructor(src){super();if(window.__realSkipFeedback&&src.includes('ayos_lang_subukan_natin_ang_susunod.mp3')){const audio=new NativeAudio(src);window.__l15FeedbackAudio=audio;return audio;}this.src=src;this.currentTime=0;this.paused=true;}play(){this.paused=false;window.__l15PlayedAudios.push(this.src);const finish=()=>{if(this.paused)return;this.paused=true;this.onended?.();this.dispatchEvent(new Event('ended'));};if(window.__holdSkipFeedback&&this.src.includes('ayos_lang_subukan_natin_ang_susunod.mp3'))window.__finishSkipFeedback=finish;else setTimeout(finish,window.__l15AudioDelay||50);return Promise.resolve();}pause(){this.paused=true;}};});
 const page=await student.newPage(), errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(url);
 assert.equal(await page.locator('#skip').isDisabled(),true);
 await page.evaluate(()=>window.__l15AudioDelay=750);
 await page.locator('#gawain4-start-button').click();
 assert.equal(await page.locator('#skip').isDisabled(),true);
 await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 await page.evaluate(()=>window.__l15AudioDelay=50);
 // Skip-only presentation: real icon font, centered group, desktop/mobile layout.
 await page.evaluate(()=>document.fonts.load('16px bootstrap-icons'));
 for(const viewport of [{width:1920,height:1080},{width:1366,height:768},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  const layout=await page.locator('#skip').evaluate(button=>{
   const icon=button.querySelector('i'),label=button.querySelector('span'),b=button.getBoundingClientRect(),i=icon.getBoundingClientRect(),s=label.getBoundingClientRect(),css=getComputedStyle(button);
   return {font:document.fonts.check('16px bootstrap-icons'),glyph:getComputedStyle(icon,'::before').content,
    gap:s.left-i.right,horizontal:Math.abs((i.left+s.right)/2-(b.left+b.right)/2),
    vertical:Math.abs((i.top+i.bottom)/2-(s.top+s.bottom)/2),whiteSpace:css.whiteSpace,
    fits:b.left>=0&&b.right<=innerWidth,cursor:css.cursor,transition:css.transitionDuration};
  });
  assert.ok(layout.font&&layout.glyph!=='none'&&layout.glyph!=='normal');
  assert.ok(Math.abs(layout.gap-9)<1&&layout.horizontal<1&&layout.vertical<1);
  assert.equal(layout.whiteSpace,'nowrap');assert.ok(layout.fits);assert.equal(layout.cursor,'pointer');
  assert.ok(layout.transition.split(',').every(value=>value.trim()==='0.2s'));
 }
 await page.setViewportSize({width:1366,height:768});
 await page.locator('#skip').hover();
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('#skip')).transform==='matrix(1, 0, 0, 1, 0, -2)');
 const hovered=await page.locator('#skip').evaluate(button=>({background:getComputedStyle(button).backgroundColor,border:getComputedStyle(button).borderColor,shadow:getComputedStyle(button).boxShadow}));
 assert.equal(hovered.background,'rgb(225, 243, 239)');assert.equal(hovered.border,'rgb(88, 185, 178)');assert.notEqual(hovered.shadow,'none');
 await page.mouse.down();
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('#skip')).transform==='matrix(0.98, 0, 0, 0.98, 0, 1)');
 await page.mouse.move(0,0);await page.mouse.up();
 assert.equal(await page.locator('#g15-skip-modal').count(),0);
 await page.mouse.move(0,0);await page.keyboard.press('Tab');await page.locator('#skip').focus();
 assert.equal(await page.locator('#skip').evaluate(button=>button.matches(':focus-visible')),true);
 assert.equal(await page.locator('#skip').evaluate(button=>getComputedStyle(button).outlineStyle),'solid');
 await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#skip').hover();
 assert.equal(await page.locator('#skip').evaluate(button=>getComputedStyle(button).transform),'none');
 await page.emulateMedia({reducedMotion:'no-preference'});await page.mouse.move(0,0);
 // A genuinely disabled button cannot animate or open confirmation.
 await page.evaluate(()=>window.__l15AudioDelay=750);await page.locator('#listen').click();
 assert.equal(await page.locator('#skip').isDisabled(),true);await page.locator('#skip').hover();
 const disabled=await page.locator('#skip').evaluate(button=>{const css=getComputedStyle(button);return{background:css.backgroundColor,border:css.borderColor,color:css.color,icon:getComputedStyle(button.querySelector('i')).color,transform:css.transform,shadow:css.boxShadow,cursor:css.cursor};});
 assert.deepEqual(disabled,{background:'rgb(217, 223, 224)',border:'rgb(181, 191, 194)',color:'rgb(112, 123, 128)',icon:'rgb(112, 123, 128)',transform:'none',shadow:'none',cursor:'not-allowed'});
 await page.mouse.down();await page.mouse.up();assert.equal(await page.locator('#g15-skip-modal').count(),0);
 await page.waitForFunction(()=>!document.querySelector('#skip').disabled);await page.evaluate(()=>window.__l15AudioDelay=50);
 for(const state of ['listening','processing']){
  await page.evaluate(state=>window.dispatchEvent(new CustomEvent('basahin:state',{detail:{state}})),state);
  assert.equal(await page.locator('#skip').isDisabled(),true);
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('basahin:state',{detail:{state:'idle'}})));
 }
 let releaseSave,arrived;const arrival=new Promise(resolve=>arrived=resolve);
 const progressUrl=await page.evaluate(()=>JSON.parse(document.getElementById('gawain3-data').textContent).progress_url);
 await page.route(base+progressUrl,async route=>{await new Promise(resolve=>{releaseSave=resolve;arrived();});await route.continue();});
 await page.evaluate(()=>{window.__skipPendingSave=window.__session5LeaveAdapter.saveCurrentProgress();});
 await arrival;assert.equal(await page.locator('#skip').isDisabled(),true);releaseSave();
 await page.evaluate(()=>window.__skipPendingSave);await page.unroute(base+progressUrl);
 await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 console.log('PASS skip UI: icon, 9px centered gap, desktop/laptop/mobile alignment, hover, press, keyboard focus, reduced motion, disabled audio/recording/processing/pending-save states');
 const inventory=await page.evaluate(()=>JSON.parse(document.getElementById('gawain3-data').textContent).items);
 assert.equal(inventory.length,22);
 // Only capture is replaced. The production transcribe/save endpoint is used.
 await page.evaluate(encoded=>{const original=window.Basahin;window.Basahin={...original,read:async(fields,options)=>{
   if(window.__l15CaptureError)throw Object.assign(new Error('No speech'),{name:window.__l15CaptureError});
   const bytes=Uint8Array.from(atob(encoded),x=>x.charCodeAt(0));
   return original.transcribe(new Blob([bytes],{type:'audio/wav'}),fields,{url:options.url});
 }};},process.env.L15_AUDIO);
 await page.evaluate(()=>window.__l15CaptureError='NoSpeechError');
 await page.locator('#read').click();await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 assert.equal(await page.locator('.item').getAttribute('data-index'),'0');
 await page.evaluate(()=>window.__l15CaptureError='CaptureLimitError');
 await page.locator('#read').click();await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 await page.evaluate(()=>window.__l15CaptureError=null);
 await page.locator('#read').click();await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 assert.equal(await page.locator('.item').getAttribute('data-index'),'0');
 for(let index=1;index<=3;index++){
  await page.locator('#read').click();await page.waitForFunction(i=>document.querySelector('.item')?.dataset.index===String(i),index);
  await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 }
 // Failed save: no audio or advancement, inline error and retryable controls.
 const skipUrl=await page.evaluate(()=>JSON.parse(document.getElementById('gawain3-data').textContent).skip_url);
 await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
 const beforeFailureAudio=await page.evaluate(()=>window.__l15PlayedAudios.length);
 await page.route(base+skipUrl,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({success:false,error:'Hindi na-save ang paglaktaw. Subukan muli.'})}));
 await page.locator('#skip').click();
 await page.waitForFunction(()=>!document.querySelector('#skip').disabled&&document.querySelector('#status').textContent.includes('Hindi na-save'));
 assert.equal(await page.locator('.item').getAttribute('data-index'),'3');
 assert.equal(await page.evaluate(()=>window.__l15PlayedAudios.length),beforeFailureAudio);
 assert.equal(await page.locator('#read').isDisabled(),false);assert.equal(await page.locator('#listen').isDisabled(),false);
 await page.unroute(base+skipUrl);
 // Hold the real save request, then hold the feedback's ended event.
 let releaseSkip,skipArrived;const skipArrival=new Promise(resolve=>skipArrived=resolve);let skipRequests=0;
 page.on('request',request=>{if(request.url()===base+skipUrl)skipRequests++;});
 await page.route(base+skipUrl,async route=>{await new Promise(resolve=>{releaseSkip=resolve;skipArrived();});await route.continue();});
 await page.evaluate(()=>{window.__holdSkipFeedback=true;const button=document.querySelector('#skip');button.click();button.click();});
 await skipArrival;assert.equal(skipRequests,1);assert.equal(await page.locator('.item').getAttribute('data-index'),'3');
 for(const selector of ['#skip','#read','#listen'])assert.equal(await page.locator(selector).isDisabled(),true);
 assert.equal(await page.evaluate(()=>window.__l15PlayedAudios.length),beforeFailureAudio);
 assert.equal(await page.locator('#g15-skip-modal').count(),0);
 releaseSkip();await page.waitForFunction(()=>typeof window.__finishSkipFeedback==='function');
 assert.equal(await page.locator('.item').getAttribute('data-index'),'3');
 for(const selector of ['#skip','#read','#listen'])assert.equal(await page.locator(selector).isDisabled(),true);
 assert.equal(await page.evaluate(()=>window.__l15PlayedAudios.at(-1).endsWith('ayos_lang_subukan_natin_ang_susunod.mp3')),true);
 const persistedSkip=await teacher.request.get(base+'/api/teacher/lesson-15-gawain-3/reviews/?student_id='+process.env.L15_STUDENT_ID);
 const skippedRow=(await persistedSkip.json()).items[3];
 assert.equal(skippedRow.classification,'RED');assert.equal(skippedRow.classification_source,'skipped');assert.equal(skippedRow.status,'not_read');
 await page.evaluate(()=>{window.__holdSkipFeedback=false;window.__finishSkipFeedback();delete window.__finishSkipFeedback;});
 await page.waitForFunction(()=>document.querySelector('.item')?.dataset.index==='4');
 await page.unroute(base+skipUrl);assert.equal(skipRequests,1);
 await page.reload();await page.locator('#gawain4-start-button').click();
 assert.equal(await page.locator('.item').getAttribute('data-index'),'4');
 // Help X/ack, Pause continue, restart cancel, and return to Django URL.
 const prefix='#prescribed-s5l15g3';
 await page.locator(prefix+'-help-btn').click();await page.locator(prefix+'-help-close').click();
 await page.locator(prefix+'-help-btn').click();await page.locator(prefix+'-help-ack').click();
 await page.locator(prefix+'-audio-settings-btn').click();await page.locator(prefix+'-resume').click();
 await page.locator(prefix+'-audio-settings-btn').click();await page.locator(prefix+'-restart').click();await page.locator(prefix+'-restart-no').click();
 await page.locator(prefix+'-back').click();await page.locator(prefix+'-leave-yes').click();
 await page.waitForURL('**/dashboard/assessment/');
 await page.goto(url);await page.locator('#gawain4-start-button').click();
 assert.equal(await page.locator('.item').getAttribute('data-index'),'4');
 // Exercise the same teacher table component used by Course/Student Progress.
 const review=await teacher.newPage();await review.goto(base+'/api/teacher/lesson-15-gawain-3/reviews/?student_id='+process.env.L15_STUDENT_ID);
 await teacher.addCookies([{name:'csrftoken',value:'a'.repeat(32),url:base}]);
 const data=await review.evaluate(()=>JSON.parse(document.body.textContent));assert.equal(data.pending,3);
 await review.setContent('<main id="review"></main>');
 await review.addScriptTag({url:base+'/static/pabasa_app/js/lesson15_reading_review.js'});
 await review.evaluate(({data,studentId,base})=>{const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));document.getElementById('review').innerHTML=window.Lesson15ReadingReview.render(data.items,studentId,escape,base+'/api/teacher/lesson-15-gawain-3/classify/');},{data,studentId:process.env.L15_STUDENT_ID,base});
 const player=review.locator('audio').first();await player.evaluate(audio=>audio.play());
 await review.waitForFunction(()=>document.querySelector('audio').currentTime>0);
 for(const [index,grade] of ['GREEN','YELLOW','RED'].entries()){
  await review.locator(`[data-item-index="${index}"] select`).selectOption(grade);
  await review.waitForFunction(i=>!document.querySelector(`[data-item-index="${i}"] select`).disabled,index);
  assert.ok((await review.locator('.session5-evaluation-summary strong').textContent()).includes(`${index+2} / 22`),await review.locator('.lesson15-review-feedback').textContent());
 }
 assert.equal(await review.locator('[data-item-index="3"] select').count(),0);
 const refreshed=await teacher.request.get(base+'/api/teacher/lesson-15-gawain-3/reviews/?student_id='+process.env.L15_STUDENT_ID);
 const results=await refreshed.json();assert.deepEqual(results.items.slice(0,3).map(item=>item.classification),['GREEN','YELLOW','RED']);assert.equal(results.items[3].classification_source,'skipped');
 // Direct skips; the final item uses the actual existing MP3 in Chrome.
 for(let index=4;index<22;index++){
  await page.waitForFunction(()=>!document.querySelector('#skip').disabled);
  if(index===21)await page.evaluate(()=>window.__realSkipFeedback=true);
  await page.locator('#skip').click();
  if(index<21)await page.waitForFunction(i=>document.querySelector('.item')?.dataset.index===String(i),index+1);
 }
 await page.waitForFunction(()=>window.__l15FeedbackAudio?.currentTime>0&&!window.__l15FeedbackAudio.paused);
 assert.equal(await page.locator('.item').getAttribute('data-index'),'21');assert.equal(await page.locator('.completion').count(),0);
 for(const selector of ['#skip','#read','#listen'])assert.equal(await page.locator(selector).isDisabled(),true);
 await page.locator('.completion').waitFor();assert.equal(await page.locator('.session5-controls-tools').isVisible(),false);
 assert.equal(await page.evaluate(()=>window.__l15FeedbackAudio.ended),true);
 await page.reload();await page.locator('.completion').waitFor();
 assert.deepEqual(errors,[]);
 console.log('PASS browser: direct skip, save-before-audio, ended-before-advance/final completion, failure retry, double-click protection, RED after refresh/read-only teacher display; simulated STT, teacher saves/totals/audio, Help/Pause/return/reopen unchanged; no page errors');
 } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
"""
        with patch('pabasa_app.views._dashboard_context', return_value={}), patch(
                'pabasa_app.views.transcribe_audio_bytes_with_model',
                side_effect=[('mali', 'chirp_3', ''), ('tawa', 'chirp_3', ''),
                             ('sawa', 'chirp_3', ''), ('lawa', 'chirp_3', '')]):
            result = subprocess.run(['node', '-e', script], env=environment, capture_output=True, text=True, timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.current().activity_completed)
        print(result.stdout.strip())
