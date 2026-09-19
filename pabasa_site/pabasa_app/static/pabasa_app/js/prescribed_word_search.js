(() => {
  'use strict';

  const dataNode = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!dataNode || !app) return;

  const data = JSON.parse(dataNode.textContent || '{}');
  const grid = data.grid || [];
  const words = data.words || [];
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const normalizedWord = value => String(value || '').toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');

  let savedState = data.progress?.state || {};
  let matches = data.progress?.matches || savedState.matches || {};
  let reading = savedState.reading || {};
  let attempts = savedState.attempts || {};
  let currentIndex = 0;
  let selectedCell = null;
  let busy = false;
  let activeStream = null;
  let instructionAudioUrl = null;
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const READING_CORRECT_FEEDBACK = "That's right, now let's find the word.";
  const GRID_CORRECT_FEEDBACK = "That's right, now let's read the next word.";

  async function save(payload) {
    const response = await fetch(data.progress_url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');
    if (result.progress?.state) {
      savedState = result.progress.state;
      reading = savedState.reading || reading;
      attempts = savedState.attempts || attempts;
    }
    if (result.progress?.matches) matches = result.progress.matches;
    return result;
  }

  function render(message = '', messageType = '') {
    const next = words.findIndex((_, index) => !matches[String(index)]);
    currentIndex = next < 0 ? words.length : next;
    const progress = `<div class="lesson26-progress" aria-label="Word progress">${words.map((_, index) => `<span class="lesson26-step ${matches[String(index)] ? 'done' : ''} ${index === currentIndex ? 'active' : ''}" ${index === currentIndex ? 'aria-current="step"' : ''}>${index + 1}</span>`).join('')}</div>`;
    if (currentIndex >= words.length) {
      app.innerHTML = `<div class="lesson26-complete-message">🎉 Great job! You completed the Word Search.</div>${progress}`;
      return;
    }
    const targetWord = words[currentIndex];
    const hasReadCorrectly = Boolean(reading[String(currentIndex)]);
    const readAttempts = Number(attempts[String(currentIndex)] || 0);
    const canListen = hasReadCorrectly || readAttempts >= 3;
    app.innerHTML = `<div class="eyebrow">SESSION ${escapeHtml(data.session_number)} · LESSON ${escapeHtml(data.lesson_number)} · ACTIVITY ${escapeHtml(data.gawain_number)}</div>
      <h1 class="title">Word Search</h1><p class="instruction">Find the words on the grid.</p>
      <div class="layout"><section class="word-panel"><div class="label">Read the word aloud first</div>
      <div class="word">${escapeHtml(targetWord)}</div>
      <div class="actions"><button class="button" id="read" type="button" ${hasReadCorrectly ? 'disabled' : ''}>🎙️ ${hasReadCorrectly ? 'Read the word again' : 'Read the word'}</button><button class="button secondary" id="listen-instructions" type="button" ${canListen ? '' : 'disabled'}>🔊 Listen</button></div></section>
      <section><div class="grid-wrap"><div class="grid">${grid.flatMap((row, rowIndex) => row.map((letter, columnIndex) => {
        const locked = !hasReadCorrectly || Boolean(matches[String(currentIndex)]);
        const match = matches[String(currentIndex)];
        const found = match && rowIndex >= Math.min(match.start[0], match.end[0]) && rowIndex <= Math.max(match.start[0], match.end[0])
          && columnIndex >= Math.min(match.start[1], match.end[1]) && columnIndex <= Math.max(match.start[1], match.end[1]);
        return `<button class="cell ${locked ? '' : ''} ${found ? 'found' : ''}" data-row="${rowIndex}" data-column="${columnIndex}" type="button" ${locked ? 'disabled' : ''}>${escapeHtml(letter)}</button>`;
      })).join('')}</div></div></section></div>${progress}`;
    app.querySelector('#read').addEventListener('click', readWord);
    app.querySelector('#listen-instructions')?.addEventListener('click', () => readAloud(targetWord));
    app.querySelectorAll('.cell:not(:disabled)').forEach(button => button.addEventListener('click', () => selectCell(button)));
  }

  async function playReadAloud(textToSpeak) {
    try {
      const response = await fetch(data.read_aloud_url, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({target_text: textToSpeak, language: 'English', lesson_tts_key: 'lesson-26-gawain-1'}),
      });
      const result = await response.json();
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play the audio. Please try again.');
      const bytes = Uint8Array.from(atob(result.audio_content), character => character.charCodeAt(0));
      if (instructionAudioUrl) URL.revokeObjectURL(instructionAudioUrl);
      instructionAudioUrl = URL.createObjectURL(new Blob([bytes], {type: result.mime_type || 'audio/mpeg'}));
      const audio = new Audio(instructionAudioUrl);
      await audio.play();
      await new Promise((resolve, reject) => {
        audio.addEventListener('ended', resolve, {once: true});
        audio.addEventListener('error', () => reject(new Error('Audio playback failed. Please try again.')), {once: true});
      });
      return true;
    } catch (error) {
      return false;
    } finally {
      if (instructionAudioUrl) { URL.revokeObjectURL(instructionAudioUrl); instructionAudioUrl = null; }
    }
  }

  async function readAloud(textToSpeak) {
    if (busy) return;
    busy = true;
    const buttons = app.querySelectorAll('#read, #listen-instructions');
    buttons.forEach(button => { button.disabled = true; });
    const played = await playReadAloud(textToSpeak);
    busy = false;
    render(played ? '' : 'Could not play the audio. Please try again.', played ? '' : 'bad');
  }

  async function readWord() {
    if (busy || currentIndex >= words.length) return;
    const wordIndex = currentIndex;
    const targetWord = words[wordIndex];
    const button = app.querySelector('#read');
    busy = true;
    button.disabled = true;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('Microphone recording is not available in this browser.');
      }
      activeStream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
      const recorder = new MediaRecorder(activeStream);
      const chunks = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const recording = new Promise((resolve, reject) => {
        recorder.onerror = () => reject(new Error('Could not record your voice. Please try again.'));
        recorder.onstop = () => resolve(new Blob(chunks, {type: recorder.mimeType || 'audio/webm'}));
        recorder.start();
        window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 3000);
      });
      const audio = await recording;
      stopStream();

      const form = new FormData();
      form.append('audio', audio, 'word-search-reading.webm');
      form.append('target_text', targetWord);
      form.append('language', 'English');
      form.append('mode', 'reading');
      const response = await fetch(data.transcribe_url, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form,
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Please try again.');

      const target = normalizedWord(targetWord);
      const transcript = String(result.raw_transcript || result.transcript || '').trim();
      const heardWords = transcript.toLowerCase().normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '').match(/[a-z]+/g) || [];
      // The API's `complete` flag is syllable-analyzer feedback, not the STT
      // transcript itself. For this single-word task, accept an exact spoken
      // word token and reject substring lookalikes such as “matter” for “mat”.
      const acceptedWords = ({mat:['mat','math'],hat:['hat','hot'],wore:['wore','war'],bat:['bat','butt'],loved:['loved','love']})[target] || [target];
      const saidTarget = heardWords.some(token => acceptedWords.includes(normalizedWord(token)));
      const saved = await save({word_index: wordIndex, reading_result: saidTarget});
      reading = saved.progress?.state?.reading || reading;
      attempts = saved.progress?.state?.attempts || attempts;
      render('', saidTarget ? 'good' : 'bad');
      await playReadAloud(saidTarget ? READING_CORRECT_FEEDBACK : RETRY_FEEDBACK);
    } catch (error) {
      stopStream();
      render(error.message || 'Could not recognize your speech. Please try again.', 'bad');
    } finally {
      busy = false;
    }
  }

  function stopStream() {
    activeStream?.getTracks().forEach(track => track.stop());
    activeStream = null;
  }

  async function selectCell(button) {
    if (busy) return;
    const point = [Number(button.dataset.row), Number(button.dataset.column)];
    if (selectedCell === null) {
      selectedCell = point;
      button.classList.add('selected');
      return;
    }
    const start = selectedCell;
    const end = point;
    selectedCell = null;
    busy = true;
    const result = await save({candidate_match: {word_index: currentIndex, start, end}}).catch(error => {
      render(error.message, 'bad');
      return null;
    });
    if (!result) { busy = false; return; }
    if (!result.accepted) {
      render('', 'bad');
      await playReadAloud(RETRY_FEEDBACK);
      busy = false;
      return;
    }
    matches = result.progress.matches;
    if (Object.keys(matches).length >= words.length) {
      try {
        const response = await fetch(data.completion_url, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: '{}',
        });
        const completed = await response.json();
        if (!response.ok || !completed.success) throw new Error(completed.error || 'Could not save completion.');
      } catch (error) {
        render(error.message, 'bad');
        await playReadAloud(error.message);
        busy = false;
        return;
      }
      render();
      await playReadAloud(GRID_CORRECT_FEEDBACK);
    } else {
      render('', 'good');
      await playReadAloud(GRID_CORRECT_FEEDBACK);
    }
    busy = false;
  }

  window.addEventListener('pagehide', stopStream);
  async function resetAndExit(event) {
    event.preventDefault();
    const button = event.currentTarget;
    if (busy) return;
    busy = true;
    button.disabled = true;
    try {
      const response = await fetch(data.progress_url, {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
        body: JSON.stringify({reset: true}),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Could not reset this activity. Please try again.');
      window.location.assign(document.getElementById('lesson26-back').href);
    } catch (error) {
      busy = false;
      button.disabled = false;
      window.alert(error.message || 'Could not reset this activity. Please try again.');
    }
  }
  document.getElementById('lesson26-back')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson26-later-button')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson26-start-button')?.addEventListener('click', () => {
    window.setTimeout(() => readAloud('Word Search. Find the words on the grid.'), 0);
  });
  render();
})();
