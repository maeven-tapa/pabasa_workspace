(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;
  const refinement = document.createElement('link');
  refinement.rel = 'stylesheet';
  refinement.href = '/static/pabasa_app/css/lesson29_activity2_refinement.css?v=lesson29-a2-ui-5';
  document.head.appendChild(refinement);
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let state = {...(data.progress?.state || {})}, busy = false, paused = false, audioUrl = null, audio = null, completionAnnounced = false;
  const emitDebug = detail => window.dispatchEvent(new CustomEvent('session13-prescribed-s13l29g2-debug', {detail}));
  function hydrate() { state.current_item = Number(state.current_item || 0); state.selected_words ||= []; state.phase ||= 'spotting'; }
  async function post(url, body) { const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)}), result = await response.json(); if (!response.ok || !result.success) throw Error(result.error || 'Could not save your progress.'); if (result.progress?.state) state = {...result.progress.state}; hydrate(); return result; }
  function steps() { const current = state.phase === 'complete' ? data.words.length : state.current_item; return `<div class="progress">${data.words.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`; }
  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.words.length) { window.PrescribedLessonUi.showCompletion(app); post(data.completion_url, {}).catch(() => {}); if (!completionAnnounced) { completionAnnounced = true; play('Great job! You spotted all the words.').catch(() => {}); } return; }
    const selected = new Set(state.selected_words);
    app.innerHTML = `<div class="eyebrow">SESSION 13 · LESSON 29 · ACTIVITY 2</div><h1 class="title">Spot the Word</h1><p class="instruction">Listen to the word, then encircle it.</p><div class="grid">${data.words.map(word => `<button class="word ${selected.has(word) ? 'correct' : state.wrong_word === word ? 'wrong' : ''}" data-word="${esc(word)}" ${selected.has(word) || busy ? 'disabled' : ''}>${esc(word)}</button>`).join('')}</div><p class="status ${kind}">${esc(message || 'Listen carefully, then choose the word you heard.')}</p><button class="button" id="listen" ${busy ? 'disabled' : ''}>🔊 Listen</button>${steps()}`;
    app.querySelectorAll('[data-word]').forEach(button => { button.onclick = () => choose(button.dataset.word); });
    document.getElementById('listen').onclick = () => play(state.target_word).catch(error => render(error.message, 'bad'));
    emitDebug({status:paused ? 'Paused' : 'Ready', expected:state.target_word || '—', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting'});
  }
  async function play(text) {
    if (busy || paused || !text) return;
    emitDebug({status:'Playing audio', expected:state.target_word || '—', raw:`Playing: ${text}`});
    busy = true;
    const buttons=[...app.querySelectorAll('button')],buttonStates=buttons.map(button=>({button,disabled:button.disabled})); buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});


    try { const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-29-gawain-2'})}), result = await response.json(); if (!response.ok || !result.success || !result.audio_content) throw Error(result.error || 'Could not play audio.'); const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0)); audioUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'})); audio = new Audio(audioUrl); await new Promise((resolve, reject) => { audio.onended = resolve; audio.onerror = () => reject(Error('Audio playback failed.')); audio.play().catch(reject); }); }
    catch (error) { emitDebug({status:'Error', error:error.message || 'Audio playback failed.', raw:`Error: ${error.message || 'Audio playback failed.'}`}); }
    finally { busy=false; buttonStates.forEach(({button,disabled})=>{if(button.isConnected)button.disabled=disabled;}); buttons.forEach(button=>{if(button.isConnected)button.classList.remove('is-busy');}); if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null;} audio=null; }
  }
  async function begin() { await post(data.progress_url, {action:'begin', item_index:state.current_item}); render(); }
  async function choose(word) {
    if (busy || paused) return;
    busy = true; let message = '', kind = '', nextTarget = '', feedback = '', accepted = false;
    try { const result = await post(data.progress_url, {action:'choose', item_index:state.current_item, word}); accepted = Boolean(result.accepted); message = accepted ? 'Correct' : 'Try again'; feedback = accepted ? 'Correct.' : 'Try again.'; kind = accepted ? 'good' : 'bad'; nextTarget = accepted && state.phase !== 'complete' ? state.target_word : ''; }
    catch (error) { message = error.message; kind = 'bad'; }
    finally { busy = false; }
    emitDebug({status:accepted ? 'Correct' : 'Try again', raw:feedback || 'Waiting for selection.'});
    render(message, kind);
    if (feedback) await play(feedback).catch(() => {});
    if (nextTarget) await play(nextTarget).catch(error => render(error.message, 'bad'));
  }
  async function reset(event) { event.preventDefault(); if (busy) return; busy = true; try { await post(data.progress_url, {reset:true}); window.location.reload(); } catch (error) { busy = false; alert(error.message); } }

  document.getElementById('lesson29a2-later').onclick = reset;
  document.getElementById('lesson29a2-go').onclick = async () => { document.getElementById('lesson29a2-start').hidden = true; document.getElementById('lesson29a2-stage').classList.remove('waiting'); try { await play('Spot the Word. Listen to the word, then encircle it.'); await begin(); await play(state.target_word); } catch (error) { render(error.message, 'bad'); } };
  window.addEventListener('pagehide', () => audio?.pause());
  window.addEventListener('session13-prescribed-s13l29g2-pause', () => { paused = true; audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g2-resume', () => { paused = false; render(); });
  window.addEventListener('session13-prescribed-s13l29g2-restart', () => reset(new Event('submit')));
  window.addEventListener('session13-prescribed-s13l29g2-cleanup', () => audio?.pause());
  hydrate();
  render();
})();
