// JavaScript regression checks; these do not replace a live browser test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname,
  '../pabasa_site/pabasa_app/templates/pabasa_app/salitang_magkatugma_page.html'), 'utf8');
const progressKey = 'pabasa:lesson-2-gawain-1:progress';
const completionKey = 'pabasa:salitang-magkatugma:completed';
const storage = new Map([['unrelated-activity', 'keep']]);
let server = null;

function load() {
  const elements = Object.fromEntries(['stage', 'progress', 'read', 'listen', 'status'].map(id => [id, {}]));
  const context = vm.createContext({
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    document: {
      getElementById: id => elements[id],
      querySelectorAll: () => [],
      cookie: '',
    },
    read: elements.read,
    listen: elements.listen,
    lesson2ProgressUrl: '/progress/',
    fetch: (url, options) => {
      server = JSON.parse(options.body);
      return Promise.resolve({});
    },
    console,
  });
  const script = template.split('<script>')[1].split('</script>')[0]
    .replace('{{ lesson_2_progress|default:"null"|safe }}', JSON.stringify(server))
    .replace(/{%.*?%}/g, '/test/');
  vm.runInContext(script, context);
  assert.equal(storage.get('unrelated-activity'), 'keep');
  return {context, elements};
}

function assertFresh() {
  const {context, elements} = load();
  assert.equal(vm.runInContext('JSON.stringify([pi,wi,ra,aa,busy])', context), '[0,0,[0,0],0,false]');
  assert.equal(elements.progress.textContent, 'Pares 1 / 5');
  assert.match(elements.stage.innerHTML, /Basahin ang aso\./);
  assert.match(elements.stage.innerHTML, /id="answers" hidden/);
  assert.equal(storage.has(progressKey), false);
  assert.equal(storage.has(completionKey), false);
}

assertFresh();
let page = load();
vm.runInContext("answer('right'); answer('right'); answer('right');", page.context);
assert.equal(server.current_index, 3);
page = load();
assert.equal(page.elements.progress.textContent, 'Pares 4 / 5');
assert.equal(vm.runInContext('pi', page.context), 3);

// Resetting the server row must win over both stale browser keys.
storage.set(completionKey, 'true');
server = {current_index: 0, completed_items: 0, activity_completed: false};
assertFresh();
// Completion alone previously escaped the guard when both indices were zero.
storage.set(completionKey, 'true');
assertFresh();
// Deleting the server row is also a reset.
storage.set(progressKey, '5');
storage.set(completionKey, 'true');
server = null;
assertFresh();

// Persistence still works after resetting, and server progress can restore a cache.
page = load();
vm.runInContext("answer('right'); answer('right');", page.context);
assert.equal(load().elements.progress.textContent, 'Pares 3 / 5');
storage.delete(progressKey);
assert.equal(load().elements.progress.textContent, 'Pares 3 / 5');
server = {current_index: 5, completed_items: 5, activity_completed: true};
load();
assert.equal(storage.get(progressKey), '5');
assert.equal(storage.get(completionKey), 'true');
console.log('PASS: reset row, deleted row, stale completion, fresh state, normal persistence before/after reset, server restoration, unrelated storage preserved.');
