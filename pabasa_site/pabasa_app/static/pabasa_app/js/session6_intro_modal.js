(function () {
  'use strict';

  // Session 6 has several activity renderers that create their own Audio
  // objects. Keep one shared playback lease so an instruction, word, or
  // feedback clip always cancels the previous clip, including an in-flight
  // read-aloud request.
  const audioBus = window.__session6AudioBus || (() => {
    let generation = 0;
    let currentPlayer = null;
    let currentController = null;

    const cancel = () => {
      generation += 1;
      currentController?.abort();
      currentController = null;
      if (currentPlayer) {
        const player = currentPlayer;
        currentPlayer = null;
        player.onended = null;
        player.onerror = null;
        player.onpause = null;
        player.pause();
      }
    };

    const begin = () => {
      cancel();
      const leaseGeneration = generation;
      const controller = new AbortController();
      currentController = controller;
      return {
        signal: controller.signal,
        isCurrent: () => leaseGeneration === generation,
        play: async source => {
          if (leaseGeneration !== generation || !source) return false;
          const player = new Audio(source);
          currentPlayer = player;
          return new Promise(resolve => {
            let settled = false;
            const finish = () => {
              if (settled) return;
              settled = true;
              player.onended = null;
              player.onerror = null;
              player.onpause = null;
              if (currentPlayer === player) currentPlayer = null;
              if (currentController === controller) currentController = null;
              resolve(leaseGeneration === generation);
            };
            player.onended = finish;
            player.onerror = finish;
            player.onpause = finish;
            Promise.resolve(player.play()).catch(finish);
          });
        },
      };
    };

    const bus = { begin, cancel };
    window.__session6AudioBus = bus;
    addEventListener('session6-prescribed-cancel', cancel);
    addEventListener('pagehide', cancel, { once: true });
    return bus;
  })();

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
  // These activities own their first narration on the activity page. Playing
  // their prompt here makes the modal skip the activity intro and repeats the
  // same narration when the first word is rendered.
  const activityIntroAudioKeys = new Set([
    'session-6-lesson-16-gawain-4',
    'lesson-17-18-gawain-6',
    'lesson-17-18-gawain-7',
    'lesson-17-18-gawain-8',
    'lesson-17-18-gawain-9',
  ]);
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
  const modalOpeningAudio = activityIntroAudioKeys.has(key) ? [] : openingAudio;

  const playOpeningAudio = async () => {
    if (!modalOpeningAudio.length) return;
    window.__session6IntroModalAudioStarted = true;
    if (key === 'lesson-17-18-gawain-7' || key === 'lesson-17-18-gawain-8') {
      window.__session6IntroModalSkipFirstPromptIntro = true;
    }
    const lease = audioBus.begin();
    for (const source of modalOpeningAudio) {
      if (!lease.isCurrent()) break;
      await lease.play(source);
    }
    window.__session6IntroModalAudioStarted = false;
  };
  const playGawain9IntroAudio = async () => {
    if (key !== 'lesson-17-18-gawain-9') return;
    const phase = String(state.phase || 'intro').toLowerCase();
    let source = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_9/intro_basahin_isulat_ngalan_larawan_tts.mp3';
    if (hasSavedProgress && !['intro', 'initial'].includes(phase)) {
      if (phase !== 'oral_reading') return;
      const index = Number(state.current_item_index) || 0;
      const item = Array.isArray(data.items) ? data.items[index] : null;
      if (!item) return;
      const prompts = [
        'unang_larawan_pana_tts.mp3', 'ikalawang_larawan_pisara_tts.mp3',
        'ikatlong_larawan_palaka_tts.mp3', 'ika_apat_na_larawan_pito_tts.mp3',
        'ikalimang_larawan_regalo_tts.mp3',
      ];
      source = `/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_9/${prompts[index] || ''}`;
    }
    if (!source.endsWith('.mp3')) return;
    const lease = audioBus.begin();
    await lease.play(source);
  };
  const playGawain4ContinuationAudio = async () => {
    if (!hasSavedProgress || key !== 'session-6-lesson-16-gawain-4' || state.phase !== 'oral_reading') return;
    const index = Array.isArray(progress.answers)
      ? progress.answers.length
      : Number(state.current_item_index ?? state.current_index ?? 0);
    const prompts = [
      '02_item_01_gamot_read_prompt.mp3', '04_item_02_bunga_read_prompt.mp3',
      '06_item_03_panga_read_prompt.mp3', '08_item_04_goma_read_prompt.mp3',
      '10_item_05_sanga_read_prompt.mp3',
    ];
    const source = prompts[index];
    if (!source) return;
    const lease = audioBus.begin();
    await lease.play(`/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_4/${source}`);
  };
  const playGawain6ContinuationAudio = async () => {
    if (!hasSavedProgress || key !== 'lesson-17-18-gawain-6'
      || !['oral', 'oral_reading'].includes(String(state.phase || '').toLowerCase())
      || state.oral_mode === 'aloud') return;
    const index = Array.isArray(progress.answers)
      ? progress.answers.length
      : Number(state.current_index ?? progress.current_index ?? 0);
    const words = ['pusa', 'pako', 'paruparo', 'rosas', 'kariton'];
    const word = words[index];
    if (!word) return;
    const lease = audioBus.begin();
    await lease.play(`/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_6/babasahin_${word}_tts.mp3`);
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
    // Gawain 7's activity start handler already announces its instruction;
    // skip only the duplicate intro clip in the first prompt queue.
    window.__session6IntroModalSkipFirstPromptIntro = !hasSavedProgress
      && key === 'lesson-17-18-gawain-7';
    window.__session6IntroReady = true;
    window.__session6IntroModalOpen = false;
    backdrop.remove();
    document.body.classList.remove('lesson-start-open');
    window.dispatchEvent(new Event('lesson-start-ready'));
    window.dispatchEvent(new Event('session6-prescribed-resume'));
  };

  startButton?.addEventListener('click', async () => {
    if (startButton.disabled) return;
    startButton.disabled = true;
    laterButton.disabled = true;
    // Keep the activity modal open until every opening clip has finished. This
    // prevents the activity renderer from starting its first prompt alongside
    // the modal's intro MP3.
    await playOpeningAudio();
    close();
    if (key === 'lesson-17-18-gawain-9') {
      const activityStart = document.querySelector('#app #start');
      if (activityStart) activityStart.disabled = true;
      void playGawain9IntroAudio().finally(() => {
        if (activityStart?.isConnected) activityStart.disabled = false;
      });
    }
    if (key === 'session-6-lesson-16-gawain-4') {
      void playGawain4ContinuationAudio();
    }
    if (key === 'lesson-17-18-gawain-6') {
      void playGawain6ContinuationAudio();
    }
    // Leave the activity-owned intro screen visible. Its own start handler
    // must control the transition into the first word prompt.
    if (!hasSavedProgress && !activityIntroAudioKeys.has(key)) {
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
