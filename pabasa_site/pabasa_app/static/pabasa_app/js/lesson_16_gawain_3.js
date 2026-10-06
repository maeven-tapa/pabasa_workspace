(() => {
  'use strict';
  const dataNode = document.getElementById('prescribed-activity-data');
  const app = document.getElementById('l16g3-app');
  if (!dataNode || !app) return;
  const data = JSON.parse(dataNode.textContent || '{}');
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const audioBase = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_16/GAWAIN_3/';
  const retryCue = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_7/pakinggan_muna_ang_salita_tts.mp3';
  const tryCue = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_7/subukan_mong_basahin_salita_tts.mp3';
  const readPrompts = ['01_item_01_sanga_match_prompt.mp3','03_item_02_goma_match_prompt.mp3','05_item_03_bunga_match_prompt.mp3','07_item_04_panga_match_prompt.mp3','09_item_05_gamot_match_prompt.mp3'];
  const wordAudio = ['02_item_01_sanga_word.mp3','04_item_02_goma_word.mp3','06_item_03_bunga_word.mp3','08_item_04_panga_word.mp3','10_item_05_gamot_word.mp3'];
  let progress = data.progress || {};
  let state = progress.state || {};
  let screen = data.screen || {};
  let busy = false, paused = false, generation = 0, stream = null, controller = null;
  let pendingProgressSave = Promise.resolve();
  let restartPending = false;
  let audioPlayer = null;
  const total = 5;
  const request = async (url, body, signal) => {
    const response = await fetch(url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body),...(signal?{signal}:{})});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) throw new Error(result.error || 'Hindi na-save ang iyong progreso. Subukang muli.');
    return result;
  };
  const send = body => {
    const operation = request(data.progress_url, body, controller?.signal);
    pendingProgressSave = operation;
    return operation;
  };
  const cancelWork = () => {
    generation += 1;
    controller?.abort(); controller = null;
    stream?.getTracks().forEach(track => track.stop()); stream = null;
    if (audioPlayer) { audioPlayer.pause(); audioPlayer.currentTime = 0; audioPlayer = null; }
    window.Basahin?.cancelAll?.();
  };
  const play = async (source, expectedGeneration = generation) => {
    if (!source || expectedGeneration !== generation) return;
    if (audioPlayer) { audioPlayer.pause(); audioPlayer = null; }
    const player = new Audio(source); audioPlayer = player;
    await new Promise((resolve, reject) => {
      player.addEventListener('ended', resolve, {once:true});
      player.addEventListener('pause', resolve, {once:true});
      player.addEventListener('error', () => reject(new Error('Hindi ma-play ang nakatalagang Filipino audio.')), {once:true});
      player.play().catch(reject);
    });
    if (audioPlayer === player) audioPlayer = null;
  };
  const playSequence = async (sources, gen = generation) => { for (const source of sources) { if (gen !== generation) return; await play(source, gen); } };
  const sync = result => {
    progress = result.progress || progress;
    state = progress.state || state;
    screen = result.screen || screen;
  };
  const header = (title, sub, phaseName, index) => {
    const current = Math.min(index, total - 1);
    const count = Math.min(index + 1, total);
    const marks = Array.from({length:total}, (_, i) => `<i class="${i < index ? 'is-done' : i === current ? 'is-current' : ''}" aria-hidden="true"></i>`).join('');
    return `<p class="l16g3-eyebrow">Session 6 · Lesson 16 · Gawain 3</p><h1 id="l16g3-title">${title}</h1><p class="l16g3-instruction">${sub}</p><p class="l16g3-progress-label">${phaseName}: ${count} sa ${total}</p><div class="l16g3-progress" role="img" aria-label="${phaseName}: ${count} sa ${total}">${marks}</div>`;
  };
  const status = (message='', kind='') => `<p class="l16g3-status ${kind}" id="l16g3-status" role="status" aria-live="polite">${esc(message)}</p>`;
  const render = (message='', kind='') => {
    if (progress.activity_completed || state.phase === 'complete') { renderComplete(); return; }
    if (state.phase === 'matching') { renderMatching(message,kind); return; }
    renderOral(message,kind);
    window.dispatchEvent(new CustomEvent('session6-prescribed-render'));
  };
  const renderOral = (message='',kind='') => {
    const idx = Number(state.oral_index || 0);
    app.innerHTML = header('Basahin ang Salita','Tingnan ang larawan at basahin nang malakas ang salita.','Pagbasa',idx)
      + `<div class="l16g3-visual-panel"><img class="l16g3-picture" src="${esc(screen.oral_image_url || '')}" alt="" aria-hidden="true"></div><p class="l16g3-word oral-word">${esc(screen.current_word || '')}</p><button class="l16g3-action" id="oral" type="button" data-basahin-button ${busy?'disabled':''}>${busy?'NAKIKINIG…':'BASAHIN'}</button>${status(message,kind)}`;
    const button = document.getElementById('oral');
    if (button) window.Basahin?.bindActivity(button, readCurrent);
  };
  const renderMatching = (message='',kind='') => {
    const idx = Number(state.matching_index || 0);
    if (idx >= total) {
      app.innerHTML = header('Piliin ang Larawang Katugma ng Salita','Nai-save na ang lahat ng tamang tugma.','Pagtutugma',idx)
        + `<button class="l16g3-action" id="l16g3-retry-complete" type="button" ${busy?'disabled':''}>Subukang muli</button>${status(message || 'Hindi natapos ang pag-save. Pindutin muli upang subukang muli.','is-error')}`;
      document.getElementById('l16g3-retry-complete').addEventListener('click', finishCompletion);
      return;
    }
    const choices = (screen.picture_choices || []).map((choice,i) => `<button class="l16g3-choice" type="button" data-picture="${esc(choice.id)}" aria-label="Larawan ${i+1}" ${busy?'disabled':''}><img src="${esc(choice.image_url)}" alt="" aria-hidden="true"></button>`).join('');
    app.innerHTML = header('Piliin ang Larawang Katugma ng Salita','Piliin ang larawang tumutugma sa salita.','Pagtutugma',idx)
      + `<p class="l16g3-word oral-word">${esc(screen.current_word || '')}</p><div class="l16g3-choices" aria-label="Mga pagpipiliang larawan">${choices}</div>${status(message,kind)}`;
    app.querySelectorAll('[data-picture]').forEach(button => button.addEventListener('click', () => submitPicture(button.dataset.picture, button)));
    if (kind === 'is-error' && screen.last_picture_id) {
      Array.from(app.querySelectorAll('[data-picture]')).find(button => button.dataset.picture === screen.last_picture_id)?.classList.add('is-incorrect');
    }
  };
  const renderComplete = () => {
    app.innerHTML = `<div class="l16g3-complete"><span class="l16g3-star" aria-hidden="true">⭐</span><p class="l16g3-eyebrow">Session 6 · Lesson 16 · Gawain 3</p><h1 id="l16g3-title">Magaling!</h1><p class="l16g3-instruction">Natapos mo ang gawain.</p><a class="l16g3-action" href="${esc(data.back_url)}">BALIK SA AKING ARALIN</a>${status()}</div>`;
  };
  async function readCurrent() {
    if (busy || state.phase === 'matching') return;
    busy = true; const gen = generation; controller = new AbortController();
    renderOral('Nakikinig sa iyong pagbasa…');
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !window.Basahin) throw new Error('Hindi available ang mikropono sa device na ito. Maaari mong subukang muli.');
      stream = await window.Basahin.openMicrophone({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}},{signal:controller.signal});
      const blob = await window.Basahin.capture({button:document.getElementById('oral'),stream,signal:controller.signal});
      if (gen !== generation) return;
      const form = new FormData(); form.append('audio',blob,'lesson16-gawain3-reading.webm');
      form.append('target_text',screen.current_word); form.append('language','Filipino'); form.append('mode','reading');
      form.append('prescribed_activity_key','lesson-16-gawain-3');
      const response = await fetch(data.transcribe_url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf()},body:form,signal:controller.signal});
      const verdict = await response.json().catch(() => ({}));
      if (gen !== generation) return;
      if (!response.ok || !verdict.success) throw new Error(verdict.error || 'Hindi nasuri ang pagbasa. Subukang muli.');
      if (verdict.complete !== true || !verdict.verification_token) {
        renderOral('Subukan mong basahin muli.','is-error');
        await playSequence([audioBase+'12_feedback_reading_retry.mp3',retryCue,audioBase+wordAudio[Number(state.oral_index||0)]],gen);
        return;
      }
      if (verdict.complete !== true || !verdict.verification_token) throw new Error('Hindi napatunayan ang pagbasa. Subukang muli.');
      const advanced = await send({action:'advance_oral',verification_token:verdict.verification_token});
      if (gen !== generation) return;
      sync(advanced);
      if (state.phase === 'matching') {
        render();
        await play(audioBase+'11_feedback_reading_correct.mp3',gen);
        await play(audioBase+'13_matching_start_prompt.mp3',gen);
      } else {
        renderOral('Tama ang pagbasa!','is-good');
        const next = Number(state.oral_index || 0);
        const audio = [audioBase+'11_feedback_reading_correct.mp3',audioBase+readPrompts[next]];
        await playSequence(audio,gen);
        render();
      }
    } catch (error) {
      if (gen === generation && error.name !== 'AbortError') renderOral(error.message || 'Hindi na-save ang progreso. Pindutin muli ang BASAHIN.','is-error');
    } finally {
      stream?.getTracks().forEach(track => track.stop()); stream = null; controller = null; busy = false;
      if (gen === generation && state.phase !== 'complete') render();
    }
  }
  async function submitPicture(pictureId, button) {
    if (busy) return;
    busy = true; const gen = generation; const activeController = new AbortController(); controller = activeController;
    app.querySelectorAll('.l16g3-choice').forEach(choice => { choice.disabled = true; });
    try {
      const result = await send({action:'match_picture',picture_id:pictureId});
      if (gen !== generation) return;
      sync(result);
      if (!result.accepted) {
        screen.last_picture_id = pictureId;
        render('Hindi iyon ang katugmang larawan. Subukan muli.','is-error');
        await play(audioBase+'15_feedback_matching_retry.mp3',gen);
      } else {
        delete screen.last_picture_id;
        button?.classList.add('is-correct');
        const live = app.querySelector('.l16g3-status');
        if (live) { live.textContent = 'Tama!'; live.className = 'l16g3-status is-good'; }
        if (button) button.setAttribute('aria-pressed','true');
        if (state.matching_index >= total) {
          if (live) live.textContent = 'Tama! Inililigtas ang iyong natapos na gawain…';
          await play(audioBase+'14_feedback_matching_correct.mp3',gen);
          if (gen !== generation) return;
          await finishCompletion(gen);
          if (gen !== generation) return;
        } else {
          await play(audioBase+'14_feedback_matching_correct.mp3',gen);
          if (gen !== generation) return;
          render();
        }
      }
    } catch (error) {
      if (gen === generation && error.name !== 'AbortError') render(error.message || 'Hindi na-save ang sagot. Subukang muli.','is-error');
    } finally {
      controller = null; busy = false;
      if (gen === generation && state.phase !== 'complete') app.querySelectorAll('.l16g3-choice').forEach(choice => { choice.disabled = false; });
    }
  }
  async function finishCompletion(expectedGeneration = generation) {
    if (expectedGeneration !== generation) return;
    busy = true;
    try {
      if (!controller) controller = new AbortController();
      await request(data.completion_url,{duration_seconds:1},controller.signal);
      if (expectedGeneration !== generation) return;
      progress = {...progress,activity_completed:true}; state = {...state,phase:'complete'};
      renderComplete();
    } catch (error) {
      if (expectedGeneration === generation) renderMatching(error.message || 'Hindi na-save ang pagtatapos. Pindutin muli upang subukang muli.','is-error');
      busy = false;
      return;
    }
    try { await play(audioBase+'16_feedback_completion.mp3',expectedGeneration); }
    catch (error) {
      if (expectedGeneration === generation) {
        const live = app.querySelector('.l16g3-status');
        if (live) { live.textContent = error.message || 'Hindi ma-play ang completion audio.'; live.classList.add('is-error'); }
      }
    } finally { busy = false; }
  }
  const startOrResume = async () => {
    if (busy) return;
    const fresh = state.phase === 'intro';
    busy = true;
    const gen = generation;
    controller = new AbortController();
    try {
      const restored = await send({action:'start'});
      if (gen !== generation) return;
      sync(restored);
      render();
      if (fresh) await playSequence([audioBase+'00_activity_intro.mp3',audioBase+readPrompts[0]],gen);
      else if (state.phase === 'matching' && Number(state.matching_index || 0) >= total) await finishCompletion(gen);
      else if (state.phase === 'oral_reading') await play(audioBase+readPrompts[Math.min(total-1,Number(state.oral_index||0))],gen);
    } catch (error) {
      if (gen === generation) render(error.message || 'Hindi naibalik ang gawain. Subukang muli.','is-error');
    } finally { controller = null; busy = false; if (gen === generation && state.phase !== 'complete') render(); }
  };
  window.addEventListener('lesson-start-ready', startOrResume);
  window.addEventListener('session6-prescribed-cancel', event => {
    if (event.detail?.reason === 'cleanup') {
      generation += 1;
      stream?.getTracks().forEach(track => track.stop()); stream = null;
      if (audioPlayer) { audioPlayer.pause(); audioPlayer.currentTime = 0; audioPlayer = null; }
      window.Basahin?.cancelAll?.();
      busy = false;
      return;
    }
    cancelWork(); busy = false;
    if (event.detail?.reason === 'pause') paused = true;
    if (event.detail?.reason === 'pause' || event.detail?.reason === 'navigation' || event.detail?.reason === 'restart') render();
  });
  window.addEventListener('session6-prescribed-resume', () => { if (paused) { paused = false; startOrResume(); } });
  document.getElementById(`prescribed-s6-${data.activity_key}-restart-yes`)
    ?.addEventListener('click', () => { restartPending = true; }, true);
  window.addEventListener('unhandledrejection', event => {
    if (!restartPending) return;
    restartPending = false;
    event.preventDefault();
    render('Hindi na-reset ang gawain. Subukang muli sa menu ng paghinto.','is-error');
  });
  window.addEventListener('pagehide', cancelWork,{once:true});
  window.__session6LeaveAdapter = {
    saveCurrentProgress: () => pendingProgressSave,
    cleanup: () => {
      generation += 1;
      stream?.getTracks().forEach(track => track.stop()); stream = null;
      if (audioPlayer) { audioPlayer.pause(); audioPlayer.currentTime = 0; audioPlayer = null; }
      window.Basahin?.cancelAll?.();
    },
  };
  render();
})();
