(function () {
  'use strict';
  if (typeof window.__lessonStartReady !== 'boolean') window.__lessonStartReady = false;
  const originalSpeak = window.speechSynthesis?.speak;
  if (originalSpeak) {
    window.speechSynthesis.speak = function (utterance) {
      if (window.__lessonStartReady) originalSpeak.call(window.speechSynthesis, utterance);
    };
  }
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    const body = init?.body;
    const isReadAloud = body && String(body).includes('target_text=');
    if (!window.__lessonStartReady && isReadAloud) return Promise.reject(new Error('Lesson has not started'));
    return originalFetch.apply(this, arguments);
  };
  function closeModal(button) {
    const backdrop = button.closest('.lesson-start-backdrop');
    if (!backdrop) return;
    backdrop.remove();
    document.body.classList.remove('lesson-start-open');
    window.__lessonStartReady = true;
    window.dispatchEvent(new Event('lesson-start-ready'));
  }
  function mount() {
    if (document.querySelector('.lesson-start-backdrop')) return;
    const path = location.pathname.toLowerCase();
    let target = null;
    if (document.body.classList.contains('gawain-2') || path.includes('lesson-3-gawain-2')) target = ['lesson-3-g2-start', 'SESSION 1 · LESSON 3 · GAWAIN 2'];
    else if (document.body.classList.contains('lesson-3-responsive') || path.includes('lesson-3-gawain-1')) target = ['lesson-3-g1-start', 'SESSION 1 · LESSON 3 · GAWAIN 1'];
    else if (document.querySelector('.salitang-speech-debug') || path.includes('lesson2-gawain1')) target = ['lesson-2-g1-start', 'SESSION 1 · LESSON 2 · GAWAIN 1'];
    else if (document.body.classList.contains('lesson-4-responsive') || path.includes('lesson-4/gawain-1')) target = ['lesson-4-g1-start', 'SESSION 2 · LESSON 4 · GAWAIN 1'];
    else if (path.includes('session-2-lesson-4-gawain-2')) target = ['session-2-lesson-4-g2-start', 'SESSION 2 · LESSON 4 · GAWAIN 2'];
    else if (path.includes('lesson-5/gawain-1')) target = ['lesson-5-g1-start', 'SESSION 2 · LESSON 5 · GAWAIN 1'];
    else if (path.includes('lesson-6/gawain-1')) target = ['lesson-6-g1-start', 'SESSION 2 · LESSON 6 · GAWAIN 1'];
    if (!target) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/pabasa_app/css/lesson_start_modal.css';
    document.head.append(link);
    const [id, label] = target;
    const backdrop = document.createElement('div');
    backdrop.className = 'lesson-start-backdrop lesson-13-start-backdrop';
    backdrop.id = id;
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.innerHTML = `<div class="lesson-start-modal lesson-13-start-modal"><p class="lesson-start-label lesson-13-start-label">${label}</p><h2 class="lesson-start-title lesson-13-start-title">Salitang Magkatugma</h2><div class="lesson-start-actions lesson-13-start-actions"><button type="button" data-start>SIMULAN</button><button type="button" data-later>MAMAYA NA LANG</button></div></div>`;
    document.body.prepend(backdrop);
    document.body.classList.add('lesson-start-open');
    backdrop.querySelector('[data-start]').focus();
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('.lesson-start-actions button');
    if (!button) return;
    if (button.matches('[data-later]')) {
      window.location.href = '/dashboard/assessment/';
      return;
    }
    closeModal(button);
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
}());
