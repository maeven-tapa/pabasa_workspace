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

  let state = {...(data.progress?.state || {})};
  let busy = false;
  let paused = false;
  let audio = null;
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
          ${item.choices.map(word => `<button class="choice ${wrongChoice === word ? 'is-wrong' : ''}" data-choice="${esc(word)}" type="button" ${!target || busy || paused ? 'disabled' : ''}>${esc(word)}</button>`).join('')}
        </div>
        <p class="status ${kind}" id="status">${esc(message || (target ? 'Choose the word you heard.' : 'Preparing the word…'))}</p>
        <div class="actions"><button class="button secondary" id="listen" type="button" ${!target || busy || paused ? 'disabled' : ''}><span aria-hidden="true">🔊</span> Listen</button></div>
      </div>${steps()}`;

    document.getElementById('listen')?.addEventListener('click', () => playWord(target).catch(error => render(error.message, 'bad')));
    app.querySelectorAll('[data-choice]').forEach(button => {
      button.addEventListener('click', () => choose(button.dataset.choice));
    });
  }

  async function playFile(filename) {
    if (!filename) throw new Error('Could not find the audio for this activity.');
    audio?.pause();
    audio = new Audio(`${audioBase}${filename.split('/').map(encodeURIComponent).join('/')}`);
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(new Error('Audio playback failed. Try again.'));
      audio.play().catch(reject);
    });
    audio = null;
  }

  async function playWord(word) {
    if (busy || paused || !word) return;
    busy = true;
    render('Listening…');
    try {
      await playFile(wordAudio[String(word).toLowerCase()]);
    } finally {
      busy = false;
      render();
    }
  }

  async function begin() {
    await post(data.progress_url, {action: 'begin', item_index: state.current_item});
    wrongChoice = '';
    render();
  }

  async function choose(choice) {
    if (busy || paused || !state.target_word) return;
    busy = true;
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
      accepted = Boolean(result.accepted);
      wrongChoice = accepted ? '' : choice;
      message = accepted ? 'Correct! Listen to the next word.' : 'That is not the matching word. Try another choice.';
      kind = accepted ? 'good' : 'bad';
      nextTarget = accepted ? state.target_word : '';
      feedbackAudio = accepted
        ? (state.phase === 'complete' ? completionAudio : correctAudio)
        : retryAudio;
      render(message, kind);
      await playFile(feedbackAudio);
      if (!accepted) wrongChoice = '';
    } catch (error) {
      message = error.message || 'Could not save your choice.';
      kind = 'bad';
    } finally {
      busy = false;
    }
    render(message, kind);
    if (nextTarget) await playWord(nextTarget);
  }

  function stopAudio() {
    audio?.pause();
    audio = null;
  }

  async function reset(event) {
    event?.preventDefault();
    if (busy) return;
    busy = true;
    try {
      await post(data.progress_url, {reset: true});
      window.location.reload();
    } catch (error) {
      busy = false;
      window.alert(error.message || 'Could not reset the activity.');
    }
  }

  document.getElementById('lesson28a2-later')?.addEventListener('click', reset);
  document.getElementById('lesson28a2-go')?.addEventListener('click', async () => {
    document.getElementById('lesson28a2-start').hidden = true;
    document.getElementById('lesson28a2-stage').classList.remove('waiting');
    try {
      await playFile(introAudio);
      await begin();
      await playWord(state.target_word);
    } catch (error) {
      busy = false;
      render(error.message, 'bad');
    }
  });

  window.addEventListener('pagehide', stopAudio);
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
        resume() {
          paused = false;
          render();
        },
        restart() {
          return reset();
        },
        cleanup: stopAudio,
      },
    });
  }
})();
