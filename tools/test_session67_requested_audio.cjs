// Called by tests_session67_requested_audio: actual Django templates and assets,
// synthetic capture/provider, in-memory progress. No database or live-site access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {chromium} = require('playwright');
const fixtures = JSON.parse(fs.readFileSync(process.env.PABASA_SESSION67_FIXTURES, 'utf8'));
const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static');
const prefix = '/static/pabasa_app/prescribed/audio/SESSION_6/';
const correct = prefix + 'LESSON_17_18/GAWAIN_7/magaling_tama_ang_nabasa_mo_tts.mp3';
const writtenCorrect = prefix + 'LESSON_17_18/GAWAIN_6/tama_magaling_ang_iyong_sagot.mp3';
let checks = 0;

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  async function open(key, state = {}, {realAudio = false, viewport = {width: 1366, height: 900}, answers = []} = {}) {
    const fixture = fixtures.find(item => item.key === key);
    const page = await browser.newPage({viewport});
    const errors = [], writes = [], missing = [];
    let saved = structuredClone(state), completionCount = 0;
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(real => {
      window.audioMode = 'end'; window.played = []; window.players = []; window.overlaps = [];
      window.speechAccepted = true; window.speechFailure = false; window.speechTranscript = null; window.nativeEvents = [];
      const NativeAudio = window.Audio;
      if (real) {
        window.Audio = function(src) {
          const player = new NativeAudio(src); window.players.push(player);
          for (const event of ['playing', 'ended', 'pause', 'error']) player.addEventListener(event, () =>
            window.nativeEvents.push({src, event, reason: player.__session6PauseReason, code: player.error?.code}));
          const nativePlay = player.play.bind(player);
          player.play = () => nativePlay().catch(error => {window.nativeEvents.push({src, error: error.name, message: error.message}); throw error;});
          player.addEventListener('play', () => window.played.push(src));
          return player;
        };
        window.Audio.prototype = NativeAudio.prototype;
      } else {
        window.Audio = class extends EventTarget {
          constructor(src) { super(); this.src = src; this.paused = true; this.currentTime = 0; window.players.push(this); }
          emit(type) { this.dispatchEvent(new Event(type)); this['on' + type]?.(); }
          end() { if (this.paused) return; this.paused = true; this.ended = true; this.emit('pause'); this.emit('ended'); }
          play() {
            if (window.audioMode === 'reject') return Promise.reject(Error('Synthetic audio failure'));
            if (window.players.some(player => player !== this && !player.paused)) window.overlaps.push(this.src);
            this.paused = false; window.played.push(this.src);
            if (window.audioMode !== 'hold') setTimeout(() => this.end(), 5);
            return Promise.resolve();
          }
          pause() { if (!this.paused) { this.paused = true; this.emit('pause'); } }
        };
      }
      window.BasahinButton = {LABEL: 'BASAHIN', setState(button) {button.disabled = false; button.textContent = 'BASAHIN';}};
      window.Basahin = {
        openMicrophone: async () => ({getTracks: () => [{stop() {}}], getAudioTracks: () => []}),
        capture: async () => new Blob(['test'], {type: 'audio/webm'}),
        bindActivity: (button, action) => button.onclick = action,
        attachStreamResult() {}, cancelAll() {}, isCaptureError: () => false,
      };
      window.MediaRecorder = class extends EventTarget {};
      Object.defineProperty(navigator, 'mediaDevices', {configurable: true, value: {
        getUserMedia: async () => ({getTracks: () => [{stop() {}}], getAudioTracks: () => []}),
        enumerateDevices: async () => [],
      }});
    }, realAudio);
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/activity/') {
        let html = fixture.html.replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi,
          (tag, attrs) => /src=.*(?:basahin|speech_debug)/.test(attrs) ? '' : tag);
        const data = {...fixture.data, progress: {state: saved, answers}};
        html = html.replace(/(<script[^>]*id="prescribed-activity-data"[^>]*>)[\s\S]*?(<\/script>)/,
          (_, head, tail) => head + JSON.stringify(data) + tail);
        return route.fulfill({contentType: 'text/html', body: html});
      }
      if (url.pathname === '/progress/') {
        const body = route.request().postDataJSON(); writes.push(body);
        if (body.state) saved = structuredClone(body.state);
        const accepted = fixture.key === 'lesson-17-18-gawain-6'
          ? Boolean(body.candidate_answer) && body.candidate_answer === fixture.data.items[body.current_index]?.answer
          : Boolean(body.candidate_answer);
        return route.fulfill({json: {success: true, accepted, progress: {state: saved}}});
      }
      if (url.pathname.includes('transcribe')) {
        const speech = await page.evaluate(() => ({failed: speechFailure, transcript: speechTranscript, accepted: speechAccepted}));
        let result = speech.failed ? {success: false, error: 'Provider unavailable'} : {success: true, complete: speech.accepted};
        if (fixture.key === 'lesson-17-18-gawain-6') {
          const body = route.request().postDataBuffer().toString();
          assert.match(body, /name="prescribed_activity_key"\r\n\r\nlesson-17-18-gawain-6\r\n/);
          assert.match(body, /name="language"\r\n\r\nFilipino\r\n/);
          assert.match(body, /name="mode"\r\n\r\nreading\r\n/);
          const target = body.match(/name="target_text"\r\n\r\n([^\r\n]+)/)?.[1];
          if (!speech.failed && speech.transcript !== null) {
            result = fixture.speech_verdicts[target]?.[speech.transcript];
            assert.ok(result, `Missing backend verdict for ${target}/${speech.transcript}`);
          }
        }
        return route.fulfill({json: result});
      }
      if (url.pathname === '/complete/') {completionCount++; return route.fulfill({json: {success: true}});}
      if (url.pathname.startsWith('/static/')) {
        const file = path.join(staticRoot, decodeURIComponent(url.pathname.slice(8)));
        if (fs.existsSync(file) && fs.statSync(file).isFile()) return route.fulfill({path: file});
        missing.push(url.pathname); return route.fulfill({status: 404, body: ''});
      }
      return route.fulfill({body: ''});
    });
    await page.goto('http://localhost/activity/');
    return {page, errors, writes, missing, state: () => saved, completions: () => completionCount};
  }
  async function start(page) {
    const modal = page.locator('[data-session6-start],[data-session7-start]');
    if (await modal.count()) await modal.click();
    const button = page.locator('#activityStart,#start');
    if (await button.count()) await button.click();
    await page.waitForTimeout(40);
  }
  async function close(test) {
    assert.deepEqual(test.errors, []); assert.deepEqual(test.missing, []);
    assert.deepEqual(await test.page.evaluate(() => overlaps), []);
    checks++; await test.page.close();
  }
  async function hold(page) {
    await page.evaluate(() => {audioMode = 'hold'; played = [];});
  }
  async function end(page) {
    await page.evaluate(() => players.findLast(player => !player.paused)?.end());
    await page.waitForTimeout(25);
  }
  async function played(page) {return page.evaluate(() => played);}

  try {
    // Visual left-to-right order and existing Help/Mute/Pause behavior at both sizes.
    for (const key of ['lesson-17-18-gawain-5', 'lesson-17-18-gawain-6', 'lesson-17-18-gawain-9', 'session-7-lesson-19-gawain-2']) {
      for (const viewport of [{width: 1366, height: 900}, {width: 390, height: 844}]) {
        const test = await open(key, {}, {viewport}); await start(test.page);
        const tools = test.page.locator('.s6-controls > button,.prescribed-session-tools > button');
        const controls = await tools.evaluateAll(nodes => nodes.map(node => ({
          id: node.id, label: node.getAttribute('aria-label'), x: node.getBoundingClientRect().x,
          right: node.getBoundingClientRect().right, order: getComputedStyle(node).order,
        })));
        assert.equal(controls.length, 3);
        assert.match(controls[0].id, /-help-btn$/); assert.ok(controls[0].label);
        assert.match(controls[1].id, /-mic-toggle$/); assert.ok(controls[1].label);
        assert.match(controls[2].id, /-audio-settings-btn$/); assert.equal(controls[2].label, 'I-pause ang gawain');
        assert.ok(controls[0].right <= controls[1].x && controls[1].right <= controls[2].x);
        await tools.nth(0).click(); assert.ok(await test.page.locator('[id$="-help-modal"]').isVisible());
        await test.page.locator('[id$="-help-close"]').click();
        await tools.nth(1).click(); assert.equal(await tools.nth(1).getAttribute('aria-pressed'), 'true');
        await tools.nth(1).click(); assert.equal(await tools.nth(1).getAttribute('aria-pressed'), 'false');
        await tools.nth(2).click(); assert.ok(await test.page.locator('[id$="-pause-modal"]').isVisible());
        await test.page.locator('[id$="-resume"]').click();
        if (key === 'lesson-17-18-gawain-6') {
          assert.deepEqual(await test.page.locator('#app button').allTextContents(), ['BASAHIN', 'PAKINGGAN']);
          await test.page.screenshot({path: path.join(os.tmpdir(), `pabasa-session6-gawain6-${viewport.width}.png`)});
        }
        await close(test);
      }
    }
    const later = await open('later-controls');
    assert.equal(await later.page.locator('body').evaluate(node => node.classList.contains('session67-activity')), false);
    assert.deepEqual(await later.page.locator('.prescribed-session-tools > button').evaluateAll(nodes => nodes.map(node => getComputedStyle(node).order)), ['0', '0', '0']);
    await close(later);

    // Every correct oral item must finish feedback before the next prompt/intro.
    const reading = await open('lesson-17-18-gawain-5'); await start(reading.page);
    for (let index = 0; index < 5; index++) {
      await hold(reading.page); await reading.page.locator('#oral-action').click();
      await reading.page.waitForFunction(expected => window.played.includes(expected), correct);
      assert.deepEqual(await played(reading.page), [correct]);
      assert.equal(await reading.page.locator('.oral-word').textContent(), fixtures[0].data.items[index].label);
      await end(reading.page);
      const sources = await played(reading.page);
      assert.equal(sources.length, 2);
      assert.ok(sources[1].endsWith(index === 4 ? '/01_activity_intro.mp3' : ['','/04_item_02_payong_read_prompt.mp3','/06_item_03_pitaka_read_prompt.mp3','/08_item_04_riles_read_prompt.mp3','/10_item_05_puso_read_prompt.mp3'][index + 1]));
      await end(reading.page);
    }
    assert.equal(await reading.page.locator('.syllable-grid').count(), 1); await close(reading);

    // Pause during feedback cannot release a stale next prompt.
    const paused = await open('lesson-17-18-gawain-5'); await start(paused.page); await hold(paused.page);
    await paused.page.locator('#oral-action').click(); await paused.page.waitForFunction(expected => played.includes(expected), correct);
    await paused.page.locator('[id$="-audio-settings-btn"]').click(); await paused.page.waitForTimeout(30);
    assert.deepEqual(await played(paused.page), [correct]);
    await paused.page.locator('[id$="-resume"]').click(); await paused.page.waitForTimeout(30);
    assert.ok((await played(paused.page)).at(-1).endsWith('/04_item_02_payong_read_prompt.mp3')); await close(paused);

    // Gawain 6: feedback, next oral screen, exact instruction; word-only listening.
    for (const answers of [[], ['pu', 'ko', 'ro', 'ro']]) {
      const test = await open('lesson-17-18-gawain-6', {phase: 'oral'}, {answers}); await start(test.page);
      await test.page.locator('#oral').click(); await test.page.locator('#answer').waitFor();
      await test.page.waitForTimeout(30); await hold(test.page);
      await test.page.locator('#answer').fill(answers.length ? 'ri' : 'pu');
      await test.page.locator('#answerForm button').click();
      await test.page.waitForFunction(source => played.includes(source), writtenCorrect);
      assert.deepEqual(await played(test.page), [writtenCorrect]);
      assert.equal(await test.page.locator('#oral').count(), 0);
      await end(test.page);
      if (answers.length) {
        assert.equal(test.completions(), 1);
      } else {
        assert.equal(await test.page.locator('.oral-word').textContent(), 'PAKO');
        assert.deepEqual(await played(test.page), [writtenCorrect, prefix + 'LESSON_17_18/GAWAIN_6/babasahin_pako_tts.mp3']);
        await end(test.page); await test.page.evaluate(() => {played = []; audioMode = 'end';});
        await test.page.locator('#listen-help').click(); await test.page.waitForTimeout(30);
        assert.deepEqual(await played(test.page), [prefix + 'LESSON_17_18/GAWAIN_6/pako_tts.mp3']);
      }
      assert.equal(await test.page.locator('#retry-audio').count(), 0); await close(test);
    }
    const failed = await open('lesson-17-18-gawain-6'); await start(failed.page);
    await failed.page.evaluate(() => audioMode = 'reject'); await failed.page.locator('#listen-help').click();
    await failed.page.waitForTimeout(30);
    assert.match(await failed.page.locator('#status').textContent(), /Hindi ma-play/);
    assert.deepEqual(await failed.page.locator('#app button').allTextContents(), ['BASAHIN', 'PAKINGGAN']);
    await failed.page.evaluate(() => {audioMode = 'end'; speechFailure = true;});
    await failed.page.locator('#oral').click(); await failed.page.waitForTimeout(30);
    assert.equal(failed.state().phase || 'oral', 'oral');
    assert.equal(failed.state().reading_attempts || 0, 0); await close(failed);

    // Cancelling written feedback leaves usable oral controls and no stale audio.
    for (const suffix of ['-audio-settings-btn', '-mic-toggle']) {
      const test = await open('lesson-17-18-gawain-6'); await start(test.page);
      await test.page.locator('#oral').click(); await test.page.locator('#answer').waitFor();
      await test.page.waitForTimeout(30); await hold(test.page);
      await test.page.locator('#answer').fill('pu'); await test.page.locator('#answerForm button').click();
      await test.page.waitForFunction(source => played.includes(source), writtenCorrect);
      await test.page.locator(`[id$="${suffix}"]`).click(); await test.page.waitForTimeout(30);
      assert.deepEqual(await played(test.page), [writtenCorrect]);
      if (suffix === '-audio-settings-btn') await test.page.locator('[id$="-resume"]').click();
      else await test.page.locator('[id$="-mic-toggle"]').click();
      await test.page.waitForTimeout(30); await end(test.page);
      assert.equal(await test.page.locator('.oral-word').textContent(), 'PAKO');
      assert.deepEqual(await test.page.locator('#app button').allTextContents(), ['BASAHIN', 'PAKINGGAN']);
      await close(test);
    }

    // Gawain 6: the backend's USA allowance takes the normal written/progress path.
    const usa = await open('lesson-17-18-gawain-6'); await start(usa.page);
    await usa.page.evaluate(() => speechTranscript = 'USA');
    await usa.page.locator('#oral').click(); await usa.page.locator('#answer').waitFor();
    assert.equal(usa.state().phase, 'written'); assert.equal(usa.state().reading_attempts, 0);
    assert.ok(usa.writes.every(body => body.answers.length === 0 && !body.candidate_answer));
    await usa.page.locator('#answer').fill('pa'); await usa.page.locator('#answerForm button').click();
    await usa.page.waitForFunction(() => document.querySelector('#status')?.textContent === 'Subukan muli.');
    assert.equal(usa.state().written_attempts, 1); assert.equal(usa.completions(), 0);
    await usa.page.locator('#answer').fill('pu'); await usa.page.locator('#answerForm button').click();
    await usa.page.waitForFunction(() => document.querySelector('.oral-word')?.textContent === 'PAKO');
    for (let attempt = 1; attempt <= 3; attempt++) {
      await Promise.all([
        usa.page.waitForResponse(response => new URL(response.url()).pathname === '/progress/' &&
          response.request().postDataJSON().state?.reading_attempts === attempt),
        usa.page.locator('#oral').click(),
      ]);
      await usa.page.waitForFunction(() => document.querySelector('#status')?.textContent === 'Subukan muli.');
      assert.equal(usa.state().reading_attempts, attempt); assert.equal(usa.state().phase, 'oral');
      assert.ok(await usa.page.locator('#oral').isEnabled());
    }
    await usa.page.evaluate(() => speechFailure = true); await usa.page.locator('#oral').click();
    await usa.page.waitForFunction(() => document.querySelector('#status')?.textContent === 'Provider unavailable');
    assert.equal(usa.state().reading_attempts, 3); assert.equal(usa.state().phase, 'oral');
    await usa.page.evaluate(() => {speechFailure = false; speechTranscript = 'PAKO';});
    await usa.page.locator('#oral').click(); await usa.page.locator('#answer').waitFor();
    assert.equal(usa.state().reading_attempts, 0);
    for (const [index, word, answer] of [[1, 'PAKO', 'ko'], [2, 'PARUPARO', 'ro'], [3, 'ROSAS', 'ro'], [4, 'KARITON', 'ri']]) {
      if (index > 1) {
        await usa.page.waitForFunction(expected => document.querySelector('.oral-word')?.textContent === expected, word);
        await usa.page.evaluate(() => speechTranscript = 'USA'); await usa.page.locator('#oral').click();
        await usa.page.waitForFunction(() => document.querySelector('#status')?.textContent === 'Subukan muli.');
        assert.equal(usa.state().reading_attempts, 1); assert.equal(usa.state().phase, 'oral');
        await usa.page.evaluate(word => speechTranscript = word, word);
        await usa.page.locator('#oral').click(); await usa.page.locator('#answer').waitFor();
      }
      await usa.page.locator('#answer').fill(answer); await usa.page.locator('#answerForm button').click();
    }
    await usa.page.locator('.done').waitFor(); assert.equal(usa.completions(), 1);
    assert.deepEqual(usa.writes.at(-1).answers, ['pu', 'ko', 'ro', 'ro', 'ri']);
    const prompts = (await played(usa.page)).filter(source => /\/babasahin_/.test(source));
    assert.deepEqual(prompts, ['pusa', 'pako', 'paruparo', 'rosas', 'kariton'].map(word =>
      prefix + `LESSON_17_18/GAWAIN_6/babasahin_${word}_tts.mp3`));
    await close(usa);

    // Each requested STT spelling follows the normal Gawain 6 written path.
    for (const [index, transcript] of [[1, 'paco'], [3, 'RoSeS'], [4, 'CARTON']]) {
      const answers = ['pu', 'ko', 'ro', 'ro'].slice(0, index);
      const test = await open('lesson-17-18-gawain-6', {phase: 'oral', reading_attempts: 2}, {answers});
      await start(test.page);
      await test.page.evaluate(value => speechTranscript = value, transcript);
      await test.page.locator('#oral').click(); await test.page.locator('#answer').waitFor();
      assert.equal(test.state().phase, 'written'); assert.equal(test.state().reading_attempts, 0);
      assert.ok(test.writes.every(body => body.answers.length === index && !body.candidate_answer));
      await test.page.waitForTimeout(30); await hold(test.page);
      await test.page.locator('#answer').fill(['pu', 'ko', 'ro', 'ro', 'ri'][index]);
      await test.page.locator('#answerForm button').click();
      await test.page.waitForFunction(source => played.includes(source), writtenCorrect);
      assert.deepEqual(await played(test.page), [writtenCorrect]);
      await end(test.page);
      if (index === 4) assert.equal(test.completions(), 1);
      else assert.equal(test.writes.at(-1).answers.length, index + 1);
      await close(test);
    }

    // Oral PAKINGGAN must contain only the displayed word for every item.
    for (const [index, word] of ['pana', 'pisara', 'palaka', 'pito', 'regalo'].entries()) {
      const test = await open('lesson-17-18-gawain-9', {phase: 'oral_reading', current_item_index: index, oral_attempts: {[index]: 3}});
      await start(test.page); await test.page.evaluate(() => played = []);
      await test.page.locator('#listen').click(); await test.page.waitForTimeout(30);
      assert.deepEqual(await played(test.page), [prefix + `LESSON_17_18/GAWAIN_9/${word}_tts.mp3`]); await close(test);
    }

    // Gawain 1 also follows real media-ended events into a prompt and matching.
    for (const index of [0, 4]) {
      const test = await open('lesson-17-18-gawain-5', {phase: 'oral_reading', oral_index: index}, {realAudio: true});
      await start(test.page); await test.page.evaluate(() => {played = []; nativeEvents = [];});
      await test.page.locator('#oral-action').click();
      const following = prefix + 'LESSON_17_18/GAWAIN_5/' + (index === 4 ? '01_activity_intro.mp3' : '04_item_02_payong_read_prompt.mp3');
      await test.page.waitForFunction(source => nativeEvents.some(event => event.src === source && event.event === 'ended'), following);
      assert.deepEqual(await played(test.page), [correct, following]);
      if (index === 4) assert.equal(await test.page.locator('.syllable-grid').count(), 1);
      else assert.equal(await test.page.locator('.oral-word').textContent(), fixtures[0].data.items[1].label);
      await close(test);
    }

    // Real browser media decoding and ended events for every new/scoped clip.
    const native = await open('lesson-17-18-gawain-6', {}, {realAudio: true});
    await start(native.page);
    await native.page.locator('#oral').click(); await native.page.locator('#answer').waitFor();
    await native.page.locator('#answer').fill('pu'); await native.page.locator('#answerForm button').click();
    await native.page.waitForFunction(() => document.querySelector('.oral-word')?.textContent === 'PAKO');
    await native.page.waitForFunction(() => players.every(player => player.paused));
    assert.deepEqual(native.missing, []);
    assert.doesNotMatch(await native.page.locator('#status').textContent(), /Hindi/, JSON.stringify(await native.page.evaluate(() => nativeEvents)));
    const assets = [correct, writtenCorrect, prefix + 'LESSON_17_18/GAWAIN_5/01_activity_intro.mp3',
      ...['pusa', 'pako', 'paruparo', 'rosas', 'kariton'].map(word => prefix + `LESSON_17_18/GAWAIN_6/babasahin_${word}_tts.mp3`),
      ...['pusa', 'pako', 'paruparo', 'rosas', 'kariton'].map(word => prefix + `LESSON_17_18/GAWAIN_6/${word}_tts.mp3`),
      ...['pana', 'pisara', 'palaka', 'pito', 'regalo'].map(word => prefix + `LESSON_17_18/GAWAIN_9/${word}_tts.mp3`)];
    const playback = await native.page.evaluate(async assets => {
      const results = [];
      for (const source of assets) {
        const player = new Audio(source);
        const ended = new Promise((resolve, reject) => {player.onended = resolve; player.onerror = () => reject(Error(source));});
        await player.play(); await ended; results.push({source, duration: player.duration});
      }
      return results;
    }, assets);
    assert.equal(playback.length, assets.length); assert.ok(playback.every(item => item.duration > 0 && item.duration < 15));
    await close(native);
    console.log(`${checks} Session 6–7 browser scenarios passed; ${assets.length} MP3s decoded and played to completion.`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
