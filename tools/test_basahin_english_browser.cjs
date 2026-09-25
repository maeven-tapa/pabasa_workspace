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
        {text:'The cat wore a hat,', words:[]}, {text:'He sat on a mat,', words:[]},
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
        assert.equal(saves.length, 0, 'Partial clips must not save activity attempts');
        return route.fulfill({json:{success:true, complete:requests.length === 2,
          transcript:requests.length === 1 ? 'The cat' : 'wore a hat',
          current_syllable_index:requests.length === 1 ? 2 : 5, syllable_context:''}});
      }
      if (url.pathname === '/progress/') {
        saves.push(route.request().postDataJSON());
        return route.fulfill({json:{success:true, progress:{state:{...state, verse_index:1}}}});
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
      const context = new AudioContext(), tone = context.createOscillator(), gain = context.createGain();
      const output = context.createMediaStreamDestination();
      gain.gain.value = 0;
      tone.connect(gain).connect(output); tone.start();
      gain.gain.setValueAtTime(0.2, context.currentTime + 1.5);
      navigator.mediaDevices.getUserMedia = async () => output.stream;
    });
    assert.equal(await page.locator('#record-verse').textContent(), 'Read');
    await page.locator('#record-verse').click();
    await page.waitForFunction(() => document.querySelector('.lesson27-prompt')?.textContent.includes('verse 2'), {timeout:15000});
    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.match(request, /name="language"\r\n\r\nEnglish/);
      assert.match(request, /name="mode"\r\n\r\nsentence/);
      assert.match(request, /name="target_text"\r\n\r\nThe cat wore a hat,/);
    }
    assert.match(requests[1], /name="current_syllable_index"\r\n\r\n2/);
    assert.deepEqual(saves, [{action:'verse_read', item_index:0, verse_index:0, success:true}]);
    assert.equal(await page.locator('#record-verse').textContent(), 'Read');
    assert.deepEqual(errors, []);
    console.log('PASS: verse UI sends English sentence clips, carries progress and saves one completed attempt.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
