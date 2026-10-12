(() => {   'use strict';   const node = document.getElementById('prescribed-activity-data');   const app = document.getElementById('app');   if (!node || !app) return;   const data = JSON.parse(node.textContent || '{}');   const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');   const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({     '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'   }[char]));   let state = { ...(data.progress?.state || {}) };   let busy = false;   let stream = null;   let audio = null;   let wrongChoice = '';
  let paused = false, muted = false, disposed = false, generation = 0, audioAbort = null, pendingSave = null;
  const pendingSaves = new Set();
  window.__session15RestartAdapters ||= {};
  window.__session15RestartAdapters.lesson31a1 = {async waitForPendingSaves() {
    const results = await Promise.allSettled([...pendingSaves]);
    const failure = results.find(result => result.status === 'rejected');
    if (failure) throw failure.reason;
  }};
  const isCurrent = token => token === generation && !paused && !disposed;
  // A cached history entry retains disposed controls and potentially stale
  // progress. Reload it through the normal saved-progress/start flow.
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
  const playbackCancelled = () => new DOMException('Activity playback cancelled.', 'AbortError');
  function cancel(speechHandledByControls = false) {
    generation++;
    audioAbort?.abort();
    audio?.pause();
    if (!speechHandledByControls) window.Basahin?.cancelAll();
    stream?.getTracks().forEach(track => track.stop());
    stream = null;
    busy = false;
    if (!disposed) render();
  }
  for (const event of ['cancel', 'pause', 'cleanup', 'restart']) {
    window.addEventListener('session15-lesson31a1-' + event, detailEvent => {
      if (event === 'pause') paused = true;
      if (event === 'cleanup' || event === 'restart') disposed = true;
      cancel(detailEvent.detail?.speechHandledByControls);
    });
  }
  window.addEventListener('session15-lesson31a1-resume', () => { if (disposed) return; paused = false; window.__session15SilentCancel = false; render(); });
  const pauseModal = document.getElementById('lesson31a1-pause-modal');
  pauseModal?.addEventListener('click', event => {
    if (event.target === pauseModal) window.dispatchEvent(new Event('session15-lesson31a1-resume'));
  });
  const restartModal = document.getElementById('lesson31a1-restart-modal');
  restartModal?.addEventListener('click', event => {
    if (event.target === restartModal && pauseModal) pauseModal.hidden = false;
  });
  window.addEventListener('keydown', event => {
    const restartModal = document.getElementById('lesson31a1-restart-modal');
    if (event.key === 'Escape' && restartModal && !restartModal.hidden && pauseModal) pauseModal.hidden = false;
  });
  window.addEventListener('session15-lesson31a1-mute', event => {
    muted = Boolean(event.detail?.muted);
    if (muted) cancel(event.detail?.speechHandledByControls);
  });
    function hydrate() {     state.current_item = Number(state.current_item || 0);     state.choice_index = Number(state.choice_index || 0);     state.phase ||= 'reading_choices';   }    async function post(url, body) {
    const token = generation;
    const task = (async () => {     const response = await fetch(url, {       method: 'POST', credentials: 'same-origin',       headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },       body: JSON.stringify(body)     });     const text = await response.text();     let result;     try { result = JSON.parse(text); }     catch (_) { throw new Error('The activity service is temporarily unavailable. Please try again.'); }     if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');     if (result.progress?.state) state = { ...result.progress.state };     hydrate();     return result;   })();
    pendingSave = task;
    pendingSaves.add(task);
    try {return await task;}
    finally {
      pendingSaves.delete(task);
      if (pendingSave === task) pendingSave = null;
      // A request already sent may commit during cancellation. Keep its
      // authoritative state visible without replaying the cancelled feedback.
      if (token !== generation && !paused && !disposed) render();
    }
  }
  function render(message = '', kind = '') {     hydrate();     if (state.phase === 'complete' || state.current_item >= data.items.length) {       window.PrescribedLessonUi.showCompletion(app);       post(data.completion_url, {}).catch(() => {});       return;     }     const item = data.items[state.current_item];     const choices = item.choices;     const reading = state.phase === 'reading_choices';     const choiceIndex = Math.min(state.choice_index, choices.length - 1);     app.innerHTML = `<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 1</div>       <h1 class="title">Circle the Right Word!</h1>       <p class="instruction">${reading ? 'Read each choice aloud, one at a time.' : 'Look at the picture. Circle the correct word.'}</p>       <p class="item-label">Item ${state.current_item + 1} of ${data.items.length}</p>       ${reading         ? `<div class="word" aria-live="polite">${escapeHtml(choices[choiceIndex])}</div>            <div class="read-actions"><button data-basahin-button data-basahin-language="English" class="button" id="read" type="button">Read</button><button class="button secondary" id="listen" type="button" ${Number(state.attempts||0)<3?'disabled':''}>🔊 Listen</button></div>            <div class="choices" aria-label="Choices to read">${choices.map((word, i) => `<span class="choice ${i === choiceIndex ? 'correct' : ''}">${escapeHtml(word)}</span>`).join('')}</div>`         : `<div class="picture"><img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.alt_text)}"></div>            <div class="choices" aria-label="Circle the matching word">${choices.map(word => `<button class="choice ${wrongChoice === word ? 'selected' : ''}" data-choice="${escapeHtml(word)}" type="button" ${busy ? 'disabled' : ''}>${escapeHtml(word)}</button>`).join('')}</div>` }       ${steps()}`;     if (reading) {       window.Basahin.bindActivity(document.getElementById('read'), record);       document.getElementById('listen').onclick = () => play(choices[choiceIndex]).then(() => render('Now read the word aloud.')).catch(error => { if (error?.name !== 'AbortError' && !paused && !disposed) render(error.message, 'bad'); });     } else {       app.querySelectorAll('[data-choice]').forEach(button => { button.onclick = () => choose(button.dataset.choice); });     }   }      function steps() {     const current = state.phase === 'complete' ? data.items.length : state.current_item;     return `<div class="progress" aria-label="Activity progress">${data.items.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;   }    async function play(text) {
    // Completion narration can play while its final acknowledgement is saved.
    if (busy || (pendingSave && state.phase !== 'complete') || paused || disposed || !text) return;
    const token = generation, controller = new AbortController();
    let playback = null, playbackUrl = null;
    audioAbort = controller;
    busy = true;
    const buttons = [...app.querySelectorAll('button')];
    const states = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    try {
      const response = await fetch(data.read_aloud_url, {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{'X-CSRFToken':csrf(), 'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-31-gawain-1'})
      });
      const body = await response.text();
      if (!isCurrent(token)) throw playbackCancelled();
      let result;
      try { result = JSON.parse(body); }
      catch (_) { throw new Error('Read aloud is temporarily unavailable. Please try again.'); }
      if (!isCurrent(token)) throw playbackCancelled();
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio.');
      const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0));
      playbackUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'}));
      playback = new Audio(playbackUrl);
      audio = playback;
      await new Promise((resolve, reject) => {
        playback.onended = resolve;
        playback.addEventListener('pause', resolve, {once:true});
        playback.onerror = () => reject(new Error('Audio playback failed.'));
        playback.play().catch(reject);
      });
      if (!isCurrent(token)) throw playbackCancelled();
    } finally {
      if (isCurrent(token)) {
        busy = false;
        states.forEach(({button, disabled}) => { if (button.isConnected) {button.disabled = disabled; button.classList.remove('is-busy');} });
      }
      if (playbackUrl) URL.revokeObjectURL(playbackUrl);
      if (audio === playback) audio = null;
      if (audioAbort === controller) audioAbort = null;
    }
  }

  async function record() {     if (busy || pendingSave || paused || muted || disposed || state.phase !== 'reading_choices') return; const token = generation;     if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {       render('Microphone recording is not available in this browser.', 'bad');       return;     }     busy = true;     const button = document.getElementById('read'), listen = document.getElementById('listen'); button?.classList.add('is-busy'); if (listen) listen.disabled = true;     const itemIndex = state.current_item;     const choiceIndex = state.choice_index;     const target = data.items[itemIndex].choices[choiceIndex];     let message = '';     let kind = '';     try {       const transcript = await window.Basahin.read({target_text:target, language:'English', mode:'reading', prescribed_activity_key:'lesson-31-gawain-1'}, {button:button, url:data.transcribe_url}); if (!isCurrent(token)) return; const heard = String(transcript.raw_transcript || transcript.transcript || '');       const result = await post(data.progress_url, { action: 'read_choice', item_index: itemIndex, choice_index: choiceIndex, heard });       if (!isCurrent(token)) return; message = result.accepted ? (state.phase === 'choosing' ? 'Great reading! Now look at the picture and circle the matching word.' : 'Correct! Read the next choice.') : `I heard “${heard}”. Please try “${target}” again.`;       kind = result.accepted ? 'good' : 'bad';     } catch (error) { if (error?.name === 'AbortError' || !isCurrent(token)) return;        stopStream();       message = error.message || 'I could not hear you. Please try again.';       kind = 'bad';     } finally {       if (isCurrent(token)) { button?.classList.remove('is-busy'); if (listen?.isConnected) listen.disabled = Number(state.attempts||0) < 3; busy = false; }     }     render(message, kind);     if (kind === 'good' && state.phase === 'choosing') { play('Correct!').then(() => play('Now, encircle the right choice.')).catch(() => {}); } else { play(kind === 'good' ? (state.phase === 'complete' ? 'Wonderful! You finished the activity.' : 'Correct!') : 'Hmm, let’s try that again.').catch(() => {}); }   }    async function choose(word) {     if (busy || pendingSave || paused || disposed || state.phase !== 'choosing') return; const token = generation;     busy = true;     const itemIndex = state.current_item;     let message = '';     let kind = '';     try {       const result = await post(data.progress_url, { action: 'choose', item_index: itemIndex, choice: word });       if (!isCurrent(token)) return; wrongChoice = result.accepted ? '' : word;       message = result.accepted ? (state.phase === 'complete' ? 'Wonderful! You finished the activity.' : 'Correct! Read the next set of choices.') : 'That is not the matching word. Try another choice.';       kind = result.accepted ? 'good' : 'bad';     } catch (error) {       if (!isCurrent(token)) return; message = error.message || 'Could not save your answer.';       kind = 'bad';     } finally { if (isCurrent(token)) busy = false; } if (!isCurrent(token)) return; render(message, kind);     play(kind === 'good' ? (state.phase === 'complete' ? 'Wonderful! You finished the activity.' : "Correct, now let's read the next choices.") : (state.phase === 'reading_choices' ? 'Let' + String.fromCharCode(39) + 's move to the next word.' : 'Hmm, let' + String.fromCharCode(0x2019) + 's try that again.')).catch(() => {});   }    function stopStream() { window.Basahin?.cancelAll();      stream?.getTracks().forEach(track => track.stop());     stream = null;   }    async function leave(event) {     event.preventDefault();     if (busy) return;     busy = true;     try {       await post(data.progress_url, { reset: true });       window.location.reload();     } catch (error) {       busy = false;       window.alert(error.message || 'Could not reset the activity.');     }   }       document.getElementById('lesson31a1-later').addEventListener('click', leave);   document.getElementById('lesson31a1-go').addEventListener('click', async () => {     document.getElementById('lesson31a1-start').hidden = true;     document.getElementById('lesson31a1-stage').classList.remove('waiting');     try {       await play('Circle the Right Word. Read all three choices aloud, one at a time. Then look at the picture and circle the correct word.');       if (!paused && !disposed) render();     } catch (error) {       if (error?.name !== 'AbortError' && !paused && !disposed) render(error.message, 'bad');     }   });   window.addEventListener('pagehide', () => { disposed = true; cancel(); });   hydrate();   render(); })();
