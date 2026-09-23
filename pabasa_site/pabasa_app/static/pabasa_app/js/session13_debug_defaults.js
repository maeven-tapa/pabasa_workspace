(() => {
  'use strict';

  const normalize = () => {
    document.querySelectorAll('[data-session13-controls]').forEach(root => {
      const prefix = root.dataset.prefix;
      if (!prefix) return;
      const panel = document.getElementById(`${prefix}-debug-panel`);
      const expected = document.getElementById(`${prefix}-debug-expected`);
      const expectedLabel = expected?.previousElementSibling;
      if (expectedLabel) expectedLabel.textContent = 'Expected Word';
      if (!panel) return;
      const defaults = {
        transcript: 'No transcript yet.',
        normalized: '—',
        result: '—',
        recorder: 'inactive',
        vad: 'waiting',
        error: '—',
        raw: 'Waiting for speech...',
      };
      Object.entries(defaults).forEach(([key, value]) => {
        const field = document.getElementById(`${prefix}-debug-${key}`);
        if (field && field.textContent.trim() === 'Not available') field.textContent = value;
      });
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', normalize, {once: true});
  else normalize();
})();
