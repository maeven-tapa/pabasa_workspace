(() => {
  'use strict';

  const MESSAGE = 'Babalikan mo ito kung saan ka huminto.';
  const ERROR = 'Hindi na-save ang iyong gawain. Subukan muli.';

  window.Session4LeaveConfirmation = {
    init(config) {
      const prefix = config.prefix;
      const modal = document.getElementById(`${prefix}-leave-modal`);
      const no = document.getElementById(`${prefix}-leave-no`);
      const yes = document.getElementById(`${prefix}-leave-yes`);
      const pause = document.getElementById(`${prefix}-pause-modal`);
      const pauseBack = config.pauseBackSelector ? document.querySelector(config.pauseBackSelector) : null;
      const back = document.querySelector(config.backSelector);
      if (!modal || !no || !yes) return;
      if (modal.dataset.leaveInitialized === 'true') return;
      modal.dataset.leaveInitialized = 'true';

      let leaveInFlight = false;
      const message = document.getElementById(`${prefix}-leave-message`);
      const open = source => {
        if (message) message.textContent = MESSAGE;
        modal.dataset.source = source;
        if (source === 'pause' && pause) pause.hidden = true;
        modal.hidden = false;
        no.focus();
      };
      const close = () => { modal.hidden = true; };

      back?.addEventListener('click', event => {
        event.preventDefault();
        open('activity');
      });

      pauseBack?.addEventListener('click', event => {
        event.preventDefault();
        open('pause');
      });

      no.addEventListener('click', event => {
        event.preventDefault();
        close();
        if (modal.dataset.source === 'pause' && pause) pause.hidden = false;
      });

      yes.addEventListener('click', async event => {
        event.preventDefault();
        if (leaveInFlight) return;
        leaveInFlight = true;
        no.disabled = true;
        yes.disabled = true;
        try {
          const state = config.captureState?.();
          await config.cleanup?.();
          if (typeof config.saveCurrentProgress !== 'function') {
            throw new Error('Session 4 leave save adapter is unavailable.');
          }
          await config.saveCurrentProgress(state);
          window.location.href = config.returnUrl || '/dashboard/assessment/';
        } catch (error) {
          console.error(`[${prefix} leave] save failed`, error);
          if (message) message.textContent = ERROR;
          no.disabled = false;
          yes.disabled = false;
          leaveInFlight = false;
        }
      });

      document.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || modal.hidden || leaveInFlight) return;
        const source = modal.dataset.source;
        close();
        if (source === 'pause' && pause) pause.hidden = false;
      });
    },
  };
})();
