// Run with installed Chrome and BASAHIN_PLAYWRIGHT_PATH pointing to playwright-core.
// Executes the actual lesson scripts, replacing microphone/STT with fixed responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.BASAHIN_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '../pabasa_site/pabasa_app');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  let checked = 0;
  try {
    for (const [file, dataId] of [
      ['session_5_lesson_14_gawain_4_page.html', 'gawain4-data'],
      ['session_5_lesson_15_gawain_3_page.html', 'gawain3-data'],
    ]) {
      const template = fs.readFileSync(path.join(root, 'templates/pabasa_app', file), 'utf8');
      const script = [...template.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
        .map(match => match[1]).find(code => code.includes('async function read(){'))
        .replace(/{%[\s\S]*?%}/g, '/assessment/');
      for (const scenario of [
        {success: true, complete: false, suffix: 'g', accepted: false},
        {success: true, complete: true, suffix: '-different-STT-spelling', accepted: true},
        {success: false, complete: true, suffix: '', accepted: false},
      ]) {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('http://localhost:9876/**', route => route.fulfill({contentType: 'text/html', body: '<main id="app"></main>'}));
        await page.goto('http://localhost:9876/');
        await page.evaluate(({dataId, scenario}) => {
          const data = document.createElement('script');
          data.type = 'application/json'; data.id = dataId;
          data.textContent = JSON.stringify({items: [{text: 'lata'}, {text: 'bata'}], progress_url: '/progress', progress: {state: {}}});
          document.body.append(data);
          window.saves = [];
          window.fetch = async (url, options) => {
            window.saves.push(JSON.parse(options.body));
            return {json: async () => ({success: true})};
          };
          window.Audio = class {
            play() { queueMicrotask(() => this.onended?.()); return Promise.resolve(); }
            pause() {}
          };
          window.Basahin = {
            bindActivity(button, callback) { button.onclick = callback; },
            async read(fields) { return {...scenario, transcript: fields.target_text + scenario.suffix}; },
          };
          window.BasahinButton = {LABEL: 'Basahin'};
        }, {dataId, scenario});
        await page.addScriptTag({content: script});
        await page.locator('#read').click();
        await page.waitForFunction(() => window.saves.length > 0);
        const saved = await page.evaluate(() => window.saves[0].state);
        assert.equal(saved.reading_matches['0'], scenario.accepted, `${file}: ${JSON.stringify(scenario)}`);
        assert.equal(saved.reading_attempts['0'], 1);
        if (scenario.accepted) {
          await page.waitForFunction(() => window.saves.some(save => save.state.current_index === 1));
        } else {
          assert.equal(await page.evaluate(() => window.saves.at(-1).state.current_index), 0);
        }
        assert.deepEqual(errors, []);
        await page.close();
        checked++;
      }
    }
    console.log(`PASS: ${checked} browser grading cases; backend verdict controls saved matches and advancement.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
