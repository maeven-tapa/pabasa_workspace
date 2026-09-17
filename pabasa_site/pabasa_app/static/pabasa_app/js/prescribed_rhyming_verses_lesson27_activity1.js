(() => {
  'use strict';
  const dataNode = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('app');
  if (!dataNode || !app) return;
  const data = JSON.parse(dataNode.textContent || '{}');
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const normalize = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
  const canonicalTranscript = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\bdanced\b/g, 'dance').replace(/\bhot\b/g, 'hat').replace(/\bmath\b/g, 'mat').replace(/\bwar\b/g, 'wore').replace(/\bbutt\b/g, 'bat').replace(/\bbath\b/g, 'bat').replace(/\bbut\b/g, 'bat').replace(/\bquiet\b/g, 'quite').replace(/\blaugh\b/g, 'laughed').replace(/\blove\b/g, 'loved');
  let state = {phase:'reading', item_index:0, verse_index:0, attempts:0, help_visible:false, selected:[], completed_items:0, ...(data.progress?.state || {})};
  let busy = false;
  let stream = null;
  let audio = null;
  let audioUrl = null;

  async function responseJson(response, label) {
    const type = response.headers.get('content-type') || '';
    if (!type.includes('application/json')) {
      if (response.redirected) throw new Error('Your session may have expired. Refresh and sign in again.');
      throw new Error(`${label} returned an unexpected page (HTTP ${response.status}). Refresh and try again.`);
    }
    return response.json();
  }
  async function save(payload) {
    const response = await fetch(data.progress_url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(payload)});
    const result = await responseJson(response, 'Saving progress');
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');
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
      frame('<div class="lesson27-complete">🎉 Great job! You finished all the rhyming verses.</div>');
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
    let controls = '';
    if (state.phase === 'reading') {
      controls = `<p class="lesson27-prompt">Read verse ${state.verse_index + 1} of ${item.lines.length} aloud.</p><p class="lesson27-status ${type}" id="status">${esc(message || (state.help_visible ? 'Listen to hear the verse, then try reading it again.' : 'Read the highlighted verse aloud.'))}</p><div class="lesson27-actions"><button class="lesson27-button" id="record-verse" type="button">🎙️ Read the verse</button><button class="lesson27-button secondary" id="listen-verse" type="button">🔊 Listen</button></div>`;
    } else {
      controls = `<p class="lesson27-prompt">Click all the words that rhyme with “at.”</p><p class="lesson27-status ${type}" id="status">${esc(message || 'Select every rhyming word. They will turn green when correct.')}</p><div class="lesson27-actions"><button class="lesson27-button secondary" id="listen-rhyme-directions" type="button">🔊 Listen to directions</button><button class="lesson27-button" id="listen-poem" type="button">🔊 Listen to the poem</button></div>`;
    }
    frame(`<div class="lesson27-content"><h2 class="lesson27-poem-title">${esc(item.title)}</h2><div class="lesson27-verses">${lines}</div>${controls}</div>`);
    document.getElementById('record-verse')?.addEventListener('click', () => recordVerse(activeVerse));
    document.getElementById('listen-verse')?.addEventListener('click', () => playAudio(activeVerse).catch(error => render(error.message, 'bad')));
    document.getElementById('listen-rhyme-directions')?.addEventListener('click', () => playAudio('Click all the words that rhyme with at.').catch(error => render(error.message, 'bad')));
    document.getElementById('listen-poem')?.addEventListener('click', () => playAudio(item.lines.map(line => line.text).join(' ')).catch(error => render(error.message, 'bad')));
    app.querySelectorAll('.lesson27-word:not(:disabled)').forEach(button => button.addEventListener('click', () => selectWord(button)));
  }
  async function playAudio(text) {
    if (busy || !text) return;
    busy = true;
    const buttons = app.querySelectorAll('button'); buttons.forEach(button => { button.disabled = true; });
    const status = document.getElementById('status'), oldStatus = status?.textContent;
    if (status) status.textContent = 'Playing audio…';
    try {
      const response = await fetch(data.read_aloud_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-27-gawain-1'})});
      const result = await responseJson(response, 'Read-aloud service');
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio. Try again.');
      const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0));
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'}));
      audio = new Audio(audioUrl);
      await new Promise((resolve, reject) => {
        audio.addEventListener('ended', resolve, {once:true});
        audio.addEventListener('error', () => reject(new Error('Audio playback failed. Try again.')), {once:true});
        audio.play().catch(reject);
      });
    } finally {
      busy = false;
      app.querySelectorAll('button').forEach(button => { button.disabled = false; });
      if (status?.isConnected && status.textContent === 'Playing audio…') status.textContent = oldStatus;
      audio = null;
      if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
    }
  }
  async function recordVerse(target) {
    if (busy) return;
    busy = true;
    const button = document.getElementById('record-verse'), status = document.getElementById('status');
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { status.textContent = 'Microphone recording is not available in this browser.'; busy = false; return; }
    button.disabled = true; button.textContent = 'Listening…'; status.textContent = 'Listening…';
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      const recorder = new MediaRecorder(stream), chunks = [];
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      const stopped = new Promise((resolve, reject) => { recorder.onerror = () => reject(new Error('Could not record your voice. Try again.')); recorder.onstop = () => resolve(new Blob(chunks,{type:recorder.mimeType || 'audio/webm'})); recorder.start(); window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 4500); });
      const blob = await stopped; stopStream();
      const form = new FormData(); form.append('audio',blob,'lesson27-rhyming-verse.webm'); form.append('target_text',target); form.append('language','English'); form.append('mode','reading');
      const response = await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await responseJson(response, 'Speech recognition');
      if (!response.ok || !result.success) throw new Error(result.error || 'Speech recognition failed. Try again.');
      const heardText = result.raw_transcript || result.transcript;
      const spoken = normalize(canonicalTranscript(heardText));
      const expected = normalize(canonicalTranscript(target));
      const spokenTokens = canonicalTranscript(heardText).match(/[a-z]+/g) || [];
      const expectedTokens = canonicalTranscript(target).match(/[a-z]+/g) || [];
      const isPlayfulBatVerse = expectedTokens.includes('dance') && expectedTokens.includes('playful') && expectedTokens.includes('bat');
      const playfulBatHeard = spokenTokens.includes('bat') && (spokenTokens.includes('dance') || spokenTokens.includes('playful'));
      const correct = Boolean(expected && (spoken.includes(expected) || (isPlayfulBatVerse && playfulBatHeard)));
      const message = correct ? 'Correct! Read the next verse.' : `I heard “${result.raw_transcript || result.transcript || 'unclear speech'}”. Please try the verse again.`;
      await save({action:'verse_read',item_index:state.item_index,verse_index:state.verse_index,success:correct});
      render(message, correct ? 'good' : 'bad');
    } catch (error) { stopStream(); render(error.message || 'Could not recognize your speech. Try again.','bad'); }
    finally { busy = false; }
  }
  async function selectWord(button) {
    if (busy || button.classList.contains('selected')) return;
    busy = true;
    try {
      const result = await save({action:'rhyme_select',token_id:button.dataset.id});
      if (!result.accepted) {
        button.classList.add('wrong');
        window.setTimeout(() => button.classList.remove('wrong'), 500);
        return;
      }
      if (state.phase === 'complete') {
        const response = await fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'});
        const payload = await responseJson(response, 'Saving completion');
        if (!response.ok || !payload.success) throw new Error(payload.error || 'Could not save completion.');
      }
      render(result.accepted ? 'Correct! Keep finding the rhyming words.' : '', 'good');
    } catch (error) { render(error.message || 'Could not save your selection. Try again.','bad'); }
    finally { busy = false; }
  }
  function stopStream() { stream?.getTracks().forEach(track => track.stop()); stream = null; }
  async function resetAndExit(event) {
    event.preventDefault(); if (busy) return;
    const button = event.currentTarget; busy = true; button.disabled = true;
    try {
      const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({reset:true})});
      const result = await responseJson(response, 'Resetting activity');
      if (!response.ok || !result.success) throw new Error(result.error || 'Could not reset the activity. Try again.');
      window.location.assign(document.getElementById('lesson27-back').href);
    } catch (error) { busy = false; button.disabled = false; window.alert(error.message || 'Could not reset the activity. Try again.'); }
  }
  document.getElementById('lesson27-back')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson27-later-button')?.addEventListener('click', resetAndExit);
  document.getElementById('lesson27-start-button')?.addEventListener('click', () => {
    window.setTimeout(() => playAudio('Rhyming Verses. Read each verse, then select the words that rhyme with at.').catch(error => render(error.message || 'Could not play the instructions. Try again.','bad')), 0);
  });
  window.addEventListener('pagehide', () => { stopStream(); audio?.pause(); if (audioUrl) URL.revokeObjectURL(audioUrl); });
  render();
})();
