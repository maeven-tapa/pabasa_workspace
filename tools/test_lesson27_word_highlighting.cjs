// Lesson 27 UI regression with actual Django markup and backend word results.
// Microphone/provider replies and progress persistence are local fixtures only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import json, os, re, sys
sys.path.insert(0, 'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from django.template.loader import render_to_string
from pabasa_app.prescribed_activity_catalog import prescribed_activity
from pabasa_app.lesson27_reading import analyze_verse_reading
activity = prescribed_activity('lesson-27-gawain-1')
items, clips = [], []
for i, item in enumerate(activity['items']):
    lines = []
    for j, text in enumerate(item['verses']):
        words = [{'id': f'w{i}-{j}-{k}', 'text': m.group()} for k, m in enumerate(re.finditer('[A-Za-z]+', text))]
        lines.append({'text': text, 'words': words})
        prefix = ' '.join(text.split()[:2])
        partial = analyze_verse_reading(text, 0, prefix, 'en-US')
        wrong = analyze_verse_reading(text, 0, prefix + ' banana potato', 'en-US')
        rest = analyze_verse_reading(text, partial['current_syllable_index'], ' '.join(text.split()[2:]), 'en-US')
        full = analyze_verse_reading(text, 0, text, 'en-US')
        clips.append({'item':i, 'verse':j, 'partial':partial, 'wrong':wrong, 'rest':rest, 'full':full})
    items.append({'id':item['id'], 'title':item['title'], 'lines':lines})
data = {'activity_key':'lesson-27-gawain-1', 'items':items, 'progress':{'state':{}},
        'progress_url':'/progress/', 'transcribe_url':'/transcribe/', 'completion_url':'/complete/'}
html = render_to_string('pabasa_app/prescribed_rhyming_verses_lesson27_activity1_page.html', {'prescribed_activity_data':data})
print(json.dumps({'html':html,'data':data,'clips':clips}))
`], {cwd:root, encoding:'utf8', maxBuffer:3 * 1024 * 1024});
assert.equal(rendered.status, 0, rendered.stderr);
const fixture = JSON.parse(rendered.stdout);
const scriptNames = new Set(['basahin_button.js', 'prescribed_controls.js', 'prescribed_lesson26_31_ui.js',
  'prescribed_rhyming_verses_lesson27_activity1.js', 'prescribed_leave_confirmation.js']);

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checks = 0;
  async function open(clip, viewport = {width:1366, height:768}) {
    const page = await browser.newPage({viewport});
    const errors = [], saves = [];
    let state = {phase:'reading',item_index:clip.item,verse_index:clip.verse,selected:[],attempts:0,
      verse_syllable_index:0,verse_word_index:0,completed_items:clip.item};
    page.on('pageerror', e => errors.push(e.message));
    await page.route('http://localhost:9876/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/lesson-27-gawain-1/') {
        const data = {...fixture.data, progress:{state}};
        let html = fixture.html.replace(/(<script id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,
          (_, before, after) => before + JSON.stringify(data) + after);
        html = html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi, (tag, attrs) => {
          if (/application\/json/.test(attrs)) return tag;
          const src = attrs.match(/src="([^"]+)"/)?.[1];
          return src && scriptNames.has(path.posix.basename(src.split('?')[0])) ? tag : '';
        });
        return route.fulfill({contentType:'text/html', body:html});
      }
      if (url.pathname === '/progress/') {
        const payload = route.request().postDataJSON();
        saves.push(payload);
        if (await page.evaluate(() => window.progressFailures > 0)) {
          await page.evaluate(() => window.progressFailures--);
          return route.fulfill({status:503,json:{success:false,error:'Temporary save failure'}});
        }
        if (payload.action === 'verse_progress') {
          state.verse_syllable_index = payload.current_syllable_index;
          state.verse_word_index = clip.full.word_syllable_ranges.filter(range => range[1] <= payload.current_syllable_index).length;
        } else if (payload.action === 'verse_read') {
          if (payload.success) {
            state.verse_index++;
            state.verse_syllable_index = state.verse_word_index = state.attempts = 0;
            if (state.verse_index === 4) state.phase = 'rhymes';
          } else state.attempts++;
        } else if (payload.action === 'rhyme_select') state.selected.push(payload.token_id);
        return route.fulfill({json:{success:true, accepted:true, progress:{state}}});
      }
      if (url.pathname.startsWith('/static/pabasa_app/')) {
        const file = path.join(app, url.pathname.slice(1));
        if (fs.existsSync(file)) return route.fulfill({body:fs.readFileSync(file), contentType:file.endsWith('.js') ? 'text/javascript' : 'application/octet-stream'});
      }
      return route.fulfill({status:404,body:''});
    });
    await page.addInitScript(() => {
      window.clips = [];
      window.readingFields = [];
      window.readingOptions = [];
      window.playedAudio = [];
      const readers = new Set();
      window.MediaRecorder = function () {};
      navigator.mediaDevices.getUserMedia = async () => { throw Error('No real microphone should be used'); };
      navigator.mediaDevices.enumerateDevices = async () => [];
      window.Audio = class extends EventTarget {
        constructor(url) { super(); this.url = decodeURIComponent(url); }
        play() { window.playedAudio.push(this.url); queueMicrotask(() => this.dispatchEvent(new Event('ended'))); return Promise.resolve(); }
        pause() { this.dispatchEvent(new Event('pause')); }
      };
      window.Basahin = {
        bindActivity(button, action) { window.BasahinButton.bindActivity(button, action); },
        cancelAll() { readers.forEach(reader => reader.stop()); },
        create(options) {
          window.readingOptions.push({silenceMs:options.silenceMs});
          let stopped = false, wake;
          const reader = {
            async start() {
              try {
                for (let n = 0; n < 25 && !stopped; n++) {
                  window.readingFields.push({...options.getFields()});
                  window.lateResult = options.onResult;
                  if (!window.clips.length) { await new Promise(resolve => { wake = resolve; }); break; }
                  const clip = window.clips.shift();
                  if (clip.error) throw new Error(clip.error);
                  if (await options.onResult(clip)) break;
                }
              } catch (error) { options.onError(error); }
            },
            stop() { stopped = true; wake?.(); },
            destroy() { this.stop(); readers.delete(reader); },
          };
          readers.add(reader);
          return reader;
        },
      };
    });
    await page.goto('http://localhost:9876/lesson-27-gawain-1/');
    await page.evaluate(() => {
      document.getElementById('lesson27-start').hidden = true;
      document.getElementById('lesson27-stage').classList.remove('is-waiting');
    });
    return {page, errors, saves, getState:() => state};
  }
  async function speak(page, result) {
    await page.evaluate(result => { window.clips = [result]; }, result);
    await page.locator('#record-verse').click();
  }
  try {
    // All sixteen verses, including multi-syllable words and "he'll".
    for (const clip of fixture.clips) {
      const {page, errors, saves} = await open(clip);
      const line = fixture.data.items[clip.item].lines[clip.verse];
      assert.equal(await page.locator('.lesson27-verse.active .lesson27-unread').textContent(), line.text);
      await speak(page, clip.partial);
      await page.waitForFunction(() => window.playedAudio.some(url => url.includes('read the rest of the verse')));
      assert.equal(saves.filter(p => p.action === 'verse_read').length, 0, 'A correct partial verse must not count as a failed attempt');
      assert.equal((await page.evaluate(() => window.readingOptions))[0].silenceMs, 3000);
      assert.equal((await page.evaluate(() => window.playedAudio))[0].split('/').at(-1), "Great! now let's read the rest of the verse..mp3");
      await speak(page, clip.wrong);
      await page.waitForFunction(() => window.playedAudio.some(url => url.includes('try that again')));
      const active = page.locator('.lesson27-verse').nth(clip.verse);
      assert.deepEqual(await active.locator('.is-read').allTextContents(), fixture.data.items[clip.item].lines[clip.verse].words.slice(0,2).map(word => word.text));
      assert.equal(saves.filter(p => p.action === 'verse_read').length, 1);
      assert.equal(saves.at(-1).success, false);
      assert.equal(await page.locator('.lesson27-verse.active').count(), 1);
      assert.equal(await active.locator('[aria-current="true"]').getAttribute('data-word-index'), '2');
      assert.deepEqual(await active.locator('.lesson27-unread .lesson27-word').allTextContents(), line.words.slice(2).map(word => word.text));
      assert.equal(await active.locator('.lesson27-unread .is-read').count(), 0);
      await speak(page, clip.rest);
      await page.waitForFunction(() => document.querySelector('.lesson27-prompt').textContent.includes('Click all') || window.readingFields.length === 3 && window.playedAudio.length === 3);
      assert.equal(saves.filter(p => p.action === 'verse_read').at(-1).success, true);
      const fields = await page.evaluate(() => window.readingFields);
      assert.equal(fields[2].current_syllable_index, clip.partial.current_syllable_index);
      assert.equal(fields[2].language, 'English');
      assert.equal(fields[2].prescribed_activity_key, 'lesson-27-gawain-1');
      if (clip.verse < 3) assert.equal(await active.locator('.is-read').count(), fixture.data.items[clip.item].lines[clip.verse].words.length);
      else {
        assert.equal(await page.locator('.lesson27-word:disabled').count(), 0);
        assert.equal(await page.locator('.lesson27-word.is-read').count(), 0, 'Reading highlights must not replace rhyme selections');
        const rhyme = page.locator('.lesson27-word').filter({hasText:/^hat$|^rat$|^bat$|^sat$|^chat$/}).first();
        await rhyme.click();
        await page.waitForFunction(() => document.querySelector('.lesson27-word.selected'));
      }
      assert.deepEqual(errors, []);
      checks++;
      await page.close();
    }
    const clip = fixture.clips[0];
    {
      const {page, errors, saves, getState} = await open(clip);
      await page.evaluate(() => window.progressFailures = 1);
      await speak(page, clip.full);
      await page.waitForFunction(() => window.playedAudio.length > 0);
      assert.equal(getState().verse_index, 0, 'A failed save must not complete the verse');
      await speak(page, clip.full);
      await page.waitForFunction(() => document.querySelector('.lesson27-prompt').textContent.includes('verse 2'));
      await page.evaluate(() => window.__prescribedLeaveAdapters['prescribed-l27a1'].saveCurrentProgress());
      assert.deepEqual(saves.map(p => p.action), ['verse_progress','verse_progress','verse_read','state_sync']);
      assert.equal(getState().verse_index, 1, 'Successful rereading must clear the failed previous-verse save');
      assert.deepEqual(errors, []);
      checks++;
      await page.close();
    }
    {
      const {page, errors, saves, getState} = await open(clip);
      await page.evaluate(() => window.progressFailures = 1);
      await speak(page, clip.partial);
      await page.waitForFunction(() => window.playedAudio.length > 0);
      assert.equal(getState().verse_syllable_index, 0);
      assert.equal(await page.locator('.lesson27-verse.active .is-read').count(), 2);
      await page.evaluate(() => window.progressFailures = 1);
      const failure = await page.evaluate(async () => {
        try { await window.__prescribedLeaveAdapters['prescribed-l27a1'].saveCurrentProgress(); return ''; }
        catch (error) { return error.message; }
      });
      assert.equal(failure, 'Temporary save failure', 'Leave must stay blocked while saving still fails');
      assert.equal(saves.filter(p => p.action === 'state_sync').length, 0);
      await page.evaluate(() => window.__prescribedLeaveAdapters['prescribed-l27a1'].saveCurrentProgress());
      assert.deepEqual(saves.map(p => p.action), ['verse_progress','verse_progress','verse_progress','state_sync']);
      assert.equal(getState().verse_syllable_index, clip.partial.current_syllable_index);
      await page.reload();
      await page.evaluate(() => { document.getElementById('lesson27-start').hidden = true; document.getElementById('lesson27-stage').classList.remove('is-waiting'); });
      assert.equal(await page.locator('.lesson27-verse.active .is-read').count(), 2);
      await speak(page, clip.rest);
      await page.waitForFunction(() => document.querySelector('.lesson27-prompt').textContent.includes('verse 2'));
      assert.deepEqual(errors, []);
      checks++;
      await page.close();
    }
    for (const viewport of [{width:1366,height:768}, {width:390,height:844}]) {
      const {page, errors, saves} = await open(clip, viewport);
      await speak(page, clip.partial);
      await page.waitForFunction(() => window.playedAudio.some(url => url.includes('read the rest of the verse')));
      assert.equal(saves.filter(p => p.action === 'verse_read').length, 0, 'Correct partial clips prompt without counting a failed attempt');
      assert.equal(await page.locator('.lesson27-verse.active .is-read').count(), 2);
      await page.evaluate(() => window.PrescribedLesson27Activity.pause());
      await page.evaluate(() => window.__prescribedLeaveAdapters['prescribed-l27a1'].saveCurrentProgress());
      await page.evaluate(result => window.lateResult(result), clip.full);
      assert.equal(saves.filter(p => p.action === 'verse_read').length, 0, 'Cancelled recording cannot advance a verse');
      await page.reload();
      await page.evaluate(() => { document.getElementById('lesson27-start').hidden = true; document.getElementById('lesson27-stage').classList.remove('is-waiting'); });
      assert.equal(await page.locator('.lesson27-verse.active .is-read').count(), 2);
      assert.equal(await page.locator('.lesson27-verse.active [aria-current="true"]').textContent(), 'wore');
      assert.equal(await page.locator('.lesson27-verse.active .lesson27-unread').textContent(), 'wore a hat,');
      await page.waitForFunction(() => getComputedStyle(document.getElementById('lesson27-stage')).filter === 'none');
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({path:path.join(process.env.TEMP || root, `lesson27-highlight-${viewport.width}.png`)});
      await speak(page, clip.rest);
      await page.waitForFunction(() => document.querySelector('.lesson27-prompt').textContent.includes('verse 2'));
      assert.equal((await page.evaluate(() => window.readingFields))[0].current_syllable_index, 2);
      assert.deepEqual(errors, []);
      checks++;
      await page.close();
    }
    for (const failure of [{error:'Speech provider unavailable'}, {transcript:'', current_syllable_index:0}]) {
      const {page, errors, saves} = await open(clip);
      await speak(page, failure);
      await page.waitForFunction(() => window.playedAudio.some(url => url.includes('try that again')));
      assert.equal(await page.locator('.lesson27-word.is-read').count(), 0);
      assert.equal(saves.length, 0, 'Provider errors and silence cannot invent successful progress');
      assert.deepEqual(errors, []);
      checks++;
      await page.close();
    }
    const audioPage = await browser.newPage();
    const promptName = "Great! now let's read the rest of the verse..mp3";
    await audioPage.route('http://localhost:9876/**', route => {
      if (new URL(route.request().url()).pathname === '/prompt.mp3') {
        return route.fulfill({contentType:'audio/mpeg', body:fs.readFileSync(path.join(app, 'static/pabasa_app/prescribed/audio/SESSION_11/LESSON_27/GAWAIN_1', promptName))});
      }
      return route.fulfill({contentType:'text/html',body:'<audio id="prompt" src="/prompt.mp3" preload="auto"></audio><button onclick="document.getElementById(\'prompt\').play()">Play</button>'});
    });
    await audioPage.goto('http://localhost:9876/audio-test');
    await audioPage.waitForFunction(() => document.getElementById('prompt').readyState >= 1);
    assert.ok(await audioPage.evaluate(() => document.getElementById('prompt').duration > 0));
    await audioPage.getByRole('button', {name:'Play'}).click();
    await audioPage.waitForFunction(() => document.getElementById('prompt').ended);
    await audioPage.close();
    console.log(`PASS: ${checks} verse highlighting, partial prompts, retry, continuation, rhyme, cancellation and reload checks; supplied MP3 plays.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
