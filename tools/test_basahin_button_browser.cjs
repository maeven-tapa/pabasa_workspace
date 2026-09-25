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
        window.BasahinButton.setState(button, 'listening');
        await new Promise(resolve => { window.finishAttempt = resolve; });
        button.disabled = false;
        window.BasahinButton.setState(button, 'idle');
      });
    });
    await page.locator('#read').click();
    await page.evaluate(() => document.getElementById('read').dispatchEvent(new MouseEvent('click', {bubbles: true})));
    assert.equal(await page.evaluate(() => window.attempts), 1);
    const listening = await page.locator('#read').evaluate(button => ({
      text: button.textContent, animation: getComputedStyle(button).animationName,
      background: getComputedStyle(button).backgroundColor, busy: button.getAttribute('aria-busy'),
    }));
    assert.equal(listening.text, 'Nakikinig...');
    assert.equal(listening.animation, 'basahin-listening');
    assert.equal(listening.background, 'rgb(41, 158, 154)');
    assert.equal(listening.busy, 'true');
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
    // Real Chromium MediaRecorder + RMS analyser with synthetic audio.
    const clip = await page.evaluate(async () => {
      const context = new AudioContext(), tone = context.createOscillator(), gain = context.createGain();
      const output = context.createMediaStreamDestination();
      gain.gain.value = 0;
      tone.connect(gain).connect(output); tone.start();
      gain.gain.setValueAtTime(0.2, context.currentTime + 0.9);
      const started = performance.now();
      const audio = await window.Basahin.capture({stream: output.stream});
      const elapsed = performance.now() - started;
      const decoded = await context.decodeAudioData(await audio.arrayBuffer());
      tone.stop(); await context.close();
      return {size: audio.size, elapsed, duration: decoded.duration};
    });
    assert.ok(clip.size > 0); assert.ok(clip.elapsed >= 2300 && clip.elapsed < 4500);
    assert.ok(clip.duration > 2 && clip.duration < 3);
    assert.deepEqual(errors, []);
    if (process.env.BASAHIN_SCREENSHOT) {
      await page.setViewportSize({width: 1000, height: 720});
      await page.evaluate(() => {
        document.querySelector('main').innerHTML = '<h1>Basahin</h1>' + ['idle','listening','processing'].map(state => `<button data-basahin-button id="${state}"></button>`).join('');
        for (const state of ['idle','listening','processing']) {
          const button = document.getElementById(state);
          window.BasahinButton.setState(button, state); button.disabled = state !== 'idle';
        }
      });
      await page.screenshot({path: process.env.BASAHIN_SCREENSHOT});
    }
    console.log('PASS: shared click dispatch, states, animations, reduced motion, re-rendering, mobile layout, hidden buttons and real 2.4-second recording.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
