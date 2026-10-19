// Local regression only. Never use an existing account or a live website.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');

(async () => {
    const base = process.env.PABASA_LOGOUT_SERVER;
    assert.ok(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(base));
    const sessions = JSON.parse(process.env.PABASA_LOGOUT_SESSIONS);
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    let page;
    try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        await context.addCookies([{ name: 'sessionid', value: sessions[0], url: base }]);
        page = await context.newPage();
        page.setDefaultTimeout(15000);
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const modal = page.locator('#logoutConfirmModal');
        const cancel = modal.getByRole('button', { name: 'Cancel', exact: true });
        const trigger = () => page.locator('.signature-footer [data-bs-target="#logoutConfirmModal"]:visible').first();
        const openLogout = async () => {
            await page.evaluate(() => new Promise(resolve => window.PabasaDashboardLoading.whenReady(resolve)));
            // Let the existing dashboard startup cleanup finish before interacting.
            await page.waitForFunction(() => performance.now() > 500);
            if (!(await trigger().isVisible())) {
                await page.locator('[data-bs-target="#dashboardSidebar"]:visible').first().click();
                await page.waitForFunction(() => {
                    const sidebar = document.querySelector('#dashboardSidebar');
                    return sidebar.classList.contains('show') && !sidebar.classList.contains('showing');
                });
            }
            const button = trigger();
            await button.click();
            return button;
        };
        const readyCourse = async () => {
            await page.waitForFunction(() => {
                const course = document.querySelector('#courseDetailModal');
                return course?.dataset.courseId && !course.classList.contains('course-detail-initializing');
            });
        };
        // Reproduce the former adapter in this response only, without editing source files.
        await page.route('**/dashboard/courses/', async route => {
            const response = await route.fetch();
            const html = (await response.text()).replace(" || modalEl?.id === 'logoutConfirmModal'", '');
            await route.fulfill({ response, body: html });
        });
        await page.goto(base + '/dashboard/courses/');
        await readyCourse();
        await openLogout();
        assert.equal(await page.locator('#courseInlineDialogHost').getAttribute('data-inline-modal-id'), 'logoutConfirmModal');
        assert.equal(await page.locator('.modal-backdrop').count(), 0);
        assert.equal(await page.locator('#logoutConfirmModal .logout-modal-title').count(), 0);
        await page.unroute('**/dashboard/courses/');

        const styleSnapshot = () => modal.evaluate(el => {
            const style = (selector, properties) => {
                const computed = getComputedStyle(el.querySelector(selector));
                return Object.fromEntries(properties.map(property => [property, computed.getPropertyValue(property)]));
            };
            return {
                dialog: style('.modal-dialog', ['max-width', 'margin-left', 'margin-right']),
                content: style('.modal-content', ['background-color', 'background-image', 'border-radius', 'border-width', 'box-shadow']),
                body: style('.modal-body', ['padding', 'display', 'align-items', 'font-size', 'line-height']),
                icon: style('.logout-modal-icon', ['background-image', 'color', 'width', 'height']),
                title: style('.logout-modal-title', ['font-family', 'font-size', 'color', 'font-weight']),
                copy: style('.logout-modal-copy', ['font-family', 'font-size', 'color']),
                footer: style('.modal-footer', ['background-color', 'padding', 'gap']),
                cancel: style('[data-bs-dismiss="modal"]', ['border-width', 'padding', 'min-height', 'box-shadow']),
                confirm: style('#confirmLogoutBtn', ['background-image', 'padding', 'min-height', 'box-shadow']),
                backdrop: (() => {
                    const computed = getComputedStyle(document.querySelector('.modal-backdrop'));
                    return { background: computed.backgroundColor, opacity: computed.opacity };
                })(),
            };
        });
        const results = [];
        for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
            await page.setViewportSize(viewport);
            let referenceStyle;
            for (const location of ['dashboard', 'materials', 'students', 'results', 'reports']) {
                const url = location === 'dashboard' ? '/dashboard/teacher/' : '/dashboard/courses/';
                await page.goto(base + url);
                if (location !== 'dashboard') {
                    await readyCourse();
                    const tabs = { materials: 'materials', students: 'students', results: 'assessments', reports: 'reports' };
                    await page.locator(`#side-${tabs[location]}-tab`).click();
                    if (location === 'reports') await page.locator('#courseUnifiedStudentReportList').evaluate(el => { el.scrollTop = 180; });
                    await page.locator('#courseMainContent').evaluate(el => { el.scrollTop = 80; });
                }
                const beforeURL = page.url();
                const launcher = await openLogout();
                await modal.waitFor({ state: 'visible' });
                await page.waitForFunction(() => document.querySelector('#logoutConfirmModal')?.getAttribute('aria-modal') === 'true');
                // Bootstrap's transition must finish before inspecting centering or dismissing.
                await page.waitForTimeout(400);
                assert.equal(page.url(), beforeURL);
                assert.equal(await page.locator('#logoutConfirmModal').count(), 1);
                assert.equal(await page.locator('.modal-backdrop').count(), 1, `${location} ${viewport.width}: one backdrop`);
                assert.equal(await modal.locator('.modal-content .logout-modal-title').innerText(), 'Ready to sign out?');
                assert.equal(await page.locator('#courseInlineDialogHost[data-inline-modal-id="logoutConfirmModal"]').count(), 0);
                const geometry = await modal.evaluate(el => {
                    const box = el.querySelector('.modal-content').getBoundingClientRect();
                    const hit = document.elementFromPoint(4, innerHeight / 2);
                    return { x: box.x, y: box.y, width: box.width, height: box.height,
                        screenWidth: innerWidth, screenHeight: innerHeight,
                        backdropBlocksPage: hit === el || el.contains(hit),
                        focusInside: el.contains(document.activeElement),
                        bodyLocked: document.body.classList.contains('modal-open'),
                        horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1 };
                });
                assert.ok(Math.abs(geometry.x + geometry.width / 2 - geometry.screenWidth / 2) < 2, JSON.stringify(geometry));
                assert.ok(Math.abs(geometry.y + geometry.height / 2 - geometry.screenHeight / 2) < 2, JSON.stringify(geometry));
                assert.ok(geometry.backdropBlocksPage && geometry.focusInside && geometry.bodyLocked);
                assert.equal(geometry.horizontalOverflow, false);
                const styles = await styleSnapshot();
                if (location === 'dashboard') referenceStyle = styles;
                else assert.deepEqual(styles, referenceStyle, `${location} must use the exact shared logout styles`);
                // Keyboard order and Bootstrap's trap keep page controls out of focus.
                await cancel.focus();
                await page.keyboard.press('Tab');
                assert.equal(await modal.locator('#confirmLogoutBtn').evaluate(el => el === document.activeElement), true);
                await page.keyboard.press('Shift+Tab');
                assert.equal(await cancel.evaluate(el => el === document.activeElement), true);
                await launcher.evaluate(el => el.focus());
                assert.equal(await modal.evaluate(el => el.contains(document.activeElement)), true);
                if (process.env.PABASA_LOGOUT_SCREENSHOTS && ['dashboard', 'reports'].includes(location)) {
                    await page.screenshot({ path: path.join(process.env.PABASA_LOGOUT_SCREENSHOTS, `logout-${location}-${viewport.width}.png`) });
                }
                await cancel.click();
                await modal.waitFor({ state: 'hidden' });
                await page.waitForFunction(() => !document.querySelector('.modal-backdrop') && !document.body.classList.contains('modal-open'));
                assert.equal(await page.locator('.modal-backdrop').count(), 0);
                assert.equal(page.url(), beforeURL);
                assert.equal(await launcher.evaluate(el => el === document.activeElement), true);
                // Reopening exercises handler/overlay duplication and Escape dismissal.
                await openLogout();
                await modal.waitFor({ state: 'visible' });
                await page.waitForTimeout(400);
                await page.keyboard.press('Escape');
                await modal.waitFor({ state: 'hidden' });
                await page.waitForFunction(() => !document.querySelector('.modal-backdrop') && !document.body.classList.contains('modal-open'));
                assert.equal(await page.locator('.modal-backdrop').count(), 0);
                assert.equal(page.url(), beforeURL);
                results.push({ width: viewport.width, page: location, centered: true, sharedStyle: true, cancel: true, escape: true });
            }
        }
        // Confirm the real logout route for both pages using separate disposable sessions.
        for (const [index, url] of ['/dashboard/teacher/', '/dashboard/courses/'].entries()) {
            const logoutContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
            await logoutContext.addCookies([{ name: 'sessionid', value: sessions[index + 1], url: base }]);
            const logoutPage = await logoutContext.newPage();
            await logoutPage.goto(base + url);
            if (url.includes('/courses/')) await logoutPage.waitForFunction(() => document.querySelector('#courseDetailModal')?.dataset.courseId && !document.querySelector('#courseDetailModal').classList.contains('course-detail-initializing'));
            await logoutPage.locator('.signature-footer [data-bs-target="#logoutConfirmModal"]:visible').first().click();
            await logoutPage.locator('#logoutConfirmModal.show').waitFor();
            await logoutPage.locator('#confirmLogoutBtn').click();
            await logoutPage.waitForURL(base + '/');
            const protectedResponse = await logoutContext.request.get(base + url, { maxRedirects: 0 });
            assert.equal(protectedResponse.status(), 302);
            assert.equal(protectedResponse.headers().location, '/auth/');
            await logoutContext.close();
        }
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({ result: 'passed', reproducedOriginalBug: true, realLogout: ['dashboard', 'courses'], checks: results }));
    } catch (error) {
        if (page) console.error(await page.evaluate(() => {
            const el = document.querySelector('#logoutConfirmModal');
            const instance = el && window.bootstrap?.Modal.getInstance(el);
            return { path: location.pathname, viewport: innerWidth,
                focus: document.activeElement?.outerHTML?.slice(0, 180),
                focusTrap: instance?._focustrap?._isActive, modalShown: instance?._isShown };
        }));
        if (page && process.env.PABASA_LOGOUT_SCREENSHOTS) await page.screenshot({ path: path.join(process.env.PABASA_LOGOUT_SCREENSHOTS, 'logout-failure.png') });
        throw error;
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exit(1); });
