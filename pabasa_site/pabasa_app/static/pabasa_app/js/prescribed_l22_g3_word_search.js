(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent || '{}');
  const activity = data.activity, app = document.getElementById('l22g3-app');
  const instruction = 'Hanapin at kulayan ng paboritong kulay ang sumusunod na salita sa ibaba.';
  const colors = ['#55a9df', '#f2c94c', '#ef8d8d', '#78c596', '#b18ae0'];
  let state = {...(data.state || {})}, selectedColor = '#55a9df', active = null, busy = false;
  let audio = null, audioController = null, audioRun = 0, instructionBusy = false;
  let instructionPlayed = false, automaticInstructionAttempted = false;
  const words = activity.items.map(item => item.text);
  const found = () => state.found_words && typeof state.found_words === 'object' ? state.found_words : {};
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pathBetween = (start, end) => {
    if (!start || !end || start[0] !== end[0]) return [];
    const step = Math.sign(end[1] - start[1]);
    return Array.from({length: Math.abs(end[1] - start[1]) + 1}, (_, i) => [start[0], start[1] + i * step]);
  };
  const wordForPath = path => words.find(word => word.length === path.length && word.split('').every((letter, i) => letter.toUpperCase() === activity.grid[path[i][0]][path[i][1]].toUpperCase())) || '';
  const setSelection = path => {
    document.querySelectorAll('.cell').forEach(cell => cell.classList.toggle('selected', path.some(([r,c]) => r === +cell.dataset.row && c === +cell.dataset.col)));
  };
  const stopAudio = () => {
    audioRun += 1;
    audioController?.abort(); audioController = null;
    if (audio) { const finish = audio.onended; audio.pause(); audio.currentTime = 0; audio.onended = null; audio.onerror = null; audio = null; finish?.(); }
  };
  async function speakExact(text) {
    stopAudio();
    const run = audioRun, controller = new AbortController(); audioController = controller;
    const form = new FormData(); form.append('target_text', text); form.append('language', 'Filipino'); form.append('mode', 'reading'); form.append('prescribed_activity_key', activity.activity_key);
    try {
      const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', headers:{'Accept':'application/json','X-CSRFToken':csrf()}, body:form, signal:controller.signal});
      const result = await response.json().catch(() => ({}));
      if (run !== audioRun) throw Object.assign(Error('Audio interrupted.'), {cancelled:true});
      if (!response.ok || !result.success || !result.audio_content) throw Error(result.error || 'Hindi available ang Filipino audio.');
      if (result.tts_language !== 'fil-PH' || result.voice_name !== 'fil-PH-Wavenet-A') throw Error('Hindi available ang tamang Filipino voice.');
      audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
      await audio.play();
      await new Promise((resolve, reject) => { audio.onended = resolve; audio.onerror = () => reject(Error('Hindi ma-play ang Filipino audio.')); });
    } catch (error) {
      if (run !== audioRun || error?.name === 'AbortError') throw Object.assign(error, {cancelled:true});
      throw error;
    } finally {
      if (audioController === controller) audioController = null;
      if (audio && run === audioRun) { audio.pause(); audio = null; }
    }
  }
  const updateInstructionButton = () => {
    const button = document.getElementById('tts');
    if (button) { button.disabled = instructionBusy; button.textContent = `🔊 ${instructionPlayed ? 'Pakinggan Muli ang Panuto' : 'Pakinggan ang Panuto'}`; }
  };
  async function playInstruction({automatic = false} = {}) {
    if (instructionBusy) return;
    instructionBusy = true; updateInstructionButton();
    try {
      await speakExact(instruction); instructionPlayed = true;
    } catch (error) {
      if (!error?.cancelled) showFeedback(automatic ? 'Pindutin ang “Pakinggan ang Panuto” para mapakinggan ang panuto.' : 'Hindi available ang audio. Subukan muli.', true);
    } finally { instructionBusy = false; updateInstructionButton(); }
  }
  const feedbackText = message => {
    const correct = words.some(word => message === `Tama! Nahanap mo ang ${word}.`);
    return message === 'Subukan muli.' || message === 'Hindi iyon ang salitang hinahanap. Subukan muli.' || message === 'Nahanap mo na ang salitang ito.' || message === 'Magaling! Nahanap mo ang lahat ng salita!' || correct ? message : '';
  };
  function speakFeedback(message) { const text = feedbackText(message); if (text) speakExact(text).catch(() => {}); }
  function showFeedback(message, error = false) { const node = document.getElementById('feedback'); if (node) { node.textContent = message || ''; node.className = `feedback${error ? ' error' : ''}`; } }
  async function send(event) {
    if (data.preview) return {success:true, state};
    const response = await fetch(data.progress_url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify({...event, revision:Number(state.revision || 0)})});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) throw Error(result.error || 'Hindi na-save ang gawain.');
    state = result.state; return result;
  }
  function render() {
    const completed = Boolean(state.completed), count = Object.keys(found()).length;
    if (completed) {
      app.innerHTML = `<div class="shell"><header class="header"><a class="back" href="${esc(data.back_url)}">Aking Aralin</a><p class="eyebrow">LESSON 22 • GAWAIN 3</p><h1>Hanap-Salita</h1></header><section class="complete"><h2>Magaling! Nahanap mo ang lahat ng salita!</h2><p class="progress">Nahanap: 9 / 9</p><a class="button" href="${esc(data.back_url)}">Bumalik sa Aking Aralin</a></section></div>`;
      return;
    }
    app.innerHTML = `<div class="shell"><header class="header"><a class="back" href="${esc(data.back_url)}">Aking Aralin</a><p class="eyebrow">LESSON 22 • GAWAIN 3</p><h1>Hanap-Salita</h1><p class="instruction">${esc(instruction)}</p><button id="tts" class="tts" type="button">🔊 Pakinggan ang Panuto</button><p class="progress">Nahanap: ${count} / 9</p></header><section class="activity-card"><div class="grid-wrap"><div id="grid" class="grid" aria-label="9 by 9 na hanap-salita" role="grid">${activity.grid.map((row, r) => Array.from(row).map((letter, c) => `<button class="cell" type="button" role="gridcell" data-row="${r}" data-col="${c}" aria-label="Hanay ${r+1}, kolum ${c+1}: ${esc(letter)}">${esc(letter)}</button>`).join('')).join('')}</div><p class="helper">Pindutin ang unang letra at i-drag hanggang sa huling letra.</p></div><aside class="word-list"><h2>MGA SALITANG HAHANAPIN</h2><ul>${words.map(word => `<li class="${found()[word] ? 'found' : ''}"><span aria-hidden="true">${found()[word] ? '✓' : '○'}</span><span>${esc(word)}</span></li>`).join('')}</ul><div class="tools"><span aria-label="Paboritong kulay">Kulay:</span>${colors.map(color => `<button type="button" class="swatch" data-color="${color}" aria-label="Pumili ng kulay ${color}" style="width:32px;height:32px;border-radius:50%;border:3px solid ${color === selectedColor ? '#17485d' : '#fff'};background:${color};cursor:pointer"></button>`).join('')}</div><p id="feedback" class="feedback" role="status" aria-live="polite">${esc(state.last_feedback || '')}</p><button id="restart" class="restart" type="button">Ulitin Mula sa Simula</button></aside></section><div id="confirm" class="confirm" hidden><div class="confirm-card"><p>Sigurado ka bang gusto mong magsimula muli? Mawawala ang progreso mo sa Gawain 3.</p><div class="confirm-actions"><button id="cancel" type="button">Kanselahin</button><button id="confirm-restart" class="primary" type="button">Magsimula Muli</button></div></div></div></div>`;
    const grid = document.getElementById('grid');
    Object.entries(found()).forEach(([, entry]) => entry.path.forEach(([r,c]) => { const cell = grid.querySelector(`[data-row="${r}"][data-col="${c}"]`); if (cell) { cell.classList.add('found'); cell.style.background = entry.color; } }));
    document.getElementById('tts').onclick = playInstruction; updateInstructionButton();
    document.querySelectorAll('.swatch').forEach(button => { button.onclick = () => { selectedColor = button.dataset.color; document.querySelectorAll('.swatch').forEach(b => b.style.borderColor = b === button ? '#17485d' : '#fff'); }; });
    document.getElementById('restart').onclick = () => { document.getElementById('confirm').hidden = false; };
    document.getElementById('cancel').onclick = () => { document.getElementById('confirm').hidden = true; };
    document.getElementById('confirm-restart').onclick = async () => { if (busy) return; busy = true; try { await send({action:'restart'}); document.getElementById('confirm').hidden = true; render(); } catch (error) { showFeedback(error.message, true); } finally { busy = false; } };
    grid.addEventListener('pointerdown', event => { const cell = event.target.closest('.cell'); if (!cell || busy || data.preview) return; active = {pointerId:event.pointerId, start:[+cell.dataset.row,+cell.dataset.col], path:[+cell.dataset.row,+cell.dataset.col]}; grid.setPointerCapture(event.pointerId); event.preventDefault(); setSelection(active.path); });
    grid.addEventListener('pointermove', event => { if (!active || event.pointerId !== active.pointerId) return; const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest('.cell'); if (!cell || !grid.contains(cell)) return; active.path = pathBetween(active.start, [+cell.dataset.row,+cell.dataset.col]); setSelection(active.path); event.preventDefault(); });
    const end = async event => { if (!active || event.pointerId !== active.pointerId) return; const gesture = active; active = null; setSelection([]); try { const endCell = document.elementFromPoint(event.clientX,event.clientY)?.closest('.cell'); const path = endCell ? pathBetween(gesture.start,[+endCell.dataset.row,+endCell.dataset.col]) : gesture.path; if (path.length < 2) return; busy = true; const result = await send({action:'select_word', path, word:wordForPath(path), color:selectedColor}); const feedback = result.state.last_feedback || ''; render(); if (feedback) { showFeedback(feedback); speakFeedback(feedback); } } catch (error) { showFeedback(error.message, true); } finally { busy = false; } };
    grid.addEventListener('pointerup', end); grid.addEventListener('pointercancel', end); grid.addEventListener('lostpointercapture', () => { active = null; setSelection([]); });
  }
  window.addEventListener('pagehide', stopAudio); render();
  if (!data.preview && !state.completed && !automaticInstructionAttempted) { automaticInstructionAttempted = true; setTimeout(() => playInstruction({automatic:true}), 0); }
})();
