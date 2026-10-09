const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const requests = [];
const key = 'aral-s9-a1-family-drawing';
const originalStorage = new Map([['student-progress', 'unchanged']]);
const context = vm.createContext({
    URL, Response, Headers, FormData, Map, JSON,
    window: {
        location: { href: 'https://test/preview/', origin: 'https://test' },
        __PABASA_ADMIN_PRESCRIBED_KEY__: key,
        localStorage: {
            getItem: name => originalStorage.get(name),
            setItem: (name, value) => originalStorage.set(name, value),
        },
        fetch: async (url, options) => {
            requests.push(url);
            assert.equal(url, `/api/admin/prescribed/${key}/event/`);
            const event = JSON.parse(options.body);
            assert.ok(event._preview_state);
            return new Response(JSON.stringify({success:true,preview_only:true,
                state:{...event._preview_state,revision:event._preview_state.revision+1,completed:event.action==='finish'},
                progress:{completed_items:1,correct_items:1},
            }), {headers:{'Content-Type':'application/json'}});
        },
    },
    document: {
        getElementById: () => ({textContent:JSON.stringify({state:{revision:0}})}),
        addEventListener: () => {},
    },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/static/pabasa_app/js/admin_prescribed_preview.js'), 'utf8'), context);
(async () => {
    vm.runInContext('window.localStorage.setItem("student-progress", "preview draft")', context);
    assert.equal(originalStorage.get('student-progress'), 'unchanged');
    assert.equal(vm.runInContext('window.localStorage.getItem("student-progress")', context), 'preview draft');
    for (const action of ['draft', 'finish']) {
        const response = await context.window.fetch(`/api/dashboard/assessment/activity/prescribed/${key}/progress/`, {
            method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action}),
        });
        assert.equal(response.status, 200);
    }
    const complete = await context.window.fetch(`/api/dashboard/assessment/activity/prescribed/${key}/complete/`, {method:'POST',body:'{}'});
    assert.equal((await complete.json()).result.correct_items, 1);
    const notifications = await context.window.fetch('/api/notifications/', {method:'POST',body:'{}'});
    assert.equal(notifications.status, 403);
    assert.equal(requests.length, 2);
    assert.ok(requests.every(url => url.startsWith('/api/admin/prescribed/')));
    console.log('PASS: workbook events evaluated through admin preview; completion displays ephemeral results; student storage and notifications untouched');
})().catch(error => { console.error(error); process.exitCode = 1; });
