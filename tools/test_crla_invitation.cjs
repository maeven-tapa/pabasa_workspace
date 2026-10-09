const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname,
  '../pabasa_site/pabasa_app/templates/pabasa_app/base_dashboard.html'), 'utf8');
const script = template.slice(template.indexOf('        let liveAssessmentInviteWatchTimer'),
  template.indexOf('        function renderMissedAssessmentModalContent'));
let now = 1000;
let requests = 0;
let redirects = 0;
let hidden = 0;
let removed = 0;
let reply = { success: true, session: null, invitation_disabled: true, retry_after_seconds: 30 };
let modal = { remove: () => { removed++; modal = null; } };
const storage = { getItem: () => null, setItem: () => {} };
const context = vm.createContext({
  Date: { now: () => now },
  console: { debug() {}, warn() {} },
  document: { getElementById: () => modal },
  bootstrap: { Modal: { getInstance: () => ({ hide: () => { hidden++; } }) } },
  window: {
    PABASA_USER_ROLE: 'student', localStorage: storage, sessionStorage: storage,
    bootstrap: true,
    location: { pathname: '/dashboard/assessment/', href: '/dashboard/assessment/',
      assign: () => { redirects++; } },
  },
  fetch: async () => { requests++; return { status: 200, json: async () => reply }; },
});
vm.runInContext(script, context);
const check = () => vm.runInContext('checkForActiveLiveAssessmentInvitation()', context);

(async () => {
  assert.equal(await check(), false);
  assert.equal(requests, 1);
  assert.equal(hidden, 1);
  assert.equal(removed, 1);
  assert.equal(redirects, 0);
  now += 3000;
  await check();
  assert.equal(requests, 1, 'Completed students should not fetch another invitation every three seconds');
  now += 27000;
  reply = { success: true, session: { id: 'later-crla', status: 'waiting',
    redirect_to_waiting_room: true, join_url: '/dashboard/live-assessment/later-crla/waiting/' } };
  assert.equal(await check(), true);
  assert.equal(requests, 2);
  assert.equal(redirects, 1, 'A later CRLA invitation must still be available');
  modal = { remove: () => { removed++; } };
  reply = { success: false };
  await check();
  assert.equal(removed, 1, 'A failed lookup must not dismiss a valid invitation');
  reply = { success: true, session: null };
  await check();
  assert.equal(removed, 2, 'An invitation that is no longer available must close');
  console.log('CRLA invitation client checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
