(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent || '{}');
  const activity = data.activity || {};
  const root = document.querySelector('.wb-shell');
  if (!root) return;
  const items = activity.items || [];
  const localAudio = data.local_audio || {};
  let state = {...(data.state || {})};
  let busy = false;
  let audio = null;
  let stream = null;
  let requestId = 0;
  let audioRun = 0;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const current = () => Number(state.index || 0);
  const oral = index => {
    const item = items[index];
    return (state.oral && item && state.oral[item.id]) || {
      passed: false, attempts: 0, listens: 0, phase: activity.model_first ? 'model' : 'read'
    };
  };
  const completed = () => items.reduce((total, item) => total + (state.oral?.[item.id]?.passed ? 1 : 0), 0);
  const target = () => items[current()]?.text || '';
  const mappedAudio = text => text === activity.instruction ? localAudio.instruction
    : (localAudio.words || {})[text]
      || (localAudio.feedback || {})[text]
      || (localAudio.completion || {})[text]
      || null;
  const stopAudio = () => {
    audioRun += 1;
    if (audio) { audio.pause(); audio.currentTime = 0; audio = null; }
  };
  const request = async (event, form = null) => {
    const body = form || JSON.stringify({...event, revision: Number(state.revision || 0)});
    const headers = {'X-CSRFToken': csrf()};
    if (!form) headers['Content-Type'] = 'application/json';
    const response = await fetch(data.progress_url, {method: 'POST', credentials: 'same-origin', headers, body});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) throw Error(result.error || 'Hindi na-save ang iyong gawain.');
    if (result.state) state = result.state;
    return result;
  };
  const playUrl = async url => {
    if (!url) return false;
    stopAudio();
    const mine = audioRun;
    audio = new Audio(url);
    await audio.play();
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(Error('Hindi ma-play ang audio.'));
    });
    if (mine !== audioRun) return false;
    audio = null;
    return true;
  };
  const playMappedFeedback = text => {
    return speak(text).catch(() => false);
  };
  const speak = async text => {
    const mapped = mappedAudio(text);
    if (mapped) return playUrl(mapped);
    stopAudio();
    const mine = audioRun;
    const form = new FormData();
    form.append('target_text', text);
    form.append('language', 'Filipino');
    form.append('mode', 'reading');
    form.append('prescribed_activity_key', activity.activity_key);
    form.append('session_key', activity.session_key || 'session-8');
    const response = await fetch(data.read_aloud_url, {
      method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success || !result.audio_content) {
      throw Error(result.error || 'Hindi available ang Filipino audio.');
    }
    if (!result.local_audio && (result.tts_language !== 'fil-PH' || result.voice_name !== 'fil-PH-Wavenet-A')) {
      throw Error('Hindi available ang tamang Filipino voice.');
    }
    if (mine !== audioRun) return false;
    audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
    await audio.play();
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(Error('Hindi ma-play ang Filipino audio.'));
    });
    audio = null;
    return true;
  };
  const list = () => items.map((item, index) => {
    const itemState = oral(index);
    const kind = itemState.passed ? 'done' : index === current() ? 'current' : 'future';
    return `<li class="l24g3-repeat-word ${kind}" aria-current="${index === current() ? 'step' : 'false'}">${esc(item.text)}</li>`;
  }).join('');
  function render(message = '', kind = '') {
    const index = current();
    const finished = Boolean(state.completed) || index >= items.length;
    const currentState = oral(index);
    const controlsLocked = busy;
    const back = esc(data.back_url || '/dashboard/assessment/');
    const next = esc(data.next_url || back);
    const phase = currentState.phase;
    const listenRequired = phase === 'model';
    const recovery = phase === 'listen';
    const recoveryReady = recovery && Number(currentState.listens || 0) >= 3;
    root.innerHTML = `<div class="l24g3-repeat-shell">
      <a class="l24g3-repeat-back" href="${back}">← <span>Aking Aralin</span></a>
      <section class="l24g3-repeat-card">
        <header class="l24g3-repeat-header">
          <p class="l24g3-repeat-eyebrow">SESSION 8 · LESSON 24 · BAHAGI 1 · GAWAIN 3 · P. ${esc(activity.printed_page || 45)}</p>
          <h1>${esc(activity.title || 'Pakinggan at ulitin: X')}</h1>
          <p class="l24g3-repeat-instruction">${esc(activity.instruction || '')}</p>
          <button class="l24g3-repeat-replay" id="instruction" type="button" ${controlsLocked ? 'disabled' : ''}>🔊 Pakinggan Muli</button>
          <div class="l24g3-repeat-progress"><span>Nabasa: ${completed()} / ${items.length}</span><i><b style="width:${items.length ? completed() / items.length * 100 : 0}%"></b></i></div>
        </header>
        ${finished ? `<section class="l24g3-repeat-complete"><h2>Magaling!</h2><p>Natapos mo ang Gawain 3.</p><div><a class="l24g3-repeat-primary" href="${next}">Susunod</a><a class="l24g3-repeat-secondary" href="${back}">Bumalik sa Aking Aralin</a></div></section>` : `<div class="l24g3-repeat-layout">
          <section class="l24g3-repeat-word-panel"><h2>MGA SALITA</h2><ul>${list()}</ul></section>
          <section class="l24g3-repeat-reading-panel">
            <h2>PAKINGGAN AT ULITIN</h2><p class="l24g3-repeat-label">Salitang Pakikinggan at Uulitin</p><strong class="l24g3-repeat-target">${esc(target())}</strong>
            <div class="l24g3-repeat-actions">
              <button class="l24g3-repeat-listen" id="listen" type="button" ${controlsLocked ? 'disabled' : ''}>🔊 Pakinggan</button>
              <p class="l24g3-repeat-state" role="status">${esc(message || (listenRequired ? 'Pakinggan muna ang salita.' : recovery ? (recoveryReady ? 'Pindutin ang Subukan Muli kapag handa ka na.' : 'Pakinggan muli ang tamang pagbigkas.') : 'Ngayon, ulitin ang salita.'))}</p>
              <button class="l24g3-repeat-speak" id="speak" type="button" ${controlsLocked || listenRequired || recovery ? 'disabled' : ''}>🎙 Ulitin</button>
              ${recovery ? `<button class="l24g3-repeat-secondary" id="retry" type="button" ${!recoveryReady || controlsLocked ? 'disabled' : ''}>Subukan Muli</button>` : ''}
            </div>
            <p class="l24g3-repeat-attempts">Pagsubok: ${Number(currentState.attempts || 0)} / 3</p>
            <div class="l24g3-repeat-heard"><span>NARINIG KO</span><strong>${esc(state.last_transcript || '—')}</strong></div>
            <p class="l24g3-repeat-feedback ${kind}" role="status">${esc(state.last_feedback || '')}</p>
            <button class="l24g3-repeat-reset" id="restart" type="button" ${controlsLocked ? 'disabled' : ''}>Ulitin Mula sa Simula</button>
          </section>
        </div>`}
      </section></div>`;
    document.getElementById('instruction')?.addEventListener('click', playInstruction);
    if (!finished) {
      document.getElementById('listen')?.addEventListener('click', listen);
      document.getElementById('speak')?.addEventListener('click', record);
      document.getElementById('retry')?.addEventListener('click', retry);
      document.getElementById('restart')?.addEventListener('click', restart);
    }
  }
  async function playInstruction() {
    if (busy) return;
    busy = true; render('Nilo-load ang audio…');
    try { await speak(activity.instruction || ''); render(); }
    catch (error) { render(error.message || 'Hindi available ang panuto.', 'bad'); }
    finally { busy = false; render(); }
  }
  async function listen() {
    if (busy) return;
    busy = true; render('Pinakikinggan ang tamang pagbigkas…');
    try {
      await speak(target());
      const phase = oral(current()).phase;
      if (phase === 'model') await request({action: 'model_listened'});
      else if (phase === 'listen') await request({action: 'listened'});
      render('Ngayon, ulitin ang salita.');
    } catch (error) { render(error.message || 'Hindi available ang audio.', 'bad'); }
    finally { busy = false; render(); }
  }
  async function record() {
    if (busy || oral(current()).phase !== 'read') return;
    busy = true; const mine = ++requestId;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw Error('Hindi available ang mikropono.');
      stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true}});
      render('Nakikinig…');
      const recorder = new MediaRecorder(stream), chunks = [];
      const blob = await new Promise((resolve, reject) => {
        recorder.ondataavailable = event => event.data?.size && chunks.push(event.data);
        recorder.onerror = reject;
        recorder.onstop = () => resolve(new Blob(chunks, {type: recorder.mimeType || 'audio/webm'}));
        recorder.start();
        setTimeout(() => recorder.state === 'recording' && recorder.stop(), 3500);
      });
      stream.getTracks().forEach(track => track.stop()); stream = null;
      if (mine !== requestId) return;
      render('Pinoproseso…');
      const form = new FormData();
      form.append('audio', blob, 'lesson24-gawain3-repeat.webm');
      form.append('action', 'reading');
      form.append('item_index', String(current()));
      form.append('revision', String(state.revision || 0));
      const result = await request({action: 'reading'}, form);
      if (result.state?.oral?.[items[current()]?.id]?.passed) {
        await request({action: 'answer', answer: null});
        if (current() >= items.length) {
          await request({action: 'finish'});
          await playMappedFeedback('Magaling! Natapos mo ang Gawain 3.');
        } else await playMappedFeedback('Tama!');
        render('Tama!');
      } else {
        const feedback = result.state?.last_feedback || 'Subukan muli.';
        await playMappedFeedback(feedback);
        render(feedback, 'bad');
      }
    } catch (error) { if (mine === requestId) render(error.message || 'Hindi nakuha ang iyong boses. Subukan muli.', 'bad'); }
    finally { stream?.getTracks().forEach(track => track.stop()); stream = null; busy = false; render(); }
  }
  async function retry() {
    if (busy || oral(current()).phase !== 'listen') return;
    busy = true; render('Inihahanda ang pag-ulit…');
    try { await request({action: 'retry_reading'}); render('Ngayon, ulitin ang salita.'); }
    catch (error) { render(error.message || 'Pakinggan muna ang tamang pagbigkas.', 'bad'); }
    finally { busy = false; render(); }
  }
  async function restart() {
    if (busy || !window.confirm('Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa Gawain 3.')) return;
    busy = true;
    try { await request({action: 'restart'}); render(); }
    catch (error) { render(error.message || 'Hindi na-reset ang gawain.', 'bad'); }
    finally { busy = false; render(); }
  }
  window.addEventListener('pagehide', () => { requestId += 1; stream?.getTracks().forEach(track => track.stop()); stopAudio(); });
  render();
})();
