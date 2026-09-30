(() => {
  'use strict';

  window.PabasaLessonStart = function initLessonStart({modalId, startId, laterId, backUrl, onStart} = {}) {
    const modal = document.getElementById(modalId);
    const start = document.getElementById(startId);
    const later = document.getElementById(laterId);
    if (!modal || !start || !later) return null;

    let closed = false;
    document.body.classList.add('lesson-start-open');
    const close = (callback) => {
      if (closed) return;
      closed = true;
      start.disabled = true;
      later.disabled = true;
      try {
        callback?.();
      } finally {
        modal.remove();
        document.body.classList.remove('lesson-start-open');
      }
    };
    start.addEventListener('click', () => close(onStart));
    later.addEventListener('click', () => {
      if (closed) return;
      closed = true;
      start.disabled = true;
      later.disabled = true;
      document.body.classList.remove('lesson-start-open');
      window.location.href = backUrl || document.getElementById('wb-back')?.href || '/dashboard/assessment/';
    });
    return {close};
  };
})();
