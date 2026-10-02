(function () {
  'use strict';
  if (typeof window.__lessonStartReady !== 'boolean') window.__lessonStartReady = false;
  const originalSpeak = window.speechSynthesis?.speak;
  if (originalSpeak) window.speechSynthesis.speak = u => { if (window.__lessonStartReady) originalSpeak.call(window.speechSynthesis, u); };
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    const body = init?.body;
    if (!window.__lessonStartReady && body && String(body).includes('target_text=')) return Promise.reject(new Error('Lesson has not started'));
    return originalFetch.apply(this, arguments);
  };

  // Public API for newer activities that provide their own modal markup.
  window.PabasaLessonStart = function ({modalId, startId, laterId, backUrl, onStart} = {}) {
    const modal = document.getElementById(modalId), start = document.getElementById(startId), later = document.getElementById(laterId);
    if (!modal || !start || !later) return null;
    let closed = false;
    document.body.classList.add('lesson-start-open');
    const close = callback => { if (closed) return; closed = true; start.disabled = true; later.disabled = true; try { callback?.(); } finally { modal.remove(); document.body.classList.remove('lesson-start-open'); } };
    start.addEventListener('click', () => close(onStart));
    later.addEventListener('click', () => { if (closed) return; closed = true; start.disabled = true; later.disabled = true; document.body.classList.remove('lesson-start-open'); window.location.href = backUrl || document.getElementById('wb-back')?.href || '/dashboard/assessment/'; });
    return {close};
  };

  function closeModal(button) {
    const backdrop = button.closest('.lesson-start-backdrop');
    if (!backdrop || window.__lessonStartReady) return;
    backdrop.remove(); document.body.classList.remove('lesson-start-open');
    if (document.body.classList.contains('gawain-2') || location.pathname.toLowerCase().includes('lesson-3-gawain-2')) {
      const unlock = new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAESsAAABAAgAZGF0YQAAAAA='); unlock.volume = 0; unlock.play().catch(() => {});
    }
    window.__lessonStartReady = true; window.dispatchEvent(new Event('lesson-start-ready'));
  }
  function resumeConfig() {
    const config = window.__lessonStartProgress;
    if (!config || !config.progress) return null;
    const progress = config.progress;
    if (progress.activity_completed === true) return {config, progress, state: 'completed'};
    const state = progress.state && typeof progress.state === 'object' ? progress.state : {};
    const freshPhases = new Set(['', 'initial', 'say', 'oral', 'oral_syllables', 'read', 'preview', 'ready']);
    const hasStateProgress = Object.entries(state).some(([key, value]) => {
      if (key === 'phase') return !freshPhases.has(String(value || '').toLowerCase());
      if (Array.isArray(value)) return value.some(item => item !== null && item !== undefined && item !== '');
      if (typeof value === 'number') return value > 0;
      if (typeof value === 'boolean') return value;
      return false;
    });
    return {config, progress, state: Number(progress.current_index) > 0 || Number(progress.completed_items) > 0 || hasStateProgress ? 'resume' : 'fresh'};
  }
  function startCompletedActivity() { if (!window.__lessonStartReady) { window.__lessonStartReady = true; window.dispatchEvent(new Event('lesson-start-ready')); } }

  function mount() {
    // Explicit activities already own their markup and initialize via the API.
    if (document.querySelector('.lesson-start-backdrop')) return;
    const path = location.pathname.toLowerCase();
    let target = null;
    if (document.body.classList.contains('gawain-2') || path.includes('lesson-3-gawain-2')) target = ['lesson-3-g2-start', 'SESSION 1 · LESSON 3 · GAWAIN 2'];
    else if (document.body.classList.contains('lesson-3-responsive') || path.includes('lesson-3-gawain-1')) target = ['lesson-3-g1-start', 'SESSION 1 · LESSON 3 · GAWAIN 1'];
    else if (document.querySelector('.salitang-speech-debug') || path.includes('lesson2-gawain1')) target = ['lesson-2-g1-start', 'SESSION 1 · LESSON 2 · GAWAIN 1'];
    else if (document.body.classList.contains('lesson-4-responsive') || path.includes('lesson-4/gawain-1')) target = ['lesson-4-g1-start', 'SESSION 2 · LESSON 4 · GAWAIN 1'];
    else if (path.includes('session-2-lesson-4-gawain-2') || path.includes('lesson4-gawain2')) target = ['session-2-lesson-4-g2-start', 'SESSION 2 · LESSON 4 · GAWAIN 2'];
    else if (path.includes('lesson-5/gawain-1')) target = ['lesson-5-g1-start', 'SESSION 2 · LESSON 5 · GAWAIN 1'];
    else if (path.includes('lesson-6/gawain-1')) target = ['lesson-6-g1-start', 'SESSION 2 · LESSON 6 · GAWAIN 1'];
    else if (window.__lessonStartProgress?.sessionKey === 'session-3') target = ['session-3-start', 'SESSION 3 · LESSON ' + (window.__lessonStartProgress.lessonNumber || '') + ' · GAWAIN ' + (window.__lessonStartProgress.gawainNumber || '')];
    if (!target) return;
    const link = document.createElement('link'); link.rel = 'stylesheet'; link.href = '/static/pabasa_app/css/lesson_start_modal.css'; document.head.append(link);
    const [id, label] = target, saved = resumeConfig();
    if (saved?.state === 'completed') return startCompletedActivity();
    const backdrop = document.createElement('div'); backdrop.className = 'lesson-start-backdrop lesson-13-start-backdrop'; backdrop.id = id; backdrop.setAttribute('role', 'dialog'); backdrop.setAttribute('aria-modal', 'true');
    const metadata = window.__lessonStartProgress || {}, match = path.match(/(?:session-2-)?lesson-?(\d+)(?:\/|-)?gawain-?([\w-]+)/), derivedLabel = match ? `SESSION 2 · LESSON ${match[1]} · GAWAIN ${match[2].toUpperCase()}` : null, session3Label = metadata.sessionKey === 'session-3' ? `SESSION 3 · LESSON ${metadata.lessonNumber || ''} · GAWAIN ${metadata.gawainNumber || ''}` : null, isResume = saved?.state === 'resume';
    const modalLabel = metadata.activityLabel || session3Label || derivedLabel || label, title = metadata.activityTitle || document.title.replace(/^Lesson\s+\d+\s*·\s*Gawain\s+[^:]+:\s*/i, '') || (isResume ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : 'Salitang Magkatugma');
    backdrop.innerHTML = `<div class="lesson-start-modal lesson-13-start-modal"><p class="lesson-start-label lesson-13-start-label">${modalLabel}</p><h2 class="lesson-start-title lesson-13-start-title">${title}</h2><div class="lesson-start-actions lesson-13-start-actions"><button type="button" data-start>${isResume ? 'IPAGPATULOY' : 'SIMULAN'}</button><button type="button" data-later>${isResume ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button></div></div>`;
    document.body.prepend(backdrop); document.body.classList.add('lesson-start-open'); backdrop.querySelector('[data-start]').focus(); if (isResume) backdrop.dataset.resume = 'true';
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('.lesson-start-actions button'); if (!button) return;
    const backdrop = button.closest('.lesson-start-backdrop');
    if (button.matches('[data-later]') && backdrop?.dataset.resume === 'true') {
      const config = window.__lessonStartProgress; button.disabled = true;
      fetch(config.progressUrl, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || ''}, body: JSON.stringify({activity_key: config.activityKey, reset: true, total_items: config.totalItems})}).then(response => { if (!response.ok) throw new Error('Progress reset failed'); config.storageKeys.forEach(key => localStorage.removeItem(key)); location.reload(); }).catch(error => { console.error('Lesson progress reset failed', error); button.disabled = false; });
      return;
    }
    if (button.matches('[data-later]')) { window.location.href = '/dashboard/assessment/'; return; }
    if (backdrop?.dataset.resume === 'true') window.__lessonStartResumeIndex = Number(window.__lessonStartProgress.progress.current_index) || 0;
    closeModal(button);
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true}); else mount();
}());
