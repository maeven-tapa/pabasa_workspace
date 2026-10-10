/* Local Chrome checks with synthetic API responses; no production requests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static');
const loader = fs.readFileSync(path.join(staticRoot, 'pabasa_app/js/class_materials.js'), 'utf8');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const listing = id => ({ success: true, section_id: Number(id), class_name: 'Synthetic Class',
    class_code: 'SYNTHETIC', subject: 'Reading', materials: { word: [{
        id: `material-${id}`, title: 'Synthetic reading', student_has_completed: false,
    }] } });

async function main() {
    const browser = await chromium.launch({
        executablePath: process.env.PABASA_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
        headless: true,
    });
    try {
        const page = await browser.newPage();
        let requests = [], active = 0, maximum = 0, fail = null, completed = false;
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.pathname === '/api/class/materials/') {
                const id = url.searchParams.get('section_id');
                requests.push({ id, view: url.searchParams.get('view') });
                active += 1; maximum = Math.max(maximum, active);
                await wait(50);
                const failure = fail;
                fail = null;
                const payload = listing(id);
                payload.materials.word[0].student_has_completed = completed;
                active -= 1;
                await route.fulfill({ status: failure || 200, contentType: 'application/json',
                    body: JSON.stringify(failure ? { success: false, error: 'Synthetic failure' } : payload) });
            } else {
                await route.fulfill({ contentType: 'text/html', body: '<html><body>Fixture</body></html>' });
            }
        });
        await page.goto('http://pabasa.test/?section_id=9');
        await page.evaluate(() => {
            window.PABASA_USER_ROLE = 'student';
            localStorage.setItem('pabasa_section_readings', JSON.stringify({ 99: { word: [{ title: 'Old listing' }] } }));
        });
        await page.addScriptTag({ content: loader });
        assert.equal(await page.evaluate(() => localStorage.getItem('pabasa_section_readings')), '{}');
        const same = await page.evaluate(async () => {
            const a = PabasaMaterials.load(1), b = PabasaMaterials.load(1);
            await Promise.all([a, b]);
            return a === b;
        });
        assert.equal(same, true);
        assert.equal(requests.length, 1);
        await page.evaluate(() => PabasaMaterials.load(1));
        assert.equal(requests.length, 1);
        assert.equal(requests[0].view, 'summary');
        await page.evaluate(async () => { await PabasaMaterials.load(1, { view: 'full' }); });
        assert.equal(requests.length, 2);
        assert.equal(requests[1].view, null);
        const shape = await page.evaluate(() => JSON.parse(localStorage.getItem('pabasa_section_readings'))['1']);
        assert.ok(Array.isArray(shape.word));
        assert.equal(shape.materials, undefined);

        requests = []; maximum = 0;
        await page.evaluate(async () => {
            await Promise.all([2, 3, 4, 5, 9].map(id => PabasaMaterials.load(id)));
        });
        assert.equal(maximum, 2);
        assert.equal(requests[2].id, '9'); // Requested class jumps ahead of queued background work.

        fail = 403;
        const denied = await page.evaluate(async () => {
            try { await PabasaMaterials.load(1, { fresh: true }); return false; }
            catch (error) { return error.status === 403; }
        });
        assert.equal(denied, true);
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pabasa_section_readings'))['1']), undefined);
        await page.evaluate(() => PabasaMaterials.load(1)); // Failed entries can be retried.
        fail = 500;
        await page.evaluate(async () => { try { await PabasaMaterials.load(1, { fresh: true }); } catch (_) {} });
        await page.evaluate(() => PabasaMaterials.load(1));

        // Old requests may not repopulate storage after invalidation.
        const obsolete = await page.evaluate(async () => {
            const old = PabasaMaterials.load(6);
            PabasaMaterials.invalidate(6);
            const fresh = PabasaMaterials.load(6);
            return (await Promise.allSettled([old, fresh])).map(result => result.status);
        });
        assert.deepEqual(obsolete, ['rejected', 'fulfilled']);
        await page.evaluate(() => PabasaMaterials.prune([1]));
        assert.deepEqual(await page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('pabasa_section_readings')))), ['1']);
        completed = true;
        await page.evaluate(() => new Promise(resolve => {
            window.addEventListener('pabasa:student-class-updated', resolve, { once: true });
            window.dispatchEvent(new CustomEvent('pabasa:assessment-completed'));
        }));
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pabasa_section_readings'))['1'].word[0].student_has_completed), true);
        const beforeItemProgress = requests.length;
        await page.evaluate(() => window.dispatchEvent(new CustomEvent('pabasa:practice-progress-updated')));
        await wait(100);
        assert.equal(requests.length, beforeItemProgress); // Per-item free practice must not refetch listings.
        await page.evaluate(() => new Promise(resolve => {
            window.addEventListener('pabasa:student-class-updated', resolve, { once: true });
            window.dispatchEvent(new CustomEvent('pabasa:practice-completed'));
        }));
        assert.equal(requests.length, beforeItemProgress + 1);
        const beforeNavigation = requests.length;
        await page.reload();
        await page.evaluate(() => { window.PABASA_USER_ROLE = 'student'; });
        await page.addScriptTag({ content: loader });
        await page.evaluate(() => PabasaMaterials.load(1));
        assert.equal(requests.length, beforeNavigation + 1);
        console.log('PASS: browser deduplication, two-request limit, requested-class priority, compact mode, storage shape, retries, authorization clearing, stale-request rejection, completion and navigation refresh');
        await page.close();

        const htmlPath = path.join(root, 'tmp/materials-browser-page.html');
        const dataPath = path.join(root, 'tmp/materials-browser-payload.json');
        assert.ok(fs.existsSync(htmlPath) && fs.existsSync(dataPath), 'Run benchmark_class_materials.py first to render the synthetic assessment page');
        const html = fs.readFileSync(htmlPath, 'utf8');
        assert.ok(html.includes('class_materials.js') && html.includes('subjectGrid'));
        const fixture = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
        const integration = await browser.newPage();
        // The page's CDN scripts have SRI hashes. Supply the Bootstrap API in
        // this offline fixture instead of executing a third-party download.
        await integration.addInitScript(() => {
            class Component {
                show() {} hide() {} dispose() {}
                static getInstance() { return new Component(); }
                static getOrCreateInstance() { return new Component(); }
            }
            window.bootstrap = { Tooltip: Component, Modal: Component, Offcanvas: Component };
        });
        let materialRequests = 0;
        const errors = [];
        integration.on('pageerror', error => errors.push(error.message));
        await integration.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.hostname === 'pabasa.test' && url.pathname === '/dashboard/assessment/') {
                return route.fulfill({ contentType: 'text/html', body: html });
            }
            if (url.pathname === '/api/class/materials/') {
                materialRequests += 1;
                assert.equal(url.searchParams.get('view'), 'summary');
                await wait(80);
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture.listing) });
            }
            if (url.pathname === '/api/student/classes/') {
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture.classes) });
            }
            if (url.pathname.startsWith('/static/')) {
                const filename = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice('/static/'.length)));
                if (filename.startsWith(staticRoot + path.sep) && fs.existsSync(filename) && /\.(js|css)$/.test(filename)) {
                    return route.fulfill({ contentType: filename.endsWith('.js') ? 'application/javascript' : 'text/css', body: fs.readFileSync(filename) });
                }
            }
            if (url.pathname.includes('bootstrap') && url.pathname.endsWith('.js')) {
                return route.fulfill({ contentType: 'application/javascript', body: `
                    class Component { constructor(){} show(){} hide(){} dispose(){} static getInstance(){return new Component()} static getOrCreateInstance(){return new Component()} }
                    window.bootstrap={Tooltip:Component,Modal:Component,Offcanvas:Component};` });
            }
            return route.fulfill({ contentType: url.pathname.startsWith('/api/') ? 'application/json' : 'text/plain',
                body: url.pathname.startsWith('/api/') ? JSON.stringify({ success: true, unread_count: 0, notifications: [], invitation: null }) : '' });
        });
        await integration.goto('http://pabasa.test/dashboard/assessment/');
        try {
            // Supplementary cards are moved from subjectGrid into week modals.
            await integration.waitForSelector('.assessment-type-link', { state: 'attached', timeout: 10000 });
        } catch (error) {
            console.error(JSON.stringify({ materialRequests, errors,
                role: await integration.evaluate(() => window.PABASA_USER_ROLE),
                totalCards: await integration.locator('.assessment-type-link').count() }));
            throw error;
        }
        await integration.waitForFunction(() => document.querySelector('#sessionGrid .session-folder-column'));
        assert.equal(materialRequests, 1);
        const links = await integration.locator('.assessment-type-link').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')));
        assert.ok(links.some(href => href.includes('story-reading') && href.includes('id=material-')));
        assert.ok(links.some(href => href.includes('fluency-reading') && href.includes('id=material-')));
        assert.equal(errors.length, 0, `Assessment page errors: ${errors.join('; ')}`);
        console.log('PASS: actual Django-rendered assessment/session page, compact cards, preserved activity links, and one shared materials request across dashboard and assessment scripts');
        await integration.close();

        const storyHtml = fs.readFileSync(path.join(root, 'tmp/materials-browser-story-page.html'), 'utf8');
        assert.ok(storyHtml.indexOf('class_materials.js') < storyHtml.indexOf('story_reading_player.js'));
        const storyPage = await browser.newPage();
        let storyRequests = 0;
        const storyErrors = [];
        storyPage.on('pageerror', error => storyErrors.push(error.message));
        await storyPage.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.pathname === '/dashboard/assessment/story-reading/') {
                return route.fulfill({ contentType: 'text/html', body: storyHtml });
            }
            if (url.pathname === '/api/class/materials/') {
                storyRequests += 1;
                assert.equal(url.searchParams.get('view'), 'summary');
                const payload = JSON.parse(JSON.stringify(fixture.listing));
                const storyId = await storyPage.evaluate(() => JSON.parse(document.getElementById('story-reading-data').textContent).material_id);
                payload.materials.paragraph.push({ id: 'material-9999', status: 'published', content_json: {
                    template_title: "5W's Story Questions", sourceMaterialId: storyId,
                } });
                return route.fulfill({ contentType: 'application/json', body: JSON.stringify(payload) });
            }
            if (url.pathname.startsWith('/static/')) {
                const filename = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice('/static/'.length)));
                if (filename.startsWith(staticRoot + path.sep) && fs.existsSync(filename) && filename.endsWith('.js')) {
                    return route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(filename) });
                }
            }
            return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true }) });
        });
        await storyPage.goto('http://pabasa.test/dashboard/assessment/story-reading/');
        await storyPage.waitForSelector('#storyScoreModal:not([hidden])');
        await storyPage.waitForSelector('.story-score-done:not([disabled])');
        assert.equal(storyRequests, 1);
        assert.equal(storyErrors.length, 0, `Story Reading errors: ${storyErrors.join('; ')}`);
        console.log('PASS: standalone Story Reading loads the shared loader first and enables its 5W continuation using compact metadata');
        await storyPage.close();
    } finally {
        await browser.close();
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
