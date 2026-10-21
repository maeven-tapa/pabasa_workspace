// Isolated local audio fixtures; no accounts, student audio, or live requests.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const template = fs.readFileSync('pabasa_site/pabasa_app/templates/pabasa_app/courses.html', 'utf8');
const helpers = template.slice(template.indexOf('    const studentProgressRetellGrades = new Map();'),
    template.indexOf('    // Existing course student-progress actions'));
function wave(seconds) {
    const bytes = Buffer.alloc(44 + 32000 * seconds);
    bytes.write('RIFF'); bytes.writeUInt32LE(bytes.length - 8, 4); bytes.write('WAVEfmt ', 8);
    bytes.writeUInt32LE(16, 16); bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(1, 22);
    bytes.writeUInt32LE(16000, 24); bytes.writeUInt32LE(32000, 28);
    bytes.writeUInt16LE(2, 32); bytes.writeUInt16LE(16, 34);
    bytes.write('data', 36); bytes.writeUInt32LE(bytes.length - 44, 40);
    return bytes;
}
(async () => {
    const browser = await chromium.launch({channel:'chrome', headless:true});
    try {
        const page = await browser.newPage();
        let seconds = 1, requests = 0;
        await page.route('http://local.test/**', route => {
            if (route.request().url().endsWith('/recording')) {
                requests++;
                return route.fulfill({contentType:'audio/wav', body:wave(seconds)});
            }
            return route.fulfill({contentType:'text/html', body:'<div></div>'});
        });
        await page.goto('http://local.test/');
        await page.addScriptTag({content:helpers});
        const load = () => page.evaluate(async () => {
            const recording = await prepareStudentProgressRecording('http://local.test/recording');
            return {duration:recording.duration, url:recording.playbackUrl};
        });
        const first = await load();
        assert.equal(first.duration, 1);
        assert.equal((await load()).url, first.url);
        assert.equal(requests, 1, 'Reuse audio only within the same review');
        await page.evaluate(() => stopStudentProgressAudio());
        assert.equal(await page.evaluate(() => studentProgressPlaybackUrls.size), 0);
        seconds = 2;
        const replacement = await load();
        assert.equal(replacement.duration, 2);
        assert.notEqual(replacement.url, first.url);
        assert.equal(requests, 2, 'Reopening review must fetch the replacement');
        await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
        assert.equal(await page.evaluate(() => studentProgressPlaybackUrls.size + studentProgressDurationLoads.size), 0);
        console.log('PASS: replacement audio is fetched after review closes; old playback URLs and caches are released.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
