// Local Chrome pixel checks; no server, credentials, or student data.
// Run with node tools/test_crla_timer_geometry.cjs (playwright and pngjs).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.CRLA_PLAYWRIGHT_PATH || 'playwright');
const {PNG} = require('pngjs');
const root = path.resolve(__dirname, '..');
const reader = fs.readFileSync(path.join(root,
  'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'), 'utf8');
const template = fs.readFileSync(path.join(root,
  'pabasa_site/pabasa_app/templates/pabasa_app/reading_assessment_base.html'), 'utf8');
const geometry = reader.slice(reader.indexOf('function updateStoryReadingTimerGeometry()'),
  reader.indexOf('function resetStoryReadingTimerUi()'));
const observer = reader.match(/new window.ResizeObserver\(updateStoryReadingTimerGeometry\)\.observe\(storyReadingTimer\);/)[0];
const svg = template.match(/<svg class="story-reading-timer"[\s\S]*?<\/svg>/)[0];
const css = template.slice(template.indexOf('        .story-reading-timer {'),
  template.indexOf('        .story-reading-timer-overlay,'));
function blueAt(png, x, y) {
  for (let row = Math.round(y) - 2; row <= Math.round(y) + 2; row++) {
    for (let col = Math.round(x) - 2; col <= Math.round(x) + 2; col++) {
      const offset = (row * png.width + col) * 4;
      if (png.data[offset + 2] > 180 && png.data[offset] < 70) return true;
    }
  }
  return false;
}
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1200, height: 1000}});
    await page.setContent(`<style>${css}
      .card{position:relative;width:800px;height:300px}
      .story-reading-timer-progress{stroke:blue;transition:none}
      .story-reading-timer-track{stroke:#ddd}
      </style><div class="reader-shell is-story-reading"><div class="card">${svg}</div></div>`);
    await page.addScriptTag({content: `const storyReadingTimer = document.getElementById('storyReadingTimer');
      ${geometry}; ${observer}`});
    for (const [width, height] of [[800, 300], [350, 700], [600, 400]]) {
      await page.locator('.card').evaluate((el, size) => {
        el.style.width = size[0] + 'px'; el.style.height = size[1] + 'px';
      }, [width, height]);
      await page.waitForFunction(width => {
        const svg = document.getElementById('storyReadingTimer');
        return svg.viewBox.baseVal.width === width - 14;
      }, width);
      const timer = page.locator('#storyReadingTimer');
      const progress = page.locator('#storyReadingTimerProgress');
      const dims = await timer.evaluate(el => ({width: el.clientWidth, height: el.clientHeight}));
      await progress.evaluate(el => { el.style.strokeDashoffset = '0'; });
      let png = PNG.sync.read(await timer.screenshot());
      assert.ok(blueAt(png, dims.width / 2, 3), 'full timer covers top midpoint');
      assert.ok(blueAt(png, dims.width / 4, 3), 'full timer covers left top edge');
      await progress.evaluate(el => { el.style.strokeDashoffset = '100'; });
      png = PNG.sync.read(await timer.screenshot());
      assert.equal(blueAt(png, dims.width / 2 - 12, 3), false,
        `elapsed timer must retreat from top midpoint at ${width}x${height}`);
      assert.ok(blueAt(png, dims.width / 2 + 12, 3), 'start side stays visible');
      assert.ok(blueAt(png, dims.width - 3, dims.height / 2), 'right edge stays visible');
      await progress.evaluate(el => { el.style.strokeDashoffset = '1000'; });
      png = PNG.sync.read(await timer.screenshot());
      assert.equal(blueAt(png, dims.width - 3, dims.height / 2), false, 'expired timer is empty');
      console.log(`PASS story timer: full, midpoint retreat, empty and resize at ${width}x${height}`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
