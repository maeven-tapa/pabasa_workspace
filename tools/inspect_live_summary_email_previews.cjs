// Local synthetic previews only. No accounts, authenticated browser or messages.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');

(async () => {
    const root = path.resolve(process.argv[2] || 'output/email/live-summary');
    const output = path.resolve('tmp/live-summary-email');
    await fs.mkdir(output, { recursive: true });
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    const results = [];
    try {
        const context = await browser.newContext();
        const files = (await fs.readdir(root)).filter(name => name.endsWith('.html'));
        for (const file of files) {
            for (const width of [960, 390, 320]) {
                const page = await context.newPage();
                await page.setViewportSize({ width, height: 900 });
                await page.goto(pathToFileURL(path.join(root, file)).href);
                await page.locator('img').evaluateAll(images => Promise.all(images.map(img => img.decode())));
                const state = await page.evaluate(() => ({
                    overflow: document.documentElement.scrollWidth > innerWidth,
                    images: Array.from(document.images, img => ({ loaded: img.complete && img.naturalWidth > 0,
                        ratio: img.clientWidth / img.clientHeight })),
                    kpis: Array.from(document.querySelectorAll('.kpi-number'), el => el.textContent.trim()),
                    cards: Array.from(document.querySelectorAll('.kpi-pad'), el => el.getBoundingClientRect().height),
                    listCount: document.querySelectorAll('.list-cell').length,
                    completionOverlap: (() => {
                        const range = document.createRange();
                        range.selectNodeContents(document.querySelector('.completion-number'));
                        const value = range.getBoundingClientRect();
                        range.selectNodeContents(document.querySelector('.completion-copy p'));
                        const copy = range.getBoundingClientRect();
                        return value.left < copy.right && value.right > copy.left && value.top < copy.bottom && value.bottom > copy.top;
                    })(),
                    completionGeometry: (() => {
                        const range = document.createRange();
                        range.selectNodeContents(document.querySelector('.completion-number'));
                        const value = range.getBoundingClientRect().toJSON();
                        range.selectNodeContents(document.querySelector('.completion-copy p'));
                        return { value, copy: range.getBoundingClientRect().toJSON() };
                    })(),
                }));
                assert.equal(state.overflow, false, `${file} overflows at ${width}px`);
                assert.ok(state.images.every(img => img.loaded), `${file} has a broken logo`);
                assert.ok(state.images.every(img => Math.abs(img.ratio - 3) < .08), 'Logo aspect ratio changed');
                assert.equal(state.kpis.length, 3);
                assert.ok(Math.max(...state.cards) - Math.min(...state.cards) < 1, 'Unequal KPI card heights');
                assert.equal(state.listCount, 2);
                assert.equal(state.completionOverlap, false, `${file} at ${width}px: completion percentage overlaps its explanation ${JSON.stringify(state.completionGeometry)}`);
                const label = `${path.basename(file, '.html')}-${width}`;
                await page.screenshot({ path: path.join(output, `${label}.png`), fullPage: true });
                results.push({ file, width, ...state });
                await page.close();
            }
        }
        // Simulate clients discarding head styles and blocking images. Core text,
        // table layout and bgcolor fallbacks must still be usable without overflow.
        const fallback = await context.newPage();
        await fallback.setViewportSize({ width: 660, height: 900 });
        await fallback.goto(pathToFileURL(path.join(root, 'mixed.html')).href);
        await fallback.locator('style').evaluateAll(styles => styles.forEach(style => style.remove()));
        await fallback.locator('[style]').evaluateAll(elements => elements.forEach(el => {
            el.style.backgroundImage = 'none';
            el.style.boxShadow = 'none';
            el.style.borderRadius = '0';
        }));
        await fallback.locator('img').evaluateAll(images => images.forEach(img => img.removeAttribute('src')));
        assert.equal(await fallback.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await fallback.screenshot({ path: path.join(output, 'fallback-styles-and-images-disabled.png'), fullPage: true });
        await fallback.close();
        await fs.writeFile(path.join(output, 'layout-results.json'), JSON.stringify(results, null, 2));
        console.log(`${results.length} desktop/mobile layouts passed; solid-color/image-blocked fallback inspected.`);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
