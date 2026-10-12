(() => {
  'use strict';
  const WELCOME_AUDIO_URL = '/static/pabasa_app/prescribed/audio/SESSION%201/LESSON%201/GAWAIN%201/hello_ka-basa.mp3';
  const REMINDER_AUDIO_URL = '/static/pabasa_app/prescribed/audio/SESSION%201/LESSON%201/GAWAIN%201/alpabeto_recording_reminder.mp3';
  const WELCOME_MESSAGE = 'Sabay nating panuorin at pakinggan ang Awiting Alpabeto ng Filipino. Handa ka na ba?';
  const REMINDER_MESSAGE = 'Magsisimula ang pag-record ng iyong boses kasabay ng pagtugtog ng Awiting Alpabeto ng Filipino. Kaya ihanda ang iyong sarili at sabayan ang awitin!';
  const state = {
    phase: 'ready', generation: 0, stream: null, recorder: null, parts: [],
    timer: null, cancelCountdown: null, recordingBlob: null, durationMs: 0,
    startedAt: 0, naturallyEnded: false, submissionPromise: null,
    welcomeModal: null, startModal: null, welcomeAudio: null, welcomeAudioUrl: null,
    welcomeGeneration: 0, cancelWelcomeNarration: null, welcomeNarrating: false,
    welcomeNarrationReady: false, welcomeSubmissionOnly: false,
    welcomeObserver: null, welcomeAudioTimer: null,
    statusPollTimer: null, awaitingTeacherCheck: false, disposed: false,
  };
  const data = () => JSON.parse(document.getElementById('lesson-one-data')?.textContent || '{}');
  const video = () => document.getElementById('alphabet-video');
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  const active = generation => generation === state.generation && !state.disposed;
  function syncRecordingIndicator() {
    const indicator = document.getElementById('lesson-one-recording-indicator');
    const recording = state.phase === 'playing' && !state.disposed
      && ['recording', 'paused'].includes(state.recorder?.state);
    const paused = recording && state.recorder.state === 'paused';
    indicator.hidden = !recording;
    indicator.classList.toggle('is-paused', paused);
    indicator.querySelector('[data-recording-label]').textContent = paused
      ? 'Naka-pause ang recording' : 'Nagre-record…';
  }
  function feedback(text = '') {
    const output = document.getElementById('lesson-one-feedback');
    output.textContent = text;
    output.hidden = !text;
    output.classList.toggle('is-countdown', /^[1-5]$/.test(text));
  }
  function stopWelcomeClip() {
    clearTimeout(state.welcomeAudioTimer);
    state.welcomeAudioTimer = null;
    if (state.welcomeAudio) {
      state.welcomeAudio.onended = state.welcomeAudio.onerror = null;
      state.welcomeAudio.pause();
    }
    state.welcomeAudio = null;
    if (state.welcomeAudioUrl) URL.revokeObjectURL(state.welcomeAudioUrl);
    state.welcomeAudioUrl = null;
  }
  function clearWelcomeAudio() {
    state.welcomeGeneration += 1;
    state.welcomeNarrationReady = state.welcomeNarrating = false;
    state.cancelWelcomeNarration?.();
    state.cancelWelcomeNarration = null;
    stopWelcomeClip();
    setWelcomeButtons(false);
  }

  function setWelcomeButtons(enabled) {
    state.welcomeModal?.querySelectorAll('[data-welcome-choice]').forEach(button => {
      button.disabled = !enabled;
    });
  }

  async function narrateWelcome(submissionOnly = false) {
    const modal = state.welcomeModal;
    if (!modal?.isConnected || state.disposed || state.welcomeNarrating) return;
    clearWelcomeAudio();
    feedback();
    state.welcomeNarrating = true;
    state.welcomeSubmissionOnly = submissionOnly;
    const generation = state.welcomeGeneration;
    const current = () => generation === state.welcomeGeneration && !state.disposed
      && state.welcomeModal === modal && modal.isConnected;
    const message = modal.querySelector('[data-welcome-message]');
    const retry = modal.querySelector('[data-welcome-retry]');
    retry.hidden = true;
    retry.textContent = 'Ulitin ang pagsasalaysay';
    retry.onclick = () => narrateWelcome(submissionOnly);
    try {
      for (const [text, url] of [[WELCOME_MESSAGE, WELCOME_AUDIO_URL], [REMINDER_MESSAGE, REMINDER_AUDIO_URL]]) {
        if (!current()) return;
        message.textContent = text;
        const audio = new Audio(url);
        state.welcomeAudio = audio;
        const finished = await new Promise((resolve, reject) => {
          state.cancelWelcomeNarration = () => resolve(false);
          state.welcomeAudioTimer = setTimeout(() => reject(new Error('Narration timed out.')), 60000);
          audio.onended = () => resolve(true);
          audio.onerror = () => reject(new Error('Hindi mapatugtog ang pagsasalaysay. Pindutin ang “Ulitin ang pagsasalaysay”.'));
          audio.play().catch(reject);
        });
        if (!current()) return;
        state.cancelWelcomeNarration = null;
        stopWelcomeClip();
        if (!finished) return;
      }
      if (!current()) return;
      state.welcomeNarrationReady = true;
      if (submissionOnly) {
        // Preserve the existing upload-only retry: never start a second
        // microphone recording when the finalized audio is already saved.
        modal.querySelector('[data-welcome-choice="no"]').disabled = false;
        retry.textContent = 'Subukan muli';
        retry.hidden = false;
        retry.onclick = () => {
          if (!state.welcomeNarrationReady || state.welcomeModal !== modal || !modal.isConnected) return;
          clearWelcomeAudio();
          modal.remove(); state.welcomeModal = null; submitRecording();
        };
      } else setWelcomeButtons(true);
    } catch (_) {
      if (!current()) return;
      feedback('Hindi natapos ang pagsasalaysay. Pindutin ang “Ulitin ang pagsasalaysay”.');
      retry.hidden = false;
    } finally {
      if (current()) {
        state.welcomeNarrating = false;
        state.cancelWelcomeNarration = null;
        stopWelcomeClip();
      }
    }
  }

  function showWelcomeModal() {
    const modal = document.createElement('section');
    modal.className = 'lesson-one-welcome-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'lesson-one-welcome-title');
    modal.innerHTML = '<div class="lesson-one-welcome-card"><h2 id="lesson-one-welcome-title">Hello, Ka-BASA!</h2><p data-welcome-message aria-live="polite" aria-atomic="true">Sabay nating panuorin at pakinggan ang Awiting Alpabeto ng Filipino. Handa ka na ba?</p><div class="lesson-one-welcome-actions"><button type="button" data-welcome-choice="yes" disabled>Oo</button><button type="button" data-welcome-choice="no" disabled>Hindi</button></div><button type="button" class="lesson-one-welcome-retry" data-welcome-retry hidden>Ulitin ang pagsasalaysay</button></div>';
    document.body.appendChild(modal);
    state.welcomeModal = modal;
    state.startModal = modal;
    state.welcomeObserver = new MutationObserver(() => {
      if (state.welcomeModal === modal && !modal.isConnected) {
        clearWelcomeAudio();
        state.welcomeModal = null;
      }
    });
    state.welcomeObserver.observe(document.body, { childList: true });
    modal.querySelector('[data-welcome-choice="yes"]').onclick = () => {
      if (modal.querySelector('[data-welcome-choice="yes"]').disabled || !state.welcomeNarrationReady
          || state.welcomeModal !== modal || !modal.isConnected || state.disposed) return;
      clearWelcomeAudio();
      modal.remove();
      state.welcomeModal = null;
      startRecording();
    };
    modal.querySelector('[data-welcome-choice="no"]').onclick = () => {
      if (modal.querySelector('[data-welcome-choice="no"]').disabled
          || (!state.welcomeNarrationReady && !state.welcomeSubmissionOnly)
          || state.welcomeModal !== modal || !modal.isConnected || state.disposed) return;
      clearWelcomeAudio();
      window.location.assign(document.querySelector('.back')?.href || '/');
    };
    modal.querySelector('[data-welcome-retry]').onclick = () => narrateWelcome();
    narrateWelcome();
  }

  function stopTracks() {
    state.stream?.getTracks().forEach(track => track.stop());
    state.stream = null;
  }

  function cleanup() {
    state.generation += 1;
    clearTimeout(state.timer);
    state.cancelCountdown?.();
    state.cancelCountdown = null;
    state.phase = 'ready';
    video().pause();
    const recorder = state.recorder;
    state.recorder = null;
    syncRecordingIndicator();
    if (recorder) {
      recorder.onstop = recorder.ondataavailable = recorder.onerror = null;
      recorder.onstart = recorder.onresume = recorder.onpause = null;
      if (recorder.state !== 'inactive') {
        try { recorder.stop(); } catch (_) { /* Already stopped by the browser. */ }
      }
    }
    stopTracks();
    feedback();
  }

  // Reattach the same start modal and reuse its confirmation handler for retries.
  function showRetry(message, submissionOnly = false) {
    if (state.disposed) return;
    const modal = state.startModal;
    clearWelcomeAudio();
    state.welcomeModal = modal;
    document.body.appendChild(modal);
    narrateWelcome(submissionOnly);
    feedback(message);
  }

  function failAttempt(message) {
    cleanup();
    state.recordingBlob = null;
    state.parts = [];
    state.naturallyEnded = false;
    showRetry(message);
  }

  function countdown(generation) {
    state.phase = 'countdown';
    return new Promise(resolve => {
      state.cancelCountdown = () => resolve(false);
      let remaining = 5;
      const tick = () => {
        if (!active(generation)) return resolve(false);
        if (!remaining) {
          state.cancelCountdown = null;
          feedback();
          resolve(true);
          return;
        }
        feedback(String(remaining--));
        state.timer = setTimeout(tick, 1000);
      };
      tick();
    });
  }

  async function startRecording() {
    if (state.disposed || state.phase !== 'ready' || state.submissionPromise) return;
    cleanup();
    const generation = state.generation;
    state.phase = 'initializing';
    state.parts = [];
    state.recordingBlob = null;
    state.naturallyEnded = false;
    const player = video();
    feedback('Inihahanda ang mikropono…');
    try {
      if (player.error) player.load();
      player.currentTime = 0;
      player.muted = false;
      player.volume = 1;
      player.playbackRate = 1;
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('Hindi available ang mikropono sa browser na ito.');
      }
      // Confirming a new recording also restores the shared microphone toggle.
      const micToggle = document.getElementById('prescribed-s1l1g1-mic-toggle');
      if (micToggle?.getAttribute('aria-pressed') === 'true') micToggle.click();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true,
      } });
      // Permission may resolve after navigation, pause, or another cancelled attempt.
      if (!active(generation)) { stream.getTracks().forEach(track => track.stop()); return; }
      state.stream = stream;
      const tracks = stream.getAudioTracks();
      if (!tracks.length || tracks.some(track => track.readyState !== 'live' || !track.enabled)) {
        throw new Error('Hindi handa ang mikropono. I-unmute ito at subukan muli.');
      }
      const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
        .find(value => MediaRecorder.isTypeSupported(value));
      const recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
      state.recorder = recorder;
      recorder.onstart = recorder.onresume = recorder.onpause = () => {
        if (active(generation)) syncRecordingIndicator();
      };
      recorder.ondataavailable = event => {
        if (active(generation) && event.data.size) state.parts.push(event.data);
      };
      recorder.onerror = () => {
        if (active(generation)) failAttempt('Hindi natapos ang pag-record. Subukan muli.');
      };
      tracks.forEach(track => track.addEventListener('ended', () => {
        if (active(generation) && ['countdown', 'starting', 'playing'].includes(state.phase)) {
          failAttempt('Naputol ang mikropono. Subukan muli.');
        }
      }, { once: true }));
      recorder.onstop = () => {
        if (!active(generation)) return;
        syncRecordingIndicator();
        if (state.phase !== 'finalizing' || !state.naturallyEnded) {
          failAttempt('Naputol ang pag-record. Subukan muli.');
          return;
        }
        clearTimeout(state.timer);
        state.durationMs = performance.now() - state.startedAt;
        state.recorder = null;
        stopTracks();
        state.recordingBlob = new Blob(state.parts, { type: recorder.mimeType || type || 'audio/webm' });
        if (!state.recordingBlob.size || state.durationMs <= 0) {
          failAttempt('Walang na-record na audio. Subukan muli.');
          return;
        }
        submitRecording();
      };
      if (!await countdown(generation) || !active(generation)) return;
      state.phase = 'starting';
      // The first playing event starts capture in the same event-loop turn.
      await player.play();
      if (!active(generation)) return;
      if (state.phase !== 'playing') throw new Error('Hindi nagsimula ang video.');
    } catch (error) {
      if (!active(generation)) return;
      const message = error.name === 'NotAllowedError'
        ? 'Pahintulutan ang mikropono at pag-play ng video, pagkatapos ay subukan muli.'
        : error.message || 'Hindi masimulan ang video o recording. Subukan muli.';
      failAttempt(message);
    }
  }

  async function submitRecording() {
    if (!state.naturallyEnded || !state.recordingBlob?.size || state.disposed) return;
    if (state.submissionPromise) return state.submissionPromise;
    state.phase = 'submitting';
    feedback('Isinusumite ang iyong recording…');
    const form = new FormData();
    const extension = state.recordingBlob.type.includes('mp4') ? 'm4a'
      : state.recordingBlob.type.includes('ogg') ? 'ogg' : 'webm';
    form.append('audio', state.recordingBlob, `lesson-1-gawain-1.${extension}`);
    form.append('duration_seconds', String(Math.max(1, Math.round(state.durationMs / 1000))));
    form.append('video_completed', 'true');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    state.submissionPromise = (async () => {
      try {
        const response = await fetch(data().submission_url, { method: 'POST', credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf() }, body: form, signal: controller.signal });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.success) throw new Error(result.error || 'Hindi naisumite ang recording.');
        if (state.disposed) return;
        state.phase = 'submitted';
        state.recordingBlob = null;
        state.parts = [];
        feedback();
        showPersistedActivityState({ submission_status: result.status || 'submitted' });
        startCompletionStatusPolling();
      } catch (_) {
        if (!state.disposed) {
          state.phase = 'ready';
          showRetry('Hindi naisumite ang recording. Subukan muli.', true);
        }
      } finally {
        clearTimeout(timeout);
        state.submissionPromise = null;
      }
    })();
    return state.submissionPromise;
  }

  function showPersistedActivityState(payload = data()) {
    const checked = payload.submission_status === 'checked' || payload.progress?.activity_completed;
    const submitted = payload.submission_status === 'submitted' || payload.submitted;
    if (!checked && !submitted) return false;
    state.awaitingTeacherCheck = !checked;
    state.phase = checked ? 'checked' : 'submitted';
    const completion = document.getElementById('completion');
    completion.querySelector('h2').textContent = checked ? 'Tapos na ang gawain! 🎉' : 'Naghihintay sa guro';
    completion.querySelector('.completion-card > p:not(.save-error)').textContent = checked
      ? 'Mahusay! Nakumpleto mo na ang aktibidad.' : 'Naipasa na ang recording mo. Maghintay muna.';
    completion.querySelector('#done').textContent = 'BALIK SA AKING ARALIN';
    document.querySelector('.page').classList.add('is-complete');
    completion.classList.add('show');
    return true;
  }

  function startCompletionStatusPolling() {
    if (state.statusPollTimer || !state.awaitingTeacherCheck) return;
    let polling = false;
    state.statusPollTimer = setInterval(async () => {
      if (polling || !state.awaitingTeacherCheck || state.disposed) return;
      polling = true;
      try {
        const response = await fetch(window.location.href, { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok || state.disposed) return;
        const copy = new DOMParser().parseFromString(await response.text(), 'text/html');
        const payload = JSON.parse(copy.getElementById('lesson-one-data')?.textContent || '{}');
        if (state.disposed) return;
        if (payload.submission_status === 'checked' || payload.progress?.activity_completed) {
          clearInterval(state.statusPollTimer); state.statusPollTimer = null;
          showPersistedActivityState(payload);
        } else if (payload.submission_status === 'retry' || payload.progress?.state?.retry_requested) {
          clearInterval(state.statusPollTimer); state.statusPollTimer = null;
          state.awaitingTeacherCheck = false;
          cleanup();
          document.getElementById('completion').classList.remove('show');
          document.querySelector('.page').classList.remove('is-complete');
          // A pending submission loaded on page open has not mounted the start modal yet.
          if (!state.startModal) showWelcomeModal();
          else showRetry('Hiniling ng guro na ulitin ang gawain.');
        }
      } catch (_) { /* A temporary status failure retries on the next poll. */ }
      finally { polling = false; }
    }, 4000);
  }

  function dispose() {
    state.disposed = true;
    clearWelcomeAudio();
    state.welcomeObserver?.disconnect();
    clearInterval(state.statusPollTimer);
    cleanup();
  }

  function init() {
    const player = video();
    player.addEventListener('playing', () => {
      if (state.phase === 'playing' && state.recorder?.state === 'paused') {
        try { state.recorder.resume(); }
        catch (_) { failAttempt('Hindi maipagpatuloy ang pag-record. Subukan muli.'); }
        return;
      }
      if (state.phase !== 'starting') return;
      try {
        state.recorder.start(1000);
        state.startedAt = performance.now();
        state.phase = 'playing';
      } catch (_) { failAttempt('Hindi masimulan ang pag-record. Subukan muli.'); }
    });
    player.addEventListener('ended', () => {
      if (state.phase !== 'playing' || !player.ended || !['recording', 'paused'].includes(state.recorder?.state)) return;
      state.naturallyEnded = true;
      state.phase = 'finalizing';
      feedback('Inaayos ang iyong recording…');
      state.timer = setTimeout(() => failAttempt('Hindi natapos ang pag-record. Subukan muli.'), 10000);
      try { state.recorder.stop(); }
      catch (_) { failAttempt('Hindi natapos ang pag-record. Subukan muli.'); }
    });
    player.addEventListener('pause', () => {
      if (state.phase === 'playing' && !player.ended) failAttempt('Naputol ang video. Subukan muli.');
    });
    player.addEventListener('waiting', () => {
      if (state.phase === 'playing' && state.recorder?.state === 'recording') {
        try { state.recorder.pause(); }
        catch (_) { failAttempt('Hindi maipagpatuloy ang pag-record. Subukan muli.'); }
      }
    });
    player.addEventListener('error', () => {
      if (['countdown', 'starting', 'playing'].includes(state.phase)) failAttempt('Hindi mapatugtog ang video. Subukan muli.');
    });
    // The shared controls retain their own leave-confirmation dialog and navigation.
    // This activity has no partial item progress to save; never overwrite a submitted state on leave.
    window.__activityLeaveAdapter = { cleanup: dispose, saveCurrentProgress: async () => state.submissionPromise };
    window.lessonOneVideoFlow = {
      interrupt() {
        if (['initializing', 'countdown', 'starting', 'playing', 'finalizing'].includes(state.phase)) {
          failAttempt('Naantala ang gawain. Subukan muli.');
        }
      },
      cleanup: dispose,
    };
    if (!showPersistedActivityState()) showWelcomeModal();
    startCompletionStatusPolling();
    document.getElementById('done').addEventListener('click', () => {
      dispose(); window.location.assign(document.querySelector('.back').href);
    });
    window.addEventListener('pagehide', dispose);
    window.addEventListener('beforeunload', dispose);
  }
  document.addEventListener('DOMContentLoaded', init, { once: true });
})();
