// Local rendered Django pages and real static assets. Speech capture/provider and
// progress are synthetic and stay in memory; no accounts or database writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static');
const output = path.join(os.tmpdir(), 'pabasa-three-activity-verification');
fs.mkdirSync(output, {recursive: true});
const baseline = process.env.PABASA_THREE_BASELINE || '';
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import json, os, sys
from pathlib import Path
sys.path.insert(0, 'pabasa_site')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
import django
django.setup()
from django.template import engines
from django.template.loader import render_to_string
from django.templatetags.static import static
from pabasa_app.prescribed_activity_catalog import prescribed_activity
names = {'lesson-16-gawain-1':'prescribed_missing_syllable_page',
         'session-6-lesson-16-gawain-4':'prescribed_picture_word_write_page',
         'session-7-lesson-19-gawain-2':'session7_missing_syllable_page'}
fixtures = []
for key, name in names.items():
    activity = prescribed_activity(key)
    data = {**activity, 'items':[{**item, 'image_url':static(item['image_path'])} for item in activity['items']],
            'intro_enabled':key=='lesson-16-gawain-1', 'progress':{'state':{}},
            'progress_url':'/progress/', 'completion_url':'/complete/',
            'transcribe_url':'/transcribe/', 'read_aloud_url':'/narrate/'}
    context = {'prescribed_activity_data':data}
    fixture = {'key':key, 'data':data, 'html':render_to_string('pabasa_app/'+name+'.html', context)}
    baseline = os.environ.get('PABASA_THREE_BASELINE')
    if baseline:
        fixture['baseline'] = engines['django'].from_string((Path(baseline)/(name+'.html')).read_text(encoding='utf-8')).render(context)
    fixtures.append(fixture)
