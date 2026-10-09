const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const activityScript = fs.readFileSync(process.argv[2], 'utf8');
const controlsScript = fs.readFileSync(process.argv[3], 'utf8');
const payload = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const speechDebugScript = fs.readFileSync(process.argv[5], 'utf8');
const listeners = new Map();
const nextButton = {};
const oralButton = {};
const debugFields = Object.fromEntries(
  ['expected', 'status', 'result', 'mic', 'recorder', 'vad', 'error', 'output']
    .map(name => [name, {textContent: ''}]),
);
const expected = debugFields.expected;
const debugOutput = debugFields.output;
debugOutput.closest = () => ({
  querySelector(selector) {
    const suffix = selector.match(/-debug-([a-z]+)"/i)?.[1];
    return debugFields[suffix] || null;
  },
});
const app = {
  innerHTML: '',
  querySelector(selector) {
    if (selector === '#next') return nextButton;
    if (selector === '#oral, #oral-retry' || selector === '#oral' || selector === '#oral-retry') return oralButton;
    return null;
  },
  querySelectorAll() { return []; },
};
const dataNode = {type: 'application/json', textContent: JSON.stringify(payload)};
let submittedTarget = '';
const stream = {getTracks: () => [{stop() {}}], getAudioTracks: () => []};
const context = {
  document: {
    cookie: '', scripts: [dataNode],
    getElementById(id) {
      if (id === 'prescribed-activity-data') return dataNode;
      if (id === 'app') return app;
      if (id.startsWith('prescribed-s7-l19-g1-debug-')) return debugFields[id.slice('prescribed-s7-l19-g1-debug-'.length)] || null;
      return null;
    },
    querySelector(selector) {
      if (selector === '[data-prescribed-session-controls]') return {dataset: {prefix: 'prescribed-s7-l19-g1'}};
      if (selector === '[data-speech-debug-output]') return debugOutput;
      return null;
    },
    querySelectorAll(selector) { return selector === '[data-speech-debug-output]' ? [debugOutput] : []; },
  },
  navigator: {mediaDevices: {getUserMedia: async () => stream}},
  Basahin: {
    bindActivity(button, handler) { button.read = handler; },
    openMicrophone: async () => stream,
    capture: async () => new Blob(['audio']),
    isCaptureError: () => false,
  },
  BasahinButton: {LABEL: 'Basahin'},
  PrescribedControls: {init() {}},
  Audio: class {
    play() { Promise.resolve().then(() => this.onended?.()); return Promise.resolve(); }
    pause() {}
  },
  MediaRecorder: class {},
  Blob, FormData, Promise, Uint8Array, AbortController, DOMException,
  CustomEvent: class {constructor(type) {this.type = type;}},
  addEventListener(type, handler) {
    if (!listeners.has(type)) listeners.set(type, []);
    listeners.get(type).push(handler);
  },
  dispatchEvent(event) {for (const handler of listeners.get(event.type) || []) handler(event);},
  setInterval() {return 1;}, clearInterval() {},
  requestAnimationFrame(callback) {callback(); return 1;},
  fetch: async (url, options = {}) => {
    let result;
    if (String(url).includes('transcribe')) {
      submittedTarget = options.body.get('target_text');
      result = {success: false, complete: false};
    } else {
      result = {success: true, progress: {state: JSON.parse(options.body).state}};
    }
    return {ok: true, json: async () => result, clone() {return {json: async () => result};}};
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(activityScript, context, {filename: 'gawain1.js'});
vm.runInContext(speechDebugScript, context, {filename: 'speech_debug.js'});
vm.runInContext(controlsScript, context, {filename: 'prescribed_session8_11_controls.js'});

(async () => {
  assert.equal(expected.textContent, 'Not reading');
  assert.equal(typeof nextButton.onclick, 'function');
  await nextButton.onclick();
  assert.equal(expected.textContent, 'daga');
  assert.equal(debugFields.status.textContent, '', 'A progress save must not appear as an STT response');
  assert.equal(debugFields.result.textContent, '', 'A progress save must not replace the reading result');
  context.dispatchEvent({type: 'basahin:state', detail: {state: 'level', speaking: true}});
  assert.equal(debugFields.status.textContent, 'Listening');
  assert.equal(debugFields.vad.textContent, 'Speaking');
  assert.equal(expected.textContent, 'daga');
  assert.equal(typeof oralButton.read, 'function');
  expected.textContent = 'hikaw';
  const reading = oralButton.read();
  assert.equal(expected.textContent, 'daga');
  await reading;
  assert.equal(submittedTarget, 'daga');
  assert.equal(expected.textContent, 'daga');
  assert.match(debugFields.result.textContent, /Incorrect|No transcript returned/);
  assert.match(debugFields.output.textContent, /STT response/);
})().catch(error => {console.error(error); process.exitCode = 1;});
