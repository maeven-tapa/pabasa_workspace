// Actual verse UI + shared capture, using synthetic audio and provider responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.BASAHIN_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [], requests = [], saves = [];
    page.on('pageerror', error => errors.push(error.message));
    const state = {phase:'reading', item_index:0, verse_index:0, attempts:0, selected:[]};
    const fixture = {
      transcribe_url:'/api/reading/transcribe/', progress_url:'/progress/',
      progress:{state}, items:[{title:'The Cat in the Hat', lines:[
        {text:'The cat wore a hat,', words:['The','cat','wore','a','hat'].map((text,index) => ({text,id:`w0-0-${index}`}))},
        {text:'He sat on a mat,', words:['He','sat','on','a','mat'].map((text,index) => ({text,id:`w0-1-${index}`}))},
      ]}],
    };
    await page.route('http://localhost:9876/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/') return route.fulfill({contentType:'text/html', body:`<!doctype html>
        <link rel="stylesheet" href="/css/basahin.css">
        <script src="/js/basahin_button.js"></script><script src="/js/basahin.js"></script>
        <div id="app"></div><script id="prescribed-activity-data" type="application/json">${JSON.stringify(fixture)}</script>
        <script src="/js/prescribed_rhyming_verses_lesson27_activity1.js"></script>`});
      if (url.pathname === '/api/reading/transcribe/') {
        requests.push(route.request().postDataBuffer().toString());
        assert.equal(saves.filter(save => save.action === 'verse_read').length, requests.length <= 2 ? 0 : 1, 'Only completed verses save activity attempts');
        if (requests.length === 2) {
          assert.deepEqual(await page.locator('.lesson27-verse').first().locator('.is-read').allTextContents(), ['The', 'cat']);
          assert.equal(await page.locator('.lesson27-verse').first().locator('.lesson27-unread').textContent(), 'wore a hat,');
        }
        return route.fulfill({json:{success:true, complete:requests.length >= 2,
          transcript:requests.length === 1 ? 'The cat' : requests.length === 2 ? 'wore a hat' : 'The cat wore a hat',
          current_syllable_index:requests.length === 1 ? 2 : 5, word_syllable_ranges:[[0,1],[1,2],[2,3],[3,4],[4,5]], syllable_context:''}});
      }
      if (url.pathname === '/progress/') {
        const payload = route.request().postDataJSON();
        saves.push(payload);
        if (payload.action === 'verse_progress') Object.assign(state, {verse_syllable_index:payload.current_syllable_index,verse_word_index:payload.current_syllable_index});
        if (payload.action === 'verse_read') Object.assign(state, {verse_index:1,verse_syllable_index:0,verse_word_index:0});
        return route.fulfill({json:{success:true, progress:{state}}});
      }
      return route.fulfill({contentType:url.pathname.endsWith('.js') ? 'text/javascript' : 'text/css',
        body:fs.readFileSync(path.join(root, url.pathname))});
    });
    await page.addInitScript(() => {
      window.Audio = class extends EventTarget {
        play() { queueMicrotask(() => this.dispatchEvent(new Event('ended'))); return Promise.resolve(); }
        pause() { this.dispatchEvent(new Event('pause')); }
      };
    });
    await page.goto('http://localhost:9876/');
    await page.evaluate(() => {
      const context = new AudioContext();
      window.playedPrompt = [];
      window.testStreams = [];
      const originalAudio = window.Audio;
      window.Audio = class extends originalAudio {
        constructor(url) { super(); window.playedPrompt.push(decodeURIComponent(url)); }
      };
      navigator.mediaDevices.getUserMedia = async () => {
        const tone = context.createOscillator(), gain = context.createGain();
        const output = context.createMediaStreamDestination();
        gain.gain.value = 0;
        tone.connect(gain).connect(output); tone.start();
        gain.gain.setValueAtTime(0.2, context.currentTime + 1.5);
        gain.gain.setValueAtTime(0, context.currentTime + 2.7);
        window.testStreams.push(output.stream);
        return output.stream;
      };
    });
    assert.equal(await page.locator('#record-verse').textContent(), 'Read');
    await page.locator('#record-verse').click();
    await page.waitForFunction(() => window.playedPrompt.some(url => url.includes('read the rest of the verse')), {timeout:15000});
    assert.equal(requests.length, 1, 'A silent pause after partial reading must stop the recorder');
    assert.equal(saves.filter(save => save.action === 'verse_read').length, 0);
    assert.ok(await page.evaluate(() => window.testStreams[0].getTracks().every(track => track.readyState === 'ended')));
    assert.deepEqual(await page.locator('.lesson27-verse').first().locator('.is-read').allTextContents(), ['The','cat']);
    await page.locator('#record-verse').click();
    await page.waitForFunction(() => document.querySelector('.lesson27-prompt')?.textContent.includes('verse 2'), {timeout:15000});
    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.match(request, /name="language"\r\n\r\nEnglish/);
      assert.match(request, /name="mode"\r\n\r\nsentence/);
      assert.match(request, /name="target_text"\r\n\r\nThe cat wore a hat,/);
    }
    assert.match(requests[1], /name="current_syllable_index"\r\n\r\n2/);
    assert.deepEqual(saves.filter(save => save.action === 'verse_read'), [{action:'verse_read', item_index:0, verse_index:0, success:true}]);
    assert.equal(saves.filter(save => save.action === 'verse_progress').length, 2);
    assert.equal(await page.locator('.lesson27-verse').first().locator('.is-read').count(), 5);
    assert.equal(await page.locator('#record-verse').textContent(), 'Read');
    assert.deepEqual(errors, []);
    Object.assign(state, {verse_index:0,verse_syllable_index:0,verse_word_index:0});
    await page.reload();
    await page.evaluate(() => {
      const context = new AudioContext();
      window.playedPrompt = [];
      const originalAudio = window.Audio;
      window.Audio = class extends originalAudio {
        constructor(url) { super(); window.playedPrompt.push(decodeURIComponent(url)); }
      };
      navigator.mediaDevices.getUserMedia = async () => {
        const tone = context.createOscillator(), gain = context.createGain(), output = context.createMediaStreamDestination();
        gain.gain.value = 0;
        tone.connect(gain).connect(output); tone.start();
        gain.gain.setValueAtTime(0.2,context.currentTime+1.5);
        gain.gain.setValueAtTime(0,context.currentTime+2.3);
        gain.gain.setValueAtTime(0.2,context.currentTime+3.3);
        gain.gain.setValueAtTime(0,context.currentTime+4.1);
        return output.stream;
      };
    });
    await page.locator('#record-verse').click();
    await page.waitForFunction(() => document.querySelector('.lesson27-prompt')?.textContent.includes('verse 2'), {timeout:15000});
    assert.equal(requests.length, 3, 'A one-second pause stays in one recording');
    assert.equal((await page.evaluate(() => window.playedPrompt)).filter(url => url.includes('read the rest of the verse')).length, 0);
    assert.equal(saves.filter(save => save.action === 'verse_read').length, 2);
    assert.deepEqual(errors, []);
    console.log('PASS: real capture stops after partial-reading silence, releases the mic, prompts, and resumes with one completed attempt.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
