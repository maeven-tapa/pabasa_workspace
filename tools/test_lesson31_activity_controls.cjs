// Local fixtures use real templates/activity controls; no accounts or providers.
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
for number,name in [(1,'circle_right_word'),(4,'say_circle')]:
 key=f'lesson-31-gawain-{number}';activity=prescribed_activity(key)
 data={**activity,'progress':{'state':{}},'progress_url':'/progress/','completion_url':'/complete/','transcribe_url':'/transcribe/','read_aloud_url':'/narrate/'}
 data['items']=[{**item,'image_url':static(item['image_path']) if item.get('image_path') else ''} for item in activity['items']]
 fixtures.append({'number':number,'key':key,'data':data,'html':render_to_string(f'pabasa_app/prescribed_{name}_lesson31_activity{number}_page.html',{'prescribed_activity_data':data})})
print(json.dumps(fixtures))
`], {cwd:root, encoding:'utf8', maxBuffer:2*1024*1024});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checked = 0;
  async function open(fixture, startState={}) {
    const page = await browser.newPage(), errors = [], saves = [], narrations = [], completions = [], alerts = [];
    let releaseNarration, holdNarration = false, releaseSave, holdSave = false, holdCompletion = false;
    const completionReleases=[];
    let resetFailure = null, answerFailure = false;
    const state = {phase:fixture.number === 1 ? 'reading_choices' : 'reading', current_item:0, choice_index:0, attempts:3, ...startState};
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', async dialog => {alerts.push(dialog.message()); await dialog.dismiss();});
    await page.addInitScript(() => {
      window.captureCalls = 0; window.cancelCalls = 0; window.readFields = []; window.playbacks = [];
      window.holdAudio = false; window.ignoreCancel = false; window.autoSpeech = false;
      let rejectSpeech;
      window.Basahin = {
        bindActivity(button, action) {button?.addEventListener('click', action);},
        cancelAll() {window.cancelCalls++; if (!window.ignoreCancel) rejectSpeech?.(new DOMException('Cancelled', 'AbortError'));},
        read(fields) {
          window.captureCalls++; window.readFields.push(fields);
          if (window.autoSpeech) return Promise.resolve({raw_transcript:fields.target_text, complete:true});
          return new Promise((resolve, reject) => {window.completeSpeech=resolve; rejectSpeech=reject;});
        }
      };
      navigator.mediaDevices.getUserMedia = async () => {throw Error('Physical microphone is not used by this test');};
      window.Audio = class extends EventTarget {
        constructor() {super(); this.paused=true; window.playbacks.push(this);}
        play() {
          this.paused=false;
          if (!window.holdAudio) queueMicrotask(() => {if (!this.paused) {this.paused=true; this.onended?.(); this.dispatchEvent(new Event('ended'));}});
          return Promise.resolve();
        }
        pause() {if (!this.paused) {this.paused=true; this.dispatchEvent(new Event('pause'));}}
      };
    });
    await page.route('http://localhost:9876/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/activity/') {
        const data = {...fixture.data, progress:{state}};
        let html = fixture.html.replace(/(<script id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/, (_, start, end) => start+JSON.stringify(data)+end);
        html = html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi, (tag, attrs) => {
          if (/application\/json/.test(attrs)) return tag;
          return /prescribed_lesson26_31_ui\.js|prescribed_controls\.js|session15_prescribed_controls\.js|prescribed_circle_right_word_lesson31_activity1\.js|prescribed_say_circle_lesson31_activity4\.js/.test(attrs) ? tag : '';
        });
        return route.fulfill({contentType:'text/html', body:html});
      }
      if (url.pathname === '/narrate/') {
        narrations.push(new URLSearchParams(route.request().postData()).get('target_text'));
        if (holdNarration) await new Promise(resolve => {releaseNarration=resolve;});
        return route.fulfill({json:{success:true, audio_content:'AA==', mime_type:'audio/mpeg'}}).catch(() => {});
      }
      if (url.pathname === '/progress/') {
        const body = route.request().postDataJSON(); saves.push(body);
        if (holdSave) await new Promise(resolve => {releaseSave=resolve;});
        if (body.reset) {
          if (resetFailure === 'lost') {
            Object.assign(state, {phase:fixture.number === 1 ? 'reading_choices' : 'reading', current_item:0, choice_index:0, attempts:0});
            return route.abort('failed');
          }
          if (resetFailure === 'network') return route.abort('failed');
          if (resetFailure === 'http') return route.fulfill({status:503, json:{success:false, error:'Temporary reset failure'}});
          if (resetFailure === 'rejected') return route.fulfill({json:{success:false, error:'Reset rejected'}});
          if (resetFailure === 'malformed') return route.fulfill({contentType:'text/html', body:'Service unavailable'});
          Object.assign(state, {phase:fixture.number === 1 ? 'reading_choices' : 'reading', current_item:0, choice_index:0, attempts:3});
        }
        if (body.action && answerFailure) return route.abort('failed');
        if (body.action === 'read_choice') {state.choice_index++; state.phase=state.choice_index === 3 ? 'choosing' : 'reading_choices';}
        if (body.action === 'read_word') state.phase='choosing';
        if (body.action === 'choose') {state.current_item++; state.choice_index=0; state.phase=state.current_item===fixture.data.items.length ? 'complete' : fixture.number === 1 ? 'reading_choices' : 'reading';}
        return route.fulfill({json:{success:true, accepted:true, progress:{state}}});
      }
      if (url.pathname === '/complete/') {
        completions.push(route.request().postDataJSON());
        if (holdCompletion) await new Promise(resolve => {completionReleases.push(resolve);});
        return route.fulfill({json:{success:true}}).catch(() => {});
      }
      if (url.pathname.startsWith('/static/')) {
        const file=path.join(app, decodeURIComponent(url.pathname.slice(1)));
        if (fs.existsSync(file)) return route.fulfill({body:fs.readFileSync(file), contentType:file.endsWith('.js') ? 'text/javascript' : 'application/octet-stream'});
      }
      return route.fulfill({status:404, body:''});
    });
    await page.goto('http://localhost:9876/activity/');
    const prefix='lesson31a'+fixture.number;
    await page.click('#'+prefix+'-go');
    await page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio => audio.paused) && !document.querySelector('#read')?.disabled);
    return {page, prefix, errors, saves, state, narrations, completions, alerts,
      failReset(kind) {resetFailure=kind;},
      failAnswer() {answerFailure=true;},
      holdNarration() {holdNarration=true;},
      holdSave() {holdSave=true;},
      holdCompletion() {holdCompletion=true;},
      releaseCompletion() {holdCompletion=false; completionReleases.splice(0).forEach(resolve => resolve());},
      async releaseSave() {await page.waitForTimeout(20); holdSave=false; releaseSave?.();},
      async releaseNarration() {await page.waitForTimeout(20); releaseNarration?.();},
      async pause() {await page.click('#'+prefix+'-audio-settings-btn');},
      async resume() {await page.click('#'+prefix+'-resume');},
      async finish() {assert.deepEqual(errors, []); await page.close(); checked++;}
    };
  }
  try {
    for (const fixture of fixtures) {
      // Toolbar actions cancel shared speech once, while direct lifecycle
      // events still perform their own cancellation when no toolbar handles it.
      let cancellation=await open(fixture);
      for (const action of ['pause', 'mute', 'help']) {
        await cancellation.page.evaluate(() => window.cancelCalls=0);
        if (action==='pause') await cancellation.pause();
        if (action==='mute') await cancellation.page.click('#'+cancellation.prefix+'-mic-toggle');
        if (action==='help') await cancellation.page.click('#'+cancellation.prefix+'-help-btn');
        assert.equal(await cancellation.page.evaluate(() => window.cancelCalls), 1, action+' must cancel speech once');
        if (action==='pause') await cancellation.resume();
        if (action==='mute') await cancellation.page.click('#'+cancellation.prefix+'-mic-toggle');
        if (action==='help') await cancellation.page.click('#'+cancellation.prefix+'-help-close');
      }
      await cancellation.page.evaluate(prefix => {
        window.cancelCalls=0;
        window.dispatchEvent(new CustomEvent('session15-'+prefix+'-pause'));
      }, cancellation.prefix);
      assert.equal(await cancellation.page.evaluate(() => window.cancelCalls), 1);
      await cancellation.page.evaluate(prefix => window.dispatchEvent(new Event('session15-'+prefix+'-resume')), cancellation.prefix);
      await cancellation.pause(); await cancellation.page.click('#'+cancellation.prefix+'-restart');
      cancellation.holdSave();
      await cancellation.page.evaluate(() => window.cancelCalls=0);
      await cancellation.page.click('#'+cancellation.prefix+'-restart-yes');
      assert.equal(await cancellation.page.evaluate(() => window.cancelCalls), 1, 'Restart must cancel speech once');
      const resetDone=cancellation.page.waitForEvent('domcontentloaded');
      await cancellation.releaseSave(); await resetDone;
      await cancellation.finish();

      // Muting blocks capture; unmuting restores it without advancing progress.
      let h=await open(fixture);
      await h.page.click('#'+h.prefix+'-mic-toggle'); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 0); assert.equal(h.saves.length, 0);
      await h.page.click('#'+h.prefix+'-mic-toggle'); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      await h.finish();

      // Active narration stops; resume makes both Read and Listen operational.
      h=await open(fixture); await h.page.evaluate(() => window.holdAudio=true); await h.page.click('#listen');
      await h.page.waitForFunction(() => window.playbacks.some(audio => !audio.paused)); await h.pause();
      assert.equal(await h.page.evaluate(() => window.playbacks.every(audio => audio.paused)), true);
      await h.resume(); assert.equal(await h.page.isEnabled('#read'), true);
      await h.page.evaluate(() => window.holdAudio=false); await h.page.click('#listen');
      await h.page.waitForFunction(() => !document.querySelector('#read').disabled);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      await h.finish();

      // The existing backdrop dismissal also resumes the activity.
      h=await open(fixture); await h.pause();
      await h.page.locator('#'+h.prefix+'-pause-modal').click({position:{x:5,y:5}});
      assert.equal(await h.page.isVisible('#'+h.prefix+'-pause-modal'), false);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      await h.finish();

      // Escaping a restart confirmation returns to Pause, allowing Resume.
      h=await open(fixture); await h.pause(); await h.page.click('#'+h.prefix+'-restart');
      await h.page.keyboard.press('Escape');
      assert.equal(await h.page.isVisible('#'+h.prefix+'-pause-modal'), true);
      await h.resume(); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 1); await h.finish();

      // Dismissing Restart by its backdrop returns to Pause, just like Escape.
      h=await open(fixture); await h.pause(); await h.page.click('#'+h.prefix+'-restart');
      await h.page.locator('#'+h.prefix+'-restart-modal').click({position:{x:5,y:5}});
      assert.equal(await h.page.isVisible('#'+h.prefix+'-restart-modal'), false);
      assert.equal(await h.page.isVisible('#'+h.prefix+'-pause-modal'), true);
      await h.resume(); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      assert.equal(h.saves.length, 0); await h.finish();

      // Failed/uncertain resets reload authoritative state, since failure to
      // receive a response does not prove the reset failed on the server.
      for (const failure of ['network', 'http', 'rejected', 'malformed', 'lost']) {
        const choosing=failure === 'http';
        h=await open(fixture, {current_item:1, choice_index:choosing ? 3 : 1, ...(choosing ? {phase:'choosing'} : {})});
        h.failReset(failure); await h.pause(); await h.page.click('#'+h.prefix+'-restart');
        const recovered=h.page.waitForEvent('domcontentloaded');
        await h.page.click('#'+h.prefix+'-restart-yes'); await recovered;
        assert.equal(h.alerts.length, 1); assert.equal(h.state.current_item, failure === 'lost' ? 0 : 1);
        assert.equal(h.state.choice_index, failure === 'lost' ? 0 : choosing ? 3 : 1);
        await h.page.click('#'+h.prefix+'-go');
        await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read')?.disabled);
        if (choosing) {
          await h.page.locator('[data-choice], [data-word]').first().click();
          await h.page.waitForSelector('#read'); assert.equal(h.state.current_item, 2);
        } else {
          if (failure !== 'lost') {
            const previous=h.narrations.length; await h.page.click('#listen');
            await h.page.waitForFunction(() => window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
            assert.equal(h.narrations.length, previous+1);
          }
          await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
          const fields=await h.page.evaluate(() => window.readFields);
          assert.equal(fields[0].target_text, fixture.number === 1 ? fixture.data.items[h.state.current_item].choices[h.state.choice_index] : fixture.data.items[h.state.current_item].word);
        }
        assert.equal(h.saves.filter(body=>body.reset).length, 1);
        assert.equal(h.saves.filter(body=>body.action).length, choosing ? 1 : 0);
        await h.finish();
      }

      // Reading stays blocked while a successful reset is pending.
      // A confirmed reset reloads and starts at the first item again.
      h=await open(fixture, {current_item:1, choice_index:1}); h.holdSave();
      await h.pause(); await h.page.click('#'+h.prefix+'-restart'); await h.page.click('#'+h.prefix+'-restart-yes');
      await h.page.waitForTimeout(50); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 0);
      const resetReload=h.page.waitForEvent('domcontentloaded'); await h.releaseSave(); await resetReload;
      assert.equal(h.state.current_item, 0); assert.equal(h.state.choice_index, 0);
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      assert.equal(h.saves.length, 1); assert.equal(h.alerts.length, 0); await h.finish();

      // An uncertain reset reloads; restarting again works on the fresh page.
      h=await open(fixture, {current_item:1, choice_index:1}); h.failReset('network');
      await h.pause(); await h.page.click('#'+h.prefix+'-restart');
      const failedReload=h.page.waitForEvent('domcontentloaded'); await h.page.click('#'+h.prefix+'-restart-yes'); await failedReload;
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
      h.failReset(null); await h.pause(); await h.page.click('#'+h.prefix+'-restart');
      const retryReload=h.page.waitForEvent('domcontentloaded');
      await h.page.click('#'+h.prefix+'-restart-yes'); await retryReload;
      assert.equal(h.state.current_item, 0); assert.equal(h.state.choice_index, 0);
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      assert.equal(h.saves.length, 2); assert.equal(h.alerts.length, 1); await h.finish();

      // Restart waits for the current answer save. Repeated Restart clicks
      // cannot send another reset while that save is unresolved.
      h=await open(fixture, {current_item:1, choice_index:1}); h.holdSave();
      await h.page.evaluate(() => window.autoSpeech=true); await h.page.click('#read');
      await h.page.waitForTimeout(50); assert.equal(h.saves.length, 1);
      await h.pause(); await h.page.click('#'+h.prefix+'-restart'); await h.page.click('#'+h.prefix+'-restart-yes');
      await h.pause(); await h.page.click('#'+h.prefix+'-restart'); await h.page.click('#'+h.prefix+'-restart-yes');
      await h.page.waitForTimeout(50); assert.equal(h.saves.length, 1);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      const orderedReset=h.page.waitForEvent('domcontentloaded'); await h.releaseSave(); await orderedReset;
      assert.deepEqual(h.saves.map(body=>body.action || (body.reset ? 'reset' : '')), [fixture.number === 1 ? 'read_choice' : 'read_word', 'reset']);
      assert.equal(h.state.current_item, 0); assert.equal(h.state.choice_index, 0);
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
      await h.page.click('#read');
      const resetFields=await h.page.evaluate(() => window.readFields);
      assert.equal(resetFields[0].target_text, fixture.number === 1 ? fixture.data.items[0].choices[0] : fixture.data.items[0].word);
      await h.finish();

      // If the pending answer's outcome is unknown, do not send an overlapping
      // reset. Reload to recover saved state before further input instead.
      h=await open(fixture, {current_item:1, choice_index:1}); h.holdSave(); h.failAnswer();
      await h.page.evaluate(() => window.autoSpeech=true); await h.page.click('#read');
      await h.page.waitForTimeout(50); await h.pause(); await h.page.click('#'+h.prefix+'-restart'); await h.page.click('#'+h.prefix+'-restart-yes');
      const uncertainAnswer=h.page.waitForEvent('domcontentloaded'); await h.releaseSave(); await uncertainAnswer;
      assert.equal(h.saves.length, 1); assert.equal(h.saves.filter(body=>body.reset).length, 0);
      assert.equal(h.alerts.length, 1); assert.equal(h.state.current_item, 1);
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio=>audio.paused) && !document.querySelector('#read').disabled);
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1); await h.finish();

      // Cleanup while reset is pending must prevent recovery from resurrecting
      // the old activity or interrupting navigation with an error dialog.
      h=await open(fixture); h.holdSave(); h.failReset('network');
      await h.pause(); await h.page.click('#'+h.prefix+'-restart'); await h.page.click('#'+h.prefix+'-restart-yes');
      await h.page.waitForTimeout(50); await h.page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
      await h.releaseSave(); await h.page.waitForTimeout(80);
      assert.equal(h.alerts.length, 0); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 0); await h.finish();

      // A narration response arriving after pause must not restart playback.
      h=await open(fixture); const initialPlaybacks=await h.page.evaluate(() => window.playbacks.length);
      h.holdNarration(); await h.page.click('#listen'); await h.pause(); await h.resume(); await h.releaseNarration();
      await h.page.waitForTimeout(60);
      assert.equal(await h.page.evaluate(() => window.playbacks.length), initialPlaybacks);
      assert.equal(await h.page.isEnabled('#read'), true); await h.finish();

      // A late speech result is discarded after pause/resume, even if the
      // provider does not honor cancellation immediately.
      h=await open(fixture); await h.page.evaluate(() => window.ignoreCancel=true); await h.page.click('#read');
      await h.page.waitForFunction(() => window.completeSpeech); await h.pause(); await h.resume();
      await h.page.evaluate(() => window.completeSpeech({raw_transcript:'pet', complete:true}));
      await h.page.waitForTimeout(60); assert.equal(h.saves.length, 0);
      assert.equal(await h.page.isEnabled('#read'), true); await h.finish();

      // A progress request already sent may finish after resume. Restore its
      // committed state without replaying old feedback or allowing duplicate
      // capture while its outcome is unknown.
      h=await open(fixture); h.holdSave(); await h.page.evaluate(() => window.autoSpeech=true);
      await h.page.click('#read'); await h.page.waitForTimeout(50);
      assert.equal(h.saves.length, 1); await h.pause(); await h.resume();
      await h.page.click('#read'); assert.equal(await h.page.evaluate(() => window.captureCalls), 1);
      await h.releaseSave();
      if (fixture.number === 1) await h.page.waitForFunction(() => document.querySelector('.word')?.textContent.trim() === 'mat');
      else await h.page.waitForSelector('[data-word]');
      assert.equal(h.saves.length, 1); await h.finish();

      // Help cancels playback and can be closed without leaving Read blocked.
      h=await open(fixture); await h.page.evaluate(() => window.holdAudio=true); await h.page.click('#listen');
      await h.page.waitForFunction(() => window.playbacks.some(audio => !audio.paused));
      await h.page.click('#'+h.prefix+'-help-btn');
      assert.equal(await h.page.evaluate(() => window.playbacks.every(audio => audio.paused)), true);
      await h.page.click('#'+h.prefix+'-help-close'); await h.page.click('#read');
      assert.equal(await h.page.evaluate(() => window.captureCalls), 1); await h.finish();

      // Successful word reading still unlocks the existing choice phase, and
      // choosing advances to the next item's original reading phase.
      h=await open(fixture); await h.page.evaluate(() => window.autoSpeech=true);
      const words=fixture.number === 1 ? 3 : 1;
      for (let i=0; i<words; i++) {
        await h.page.click('#read');
        await h.page.waitForFunction(count => window.readFields.length === count && window.playbacks.every(audio => audio.paused) && !document.querySelector('#read')?.disabled, i+1);
      }
      await h.page.waitForSelector('[data-choice], [data-word]');
      assert.equal(h.state.phase, 'choosing');
      for (const fields of await h.page.evaluate(() => window.readFields)) {
        assert.equal(fields.language, 'English'); assert.equal(fields.mode, 'reading'); assert.equal(fields.prescribed_activity_key, fixture.key);
      }
      await h.page.locator('[data-choice], [data-word]').first().click(); await h.page.waitForSelector('#read');
      assert.equal(h.state.current_item, 1); assert.equal(h.state.phase, fixture.number === 1 ? 'reading_choices' : 'reading');
      await h.finish();

      // Pause/resume while a choice save is pending cannot submit it twice.
      h=await open(fixture); await h.page.evaluate(() => window.autoSpeech=true);
      for (let i=0; i<words; i++) {
        await h.page.click('#read');
        await h.page.waitForFunction(count => window.readFields.length === count && window.playbacks.every(audio => audio.paused) && !document.querySelector('#read')?.disabled, i+1);
      }
      await h.page.waitForSelector('[data-choice], [data-word]'); h.holdSave();
      await h.page.locator('[data-choice], [data-word]').first().click(); await h.page.waitForTimeout(50);
      assert.equal(h.saves.length, words+1); await h.pause(); await h.resume();
      await h.page.locator('[data-choice], [data-word]').first().click();
      assert.equal(h.saves.length, words+1); await h.releaseSave(); await h.page.waitForSelector('#read');
      assert.equal(h.state.current_item, 1); await h.finish();

      // A persisted history restoration reloads the authoritative saved state
      // and restores usable controls without resetting or submitting answers.
      h=await open(fixture, {current_item:1, choice_index:1});
      const reloaded=h.page.waitForEvent('domcontentloaded');
      await h.page.evaluate(() => {
        window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}));
        window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}));
      });
      await reloaded;
      await h.page.click('#'+h.prefix+'-go');
      await h.page.waitForFunction(() => window.playbacks.length && window.playbacks.every(audio => audio.paused) && !document.querySelector('#read')?.disabled);
      await h.page.click('#read');
      const fields=await h.page.evaluate(() => window.readFields);
      assert.equal(fields.length, 1); assert.equal(h.state.current_item, 1); assert.equal(h.state.choice_index, 1);
      assert.equal(fields[0].target_text, fixture.number === 1 ? fixture.data.items[1].choices[1] : fixture.data.items[1].word);
      assert.equal(h.saves.length, 0); await h.finish();

      // The final spoken feedback must play even while the completion
      // acknowledgement remains pending; finishing still saves just one choice.
      h=await open(fixture, {phase:'choosing', current_item:fixture.data.items.length-1, choice_index:3});
      h.holdCompletion();
      const feedback=fixture.number === 1 ? 'Wonderful! You finished the activity.' : 'Great job! You completed Say and Circle.';
      await h.page.locator('[data-choice], [data-word]').first().click();
      await h.page.waitForSelector('.pabasa-completion-card');
      await h.page.waitForFunction(() => window.playbacks.length>=2 && window.playbacks.every(audio => audio.paused));
      assert.equal(h.state.phase, 'complete'); assert.ok(h.completions.length>=1);
      assert.deepEqual(h.narrations.slice(1), [feedback]); assert.equal(h.saves.length, 1);
      h.releaseCompletion(); await h.finish();
    }
    console.log(`PASS: ${checked} Lesson 31 Activity 1/4 mute, pause, delayed response, Help and reading/choice flow scenarios.`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
