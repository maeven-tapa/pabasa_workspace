(() => {
  'use strict';

  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;

  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const audioBase = '/static/pabasa_app/prescribed/audio/SESSION_12/LESSON_28/GAWAIN_2/';
  const introAudio = 'Word Identifying. Listen to the word, then circle the correct word..mp3';
  const correctAudio = 'That’s right, now let’s read the next word..mp3';
  const retryAudio = 'Hmm, let’s try that again..mp3';
  const completionAudio = 'Great job! You completed Word Identifying..mp3';
  const wordAudio = {let: 'Let.mp3', lit: 'Lit.mp3', met: 'Met.mp3', sat: 'Sat.mp3', set: 'Set.mp3', sit: 'Sit.mp3', sun: 'Sun.mp3'};
  const audioUrl = filename => {
    if (!filename) throw new Error('Could not find the audio for this activity.');
    return `${audioBase}${filename.split('/').map(encodeURIComponent).join('/')}`;
  };

  let state = {...(data.progress?.state || {})};
  let busy = false;
  let paused = false;
  const audioPlayer = window.PrescribedAudioPlayer.create();
  const pendingWrites = new Set();
  let started = false, restarting = false, disposed = false;
  const current = token => audioPlayer.isCurrent(token) && !paused && !disposed;
  let wrongChoice = '';

  function updateStaticCopy() {
    document.querySelector('#lesson28a2-start .modal > p:not(.start-label)')?.replaceChildren('Listen to the word, then circle the correct word.');
    document.querySelector('#prescribed-l28a2-help-modal .prescribed-l28a2-help-step:last-child span')?.replaceChildren('Circle the word you heard to continue.');
  }

  function hydrate() {
    state.current_item = Number(state.current_item || 0);
    state.completed_items = Number(state.completed_items || 0);
    state.phase ||= 'choosing';
  }

  async function post(url, body) {
    const task = send(url, body);
    pendingWrites.add(task);
    try { return await task; }
    finally { pendingWrites.delete(task); }
  }

  async function send(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save your progress.');
    if (result.progress?.state) state = {...result.progress.state};
    hydrate();
    return result;
  }

  function steps() {
    const current = state.phase === 'complete' ? data.items.length : state.current_item;
    return `<div class="progress" aria-label="Activity progress">${data.items.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;
  }

  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.items.length) {
      window.PrescribedLessonUi.showCompletion(app);
      post(data.completion_url, {}).catch(() => {});
      return;
    }

    const item = data.items[state.current_item];
    const target = state.target_word || '';
    app.innerHTML = `<div class="eyebrow">SESSION 12 · LESSON 28 · ACTIVITY 2</div>
      <p class="instruction">Listen to the word, then circle the correct word.</p>
      <div class="content">
        <p class="label">Listen carefully, then circle the matching word.</p>
        <div class="choices" aria-label="Circle the matching word">
          ${item.choices.map(word => `<button class="choice ${wrongChoice === word ? 'is-wrong' : ''}" data-choice="${esc(word)}" type="button" ${!target || busy || paused || pendingWrites.size ? 'disabled' : ''}>${esc(word)}</button>`).join('')}
        </div>
        <p class="status ${kind}" id="status">${esc(message || (target ? 'Choose the word you heard.' : 'Preparing the word…'))}</p>
        <div class="actions"><button class="button secondary" id="listen" type="button" ${!target || busy || paused || pendingWrites.size ? 'disabled' : ''}><span aria-hidden="true">🔊</span> Listen</button></div>
      </div>${steps()}`;

    document.getElementById('listen')?.addEventListener('click', () => playWord(target).catch(error => render(error.message, 'bad')));
    app.querySelectorAll('[data-choice]').forEach(button => {
      button.addEventListener('click', () => choose(button.dataset.choice));
    });
  }

  async function playFile(filename) {
    await audioPlayer.playSequence([audioUrl(filename)]);
  }

  async function playWord(word) {
    if (busy || paused || disposed || pendingWrites.size || !word) return;
    const token = audioPlayer.generation;
    busy = true;
    let message = '';
    render('Listening…');
    try {
      await playFile(wordAudio[String(word).toLowerCase()]);
    } catch (error) {
      if (current(token) && error.name !== 'AbortError') message = error.message;
    } finally {
      if (current(token)) { busy = false; render(message, message ? 'bad' : ''); }
    }
  }

  async function begin() {
    await post(data.progress_url, {action: 'begin', item_index: state.current_item});
    wrongChoice = '';
  }

  async function choose(choice) {
    if (busy || paused || disposed || pendingWrites.size || !state.target_word) return;
    const token = audioPlayer.generation;
    busy = true;
    render();
    let message = '';
    let kind = '';
    let nextTarget = '';
    let feedbackAudio = '';
    let accepted = false;
    try {
      const result = await post(data.progress_url, {
        action: 'choose',
        item_index: state.current_item,
        choice,
      });
      if (!current(token)) return;
      accepted = Boolean(result.accepted);
      wrongChoice = accepted ? '' : choice;
      message = accepted ? 'Correct! Listen to the next word.' : 'That is not the matching word. Try another choice.';
      kind = accepted ? 'good' : 'bad';
      // A mistake repeats this row's target. A correct answer has already
      // advanced the server state, so its target belongs to the next row.
      nextTarget = state.phase === 'complete' ? '' : state.target_word;
      feedbackAudio = accepted
        ? (state.phase === 'complete' ? completionAudio : correctAudio)
        : retryAudio;
      render(message, kind);
      const clips = [audioUrl(feedbackAudio)];
      if (nextTarget) clips.push(audioUrl(wordAudio[String(nextTarget).toLowerCase()]));
      await audioPlayer.playSequence(clips);
      if (!current(token)) return;
      if (!accepted) wrongChoice = '';
    } catch (error) {
      if (!current(token) || error.name === 'AbortError') return;
      message = error.message || 'Could not save your choice.';
      kind = 'bad';
    } finally {
      if (current(token)) busy = false;
    }
    if (!current(token)) return;
    render(message, kind);
  }

  function stopAudio() {
    audioPlayer.cancel();
    busy = Boolean(pendingWrites.size);
    wrongChoice = '';
  }

  async function reset(event) {
    event?.preventDefault();
    if (restarting) return;
    restarting = true;
    stopAudio();
    busy = true;
    try {
      // An answer already sent must settle before reset can clear it.
      await Promise.allSettled([...pendingWrites]);
      await post(data.progress_url, {reset: true});
      window.location.reload();
    } catch (error) {
      busy = false;
      restarting = false;
      paused = false;
      render(error.message, 'bad');
      window.alert(error.message || 'Could not reset the activity.');
    }
  }

  document.getElementById('lesson28a2-later')?.addEventListener('click', reset);
  document.getElementById('lesson28a2-go')?.addEventListener('click', async () => {
    if (started) return;
    started = true;
    const token = audioPlayer.generation;
    document.getElementById('lesson28a2-start').hidden = true;
    document.getElementById('lesson28a2-stage').classList.remove('waiting');
    busy = true;
    render();
    // Prepare the target while the introduction plays. Handle a rejected save
    // immediately, even if the learner pauses before the intro has finished.
    const prepared = begin().then(() => null, error => error);
    try {
      await audioPlayer.playSequence([audioUrl(introAudio), async () => {
        const error = await prepared;
        if (error) throw error;
        return audioUrl(wordAudio[String(state.target_word || '').toLowerCase()]);
      }]);
      if (current(token)) { busy = false; render(); }
    } catch (error) {
      if (current(token) && error.name !== 'AbortError') { busy = false; render(error.message, 'bad'); }
    }
  });

  window.addEventListener('pagehide', () => { disposed = true; stopAudio(); });
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
  updateStaticCopy();
  hydrate();
  render();

  if (window.PrescribedControls && !window.__prescribedL28a2ControlsInitialized) {
    window.__prescribedL28a2ControlsInitialized = true;
    window.PrescribedControls.init({
      prefix: 'prescribed-l28a2',
      adapter: {
        pause() {
          paused = true;
          stopAudio();
          render();
        },
        async resume() {
          if (!paused || restarting || disposed) return;
          paused = false;
          const token = audioPlayer.generation;
          busy = true;
          render();
          try {
            await Promise.allSettled([...pendingWrites]);
            if (!current(token) || restarting) return;
            if (started && !state.target_word && state.phase !== 'complete') await begin();
            if (!current(token) || restarting) return;
            busy = false;
            render();
            if (started && state.phase !== 'complete') await playWord(state.target_word);
          } catch (error) {
            if (current(token)) { busy = false; render(error.message, 'bad'); }
          }
        },
        restart() {
          return reset();
        },
        cleanup() { disposed = true; stopAudio(); },
      },
    });
  }
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters['prescribed-l28a2'] = {
    async saveCurrentProgress() {
      await Promise.all([...pendingWrites]);
    },
    cleanup() { disposed = true; stopAudio(); },
  };
})();
