(() => {
  'use strict';
  const dataNode = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!dataNode || !app) return;
  const data = JSON.parse(dataNode.textContent || '{}');
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const normalize = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
  const canonicalTranscript = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\bdanced\b/g, 'dance').replace(/\bjump\b/g, 'jumped').replace(/\bhot\b/g, 'hat').replace(/\bmath\b/g, 'mat').replace(/\bwar\b/g, 'wore').replace(/\bbutt\b/g, 'bat').replace(/\bbath\b/g, 'bat').replace(/\bbut\b/g, 'bat').replace(/\bquiet\b/g, 'quite').replace(/\blaugh\b/g, 'laughed').replace(/\blove\b/g, 'loved');
  let state = {phase:'reading', item_index:0, verse_index:0, attempts:0, help_visible:false, selected:[], completed_items:0, ...(data.progress?.state || {})};
  let busy = false;
  let stream = null;
  let audio = null;
  let audioUrl = null;
  let isPaused = false;
  let isMuted = false;
  let activeRecorder = null;
  let recordingTimer = null;
  let activeSpeechButton = null;
  let generation = 0;
  const debugState = {status:'Ready', transcript:'No transcript yet.', expected:'—', normalized:'—', result:'—', mic:'Inactive · Unmuted', recorder:'inactive', vad:'Not available', error:'—', raw:['Activity ready']};
  const publishDebug = (patch = {}, line) => { Object.assign(debugState, patch); if (line) debugState.raw = [...debugState.raw, line].slice(-6); window.dispatchEvent(new CustomEvent('prescribed-l27a1-debug-state', {detail:{...debugState, raw:[...debugState.raw]}})); };
  window.PrescribedLesson27Debug = {getState:() => ({...debugState, raw:[...debugState.raw]}), reset:() => {Object.assign(debugState,{status:'Ready',transcript:'No transcript yet.',expected:'—',normalized:'—',result:'—',mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`,recorder:'inactive',vad:'Not available',error:'—',raw:['Activity reset']});publishDebug();}};
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const READ_CORRECT_FEEDBACK = "That's right, now let's read the next verse.";
  const RHYME_INSTRUCTION_FEEDBACK = "That's right, now choose the rhyming words.";
  const RHYME_CORRECT_FEEDBACK = "That's right, now let's read the next verse.";
  const COMPLETION_FEEDBACK = "Great job! You finished all the rhyming verses.";
  const localAudioBase = '/static/pabasa_app/prescribed/audio/SESSION_11/LESSON_27/GAWAIN_1/';

  function localAudioKey(value) {
    return String(value || '').trim().toLowerCase()
      .replace(/[’']/g, "'").replace(/[.!?]+$/, '');
  }

  const localAudioFiles = {
    [localAudioKey('Rhyming Verses. Read each verse, then select the words that rhyme with at.')]: 'Rhyming Verses. Read each verse, then select the words that rhyme with at..mp3',
    [localAudioKey('Click all the words that rhyme with at.')]: 'Click all the words that rhyme with at..mp3',
    [localAudioKey(RETRY_FEEDBACK)]: 'Hmm, let’s try that again..mp3',
    [localAudioKey(RHYME_INSTRUCTION_FEEDBACK)]: 'That’s right, now choose the rhyming words..mp3',
    [localAudioKey(RHYME_CORRECT_FEEDBACK)]: 'That’s right, now let’s read the next verse..mp3',
    [localAudioKey(COMPLETION_FEEDBACK)]: 'Great job! You completed the Rhyming Verses..mp3',
    [localAudioKey('The Cat in the Hat')]: 'The Cat in the Hat.mp3',
    [localAudioKey('The Funny Rat')]: 'The Funny Rat.mp3',
    [localAudioKey('Pat the Cat')]: 'Pat the Cat.mp3',
    [localAudioKey('The Splat')]: 'The Splat.mp3',
    [localAudioKey('The cat wore a hat,')]: 'The cat wore a hat,.mp3',
    [localAudioKey('He sat on a mat,')]: 'He sat on a mat,.mp3',
    [localAudioKey('Next to a big, fluffy rat,')]: 'Next to a big, fluffy rat,.mp3',
    [localAudioKey('Who loved to chat with a fat bat.')]: 'Who loved to chat with a fat bat..mp3',
    [localAudioKey('A little creature fell from the hat,')]: 'A little creature fell from the hat,.mp3',
    [localAudioKey('Danced with a playful bat,')]: 'Danced with a playful bat,.mp3',
    [localAudioKey('They jumped on a mat,')]: 'They jumped on a mat,.mp3',
    [localAudioKey('And both got quite fat!')]: 'And both got quite fat!.mp3',
    [localAudioKey('Upside down was the silly cat,')]: 'Upside down was the silly cat,.mp3',
    [localAudioKey('There was a loud splat on the mat,')]: 'There was a loud splat on the mat,.mp3',
    [localAudioKey('Who laughed at the splash with a gentle pat.')]: 'Who laughed at the splash with a gentle pat..mp3',
    [localAudioKey('On a sunny day, he’ll sit and sat,')]: 'On a sunny day, he’ll sit and sat,.mp3',
    [localAudioKey('He loves to play and chase his hat,')]: 'He loves to play and chase his hat,.mp3',
    [localAudioKey('Watching the world with a cheerful chat.')]: 'Watching the world with a cheerful chat..mp3',
    [localAudioKey('A silly little rat,')]: 'A silly little rat,.mp3',
  };

  function audioFilesFor(text) {
    const direct = localAudioFiles[localAudioKey(text)];
    if (direct) return [direct];
    const item = data.items[state.item_index];
    const lines = item?.lines || [];
    if (localAudioKey(lines.map(line => line.text).join(' ')) !== localAudioKey(text)) return [];
    return lines.map(line => localAudioFiles[localAudioKey(line.text)]).filter(Boolean);
  }

  async function responseJson(response, label) {
    const type = response.headers.get('content-type') || '';
    if (!type.includes('application/json')) {
      if (response.redirected) throw new Error('Your session may have expired. Refresh and sign in again.');
      throw new Error(`${label} returned an unexpected page (HTTP ${response.status}). Refresh and try again.`);
    }
    return response.json();
  }
  async function save(payload, isCurrent = () => true) {
    const response = await fetch(data.progress_url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(payload)});
    const result = await responseJson(response, 'Saving progress');
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');
    if (!isCurrent()) return {...result, stale: true};
    state = {...result.progress.state};
    return result;
  }
  function progressDots() {
    const complete = state.phase === 'complete';
    return `<div class="lesson27-progress" aria-label="Poem progress">${data.items.map((_, index) => `<span class="lesson27-step ${complete || index < state.item_index ? 'done' : ''} ${!complete && index === state.item_index ? 'active' : ''}" ${!complete && index === state.item_index ? 'aria-current="step"' : ''}>${index + 1}</span>`).join('')}</div>`;
  }
  function frame(body) {
    app.innerHTML = `<div class="lesson27-eyebrow">SESSION 11 · LESSON 27 · ACTIVITY 1</div><h1 class="lesson27-title">Rhyming Verses</h1><p class="lesson27-instruction">Read each verse, then select the words that rhyme with “at.”</p>${body}${progressDots()}`;
  }
  function renderLineWords(line, lineIndex) {
    let cursor = 0;
    const renderedWords = line.words.map(word => {
      const start = line.text.toLowerCase().indexOf(word.text.toLowerCase(), cursor);
      if (start < cursor) return `<button type="button" class="lesson27-word ${state.selected.includes(word.id) ? 'selected' : ''}" data-id="${esc(word.id)}" ${state.phase !== 'rhymes' ? 'disabled' : ''}>${esc(word.text)}</button> `;
      const separator = line.text.slice(cursor, start);
      cursor = start + word.text.length;
      return `${esc(separator)}<button type="button" class="lesson27-word ${state.selected.includes(word.id) ? 'selected' : ''}" data-id="${esc(word.id)}" ${state.phase !== 'rhymes' ? 'disabled' : ''}>${esc(word.text)}</button>`;
    }).join('');
    return renderedWords + esc(line.text.slice(cursor));
  }
  function render(message = '', type = '') {
    if (state.phase === 'complete') {
      window.PrescribedLessonUi.showCompletion(app);
      return;
    }
    const item = data.items[state.item_index];
    if (!item) { state.phase = 'complete'; render(); return; }
    const lines = item.lines.map((line, lineIndex) => {
      const words = renderLineWords(line, lineIndex);
      const status = state.phase === 'reading' && lineIndex < state.verse_index ? 'read' : state.phase === 'reading' && lineIndex === state.verse_index ? 'active' : '';
      return `<div class="lesson27-verse ${status}">${words}</div>`;
    }).join('');
    const activeVerse = item.lines[state.verse_index]?.text || '';
    publishDebug({expected:activeVerse || '—', status:isPaused ? 'Paused' : 'Ready'});
    let controls = '';
    if (state.phase === 'reading') {
      const canListen = Boolean(state.help_visible || state.attempts >= 3);
      controls = `<p class="lesson27-prompt">Read verse ${state.verse_index + 1} of ${item.lines.length} aloud.</p><div class="lesson27-actions"><button class="lesson27-button" id="record-verse" type="button">🎙️ Read the verse</button><button class="lesson27-button secondary" id="listen-verse" type="button" ${canListen ? '' : 'disabled'}>🔊 Listen</button></div>`;
    } else {
      controls = `<p class="lesson27-prompt">Click all the words that rhyme with “at.”</p><div class="lesson27-actions"><button class="lesson27-button secondary" id="listen-rhyme-directions" type="button">🔊 Listen to directions</button><button class="lesson27-button" id="listen-poem" type="button">🔊 Listen to the poem</button></div>`;
    }
    frame(`<div class="lesson27-content"><h2 class="lesson27-poem-title">${esc(item.title)}</h2><div class="lesson27-verses">${lines}</div>${controls}</div>`);
    document.getElementById('record-verse')?.addEventListener('click', () => recordVerse(activeVerse));
    document.getElementById('listen-verse')?.addEventListener('click', () => playAudio(activeVerse).catch(error => render(error.message, 'bad')));
    document.getElementById('listen-rhyme-directions')?.addEventListener('click', () => playAudio('Click all the words that rhyme with at.').catch(error => render(error.message, 'bad')));
    document.getElementById('listen-poem')?.addEventListener('click', () => playAudio(item.lines.map(line => line.text).join(' ')).catch(error => render(error.message, 'bad')));
    app.querySelectorAll('.lesson27-word:not(:disabled)').forEach(button => button.addEventListener('click', () => selectWord(button)));
  }
  async function playAudio(text) {
    if (busy || isPaused || !text) return;
    const attempt = generation;
    busy = true;
    const buttons = [...app.querySelectorAll('button')];
    const buttonStates = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    try {
      const filenames = audioFilesFor(text);
      if (!filenames.length) throw new Error('Could not find the audio for this activity.');
      for (const filename of filenames) {
        audio = new Audio(`${localAudioBase}${filename.split('/').map(encodeURIComponent).join('/')}`);
        await new Promise((resolve, reject) => {
          audio.addEventListener('ended', resolve, {once:true});
          audio.addEventListener('pause', resolve, {once:true});
          audio.addEventListener('error', () => reject(new Error('Audio playback failed. Try again.')), {once:true});
          audio.play().catch(reject);
        });
        if (attempt !== generation || isPaused) return;
      }
    } finally {
      busy = false;
      buttonStates.forEach(({button, disabled}) => { if (button.isConnected) button.disabled = disabled; });
      buttons.forEach(button => { if (button.isConnected) button.classList.remove('is-busy'); });
      audio = null;
      if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
    }
  }
  async function recordVerse(target) {
    if (busy || isPaused) return;
    if (isMuted) { render('Please unmute your microphone before reading.', 'bad'); publishDebug({status:'Muted',error:'Microphone is muted.'},'Reading blocked while muted'); return; }
    const attempt = generation;
    busy = true;
    const button = document.getElementById('record-verse');
    activeSpeechButton = button;
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { busy = false; return; }
    button.textContent = 'Listening…';
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; });
      activeRecorder = new MediaRecorder(stream); const recorder = activeRecorder, chunks = [];
      publishDebug({status:'Recording', transcript:'No transcript yet.', expected:target, mic:`Active · ${isMuted?'Muted':'Unmuted'}`, recorder:recorder.state, error:'—'},'Recording started');
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => { recorder.onerror = () => reject(new Error('Could not record your voice. Try again.')); recorder.onstop = () => { if (activeRecorder === recorder) activeRecorder = null; if (recordingTimer) { window.clearTimeout(recordingTimer); recordingTimer = null; } resolve(new Blob(chunks,{type:recorder.mimeType || 'audio/webm'})); }; recorder.start(); recordingTimer = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 4500); });
      const blob = await stopped; stopStream(); publishDebug({recorder:'inactive'},'Recording completed'); if (attempt !== generation || isPaused) return;
      const form = new FormData(); form.append('audio',blob,'lesson27-rhyming-verse.webm'); form.append('target_text',target); form.append('language','English'); form.append('mode','reading');
      const response = await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await responseJson(response, 'Speech recognition');
      if (attempt !== generation || isPaused) return;
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const heardText = result.raw_transcript || result.transcript;
      const expectedText = canonicalTranscript(target);
      const expectedHasHeLl = /\bhe(?:['’]?)ll\b/.test(expectedText);
      const spokenText = canonicalTranscript(heardText);
      const acceptedSpokenText = expectedHasHeLl ? spokenText.replace(/\bhill\b/g, "he'll") : spokenText;
      const spoken = normalize(acceptedSpokenText);
      const expected = normalize(expectedText);
      const spokenTokens = acceptedSpokenText.match(/[a-z]+/g) || [];
      const expectedTokens = expectedText.match(/[a-z]+/g) || [];
      const isPlayfulBatVerse = expectedTokens.includes('dance') && expectedTokens.includes('playful') && expectedTokens.includes('bat');
      const playfulBatHeard = spokenTokens.includes('bat') && (spokenTokens.includes('dance') || spokenTokens.includes('playful'));
      const correct = Boolean(expected && (spoken.includes(expected) || (isPlayfulBatVerse && playfulBatHeard)));
      publishDebug({status:'Processing',transcript:String(heardText || 'No transcript returned.'),normalized:spoken,result:correct?'Match':'Not Match'},`Transcription received: ${heardText || '(empty)'}`);
      if (attempt !== generation || isPaused) return;
      await save({action:'verse_read',item_index:state.item_index,verse_index:state.verse_index,success:correct}, () => attempt === generation && !isPaused);
      if (attempt !== generation || isPaused) return;
      busy = false;
      const correctFeedback = state.phase === 'rhymes' ? RHYME_INSTRUCTION_FEEDBACK : READ_CORRECT_FEEDBACK;
      render(correct ? correctFeedback : `I heard “${heardText || 'unclear speech'}”. ${RETRY_FEEDBACK}`, correct ? 'good' : 'bad');
      await playAudio(correct ? correctFeedback : RETRY_FEEDBACK);
    } catch (error) { stopStream(); if (attempt === generation && !isPaused) { publishDebug({status:'Error',error:error.message || 'Recording/transcription error'},`Error: ${error.message || 'Recording/transcription error'}`); render(error.message || 'Could not recognize your speech. Try again.','bad'); } }
    finally { button?.classList.remove('is-busy'); if (activeSpeechButton === button) activeSpeechButton = null; busy = false; }
  }
  async function selectWord(button) {
    if (busy || button.classList.contains('selected')) return;
    busy = true;
    try {
      const result = await save({action:'rhyme_select',token_id:button.dataset.id});
      if (!result.accepted) {
        button.classList.add('wrong');
        window.setTimeout(() => button.classList.remove('wrong'), 500);
        busy = false;
        render('That word does not rhyme with “at.”', 'bad');
        return;
      }
      if (state.phase === 'complete') {
        const response = await fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'});
        const payload = await responseJson(response, 'Saving completion');
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Could not save completion.');
      }
      const completedRhymeSelection = state.phase !== 'rhymes';
      const response = state.phase === 'complete' ? COMPLETION_FEEDBACK : RHYME_CORRECT_FEEDBACK;
      busy = false;
      render(completedRhymeSelection ? response : 'Correct selection. Keep finding the rhyming words.', completedRhymeSelection ? 'good' : '');
      if (completedRhymeSelection) await playAudio(response);
    } catch (error) { render(error.message || 'Could not save your selection. Try again.','bad'); }
    finally { busy = false; }
  }
  function stopStream() { if (recordingTimer) { window.clearTimeout(recordingTimer); recordingTimer = null; } stream?.getTracks().forEach(track => track.stop()); stream = null; publishDebug({mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`,recorder:'inactive'}); }
  function cancelSpeechAttempt() { generation += 1; if (recordingTimer) { window.clearTimeout(recordingTimer); recordingTimer = null; } if (activeRecorder?.state === 'recording' || activeRecorder?.state === 'paused') { try { activeRecorder.stop(); } catch (_) {} } activeRecorder = null; activeSpeechButton?.classList.remove('is-busy'); if (activeSpeechButton?.isConnected) activeSpeechButton.textContent = '🎙️ Read the verse'; activeSpeechButton = null; stopStream(); publishDebug({status:isPaused?'Paused':'Ready',recorder:'inactive',mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`},'Recording cancelled'); }
  window.PrescribedLesson27Activity = {
    pause() { if (isPaused) return; isPaused = true; cancelSpeechAttempt(); audio?.pause(); busy = false; publishDebug({status:'Paused'},'Activity paused'); },
    resume() { isPaused = false; publishDebug({status:'Ready',recorder:'inactive',mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`},'Activity resumed'); },
    setMuted(value) { isMuted = Boolean(value); stream?.getAudioTracks().forEach(track => { track.enabled = !isMuted; }); const button=document.getElementById('prescribed-l27a1-mic-toggle'); button?.setAttribute('aria-pressed',String(isMuted)); button?.setAttribute('aria-label',isMuted?'Unmute microphone':'Mute microphone'); button?.setAttribute('title',isMuted?'Unmute microphone':'Mute microphone'); button?.classList.toggle('is-muted',isMuted); if(button)button.innerHTML=`<i class="bi ${isMuted?'bi-mic-mute-fill':'bi-mic-fill'}" aria-hidden="true"></i>`; publishDebug({mic:`${stream?'Active':'Inactive'} · ${isMuted?'Muted':'Unmuted'}`,status:isMuted?'Muted':(isPaused?'Paused':'Ready')},isMuted?'Microphone muted':'Microphone unmuted'); },
    async restart() { isPaused = true; cancelSpeechAttempt(); audio?.pause(); busy = false; window.PrescribedLesson27Debug.reset(); await resetAndExit({preventDefault(){},currentTarget:{disabled:false}}); },
    cleanup() { isPaused = true; cancelSpeechAttempt(); audio?.pause(); audio = null; busy = false; },
    cancelSpeechAttempt,
    bindDebug() { const panel=document.getElementById('prescribed-l27a1-debug-panel'), toggle=document.getElementById('prescribed-l27a1-debug-toggle'), keys=['status','transcript','expected','normalized','result','mic','recorder','vad','error','raw']; const render=s=>{if(!s)return; panel.hidden=!toggle.checked; panel.setAttribute('aria-hidden',String(!toggle.checked)); keys.forEach(k=>{const el=document.getElementById(`prescribed-l27a1-debug-${k}`);if(el&&s[k]!==undefined)el.textContent=Array.isArray(s[k])?s[k].join('\n'):s[k]})}; toggle.checked=localStorage.getItem('pabasaShowSpeechDebugPanel')==='true'; toggle.addEventListener('change',()=>{localStorage.setItem('pabasaShowSpeechDebugPanel',String(toggle.checked));render(window.PrescribedLesson27Debug.getState())}); window.addEventListener('prescribed-l27a1-debug-state',e=>render(e.detail)); render(window.PrescribedLesson27Debug.getState()); },
    bindAudioTest() { const select=document.getElementById('prescribed-l27a1-device-select'), status=document.getElementById('prescribed-l27a1-settings-status'), fill=document.getElementById('prescribed-l27a1-level-fill'), test=document.getElementById('prescribed-l27a1-test-toggle'); let testStream=null, ctx=null, analyser=null, source=null, frame=0, active=false; const stop=()=>{active=false;if(frame)cancelAnimationFrame(frame);source?.disconnect();analyser?.disconnect();ctx?.close();source=analyser=ctx=null;testStream?.getTracks().forEach(t=>t.stop());testStream=null;if(fill)fill.style.width='0%';if(test)test.innerHTML='<i class="bi bi-mic-fill"></i> Start Test'}; const meter=()=>{if(!analyser)return;const values=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(values);let sum=0;for(const value of values){const n=(value-128)/128;sum+=n*n}fill.style.width=`${Math.min(100,Math.sqrt(sum/values.length)*260)}%`;frame=requestAnimationFrame(meter)}; const start=async()=>{try{const c=select.value?{audio:{deviceId:{exact:select.value}}}:{audio:true};testStream=await navigator.mediaDevices.getUserMedia(c);ctx=new AudioContext();analyser=ctx.createAnalyser();analyser.fftSize=512;source=ctx.createMediaStreamSource(testStream);source.connect(analyser);active=true;status.innerHTML='<strong>Microphone Status:</strong> Access granted. Testing live input.';test.innerHTML='<i class="bi bi-stop-fill"></i> Stop Test';meter()}catch(_){stop();status.innerHTML='<strong>Microphone Status:</strong> Access denied or unavailable.'}}; test?.addEventListener('click',()=>active?stop():start());select?.addEventListener('change',()=>{if(active){stop();start()}});document.getElementById('prescribed-l27a1-audio-close')?.addEventListener('click',stop);document.getElementById('prescribed-l27a1-audio-settings-modal')?.addEventListener('click',e=>{if(e.target===e.currentTarget)stop()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.getElementById('prescribed-l27a1-audio-settings-modal').hidden)stop()}); if(navigator.mediaDevices?.enumerateDevices)navigator.mediaDevices.enumerateDevices().then(ds=>{select.replaceChildren(new Option('Default microphone',''));ds.filter(d=>d.kind==='audioinput').forEach(d=>select.add(new Option(d.label||`Microphone ${select.options.length}`,d.deviceId)))}).catch(()=>{}); window.addEventListener('pagehide',stop); },
    isPaused:() => isPaused,
  };
  async function resetAndExit(event) {
    event.preventDefault(); if (busy) return;
    const button = event.currentTarget; busy = true; button.disabled = true;
    try {
      const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({reset:true})});
      const result = await responseJson(response, 'Resetting activity');
      if (!response.ok || !result.success) throw new Error(result.error || 'Could not reset the activity. Try again.');
      window.location.reload();
    } catch (error) { busy = false; button.disabled = false; window.alert(error.message || 'Could not reset the activity. Try again.'); }
  }

  window.PrescribedControls?.init({prefix:'prescribed-l27a1',adapter:window.PrescribedLesson27Activity});
  window.PrescribedLesson27Activity.setMuted(isMuted);
  document.getElementById('prescribed-l27a1-help-btn')?.addEventListener('click', () => window.PrescribedLesson27Activity.cancelSpeechAttempt());
  document.getElementById('lesson27-later-button')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson27-start-button')?.addEventListener('click', () => {
    window.setTimeout(() => playAudio('Rhyming Verses. Read each verse, then select the words that rhyme with at.').catch(error => render(error.message || 'Could not play the instructions. Try again.','bad')), 0);
  });
  window.addEventListener('pagehide', () => { stopStream(); audio?.pause(); if (audioUrl) URL.revokeObjectURL(audioUrl); });
  render();
})();
