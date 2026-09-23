(() => {
  'use strict';

  const debugPreference = 'pabasaShowSpeechDebugPanel';

  function init({ prefix, adapter, speech = false }) {
    if (!window.PrescribedControls || document.documentElement.dataset[`${prefix}ControlsReady`]) return;
    const q = suffix => document.getElementById(`${prefix}${suffix}`);
    const debug = {
      panel: q('-debug-panel'),
      toggle: q('-debug-toggle'),
      values: {
        status: q('-debug-status'), transcript: q('-debug-transcript'), expected: q('-debug-expected'),
        normalized: q('-debug-normalized'), result: q('-debug-result'), mic: q('-debug-mic'),
        recorder: q('-debug-recorder'), vad: q('-debug-vad'), error: q('-debug-error'), raw: q('-debug-raw')
      }
    };
    const publish = state => {
      const s = state || {};
      Object.entries({
        status: s.status ?? 'Ready', transcript: s.transcript ?? 'No transcript yet.',
        expected: s.expected ?? '—', normalized: s.normalized ?? '—', result: s.result ?? '—',
        mic: s.mic ?? 'Inactive · Unmuted', recorder: s.recorder ?? 'inactive',
        vad: s.vad ?? 'Not available', error: s.error ?? '—'
      }).forEach(([key, value]) => { if (debug.values[key]) debug.values[key].textContent = value; });
      if (debug.values.raw && s.event) {
        const entries = (debug.values.raw.dataset.entries ? JSON.parse(debug.values.raw.dataset.entries) : []);
        entries.unshift(`${new Date().toLocaleTimeString()} — ${s.event}`);
        const bounded = entries.slice(0, 6);
        debug.values.raw.dataset.entries = JSON.stringify(bounded);
        debug.values.raw.textContent = bounded.join('\n');
      }
    };
    const audioTestBinder = adapter.bindAudioTest;
    const debugBinder = adapter.bindDebug;
    adapter.bindAudioTest = (...args) => {
      try { return audioTestBinder?.(...args); } catch (_) { return undefined; }
    };
    adapter.bindDebug = (...args) => {
      try { return debugBinder?.(...args); } catch (_) { return undefined; }
    };
    adapter.publishDebug = state => publish(state);
    try {
      window.PrescribedControls.init({ prefix, adapter });
    } catch (_) {
      return;
    }
    document.documentElement.dataset[`${prefix}ControlsReady`] = '1';
    const help = q('-help-btn');
    help?.addEventListener('click', () => adapter.help?.(), { capture: true });
    const audioClose = q('-audio-close');
    audioClose?.addEventListener('click', () => adapter.stopAudioTest?.(), { capture: true });
  }

  window.Session4PrescribedControls = { init, debugPreference };
})();
