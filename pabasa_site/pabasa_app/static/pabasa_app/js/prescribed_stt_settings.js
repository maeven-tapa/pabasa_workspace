/* Shared by prescribed Audio Settings; legacy activities submit their own audio. */
(() => {
  'use strict';
  if (window.PrescribedSttSettings) {
    window.PrescribedSttSettings.init();
    return;
  }
  const storageKey = 'pabasa.prescribed.stt-provider';
  let provider = 'google';
  try { if (localStorage.getItem(storageKey) === 'azure') provider = 'azure'; } catch (_) {}

  const sync = () => document.querySelectorAll('[data-prescribed-stt]').forEach(panel => {
    panel.querySelector('[data-prescribed-stt-toggle]').checked = provider === 'azure';
    panel.querySelector('[data-prescribed-stt-status]').textContent = provider === 'azure'
      ? 'Microsoft Azure speech recognition is selected.'
      : 'Google speech recognition is selected.';
  });
  function init() {
    document.querySelectorAll('[data-prescribed-stt-toggle]').forEach(toggle => {
      if (toggle.dataset.sttBound) return;
      toggle.dataset.sttBound = 'true';
      toggle.addEventListener('change', () => {
        window.Basahin?.cancelAll?.();
        provider = toggle.checked ? 'azure' : 'google';
        try { localStorage.setItem(storageKey, provider); } catch (_) {}
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
      headers.set('X-Pabasa-STT-Provider', provider);
      return originalFetch(input, {...options, headers});
    }
    return originalFetch(input, options);
  };
  window.PrescribedSttSettings = Object.freeze({init});
  init();
})();
