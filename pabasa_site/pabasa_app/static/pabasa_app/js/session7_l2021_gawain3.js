(() => {
  'use strict';

  const data = JSON.parse(document.getElementById('prescribed-activity-data')?.textContent || '{}');
  const app = document.getElementById('s7g3-app');
  const items = data.items || [];
  const example = data.worked_example || {};
  const total = items.length;
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const indexKey = index => String(index);
  let state = Object.assign({phase:'intro',current_item_index:0,completed_oral_reads:[],stt_attempts:{},tts_plays:{},connected_answers:{},selected_answer:'',completed_item_count:0,correct_answer_count:0,state_version:0}, data.progress?.state || {});
  let busy = false;
  let started = false;
  let requestId = 0;
  let stream = null;
  let activeAudio = null;
  let activeObjectUrl = '';
  let settleAudio = null;
  let generation = 0;
  let paused = false;

  const currentIndex = () => Math.max(0, Number(state.current_item_index) || 0);
  const currentItem = () => items[currentIndex()];
  const updateExpected = word => {
    const field = document.getElementById('prescribed-s7-l20-21-g3-debug-expected');
    if (field) field.textContent = word || 'Not reading';
  };
  const stopAudio = () => {
    settleAudio?.();
    settleAudio = null;
    if (activeAudio) { activeAudio.pause(); activeAudio.currentTime = 0; activeAudio = null; }
    if (activeObjectUrl) { URL.revokeObjectURL(activeObjectUrl); activeObjectUrl = ''; }
  };
  const stopStream = () => { stream?.getTracks?.().forEach(track => track.stop()); stream = null; };
  const cancel = () => { generation += 1; requestId += 1; window.Basahin?.cancelAll?.(); stopStream(); stopAudio(); };
  const play = source => new Promise((resolve, reject) => {
    if (!source) return resolve(false);
    const objectUrl = String(source).startsWith('blob:') ? source : '';
    stopAudio();
    activeObjectUrl = objectUrl;
    const player = activeAudio = new Audio(source);
    const finish = ok => {
      settleAudio = null;
      if (activeAudio === player) activeAudio = null;
      player.onended = player.onerror = null;
      if (!ok) {
        const status = app.querySelector('.s7g3-status');
        if (status) status.textContent = 'Hindi ma-play ang audio. Subukan muli.';
      }
      resolve(ok);
    };
    settleAudio = () => { player.onended = player.onerror = null; reject(new DOMException('Playback cancelled', 'AbortError')); };
    player.onended = () => finish(true);
    player.onerror = () => finish(false);
    player.play().catch(() => finish(false));
  });
  const audio = (group, name) => data.local_audio?.[group]?.[name] || '';
  const speakFeedback = name => play(audio('feedback', name));
  const header = () => {
    const completed = Number(state.correct_answer_count) || 0;
    const title = state.phase === 'oral_reading' ? 'Basahin ang salitang ito.' : state.phase === 'intro' ? data.title : 'Gumuhit ng Linya Mula sa Larawan Tungo sa Tamang Salita.';
    return `<p class="s7g3-label">SESSION 7 · LESSON 20 AT 21 · GAWAIN 3</p><h1 class="s7g3-title">${escapeHtml(title)}</h1><p class="s7g3-step">${state.phase === 'intro' ? 'Halimbawa' : `Hakbang ${Math.min(completed + 1, total)} sa ${total}`}</p><div class="s7g3-track" aria-label="${completed} sa ${total} na tugma"><i style="width:${total ? completed / total * 100 : 0}%"></i></div>`;
  };
  const render = (message = '', kind = '') => {
    if (!started) return;
    app.setAttribute('aria-busy', String(busy));
    if (data.progress?.activity_completed || state.phase === 'completion') {
      updateExpected('');
      app.innerHTML = `<div class="s7g3-layout s7g3-complete"><div class="s7g3-stage"><div aria-hidden="true">⭐</div><h1>Magaling!</h1><p>Natapos mo ang Lesson 20 at 21: Gawain 3.</p><a class="s7g3-primary" href="/dashboard/assessment/">Balik sa Aking Aralin</a></div></div>`;
      return;
    }
    const index = currentIndex();
    const item = currentItem();
    if (state.phase === 'intro') {
      updateExpected('');
      app.innerHTML = `<div class="s7g3-layout">${header()}<div class="s7g3-stage"><p class="s7g3-cue">Tingnan ang halimbawa.</p><div class="s7g3-example"><img src="${escapeHtml(example.image_url)}" alt="${escapeHtml(example.alt_text)}"><span class="s7g3-example-line" aria-hidden="true"></span><span class="s7g3-example-word">${escapeHtml(example.word)}</span></div><p class="s7g3-example-note">Nakaguhit na ang linya. Hindi ito kasama sa puntos.</p><button class="s7g3-primary" id="s7g3-begin" type="button">SIMULAN</button><p class="s7g3-status" role="status"></p></div></div>`;
      app.querySelector('#s7g3-begin').addEventListener('click', begin);
      return;
    }
    if (state.phase === 'feedback') {
      const previous = items[Math.max(0, index - 1)];
      updateExpected(previous?.word || '');
      app.innerHTML = `<div class="s7g3-layout">${header()}<div class="s7g3-stage"><div class="s7g3-picture-frame"><img class="s7g3-picture" src="${escapeHtml(previous?.image_url)}" alt="${escapeHtml(previous?.alt_text)}"></div><p class="s7g3-cue">Tama! Naiguhit mo ang linya.</p><button class="s7g3-primary" id="s7g3-next" type="button">${index === total ? 'TAPUSIN' : 'SUSUNOD'}</button><p class="s7g3-status s7g3-status--${kind || 'good'}" role="status">${escapeHtml(message)}</p></div></div>`;
      app.querySelector('#s7g3-next').addEventListener('click', next);
      return;
    }
    if (!item) { void completeActivity(); return; }
    updateExpected(item.word);
    const expected = `<span class="s7g3-sr" data-expected-text="${escapeHtml(item.word)}">${escapeHtml(item.word)}</span>`;
    if (state.phase === 'oral_reading') {
      const recovery = (state.stt_attempts[indexKey(index)] || 0) >= 3;
      app.innerHTML = `<div class="s7g3-layout">${header()}<div class="s7g3-stage">${expected}<p class="s7g3-cue">Larawan ${index + 1} sa ${total}</p><div class="s7g3-picture-frame"><img class="s7g3-picture" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.alt_text)}"></div>${recovery ? '<p class="s7g3-cue">Pakinggan muna ang salita.</p>' : ''}<button data-basahin-button class="s7g3-primary${recovery ? ' s7g3-primary--gold' : ''}" id="s7g3-oral" type="button">${recovery ? 'Pakinggan' : window.BasahinButton?.LABEL || 'Basahin'}</button><p class="s7g3-status s7g3-status--${kind}" role="status">${escapeHtml(message)}</p></div></div>`;
      const button = app.querySelector('#s7g3-oral');
      if (recovery) button.addEventListener('click', () => listen(index, item));
      else window.Basahin?.bindActivity?.(button, () => read(index, item));
      return;
    }
    const selected = state.selected_answer || '';
    app.innerHTML = `<div class="s7g3-layout">${header()}<div class="s7g3-stage">${expected}<p class="s7g3-cue">Piliin ang tamang salita at iguhit ang linya.</p><div class="s7g3-board"><div class="s7g3-board-picture"><img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.alt_text)}"></div><span class="s7g3-connector${selected ? '' : ' s7g3-connector--empty'}" aria-hidden="true"></span><div class="s7g3-choices" aria-label="Mga salitang pagpipilian">${item.choices.map(word => `<button class="s7g3-choice" type="button" data-choice="${escapeHtml(word)}" aria-pressed="${selected === word}">${escapeHtml(word)}</button>`).join('')}</div></div>${selected ? `<p class="s7g3-cue">Nakakonekta ang larawan sa <strong>${escapeHtml(selected)}</strong>.</p><button class="s7g3-primary s7g3-primary--gold" id="s7g3-connect" type="button">IGUHIT ANG LINYA</button>` : '<p class="s7g3-cue">Pumili ng isang salita.</p>'}<p class="s7g3-status s7g3-status--${kind}" role="status">${escapeHtml(message)}</p></div></div>`;
    app.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => selectAnswer(button.dataset.choice)));
    app.querySelector('#s7g3-connect')?.addEventListener('click', () => connect(selected));
    requestAnimationFrame(alignConnector);
  };
  const alignConnector = () => {
    const choices = app.querySelector('.s7g3-choices');
    const line = app.querySelector('.s7g3-connector:not(.s7g3-connector--empty)');
    const selected = app.querySelector('.s7g3-choice[aria-pressed="true"]');
    if (!choices || !line || !selected) return;
    const choiceBox = choices.getBoundingClientRect(), selectedBox = selected.getBoundingClientRect();
    line.style.transform = `translateY(${selectedBox.top + selectedBox.height / 2 - (choiceBox.top + choiceBox.height / 2)}px)`;
  };
  const save = async extra => {
    const mine = ++requestId;
    const lifecycle = generation;
    const response = await fetch(data.progress_url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({state:{...state,state_version:(Number(state.state_version) || 0) + 1},...(extra || {})})});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.success) throw new Error(payload.error || 'Hindi na-save ang progress. Subukan muli.');
    if (mine !== requestId || lifecycle !== generation) throw new DOMException('Activity cancelled', 'AbortError');
    state = payload.progress.state;
    return payload;
  };
  const withBusy = async task => {
    if (busy || paused) return;
    busy = true;
    try { await task(); }
    catch (error) { if (error.name !== 'AbortError') render(error.message || 'Subukan muli.', 'bad'); }
    finally { busy = false; app.setAttribute('aria-busy', 'false'); }
  };
  const begin = () => withBusy(async () => {
    stopAudio();
    state.phase = 'oral_reading';
    await save(); render();
    await play(data.local_audio?.prompts?.[items[0]?.word]);
  });
  const selectAnswer = answer => withBusy(async () => { state.selected_answer = answer; await save(); render(); });
  const read = (index, item) => withBusy(async () => {
    const mine = ++requestId;
    const button = app.querySelector('#s7g3-oral');
    try {
      stopAudio();
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Hindi available ang mikropono.');
      button.disabled = true;
      window.BasahinButton?.setState?.(button, 'waiting');
      stream = await window.Basahin.openMicrophone({audio:true});
      if (mine !== requestId) { stopStream(); return; }
      const recording = await window.Basahin.capture({button,stream});
      stopStream();
      if (mine !== requestId) return;
      window.BasahinButton?.setState?.(button, 'processing');
      const form = new FormData();
      form.append('audio', recording, 'session7-lesson20-21-gawain3.webm');
      window.Basahin.attachStreamResult?.(form, recording);
      form.append('target_text', item.word); form.append('language', 'Filipino'); form.append('mode', 'reading');
      form.append('prescribed_activity_key', data.activity_key);
      const response = await fetch(data.transcribe_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await response.json().catch(() => ({}));
      if (mine !== requestId) return;
      if (!response.ok || result.success !== true || result.complete !== true) throw new Error(result.error || 'Hindi pa. Subukan muli.');
      state.completed_oral_reads = [...new Set([...state.completed_oral_reads,index])];
      state.stt_attempts[indexKey(index)] = 0; state.tts_plays[indexKey(index)] = 0; state.phase = 'connection';
      await save(); render('Tama ang pagbasa! Piliin ang salita.', 'good');
      await speakFeedback('read_success');
      await play(data.local_audio?.intro);
    } catch (error) {
      if (mine !== requestId || error.name === 'AbortError') return;
      if (!window.Basahin?.isCaptureError?.(error)) state.stt_attempts[indexKey(index)] = Math.min(3, (state.stt_attempts[indexKey(index)] || 0) + 1);
      try { await save(); } catch (_) { /* Preserve the speech error below. */ }
      const recovery = (state.stt_attempts[indexKey(index)] || 0) >= 3;
      await speakFeedback(recovery ? 'listen' : 'retry');
      render(recovery ? 'Pakinggan muna ang salita.' : (error.message || 'Hindi nakuha ang boses. Subukan muli.'), 'bad');
    } finally { stopStream(); }
  });
  const listen = (index, item) => withBusy(async () => {
    const mine = ++requestId;
    const button = app.querySelector('#s7g3-oral');
    try {
      stopAudio(); button.disabled = true; button.textContent = 'Nilo-load…';
      const form = new FormData(); form.append('text', item.word); form.append('language', 'Filipino'); form.append('prescribed_activity_key', data.activity_key);
      const response = await fetch(data.read_aloud_url, {method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form});
      const result = await response.json().catch(() => ({}));
      if (mine !== requestId) return;
      if (!response.ok || result.success !== true || result.tts_language !== 'fil-PH' || result.voice_name !== 'fil-PH-Wavenet-A') throw new Error(result.error || 'Hindi available ang Filipino audio.');
      const objectUrl = URL.createObjectURL(new Blob([Uint8Array.from(atob(result.audio_content || ''), char => char.charCodeAt(0))], {type:result.mime_type || 'audio/mpeg'}));
      if (!await play(objectUrl)) throw new Error('Hindi ma-play ang audio.');
      if (mine !== requestId) return;
      state.tts_plays[indexKey(index)] = Math.min(3, (state.tts_plays[indexKey(index)] || 0) + 1);
      if (state.tts_plays[indexKey(index)] === 3) { state.stt_attempts[indexKey(index)] = 0; state.tts_plays[indexKey(index)] = 0; }
      await save(); render('Subukan mong basahin ang salita.');
    } catch (error) { if (mine === requestId) render(error.message || 'Hindi available ang audio. Subukan muli.', 'bad'); }
  });
  const connect = answer => withBusy(async () => {
    try {
      const payload = await save({candidate_answer:answer});
      if (!payload?.accepted) { state.selected_answer = ''; render('Hindi ito ang tamang salita. Subukan muli.', 'bad'); await speakFeedback('wrong'); return; }
      state.phase = 'feedback'; render('Tama! Naiguhit mo ang linya.', 'good'); await speakFeedback('matching_success');
    } catch (error) { if (error.name !== 'AbortError') render(error.message, 'bad'); }
  });
  const completeActivity = () => withBusy(async () => {
    try {
      stopAudio(); state.phase = 'completion';
      const response = await fetch(data.completion_url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) throw new Error(payload.error || 'Hindi na-save ang pagtatapos.');
      data.progress = {...data.progress,activity_completed:true}; render(); await speakFeedback('completion');
    } catch (error) { state.phase = 'feedback'; render(error.message, 'bad'); }
  });
  const next = () => {
    if (currentIndex() === total) return completeActivity();
    return withBusy(async () => { stopAudio(); state.phase = 'oral_reading'; state.selected_answer = ''; await save(); render(); await play(data.local_audio?.prompts?.[currentItem()?.word]); });
  };
  const startAfterModal = event => {
    if (event.detail?.activityKey !== data.activity_key) return;
    started = true; app.setAttribute('aria-busy', 'false'); render();
    const item = currentItem();
    const cue = state.phase === 'oral_reading' ? data.local_audio?.prompts?.[item?.word] : state.phase === 'completion' ? audio('feedback', 'completion') : data.local_audio?.intro;
    void withBusy(() => play(cue));
  };
  window.addEventListener('lesson-start-ready', startAfterModal);
  window.addEventListener('session7-prescribed-cancel', cancel);
  window.addEventListener('prescribed-session-paused', () => { paused = true; cancel(); });
  window.addEventListener('prescribed-session-resumed', () => { paused = false; render(); const cue = state.phase === 'oral_reading' ? data.local_audio?.prompts?.[currentItem()?.word] : state.phase === 'connection' || state.phase === 'intro' ? data.local_audio?.intro : audio('feedback', state.phase === 'feedback' ? 'matching_success' : 'completion'); void withBusy(() => play(cue)); });
  document.getElementById('prescribed-s7-l20-21-g3-help-btn')?.addEventListener('click', cancel);
  document.getElementById('prescribed-s7-l20-21-g3-restart-yes')?.addEventListener('click', cancel);
  document.querySelector('.s7g3-back')?.addEventListener('click', cancel);
  window.addEventListener('resize', () => requestAnimationFrame(alignConnector));
  window.addEventListener('pagehide', cancel, {once:true});
  window.__session7LeaveAdapter = {saveCurrentProgress:() => save(),cleanup:cancel};
  window.setTimeout(() => { if (!window.__session7IntroModalOpen && !started) startAfterModal({detail:{activityKey:data.activity_key,resumed:false}}); }, 0);
})();
