const assert = require('node:assert/strict');
const vm = require('node:vm');
const {environment} = require('./test_lesson13_gawain2.cjs');

async function run(controller, modalSource) {
  const env = environment(controller, {index: 2});
  await env.start.onclick();
  await env.window.__session5LeaveAdapter.saveCurrentProgress();
  assert.deepEqual(JSON.parse(env.calls.at(-1).request.body),
    {state: {current_index: 2, completed_items: 2, phase: 'active'}});
  const badSave = environment(controller, {saveSuccess: false});
  await assert.rejects(badSave.window.__session5LeaveAdapter.saveCurrentProgress(), /Progress save failed/);

  // Automatic instruction playback must not start behind any blocking modal.
  for (const name of ['help', 'pause', 'restart', 'audio-settings', 'leave']) {
    const blocked = environment(controller);
    blocked.ids['prescribed-s5l13g2-' + name + '-modal'] = {hidden: false};
    await blocked.start.onclick();
    assert.equal(blocked.feedback.length, 0, name);
  }
  const interrupted = environment(controller);
  const starting = interrupted.start.onclick();
  interrupted.window.__session5LeaveAdapter.stopInstruction();
  await starting;
  assert.equal(interrupted.paused.length, 1);
  assert.equal(interrupted.feedback.length, 1, 'Stopping instruction cannot replay it');
  assert.equal(interrupted.read.disabled, false, 'Stopping releases the existing audio lock');

  // Exercise the actual modal binding twice to verify handler deduplication.
  function element() {
    return {dataset: {}, listeners: {}, disabled: false, hidden: false,
      setAttribute() {}, addEventListener(name, cb) {(this.listeners[name] ||= []).push(cb);},
      async click() {for (const cb of this.listeners.click || []) await cb({preventDefault() {}});}};
  }
  const prefix = 'prescribed-s5l13g2', ids = {};
  for (const suffix of ['pause-modal','back','resume','restart','audio-test','help-btn',
      'audio-settings-btn','help-ack','help-close']) ids[prefix+'-'+suffix] = element();
  const actions = ['back','resume','restart','audio-test'].map(s => ids[prefix+'-'+s]);
  let error;
  ids[prefix+'-pause-modal'].querySelectorAll = () => actions;
  ids[prefix+'-pause-modal'].querySelector = () => ({before(el) {error = el;}});
  const document = {getElementById: id => ids[id], createElement: element};
  let release, saves = 0, cleanups = 0, stops = 0, closes = 0;
  const destinations = [];
  let rejectSave = false;
  const window = {location: {assign: url => destinations.push(url)}, __session5LeaveAdapter: {
    cleanup: async () => {cleanups++;}, stopInstruction: () => {stops++;},
    saveCurrentProgress: async () => {saves++; if (rejectSave) throw Error('save failed');
      await new Promise(resolve => {release = resolve;});}
  }};
  ids[prefix+'-help-close'].addEventListener('click', () => {closes++;});
  const context = {document, window, console: {error() {}}};
  vm.runInNewContext(modalSource, context);
  vm.runInNewContext(modalSource, context);
  assert.equal(ids[prefix+'-back'].listeners.click.length, 1);
  await ids[prefix+'-help-btn'].click(); await ids[prefix+'-audio-settings-btn'].click();
  assert.equal(stops, 2);
  await ids[prefix+'-help-ack'].click(); assert.equal(closes, 1);
  const first = ids[prefix+'-back'].click();
  for (let n = 0; n < 5; n++) await Promise.resolve();
  await ids[prefix+'-back'].click();
  assert.equal(saves, 1); assert.equal(cleanups, 1);
  assert.ok(actions.every(a => a.disabled)); assert.equal(destinations.length, 0);
  release(); await first;
  assert.deepEqual(destinations, ['/dashboard/assessment/']);

  // Fresh failed-save instance must remain on the page and permit retry.
  ids[prefix+'-back'].dataset = {}; ids[prefix+'-back'].listeners = {};
  vm.runInNewContext(modalSource, context);
  rejectSave = true;
  await ids[prefix+'-back'].click();
  assert.equal(destinations.length, 1); assert.equal(error.hidden, false);
  assert.ok(actions.every(a => !a.disabled));
  rejectSave = false;
  const retry = ids[prefix+'-back'].click();
  for (let n = 0; n < 5; n++) await Promise.resolve();
  release(); await retry;
  assert.equal(destinations.length, 2);
  console.log('PASS: saved state, failed-save guard, deduplication, awaited return, retry, Help acknowledgment');
}
module.exports = {run};
