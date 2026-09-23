(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const CORRECT_FEEDBACK = "That's right, now let's read the next sentence.";
  const COMPLETION_FEEDBACK = 'Great job! You completed all the sentences.';
  let state = {...(data.progress?.state || {})}, busy = false, paused = false, muted = false, generation = 0, stream = null, recorder = null, recorderTimer = null, audioUrl = null, audio = null;
  const emitDebug = detail => window.dispatchEvent(new CustomEvent('session13-prescribed-s13l29g1-debug', {detail}));
  const normalizeTranscript = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
  function hydrate() { state.current_item = Number(state.current_item || 0); state.completed_items = Number(state.completed_items || 0); state.phase ||= 'answering'; }
  async function post(url, body) { const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)}), result = await response.json(); if (!response.ok || !result.success) throw Error(result.error || 'Could not save your progress.'); if (result.progress?.state) state = {...result.progress.state}; hydrate(); return result; }
  function steps() { const current = state.phase === 'complete' ? data.items.length : state.current_item; return `<div class="progress">${data.items.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`; }
  function setButtonState(mode) { const read = document.getElementById('read'), listen = document.getElementById('listen'); if (!read || !listen) return; const enabled = mode === 'ready'; read.disabled = mode === 'audio'; listen.disabled = !enabled; read.classList.toggle('is-busy', mode === 'recording' || mode === 'audio'); listen.classList.toggle('is-busy', mode === 'audio'); }
  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.items.length) { window.PrescribedLessonUi.showCompletion(app); post(data.completion_url, {}).catch(() => {}); return; }
    const item = data.items[state.current_item], hint = String(state.hint || ''), blank = hint + '_'.repeat(Math.max(0, item.word_length - hint.length));
    app.innerHTML = `<div class="eyebrow">SESSION 13 · LESSON 29 · ACTIVITY 1</div><h1 class="title">Fill in the Blank</h1><p class="instruction">Say the missing word to complete each sentence.</p><div class="content"><div class="item"><div class="sentence lead">${esc(item.before)}</div><img class="picture" src="${esc(item.image_url)}" alt="Picture clue"><div class="sentence tail"><span class="blank">${esc(blank)}</span>${esc(item.after)}</div></div><p class="status ${kind}" id="status">${esc(message || (hint ? 'Use the letter hint and say the missing word.' : 'Read the sentence, then say the missing word.'))}</p><div class="actions"><button class="button" id="read" type="button">🎙️ Say the missing word</button><button class="button secondary" id="listen" type="button">🔊 Listen</button></div></div>${steps()}`;
    document.getElementById('read').onclick = record;
    document.getElementById('listen').onclick = () => play(item.tts_word || state.help_word || hint).catch(error => render(error.message, 'bad'));
    setButtonState('ready');
    emitDebug({status:paused ? 'Paused' : 'Ready', expected:item.answer || item.tts_word || '—', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting'});
  }
  async function play(text, lockButtons = true) {
    if (busy || paused || !text) return;
    busy = true; const buttons=[...app.querySelectorAll('button')],buttonStates=buttons.map(button=>({button,disabled:button.disabled})); buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});
    try { const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-29-gawain-1'})}), result = await response.json(); if (!response.ok || !result.success || !result.audio_content) throw Error(result.error || 'Could not play audio.'); const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0)); audioUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'})); audio = new Audio(audioUrl); await new Promise((resolve, reject) => { audio.onended = resolve; audio.onerror = () => reject(Error('Audio playback failed.')); audio.play().catch(reject); }); }
    catch (error) {}
    finally { busy=false; buttonStates.forEach(({button,disabled})=>{if(button.isConnected)button.disabled=disabled;}); buttons.forEach(button=>{if(button.isConnected)button.classList.remove('is-busy');}); if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null;} audio=null; }
  }
  async function record() {
    if (busy || paused || muted || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { if (!busy && !paused && !muted) render('Microphone recording is not available in this browser.', 'bad'); return; }
    const attemptGeneration = generation;
    busy = true; setButtonState('recording'); emitDebug({status:'Listening', expected:data.items[state.current_item]?.answer || data.items[state.current_item]?.tts_word || '—', mic:'Active · Unmuted', recorder:'Recording', vad:'waiting', error:'—', raw:'Listening for speech...'});
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:true});
      stream.getTracks().forEach(track => { track.enabled = !muted; });
      if (attemptGeneration !== generation || paused) throw Error('Recording cancelled.');
      recorder = new MediaRecorder(stream); const chunks = [];
      recorder.ondataavailable = event => event.data.size && chunks.push(event.data);
      const blob = await new Promise((resolve, reject) => { recorder.onerror = () => reject(Error('Could not record your voice.')); recorder.onstop = () => resolve(new Blob(chunks, {type:recorder.mimeType || 'audio/webm'})); recorder.start(); recorderTimer = setTimeout(() => recorder?.state === 'recording' && recorder.stop(), 3000); });
      if (attemptGeneration !== generation || paused) throw Error('Recording cancelled.');
      emitDebug({status:'Processing', recorder:'inactive', raw:'Processing the recording...'}); stop();
      const form = new FormData(); form.append('audio', blob, 'lesson29-activity1.webm'); form.append('target_text', data.recognition_hints); form.append('language', 'English'); form.append('mode', 'reading');
      const response = await fetch(data.transcribe_url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:form}), result = await response.json();
      if (attemptGeneration !== generation || paused) throw Error('Recording cancelled.');
      if (!response.ok || !result.success) throw Error(result.error || 'Speech recognition failed.');
      const heard = String(result.raw_transcript || result.transcript || ''), saved = await post(data.progress_url, {action:'answer', item_index:state.current_item, heard});
      emitDebug({status:'Ready', transcript:heard || 'No transcript yet.', normalized:normalizeTranscript(heard) || '—', result:saved.accepted ? 'Correct' : 'Try again', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting', error:'—', raw:`Transcript: ${heard || 'No transcript yet.'} · Result: ${saved.accepted ? 'Correct' : 'Try again'}`});
      const correct = Boolean(saved.accepted), feedback = state.phase === 'complete' ? COMPLETION_FEEDBACK : (correct ? CORRECT_FEEDBACK : RETRY_FEEDBACK);
      busy = false; render(correct ? 'Correct!' : `I heard “${heard}”. Try again.`, correct ? 'good' : 'bad');
      await play(feedback);
    } catch (error) { stop(); busy = false; emitDebug({status:'Error', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting', error:error.message || 'Recording failed.', raw:`Error: ${error.message || 'Recording failed.'}`}); render(error.message || 'I could not hear you. Try again.', 'bad'); }
    finally { busy = false; if (document.getElementById('read')) setButtonState('ready'); }
  }
  function stop() { if (recorder?.state === 'recording') { try { recorder.stop(); } catch (_) {} } if (recorderTimer) clearTimeout(recorderTimer); recorderTimer = null; recorder = null; stream?.getTracks().forEach(track => track.stop()); stream = null; }
  async function reset(event) { event.preventDefault(); if (busy) return; busy = true; try { await post(data.progress_url, {reset:true}); window.location.reload(); } catch (error) { busy = false; alert(error.message); } }

  document.getElementById('lesson29a1-later').onclick = reset;
  document.getElementById('lesson29a1-go').onclick = async () => { document.getElementById('lesson29a1-start').hidden = true; document.getElementById('lesson29a1-stage').classList.remove('waiting'); try { await play('Fill in the Blank. Say the missing word to complete each sentence.'); } catch (error) { render(error.message, 'bad'); } };
  window.addEventListener('pagehide', () => { stop(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-pause', () => { paused = true; generation += 1; stop(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-resume', () => { paused = false; render(); });
  window.addEventListener('session13-prescribed-s13l29g1-restart', () => reset(new Event('submit')));
  window.addEventListener('session13-prescribed-s13l29g1-cleanup', () => { generation += 1; stop(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-mute', event => { muted = Boolean(event.detail?.muted); stream?.getTracks().forEach(track => { track.enabled = !muted; }); emitDebug({mic:`${stream ? 'Active' : 'Inactive'} · ${muted ? 'Muted' : 'Unmuted'}`}); });
  hydrate(); render();
})();
