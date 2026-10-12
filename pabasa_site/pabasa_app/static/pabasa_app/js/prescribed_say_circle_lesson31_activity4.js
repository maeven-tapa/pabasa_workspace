(() => {
  const node = document.querySelector('#prescribed-activity-data');
  const app = document.querySelector('#app');
  if (!node || !app) return;
  const data = JSON.parse(node.textContent || '{}');
  const csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));
  let state = {...(data.progress?.state || {})}, busy = false, stream = null, flash = '', audio = null;
  let paused = false, muted = false, disposed = false, generation = 0, audioAbort = null, pendingSave = null;
  const pendingSaves = new Set();
  window.__session15RestartAdapters ||= {};
  window.__session15RestartAdapters.lesson31a4 = {async waitForPendingSaves() {
    const results = await Promise.allSettled([...pendingSaves]);
    const failure = results.find(result => result.status === 'rejected');
    if (failure) throw failure.reason;
  }};
  const isCurrent = token => token === generation && !paused && !disposed;
  // A cached history entry retains disposed controls and potentially stale
  // progress. Reload it through the normal saved-progress/start flow.
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
  const playbackCancelled = () => new DOMException('Activity playback cancelled.', 'AbortError');
  function cancel(speechHandledByControls = false) {
    generation++;
    audioAbort?.abort();
    audio?.pause();
    if (!speechHandledByControls) window.Basahin?.cancelAll();
    stream?.getTracks().forEach(track => track.stop());
    stream = null;
    busy = false;
    if (!disposed) render();
  }
  for (const event of ['cancel', 'pause', 'cleanup', 'restart']) {
    window.addEventListener('session15-lesson31a4-' + event, detailEvent => {
      if (event === 'pause') paused = true;
      if (event === 'cleanup' || event === 'restart') disposed = true;
      cancel(detailEvent.detail?.speechHandledByControls);
    });
  }
  window.addEventListener('session15-lesson31a4-resume', () => { if (disposed) return; paused = false; window.__session15SilentCancel = false; render(); });
  const pauseModal = document.getElementById('lesson31a4-pause-modal');
  pauseModal?.addEventListener('click', event => {
    if (event.target === pauseModal) window.dispatchEvent(new Event('session15-lesson31a4-resume'));
  });
  const restartModal = document.getElementById('lesson31a4-restart-modal');
  restartModal?.addEventListener('click', event => {
    if (event.target === restartModal && pauseModal) pauseModal.hidden = false;
  });
  window.addEventListener('keydown', event => {
    const restartModal = document.getElementById('lesson31a4-restart-modal');
    if (event.key === 'Escape' && restartModal && !restartModal.hidden && pauseModal) pauseModal.hidden = false;
  });
  window.addEventListener('session15-lesson31a4-mute', event => {
    muted = Boolean(event.detail?.muted);
    if (muted) cancel(event.detail?.speechHandledByControls);
  });

  const hydrate = () => { state.current_item = Number(state.current_item || 0); state.attempts = Number(state.attempts || 0); state.phase ||= 'reading'; };
  const steps = () => `<div class="progress">${data.items.map((_, index) => `<span class="step ${index < state.current_item ? 'done' : ''} ${index === state.current_item ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;
  async function save(body) {
    const token = generation;
    const task = (async () => { const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body)}),result=await response.json();if(!response.ok||!result.success)throw Error(result.error||'Could not save progress.');state={...result.progress.state};hydrate();return result; })();
    pendingSave = task;
    pendingSaves.add(task);
    try {return await task;}
    finally {
      pendingSaves.delete(task);
      if (pendingSave === task) pendingSave = null;
      // A request already sent may commit during cancellation. Keep its
      // authoritative state visible without replaying the cancelled feedback.
      if (token !== generation && !paused && !disposed) render();
    }
  }
  async function speak(text) {
    if (busy || paused || disposed || !text) return;
    const token = generation, controller = new AbortController();
    let playback = null, playbackUrl = null;
    audioAbort = controller;
    busy = true;
    const buttons = [...app.querySelectorAll('.button')];
    const states = buttons.map(button => ({button, disabled:button.disabled}));
    buttons.forEach(button => { button.disabled = true; button.classList.add('is-busy'); });
    try {
      const response = await fetch(data.read_aloud_url, {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{'X-CSRFToken':csrf(), 'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-31-gawain-4'})
      });
      const body = await response.text();
      if (!isCurrent(token)) throw playbackCancelled();
      let result;
      try { result = JSON.parse(body); }
      catch (_) { throw new Error('Read aloud is temporarily unavailable. Please try again.'); }
      if (!isCurrent(token)) throw playbackCancelled();
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio.');
      const bytes = Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0));
      playbackUrl = URL.createObjectURL(new Blob([bytes], {type:result.mime_type || 'audio/mpeg'}));
      playback = new Audio(playbackUrl);
      audio = playback;
      await new Promise((resolve, reject) => {
        playback.onended = resolve;
        playback.addEventListener('pause', resolve, {once:true});
        playback.onerror = () => reject(new Error('Audio playback failed.'));
        playback.play().catch(reject);
      });
      if (!isCurrent(token)) throw playbackCancelled();
    } finally {
      if (isCurrent(token)) {
        busy = false;
        states.forEach(({button, disabled}) => { if (button.isConnected) {button.disabled = disabled; button.classList.remove('is-busy');} });
      }
      if (playbackUrl) URL.revokeObjectURL(playbackUrl);
      if (audio === playback) audio = null;
      if (audioAbort === controller) audioAbort = null;
    }
  }

  function acknowledgeCompletion() {
    const task = fetch(data.completion_url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:'{}'});
    pendingSaves.add(task);
    task.finally(() => pendingSaves.delete(task)).catch(() => {});
  }
  function render(message='',kind=''){hydrate();if(state.phase==='complete'){window.PrescribedLessonUi.showCompletion(app);acknowledgeCompletion();return}const item=data.items[state.current_item],reading=state.phase==='reading';const header=`<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 4</div><h1 class="title">Say and Circle!</h1><p class="instruction">${reading?'Say the name of the picture.':'Box the beginning letter of its name.'}</p>`,picture=`<div class="picture"><img src="${esc(item.image_url)}" alt="${esc(item.alt_text)}"></div>`;let body;if(reading){const listen=Number(state.attempts||0)>=3?'<button class="button secondary" id="listen">🔊 Listen</button>':'<button class="button secondary" id="listen" disabled>🔊 Listen</button>';body=`<p class="status ${kind}">${esc(message||'Say the picture word aloud.')}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read">Read</button>${listen}</div>`}else{const choices=item.choices.map(letter=>`<button class="choice letter-choice ${flash===letter?'selected':''}" data-word="${esc(letter)}">${esc(letter)}</button>`).join('');body=`<div class="choices" aria-label="Beginning letter choices">${choices}</div><p class="status ${kind}">${esc(message||'Choose the beginning letter.')}</p>`}app.innerHTML=header+picture+body+steps();window.Basahin.bindActivity(app.querySelector('#read'), ()=>record(item.word));app.querySelector('#listen')?.addEventListener('click',()=>speak(item.word).catch(error=>{if(error?.name!=='AbortError'&&!paused&&!disposed)render(error.message,'bad')}));app.querySelectorAll('[data-word]').forEach(button=>button.onclick=()=>choose(button.dataset.word));}
  async function record(target){if(busy||pendingSave||paused||muted||disposed)return;const token=generation;if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)return render('Microphone recording is not available.','bad');busy=true;const read=app.querySelector('#read'),listen=app.querySelector('#listen');read?.classList.add('is-busy');if(listen)listen.disabled=true;try{const transcript = await window.Basahin.read({target_text:target, language:'English', mode:'reading', prescribed_activity_key:'lesson-31-gawain-4'}, {button:read, url:data.transcribe_url}); if(!isCurrent(token))return;const heard=transcript.raw_transcript||transcript.transcript||'';const result=await save({action:'read_word',heard});if(!isCurrent(token))return;busy=false;const debug=`Debug: target "${target}" | heard "${heard}"`;render(`${result.accepted?'Correct! Now box the beginning letter.':'Please try again.'} ${debug}`,result.accepted?'good':'bad');if(result.accepted){await speak('Correct!');await speak("Now, let's box the correct letter.");}else{await speak('Hmm, let’s try that again.')}}catch(error){ if (error?.name === 'AbortError' || !isCurrent(token)) return; busy=false;render(error.message||'Please try again.','bad');try{await speak('Hmm, let’s try that again.')}catch(_){}}finally{if(isCurrent(token)){stream?.getTracks().forEach(track=>track.stop());stream=null;read?.classList.remove('is-busy');if(listen?.isConnected)listen.disabled=Number(state.attempts||0)<3;busy=false;}}}
