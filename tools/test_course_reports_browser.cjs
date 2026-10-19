// Local only: Django owns the disposable database and mocks outbound email.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');

(async () => {
    const base = process.env.PABASA_REPORTS_SERVER;
    assert.ok(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(base), 'Requires local test server');
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    let page;
    try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        await context.addCookies([{ name: 'sessionid', value: process.env.PABASA_REPORTS_COOKIE, url: base }]);
        page = await context.newPage();
        page.setDefaultTimeout(15000);
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'warning' && message.text().includes('loadCourseReports failed')) console.error(message.text());
        });
        let mode = 'normal';
        let releaseStudents;
        const studentsGate = new Promise(resolve => { releaseStudents = resolve; });
        await page.route('**/dashboard/teacher/students-api/**', async route => {
            await studentsGate;
            if (mode === 'empty') return route.fulfill({ json: { success: true, students: [] } });
            if (mode === 'error') return route.fulfill({ status: 503, json: { success: false } });
            return route.continue();
        });
        await page.goto(base + '/dashboard/courses/', { waitUntil: 'domcontentloaded' });
        const pane = page.locator('#reportsPane');
        const list = page.locator('#courseUnifiedStudentReportList');
        const send = page.locator('#courseBtnSendParentUpdate');
        const pdf = page.locator('#coursePreviewReadingReport');
        await page.waitForFunction(() => document.querySelector('#courseUnifiedStudentReportList')?.getAttribute('aria-busy') === 'true');
        assert.equal(await list.getAttribute('aria-busy'), 'true');
        assert.equal(await send.isDisabled(), true);
        releaseStudents();
        await page.locator('#side-reports-tab').click();
        await page.waitForFunction(() => document.querySelectorAll('#courseUnifiedStudentReportList .student-checkbox').length === 20);
        await page.waitForFunction(() => document.querySelector('#courseUnifiedStudentReportList').getAttribute('aria-busy') === 'false');
        assert.equal(await send.isDisabled(), true);
        assert.equal(await pdf.isDisabled(), true);
        assert.equal(await list.locator('.student-checkbox:disabled').count(), 1);
        assert.match(await page.locator('#courseUpdateRecipientCount').innerText(), /0 students/);
        // Labels toggle selection, and Select All reflects partial and full selection.
        await list.locator('label').first().click();
        assert.equal(await send.isEnabled(), true);
        assert.equal(await pdf.isEnabled(), true);
        assert.equal(await page.locator('#courseSelectAllRecipients').evaluate(el => el.indeterminate), true);
        const [preview] = await Promise.all([context.waitForEvent('page'), pdf.click()]);
        await preview.waitForURL('**/reading-report-preview/**');
        const response = await context.request.get(preview.url());
        assert.equal(response.headers()['content-type'], 'application/pdf');
        assert.ok((await response.body()).subarray(0, 4).equals(Buffer.from('%PDF')));
        await preview.close();
        await page.locator('#courseSelectAllRecipients').check();
        assert.equal(await list.locator(':checked').count(), 19);
        assert.equal(await pdf.isDisabled(), true);
        await page.locator('#courseSelectAllRecipients').uncheck();
        await list.locator('label').first().click();

        const layouts = [];
        for (const [width, height] of [[1920, 1080], [1440, 1000], [1024, 900], [768, 1024], [390, 844], [320, 740]]) {
            await page.setViewportSize({ width, height });
            await page.waitForTimeout(150);
            const layout = await pane.evaluate(el => {
                const box = selector => el.querySelector(selector).getBoundingClientRect();
                const composer = box('.course-report-composer-card');
                const recipients = box('.course-report-recipients-card');
                const footer = box('.course-report-submit-row');
                const list = el.querySelector('#courseUnifiedStudentReportList');
                return {
                    overflow: el.scrollWidth > el.clientWidth + 1,
                    pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
                    composerX: composer.x, composerY: composer.y,
                    recipientsX: recipients.x, recipientsY: recipients.y,
                    bottomSpace: composer.bottom - footer.bottom,
                    listScrolls: list.scrollHeight > list.clientHeight,
                    listOverflowsX: list.scrollWidth > list.clientWidth + 1,
                };
            });
            assert.equal(layout.overflow || layout.pageOverflow || layout.listOverflowsX, false, JSON.stringify({ width, layout }));
            assert.ok(layout.bottomSpace < 35, 'Composer must follow content height');
            assert.equal(layout.listScrolls, true);
            if (width === 1920) assert.ok(Math.abs(layout.composerY - layout.recipientsY) < 2);
            else assert.ok(layout.composerY > layout.recipientsY, 'Panels stack');
            // Scrolling the roster leaves selection controls stationary.
            const before = await page.locator('#courseSelectAllRecipients').boundingBox();
            await list.evaluate(el => { el.scrollTop = el.scrollHeight; });
            const after = await page.locator('#courseSelectAllRecipients').boundingBox();
            assert.equal(before.y, after.y);
            await list.evaluate(el => { el.scrollTop = 0; });
            layouts.push({ width, ...layout });
            if (process.env.PABASA_REPORTS_SCREENSHOTS && [1920, 1440, 390].includes(width)) {
                await page.screenshot({ path: path.join(process.env.PABASA_REPORTS_SCREENSHOTS, `reports-${width}.png`), fullPage: true });
            }
        }
        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.locator('#courseParentUpdateTemplate').selectOption('assessment');
        assert.equal(await page.locator('#courseParentAssessmentScheduledAt').isVisible(), true);
        await page.locator('#courseParentUpdateTemplate').selectOption('general');
        await page.locator('#courseParentUpdateMessage').fill(''); // Blank notes remain supported.
        let releaseSend;
        const sendGate = new Promise(resolve => { releaseSend = resolve; });
        await page.route('**/dashboard/teacher/course/send-update/', async route => {
            await sendGate;
            return route.continue();
        });
        await send.click();
        await page.waitForFunction(() => document.querySelector('#courseParentUpdateTabForm').getAttribute('aria-busy') === 'true');
        assert.equal(await send.isDisabled(), true);
        assert.match(await send.innerText(), /Sending/);
        releaseSend();
        await page.waitForFunction(() => document.querySelector('#courseUpdateStatus').classList.contains('alert-success'));
        assert.match(await page.locator('#courseUpdateStatus').innerText(), /1 recipient/);
        assert.equal(await send.isEnabled(), true);
        await page.unroute('**/dashboard/teacher/course/send-update/');
        await page.route('**/dashboard/teacher/course/send-update/', route => route.fulfill({ status: 503, json: { success: false, error: 'Temporary test failure. Please retry.' } }));
        await send.click();
        await page.waitForFunction(() => document.querySelector('#courseUpdateStatus').classList.contains('alert-danger'));
        assert.equal(await send.isEnabled(), true);

        for (const nextMode of ['empty', 'error']) {
            mode = nextMode;
            await page.reload();
            await page.locator('#side-reports-tab').click();
            await page.waitForFunction(() => document.querySelector('#courseUnifiedStudentReportList').getAttribute('aria-busy') === 'false');
            assert.match(await list.innerText(), nextMode === 'empty' ? /No students found/ : /Could not load students/);
            assert.equal(await send.isDisabled(), true);
            assert.equal(await page.locator('#courseSelectAllRecipients').isDisabled(), true);
        }
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({ result: 'passed', layouts, states: ['loading', 'empty', 'disabled', 'partial-selection', 'select-all', 'sending', 'success', 'error', 'PDF-preview'] }));
    } catch (error) {
        if (page) {
            console.error(await page.evaluate(() => ({
                list: document.querySelector('#courseUnifiedStudentReportList')?.innerText,
                course: document.querySelector('#courseDetailModal')?.dataset.courseId,
                checkboxes: document.querySelectorAll('#courseUnifiedStudentReportList .student-checkbox').length,
            })));
            if (process.env.PABASA_REPORTS_SCREENSHOTS) await page.screenshot({ path: path.join(process.env.PABASA_REPORTS_SCREENSHOTS, 'reports-failure.png'), fullPage: true });
        }
        throw error;
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exit(1); });
