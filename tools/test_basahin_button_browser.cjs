// Browser integration check. Install playwright-core separately, or set
// BASAHIN_PLAYWRIGHT_PATH to its absolute module path. Uses installed Chrome.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.BASAHIN_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '../pabasa_site/pabasa_app');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1000, height: 720}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://localhost:9876/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/') {
        await route.fulfill({contentType: 'text/html', body: `<!doctype html><html><head>
          <link rel="stylesheet" href="/css/basahin.css">
          <script src="/js/basahin_button.js"></script><script src="/js/basahin.js"></script>
          <style>body{padding:36px;background:#eff9f6}main{display:grid;gap:30px;justify-items:start}
          .button:disabled{background:gray!important;box-shadow:none!important;transform:none!important}
          </style></head><body><main><button class="button" id="read" data-basahin-button>Basahin Ngayon</button>
          <div id="dynamic"></div></main></body></html>`});
        return;
      }
      const file = path.join(root, 'static/pabasa_app', url.pathname);
      const type = file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'text/javascript' : 'font/ttf';
      await route.fulfill({contentType: type, body: fs.readFileSync(file)});
    });
    await page.goto('http://localhost:9876/');
    await page.waitForFunction(() => document.querySelector('#read [data-basahin-label]')?.textContent === 'Basahin');
    assert.equal(await page.locator('#read i').count(), 1);
    await page.evaluate(() => {
      window.attempts = 0;
      const button = document.getElementById('read');
      window.Basahin.bindActivity(button, async () => {
        window.attempts++;
        button.disabled = true;
        window.BasahinButton.setState(button, 'waiting');
        await new Promise(resolve => { window.finishAttempt = resolve; });
        button.disabled = false;
        window.BasahinButton.setState(button, 'idle');
      });
    });
    await page.locator('#read').click();
    await page.evaluate(() => document.getElementById('read').dispatchEvent(new MouseEvent('click', {bubbles: true})));
    assert.equal(await page.evaluate(() => window.attempts), 1);
    assert.equal(await page.locator('#read').textContent(), 'Magsalita...');
    assert.equal(await page.locator('#read').evaluate(button => getComputedStyle(button).animationName), 'none');
    await page.evaluate(() => window.BasahinButton.setState(document.getElementById('read'), 'listening'));
    // Merely saying "listening" must not trigger a pulse without VAD evidence.
    assert.equal(await page.locator('#read').evaluate(button => getComputedStyle(button).animationName), 'none');
    await page.evaluate(() => window.BasahinButton.setSpeech(document.getElementById('read'), true));
    const listening = await page.locator('#read').evaluate(button => ({
      text: button.textContent, animation: getComputedStyle(button).animationName,
      background: getComputedStyle(button).backgroundColor, busy: button.getAttribute('aria-busy'),
    }));
    assert.equal(listening.text, 'Nakikinig...');
    assert.equal(listening.animation, 'basahin-listening');
    assert.equal(listening.background, 'rgb(41, 158, 154)');
    assert.equal(listening.busy, 'true');
    await page.emulateMedia({reducedMotion: 'reduce'});
    assert.equal(await page.locator('#read').evaluate(button => getComputedStyle(button).animationName), 'none');
    await page.emulateMedia({reducedMotion: 'no-preference'});
    await page.evaluate(() => window.BasahinButton.setState(document.getElementById('read'), 'processing'));
    assert.equal(await page.locator('#read i').evaluate(icon => getComputedStyle(icon).animationName), 'basahin-spin');
    await page.emulateMedia({reducedMotion: 'reduce'});
    assert.equal(await page.locator('#read i').evaluate(icon => getComputedStyle(icon).animationName), 'none');
    await page.evaluate(() => window.finishAttempt());
    await page.waitForFunction(() => document.getElementById('read').textContent === 'Basahin');
    await page.emulateMedia({reducedMotion: 'no-preference'});
    // Old activity updates may replace the button's children; the shared view
    // must restore one icon/label without losing its registered workflow.
    await page.evaluate(() => { document.getElementById('read').textContent = 'Pinoproseso...'; });
    await page.waitForFunction(() => document.querySelector('#read [data-basahin-label]')?.textContent === 'Sinusuri...');
    assert.equal(await page.locator('#read i').count(), 1);
    await page.evaluate(() => {
      const slot = document.getElementById('dynamic');
      slot.innerHTML = '<button id="replacement" data-basahin-button>Basahin ang Salita</button>';
      window.Basahin.bindActivity(slot.firstChild, () => { window.replacementClicked = true; });
    });
    await page.locator('#replacement').click();
    assert.equal(await page.evaluate(() => window.replacementClicked), true);
    await page.evaluate(() => { document.getElementById('replacement').textContent = '🔊 Pakinggan muna'; });
    await page.waitForFunction(() => document.getElementById('replacement').dataset.basahinState === 'model');
    assert.equal(await page.locator('#replacement').textContent(), 'Pakinggan muna');
    await page.setViewportSize({width: 375, height: 720});
    assert.ok((await page.locator('#read').boundingBox()).width <= 303);
    await page.evaluate(() => { document.getElementById('read').hidden = true; });
    assert.equal(await page.locator('#read').isVisible(), false);
    // Exercise read -> create -> capture with a real RMS analyser and recorder.
    // A synthetic tone stands in for voice; there is no live Google request.
    const clip = await page.evaluate(async () => {
      const context = new AudioContext(), tone = context.createOscillator(), gain = context.createGain();
      const output = context.createMediaStreamDestination();
      gain.gain.value = 0;
      tone.connect(gain).connect(output); tone.start();
      gain.gain.setValueAtTime(0.2, context.currentTime + 1.6);
      gain.gain.setValueAtTime(0, context.currentTime + 2.3);
      const started = performance.now();
      const button = document.getElementById('read'); button.hidden = false;
      const nativeRecorder = window.MediaRecorder, getUserMedia = navigator.mediaDevices.getUserMedia;
      let recordings = 0, recorder, recordingStarted, decoded, size;
      window.MediaRecorder = class extends nativeRecorder {
        constructor(...args) { super(...args); recordings++; recorder = this; }
        start(...args) { recordingStarted = performance.now(); return super.start(...args); }
      };
      navigator.mediaDevices.getUserMedia = async () => output.stream;
      const snapshot = () => ({recordings, state: button.dataset.basahinState,
        animation: getComputedStyle(button).animationName, recorderState: recorder?.state});
      const waitUntil = async condition => {
        const deadline = performance.now() + 5000;
        while (!condition()) {
          if (performance.now() > deadline) throw new Error('Speech state did not change in time.');
          await new Promise(resolve => setTimeout(resolve, 20));
        }
      };
      try {
        const reading = window.Basahin.read({target_text: 'bata'}, {button, transcribe: async audio => {
          size = audio.size; decoded = await context.decodeAudioData(await audio.arrayBuffer());
          return {success: true, complete: true, transcript: 'bata'};
        }});
        await waitUntil(() => button.dataset.basahinState === 'waiting');
        const waiting = snapshot();
        await waitUntil(() => button.dataset.basahinSpeaking === 'true');
        const speaking = snapshot();
        await waitUntil(() => button.dataset.basahinSpeaking === 'false');
        const quiet = snapshot();
        await reading;
        return {size, elapsed: performance.now() - started, recordingDelay: recordingStarted - started,
          duration: decoded.duration, waiting, speaking, quiet, final: snapshot()};
      } finally {
        window.MediaRecorder = nativeRecorder; navigator.mediaDevices.getUserMedia = getUserMedia;
        tone.stop(); await context.close();
      }
    });
    assert.equal(clip.waiting.recordings, 0); assert.equal(clip.waiting.animation, 'none');
    assert.equal(clip.speaking.recordings, 1); assert.equal(clip.speaking.animation, 'basahin-listening');
    assert.equal(clip.quiet.animation, 'none'); assert.equal(clip.quiet.recorderState, 'recording');
    assert.equal(clip.final.animation, 'none'); assert.equal(clip.final.state, 'idle');
    assert.ok(clip.size > 0); assert.ok(clip.recordingDelay >= 1500);
    assert.ok(clip.elapsed >= 3900 && clip.elapsed < 6000);
    assert.ok(clip.duration > 2 && clip.duration < 3);
    const englishLabels = await page.evaluate(() => {
      const button = document.createElement('button');
      button.dataset.basahinLanguage = 'English';
      document.body.append(button);
      const labels = ['idle','calibrating','waiting','listening','processing'].map(state => {
        window.BasahinButton.setState(button, state);
        return button.textContent;
      });
      button.remove();
      return labels;
    });
    assert.deepEqual(englishLabels, ['Read','Please wait...','Speak now...','Listening...','Checking...']);
    assert.deepEqual(errors, []);
    if (process.env.BASAHIN_SCREENSHOT) {
      await page.setViewportSize({width: 1000, height: 720});
      await page.evaluate(() => {
        document.querySelector('main').innerHTML = '<h1>Basahin</h1>' + ['idle','waiting','listening','processing'].map(state => `<button data-basahin-button id="${state}"></button>`).join('');
        for (const state of ['idle','waiting','listening','processing']) {
          const button = document.getElementById(state);
          window.BasahinButton.setState(button, state); button.disabled = state !== 'idle';
          window.BasahinButton.setSpeech(button, state === 'listening');
        }
      });
      await page.screenshot({path: process.env.BASAHIN_SCREENSHOT});
    }
    console.log('PASS: shared clicks, VAD-gated recording and pulse, quiet pauses, reduced motion, re-rendering, mobile layout and real 2.4-second recording.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
