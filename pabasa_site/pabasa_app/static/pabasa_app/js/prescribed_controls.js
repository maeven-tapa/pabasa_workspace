(() => {
  'use strict';
  window.PrescribedControls = {
    init(config) {
      // Cancel shared speech work before a pause, navigation, reset or mute can
      // make an in-flight result belong to a different activity state.
      const cancelReading = () => window.Basahin?.cancelAll();
      const q = id => document.getElementById(`${config.prefix}${id}`);
      window.addEventListener('basahin:state', event => {
        const detail = event.detail || {};
        const field = q('-debug-vad');
        if (!field) return;
        const value = detail.state === 'level'
          ? (detail.calibrating ? 'Calibrating' : detail.speaking ? 'Speech detected' : 'Quiet')
          : detail.state === 'silence' ? 'Silent clip skipped' : 'Listening';
        if (field.textContent !== value) field.textContent = value;
      });
      const help = q('-help-modal'), pause = q('-pause-modal'), restart = q('-restart-modal'), audio = q('-audio-settings-modal');
      const close = modal => { if (modal) modal.hidden = true; };
      const closeAll = () => [help, pause, restart, audio].forEach(close);
      const open = modal => { closeAll(); if (modal) modal.hidden = false; };
      q('-help-btn')?.addEventListener('click', () => { cancelReading(); open(help); });
      q('-help-close')?.addEventListener('click', () => close(help));
      q('-audio-settings-btn')?.addEventListener('click', () => { cancelReading(); config.adapter.pause?.(); open(pause); });
      q('-resume')?.addEventListener('click', () => { close(pause); config.adapter.resume?.(); });
      q('-restart')?.addEventListener('click', () => open(restart));
      q('-restart-yes')?.addEventListener('click', async () => { cancelReading(); close(restart); await config.adapter.restart?.(); });
      q('-restart-no')?.addEventListener('click', () => open(pause));
      q('-back')?.addEventListener('click', () => { cancelReading(); closeAll(); config.adapter.cleanup?.(); window.location.href = '/dashboard/assessment/'; });
      q('-audio-test')?.addEventListener('click', () => open(audio));
      q('-audio-close')?.addEventListener('click', () => open(pause));
      [help, pause, restart, audio].forEach(modal => modal?.addEventListener('click', e => { if (e.target === modal) { if (modal === audio) open(pause); else close(modal); } }));
      const mic = q('-mic-toggle');
      mic?.addEventListener('click', () => { const muted = !(mic.getAttribute('aria-pressed') === 'true'); if (muted) cancelReading(); config.adapter.setMuted?.(muted); });
      window.addEventListener('keydown', e => { if (e.key === 'Escape' && audio && !audio.hidden) open(pause); });
      config.adapter.bindAudioTest?.({audio, q});
      config.adapter.bindDebug?.({q});
    }
  };
})();
