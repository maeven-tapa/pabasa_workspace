/* Shared by prescribed Audio Settings; legacy activities submit their own audio. */
(() => {
  'use strict';
  if (window.PrescribedSttSettings) {
    window.PrescribedSttSettings.init();
    return;
  }
  const storageKey = 'pabasa.prescribed.stt-provider';
  const choices = ['google', 'chirp_2', 'chirp_3', 'knowlez'];
  let selection = 'google';
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === 'azure') selection = 'knowlez';
    else if (choices.includes(saved)) selection = saved;
  } catch (_) {}
  const descriptions = {
    google: 'Google speech recognition uses the default model for this activity.',
    chirp_2: 'Chirp 2 is selected. Word values appear in the speech debug panel. Google does not treat these values as true confidence scores.',
    chirp_3: 'Chirp 3 is selected. Word-level confidence is unavailable.',
    knowlez: 'Knowlez speech recognition is selected.',
  };

  const sync = () => document.querySelectorAll('[data-prescribed-stt]').forEach(panel => {
    panel.querySelector('[data-prescribed-stt-select]').value = selection;
    panel.querySelector('[data-prescribed-stt-status]').textContent = descriptions[selection];
  });
  function init() {
    document.querySelectorAll('[data-prescribed-stt-select]').forEach(select => {
      if (select.dataset.sttBound) return;
      select.dataset.sttBound = 'true';
      select.addEventListener('change', () => {
        window.Basahin?.cancelAll?.();
        selection = choices.includes(select.value) ? select.value : 'google';
        try { localStorage.setItem(storageKey, selection); } catch (_) {}
        sync();
      });
    });
    sync();
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, options) => {
    const url = new URL(input?.url || input, window.location.href);
    const method = String(options?.method || input?.method || 'GET').toUpperCase();
    const transcription = url.pathname === '/api/reading/transcribe/'
      || url.pathname === '/api/reading/lesson-1-gawain-1/transcribe/';
    const workbookRecording = /^\/api\/dashboard\/assessment\/activity\/prescribed\/[^/]+\/progress\/$/.test(url.pathname)
      && options?.body instanceof FormData && options.body.has('audio');
    if (url.origin === window.location.origin && method === 'POST' && (transcription || workbookRecording)) {
      const headers = new Headers(options?.headers || input?.headers);
      headers.set('X-Pabasa-STT-Provider', selection === 'knowlez' ? 'knowlez' : 'google');
      if (selection.startsWith('chirp_')) headers.set('X-Pabasa-STT-Model', selection);
      else headers.delete('X-Pabasa-STT-Model');
      return originalFetch(input, {...options, headers});
    }
    return originalFetch(input, options);
  };
  window.PrescribedSttSettings = Object.freeze({init});
  init();
})();