print(json.dumps(fixtures))
`], {cwd: root, encoding: 'utf8', maxBuffer: 3 * 1024 * 1024});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);
const g1 = 'lesson-16-gawain-1', g4 = 'session-6-lesson-16-gawain-4', g2 = 'session-7-lesson-19-gawain-2';
const correctFile = 'magaling_ang_pagbasa_pindutin_ang_tamang_letra_tts.mp3';
const readingInstruction = 'Basahin muna ang ngalan ng larawan.';
const writingInstruction = 'Isulat ang wastong salita para sa larawan.';
const report = {viewports: [], readingItems: [], audio: []};

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true, args: ['--autoplay-policy=no-user-gesture-required']});
  async function open(key, state = {}, answers = [], options = {}) {
    const fixture = fixtures.find(item => item.key === key);
    const page = await browser.newPage({viewport: options.viewport || {width: 1534, height: 729}, deviceScaleFactor: options.scale || 1});
    let saved = structuredClone(state), savedAnswers = [...answers];
    const errors = [], writes = [], missing = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(real => {
      window.played = []; window.mediaEvents = []; window.players = []; window.overlaps = [];
      window.accepted = true; window.providerFailure = false; window.holdAudio = false;
      window.captureCount = 0; window.stoppedTracks = 0;
      const NativeAudio = window.Audio;
      window.Audio = real ? function(src) {
        const player = new NativeAudio(src); window.players.push(player);
        for (const event of ['play', 'ended', 'pause', 'error']) player.addEventListener(event, () => {
          window.mediaEvents.push({src, event, time: performance.now()});
          if (event === 'play') {
            if (window.players.some(other => other !== player && !other.paused && !other.ended)) window.overlaps.push(src);
            window.played.push(src);
          }
        });
        return player;
      } : class extends EventTarget {
        constructor(src) {super(); this.src = src; this.currentTime = 0; this.paused = true; this.ended = false; window.players.push(this);}
        play() {
          if (window.players.some(other => other !== this && !other.paused)) window.overlaps.push(this.src);
          this.paused = false; window.played.push(this.src);
          if (!window.holdAudio) setTimeout(() => this.end(), 10);
          return Promise.resolve();
        }
        emit(event) {this.dispatchEvent(new Event(event)); this['on'+event]?.();}
        end() {if (this.paused) return; this.ended = true; this.paused = true; this.emit('ended');}
        pause() {if (this.paused) return; this.paused = true; this.emit('pause');}
      };
      if (real) window.Audio.prototype = NativeAudio.prototype;
      const stream = () => ({getTracks: () => [{stop() {window.stoppedTracks++;}}], getAudioTracks: () => []});
      Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {getUserMedia: async () => stream(), enumerateDevices: async () => []}});
      window.MediaRecorder = class extends EventTarget {};
      window.Basahin = {
        openMicrophone: async () => stream(),
        capture: async () => {window.captureCount++; return new Blob(['synthetic capture'], {type: 'audio/webm'});},
        bindActivity: (button, action) => window.BasahinButton.bindActivity(button, action),
        attachStreamResult() {}, cancelAll() {}, isCaptureError: () => false,
      };
    }, Boolean(options.realAudio));
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/activity/') {
        let html = options.baseline ? fixture.baseline : fixture.html;
        html = html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,
          (tag, attrs) => /src=.*(?:basahin\.js|speech_debug)/.test(attrs) ? '' : tag);
        const data = {...fixture.data, progress: {state: saved, answers: savedAnswers}};
        html = html.replace(/(<script[^>]*id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,
          (_, start, end) => start + JSON.stringify(data) + end);
        return route.fulfill({contentType: 'text/html', body: html});
      }
      if (url.pathname === '/progress/') {
        const body = route.request().postDataJSON(); writes.push(body);
        if (body.state) saved = structuredClone(body.state);
        const expected = fixture.data.items[savedAnswers.length]?.answer;
        const accepted = body.candidate_answer != null && body.candidate_answer === expected;
        if (accepted) savedAnswers.push(body.candidate_answer);
        return route.fulfill({json: {success: true, accepted, progress: {state: saved, answers: savedAnswers}}});
      }
      if (url.pathname === '/transcribe/') {
        const body = route.request().postDataBuffer().toString();
        assert.match(body, /name="language"\r\n\r\nFilipino\r\n/);
        assert.match(body, /name="mode"\r\n\r\nreading\r\n/);
        assert.match(body, /name="audio"/);
        const verdict = await page.evaluate(() => ({success: !providerFailure, complete: accepted}));
        return route.fulfill({json: verdict});
      }
      if (url.pathname === '/complete/') return route.fulfill({json: {success: true}});
      if (url.pathname === '/narrate/') return route.fulfill({json: {success: false}});
      if (url.pathname.startsWith('/static/')) {
        if (options.baseline && url.pathname.endsWith('/session67_reference.css'))
          return route.fulfill({path: path.join(baseline, 'session67_reference.css')});
        const file = path.join(staticRoot, decodeURIComponent(url.pathname.slice(8)));
        if (fs.existsSync(file) && fs.statSync(file).isFile()) return route.fulfill({path: file});
        missing.push(url.pathname); return route.fulfill({status: 404, body: ''});
      }
      return route.fulfill({body: ''});
    });
    await page.goto('http://localhost/activity/');
    const modal = page.locator('[data-session6-start],[data-session7-start]');
    if (await modal.isVisible()) await modal.click();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(200);
    return {page, errors, missing, writes, state: () => saved};
  }
  async function close(test) {
    assert.deepEqual(test.errors, [], 'Browser JavaScript errors');
    assert.deepEqual(test.missing, [], 'Missing static assets');
    assert.deepEqual(await test.page.evaluate(() => overlaps), [], 'Overlapping audio');
    await test.page.close();
  }
  async function geometry(page) {
    return page.evaluate(() => {
      const box = element => {const r = element.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right};};
      return {card:box(document.querySelector('#app')), page:box(document.querySelector('.page')),
        tools:[...document.querySelectorAll('.back,.s6-tool,.prescribed-session-tool')].map(box), width:innerWidth,height:innerHeight};
    });
  }
  try {
    // The attachments have 1917x911 page pixels at approximately 125% desktop
    // scaling. Check the corresponding CSS viewport and the 1:1 pixel viewport.
    for (const options of [{viewport:{width:1534,height:729},scale:1.25}, {viewport:{width:1917,height:911}}, {viewport:{width:1366,height:900}}]) {
      const test = await open(g1, {phase:'intro'}, [], options);
      await test.page.locator('#activityStart').waitFor();
      const measured = await geometry(test.page), card = measured.card;
      assert.ok(Math.abs(card.x + card.width/2 - measured.width/2) < 2, 'Entire card horizontally centered');
      assert.ok(Math.abs(card.y + card.height/2 - measured.height/2) < 3, 'Entire card vertically centered: '+JSON.stringify(measured));
      assert.ok(card.bottom < measured.height && measured.tools.every(tool => card.y >= tool.bottom + 8), 'Card clears floating controls');
      if (baseline) {
        const before = await open(g1, {phase:'intro'}, [], {...options, baseline:true});
        const original = (await geometry(before.page)).card;
        assert.ok(Math.abs(card.width-original.width) < 0.1 && Math.abs(card.height-original.height) < 0.1, 'Original card dimensions preserved');
        assert.equal(await test.page.locator('#app').innerHTML(), await before.page.locator('#app').innerHTML(), 'Start contents preserved');
        await close(before);
      }
      await test.page.screenshot({path:path.join(output, `gawain1-start-${options.viewport.width}.png`)});
      report.viewports.push(measured);
      await test.page.locator('#activityStart').click();
      await test.page.locator('#oralAction').waitFor();
      await close(test);
    }
    // Every picture: resumed reading/writing plus actual reading -> writing ->
    // next-picture reading. This includes goma at index 3 from the screenshot.
    const pictures = fixtures.find(f => f.key === g4).data.items;
    for (const [index, item] of pictures.entries()) {
      const answers = pictures.slice(0,index).map(i => i.answer);
      const test = await open(g4, {started:true, phase:'oral_reading', completed_oral_reads:[], stt_attempts:{}, tts_plays:{}}, answers);
      assert.equal(await test.page.locator('#app h1').textContent(), readingInstruction);
      assert.equal(await test.page.locator('#app > .instruction').count(), 0, 'Repeated instruction removed');
      assert.equal(await test.page.locator('.oral-word').textContent(), item.read_aloud);
      assert.equal(await test.page.locator('.step.completed').count(), index);
      assert.ok(await test.page.locator('.instruction-space').evaluate(node => node.getBoundingClientRect().height > 15), 'Blank space below heading');
      if (index === 3) await test.page.screenshot({path:path.join(output,'gawain4-goma-reading.png')});
      await test.page.locator('#oral-action').click();
      await test.page.locator('#answer').waitFor();
      assert.equal(await test.page.locator('#app h1').textContent(), writingInstruction);
      assert.equal(await test.page.locator('#app > .instruction').count(), 0);
      if (index === 3) await test.page.screenshot({path:path.join(output,'gawain4-goma-writing.png')});
      await test.page.locator('#answer').fill(item.answer);
      await test.page.locator('#answer-form button').click();
      if (index < pictures.length-1) {
        await test.page.locator('.oral-word').filter({hasText:pictures[index+1].read_aloud}).waitFor();
        assert.equal(await test.page.locator('#app h1').textContent(), readingInstruction);
      }
      await close(test);
      const resumed = await open(g4, {started:true, phase:'written', completed_oral_reads:[index], stt_attempts:{}, tts_plays:{}}, answers);
      assert.equal(await resumed.page.locator('#app h1').textContent(), writingInstruction);
      assert.ok(await resumed.page.locator('#answer').isVisible());
      if (baseline && index === 3) {
        const before = await open(g4, {started:true, phase:'written', completed_oral_reads:[index], stt_attempts:{}, tts_plays:{}}, answers, {baseline:true});
        const original = (await geometry(before.page)).card, current = (await geometry(resumed.page)).card;
        assert.ok(Math.abs(original.width-current.width) < 0.1 && Math.abs(original.height-current.height) < 0.1, 'Writing card dimensions preserved');
        await close(before);
      }
      await close(resumed);
      report.readingItems.push(item.read_aloud);
    }
    // Native Chrome MP3 playback: exactly one correct-reading clip, with a real
    // ended event, for each oral item; failure gets only retry feedback.
    const words = fixtures.find(f => f.key === g2).data.items;
    for (const [index, item] of words.entries()) {
      const test = await open(g2, {phase:'oral_reading',current_item_index:index,completed_oral_reads:[],stt_attempts:{},tts_plays:{},written_answers:[],correct_answer_count:0}, [], {realAudio:true});
      await test.page.waitForFunction(() => players.every(player => player.paused || player.ended));
      await test.page.evaluate(() => {played=[]; mediaEvents=[];});
      await test.page.locator('#oral').click();
      await test.page.locator('#answer').waitFor();
      await test.page.waitForFunction(file => mediaEvents.some(event => event.src.endsWith('/'+file) && event.event==='ended'), correctFile, {timeout:20000});
      const played = await test.page.evaluate(() => played);
      assert.equal(played.length, 1, 'Only one feedback clip during transition');
      assert.ok(played[0].endsWith('/SESSION_7/LESSON_19/GAWAIN_2/'+correctFile));
      assert.ok(test.state().completed_oral_reads.includes(index));
      assert.equal(test.state().stt_attempts[String(index)], 0);
      assert.equal(test.state().phase, 'written_answer');
      assert.equal(await test.page.evaluate(() => captureCount), 1);
      assert.ok(await test.page.evaluate(() => stoppedTracks > 0));
      if (index===0) await test.page.screenshot({path:path.join(output,'gawain2-after-correct-reading.png')});
      report.audio.push({word:item.word,played,events:await test.page.evaluate(() => mediaEvents)});
      await close(test);
    }
    for (const providerFailure of [false,true]) {
      const test = await open(g2, {phase:'oral_reading',current_item_index:0,completed_oral_reads:[],stt_attempts:{},tts_plays:{}});
      await test.page.evaluate(failure => {played=[]; accepted=false; window.providerFailure=failure;}, providerFailure);
      await test.page.locator('#oral').click();
      await test.page.waitForFunction(() => played.some(file => file.endsWith('/hindi_pa_tama_tts.mp3')));
      assert.ok((await test.page.evaluate(() => played)).every(file => !file.endsWith('/'+correctFile)));
      assert.equal(test.state().phase, 'oral_reading');
      assert.equal(test.state().stt_attempts['0'], 1);
      assert.deepEqual(test.state().completed_oral_reads, []);
      await close(test);
    }
    fs.writeFileSync(path.join(output,'report.json'), JSON.stringify(report,null,2));
    console.log(`Passed: 3 desktop start screens, 5 reading/writing item cycles and resumes, 5 native MP3 transitions, incorrect/provider failure. Artifacts: ${output}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
