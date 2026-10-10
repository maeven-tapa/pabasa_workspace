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
  let pendingReadingSave = Promise.resolve();
  let unsavedReadingProgress = null;
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
  const CONTINUE_FEEDBACK = "Great! now let's read the rest of the sentence.";
  const SENTENCE_PAUSE_MS = 3000;
  const CHOICE_CORRECT_FEEDBACK = "That's right, now let's read the next word.";
  const SENTENCE_CORRECT_FEEDBACK = "That's right, now let's choose the words.";
  const WORD_CORRECT_FEEDBACK = "That's right, now let's choose the next word.";
  const READ_SENTENCE_FEEDBACK = "That's right, now let's read the whole sentence.";
  const NEXT_SENTENCE_FEEDBACK = "That's right, now let's read the next sentence.";
  const COMPLETION_FEEDBACK = 'Great job! You completed the activity.';
  const localAudioBase = '/static/pabasa_app/prescribed/audio/SESSION_10/LESSON_26/GAWAIN_2/';

  function localAudioKey(value) {
    return String(value || '').trim().toLowerCase()
      .replace(/[’']/g, "'").replace(/[.!?]+$/, '');
  }

  const localAudioFiles = {
    [localAudioKey('Fill in the Blanks. Read the words, then fill in the blanks.')]: 'Fill in the Blanks. Read the words, then fill in the blanks..mp3',
    [localAudioKey("Let's read the first word")]: "Let's read the first word..mp3",
    hat: 'Hat.mp3',
    cat: 'Cat.mp3',
    rat: 'Rat.mp3',
    mat: 'Mat.mp3',
    [localAudioKey(RETRY_FEEDBACK)]: 'Hmm, let’s try that again..mp3',
    [localAudioKey(CONTINUE_FEEDBACK)]: "Great! now let's read the rest of the sentence..mp3",
    [localAudioKey(CHOICE_CORRECT_FEEDBACK)]: 'That’s right, now let’s read the next word..mp3',
    [localAudioKey(SENTENCE_CORRECT_FEEDBACK)]: 'That’s right, now let’s choose the words..mp3',
    [localAudioKey(WORD_CORRECT_FEEDBACK)]: 'That’s right, now let’s choose the next word..mp3',
    [localAudioKey(READ_SENTENCE_FEEDBACK)]: 'That’s right, now let’s read the whole sentence..mp3',
    [localAudioKey(NEXT_SENTENCE_FEEDBACK)]: 'That’s right, now let’s read the next sentence..mp3',
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
  const sentenceAudioByItem = {
    'sentence-1': {blank: 'The furry blank on the warm blank..mp3', complete: 'The furry cat on the warm mat..mp3'},
    'sentence-2': {blank: 'The blank fell off her head..mp3', complete: 'The hat fell off her head..mp3'},
    'sentence-3': {blank: 'The blank ate the blank..mp3', complete: 'The rat ate the hat..mp3'},
    'sentence-4': {blank: 'The blank was placed on the top of the shelf..mp3', complete: 'The hat was placed on the top of the shelf..mp3'},
  };

  function hydrate() {
    state.phase ||= 'choices';
    state.choice_index = Number(state.choice_index || 0);
    state.current_item = Number(state.current_item || 0);
    state.completed_items = Number(state.completed_items || 0);
    state.placements ||= {};
    state.sentence_read = Boolean(state.sentence_read);
    state.sentence_syllable_index = Number(state.sentence_syllable_index || 0);
    state.sentence_word_index = Number(state.sentence_word_index || 0);
  }
  async function save(payload, isCurrent = () => true) {
    const response = await fetch(data.progress_url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save your progress.');
    if (!isCurrent()) return result;
    if (result.progress?.state) state = {...result.progress.state};
    hydrate();
    return result;
  }
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters['prescribed-l26a2'] = {
    async saveCurrentProgress() {
      try { await pendingReadingSave; }
      catch (error) { if (!unsavedReadingProgress) throw error; }
      if (unsavedReadingProgress) await saveReadingProgress(unsavedReadingProgress);
      return save({action:'state_sync'});
    },
    cleanup() {
      window.PrescribedLesson26Activity?.cleanup();
    },
  };
  function saveReadingProgress(payload, isCurrent = () => true) {
    // Keep the recognized cursor until it is saved, so Leave can retry a
    // transient failure without losing the learner's highlighted words.
    unsavedReadingProgress = payload;
    pendingReadingSave = save(payload, isCurrent).then(result => {
      if (unsavedReadingProgress === payload) unsavedReadingProgress = null;
      return result;
    });
    return pendingReadingSave;
  }
  function steps() {
    const total = data.items.length;
    const current = state.phase === 'choices' ? Math.min(state.choice_index, total - 1) : state.completed_items;
    const finished = state.phase === 'complete' ? total : current;
    return `<div class="lesson26-progress" aria-label="Activity progress">${data.items.map((_, i) => `<span class="lesson26-step ${i < finished ? 'done' : ''} ${i === current && state.phase !== 'complete' ? 'active' : ''}" ${i === current && state.phase !== 'complete' ? 'aria-current="step"' : ''}>${i + 1}</span>`).join('')}</div>`;
  }
  function shell(title, instruction, body) {
    app.innerHTML = `<div class="eyebrow">SESSION 10 · LESSON 26 · ACTIVITY 2</div><p class="instruction">${escapeHtml(instruction)}</p>${body}${steps()}`;
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
    const body = `<div class="lesson26-content"><div class="label">Read the word aloud</div><div class="word">${escapeHtml(word || 'Great job!')}</div>${word ? `<div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read" type="button">Read</button><button class="button secondary" id="listen" type="button" ${canListen ? '' : 'disabled'}>🔊 Listen</button></div>` : ''}<div class="word-bank">${data.choices.map((choice, i) => `<span class="word-chip ${i < state.choice_index ? 'word-chip-done' : ''} ${i === state.choice_index ? 'word-chip-active' : ''}">${escapeHtml(choice)}</span>`).join('')}</div></div>`;
    shell('Fill in the Blanks', 'Read the words, then fill in the blanks.', body);
    window.Basahin.bindActivity(document.getElementById('read'), () => recordWord(word, state.choice_index));
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
      if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; await announce(RETRY_FEEDBACK); return;
    }
    button.textContent = 'Listening…'; if (status) status.textContent = 'Listening…';
    try {
      const attempt = generation; const result = await window.Basahin.read({target_text:word, language:'English', mode:'reading', prescribed_activity_key:'lesson-26-gawain-2'}, {button:button, url:data.transcribe_url}); if (attempt !== generation || isPaused) return;
      const rawTranscript = String(result.raw_transcript || result.transcript || ''); const transcript = rawTranscript.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z]+/g) || [];
      const correct = result.complete === true;
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
    } catch (error) { if (error?.name === 'AbortError') return;  stopStream(); renderChoices(error.message || 'Could not recognize your speech. Try again.', 'bad'); await announce(RETRY_FEEDBACK); }
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
    const sentenceComplete = Object.keys(state.placements).length === item.blank_count;
    let wordIndex = 0;
    const readingWords = text => sentenceComplete ? String(text).replace(/\S+/g, word => {
      const index = wordIndex++;
      return `<span class="lesson26-reading-word ${index < state.sentence_word_index ? 'is-read' : 'is-unread'}" data-word-index="${index}" ${index === state.sentence_word_index ? 'aria-current="true"' : ''}>${escapeHtml(word)}</span>`;
    }) : escapeHtml(text);
    let blankIndex = 0;
    const sentence = item.parts.map((part, index) => {
      if (index >= item.blank_count) {
        // Sentence-final punctuation belongs to the preceding word, not a new cursor.
        return /^[.,!?]+$/.test(part.trim()) ? escapeHtml(part) : readingWords(part);
      }
      const n = blankIndex++, value = state.placements[String(n)];
      return `${readingWords(part)}<button type="button" class="blank ${value ? 'correct' : ''}" data-blank="${n}" aria-label="Blank ${n + 1}">${readingWords(value || 'Choose word')}</button>`;
    }).join('');
    const remaining = data.choices.filter(word => !Object.values(state.placements).includes(word));
    const body = `<div class="lesson26-content"><p class="prompt">Listen to the sentence, then fill in each blank.</p><div class="actions"><button class="button secondary" id="listen" type="button">🔊 Listen to the sentence</button></div><div class="sentence">${sentence}</div>${sentenceComplete ? '' : `<div class="word-bank">${remaining.map(word => `<button type="button" draggable="true" class="word-chip" data-word="${escapeHtml(word)}">${escapeHtml(word)}</button>`).join('')}</div>`}${sentenceComplete ? '<div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read-sentence" type="button">Read</button></div>' : ''}</div>`;
    shell('Fill in the Blanks', 'Find the correct words and complete the sentence.', body);
    if (sentenceComplete) highlightUnreadSentence();
    document.getElementById('listen').addEventListener('click', () => playSentence());
    window.Basahin.bindActivity(document.getElementById('read-sentence'), readSentence);
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
    if (busy || isPaused) return;
    const attempt = generation;
    const item = data.items[state.current_item];
    if (!item) return;
    const sentenceComplete = Object.keys(state.placements).length >= item.blank_count;
    const mappedAudio = sentenceAudioByItem[item.id];
    const fallbackText = sentenceComplete ? sentenceText(item, false) : sentenceAudioText(item);
    const fallbackFilename = localAudioFiles[localAudioKey(
      fallbackText.replace(/\s+/g, ' ').replace(/\s+([.,!?])/g, '$1').trim()
    )];
    const filename = mappedAudio?.[sentenceComplete ? 'complete' : 'blank'] || fallbackFilename;
    try {
      await playAudioFile(filename);
      if (attempt !== generation || isPaused) return;
      if (!state.sentence_read) { await save({action:'sentence_read'}); renderSentence(); }
    } catch (error) { renderSentence(error.message || 'Could not play the sentence. Try again.', 'bad'); }
  }
  async function playTts(text) {
    if (busy || !text) return;
    if (text === COMPLETION_FEEDBACK && !app.querySelector('.pabasa-completion-card')) return;
    const filename = localAudioFiles[localAudioKey(text)];
    if (!filename) throw new Error('Could not find the audio for this activity.');
    await playAudioFile(filename);
  }
  async function playAudioFile(filename) {
    if (busy || isPaused || !filename) return;
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
      activeAudio = null;
    }
    busy = true;
    const playbackGeneration = generation;
    const buttons = [...app.querySelectorAll('.button')];
    const buttonStates = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    const status = document.getElementById('status'), previousStatus = status?.textContent; if (status) status.textContent = 'Playing audio…';
    try {
      const audioVersion = filename === 'The furry cat on the warm mat..mp3' ? '?v=20260928-replaced-first-item-audio' : '';
      activeAudio = new Audio(`${localAudioBase}${filename.split('/').map(encodeURIComponent).join('/')}${audioVersion}`);
      if (filename === "Let's read the first word..mp3") activeAudio.volume = 0.5;
      await new Promise((resolve, reject) => {
        activeAudio.addEventListener('ended', resolve, {once:true});
        activeAudio.addEventListener('pause', resolve, {once:true});
        activeAudio.addEventListener('error', () => reject(new Error('Audio playback failed. Try again.')), {once:true});
        activeAudio.play().catch(reject);
      });
    } finally {
      busy = false;
      const playbackInterrupted = isPaused || playbackGeneration !== generation;
      buttonStates.forEach(({button, disabled}) => {
        if (!button.isConnected) return;
        button.disabled = playbackInterrupted && button.id === 'read-sentence' ? false : disabled;
      });
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
    if (isMuted) { publishDebug({status:'Muted',error:'Microphone is muted.'}); return; }
    const attempt = generation;
    busy = true;
    const item = data.items[state.current_item], target = sentenceText(item, false);
    const button = document.getElementById('read-sentence'), status = document.getElementById('status');
    activeSpeechButton = button;
    activeSpeechIdleLabel = '🎙️ Read the sentence';
    button?.classList.add('is-busy');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { if (status) status.textContent = 'Microphone recording is not available in this browser.'; button?.classList.remove('is-busy'); busy = false; await announce(RETRY_FEEDBACK); return; }
    button.textContent = 'Listening…';
    try {
      const result = await readSentenceWithProgress(target, button, attempt); if (attempt !== generation || isPaused) return;
      const spokenText = String(result.raw_transcript || result.transcript || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\bhot\b/g, 'hat');
      const transcript = normalize(spokenText), correct = result.complete === true;
      if (result.continue_prompt) {
        busy = false;
        renderSentence();
        publishDebug({status:'Continue reading',transcript:result.raw_transcript || result.transcript,normalized:transcript,result:'Read the rest of the sentence',error:'—'}, CONTINUE_FEEDBACK);
        await announce(CONTINUE_FEEDBACK);
        return;
      }
      publishDebug({status:'Processing', transcript:result.raw_transcript || result.transcript || 'No transcript returned.', normalized:transcript, result:correct?'Match':'Not Match', recorder:'inactive'}, `Transcript: ${result.raw_transcript || result.transcript || '(empty)'}`);
      await save({action:'sentence_reading',success:correct}, () => attempt === generation && !isPaused);
      if (attempt !== generation || isPaused) return;
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
          await announce(NEXT_SENTENCE_FEEDBACK);
        }
      } else {
        renderSentence(transcript ? `I heard “${result.raw_transcript || result.transcript}”. Please read the sentence again.` : 'I could not hear the sentence clearly. Try again.', 'bad');
        await announce(RETRY_FEEDBACK);
      }
      if (correct && state.phase !== 'complete') { started = true; await playSentence(); }
    } catch (error) { if (error?.name === 'AbortError' || attempt !== generation || isPaused) return; stopStream(); publishDebug({status:'Error',error:error.message || 'Recording/transcription error'}); renderSentence(error.message || 'Could not recognize your speech. Try again.','bad'); await announce(RETRY_FEEDBACK); }
    finally { button?.classList.remove('is-busy'); if (activeSpeechButton === button) { activeSpeechButton = null; activeSpeechIdleLabel = ''; } busy = false; }
  }

  function highlightSentenceReading(result) {
    const cursor = Math.max(state.sentence_syllable_index, Number(result.current_syllable_index) || 0);
    const previousWords = state.sentence_word_index;
    state.sentence_syllable_index = cursor;
    state.sentence_word_index = Math.max(previousWords, (result.word_syllable_ranges || []).filter(range => Number(range[1]) <= cursor).length);
    app.querySelectorAll('.lesson26-reading-word').forEach(word => {
      const index = Number(word.dataset.wordIndex);
      word.classList.toggle('is-read', index < state.sentence_word_index);
      word.classList.toggle('is-new-read', index >= previousWords && index < state.sentence_word_index);
      word.classList.toggle('is-unread', index >= state.sentence_word_index);
      if (index === state.sentence_word_index) word.setAttribute('aria-current', 'true');
      else word.removeAttribute('aria-current');
    });
    highlightUnreadSentence();
  }
  function highlightUnreadSentence() {
    const sentence = app.querySelector('.sentence');
    const previousUnread = sentence?.querySelector('.lesson26-unread');
    if (previousUnread) previousUnread.replaceWith(...previousUnread.childNodes);
    const firstUnread = sentence?.querySelector('.lesson26-reading-word.is-unread');
    if (!firstUnread) return;
    const range = document.createRange();
    // A filled blank contains its word span; include the whole button so the
    // range does not split it or disturb its existing click/drop handlers.
    range.setStartBefore(firstUnread.closest('.blank') || firstUnread);
    range.setEndAfter(sentence.lastChild);
    const unread = document.createElement('span');
    unread.className = 'lesson26-unread';
    range.surroundContents(unread);
  }
  async function readSentenceWithProgress(target, button, attempt) {
    const fields = {target_text:target, language:'English', mode:'sentence', prescribed_activity_key:'lesson-26-gawain-2', current_syllable_index:state.sentence_syllable_index};
    const isCurrent = () => attempt === generation && !isPaused;
    let finalResult, failure;
    const reader = window.Basahin.create({
      visualButton:button, url:data.transcribe_url, continuous:true, silenceMs:SENTENCE_PAUSE_MS,
      getFields:() => fields,
      onError:error => { failure = error; },
      async onResult(result) {
        if (!isCurrent()) return true;
        if (!String(result.transcript || '').trim()) throw new Error('No speech detected. Press Read to try again.');
        const previousCursor = fields.current_syllable_index;
        highlightSentenceReading(result);
        fields.current_syllable_index = state.sentence_syllable_index;
        if (fields.current_syllable_index > previousCursor || unsavedReadingProgress) {
          await saveReadingProgress({action:'sentence_progress',item_index:state.current_item,current_syllable_index:fields.current_syllable_index}, isCurrent);
        }
        if (!isCurrent()) return true;
        finalResult = {...result, continue_prompt:!result.complete && !result.reading_mismatch && fields.current_syllable_index > previousCursor};
        // Release the microphone before feedback, retaining the next-word cursor.
        return true;
      },
    });
    try {
      await reader.start();
      if (failure) {
        if (failure.name === 'NoSpeechError') failure.message = 'No speech detected. Press Read to try again.';
        if (failure.name === 'TimeoutError') failure.message = 'Speech processing timed out. Press Read to try again.';
        throw failure;
      }
      if (!isCurrent() || !finalResult) throw new DOMException('Reading cancelled.', 'AbortError');
      return finalResult;
    } finally { reader.destroy(); }
  }

  function stopStream() { window.Basahin?.cancelAll();  stream?.getTracks().forEach(track => track.stop()); stream = null; publishDebug({mic:`Inactive · ${isMuted?'Muted':'Unmuted'}`,recorder:'inactive'}); }
  function resetSpeechInteraction() { window.Basahin?.cancelAll();
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
    resume() { isPaused = false; busy = false; const readButton = document.getElementById('read-sentence'); if (readButton) { readButton.disabled = false; readButton.classList.remove('is-busy'); readButton.textContent = 'Read'; } publishDebug({status:'Ready'},'Activity resumed'); },
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
      if (state.phase === 'choices') await playTts("Let's read the first word");
      else if (state.phase === 'sentence' && !state.sentence_read) await playSentence();
    },0);
  });
  window.addEventListener('pagehide', () => { stopStream(); activeAudio?.pause(); if (audioUrl) URL.revokeObjectURL(audioUrl); });
  hydrate(); render();
})();
