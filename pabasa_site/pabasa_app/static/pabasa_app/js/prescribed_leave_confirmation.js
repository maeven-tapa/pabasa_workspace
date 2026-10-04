(() => {
  'use strict';

  if (window.__prescribedLeaveConfirmationInitialized) return;
  window.__prescribedLeaveConfirmationInitialized = true;

  const initialize = () => {

  const host = document.querySelector('[data-prescribed-leave-prefix]');
  const inferred = [
    ['lesson28a1-back', 'prescribed-l28a1'], ['lesson28a2-back', 'prescribed-l28a2'],
    ['lesson29a1-back', 'prescribed-s13l29g1'], ['lesson29a2-back', 'prescribed-s13l29g2'],
    ['lesson29a3-back', 'prescribed-s13l29g3'],
    ['lesson30a1-back', 'lesson30a1'], ['lesson30a2-back', 'lesson30a2'],
    ['lesson30a3-back', 'lesson30a3'],
    ['lesson31a1-back', 'lesson31a1'], ['lesson31a2-back', 'lesson31a2'],
    ['lesson31a3-back', 'lesson31a3'], ['lesson31a4-back', 'lesson31a4'],
  ].find(([id]) => document.getElementById(id));
  if (!host && !inferred) return;

  const prefix = host?.dataset.prescribedLeavePrefix || inferred[1];
  const modal = document.getElementById(`${prefix}-leave-modal`);
  const leaveButton = document.getElementById(`${prefix}-leave-yes`);
  const stayButton = document.getElementById(`${prefix}-leave-no`);
  const error = document.getElementById(`${prefix}-leave-error`);
  const backLink = document.querySelector('[data-prescribed-leave-back]') || document.getElementById(inferred?.[0]);
  const pauseModal = document.getElementById(`${prefix}-pause-modal`);
  const pauseBackButton = pauseModal?.querySelector(`[id="${prefix}-back"]`);
  if (!modal) {
    const controls = prefix.startsWith('prescribed-s13') ? 'session13-controls' :
      prefix.startsWith('lesson30a') ? 'l30-controls' :
      prefix.startsWith('lesson31a') ? 's15' : prefix;
    const className = `${controls}-modal`;
    const cardClass = `${controls}-${controls === prefix ? 'modal-card' : 'card'}`;
    const actionsClass = controls === 'session13-controls' ? 'session13-controls-actions' :
      controls === 'l30-controls' ? 'l30-controls-actions' :
      controls === 's15' ? 's15-actions' : `${prefix}-pause-actions`;
    const headClass = controls === 'session13-controls' ? 'session13-controls-head' :
      controls === 'l30-controls' ? 'l30-controls-head' :
      controls === 's15' ? 's15-head' : `${prefix}-modal-head`;
    const container = document.createElement('div');
    container.className = className;
    container.id = `${prefix}-leave-modal`;
    container.hidden = true;
    container.setAttribute('role', 'dialog');
    container.setAttribute('aria-modal', 'true');
    container.setAttribute('aria-labelledby', `${prefix}-leave-title`);
    container.innerHTML = `<section class="${cardClass}"><div class="${headClass}"><h2 id="${prefix}-leave-title">Are you sure you want to leave?</h2></div><p>You can continue from where you left off.</p><p id="${prefix}-leave-error" role="alert" hidden>Your activity could not be saved. Please try again.</p><div class="${actionsClass}"><button class="primary" id="${prefix}-leave-no" type="button">Stay</button><button class="secondary" id="${prefix}-leave-yes" type="button">Leave</button></div></section>`;
    document.body.append(container);
  }
  const activeModal = document.getElementById(`${prefix}-leave-modal`);
  const activeLeaveButton = document.getElementById(`${prefix}-leave-yes`);
  const activeStayButton = document.getElementById(`${prefix}-leave-no`);
  const activeError = document.getElementById(`${prefix}-leave-error`);
  if (!activeModal || !activeLeaveButton || !activeStayButton || !backLink) return;

  let source = 'page';
  let leaving = false;

  function adapter() {
    return window.__prescribedLeaveAdapters?.[prefix] || {
      // Activity progress is persisted at each completed answer or phase change.
      saveCurrentProgress: () => Promise.resolve(),
      cleanup() {
        window.dispatchEvent(new Event('pagehide'));
      },
    };
  }

  function hideError() {
    activeError.hidden = true;
  }

  function requestLeave(nextSource) {
    if (leaving) return;
    source = nextSource;
    hideError();
    if (source === 'pause' && pauseModal) pauseModal.hidden = true;
    activeModal.hidden = false;
    activeStayButton.focus();
  }

  function stay() {
    if (leaving) return;
    activeModal.hidden = true;
    if (source === 'pause' && pauseModal) pauseModal.hidden = false;
  }

  async function leave() {
    if (leaving) return;
    const activityAdapter = adapter();

    leaving = true;
    activeLeaveButton.disabled = true;
    activeStayButton.disabled = true;
    hideError();
    try {
      await activityAdapter.saveCurrentProgress();
      await activityAdapter.cleanup();
      window.location.assign(backLink.href);
    } catch (saveError) {
      console.error('Prescribed activity leave save failed', saveError);
      activeError.hidden = false;
      leaving = false;
      activeLeaveButton.disabled = false;
      activeStayButton.disabled = false;
    }
  }

  backLink.addEventListener('click', event => {
    event.preventDefault();
    requestLeave('page');
  });
  pauseBackButton?.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    requestLeave('pause');
  }, true);
  activeStayButton.addEventListener('click', stay);
  activeLeaveButton.addEventListener('click', leave);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !activeModal.hidden) {
      event.preventDefault();
      stay();
    }
  });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
