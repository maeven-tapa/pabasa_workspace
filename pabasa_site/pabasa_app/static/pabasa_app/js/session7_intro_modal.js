(function () {
  'use strict';

  const activityKeys = new Set([
    'session-7-lesson-19-gawain-1',
    'session-7-lesson-19-gawain-2',
    'session-7-lesson-19-gawain-3',
    'session-7-lesson-19-gawain-4',
    'session-7-lesson-20-21-gawain-1',
    'session-7-lesson-20-21-gawain-2',
    'session-7-lesson-20-21-gawain-3',
    'session-7-lesson-20-21-gawain-4',
  ]);

  const dataElement = document.getElementById('prescribed-activity-data');
  if (!dataElement) return;

  let data;
  try {
    data = JSON.parse(dataElement.textContent || '{}');
  } catch (_) {
    return;
  }

  const key = String(data.activity_key || '');
  if (!activityKeys.has(key)) return;

  const progress = data.progress && typeof data.progress === 'object' ? data.progress : {};
  const state = progress.state && typeof progress.state === 'object' ? progress.state : {};

  if (progress.activity_completed === true) return;

  const freshStateValues = new Set([
    '', 'intro', 'initial', 'oral', 'oral_reading', 'reading', 'read',
    'matching', 'written', 'written_answer', 'ready', 'sound', 'trace',
  ]);
  const hasMeaningfulValue = (value, valueKey = '') => {
    if (Array.isArray(value)) return value.some(item => hasMeaningfulValue(item));
    if (value && typeof value === 'object') {
      return Object.entries(value).some(([childKey, childValue]) => hasMeaningfulValue(childValue, childKey));
    }
    if (typeof value === 'number') {
      // This is the displayed workbook row, not scored learner progress, for
      // Lesson 20 at 21 Gawain 2's worked-example-first state.
      if (key === 'session-7-lesson-20-21-gawain-2' && valueKey === 'current_item_index') return false;
      return value > 0;
    }
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') {
      if (valueKey === 'phase' || valueKey === 'oral_mode') return !freshStateValues.has(value.toLowerCase());
      return value.trim() !== '';
    }
    return false;
  };

  // Gawain 2 displays a worked example at index 0, so its normalized fresh
  // state intentionally starts at current_item_index 1. That display index is
  // not learner progress and must not open the continuation modal.
  const displayedItemProgress = key === 'session-7-lesson-20-21-gawain-2'
    ? 0
    : Number(progress.current_item_index);
  const hasSavedProgress = Number(progress.current_index) > 0
    || displayedItemProgress > 0
    || Number(progress.current_scored_index) > 0
    || Number(progress.completed_items) > 0
    || Number(progress.correct_items) > 0
    || hasMeaningfulValue(state);

  window.__session7IntroReady = false;
  window.__session7IntroModalOpen = true;
  if (key === 'session-7-lesson-19-gawain-2') document.body.classList.add('session7-g2-start-open');
  window.dispatchEvent(new Event('session7-prescribed-cancel'));

  const stylesheet = document.createElement('link');
  stylesheet.rel = 'stylesheet';
  stylesheet.href = '/static/pabasa_app/css/lesson_start_modal.css?v=s7-gawain2-flow';
  document.head.appendChild(stylesheet);

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const safeKey = key.replace(/[^a-z0-9_-]/gi, '-');
  const lesson = String(data.lesson_number ?? '').toUpperCase();
  const gawain = String(data.gawain_number ?? '').toUpperCase();
  const label = `SESSION 7 \u00b7 LESSON ${lesson} \u00b7 GAWAIN ${gawain}`;
  const title = data.title || data.display_title || 'Gawain';
  const lesson19Gawain1 = key === 'session-7-lesson-19-gawain-1';
  const lesson19Gawain2 = key === 'session-7-lesson-19-gawain-2';
  const lesson19Gawain3 = key === 'session-7-lesson-19-gawain-3';
  const lesson19Gawain4 = key === 'session-7-lesson-19-gawain-4';
  const introAudio = lesson19Gawain2
      ? new Audio('/static/pabasa_app/prescribed/audio/SESSION_7/LESSON_19/GAWAIN_2/basahin_ngalan_isulat_nawawalang_pantig_tts.mp3')
      : null;
  if (introAudio) window.__session7G2IntroAudio = introAudio;
  const stopIntroAudio = () => {
    if (!introAudio) return;
    introAudio.pause();
    introAudio.currentTime = 0;
  };
  const playIntroAudio = () => {
    if (!introAudio) return;
    stopIntroAudio();
    introAudio.play().catch(() => {});
  };

  const backdrop = document.createElement('div');
  backdrop.className = `lesson-start-backdrop lesson-13-start-backdrop${lesson19Gawain1 ? ' session7-g1-start' : ''}${lesson19Gawain2 ? ' session7-g2-start' : ''}`;
  if (lesson19Gawain3) backdrop.classList.add('session7-g3-start-layer');
  backdrop.id = `session7-start-${safeKey}`;
  backdrop.dataset.resume = hasSavedProgress ? 'true' : 'false';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-labelledby', `${backdrop.id}-title`);
  backdrop.innerHTML = lesson19Gawain3
    ? `<div class="lesson-start-modal lesson-13-start-modal session7-g3-start-card">
        <p class="lesson-start-label lesson-13-start-label">${escapeHtml(label)}</p>
        <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : 'Handa ka nang magbasa at pumili ng tamang salita?'}</h2>
        <div class="lesson-start-actions lesson-13-start-actions">
          <button type="button" data-session7-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
          <button type="button" data-session7-later>${hasSavedProgress ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button>
        </div>
      </div>`
    : lesson19Gawain4
    ? `<div class="lesson-start-modal lesson-13-start-modal session7-g4-start-card">
        <p class="lesson-start-label lesson-13-start-label">${escapeHtml(label)}</p>
        <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : 'Ayusin ang mga Letra'}</h2>
        <p class="session7-g4-start-copy">${hasSavedProgress ? 'Ipagpatuloy ang iyong gawain kung saan ka huminto.' : 'Makinig, basahin, at ayusin ang mga letra.'}</p>
        <div class="lesson-start-actions lesson-13-start-actions">
          <button type="button" data-session7-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
          <button type="button" data-session7-later>${hasSavedProgress ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button>
        </div>
      </div>`
    : lesson19Gawain2
    ? `<div class="lesson-start-modal lesson-13-start-modal session7-g2-start-card">
        <p class="lesson-start-label lesson-13-start-label">${escapeHtml(label)}</p>
        <div class="session7-g2-start-art" aria-hidden="true">📚</div>
        <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'Handa ka na bang magpatuloy?' : 'Handa ka na bang magbasa at kumumpleto ng salita?'}</h2>
        <div class="lesson-start-actions lesson-13-start-actions">
          <button type="button" data-session7-start>${hasSavedProgress ? 'Ipagpatuloy' : 'Magsimula'}</button>
          ${hasSavedProgress ? '<button type="button" data-session7-later>Simulan ulit</button>' : ''}
        </div>
      </div>`
    : lesson19Gawain1
    ? `<div class="lesson-start-modal lesson-13-start-modal session7-g1-start-card">
        <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'Handa ka na bang magpatuloy?' : 'Handa ka na?'}</h2>
        <div class="lesson-start-actions lesson-13-start-actions">
          <button type="button" data-session7-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
          ${hasSavedProgress ? '<button type="button" data-session7-later>SIMULAN ULIT</button>' : ''}
        </div>
      </div>`
    : `<div class="lesson-start-modal lesson-13-start-modal">
        <p class="lesson-start-label lesson-13-start-label">${hasSavedProgress ? 'MAY NA-SAVE KANG PROGRESO!' : escapeHtml(label)}</p>
        <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : escapeHtml(title)}</h2>
        <div class="lesson-start-actions lesson-13-start-actions">
          <button type="button" data-session7-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
          <button type="button" data-session7-later>${hasSavedProgress ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button>
        </div>
      </div>`;
  document.body.prepend(backdrop);
  document.body.classList.add('lesson-start-open');
  const close = (keepIntroAudio = false) => {
    if (!keepIntroAudio) stopIntroAudio();
    window.__session7IntroReady = true;
    window.__session7IntroModalOpen = false;
    backdrop.remove();
    document.body.classList.remove('lesson-start-open');
    document.body.classList.remove('session7-g2-start-open');
    window.dispatchEvent(new CustomEvent('lesson-start-ready', { detail: { activityKey: key, hasSavedProgress, resumed: hasSavedProgress && backdrop.dataset.reset !== 'true' } }));
    window.dispatchEvent(new Event('session7-prescribed-resume'));
  };

  backdrop.querySelector('[data-session7-start]')?.addEventListener('click', () => {
    const button = backdrop.querySelector('[data-session7-start]');
    if (button.disabled) return;
    button.disabled = true;
    if (lesson19Gawain2 && state.phase === 'intro') playIntroAudio();
    close(lesson19Gawain2 && state.phase === 'intro');
  });

  backdrop.querySelector('[data-session7-later]')?.addEventListener('click', async () => {
    const button = backdrop.querySelector('[data-session7-later]');
    if (!hasSavedProgress) {
      window.location.href = '/dashboard/assessment/';
      return;
    }
    if (lesson19Gawain4 && !window.confirm('Sigurado ka bang gusto mong magsimula ulit? Mare-reset ang na-save mong progreso.')) return;
    button.disabled = true;
    try {
      const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
      const response = await fetch(data.progress_url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({
          activity_key: key,
          reset: true,
          total_items: Number(progress.total_items || data.total_items || 0),
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success) throw new Error(result.error || 'Hindi na-reset ang gawain.');
      window.location.reload();
    } catch (error) {
      console.error('Session 7 progress reset failed', error);
      button.disabled = false;
    }
  });

  backdrop.querySelector('[data-session7-start]')?.focus();
}());
