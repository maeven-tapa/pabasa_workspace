(() => {
  'use strict';

  const states = new Map();
  const fieldNames = ['status', 'transcript', 'expected', 'normalized', 'result', 'mic', 'recorder', 'vad', 'error', 'raw'];

  const stateFor = prefix => states.get(prefix);
  const write = (state, key, value) => {
    const field = state.fields[key];
    const next = String(value ?? 'Not available');
    if (field && field.textContent !== next) field.textContent = next;
  };

  const update = (prefix, patch = {}, event = '') => {
    const state = stateFor(prefix);
    if (!state) return;
    Object.entries(patch).forEach(([key, value]) => {
      if (fieldNames.includes(key)) write(state, key, value);
    });
    if (event) {
      state.history.push(event);
      while (state.history.length > 6) state.history.shift();
      write(state, 'raw', state.history.join('\n'));
    }
  };

  const init = ({ prefix, expected = '', normalize = value => String(value || '').trim().toLowerCase().replace(/[^a-z0-9áéíóúñ ]/gi, ''), transcript = result => result?.transcript || result?.raw_transcript || '', evaluateResult = null }) => {
    if (!prefix || states.has(prefix)) return;
    const q = suffix => document.getElementById(`${prefix}${suffix}`);
    const state = {
      prefix,
      normalize,
      transcript,
      evaluateResult,
      fields: Object.fromEntries(fieldNames.map(key => [key, q(`-debug-${key}`)])),
      history: [],
    };
    states.set(prefix, state);
    write(state, 'status', 'Ready');
    write(state, 'expected', expected || 'Not available');
    write(state, 'recorder', 'Inactive');
    write(state, 'mic', `Inactive · ${q('-mic-toggle')?.getAttribute('aria-pressed') === 'true' ? 'Muted' : 'Unmuted'}`);
    write(state, 'vad', 'Not available');
    write(state, 'error', 'Not available');
  };

  window.Session2PrescribedDebug = { init, update };

  const prefixes = () => Array.from(states.keys());
  const targetFromBody = body => body instanceof FormData ? String(body.get('target_text') || '').trim() : '';

  if (window.MediaRecorder && !window.MediaRecorder.__session2DebugWrapped) {
    const OriginalRecorder = window.MediaRecorder;
    const WrappedRecorder = new Proxy(OriginalRecorder, {
      construct(target, args, newTarget) {
        const recorder = Reflect.construct(target, args, newTarget);
        recorder.addEventListener?.('start', () => prefixes().forEach(prefix => update(prefix, { status: 'Listening', recorder: 'Recording' }, 'Recording started')));
        recorder.addEventListener?.('stop', () => prefixes().forEach(prefix => update(prefix, { status: 'Processing', recorder: 'Inactive' }, 'Recording stopped')));
        recorder.addEventListener?.('error', event => prefixes().forEach(prefix => update(prefix, { error: event.error?.message || 'Recorder error', recorder: 'Inactive' }, 'Recorder error')));
        return recorder;
      },
    });
    WrappedRecorder.__session2DebugWrapped = true;
    window.MediaRecorder = WrappedRecorder;
  }

  if (window.fetch && !window.fetch.__session2DebugWrapped) {
    const originalFetch = window.fetch.bind(window);
    const wrappedFetch = (input, init) => {
      const url = typeof input === 'string' ? input : input?.url || '';
      const body = init?.body;
      const target = targetFromBody(body);
      const isTranscription = url.includes('transcrib') && target;
      if (isTranscription) {
        prefixes().forEach(prefix => update(prefix, { status: 'Processing', expected: target, error: 'Not available' }, 'STT request started'));
      }
      return originalFetch(input, init).then(response => {
        if (!isTranscription) return response;
        response.clone().json().then(result => {
            prefixes().forEach(prefix => {
              const state = stateFor(prefix);
              const recognized = state.transcript(result);
              const normalized = recognized ? state.normalize(recognized) : '';
              update(prefix, {
                status: 'Ready',
                transcript: recognized || 'Not available',
                normalized: normalized || 'Not available',
                expected: target || 'Not available',
                result: typeof state.evaluateResult === 'function' ? (state.evaluateResult(result, recognized, target) ? 'Correct' : 'Incorrect') : 'Not available',
                error: result?.error ? String(result.error) : 'Not available',
              }, recognized ? `Transcript received: ${recognized}` : 'STT returned no transcript');
          });
        }).catch(() => prefixes().forEach(prefix => update(prefix, { error: 'Unable to read STT response' }, 'STT response error')));
        return response;
      }).catch(error => {
        if (isTranscription) prefixes().forEach(prefix => update(prefix, { status: 'Ready', error: error.message || 'STT request failed' }, 'STT request failed'));
        throw error;
      });
    };
    wrappedFetch.__session2DebugWrapped = true;
    window.fetch = wrappedFetch;
  }
})();
