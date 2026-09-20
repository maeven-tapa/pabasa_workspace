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
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const CHOICE_CORRECT_FEEDBACK = "That's right, now let's read the next word.";
  const SENTENCE_CORRECT_FEEDBACK = "That's right, now let's choose the words.";
  const WORD_CORRECT_FEEDBACK = "That's right, now let's choose the next word.";
  const READ_SENTENCE_FEEDBACK = "That's right, now let's read the whole sentence.";

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
      shell('Fill in the Blanks', 'Read each word, then fill in the blanks.', '<div class="lesson26-complete-message">🎉 Great job! You completed Activity 2.</div>');
      return;
    }
    if (state.phase === 'choices') renderChoices();
    else renderSentence();
  }
  function renderChoices(message = '', kind = '') {
    const word = data.choices[state.choice_index] || '';
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
    if (busy) return;
    busy = true;
    const status = document.getElementById('status');
    const button = document.getElementById('read');
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; return;
    }
    button.textContent = 'Listening…'; if (status) status.textContent = 'Listening…';
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      const recorder = new MediaRecorder(stream), chunks = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => {
        recorder.onerror = () => reject(new Error('Could not record your voice. Try again.'));
        recorder.onstop = () => resolve(new Blob(chunks, {type:recorder.mimeType || 'audio/webm'}));
        recorder.start(); window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 3000);
      });
      const audio = await stopped; stopStream();
      const form = new FormData(); form.append('audio', audio, 'lesson26-activity2-word.webm'); form.append('target_text', word); form.append('language', 'English'); form.append('mode', 'reading');
      const response = await fetch(data.transcribe_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const transcript = String(result.raw_transcript || result.transcript || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z]+/g) || [];
      const target = normalize(word), accepted = ({mat:['mat','math'],hat:['hat','hot'],wore:['wore','war'],bat:['bat','butt'],loved:['loved','love']})[target] || [target];
      const correct = transcript.some(token => accepted.includes(normalize(token)));
      const saved = await save({action:'choice_read',choice_index:index,success:correct});
      if (saved.progress?.state) state = {...saved.progress.state};
      if (state.phase === 'sentence') {
        started = false;
        render();
        await announce(correct ? SENTENCE_CORRECT_FEEDBACK : RETRY_FEEDBACK);
        if (correct) { started = true; await playSentence(); }
      } else {
        renderChoices(correct ? 'Correct! Read the next word.' : transcript.length ? `I heard “${result.raw_transcript || result.transcript}”. Try “${word}” again.` : `I could not hear “${word}” clearly. Try again.`, correct ? 'good' : 'bad');
        await announce(correct ? CHOICE_CORRECT_FEEDBACK : RETRY_FEEDBACK);
      }
    } catch (error) { stopStream(); renderChoices(error.message || 'Could not recognize your speech. Try again.', 'bad'); }
    finally { button?.classList.remove('is-busy'); busy = false; }
  }
  function sentenceText(item, blanks = true) {
    let blankIndex = 0;
    return item.parts.map((part, index) => {
      if (index >= item.blank_count) return part;
      const word = state.placements[String(blankIndex)] || (blanks ? 'blank' : ''); blankIndex += 1;
      return part + (word ? ` ${word} ` : ' ');
    }).join('').replace(/\s+([.,!?])/g, '$1').trim();
  }
  function renderSentence(message = '', kind = '') {
    const item = data.items[state.current_item];
    if (!item) { state.phase = 'complete'; render(); return; }
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
    const text = sentenceText(item);
    try {
      await playTts(text);
      if (!state.sentence_read) { await save({action:'sentence_read'}); renderSentence(); }
    } catch (error) { renderSentence(error.message || 'Could not play the sentence. Try again.', 'bad'); }
  }
  async function playTts(text) {
    if (busy || !text) return;
    busy = true;
    const buttons = [...app.querySelectorAll('.button')];
    const buttonStates = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    const status = document.getElementById('status'), previousStatus = status?.textContent; if (status) status.textContent = 'Playing audio…';
    try {
      const response = await fetch(data.read_aloud_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-26-gawain-2'})});
      const result = await response.json();
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio. Try again.');
      const bytes = Uint8Array.from(atob(result.audio_content), character => character.charCodeAt(0));
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'}));
      activeAudio = new Audio(audioUrl);
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
      if (result.sentence_complete) { renderSentence(); await announce(READ_SENTENCE_FEEDBACK); }
      else { renderSentence(); await announce(WORD_CORRECT_FEEDBACK); }
    } catch (error) { renderSentence(error.message || 'Could not save your answer. Try again.','bad'); }
    finally { busy = false; }
  }
  async function readSentence() {
    if (busy) return;
    busy = true;
    const item = data.items[state.current_item], target = sentenceText(item, false);
    const button = document.getElementById('read-sentence'), status = document.getElementById('status');
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; return; }
    button.textContent = 'Listening…';
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      const recorder = new MediaRecorder(stream), chunks = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => { recorder.onerror = () => reject(new Error('Could not record your voice.')); recorder.onstop = () => resolve(new Blob(chunks,{type:recorder.mimeType || 'audio/webm'})); recorder.start(); window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 4500); });
      const audio = await stopped; stopStream();
      const form = new FormData(); form.append('audio',audio,'lesson26-activity2-sentence.webm'); form.append('target_text',target); form.append('language','English'); form.append('mode','reading');
      const response = await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form}), result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const spokenText = String(result.raw_transcript || result.transcript || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\bhot\b/g, 'hat');
      const transcript = normalize(spokenText), correct = sentenceReadMatches(target, spokenText);
      await save({action:'sentence_reading',success:correct});
      if (correct && state.phase === 'complete') {
        const completed = await fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'});
        const payload = await completed.json(); if (!completed.ok || !payload.success) throw new Error(payload.error || 'Could not save completion.');
      }
      started = false;
      if (correct) render();
      else renderSentence(transcript ? `I heard “${result.raw_transcript || result.transcript}”. Please read the sentence again.` : 'I could not hear the sentence clearly. Try again.', 'bad');
      await announce(correct ? (state.phase === 'complete' ? 'Great job! You completed the activity.' : "That's right, now let's read the next sentence.") : RETRY_FEEDBACK);
      if (correct && state.phase !== 'complete') { started = true; await playSentence(); }
    } catch (error) { stopStream(); renderSentence(error.message || 'Could not recognize your speech. Try again.','bad'); }
    finally { button?.classList.remove('is-busy'); busy = false; }
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
  function stopStream() { stream?.getTracks().forEach(track => track.stop()); stream = null; }
  async function resetAndExit(event) {
    event.preventDefault(); if (busy) return;
    const button = event.currentTarget; busy = true; button.disabled = true;
    try {
      const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({reset:true})});
      const result = await response.json(); if (!response.ok || !result.success) throw new Error(result.error || 'Could not reset the activity. Try again.');
      window.location.assign(document.getElementById('lesson26-back').href);
    } catch (error) { busy = false; button.disabled = false; window.alert(error.message || 'Could not reset the activity. Try again.'); }
  }
  document.getElementById('lesson26-back')?.addEventListener('click',resetAndExit);
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
