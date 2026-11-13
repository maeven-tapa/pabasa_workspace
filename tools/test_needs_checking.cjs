// Local Django test server only. Credentials exist only in the child environment.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const server = process.env.PABASA_REVIEW_SERVER;
assert(server && /^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(server), 'A disposable local server is required');
const screenshots = path.resolve(__dirname, '../tmp/review-screens');
fs.mkdirSync(screenshots, {recursive: true});
(async () => {
    const browser = await chromium.launch({headless: true, ...(process.env.PABASA_BROWSER_CHANNEL ? {channel:process.env.PABASA_BROWSER_CHANNEL} : {})});
    try {
        const context = await browser.newContext({viewport: {width: 1600, height: 1050}, deviceScaleFactor: 1.25,
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36'});
        await context.addCookies([{name:'sessionid', value:process.env.PABASA_REVIEW_COOKIE, url:server}]);
        await context.addInitScript(() => localStorage.setItem('pabasaCurrentUserId', 'local-review-fixture'));
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('response', async response => { if (response.url().includes('/needs-checking/') && response.status() >= 400) console.error('Review request failed:', response.url().split('?')[0], response.status(), (await response.text()).slice(0,500)); });
        await page.goto(server + '/dashboard/teacher/needs-checking/', {waitUntil:'networkidle'});
        await page.waitForSelector('.nc-row').catch(async error => {
            await page.screenshot({path:path.join(screenshots,'failure.png'),fullPage:true});
            console.error('Page diagnostics', page.url(), errors, (await page.locator('body').innerText()).slice(0,2500));
            throw error;
        });
        assert.equal(await page.locator('.nc-row').count(), 11);
        await page.screenshot({path:path.join(screenshots,'workspace-desktop.png'),fullPage:true});
        for (const width of [820, 390]) {
            await page.setViewportSize({width, height:width === 390 ? 844 : 1100});
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            const layout = await page.evaluate(() => ({scroll:document.documentElement.scrollWidth, width:innerWidth,
                workspace:document.getElementById('nc-workspace').getBoundingClientRect().width}));
            assert(layout.scroll <= layout.width + 2 && layout.workspace <= layout.width + 2, 'Page must fit narrow viewports: ' + JSON.stringify(layout));
            await page.screenshot({path:path.join(screenshots,`workspace-${width}.png`),fullPage:true});
        }
        await page.setViewportSize({width:1600,height:1050});
        assert.equal(await page.locator('#nc-review-dialog').count(), 0, 'Inbox must not have a second grading interface');
        await page.locator('[name=q]').fill('Tunog ng mga Letra');
        await page.waitForFunction(() => document.querySelectorAll('.nc-row').length === 2);
        await page.locator('[data-open-task$="session-4-gawain-1"]').click();
        await page.waitForURL('**/dashboard/courses/**');
        const review = page.locator('.student-progress-review-dialog[open]');
        await review.locator('.session4-score-button').first().waitFor();
        assert.equal(await page.locator('#nc-review-dialog').count(), 0);
        await page.screenshot({path:path.join(screenshots,'recording-desktop.png')});
        await review.locator('audio').first().evaluate(async audio => { await audio.play(); audio.pause(); });
        await page.setViewportSize({width:390,height:844});
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const bounds = await review.boundingBox();
        assert(bounds.x >= 0 && bounds.x+bounds.width <= 392, 'Existing review dialog fits mobile');
        await page.screenshot({path:path.join(screenshots,'recording-mobile.png')});
        await review.locator(`[data-submission-id="${process.env.PABASA_REVIEW_RECORD}"] [data-score="1"]`).click();
        await review.locator('.session4-score-feedback').first().filter({hasText:'Saved'}).waitFor();
        await review.locator('.nc-course-review-nav a').click();
        await page.waitForURL('**/teacher/needs-checking/**');
        assert.equal(await page.locator('[name=q]').inputValue(), 'Tunog ng mga Letra', 'Inbox filters survive grading');
        await page.setViewportSize({width:1600,height:1050});
        await page.locator('[name=q]').fill('A small adventure');
        await page.waitForFunction(() => document.querySelectorAll('.nc-row').length === 2);
        await page.locator(`[data-open-task$="material-${process.env.PABASA_REVIEW_RETELL}"]`).click();
        await page.waitForURL('**/dashboard/courses/**');
        await page.locator('[data-retell-reviewed]').click();
        await page.getByRole('button', {name:'Reviewed · score optional'}).waitFor();
        await page.locator('.nc-course-review-nav a').first().click();
        await page.waitForURL('**/teacher/needs-checking/**');
        await page.locator(`[data-open-task$="material-${process.env.PABASA_REVIEW_RESPONSE}"]`).click();
        await page.waitForURL('**/dashboard/courses/**');
        await page.locator('.student-progress-retell-score').selectOption('4');
        await page.locator('#manualGradeConfirmModal [data-confirm-save]').click();
        await page.waitForFunction(() => document.querySelector('.student-progress-retell-score')?.disabled === true);
        await page.locator('.nc-course-review-nav a').first().click();
        await page.waitForURL('**/teacher/needs-checking/**');
        await page.locator('[name=q]').fill('no-such-student');
        await page.waitForSelector('.nc-empty h3');
        assert.equal(await page.locator('.nc-empty h3').textContent(), 'No matching submissions');
        await page.locator('[data-reset]').click();
        await page.waitForSelector('.nc-row');
        await page.locator('[data-open-task$="aral-s9-a1-family-drawing"]').click();
        await page.waitForURL('**/teacher/prescribed-review/**');
        await page.locator('[data-action=complete]').click();
        await page.waitForFunction(() => document.querySelector('.teacher-review__status')?.textContent === 'Completed');
        await page.locator('.nc-course-review-nav [data-next-review]').click();
        await page.waitForFunction(() => location.search.includes('review_task=') && !location.search.includes('aral-s9-a1-family-drawing'));
        await page.goto(server + '/dashboard/teacher/', {waitUntil:'networkidle'});
        await page.waitForFunction(() => document.querySelector('[data-nc-overview] [data-nc-stat=pending]').textContent !== '—');
        await page.screenshot({path:path.join(screenshots,'dashboard-desktop.png'),fullPage:true});
        await page.setViewportSize({width:390,height:844});
        await page.screenshot({path:path.join(screenshots,'dashboard-mobile.png'),fullPage:true});
        assert.equal(errors.length, 0, errors.join('\n'));
        console.log('Review workspace: real grading, optional retell review, audio, filters, keyboard, desktop/tablet/mobile passed.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
