// Offline request-sharing contracts; no live site or authentication sessions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js/student_classes.js'), 'utf8');

function page(fetch) {
    const context = { window: {}, fetch };
    vm.runInNewContext(source, context);
    return context.window.PabasaStudentClasses;
}

(async () => {
    let calls = 0;
    let finish;
    const classes = [{ section_id: 4, name: 'Reading' }];
    const listing = { success: true, classes };
    const api = page(() => {
        calls++;
        return new Promise(resolve => { finish = resolve; });
    });
    const sidebar = api.load();
    const dashboard = api.load();
    assert.equal(sidebar, dashboard);
    assert.equal(calls, 1);
    finish({ ok: true, json: async () => listing });
    assert.equal(await sidebar, listing);
    assert.equal(await api.load(), listing);
    assert.equal(calls, 1);
    api.invalidate();
    const refreshed = api.load();
    assert.equal(calls, 2);
    finish({ ok: true, json: async () => ({ success: true, classes: [] }) });
    assert.equal((await refreshed).classes.length, 0);

    let retries = 0;
    const retryApi = page(async () => (++retries === 1
        ? { ok: false, json: async () => ({ success: false, error: 'Forbidden' }) }
        : { ok: true, json: async () => listing }));
    await assert.rejects(retryApi.load(), /Forbidden/);
    assert.equal(await retryApi.load(), listing);
    assert.equal(retries, 2);

    // Separate page loads/accounts must not share cached enrollment data.
    const otherPage = page(async () => ({ ok: true, json: async () => ({ success: true, classes: [] }) }));
    assert.equal((await otherPage.load()).classes.length, 0);
    assert.equal((await api.load()).classes.length, 0);
    console.log('PASS: concurrent consumers share one request; refresh, failure retry, and page isolation work.');
})().catch(error => { console.error(error); process.exitCode = 1; });
