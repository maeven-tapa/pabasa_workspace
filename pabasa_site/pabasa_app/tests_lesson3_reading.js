// Unit-run the actual template's record/answer functions with endpoint verdicts.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(input.template, 'utf8');
const pairs = JSON.parse(source.match(/const pairs=(\[.*?\]),base=/)[1]
  .replace(/\b(a|b|yes):/g, '"$1":').replace(/'/g, '"'));
assert.deepEqual(pairs.map(p => [p.a, p.b, p.yes]), input.pairs);
const record = source.slice(source.indexOf('async function record(){'), source.indexOf('function listen(){'));
const answer = source.slice(source.indexOf('function answer(v){'), source.indexOf('function startLessonActivity(){'));

function element() {
  return {disabled: false, hidden: false, textContent: '',
    classList: {add() {}, remove() {}}, setAttribute() {}, removeAttribute() {}};
}
function setup(result, {ok = true, fail = false, stale = false} = {}) {
  const read = element(), status = element(), listen = element();
  let stopped = 0, renders = 0;
  const stream = {getTracks: () => [{stop() {stopped++;}}]};
  const context = vm.createContext({
    FormData, Blob, console, read, status, listen, MediaRecorder: function () {},
    navigator: {mediaDevices: {getUserMedia: async () => stream}},
    document: {querySelector: () => read, cookie: ''},
    localStorage: {setItem() {}},
    window: {BasahinButton: {LABEL: 'Basahin'}, Basahin: {
      openMicrophone: async () => stream,
      capture: async () => new Blob(['synthetic audio'], {type: 'audio/webm'}),
      attachStreamResult() {},
    }},
    fetch: async (url, options) => {
      assert.equal(options.body.get('prescribed_activity_key'), 'lesson-3-gawain-1');
      assert.equal(options.body.get('language'), 'Filipino');
      assert.equal(options.body.get('target_text'), 'WALO');
      assert.ok(options.body.get('audio').size);
      if (stale) vm.runInContext('generation++; pi=4; wi=0;', context);
      if (fail) throw Error('simulated provider failure');
      return {ok, json: async () => result};
    },
    render() {renders++;},
  });
  vm.runInContext(`const pairs=${JSON.stringify(pairs)}; let pi=3,wi=0,rt=[0,0],li=[0,0],at=0,busy=false,generation=0;
    const words=()=>[pairs[pi].a,pairs[pi].b]; const progressKey='test-progress'; ${record} ${answer}`, context);
  return {context, read, status, get stopped() {return stopped;}, get renders() {return renders;}};
}
(async () => {
  for (const [result, expected] of [[input.correct, 1], [input.incorrect, 0]]) {
    const test = setup(result);
    await vm.runInContext('record()', test.context);
    assert.equal(vm.runInContext('wi', test.context), expected);
    assert.equal(vm.runInContext('busy', test.context), false);
    assert.ok(test.stopped > 0);
    assert.equal(test.renders, expected);
    if (!expected) {
      assert.equal(vm.runInContext('rt[0]', test.context), 1);
      assert.equal(test.read.disabled, false);
      assert.match(test.status.textContent, /Subukan muli/);
    }
  }
  for (const [result, options] of [
    [input.correct, {stale: true}], [input.correct, {ok: false}],
    [input.correct, {fail: true}],
    [{...input.correct, words: ['TATLO']}, {}],
    [{...input.correct, success: false}, {}],
  ]) {
    const test = setup(result, options);
    await vm.runInContext('record()', test.context);
    assert.equal(vm.runInContext('wi', test.context), 0);
    assert.equal(vm.runInContext('busy', test.context), false);
    assert.equal(test.renders, 0);
  }
  for (let index=0; index<pairs.length; index++) {
    const gated = setup(input.correct);
    vm.runInContext(`pi=${index}; wi=0; answer('${pairs[index].yes ? 'yes' : 'no'}')`, gated.context);
    assert.equal(vm.runInContext('pi', gated.context), index);
    const test = setup(input.correct);
    vm.runInContext(`pi=${index}; wi=2; answer('${pairs[index].yes ? 'yes' : 'no'}')`, test.context);
    assert.equal(vm.runInContext('pi', test.context), index + 1);
    assert.equal(vm.runInContext('wi', test.context), 0);
    const wrong = setup(input.correct);
    vm.runInContext(`pi=${index}; wi=2; answer('${pairs[index].yes ? 'no' : 'yes'}')`, wrong.context);
    assert.equal(vm.runInContext('pi', wrong.context), index);
  }
  console.log('Production record/answer functions: acceptance, rejection, HTTP/provider failures, stale responses, stream cleanup, six rhyme answers passed.');
})().catch(error => {console.error(error); process.exitCode=1;});
