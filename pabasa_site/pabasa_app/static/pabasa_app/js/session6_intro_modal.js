(function () {
  'use strict';

  const activityKeys = new Set([
    'lesson-16-gawain-1',
    'lesson-16-gawain-2',
    'lesson-16-gawain-3',
    'session-6-lesson-16-gawain-4',
    'lesson-17-18-gawain-5',
    'lesson-17-18-gawain-6',
    'lesson-17-18-gawain-7',
    'lesson-17-18-gawain-8',
    'lesson-17-18-gawain-9',
  ]);

  const dataElement = document.getElementById('prescribed-activity-data');
  if (!dataElement) return;

  let data;
  try {
    data = JSON.parse(dataElement.textContent || '{}');
  } catch (_) {
    return;
  }
  if (!activityKeys.has(String(data.activity_key || ''))) return;

  window.__session6IntroReady = false;
  window.__session6IntroModalOpen = true;

  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const progress = data.progress && typeof data.progress === 'object' ? data.progress : {};
  const state = progress.state && typeof progress.state === 'object' ? progress.state : {};

  const hasMeaningfulValue = (value, key = '') => {
    if (Array.isArray(value)) return value.some(item => hasMeaningfulValue(item));
    if (value && typeof value === 'object') {
      return Object.entries(value).some(([childKey, childValue]) => hasMeaningfulValue(childValue, childKey));
    }
    if (typeof value === 'number') return value > 0;
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') {
      if (key === 'phase' || key === 'oral_mode') return !['', 'intro', 'initial', 'oral', 'oral_reading', 'reading', 'read', 'matching', 'written', 'written_answer', 'ready', 'sound', 'trace'].includes(value.toLowerCase());
      return value.trim() !== '';
    }
    return false;
  };

  const hasSavedProgress = !progress.activity_completed && (
    Number(progress.current_index) > 0
    || Number(progress.completed_items) > 0
    || Number(progress.correct_items) > 0
    || hasMeaningfulValue(state)
  );

  // Completed activities reopen directly, matching the reference activity.
  if (progress.activity_completed === true) {
    window.__session6IntroReady = true;
    window.__session6IntroModalOpen = false;
    return;
  }

  // Stop any renderer-level welcome narration that fired while the modal was
  // being mounted. It will be restarted by the activity after the learner
  // chooses SIMULAN or IPAGPATULOY.
  window.dispatchEvent(new Event('session6-prescribed-cancel'));

  const key = String(data.activity_key);
  const safeKey = key.replace(/[^a-z0-9_-]/gi, '-');
  const openingAudio = {
    'lesson-16-gawain-1': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_1/04_item_01_gumamela_missing_syllable_prompt.mp3'],
    'lesson-16-gawain-2': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_2/04_item_01_gumamela_missing_syllable_prompt.mp3'],
    'lesson-16-gawain-3': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_3/01_item_01_sanga_match_prompt.mp3'],
    'session-6-lesson-16-gawain-4': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_4/01_activity_intro.mp3'],
    'lesson-17-18-gawain-5': [
      '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_5/01_activity_intro.mp3',
      '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_5/02_item_01_robot_read_prompt.mp3',
    ],
    'lesson-17-18-gawain-6': [
      '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_6/panuto_basahin_tts.mp3',
      '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_6/babasahin_pusa_tts.mp3',
    ],
    'lesson-17-18-gawain-7': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_7/basahin_muna_ang_mga_ngalan_tts.mp3'],
    'lesson-17-18-gawain-8': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_8/basahin_bilugan_naiiba_sa_pangkat_tts.mp3'],
    'lesson-17-18-gawain-9': ['/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_9/unang_larawan_pana_tts.mp3'],
  }[key] || [];

  const playOpeningAudio = () => {
    if (!openingAudio.length) return;
    window.__session6IntroModalAudioStarted = true;
    if (key === 'lesson-17-18-gawain-7' || key === 'lesson-17-18-gawain-8') {
      window.__session6IntroModalSkipFirstPromptIntro = true;
    }
    let index = 0;
    const playNext = () => {
      const source = openingAudio[index++];
      if (!source) {
        window.__session6IntroModalAudioStarted = false;
        return;
      }
      const player = new Audio(source);
      player.preload = 'auto';
      player.onended = playNext;
      player.onerror = playNext;
      const attempt = player.play();
      attempt?.catch(() => playNext());
    };
    playNext();
  };
  const lesson = String(data.lesson_number ?? '').toUpperCase();
  const gawain = String(data.gawain_number ?? '').toUpperCase();
  const label = `SESSION 6 \u00b7 LESSON ${lesson} \u00b7 GAWAIN ${gawain}`;
  const title = data.title || data.display_title || 'Gawain';
  const backdrop = document.createElement('div');
  backdrop.className = 'lesson-start-backdrop lesson-13-start-backdrop';
  backdrop.id = `session6-start-${safeKey}`;
  backdrop.dataset.resume = hasSavedProgress ? 'true' : 'false';
  backdrop.setAttribute('role', 'dialog');
  backdrop.setAttribute('aria-modal', 'true');
  backdrop.setAttribute('aria-labelledby', `${backdrop.id}-title`);
  backdrop.innerHTML = `<div class="lesson-start-modal lesson-13-start-modal">
    <p class="lesson-start-label lesson-13-start-label">${hasSavedProgress ? 'MAY NA-SAVE KANG PROGRESO!' : escapeHtml(label)}</p>
    <h2 class="lesson-start-title lesson-13-start-title" id="${backdrop.id}-title">${hasSavedProgress ? 'May nasimulan ka nang gawain. Gusto mo bang ipagpatuloy ang iyong nasimulan?' : escapeHtml(title)}</h2>
    <div class="lesson-start-actions lesson-13-start-actions">
      <button type="button" data-session6-start>${hasSavedProgress ? 'IPAGPATULOY' : 'SIMULAN'}</button>
      <button type="button" data-session6-later>${hasSavedProgress ? 'SIMULAN ULIT' : 'MAMAYA NA LANG'}</button>
    </div>
  </div>`;
  document.body.prepend(backdrop);
  document.body.classList.add('lesson-start-open');

  const startButton = backdrop.querySelector('[data-session6-start]');
  const laterButton = backdrop.querySelector('[data-session6-later]');

  const close = () => {
    window.__session6IntroReady = true;
    window.__session6IntroModalOpen = false;
    backdrop.remove();
    document.body.classList.remove('lesson-start-open');
    window.dispatchEvent(new Event('lesson-start-ready'));
    window.dispatchEvent(new Event('session6-prescribed-resume'));
  };

  startButton?.addEventListener('click', () => {
    if (startButton.disabled) return;
    startButton.disabled = true;
    // Start the opening clip in this trusted click handler before the activity
    // performs any asynchronous save/render work.
    playOpeningAudio();
    close();
    // Several Session 6 renderers have their own first-screen start button.
    // Activate it only for a brand-new activity; saved activities are already
    // rendered at their restored phase and must continue where they stopped.
    if (!hasSavedProgress) {
      const activityStart = document.querySelector('#app #start');
      if (activityStart && !activityStart.disabled) activityStart.click();
    }
  });

  laterButton?.addEventListener('click', async () => {
    if (!hasSavedProgress) {
      window.location.href = '/dashboard/assessment/';
      return;
    }
    laterButton.disabled = true;
    try {
      const response = await fetch(data.progress_url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf(),
        },
        body: JSON.stringify({activity_key: key, reset: true, total_items: Number(progress.total_items || data.total_items || 0)}),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success) throw new Error(result.error || 'Hindi na-reset ang gawain.');
      window.location.reload();
    } catch (error) {
      console.error('Session 6 progress reset failed', error);
      laterButton.disabled = false;
    }
  });

  startButton?.focus();
}());
