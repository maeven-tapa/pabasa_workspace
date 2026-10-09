const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
    '../pabasa_site/pabasa_app/static/pabasa_app/js/dashboard_loading.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
function setup() {
    const frames = [], events = {}, imageEvents = {}, fonts = deferred();
    const image = {
        loading: 'eager', complete: false,
        getClientRects: () => [{}], decode: () => Promise.resolve(),
        addEventListener: (name, callback) => { imageEvents[name] = callback; },
    };
    const window = { addEventListener: (name, callback) => { events[name] = callback; } };
    vm.runInNewContext(source, {
        window, document: {
            readyState: 'loading', fonts: { ready: fonts.promise },
            images: [image, { loading: 'lazy', getClientRects: () => [{}] }],
        }, requestAnimationFrame: callback => frames.push(callback),
    });
    return { api: window.PabasaDashboardLoading, events, imageEvents, image, fonts,
        async paint() {
            await tick();
            frames.splice(0).forEach(callback => callback());
            await tick();
            frames.splice(0).forEach(callback => callback());
            await tick();
        },
    };
}

(async () => {
    const page = setup(), data = deferred();
    let content = 'Loading...', revealed = 0;
    page.api.whenReady(() => { assert.equal(content, 'Ready'); revealed++; });
    const initial = page.api.track(data.promise.then(() => { content = 'Ready'; }), 'student-data');
    page.events.load();
    await page.paint();
    assert.equal(revealed, 0, 'load event must not bypass initial data');
    data.resolve();
    await initial;
    await page.paint();
    assert.equal(revealed, 0, 'data completion must not bypass fonts and images');
    page.fonts.resolve();
    await page.paint();
    assert.equal(revealed, 0, 'critical image is still loading');
    page.image.complete = true;
    page.imageEvents.load();
    await page.paint();
    assert.equal(revealed, 1, 'ready content is revealed after its first paint');
    const later = page.api.hold('background-poll');
    page.api.whenReady(() => { revealed++; });
    assert.equal(revealed, 2, 'later polling must not reopen the initial loader');
    later();

    const failedPage = setup(), failure = deferred();
    let failureRevealed = false;
    failedPage.api.whenReady(() => { failureRevealed = true; });
    const failedRequest = failedPage.api.track(failure.promise, 'teacher-roster').catch(() => {});
    failedPage.events.load();
    failure.reject(new Error('Network unavailable'));
    await failedRequest;
    failedPage.fonts.resolve();
    await tick();
    failedPage.image.complete = true;
    failedPage.imageEvents.error();
    await failedPage.paint();
    assert.equal(failureRevealed, true, 'failed data/images must release their holds');

    const latePage = setup();
    latePage.image.complete = true;
    latePage.fonts.resolve();
    let lateRevealed = false;
    latePage.api.whenReady(() => { lateRevealed = true; });
    latePage.events.load();
    await tick();
    const releaseLate = latePage.api.hold('session-folders');
    await latePage.paint();
    assert.equal(lateRevealed, false, 'a task registered before reveal cancels the earlier paint');
    releaseLate();
    await latePage.paint();
    assert.equal(lateRevealed, true);

    const templates = path.join(__dirname, '../pabasa_site/pabasa_app/templates/pabasa_app');
    function extract(text, first, last) {
        const start = text.indexOf(first), end = text.indexOf(last, start);
        assert.ok(start >= 0 && end > start);
        return text.slice(start, end);
    }
    const studentSource = fs.readFileSync(path.join(templates, 'dashboard.html'), 'utf8');
    let studentRequests = 0;
    const student = vm.createContext({
        fetch: async () => {
            studentRequests++;
            return { ok: true, status: 200, json: async () => ({ success: true,
                classes: [{ id: 1, section_id: 17, name: 'Class A' }],
            }) };
        }, console: { warn() {}, error() {} }, performance: { now: () => 0 }, perfLog() {},
    });
    vm.runInContext(extract(studentSource, 'let initialStudentClasses = null;', 'const renderClassCards =') +
        extract(studentSource, 'const fetchStudentClassesFromDatabase =', '// Initialize with database classes'), student);
    const ids = await vm.runInContext('fetchStudentClassesFromDatabase()', student);
    const details = await vm.runInContext('fetchClassDetailsFromDatabase(["17"])', student);
    assert.equal(ids[0], '17');
    assert.equal(details['17'].name, 'Class A');
    assert.equal(studentRequests, 1, 'student initial IDs and cards share one response');
    await vm.runInContext('fetchClassDetailsFromDatabase(["17"])', student);
    assert.equal(studentRequests, 2, 'later student refresh still contacts the server');

    const teacherSource = fs.readFileSync(path.join(templates, 'dashboard_teacher.html'), 'utf8');
    let teacherRequests = 0;
    const teacher = vm.createContext({ fetch: async () => {
        teacherRequests++;
        return { ok: true, json: async () => ({ success: true, students: [{ name: 'Ana' }] }) };
    } });
    vm.runInContext(extract(teacherSource, 'let dashboardStudentResizeObserver = null;',
        'function getDashboardStudentPageSize'), teacher);
    await vm.runInContext('Promise.all([fetchDashboardRoster(), fetchDashboardRoster()])', teacher);
    assert.equal(teacherRequests, 1, 'teacher cards and statistics share the in-flight roster');
    await vm.runInContext('fetchDashboardRoster(false)', teacher);
    assert.equal(teacherRequests, 1, 'layout-only updates use the current roster');
    await vm.runInContext('fetchDashboardRoster()', teacher);
    assert.equal(teacherRequests, 2, 'explicit teacher refresh contacts the server');
    console.log('PASS: loaders wait for data, fonts, eager images and paint; late work stays covered; failures release; lazy assets and background polling do not block');
    console.log('PASS: student initial class request deduplicated; teacher roster shared; layout updates use cache; later refresh remains live');
})().catch(error => { console.error(error); process.exitCode = 1; });
