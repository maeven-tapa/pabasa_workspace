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
  window.dispatchEvent(new Event('session7-prescribed-cancel'));

  const stylesheet = document.createElement('link');
  stylesheet.rel = 'stylesheet';
  stylesheet.href = '/static/pabasa_app/css/lesson_start_modal.css';
  document.head.appendChild(stylesheet);

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const safeKey = key.replace(/[^a-z0-9_-]/gi, '-');
  const lesson = String(data.lesson_number ?? '').toUpperCase();
  const gawain = String(data.gawain_number ?? '').toUpperCase();
  const label = `SESSION 7 \u00b7 LESSON ${lesson} \u00b7 GAWAIN ${gawain}`;
  const title = data.title || data.display_title || 'Gawain';

  const backdrop = document.createElement('div');
  backdrop.className = 'lesson-start-backdrop lesson-13-start-backdrop';
  backdrop.id = `session7-start-${safeKey}`;
  backdrop.dataset.resume = hasSavedProgress ? 'true' : 'false';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-labelledby', `${backdrop.id}-title`);
  backdrop.innerHTML = `<div class="lesson-start-modal lesson-13-start-modal">
    <p class="lesson-start-label lesson-13-start-label">${hasSavedProgress ? 'MAY NA-SAVE KANG PROGRESO!' : escapeHtml(label)}</p>
    <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : escapeHtml(title)}</h2>
    <div class="lesson-start-actions lesson-13-start-actions">
      <button type="button" data-session7-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
      <button type="button" data-session7-later>${hasSavedProgress ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button>
    </div>
  </div>`;
  document.body.prepend(backdrop);
  document.body.classList.add('lesson-start-open');

  const close = () => {
    window.__session7IntroReady = true;
    window.__session7IntroModalOpen = false;
    backdrop.remove();
    document.body.classList.remove('lesson-start-open');
    window.dispatchEvent(new Event('lesson-start-ready'));
    window.dispatchEvent(new Event('session7-prescribed-resume'));
  };

  backdrop.querySelector('[data-session7-start]')?.addEventListener('click', () => {
    const button = backdrop.querySelector('[data-session7-start]');
    if (button.disabled) return;
    button.disabled = true;
    close();
  });

  backdrop.querySelector('[data-session7-later]')?.addEventListener('click', async () => {
    const button = backdrop.querySelector('[data-session7-later]');
    if (!hasSavedProgress) {
      window.location.href = '/dashboard/assessment/';
      return;
    }
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
