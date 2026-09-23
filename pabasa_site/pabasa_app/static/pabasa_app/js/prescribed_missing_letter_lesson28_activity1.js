(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const normalize = value => String(value || '').toLowerCase().replace(/[^a-z]/g, '');
  let state = {...(data.progress?.state || {})};
  let busy = false, stream = null, activeRecorder = null, recordingTimeout = null, audioUrl = null, audio = null;
  let speechGeneration = 0, speechAttemptActive = false, isMuted = false, isPaused = false;
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const READ_CORRECT_FEEDBACK = "That's right, now let's write the missing letter.";
  const LETTER_CORRECT_FEEDBACK = "That's right, now let's read the next word.";
  const COMPLETION_FEEDBACK = "Great job! You completed Missing Letter.";
  function hydrate() { state.current_item = Number(state.current_item || 0); state.completed_items = Number(state.completed_items || 0); state.phase ||= 'reading'; }
  async function post(url, body) { const r = await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body)}), x = await r.json(); if (!r.ok || !x.success) throw new Error(x.error || 'Could not save your progress.'); if (x.progress?.state) state = {...x.progress.state}; hydrate(); return x; }
  function progress() { const current = state.phase === 'complete' ? data.items.length : state.current_item; return `<div class="progress" aria-label="Activity progress">${data.items.map((_,i)=>`<span class="step ${i < current ? 'done':''} ${i === current && state.phase !== 'complete' ? 'active':''}">${i+1}</span>`).join('')}</div>`; }
  function render(message='', kind='') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.items.length) { window.PrescribedLessonUi.showCompletion(app); post(data.completion_url,{}).catch(()=>{}); return; }
    const item = data.items[state.current_item], letterPhase = state.phase === 'letter';
    const canListen = Boolean(state.help_visible || Number(state.attempts || 0) >= 3);
    const visibleSuffix = String(item.stem || '').replace(/^_+/, '');
    const readingStem = String(item.stem || '').replace(/^_+/, '_');
    app.innerHTML = `<div class="eyebrow">SESSION 12 · LESSON 28 · ACTIVITY 1</div><h1 class="title">Missing Letter</h1><p class="instruction">Read the word, then write the missing letter.</p><div class="content"><div class="item"><img class="picture" src="${esc(item.image_url)}" alt="Picture clue for ${esc(item.word)}"><div><div class="label">${letterPhase ? 'Write the missing letter' : 'Read the word aloud first'}</div><div class="stem">${letterPhase ? `<input class="letter" id="letter" maxlength="1" aria-label="Missing first letter">${esc(visibleSuffix)}` : esc(readingStem)}</div><div class="actions">${letterPhase ? '<button class="button" id="check" type="button">Check letter</button>' : `<button class="button" id="read" type="button">🎙️ Read the word</button><button class="button secondary" id="listen" type="button" ${canListen ? '' : 'disabled'}>🔊 Listen</button>`}</div></div></div></div>${progress()}`;
    document.getElementById('read')?.addEventListener('click', () => record(item));
    document.getElementById('listen')?.addEventListener('click', () => playAudio(item.word).catch(error => render(error.message,'bad')));
    document.getElementById('check')?.addEventListener('click', () => submitLetter(item));
    document.getElementById('letter')?.addEventListener('keydown', event => { if (event.key === 'Enter') submitLetter(item); });
    document.getElementById('letter')?.focus();
  }
  const localAudioBase = '/static/pabasa_app/prescribed/audio/SESSION_12/LESSON_28/GAWAIN_1/';
  function localAudioKey(value) { return String(value || '').trim().toLowerCase().replace(/[’']/g, "'").replace(/[.!?]+$/, ''); }
  const localAudioFiles = {
    [localAudioKey('Missing Letter. Read the word, then write the missing letter.')]: 'Missing Letter. Read the word, then write the missing letter..mp3',
    bell: 'Bell.mp3', egg: 'Egg.mp3', lion: 'Lion.mp3', sit: 'Sit.mp3', sun: 'Sun.mp3',
    [localAudioKey(RETRY_FEEDBACK)]: 'Hmm, let’s try that again..mp3',
    [localAudioKey(READ_CORRECT_FEEDBACK)]: 'That’s right, now let’s write the missing letter..mp3',
    [localAudioKey(LETTER_CORRECT_FEEDBACK)]: 'That’s right, now let’s read the next word..mp3',
    [localAudioKey(COMPLETION_FEEDBACK)]: 'Great job! You completed Missing Letter..mp3',
  };
  async function playAudio(text) { if (busy || !text) return; busy=true; const buttons=[...app.querySelectorAll('button')],buttonStates=buttons.map(button=>({button,disabled:button.disabled})); buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');}); try { const filename=localAudioFiles[localAudioKey(text)]; if(!filename) throw new Error('Could not find the audio for this activity.'); audio=new Audio(`${localAudioBase}${filename.split('/').map(encodeURIComponent).join('/')}`); await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(new Error('Audio playback failed. Try again.'));audio.play().catch(reject);}); } finally { busy=false; buttonStates.forEach(({button,disabled})=>{if(button.isConnected)button.disabled=disabled;}); buttons.forEach(button=>{if(button.isConnected)button.classList.remove('is-busy');}); audio=null; } }
  async function record(item) { if(busy)return; const attempt=++speechGeneration; speechAttemptActive=true; const button=document.getElementById('read'); if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){render('Microphone recording is not available in this browser.','bad');speechAttemptActive=false;return;} busy=true; button?.classList.add('is-busy'); try { stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}}); applyMuteToStream(); if(attempt!==speechGeneration)return; const recorder=new MediaRecorder(stream); activeRecorder=recorder; const chunks=[]; recorder.ondataavailable=e=>e.data.size&&chunks.push(e.data); const stopped=new Promise((resolve,reject)=>{recorder.onerror=()=>reject(new Error('Could not record your voice.'));recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}));recorder.start();recordingTimeout=setTimeout(()=>{recordingTimeout=null;if(recorder.state==='recording')recorder.stop();},3000);}); const blob=await stopped; if(recordingTimeout){clearTimeout(recordingTimeout);recordingTimeout=null;} if(activeRecorder===recorder)activeRecorder=null; stopStream(); if(attempt!==speechGeneration)return; const form=new FormData();form.append('audio',blob,'lesson28-activity1.webm');form.append('target_text',item.word);form.append('language','English');form.append('mode','reading');const response=await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form}),result=await response.json();if(attempt!==speechGeneration)return;if(!response.ok||!result.success)throw new Error(result.error||'Speech recognition failed. Try again.');const transcript=String(result.raw_transcript||result.transcript||'');const saved=await post(data.progress_url,{action:'oral_read',item_index:state.current_item,success:normalize(transcript).includes(normalize(item.word))});if(attempt!==speechGeneration)return;const correct=saved.progress?.state?.phase==='letter';busy=false;render(correct?'Correct! Now write the missing letter.':`I heard “${transcript}”. Try again.`,correct?'good':'bad');if(attempt===speechGeneration)await playAudio(correct?READ_CORRECT_FEEDBACK:RETRY_FEEDBACK); } catch(error){if(attempt===speechGeneration){stopStream();busy=false;render(error.message||'I could not hear you. Try again.','bad');}} finally{if(attempt===speechGeneration){speechAttemptActive=false;if(button?.isConnected)button.classList.remove('is-busy');busy=false;}} }
  async function submitLetter(item) { if(busy)return; const input=document.getElementById('letter'), letter=normalize(input?.value); if(letter.length!==1){render('Type one missing letter, then check your answer.','bad');return;} busy=true;try{const result=await post(data.progress_url,{action:'letter_answer',letter});busy=false;render(result.accepted?'Correct!':'That letter is incorrect. Try again.',result.accepted?'good':'bad');await playAudio(result.accepted?(state.phase==='complete'?COMPLETION_FEEDBACK:LETTER_CORRECT_FEEDBACK):RETRY_FEEDBACK);}catch(error){busy=false;render(error.message,'bad');}finally{busy=false;} }
  function applyMuteToStream(){stream?.getAudioTracks().forEach(track=>{track.enabled=!isMuted;});}
  function cancelSpeechAttempt(){speechGeneration+=1;if(recordingTimeout){clearTimeout(recordingTimeout);recordingTimeout=null;}const recorder=activeRecorder;activeRecorder=null;if(recorder&&recorder.state!=='inactive'){try{recorder.stop();}catch(_){}}stopStream();speechAttemptActive=false;busy=false;document.getElementById('read')?.classList.remove('is-busy');}
  function stopStream(){stream?.getTracks().forEach(track=>track.stop());stream=null;}
  async function reset(event){event.preventDefault();if(busy)return;cancelSpeechAttempt();busy=true;try{await post(data.progress_url,{reset:true});window.location.reload();}catch(error){busy=false;window.alert(error.message||'Could not reset the activity.');}}
  document.getElementById('lesson28a1-later').addEventListener('click',reset);document.getElementById('lesson28a1-go').addEventListener('click',async()=>{document.getElementById('lesson28a1-start').hidden=true;document.getElementById('lesson28a1-stage').classList.remove('waiting');try{await playAudio('Missing Letter. Read the word, then write the missing letter.');}catch(error){render(error.message,'bad');}});window.addEventListener('pagehide',()=>{stopStream();audio?.pause();});hydrate();render();
})();
