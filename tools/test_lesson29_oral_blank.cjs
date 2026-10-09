// Check the activity's capture requests, phase transitions and name correction.
// Speech capture and server replies are controlled; backend grading has Django tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const source = fs.readFileSync(path.resolve(__dirname,
  '../pabasa_site/pabasa_app/static/pabasa_app/js/prescribed_oral_sentence_blank_lesson29_activity1.js'), 'utf8');
const items = [
  {before:'Matt is on the ', answer:'list', after:'.'},
  {before:'The ', answer:'last', after:' man is Matt.'},
  {before:'The ', answer:'stem', after:' is green.'},
  {before:'Matt sets the grain ', answer:'mill', after:'.'},
  {before:'The city is covered in ', answer:'fog', after:'.'},
].map(item => ({...item, word_length:item.answer.length, tts_word:item.answer, image_url:''}));

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checks = 0;
  try {
    async function runCase(index, phase, attempts) {
      const page = await browser.newPage(), saves = [], errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const data = {items, recognition_hints:'list last stem mill fog',
        progress:{state:{phase, current_item:index, completed_items:index}},
        progress_url:'/progress', completion_url:'/complete',
        transcribe_url:'/transcribe', read_aloud_url:'/audio'};
      await page.addInitScript(transcripts => {
        window.captureCalls = [];
        window.debugEvents = [];
        window.Basahin = {
          bindActivity(button, handler) { button.addEventListener('click', handler); },
          async read(fields, options) {
            window.captureCalls.push({fields, continuous:options.continuous});
            const transcript = transcripts.shift();
            return {transcript, raw_transcript:transcript, complete:true};
          },
          cancelAll() {},
        };
        window.addEventListener('session13-prescribed-s13l29g1-debug', event => {
          if (event.detail.transcript) window.debugEvents.push(event.detail);
        });
      }, attempts.map(attempt => attempt.raw));
      await page.route('http://localhost:9876/**', async route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/') return route.fulfill({contentType:'text/html', body:`<!doctype html>
          <div id="app"></div><div id="lesson29a1-stage"></div><div id="lesson29a1-start"></div>
          <button id="lesson29a1-go"></button><button id="lesson29a1-later"></button>
          <script id="prescribed-activity-data" type="application/json">${JSON.stringify(data)}</script>
          <script src="/activity.js"></script>`});
        if (url.pathname === '/activity.js') return route.fulfill({contentType:'text/javascript', body:source});
        if (url.pathname === '/progress') {
          const reply = attempts[saves.length].reply;
          saves.push(route.request().postDataJSON());
          return route.fulfill({json:{success:true, ...reply}});
        }
        return route.fulfill({json:{success:false}}); // Narration can be unavailable.
      });
      try {
        await page.goto('http://localhost:9876/');
        for (let i = 0; i < attempts.length; i++) {
          const attempt = attempts[i];
          await page.locator('#read').click();
          await page.waitForFunction(count => window.debugEvents.length === count
            && !document.getElementById('read').disabled, i + 1);
          const captured = await page.evaluate(index => window.captureCalls[index], i);
          assert.equal(captured.fields.target_text, attempt.target);
          assert.equal(captured.fields.mode, attempt.mode);
          assert.equal(captured.fields.language, 'English');
          assert.equal(captured.continuous, false);
          assert.equal(saves[i].heard, attempt.heard);
          assert.equal(saves[i].action, attempt.mode === 'word' ? 'answer' : 'sentence_reading');
          const debug = await page.evaluate(index => window.debugEvents[index], i);
          assert.equal(debug.transcript, attempt.heard);
          assert.ok(debug.raw.includes(attempt.raw));
          checks++;
        }
        assert.deepEqual(errors, []);
      } finally { await page.close(); }
    }
    const reply = (phase, index, accepted) => ({accepted, progress:{state:{phase, current_item:index, completed_items:index}}});
    for (let index = 0; index < items.length; index++) {
      const word = items[index].answer;
      await runCase(index, 'answering', [{raw:word, heard:word, target:word, mode:'word', reply:reply('sentence_reading', index, true)}]);
    }
    await runCase(0, 'answering', [
      {raw:'Matt is on the list.', heard:'Matt is on the list.', target:'list', mode:'word', reply:reply('answering', 0, false)},
      {raw:'list', heard:'list', target:'list', mode:'word', reply:reply('sentence_reading', 0, true)},
      {raw:'Mad is on the list.', heard:'Matt is on the list.', target:'Mat is on the list.', mode:'sentence', reply:reply('answering', 1, true)},
      {raw:'last', heard:'last', target:'last', mode:'word', reply:reply('sentence_reading', 1, true)},
    ]);
    for (const name of ['Matt', 'mat', 'math', 'mad']) {
      await runCase(1, 'sentence_reading', [{raw:`The last man is ${name}.`, heard:'The last man is Matt.',
        target:'The last man is Mat.', mode:'sentence', reply:reply('answering', 2, true)}]);
    }
    await runCase(2, 'sentence_reading', [{raw:'The math is green.', heard:'The math is green.',
      target:'The stem is green.', mode:'sentence', reply:reply('sentence_reading', 2, false)}]);
    console.log(`PASS: ${checks} capture and transcript checks; word retry, both phase transitions, Matt aliases and unrelated sentences.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
