(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;

  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const WORD_CORRECT_FEEDBACK = "That's right, now let's read the whole sentence.";
  const SENTENCE_CORRECT_FEEDBACK = "That's right, now let's read the next sentence.";
  const COMPLETION_FEEDBACK = 'Great job! You completed all the sentences.';
  let state = {...(data.progress?.state || {})};
  let busy = false, paused = false, muted = false, speechAttemptActive = false, generation = 0, disposed = false;
  let stream = null, recorder = null, recorderTimer = null, audioUrl = null, audio = null;
  const sentenceReader = window.PrescribedSentenceReading.create({key:'lesson-29-gawain-1',
    getState:() => state, save:body => post(data.progress_url, body), url:data.transcribe_url,
    onRestore:() => {if (!paused && !busy && !disposed) render();}});

  const emitDebug = detail => window.dispatchEvent(new CustomEvent('session13-prescribed-s13l29g1-debug', {detail}));
  const normalizeTranscript = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
  const sentenceText = item => `${item.before}${item.answer}${item.after}`.replace(/\s+/g, ' ').trim();
  function hydrate() {
    state.current_item = Number(state.current_item || 0);
    state.completed_items = Number(state.completed_items || 0);
    state.sentence_attempts = Number(state.sentence_attempts || 0);
    state.phase ||= 'answering';
  }
  async function post(url, body) {
    const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok || !result.success) throw Error(result.error || 'Could not save your progress.');
    if (result.progress?.state) state = {...result.progress.state};
    hydrate();
    return result;
  }
  function steps() {
    const current = state.phase === 'complete' ? data.items.length : state.current_item;
    return `<div class="progress">${data.items.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;
  }
  function setButtonState(mode) {
    const read = document.getElementById('read'), listen = document.getElementById('listen');
    if (!read || !listen) return;
    const enabled = mode === 'ready';
    read.disabled = mode === 'audio'; listen.disabled = !enabled;
    read.classList.toggle('is-busy', mode === 'recording' || mode === 'audio');
    listen.classList.toggle('is-busy', mode === 'audio');
  }
  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.items.length) {
      window.PrescribedLessonUi.showCompletion(app);
      post(data.completion_url, {}).catch(() => {});
      return;
    }
    const item = data.items[state.current_item];
    const readingSentence = state.phase === 'sentence_reading';
    const hint = String(state.hint || '');
    const blank = hint + '_'.repeat(Math.max(0, item.word_length - hint.length));
    const answer = readingSentence
      ? `<span class="blank complete-word">${esc(item.answer)}</span>`
      : `<span class="blank">${esc(blank)}</span>`;
    const instruction = readingSentence ? 'Read the complete sentence aloud.' : 'Say the missing word to complete each sentence.';
    const defaultStatus = readingSentence ? 'Now read the whole sentence.' : (hint ? 'Use the letter hint and say the missing word.' : 'Read the sentence, then say the missing word.');
    const content = readingSentence
      ? `<img class="picture reading-picture" src="${esc(item.image_url)}" alt="Picture clue"><div class="prescribed-reading-sentence">${window.PrescribedSentenceReading.markup(sentenceText(item), Number(state.sentence_word_index || 0))}</div>`
      : `<div class="item"><div class="sentence lead">${esc(item.before)}</div><img class="picture" src="${esc(item.image_url)}" alt="Picture clue"><div class="sentence tail">${answer}${esc(item.after)}</div></div>`;
    app.innerHTML = `<div class="eyebrow">SESSION 13 · LESSON 29 · ACTIVITY 1</div><p class="instruction">${instruction}</p><div class="content">${content}<p class="status ${kind}" id="status">${esc(message || defaultStatus)}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read" type="button">Read</button><button class="button secondary" id="listen" type="button">🔊 Listen</button></div></div>${steps()}`;
    window.Basahin.bindActivity(document.getElementById('read'), record);
    document.getElementById('listen').onclick = () => play(readingSentence ? sentenceText(item) : (item.tts_word || state.help_word || hint)).catch(() => {});
    setButtonState('ready');
    emitDebug({status:paused ? 'Paused' : 'Ready', expected:readingSentence ? sentenceText(item) : (item.answer || item.tts_word || '—'), mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting'});
  }
  async function play(text){
 if(busy||paused||!text)return;
 const playbackGeneration=generation;busy=true;
 const buttons=[...app.querySelectorAll('.actions button')],states=buttons.map(button=>({button,disabled:button.disabled}));
 buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});
 let source=null,activeAudio=null;
 try{
  const response=await fetch(data.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'X-csrfToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-29-gawain-1'})});
  const result=await response.json();
  if(playbackGeneration!==generation||paused)return;
  if(!response.ok||!result.success||!result.audio_content)throw new Error(result.error||'Could not play audio.');
  source=URL.createObjectURL(new Blob([Uint8Array.from(atob(result.audio_content),c=>c.charCodeAt(0))],{type:result.mime_type||'audio/mpeg'}));
  activeAudio=new Audio(source);audio=activeAudio;
  await new Promise((resolve,reject)=>{activeAudio.onended=resolve;activeAudio.addEventListener('ended',resolve,{once:true});activeAudio.addEventListener('pause',resolve,{once:true});activeAudio.addEventListener('error',()=>reject(new Error('Audio playback failed.')),{once:true});activeAudio.play().catch(reject);});
 }finally{
  if(playbackGeneration===generation){busy=false;states.forEach(({button,disabled})=>{if(button.isConnected){button.disabled=disabled;button.classList.remove('is-busy');}});}
  if(source)URL.revokeObjectURL(source);if(audio===activeAudio)audio=null;
 }
}
  async function record() {
    if (busy || paused || muted || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      if (!busy && !paused && !muted) render('Microphone recording is not available in this browser.', 'bad');
      return;
    }
    const item = data.items[state.current_item];
    const readingSentence = state.phase === 'sentence_reading';
    const target = readingSentence ? sentenceText(item) : item.answer;
    const action = readingSentence ? 'sentence_reading' : 'answer';
    const attemptGeneration = generation;
    busy = true; speechAttemptActive = true; setButtonState('recording');
    emitDebug({status:'Listening', expected:readingSentence ? target : item.answer, mic:'Active · Unmuted', recorder:'Recording', vad:'waiting', error:'—', raw:'Listening for speech...'});
    try {
      // Word mode preserves extra spoken words so phase 1 can reject whole sentences.
      const result = readingSentence
        ? await sentenceReader.read(sentenceText(item), state.current_item, document.getElementById('read'), () => attemptGeneration === generation && !paused)
        : await window.Basahin.read({target_text:target, language:'English', mode:'word', prescribed_activity_key:'lesson-29-gawain-1'}, {button:document.getElementById('read'), url:data.transcribe_url, continuous:false});
      if (attemptGeneration !== generation || paused) return;
      if (readingSentence && result.continue_prompt) {
        emitDebug({status:'Continue reading', transcript:result.raw_transcript, result:'Read the rest', mic:'Inactive · Unmuted', recorder:'inactive', error:'—'});
        busy = false; render("Great! Now let's read the rest of the sentence.", 'good');
        busy = true; setButtonState('audio'); await sentenceReader.playPrompt(); return;
      }
      const rawHeard = String(result.raw_transcript || result.transcript || '');
      const heard = rawHeard;
      const saved = readingSentence ? result : await post(data.progress_url, {action, item_index:state.current_item, heard});
      const correct = Boolean(saved.accepted);
      emitDebug({status:'Ready', transcript:heard || 'No transcript yet.', normalized:normalizeTranscript(heard) || '—', result:correct ? 'Correct' : 'Try again', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting', error:'—', raw:`Transcript: ${rawHeard || 'No transcript yet.'} · Result: ${correct ? 'Correct' : 'Try again'}`});
      const feedback = state.phase === 'complete' ? COMPLETION_FEEDBACK : (correct ? (action === 'answer' ? WORD_CORRECT_FEEDBACK : SENTENCE_CORRECT_FEEDBACK) : RETRY_FEEDBACK);
      busy = false;
      render(correct ? (action === 'answer' ? 'Correct! Now read the whole sentence.' : 'Correct!') : `I heard “${heard}”. Try again.`, correct ? 'good' : 'bad');
      await play(feedback);
    } catch (error) {
      if (error?.name === 'AbortError' || attemptGeneration !== generation || paused) return;
      stop(); busy = false;
      emitDebug({status:'Error', mic:'Inactive · Unmuted', recorder:'inactive', vad:'waiting', error:error.message || 'Recording failed.', raw:`Error: ${error.message || 'Recording failed.'}`});
      render(error.message || 'I could not hear you. Try again.', 'bad');
    } finally {
      if (attemptGeneration === generation) {
        speechAttemptActive = false; busy = false;
        if (document.getElementById('read')) setButtonState('ready');
      }
    }
  }
  function stop() {
    window.Basahin?.cancelAll();
    if (recorder?.state === 'recording') { try { recorder.stop(); } catch (_) {} }
    if (recorderTimer) clearTimeout(recorderTimer);
    recorderTimer = null; recorder = null;
    stream?.getTracks().forEach(track => track.stop()); stream = null;
  }
  function cancelSpeechAttempt() {
    sentenceReader.cancel();
    window.Basahin?.cancelAll(); generation += 1;
    if (recorderTimer) { clearTimeout(recorderTimer); recorderTimer = null; }
    const activeRecorder = recorder; recorder = null;
    if (activeRecorder && activeRecorder.state !== 'inactive') { try { activeRecorder.stop(); } catch (_) {} }
    stop(); speechAttemptActive = false; busy = false;
    document.getElementById('read')?.classList.remove('is-busy');
    emitDebug({status:paused ? 'Paused' : (muted ? 'Muted' : 'Ready'), mic:`Inactive · ${muted ? 'Muted' : 'Unmuted'}`, recorder:'inactive'}, 'Speech attempt cancelled');
  }
  async function reset(event) {
    event.preventDefault(); if (busy) return; busy = true;
    try { await post(data.progress_url, {reset:true}); window.location.reload(); }
    catch (error) { busy = false; alert(error.message); }
  }
  document.getElementById('lesson29a1-later').onclick = reset;
  document.getElementById('prescribed-s13l29g1-help-btn')?.addEventListener('click', () => { if (speechAttemptActive) cancelSpeechAttempt(); });
  document.getElementById('lesson29a1-go').onclick = async () => { document.getElementById('lesson29a1-start').hidden = true; document.getElementById('lesson29a1-stage').classList.remove('waiting'); await play('Fill in the Blank. Say the missing word to complete each sentence.').catch(() => {}); };
  window.addEventListener('pagehide', () => { disposed = true; cancelSpeechAttempt(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-help', () => { if (speechAttemptActive) cancelSpeechAttempt(); });
  window.addEventListener('session13-prescribed-s13l29g1-pause', () => { paused = true; cancelSpeechAttempt(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-resume', async () => {
    paused = false; disposed = false; const token = generation; busy = true; setButtonState('audio');
    try {
      const restored = await sentenceReader.restore(() => token === generation && !paused && !disposed);
      if (token !== generation || paused || disposed) return;
      busy = false; render();
      if (restored?.continue_prompt) {busy = true; setButtonState('audio'); await sentenceReader.playPrompt();}
    } catch (error) {if (token === generation && !paused && !disposed) render(error.message, 'bad');}
    finally {if (token === generation) {busy = false; if (!paused && !disposed) setButtonState('ready');}}
  });
  window.addEventListener('session13-prescribed-s13l29g1-restart', () => {disposed = true; reset(new Event('submit'));});
  window.addEventListener('session13-prescribed-s13l29g1-cleanup', () => { disposed = true; cancelSpeechAttempt(); audio?.pause(); });
  window.addEventListener('session13-prescribed-s13l29g1-mute', event => { muted = Boolean(event.detail?.muted); if (muted) cancelSpeechAttempt(); stream?.getTracks().forEach(track => { track.enabled = !muted; }); emitDebug({mic:`${stream ? 'Active' : 'Inactive'} · ${muted ? 'Muted' : 'Unmuted'}`}); });
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters['prescribed-s13l29g1'] = {
    async saveCurrentProgress() {
      await sentenceReader.flush();
    },
    cleanup() {
      window.dispatchEvent(new Event('session13-prescribed-s13l29g1-cleanup'));
    },
  };
  hydrate(); render();
})();
