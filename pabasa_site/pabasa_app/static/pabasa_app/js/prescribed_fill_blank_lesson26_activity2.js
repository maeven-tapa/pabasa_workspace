(() => {
  'use strict';
  const dataNode = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!dataNode || !app) return;
  const data = JSON.parse(dataNode.textContent || '{}');
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const normalize = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
  let state = {...(data.progress?.state || {})};
  let busy = false;
  let selectedWord = '';
  let stream = null;
  let activeAudio = null;
  let audioUrl = null;
  let started = false;
  let isPaused = false, isMuted = false, activeRecorder = null, activeRecordingTimer = null, activeSpeechButton = null, activeSpeechIdleLabel = '', generation = 0;
  const debugState = {status:'Ready', transcript:'No transcript yet.', expected:'—', normalized:'—', result:'—', mic:'Inactive · Unmuted', recorder:'inactive', vad:'Not available', error:'—', raw:['Waiting for speech...']};
  const publishDebug = (patch = {}, line) => { Object.assign(debugState, patch); if (line) debugState.raw = [...debugState.raw, line].slice(-6); window.dispatchEvent(new CustomEvent('prescribed-l26a2-debug-state', {detail:{...debugState, raw:[...debugState.raw]}})); };
  window.PrescribedLesson26Debug = {getState:() => ({...debugState, raw:[...debugState.raw]}), reset:() => {debugState.transcript='No transcript yet.';debugState.expected='—';debugState.normalized='—';debugState.result='—';debugState.error='—';debugState.recorder='inactive';debugState.mic='Inactive · Unmuted';debugState.raw=['Waiting for speech...'];publishDebug({status:'Ready'},'Activity reset');}};
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const CHOICE_CORRECT_FEEDBACK = "That's right, now let's read the next word.";
  const SENTENCE_CORRECT_FEEDBACK = "That's right, now let's choose the words.";
  const WORD_CORRECT_FEEDBACK = "That's right, now let's choose the next word.";
  const READ_SENTENCE_FEEDBACK = "That's right, now let's read the whole sentence.";
  const COMPLETION_FEEDBACK = 'Great job! You completed the activity.';
  const localAudioBase = '/static/pabasa_app/prescribed/audio/SESSION_10/LESSON_26/GAWAIN_2/';

  function localAudioKey(value) {
    return String(value || '').trim().toLowerCase()
      .replace(/[’']/g, "'").replace(/[.!?]+$/, '');
  }

  const localAudioFiles = {
    [localAudioKey('Fill in the Blanks. Read the words, then fill in the blanks.')]: 'Fill in the Blanks. Read the words, then fill in the blanks..mp3',
    hat: 'Hat.mp3',
    cat: 'Cat.mp3',
    rat: 'Rat.mp3',
    mat: 'Mat.mp3',
    [localAudioKey(RETRY_FEEDBACK)]: 'Hmm, let’s try that again..mp3',
    [localAudioKey(CHOICE_CORRECT_FEEDBACK)]: 'That’s right, now let’s read the next word..mp3',
    [localAudioKey(SENTENCE_CORRECT_FEEDBACK)]: 'That’s right, now let’s choose the words..mp3',
    [localAudioKey(WORD_CORRECT_FEEDBACK)]: 'That’s right, now let’s choose the next word..mp3',
    [localAudioKey(READ_SENTENCE_FEEDBACK)]: 'That’s right, now let’s read the whole sentence..mp3',
    [localAudioKey('The furry blank on the warm blank.')]: 'The furry blank on the warm blank..mp3',
    [localAudioKey('The furry cat on the warm mat.')]: 'The furry cat on the warm mat..mp3',
    [localAudioKey('The blank fell off her head.')]: 'The blank fell off her head..mp3',
    [localAudioKey('The hat fell off her head.')]: 'The hat fell off her head..mp3',
    [localAudioKey('The blank ate the blank.')]: 'The blank ate the blank..mp3',
    [localAudioKey('The rat ate the hat.')]: 'The rat ate the hat..mp3',
    [localAudioKey('The blank was placed on the top of the shelf.')]: 'The blank was placed on the top of the shelf..mp3',
    [localAudioKey('The hat was placed on the top of the shelf.')]: 'The hat was placed on the top of the shelf..mp3',
    [localAudioKey(COMPLETION_FEEDBACK)]: 'Great job! You completed the Fill in the Blanks..mp3',
  };

  function hydrate() {
    state.phase ||= 'choices';
    state.choice_index = Number(state.choice_index || 0);
    state.current_item = Number(state.current_item || 0);
    state.completed_items = Number(state.completed_items || 0);
    state.placements ||= {};
    state.sentence_read = Boolean(state.sentence_read);
  }
  async function save(payload) {
    const response = await fetch(data.progress_url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save your progress.');
    if (result.progress?.state) state = {...result.progress.state};
    hydrate();
    return result;
  }
  function steps() {
    const total = data.items.length;
    const current = state.phase === 'choices' ? Math.min(state.choice_index, total - 1) : state.completed_items;
    const finished = state.phase === 'complete' ? total : current;
    return `<div class="lesson26-progress" aria-label="Activity progress">${data.items.map((_, i) => `<span class="lesson26-step ${i < finished ? 'done' : ''} ${i === current && state.phase !== 'complete' ? 'active' : ''}" ${i === current && state.phase !== 'complete' ? 'aria-current="step"' : ''}>${i + 1}</span>`).join('')}</div>`;
  }
  function shell(title, instruction, body) {
    app.innerHTML = `<div class="eyebrow">SESSION 10 · LESSON 26 · ACTIVITY 2</div><h1 class="title">${escapeHtml(title)}</h1><p class="instruction">${escapeHtml(instruction)}</p>${body}${steps()}`;
  }
  function render() {
    hydrate();
    if (state.phase === 'complete') {
      window.PrescribedLessonUi.showCompletion(app);
      return;
    }
    if (state.phase === 'choices') renderChoices();
    else renderSentence();
  }
  function renderChoices(message = '', kind = '') {
    const word = data.choices[state.choice_index] || '';
    publishDebug({expected:word || '—',status:isPaused?'Paused':'Ready'});
    const canListen = Boolean(state.choice_help || state.choice_attempts >= 3);
    const body = `<div class="lesson26-content"><div class="label">Read the word aloud</div><div class="word">${escapeHtml(word || 'Great job!')}</div>${word ? `<div class="actions"><button class="button" id="read" type="button">🎙️ Read the word</button><button class="button secondary" id="listen" type="button" ${canListen ? '' : 'disabled'}>🔊 Listen</button></div>` : ''}<div class="word-bank">${data.choices.map((choice, i) => `<span class="word-chip ${i < state.choice_index ? 'word-chip-done' : ''} ${i === state.choice_index ? 'word-chip-active' : ''}">${escapeHtml(choice)}</span>`).join('')}</div></div>`;
    shell('Fill in the Blanks', 'Read the words, then fill in the blanks.', body);
    document.getElementById('read')?.addEventListener('click', () => recordWord(word, state.choice_index));
    document.getElementById('listen')?.addEventListener('click', () => playTts(word).catch(error => renderChoices(error.message || 'Could not play the word. Try again.','bad')));
  }

  async function announce(text) {
    busy = false;
    try { await playTts(text); } catch (error) { console.error('Lesson 26 Activity 2 feedback audio failed', error); }
  }
  async function recordWord(word, index) {
    if (busy || isPaused) return;
    busy = true;
    const status = document.getElementById('status');
    const button = document.getElementById('read');
    activeSpeechButton = button;
    activeSpeechIdleLabel = '🎙️ Read the word';
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; return;
    }
    button.textContent = 'Listening…'; if (status) status.textContent = 'Listening…';
    try {
      const attempt = generation; stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}}); stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; });
      activeRecorder = new MediaRecorder(stream); const recorder = activeRecorder, chunks = [];
      publishDebug({status:'Recording', expected:word, mic:`Active · ${isMuted?'Muted':'Unmuted'}`, recorder:recorder.state}, 'Recording started');
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => {
        recorder.onerror = () => reject(new Error('Could not record your voice. Try again.'));
        recorder.onstop = () => { if (activeRecordingTimer) { window.clearTimeout(activeRecordingTimer); activeRecordingTimer = null; } resolve(new Blob(chunks, {type:recorder.mimeType || 'audio/webm'})); };
        recorder.start(); activeRecordingTimer = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 3000);
      });
      const audio = await stopped; activeRecorder = null; stopStream(); if (attempt !== generation || isPaused) return;
      const form = new FormData(); form.append('audio', audio, 'lesson26-activity2-word.webm'); form.append('target_text', word); form.append('language', 'English'); form.append('mode', 'reading');
      const response = await fetch(data.transcribe_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await response.json();
      if (attempt !== generation || isPaused) return;
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const rawTranscript = String(result.raw_transcript || result.transcript || ''); const transcript = rawTranscript.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z]+/g) || [];
      const target = normalize(word), accepted = ({mat:['mat','math'],hat:['hat','hot'],wore:['wore','war'],bat:['bat','butt'],loved:['loved','love']})[target] || [target];
      const correct = transcript.some(token => accepted.includes(normalize(token)));
      publishDebug({status:'Processing', transcript:rawTranscript || 'No transcript returned.', normalized:transcript.join(' '), result:correct?'Match':'Not Match', recorder:'inactive'}, `Transcript: ${rawTranscript || '(empty)'}`);
      const saved = await save({action:'choice_read',choice_index:index,success:correct});
      if (saved.progress?.state) state = {...saved.progress.state};
      if (state.phase === 'sentence') {
        started = false;
        await announce(correct ? SENTENCE_CORRECT_FEEDBACK : RETRY_FEEDBACK);
        render();
        if (correct) { started = true; await playSentence(); }
      } else {
        if (correct) await announce(CHOICE_CORRECT_FEEDBACK);
        renderChoices(correct ? 'Correct! Read the next word.' : transcript.length ? `I heard “${result.raw_transcript || result.transcript}”. Try “${word}” again.` : `I could not hear “${word}” clearly. Try again.`, correct ? 'good' : 'bad');
        if (!correct) await announce(RETRY_FEEDBACK);
      }
    } catch (error) { stopStream(); renderChoices(error.message || 'Could not recognize your speech. Try again.', 'bad'); }
    finally { button?.classList.remove('is-busy'); if (activeSpeechButton === button) { activeSpeechButton = null; activeSpeechIdleLabel = ''; } busy = false; }
  }
  function sentenceText(item, blanks = true) {
    let blankIndex = 0;
    return item.parts.map((part, index) => {
      if (index >= item.blank_count) return part;
      const word = state.placements[String(blankIndex)] || (blanks ? 'blank' : ''); blankIndex += 1;
      return part + (word ? ` ${word} ` : ' ');
    }).join('').replace(/\s+([.,!?])/g, '$1').trim();
  }
  function sentenceAudioText(item) {
    let blankIndex = 0;
    return item.parts.map((part, index) => {
      if (index >= item.blank_count) return part;
      blankIndex += 1;
      return `${part} blank `;
    }).join('').replace(/\s+/g, ' ').replace(/\s+([.,!?])/g, '$1').trim();
  }
  function renderSentence(message = '', kind = '') {
    const item = data.items[state.current_item];
    if (!item) { state.phase = 'complete'; render(); return; }
    publishDebug({expected:sentenceText(item, false),status:isPaused?'Paused':'Ready'});
    let blankIndex = 0;
    const sentence = item.parts.map((part, index) => {
      if (index >= item.blank_count) return part;
      const n = blankIndex++, value = state.placements[String(n)];
      return `${part}<button type="button" class="blank ${value ? 'correct' : ''}" data-blank="${n}" aria-label="Blank ${n + 1}">${escapeHtml(value || 'Choose word')}</button>`;
    }).join('');
    const remaining = data.choices.filter(word => !Object.values(state.placements).includes(word));
    const sentenceComplete = Object.keys(state.placements).length === item.blank_count;
    const body = `<div class="lesson26-content"><p class="prompt">Listen to the sentence, then fill in each blank.</p><div class="actions"><button class="button secondary" id="listen" type="button">🔊 Listen to the sentence</button></div><div class="sentence">${sentence}</div><div class="word-bank">${remaining.map(word => `<button type="button" draggable="true" class="word-chip" data-word="${escapeHtml(word)}">${escapeHtml(word)}</button>`).join('')}</div>${sentenceComplete ? '<div class="actions"><button class="button" id="read-sentence" type="button">🎙️ Read the sentence</button></div>' : ''}</div>`;
    shell('Fill in the Blanks', 'Find the correct words and complete the sentence.', body);
    document.getElementById('listen').addEventListener('click', () => playSentence());
    document.getElementById('read-sentence')?.addEventListener('click', readSentence);
    app.querySelectorAll('[data-word]').forEach(button => {
      button.addEventListener('dragstart', event => event.dataTransfer.setData('text/plain', button.dataset.word));
      button.addEventListener('click', () => { selectedWord = button.dataset.word; app.querySelectorAll('[data-word]').forEach(el => el.classList.toggle('word-chip-active', el === button)); });
    });
    app.querySelectorAll('[data-blank]').forEach(blank => {
      blank.addEventListener('dragover', event => event.preventDefault());
      blank.addEventListener('drop', event => { event.preventDefault(); placeWord(Number(blank.dataset.blank), event.dataTransfer.getData('text/plain')); });
      blank.addEventListener('click', () => { if (selectedWord) placeWord(Number(blank.dataset.blank), selectedWord); });
    });
    if (!state.sentence_read && started) window.setTimeout(playSentence, 250);
  }
  async function playSentence() {
    const item = data.items[state.current_item];
    if (!item) return;
    const text = sentenceAudioText(item);
    try {
      await playTts(text);
      if (!state.sentence_read) { await save({action:'sentence_read'}); renderSentence(); }
    } catch (error) { renderSentence(error.message || 'Could not play the sentence. Try again.', 'bad'); }
  }
  async function playTts(text) {
    if (busy || !text) return;
    if (text === COMPLETION_FEEDBACK && !app.querySelector('.pabasa-completion-card')) return;
    busy = true;
    const buttons = [...app.querySelectorAll('.button')];
    const buttonStates = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    const status = document.getElementById('status'), previousStatus = status?.textContent; if (status) status.textContent = 'Playing audio…';
    try {
      const filename = localAudioFiles[localAudioKey(text)];
      if (!filename) throw new Error('Could not find the audio for this activity.');
      activeAudio = new Audio(`${localAudioBase}${filename.split('/').map(encodeURIComponent).join('/')}`);
      await new Promise((resolve, reject) => {
        activeAudio.addEventListener('ended', resolve, {once:true});
        activeAudio.addEventListener('error', () => reject(new Error('Audio playback failed. Try again.')), {once:true});
        activeAudio.play().catch(reject);
      });
    } finally {
      busy = false;
      buttonStates.forEach(({button, disabled}) => { if (button.isConnected) button.disabled = disabled; });
      buttons.forEach(button => { if (button.isConnected) button.classList.remove('is-busy'); });
      if (status?.isConnected && status.textContent === 'Playing audio…') status.textContent = previousStatus;
      if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
      activeAudio = null;
    }
  }
  async function placeWord(blankIndex, word) {
    if (busy || !word || !state.sentence_read) return;
    busy = true;
    try {
      const result = await save({action:'place_word',item_index:state.current_item,blank_index:blankIndex,word});
      selectedWord = '';
      if (!result.accepted) { renderSentence('That is not the correct word. Try another one.', 'bad'); await announce(RETRY_FEEDBACK); return; }
      state = {...result.progress.state};
      if (result.sentence_complete) { await announce(READ_SENTENCE_FEEDBACK); renderSentence(); }
      else { await announce(WORD_CORRECT_FEEDBACK); renderSentence(); }
    } catch (error) { renderSentence(error.message || 'Could not save your answer. Try again.','bad'); }
    finally { busy = false; }
  }
  async function readSentence() {
    if (busy || isPaused) return;
    busy = true;
    const item = data.items[state.current_item], target = sentenceText(item, false);
    const button = document.getElementById('read-sentence'), status = document.getElementById('status');
    activeSpeechButton = button;
    activeSpeechIdleLabel = '🎙️ Read the sentence';
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; return; }
    button.textContent = 'Listening…';
    try {
      const attempt = generation; stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}}); stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; });
      activeRecorder = new MediaRecorder(stream); const recorder = activeRecorder, chunks = [];
      publishDebug({status:'Recording', expected:target, mic:`Active · ${isMuted?'Muted':'Unmuted'}`, recorder:recorder.state}, 'Recording started');
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => { recorder.onerror = () => reject(new Error('Could not record your voice.')); recorder.onstop = () => { if (activeRecordingTimer) { window.clearTimeout(activeRecordingTimer); activeRecordingTimer = null; } resolve(new Blob(chunks,{type:recorder.mimeType || 'audio/webm'})); }; recorder.start(); activeRecordingTimer = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 4500); });
      const audio = await stopped; activeRecorder = null; stopStream(); if (attempt !== generation || isPaused) return;
      const form = new FormData(); form.append('audio',audio,'lesson26-activity2-sentence.webm'); form.append('target_text',target); form.append('language','English'); form.append('mode','reading');
      const response = await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form}), result = await response.json();
      if (attempt !== generation || isPaused) return;
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const spokenText = String(result.raw_transcript || result.transcript || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\bhot\b/g, 'hat');
      const transcript = normalize(spokenText), correct = sentenceReadMatches(target, spokenText);
      publishDebug({status:'Processing', transcript:result.raw_transcript || result.transcript || 'No transcript returned.', normalized:transcript, result:correct?'Match':'Not Match', recorder:'inactive'}, `Transcript: ${result.raw_transcript || result.transcript || '(empty)'}`);
      await save({action:'sentence_reading',success:correct});
      if (correct && state.phase === 'complete') {
        const completed = await fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'});
        const payload = await completed.json(); if (!completed.ok || !payload.success) throw new Error(payload.error || 'Could not save completion.');
      }
      started = false;
      if (correct) {
        render();
        const completionCard = app.querySelector('.pabasa-completion-card');
        if (state.phase === 'complete' && completionCard) {
          await new Promise(resolve => window.setTimeout(resolve, 0));
          await announce(COMPLETION_FEEDBACK);
        } else {
          await announce("That's right, now let's read the next sentence.");
        }
      } else {
        renderSentence(transcript ? `I heard “${result.raw_transcript || result.transcript}”. Please read the sentence again.` : 'I could not hear the sentence clearly. Try again.', 'bad');
        await announce(RETRY_FEEDBACK);
      }
      if (correct && state.phase !== 'complete') { started = true; await playSentence(); }
    } catch (error) { stopStream(); renderSentence(error.message || 'Could not recognize your speech. Try again.','bad'); }
    finally { button?.classList.remove('is-busy'); if (activeSpeechButton === button) { activeSpeechButton = null; activeSpeechIdleLabel = ''; } busy = false; }
  }
  function sentenceReadMatches(target, transcript) {
    const expectedWords = String(target || '').toLowerCase().match(/[a-z]+/g) || [];
    const spokenWords = String(transcript || '').toLowerCase().match(/[a-z]+/g) || [];
    if (!expectedWords.length || !spokenWords.length) return false;
    let spokenIndex = 0, matched = 0;
    for (const expected of expectedWords) {
      const found = spokenWords.slice(spokenIndex).findIndex(word => word === expected || (expected === 'hat' && ['hot', 'had'].includes(word)));
      if (found < 0) continue;
      matched += 1;
      spokenIndex += found + 1;
    }
    return matched >= Math.max(1, Math.ceil(expectedWords.length * 0.75));
  }
  function stopStream() { stream?.getTracks().forEach(track => track.stop()); stream = null; publishDebug({mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`,recorder:'inactive'}); }
  function resetSpeechInteraction() {
    if (activeRecordingTimer) { window.clearTimeout(activeRecordingTimer); activeRecordingTimer = null; }
    activeSpeechButton?.classList.remove('is-busy');
    if (activeSpeechButton?.isConnected && activeSpeechIdleLabel) activeSpeechButton.textContent = activeSpeechIdleLabel;
    activeSpeechButton = null;
    activeSpeechIdleLabel = '';
    if (activeRecorder?.state === 'recording' || activeRecorder?.state === 'paused') {
      try { activeRecorder.stop(); } catch (_) { /* The recorder cleanup remains idempotent. */ }
    }
    activeRecorder = null;
    stopStream();
  }
  window.PrescribedLesson26Activity = {
    pause() { isPaused = true; generation += 1; activeAudio?.pause(); resetSpeechInteraction(); publishDebug({status:'Paused',mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`,recorder:'inactive'},'Activity paused'); },
    resume() { isPaused = false; publishDebug({status:'Ready'},'Activity resumed'); },
    setMuted(value) { isMuted = Boolean(value); stream?.getAudioTracks().forEach(track => { track.enabled = !isMuted; }); publishDebug({mic:`${stream?'Active':'Inactive'} · ${isMuted?'Muted':'Unmuted'}`,status:isMuted?'Muted':(isPaused?'Paused':'Ready')}, isMuted?'Microphone muted':'Microphone unmuted'); },
    async restart() { generation += 1; isPaused = true; busy = false; resetSpeechInteraction(); activeAudio?.pause(); await resetAndExit({preventDefault(){},currentTarget:{disabled:false}}); },
    cleanup() { generation += 1; resetSpeechInteraction(); activeAudio?.pause(); activeAudio = null; },
    isPaused:() => isPaused,
  };
  async function resetAndExit(event) {
    event.preventDefault(); if (busy) return;
    const button = event.currentTarget; busy = true; button.disabled = true;
    try {
      const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({reset:true})});
      const result = await response.json(); if (!response.ok || !result.success) throw new Error(result.error || 'Could not reset the activity. Try again.');
      window.location.reload();
    } catch (error) { busy = false; button.disabled = false; window.alert(error.message || 'Could not reset the activity. Try again.'); }
  }

  document.getElementById('lesson26-later-button')?.addEventListener('click',resetAndExit);
  document.getElementById('lesson26-start-button')?.addEventListener('click',() => {
    started = true;
    window.setTimeout(async () => {
      try { await playTts('Fill in the Blanks. Read the words, then fill in the blanks.'); }
      catch (error) { state.phase === 'sentence' ? renderSentence(error.message || 'Could not play the instruction. Try again.','bad') : renderChoices(error.message || 'Could not play the instruction. Try again.','bad'); return; }
      if (state.phase === 'sentence' && !state.sentence_read) await playSentence();
    },0);
  });
  window.addEventListener('pagehide', () => { stopStream(); activeAudio?.pause(); if (audioUrl) URL.revokeObjectURL(audioUrl); });
  hydrate(); render();
})();
