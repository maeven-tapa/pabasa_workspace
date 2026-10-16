(() => {
  'use strict';
  const node = document.getElementById('prescribed-activity-data'), app = document.getElementById('app');
  if (!node || !app) return;
  if (!document.getElementById('lesson29-activity3-refinement')) {
    const refinement = document.createElement('link');
    refinement.id = 'lesson29-activity3-refinement';
    refinement.rel = 'stylesheet';
    refinement.href = '/static/pabasa_app/css/lesson29_activity3_refinement.css?v=lesson29-a3-ui-21';
    document.head.appendChild(refinement);
  }
  const data = JSON.parse(node.textContent || '{}'), total = data.items?.length || 0;
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const retryPromptAudio = '/static/pabasa_app/audio/lesson_29_retry_or_proceed.mp3';
  const traceRetryAudio = '/static/pabasa_app/audio/lesson_29_try_again_write_both.mp3';
  const nextLetterAudio = '/static/pabasa_app/audio/lesson_29_next_letter.mp3';
  let state = {...(data.progress?.state || {})}, busy = false, canvas, ctx, strokes = [], activeStroke = null;
  let paused = false, muted = false, speechAbort = null;
  const audioPlayer = window.PrescribedAudioPlayer.create();
  const pendingWrites = new Set();
  const current = token => audioPlayer.isCurrent(token) && !paused;
  async function write(task) {
    pendingWrites.add(task);
    try { return await task; }
    finally { pendingWrites.delete(task); }
  }
  window.__session13RestartAdapters ||= {};
  window.__session13RestartAdapters['prescribed-s13l29g3'] = {
    async waitForPendingSaves() { await Promise.all([...pendingWrites]); },
  };
  const hydrate = () => { state.current_item = Math.max(0, Number(state.current_item || 0)); state.phase ||= 'sound'; state.traces = Array.isArray(state.traces) ? state.traces : []; state.draft_item = Number(state.draft_item ?? state.current_item); state.draft_strokes = Array.isArray(state.draft_strokes) ? state.draft_strokes : []; };
  const post = (url, body) => write((async () => { const r = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)}); const j = await r.json().catch(()=>({})); if (!r.ok || !j.success) throw Error(j.error || 'Could not save your progress.'); if (j.progress?.state) state = {...j.progress.state}; hydrate(); return j; })());
  const tracesForCurrent = () => state.traces.slice(state.current_item * 3, state.current_item * 3 + 3);
  const progress = () => `<div class="progress">${data.items.map((_, i) => `<span class="step ${i < state.current_item ? 'done' : ''} ${i === state.current_item && state.phase !== 'awaiting_teacher' ? 'active' : ''}">${i + 1}</span>`).join('')}</div>`;
  const playFile = src => audioPlayer.play(src);
  async function saveRecording(blob, itemIndex) { const form = new FormData(); form.append('audio', blob, blob.type.includes('ogg') ? 'lesson-29-letter-sound.ogg' : 'lesson-29-letter-sound.webm'); form.append('item_index', itemIndex); form.append('duration_seconds', Math.ceil((blob.size || 0) / 16000)); const r = await fetch(data.recording_url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:form}); const j = await r.json().catch(()=>({})); if (!r.ok || !j.success) throw Error(j.error || 'Could not save your recording.'); }
  function render(message='', kind='') {
    hydrate(); const stage = document.getElementById('lesson29a3-stage');
    if (state.phase === 'awaiting_teacher' || state.submitted && state.current_item >= total) { stage?.classList.remove('is-tracing'); app.innerHTML = `<div class="complete"><div><h1>Attempt submitted</h1><p>Your teacher will review your recordings and tracing. Please wait for their verdict.</p></div></div>`; return; }
    if (data.progress?.activity_completed || state.checked) { window.PrescribedLessonUi?.showCompletion(app); return; }
    const item = data.items[state.current_item], tracing = state.phase === 'trace', recorded = state.phase === 'recorded'; stage?.classList.toggle('is-tracing', tracing);
    const controls = tracing ? `<div class="board"><span class="trace-model" aria-hidden="true">${esc(item.letter)}</span><canvas id="trace-board" aria-label="Trace ${esc(item.letter)}"></canvas></div><p class="trace-count" id="trace-count" aria-live="polite">0 of 2 letters complete</p><div class="actions"><button class="button secondary" id="clear" type="button">Clear</button><button class="button" id="submit" type="button" disabled>Done tracing</button></div>` : recorded ? `<p class="status good">Your recording was saved.</p><div class="actions"><button class="button secondary" id="retry" type="button">Retry</button><button class="button" id="proceed" type="button">Submit</button></div>` : `<p class="status ${kind}" id="status">${esc(message || `Say the sound /${item.sound}/.`)}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="record" type="button">Record my sound</button><button class="button secondary" id="listen" type="button">🔊 Listen</button></div>`;
    const decisionPrompt = recorded ? '<p class="retry-proceed-prompt">Do you want to retry or proceed to the letter tracing?</p>' : '';
    const traceAttempt = Math.min(3, (state.traces?.length || 0) % 3 + 1);
    app.innerHTML = `<div class="eyebrow">SESSION 13 · LESSON 29 · ACTIVITY 3</div><p class="instruction">${tracing ? 'Trace both letters.' : 'Read the letter sound aloud first.'}</p>${decisionPrompt}<p class="item-label">Letter ${state.current_item + 1} of ${total}${tracing ? ` · Trace ${traceAttempt} of 3` : ''}</p><div class="letter">${esc(item.letter)}</div>${controls}<p class="status ${tracing ? kind : ''}">${tracing ? esc(message || 'Write both letters, then tap Done tracing.') : ''}</p>${progress()}`;
    if (tracing) { if (!strokes.length && state.draft_item === state.current_item) strokes = state.draft_strokes.map(stroke => stroke.map(point => ({...point}))); setupCanvas(); }
    else if (recorded) { app.querySelector('#retry').onclick = retryRecording; app.querySelector('#proceed').onclick = proceedToTracing; if (!paused) playFile(retryPromptAudio).catch(() => {}); }
    else { window.Basahin.bindActivity(app.querySelector('#record'), record); app.querySelector('#listen').onclick = () => speak(item.sound); }
  }
  function cancelActivity() {
    audioPlayer.cancel();
    speechAbort?.abort();
    window.Basahin?.cancelAll();
    busy = Boolean(pendingWrites.size);
  }
  async function speak(text) {
    if (busy || paused || pendingWrites.size) return;
    const token = audioPlayer.generation;
    busy = true;
    try {
      await audioPlayer.play(async signal => {
        const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', signal,
          headers:{'X-CSRFToken':csrf(), 'Content-Type':'application/x-www-form-urlencoded'},
          body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-29-gawain-3'})});
        const result = await response.json();
        if (!response.ok || !result.success || !result.audio_content) throw Error(result.error || 'Audio is unavailable.');
        return {url:'data:'+(result.mime_type || 'audio/mpeg')+';base64,'+result.audio_content};
      });
    } catch (error) {
      if (current(token) && error.name !== 'AbortError') render(error.message, 'bad');
    } finally { if (current(token)) busy = false; }
  }
  async function record() {
    if (busy || paused || muted || pendingWrites.size) return;
    // Stop the optional retry prompt before capturing a new sound.
    audioPlayer.cancel();
    const token = audioPlayer.generation, itemIndex = state.current_item;
    const controller = speechAbort = new AbortController();
    const button = app.querySelector('#record');
    let stream;
    busy = true;
    try {
      stream = await window.Basahin.openMicrophone({audio:{echoCancellation:true, noiseSuppression:false, autoGainControl:true}}, {signal:controller.signal});
      if (!current(token)) return;
      const blob = await window.Basahin.capture({stream, signal:controller.signal, streaming:false, button,
        keepStream:false, silenceMs:900, maxRecordingMs:6000});
      if (!current(token)) return;
      if (!blob?.size) throw Error('No voice was recorded.');
      // Capture is finished. Muting during the upload must not invalidate the
      // committed recording's UI update or leave its busy flag set forever.
      if (speechAbort === controller) speechAbort = null;
      // Once upload starts, finish its progress save before reset or leaving.
      await write((async () => {
        await saveRecording(blob, itemIndex);
        await post(data.progress_url, {action:'recorded', item_index:itemIndex});
      })());
      if (current(token)) render();
    } catch (error) {
      if (current(token) && error.name !== 'AbortError') render(error.message || 'I could not record your voice. Try again.', 'bad');
    } finally {
      stream?.getTracks().forEach(track => track.stop());
      if (speechAbort === controller) speechAbort = null;
      if (current(token)) { busy = false; window.BasahinButton?.setState(button, 'idle'); }
    }
  }
  async function proceedToTracing() {
    if (busy || paused || pendingWrites.size) return;
    cancelActivity();
    const token = audioPlayer.generation;
    busy = true;
    try {
      await post(data.progress_url, {action:'read_sound', item_index:state.current_item});
      if (!current(token)) return;
      render(); busy = false;
      await speak('Great! Now trace the letter three times.');
    } catch (error) { if (current(token)) render(error.message, 'bad'); }
    finally { if (current(token)) busy = false; }
  }
  async function retryRecording() {
    if (busy || paused || pendingWrites.size) return;
    cancelActivity();
    const token = audioPlayer.generation;
    busy = true;
    try {
      await post(data.progress_url, {action:'retry_sound', item_index:state.current_item});
      if (current(token)) render('Record a new attempt to replace the previous one.');
    } catch (error) { if (current(token)) render(error.message, 'bad'); }
    finally { if (current(token)) busy = false; }
  }
  function setupCanvas() { canvas=document.getElementById('trace-board'); const submit=app.querySelector('#submit'),count=app.querySelector('#trace-count'); const groupCount=()=>new Set(strokes.filter(stroke=>stroke.length>=2).map(stroke=>stroke.reduce((sum,point)=>sum+point.x,0)/stroke.length < .5 ? 0 : 1)).size; const updateGate=()=>{const completed=groupCount();if(count)count.textContent=`${completed} of 2 letters complete`;if(submit)submit.disabled=completed<2||Boolean(activeStroke);}; const resize=()=>{const r=canvas.getBoundingClientRect(),d=devicePixelRatio||1; canvas.width=Math.max(1,Math.round(r.width*d));canvas.height=Math.max(1,Math.round(r.height*d));ctx=canvas.getContext('2d');ctx.setTransform(d,0,0,d,0,0);ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#183e63';ctx.lineWidth=6;draw();}; const point=e=>{const r=canvas.getBoundingClientRect();return{x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))}}; resize(); canvas.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse'&&e.button!==0)return;canvas.setPointerCapture(e.pointerId);activeStroke=[point(e)];strokes.push(activeStroke);draw();updateGate();});canvas.addEventListener('pointermove',e=>{if(!activeStroke)return;activeStroke.push(point(e));draw();});const end=()=>{activeStroke=null;updateGate();};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);app.querySelector('#clear').onclick=()=>{strokes=[];activeStroke=null;draw();updateGate();};submit.onclick=submitTrace;updateGate();window.addEventListener('resize',resize,{once:true}); }
  function draw(){if(!ctx||!canvas)return;const w=canvas.clientWidth,h=canvas.clientHeight;ctx.clearRect(0,0,w,h);strokes.forEach(s=>{if(s.length<2)return;ctx.beginPath();s.forEach((p,i)=>i?ctx.lineTo(p.x*w,p.y*h):ctx.moveTo(p.x*w,p.y*h));ctx.stroke();});}
  async function submitTrace() {
    if (busy || paused || pendingWrites.size) return;
    const token = audioPlayer.generation, tracedItem = state.current_item;
    busy = true;
    try {
      await write((async () => {
        await post(data.progress_url, {action:'save_trace', item_index:tracedItem, strokes});
        strokes = [];
        if (state.current_item >= total) { await post(data.submission_url, {}); state.phase = 'awaiting_teacher'; }
      })());
      if (!current(token)) return;
      render(state.current_item === tracedItem ? 'Nice tracing! Trace both letters again.' : 'Nice tracing!', 'good');
      busy = false;
      await speak('Nice tracing!');
    } catch (error) {
      if (!current(token)) return;
      strokes = [];
      render('Try again. Write both letters clearly.', 'bad');
      busy = false;
      await playFile(traceRetryAudio).catch(() => {});
    } finally { if (current(token)) busy = false; }
  }
  async function leave(e){e.preventDefault();if(busy)return;busy=true;try{await post(data.progress_url,{reset:true});location.reload();}catch(err){busy=false;alert(err.message||'Could not reset the activity.');}}
  document.getElementById('lesson29a3-later').addEventListener('click',leave);
  document.getElementById('lesson29a3-go').addEventListener('click',async()=>{
    document.getElementById('lesson29a3-start').hidden=true;
    document.getElementById('lesson29a3-stage').classList.remove('waiting');
    render(); await speak('Trace and Say. Say each letter sound, then trace the letter three times.');
  });
  const prefix = 'session13-prescribed-s13l29g3';
  const pause = () => { paused = true; cancelActivity(); };
  window.addEventListener('pagehide', pause);
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
  for (const event of ['pause', 'help', 'cleanup', 'restart']) window.addEventListener(`${prefix}-${event}`, pause);
  window.addEventListener(`${prefix}-resume`, async () => {
    if (!paused) return;
    paused = false;
    const token = audioPlayer.generation;
    busy = true;
    await Promise.allSettled([...pendingWrites]);
    if (current(token)) { busy = false; render(); }
  });
  window.addEventListener(`${prefix}-mute`, event => {
    muted = Boolean(event.detail?.muted);
    if (muted && speechAbort) cancelActivity();
  });
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters['prescribed-s13l29g3'] = {
    async saveCurrentProgress() {
      await Promise.all([...pendingWrites]);
      if (state.phase === 'trace') await post(data.progress_url, {action:'save_draft_trace', item_index:state.current_item, strokes});
    },
    cleanup: pause,
  };
  hydrate(); render();
})();