async function choose(word){if(busy||pendingSave||paused||disposed)return;const token=generation;busy=true;try{const result=await save({action:'choose',choice:word});if(!isCurrent(token))return;busy=false;if(result.accepted){flash=word;const complete=state.phase==='complete',feedback=complete?'Great job! You completed Say and Circle.':'Correct!';render(feedback,'good');await speak(feedback);if(!complete)await speak("Now, let's read the next picture.");if(!isCurrent(token))return;flash='';render()}else{const complete=state.phase==='complete';render("Let's move to the next picture.",'bad');await speak("Let's move to the next picture.");if(!complete)render()}}catch(error){if(error?.name!=='AbortError'&&isCurrent(token)){busy=false;render(error.message,'bad')}}finally{if(isCurrent(token))busy=false;}}
  async function leave(event){event.preventDefault();if(busy)return;try{await save({reset:true});window.location.reload()}catch(error){alert(error.message)}}
  document.querySelector('#lesson31a4-later').onclick=leave;document.querySelector('#lesson31a4-go').onclick=async()=>{document.querySelector('#lesson31a4-start').hidden=true;document.querySelector('#lesson31a4-stage').classList.remove('waiting');render();try{await speak('Say and circle. Say the name of each picture and box the beginning letter of its name.')}catch(error){if(error?.name!=='AbortError'&&!paused&&!disposed)render(error.message,'bad')}};window.addEventListener('pagehide',()=>{disposed=true;cancel()});hydrate();render();
})();
