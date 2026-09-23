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
  let activeRecorder = null;
  let recordingCancelled = false;
  let activeAudio = null;
  let prescribedMicMuted = false;
  let selectedMicDeviceId = '';
  let vadFrame = null;
  let vadContext = null;
  let cancelVADMonitor = null;
  const debugState = {status: 'Ready', transcript: 'No transcript yet.', expected: '—', normalized: '—', result: '—', mic: 'Inactive · Unmuted', recorder: 'inactive', vad: 'waiting', error: '—', raw: 'Waiting for speech...'};
  function publishDebug(patch = {}, log = '') { Object.assign(debugState, patch); if (log) debugState.raw = [debugState.raw === 'Waiting for speech...' ? '' : debugState.raw, log].filter(Boolean).slice(-6).join('\n'); window.dispatchEvent(new CustomEvent('prescribed-l26a1-debug-state', {detail: {...debugState}})); }
  window.PrescribedLesson26Debug = {getState: () => ({...debugState}), reset: () => { Object.assign(debugState, {status: 'Ready', transcript: 'No transcript yet.', expected: '—', normalized: '—', result: '—', mic: `Inactive · ${prescribedMicMuted ? 'Muted' : 'Unmuted'}`, recorder: 'inactive', vad: 'waiting', error: '—', raw: 'Waiting for speech...'}); publishDebug(); }};
  let isActivityPaused = false;
  let pausedAudio = null;
  const VAD_CALIBRATION_MS = 800;
  const VAD_SILENCE_MS = 1000;
  const VAD_MAX_RECORDING_MS = 6000;
  const VAD_MIN_SPEECH_FRAMES = 3;
  const VAD_BASE_THRESHOLD = 0.014;
  const VAD_NOISE_MULTIPLIER = 3.2;
  const RETRY_FEEDBACK = "Hmm, let's try that again.";
  const READING_CORRECT_FEEDBACK = "That's right, now let's find the word.";
  const GRID_CORRECT_FEEDBACK = "That's right, now let's read the next word.";
  const COMPLETION_FEEDBACK = 'Great job! You completed the Word Search.';

  function pauseActivity() {
    if (isActivityPaused) return;
    isActivityPaused = true;
    if (activeRecorder?.state === 'recording') activeRecorder.pause();
    if (activeAudio && !activeAudio.paused) { pausedAudio = activeAudio; activeAudio.pause(); }
    publishDebug({status: 'Paused', recorder: activeRecorder?.state || 'inactive'});
    window.dispatchEvent(new CustomEvent('prescribed-l26a1-activity-paused'));
  }

  function resumeActivity() {
    if (!isActivityPaused) return;
    isActivityPaused = false;
    if (activeRecorder?.state === 'paused') activeRecorder.resume();
    if (pausedAudio) { pausedAudio.play().catch(() => {}); pausedAudio = null; }
    publishDebug({status: activeStream ? 'Listening' : 'Ready', recorder: activeRecorder?.state || 'inactive'});
    window.dispatchEvent(new CustomEvent('prescribed-l26a1-activity-resumed'));
  }

  function cleanupActivity() {
    isActivityPaused = true;
    pausedAudio = null;
    activeAudio?.pause();
    stopStream();
  }

  async function resetActivity() {
    cleanupActivity();
    const response = await fetch(data.progress_url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify({reset: true})});
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not restart this activity.');
    window.location.reload();
  }

  window.PrescribedLesson26Activity = {pause: pauseActivity, resume: resumeActivity, cleanup: cleanupActivity, restart: resetActivity, isPaused: () => isActivityPaused};

  window.addEventListener('prescribed-l26a1-mic-state', event => {
    prescribedMicMuted = Boolean(event.detail?.muted);
    activeStream?.getAudioTracks().forEach(track => { track.enabled = !prescribedMicMuted; });
    publishDebug({mic: `${activeStream ? 'Active' : 'Inactive'} · ${prescribedMicMuted ? 'Muted' : 'Unmuted'}`, status: prescribedMicMuted ? 'Muted' : (activeStream ? 'Listening' : debugState.status)}, prescribedMicMuted ? 'Microphone muted' : 'Microphone unmuted');
  });
  window.addEventListener('prescribed-l26a1-device-state', event => {
    selectedMicDeviceId = String(event.detail?.deviceId || '');
  });

  function configureStartModal() {
    if (data.progress?.activity_completed) return;
    const meaningful = Object.keys(matches || {}).length > 0
      || Object.values(reading || {}).some(Boolean)
      || Object.values(attempts || {}).some(value => Number(value) > 0);
    if (!meaningful) return;
    const modal = document.getElementById('lesson26-start');
    const label = modal?.querySelector('.lesson26-start-label');
    const title = document.getElementById('lesson26-start-title');
    const description = modal?.querySelector('.lesson26-start-description');
    const continueButton = document.getElementById('lesson26-start-button');
    const restartButton = document.getElementById('lesson26-later-button');
    if (!modal || !label || !title || !description || !continueButton || !restartButton) return;
    label.textContent = 'PROGRESS SAVED!';
    title.textContent = 'You’ve already started this activity. Would you like to continue where you left off?';
    description.hidden = true;
    continueButton.textContent = 'CONTINUE';
    restartButton.textContent = 'START OVER';
  }

  function renderCompletion() {
    window.PrescribedLessonUi.showCompletion(app);
  }

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
    if (data.progress?.activity_completed || currentIndex >= words.length) {
      renderCompletion();
      return;
    }
    const targetWord = words[currentIndex];
    publishDebug({expected: targetWord});
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
    app.querySelectorAll('.cell:not(:disabled)').forEach(button => {
      button.addEventListener('click', () => selectCell(button));
      button.addEventListener('mouseenter', () => previewSelection([
        Number(button.dataset.row), Number(button.dataset.column),
      ]));
    });
    app.querySelector('.grid')?.addEventListener('mouseleave', clearSelectionPreview);
  }

  function lineBetween(start, end) {
    const rowDelta = end[0] - start[0];
    const columnDelta = end[1] - start[1];
    const steps = Math.max(Math.abs(rowDelta), Math.abs(columnDelta));
    if (!steps || (rowDelta !== 0 && columnDelta !== 0 && Math.abs(rowDelta) !== Math.abs(columnDelta))) {
      return [start, end];
    }
    const rowStep = rowDelta === 0 ? 0 : rowDelta / steps;
    const columnStep = columnDelta === 0 ? 0 : columnDelta / steps;
    return Array.from({length: steps + 1}, (_, index) => [
      start[0] + rowStep * index, start[1] + columnStep * index,
    ]);
  }

  function clearSelectionPreview() {
    app.querySelectorAll('.cell.selection-preview').forEach(cell => cell.classList.remove('selection-preview'));
  }

  function previewSelection(end) {
    if (!selectedCell || busy) return;
    clearSelectionPreview();
    lineBetween(selectedCell, end).forEach(([row, column]) => {
      app.querySelector(`.cell[data-row="${row}"][data-column="${column}"]`)
        ?.classList.add('selection-preview');
    });
  }

  function showAcceptedMatch(start, end) {
    lineBetween(start, end).forEach(([row, column]) => {
      app.querySelector(`.cell[data-row="${row}"][data-column="${column}"]`)
        ?.classList.add('found');
    });
  }

  const localAudioBase = '/static/pabasa_app/prescribed/audio/SESSION_10/LESSON_26/GAWAIN_1/';
  function localAudioKey(value) {
    return String(value || '').trim().toLowerCase()
      .replace(/[’']/g, "'").replace(/[.!?]+$/, '');
  }

  const localAudioFiles = {
    'word search': 'Word Search.mp3',
    cat: 'Cat.mp3',
    hat: 'Hat.mp3',
    mat: 'Mat.mp3',
    tax: 'Tax.mp3',
    top: 'Top.mp3',
    [localAudioKey(READING_CORRECT_FEEDBACK)]: 'That’s right, now let’s find the word..mp3',
    [localAudioKey(GRID_CORRECT_FEEDBACK)]: 'That’s right, now let’s read the next word..mp3',
    [localAudioKey(RETRY_FEEDBACK)]: 'Hmm, let’s try that again..mp3',
    [localAudioKey(COMPLETION_FEEDBACK)]: 'Great job! You completed the Word Search..mp3',
  };

  async function playReadAloud(textToSpeak) {
    if (textToSpeak === COMPLETION_FEEDBACK && !app.querySelector('.pabasa-completion-card')) return false;
    const normalized = localAudioKey(textToSpeak);
    const key = normalized === 'word search. find the words on the grid'
      ? 'word search' : normalized;
    const filename = localAudioFiles[key];
    if (!filename) return false;

    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }
    const audio = new Audio(`${localAudioBase}${filename.split('/').map(encodeURIComponent).join('/')}`);
    audio.preload = 'auto';
    activeAudio = audio;
    try {
      const finished = new Promise((resolve, reject) => {
        audio.addEventListener('ended', resolve, {once: true});
        audio.addEventListener('error', () => reject(new Error('Audio playback failed. Please try again.')), {once: true});
      });
      await audio.play();
      await finished;
      return true;
    } catch (error) {
      return false;
    } finally {
      if (activeAudio === audio) activeAudio = null;
    }
  }

  async function readAloud(textToSpeak) {
    if (busy || isActivityPaused) return;
    busy = true;
    const buttons = [...app.querySelectorAll('#read, #listen-instructions')];
    const buttonStates = buttons.map(button => ({button, disabled: button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    const played = await playReadAloud(textToSpeak);
    if (isActivityPaused) return;
    buttonStates.forEach(({button, disabled}) => {
      if (button.isConnected) { button.disabled = disabled; button.classList.remove('is-busy'); }
    });
    busy = false;
    render(played ? '' : 'Could not play the audio. Please try again.', played ? '' : 'bad');
  }

  async function readWord() {
    if (busy || isActivityPaused || currentIndex >= words.length) return;
    if (prescribedMicMuted) {
      render('Microphone is muted. Turn it on and try again.', 'bad');
      return;
    }
    const wordIndex = currentIndex;
    const targetWord = words[wordIndex];
    publishDebug({expected: targetWord, error: '—', result: '—'});
    const button = app.querySelector('#read');
    busy = true;
    button.classList.add('is-busy');
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('Microphone recording is not available in this browser.');
      }
      const audioConstraints = {echoCancellation: true, noiseSuppression: false, autoGainControl: true};
      if (selectedMicDeviceId) audioConstraints.deviceId = {exact: selectedMicDeviceId};
      activeStream = await navigator.mediaDevices.getUserMedia({audio: audioConstraints});
      activeStream.getAudioTracks().forEach(track => { track.enabled = !prescribedMicMuted; });
      const recorder = new MediaRecorder(activeStream);
      activeRecorder = recorder;
      publishDebug({status: prescribedMicMuted ? 'Muted' : 'Recording', mic: `Active · ${prescribedMicMuted ? 'Muted' : 'Unmuted'}`, recorder: recorder.state, vad: 'waiting', error: '—'}, 'Recording started');
      recordingCancelled = false;
      const chunks = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const recording = new Promise((resolve, reject) => {
        recorder.onerror = () => reject(new Error('Could not record your voice. Please try again.'));
        recorder.onstop = () => {
          if (activeRecorder === recorder) activeRecorder = null;
          resolve(new Blob(chunks, {type: recorder.mimeType || 'audio/webm'}));
        };
        recorder.start();
        publishDebug({status: prescribedMicMuted ? 'Muted' : 'Recording', recorder: recorder.state});
      });
      const vadResult = monitorVAD(activeStream, recorder).catch(error => {
          if (recorder.state === 'recording') {
            try { recorder.stop(); } catch (_) { /* The outer cleanup handles the stream. */ }
          }
          throw error;
        });
      const [audio, vad] = await Promise.all([recording, vadResult]);
      publishDebug({recorder: 'inactive', vad: vad.reason === 'silence' ? 'silence detected' : vad.reason === 'maximum-duration' ? 'max duration reached' : vad.speechDetected ? 'speech detected' : 'waiting'}, `Recording stopped (${vad.reason || 'complete'})`);
      if (isActivityPaused) return;
      if (recordingCancelled || !vad.speechDetected || !audio.size) {
        throw new Error('No speech detected. Please try again.');
      }
      stopStream();

      const form = new FormData();
      form.append('audio', audio, 'word-search-reading.webm');
      form.append('target_text', targetWord);
      form.append('language', 'English');
      form.append('mode', 'reading');
      publishDebug({status: 'Processing'}, 'Processing started');
      const response = await fetch(data.transcribe_url, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form,
      });
      const result = await response.json();
      if (isActivityPaused) return;
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
      publishDebug({status: saidTarget ? 'Completed' : 'Error', transcript, normalized: normalizedWord(transcript), result: saidTarget ? 'Match' : 'Not Match', error: '—'}, `Transcript: ${transcript || '(empty)'} | Expected: ${targetWord} | Result: ${saidTarget ? 'Match' : 'Not Match'}`);
      const saved = await save({word_index: wordIndex, reading_result: saidTarget});
      reading = saved.progress?.state?.reading || reading;
      attempts = saved.progress?.state?.attempts || attempts;
      render('', saidTarget ? 'good' : 'bad');
      await playReadAloud(saidTarget ? READING_CORRECT_FEEDBACK : RETRY_FEEDBACK);
    } catch (error) {
      stopStream();
      publishDebug({status: 'Error', error: error.message || 'Recording/transcription error'}, `Error: ${error.message || 'Recording/transcription error'}`);
      render(error.message || 'Could not recognize your speech. Please try again.', 'bad');
    } finally {
      if (button?.isConnected) button.classList.remove('is-busy');
      busy = false;
    }
  }

  function stopStream() {
    stopVAD();
    if (activeRecorder && activeRecorder.state === 'recording') {
      try { activeRecorder.requestData(); } catch (_) { /* The stop event still finalizes the recorder. */ }
      try { activeRecorder.stop(); } catch (_) { /* Cleanup remains idempotent. */ }
    }
    activeStream?.getTracks().forEach(track => track.stop());
    activeStream = null;
    publishDebug({mic: `Inactive · ${prescribedMicMuted ? 'Muted' : 'Unmuted'}`, recorder: 'inactive'});
  }

  function stopVAD() {
    const cancelMonitor = cancelVADMonitor;
    cancelVADMonitor = null;
    if (cancelMonitor) cancelMonitor();
    if (vadFrame) {
      window.cancelAnimationFrame(vadFrame);
      vadFrame = null;
    }
    if (vadContext) {
      vadContext.close().catch(() => {});
      vadContext = null;
    }
  }

  function monitorVAD(stream, recorder) {
    stopVAD();
    return new Promise((resolve, reject) => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        window.setTimeout(() => {
          if (recorder.state === 'recording') recorder.stop();
          resolve({speechDetected: true});
        }, VAD_MAX_RECORDING_MS);
        return;
      }
      let analyser;
      let settled = false;
      let ambientNoiseFloor = 0;
      let speechFrameCount = 0;
      let speechDetected = false;
      let lastHeardAt = 0;
      const startedAt = Date.now();

      const finish = reason => {
        if (settled) return;
        settled = true;
        if (cancelVADMonitor) cancelVADMonitor = null;
        if (vadFrame) window.cancelAnimationFrame(vadFrame);
        vadFrame = null;
        if (recorder.state === 'recording') {
          try { recorder.requestData(); } catch (_) { /* The stop event still finalizes the blob. */ }
          try { recorder.stop(); } catch (error) { reject(error); return; }
        }
        publishDebug({vad: speechDetected ? (reason === 'silence' ? 'silence detected' : reason === 'maximum-duration' ? 'max duration reached' : 'speech detected') : 'waiting'});
        if (vadContext) {
          vadContext.close().catch(() => {});
          vadContext = null;
        }
        resolve({speechDetected, reason});
      };

      cancelVADMonitor = () => finish('cancelled');

      try {
        vadContext = new AudioContextClass();
        if (vadContext.state === 'suspended') {
          vadContext.resume().catch(() => {});
        }
        const source = vadContext.createMediaStreamSource(stream);
        analyser = vadContext.createAnalyser();
        analyser.fftSize = 1024;
        source.connect(analyser);
        const samples = new Uint8Array(analyser.fftSize);
      const tick = () => {
          if (settled) return;
          if (isActivityPaused) { vadFrame = window.requestAnimationFrame(tick); return; }
          if (recorder.state !== 'recording') return;
          const now = Date.now();
          if (vadContext?.state === 'suspended') {
            vadFrame = window.requestAnimationFrame(tick);
            return;
          }
          analyser.getByteTimeDomainData(samples);
          let sum = 0;
          for (let index = 0; index < samples.length; index += 1) {
            const centered = (samples[index] - 128) / 128;
            sum += centered * centered;
          }
          const rms = Math.sqrt(sum / samples.length);
          const elapsed = now - startedAt;
          const calibrating = elapsed < VAD_CALIBRATION_MS;
          if (!ambientNoiseFloor) ambientNoiseFloor = rms;
          else if (calibrating || rms < ambientNoiseFloor * 1.8) ambientNoiseFloor = (ambientNoiseFloor * 0.94) + (rms * 0.06);
          const threshold = Math.max(VAD_BASE_THRESHOLD, ambientNoiseFloor * VAD_NOISE_MULTIPLIER + 0.004);
          if (!calibrating && rms > threshold) speechFrameCount += 1;
          else speechFrameCount = Math.max(0, speechFrameCount - 1);
          if (speechFrameCount >= VAD_MIN_SPEECH_FRAMES) {
            speechDetected = true;
            lastHeardAt = now;
            publishDebug({vad: 'speech detected'});
          }
          if ((speechDetected && now - lastHeardAt >= VAD_SILENCE_MS) || elapsed >= VAD_MAX_RECORDING_MS) {
            finish(speechDetected ? 'silence' : 'maximum-duration');
            return;
          }
          vadFrame = window.requestAnimationFrame(tick);
        };
        tick();
      } catch (error) {
        stopVAD();
        reject(error);
      }
    });
  }

  async function selectCell(button) {
    if (busy || isActivityPaused) return;
    const point = [Number(button.dataset.row), Number(button.dataset.column)];
    if (selectedCell === null) {
      selectedCell = point;
      button.classList.add('selected');
      return;
    }
    const start = selectedCell;
    const end = point;
    selectedCell = null;
    clearSelectionPreview();
    busy = true;
    const result = await save({candidate_match: {word_index: currentIndex, start, end}}).catch(error => {
      render(error.message, 'bad');
      return null;
    });
    if (!result) { busy = false; return; }
    if (isActivityPaused) { busy = false; return; }
    if (!result.accepted) {
      render('', 'bad');
      await playReadAloud(RETRY_FEEDBACK);
      busy = false;
      return;
    }
    matches = result.progress.matches;
    showAcceptedMatch(start, end);
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
      const completionCard = app.querySelector('.pabasa-completion-card');
      if (completionCard) {
        await new Promise(resolve => window.setTimeout(resolve, 0));
        await playReadAloud(COMPLETION_FEEDBACK);
      }
    } else {
      await playReadAloud(GRID_CORRECT_FEEDBACK);
      render('', 'good');
    }
    busy = false;
  }

  window.addEventListener('pagehide', stopStream);
  window.addEventListener('prescribed-l26a1-activity-paused', () => publishDebug({status: 'Paused'}));
  window.addEventListener('prescribed-l26a1-activity-resumed', () => publishDebug({status: activeStream ? 'Listening' : 'Ready'}));
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
      window.location.reload();
    } catch (error) {
      busy = false;
      button.disabled = false;
      window.alert(error.message || 'Could not reset this activity. Please try again.');
    }
  }
  document.getElementById('lesson26-later-button')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson26-start-button')?.addEventListener('click', () => {
    window.setTimeout(() => readAloud('Word Search. Find the words on the grid.'), 0);
  });
  configureStartModal();
  render();
})();
