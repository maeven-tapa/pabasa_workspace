(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;
  const refinement = document.createElement('link');
  refinement.rel = 'stylesheet';
  refinement.href = '/static/pabasa_app/css/lesson29_activity2_refinement.css?v=lesson29-a2-ui-8';
  document.head.appendChild(refinement);
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let state = {...(data.progress?.state || {})}, busy = false, paused = false, pendingSave = null, completionAnnounced = false, transientWrongWord = '';
  const audioPlayer = window.PrescribedAudioPlayer.create();
  let disposed = false;
  window.addEventListener('pageshow', event => {if (event.persisted) window.location.reload();});
  const pendingWrites = new Set();
  window.__session13RestartAdapters ||= {};
  window.__session13RestartAdapters['prescribed-s13l29g2'] = {async waitForPendingSaves() {
    const results = await Promise.allSettled([...pendingWrites]);
    const failure = results.find(result => result.status === 'rejected');
    if (failure) throw failure.reason;
  }};
  const emitDebug = detail => window.dispatchEvent(new CustomEvent('session13-prescribed-s13l29g2-debug', {detail}));
  function hydrate() { state.current_item = Number(state.current_item || 0); state.selected_words ||= []; state.phase ||= 'spotting'; }
  async function post(url, body) {
    const task = (async () => {
      const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)}), result = await response.json();
      if (!response.ok || !result.success) throw Error(result.error || 'Could not save your progress.');
      if (result.progress?.state) state = {...result.progress.state};
      hydrate(); return result;
    })();
    // Only an answer/progress save blocks input and narration. The final
    // completion acknowledgement can run alongside its spoken feedback.
    if (url === data.progress_url) pendingSave = task;
    pendingWrites.add(task);
    try { return await task; }
    finally { pendingWrites.delete(task); if (pendingSave === task) pendingSave = null; }
  }

  function steps() { const current = state.phase === 'complete' ? data.words.length : state.current_item; return `<div class="progress">${data.words.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`; }
  function render(message = '', kind = '') {
    if (disposed) return;
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.words.length) { window.PrescribedLessonUi.showCompletion(app); post(data.completion_url, {}).catch(() => {}); if (!completionAnnounced) { completionAnnounced = true; play('Great job! You spotted all the words.').catch(() => {}); } return; }
    const selected = new Set(state.selected_words);
    app.innerHTML = `<div class="eyebrow">SESSION 13 · LESSON 29 · ACTIVITY 2</div><p class="instruction">Listen to the word, then encircle it.</p><div class="grid">${data.words.map(word => `<button class="word ${selected.has(word) ? 'correct' : transientWrongWord === word ? 'wrong' : ''}" data-word="${esc(word)}" ${selected.has(word) || busy || pendingSave || paused ? 'disabled' : ''}>${esc(word)}</button>`).join('')}</div><p class="status ${kind}">${esc(message || 'Listen carefully, then choose the word you heard.')}</p><button class="button" id="listen" ${busy || pendingSave || paused ? 'disabled' : ''}>🔊 Listen</button>${steps()}`;
    app.querySelectorAll('[data-word]').forEach(button => { button.onclick = () => choose(button.dataset.word); });
    document.getElementById('listen').onclick = () => play(state.target_word).catch(error => render(error.message, 'bad'));
    emitDebug({status:paused ? 'Paused' : 'Ready', expected:state.target_word || '—', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting'});
  }
  async function play(text) {
    if (busy || pendingSave || paused || disposed || !text) return false;
    const token = audioPlayer.generation;
    emitDebug({status:'Playing audio', expected:state.target_word || '—', raw:`Playing: ${text}`});
    busy = true;
    const buttons = [...app.querySelectorAll('button')], states = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => {button.disabled = true; button.classList.add('is-busy');});
    try {
      await audioPlayer.play(async signal => {
        const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', signal, headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-29-gawain-2'})}), result = await response.json();
        if (!response.ok || !result.success || !result.audio_content) throw Error(result.error || 'Could not play audio.');
        const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0));
        return {blob:new Blob([bytes], {type:result.mime_type || 'audio/mpeg'})};
      });
      return true;
    } catch (error) {
      if (error?.name !== 'AbortError' && audioPlayer.isCurrent(token)) emitDebug({status:'Error', error:error.message || 'Audio playback failed.', raw:`Error: ${error.message || 'Audio playback failed.'}`});
      return false;
    } finally {
      if (audioPlayer.isCurrent(token)) {
        busy = false;
        states.forEach(({button, disabled}) => {if (button.isConnected) {button.disabled = disabled; button.classList.remove('is-busy');}});
      }
    }
  }
  function stopAudio() {
    const playing = audioPlayer.cancel();
    if (playing) busy = Boolean(pendingSave);
  }

  async function begin() { await post(data.progress_url, {action:'begin', item_index:state.current_item}); render(); }
  async function choose(word) {
    if (busy || pendingSave || paused || disposed) return;
    const token = audioPlayer.generation;
    busy = true; let message = '', kind = '', nextTarget = '', feedback = '', accepted = false;
    try { const result = await post(data.progress_url, {action:'choose', item_index:state.current_item, word}); if (!audioPlayer.isCurrent(token) || paused) return; accepted = Boolean(result.accepted); transientWrongWord = accepted ? '' : String(result.wrong_word || word); message = accepted ? 'Correct' : 'Try again'; feedback = accepted ? 'Correct.' : 'Try again.'; kind = accepted ? 'good' : 'bad'; nextTarget = accepted && state.phase !== 'complete' ? state.target_word : ''; }
    catch (error) { if (!audioPlayer.isCurrent(token)) return; message = error.message; kind = 'bad'; }
    finally { busy = false; if (!audioPlayer.isCurrent(token)) render(); }
    if (!audioPlayer.isCurrent(token) || paused) return;
    emitDebug({status:accepted ? 'Correct' : 'Try again', raw:feedback || 'Waiting for selection.'});
    render(message, kind);
    if (feedback) {
      await play(feedback).catch(() => {});
      if (!audioPlayer.isCurrent(token) || paused) return;
      if (!accepted) { transientWrongWord = ''; render(); }
    }
    if (nextTarget) await play(nextTarget).catch(error => render(error.message, 'bad'));
  }
  async function reset(event) { event.preventDefault(); if (busy || pendingSave) return; stopAudio(); busy = true; try { await post(data.progress_url, {reset:true}); window.location.reload(); } catch (error) { busy = false; alert(error.message); } }

  document.getElementById('lesson29a2-later').onclick = reset;
  document.getElementById('lesson29a2-go').onclick = async () => {
    document.getElementById('lesson29a2-start').hidden = true;
    document.getElementById('lesson29a2-stage').classList.remove('waiting');
    const token = audioPlayer.generation;
    let errorMessage = '';
    busy = true;
    try {
      await begin();
      if (!audioPlayer.isCurrent(token) || paused) return;
      busy = false;
      await play('Spot the Word. Listen to the word, then encircle it.');
      if (!audioPlayer.isCurrent(token) || paused) return;
      await play(state.target_word);
    } catch (error) {
      if (audioPlayer.isCurrent(token)) errorMessage = error.message;
    } finally {
      if (audioPlayer.isCurrent(token) || !audioPlayer.playing) {busy = false; render(errorMessage, errorMessage ? 'bad' : '');}
    }
  };
  window.addEventListener('pagehide', stopAudio);
  window.addEventListener('session13-prescribed-s13l29g2-pause', () => {paused = true; stopAudio(); render();});
  window.addEventListener('session13-prescribed-s13l29g2-resume', () => {if (disposed) return; paused = false; render();});
  window.addEventListener('session13-prescribed-s13l29g2-restart', () => {disposed = true; stopAudio();});
  window.addEventListener('session13-prescribed-s13l29g2-cleanup', stopAudio);
  const pauseModal = document.getElementById('prescribed-s13l29g2-pause-modal');
  pauseModal?.addEventListener('click', event => {if (event.target === pauseModal) {paused = false; render();}});
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters['prescribed-s13l29g2'] = {
    saveCurrentProgress() {
      return Promise.resolve();
    },
    cleanup() {
      window.dispatchEvent(new Event('session13-prescribed-s13l29g2-cleanup'));
    },
  };
  hydrate();
  render();
})();
