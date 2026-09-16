(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!node || !app) return;
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  let state = { ...(data.progress?.state || {}) };
  let busy = false;
  let stream = null;
  let audio = null;
  let audioUrl = null;
  let wrongChoice = '';

  function hydrate() {
    state.current_item = Number(state.current_item || 0);
    state.choice_index = Number(state.choice_index || 0);
    state.phase ||= 'reading_choices';
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body)
    });
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); }
    catch (_) { throw new Error('The activity service is temporarily unavailable. Please try again.'); }
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');
    if (result.progress?.state) state = { ...result.progress.state };
    hydrate();
    return result;
  }

  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete' || state.current_item >= data.items.length) {
      app.innerHTML = `<div class="complete">🎉 Great job! You matched every picture.</div>${steps()}`;
      post(data.completion_url, {}).catch(() => {});
      return;
    }
    const item = data.items[state.current_item];
    const choices = item.choices;
    const reading = state.phase === 'reading_choices';
    const choiceIndex = Math.min(state.choice_index, choices.length - 1);
    app.innerHTML = `<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 1</div>
      <h1 class="title">Circle the Right Word!</h1>
      <p class="instruction">${reading ? 'Read each choice aloud, one at a time.' : 'Look at the picture. Circle the correct word.'}</p>
      <p class="item-label">Item ${state.current_item + 1} of ${data.items.length}</p>
      ${reading
        ? `<div class="word" aria-live="polite">${escapeHtml(choices[choiceIndex])}</div>
           <p class="status ${kind}" id="status">${escapeHtml(message || `Read choice ${choiceIndex + 1} of ${choices.length}.`)}</p>
           <div class="read-actions"><button class="button" id="read" type="button">🎙️ Read the word</button><button class="button secondary" id="listen" type="button">🔊 Listen</button></div>
           <div class="choices" aria-label="Choices to read">${choices.map((word, i) => `<span class="choice ${i === choiceIndex ? 'correct' : ''}">${escapeHtml(word)}</span>`).join('')}</div>`
        : `<div class="picture"><img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.alt_text)}"></div>
           <div class="choices" aria-label="Circle the matching word">${choices.map(word => `<button class="choice ${wrongChoice === word ? 'wrong' : ''}" data-choice="${escapeHtml(word)}" type="button" ${busy ? 'disabled' : ''}>${escapeHtml(word)}</button>`).join('')}</div>
           <p class="status ${kind}" id="status">${escapeHtml(message || 'Circle the word that matches the picture.')}</p>`}
      ${steps()}`;
    if (reading) {
      document.getElementById('read').onclick = record;
      document.getElementById('listen').onclick = () => play(choices[choiceIndex]).then(() => render('Now read the word aloud.')).catch(error => render(error.message, 'bad'));
    } else {
      app.querySelectorAll('[data-choice]').forEach(button => { button.onclick = () => choose(button.dataset.choice); });
    }
  }

  function steps() {
    const current = state.phase === 'complete' ? data.items.length : state.current_item;
    return `<div class="progress" aria-label="Activity progress">${data.items.map((_, index) => `<span class="step ${index < current ? 'done' : ''} ${index === current && state.phase !== 'complete' ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;
  }

  async function play(text) {
    if (busy || !text) return;
    busy = true;
    try {
      const response = await fetch(data.read_aloud_url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ target_text: text, language: 'English' })
      });
      const body = await response.text();
      let result;
      try { result = JSON.parse(body); }
      catch (_) { throw new Error('Read aloud is temporarily unavailable. Please try again.'); }
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio.');
      const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0));
      audioUrl = URL.createObjectURL(new Blob([bytes], { type: result.mime_type || 'audio/mpeg' }));
      audio = new Audio(audioUrl);
      await new Promise((resolve, reject) => {
        audio.onended = resolve;
        audio.onerror = () => reject(new Error('Audio playback failed.'));
        audio.play().catch(reject);
      });
    } finally {
      busy = false;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = null;
      audio = null;
    }
  }

  async function record() {
    if (busy || state.phase !== 'reading_choices') return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      render('Microphone recording is not available in this browser.', 'bad');
      return;
    }
    busy = true;
    const itemIndex = state.current_item;
    const choiceIndex = state.choice_index;
    const target = data.items[itemIndex].choices[choiceIndex];
    let message = '';
    let kind = '';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const recorder = new MediaRecorder(stream);
      const chunks = [];
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      const blob = await new Promise((resolve, reject) => {
        recorder.onerror = () => reject(new Error('Could not record your voice. Try again.'));
        recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
        recorder.start();
        setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 3000);
      });
      stopStream();
      const form = new FormData();
      form.append('audio', blob, 'lesson31-circle-word.webm');
      form.append('target_text', target);
      form.append('language', 'English');
      form.append('mode', 'reading');
      const response = await fetch(data.transcribe_url, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf() }, body: form });
      const body = await response.text();
      let transcript;
      try { transcript = JSON.parse(body); }
      catch (_) { throw new Error('Speech recognition is temporarily unavailable. Please try again.'); }
      if (!response.ok || !transcript.success) throw new Error(transcript.error || 'Speech recognition failed. Try again.');
      const heard = String(transcript.raw_transcript || transcript.transcript || '');
      const result = await post(data.progress_url, { action: 'read_choice', item_index: itemIndex, choice_index: choiceIndex, heard });
      message = result.accepted ? (state.phase === 'choosing' ? 'Great reading! Now look at the picture and circle the matching word.' : 'Correct! Read the next choice.') : `I heard “${heard}”. Please try “${target}” again.`;
      kind = result.accepted ? 'good' : 'bad';
    } catch (error) {
      stopStream();
      message = error.message || 'I could not hear you. Please try again.';
      kind = 'bad';
    } finally {
      busy = false;
    }
    render(message, kind);
  }

  async function choose(word) {
    if (busy || state.phase !== 'choosing') return;
    busy = true;
    const itemIndex = state.current_item;
    let message = '';
    let kind = '';
    try {
      const result = await post(data.progress_url, { action: 'choose', item_index: itemIndex, choice: word });
      wrongChoice = result.accepted ? '' : word;
      message = result.accepted ? (state.phase === 'complete' ? 'Wonderful! You finished the activity.' : 'Correct! Read the next set of choices.') : 'That is not the matching word. Try another choice.';
      kind = result.accepted ? 'good' : 'bad';
    } catch (error) {
      message = error.message || 'Could not save your answer.';
      kind = 'bad';
    } finally {
      busy = false;
    }
    render(message, kind);
  }

  function stopStream() {
    stream?.getTracks().forEach(track => track.stop());
    stream = null;
  }

  async function leave(event) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    try {
      await post(data.progress_url, { reset: true });
      window.location.assign(document.getElementById('lesson31a1-back').href);
    } catch (error) {
      busy = false;
      window.alert(error.message || 'Could not reset the activity.');
    }
  }

  document.getElementById('lesson31a1-back').addEventListener('click', leave);
  document.getElementById('lesson31a1-later').addEventListener('click', leave);
  document.getElementById('lesson31a1-go').addEventListener('click', async () => {
    document.getElementById('lesson31a1-start').hidden = true;
    document.getElementById('lesson31a1-stage').classList.remove('waiting');
    try {
      await play('Circle the Right Word. Read all three choices aloud, one at a time. Then look at the picture and circle the correct word.');
      render();
    } catch (error) {
      render(error.message, 'bad');
    }
  });
  window.addEventListener('pagehide', () => { stopStream(); audio?.pause(); });
  hydrate();
  render();
})();
