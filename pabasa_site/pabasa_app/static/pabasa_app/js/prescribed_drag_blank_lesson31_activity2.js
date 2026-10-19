(() => {
  const app = document.querySelector('#app');
  const data = JSON.parse(document.querySelector('#prescribed-activity-data').textContent);
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const escape = value => String(value ?? '').replace(/[&<>]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));
  let state = {...(data.progress?.state || {})};
  let busy = false, paused = false, muted = false, generation = 0, audio = null;
  let started = false, listening = null, pendingPlayback = null, playbackSave = null, disposed = false;
  let choosingInstructionItem = null;
  function hydrate() {
    state.current_item = Number(state.current_item || 0);
    state.choice_index = Number(state.choice_index || 0);
    state.phase ||= 'reading_choices';
  }
  async function save(body) {
    const response = await fetch(data.progress_url, {method:'POST', credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'Could not save progress.');
    state = result.progress.state; hydrate(); return result;
  }
  async function flushPlayback() {
    if (playbackSave) return playbackSave;
    if (!pendingPlayback) return null;
    const payload = pendingPlayback;
    playbackSave = (async () => {
      try {
        const result = await save(payload);
        if (pendingPlayback === payload) pendingPlayback = null;
        // A cancellation can replace the playback owner while this legitimate
        // save is in flight. Keep the visible phase in sync even in that case.
        if (started && !paused && !disposed) render(state.phase==='dragging'?'Now drag the correct word to the blank.':'');
        return result;
      } finally {playbackSave = null;}
    })();
    return playbackSave;
  }
  const sentenceReader = window.PrescribedSentenceReading.create({key:'lesson-31-gawain-2',
    getState:() => state, save, url:data.transcribe_url,
    onRestore:() => {if (!paused && !busy && !disposed) render();},
    onFeedback:(result, heard) => window.dispatchEvent(new CustomEvent('session15-lesson31a2-debug', {detail:{
      status:result.continue_prompt?'Continue reading':result.accepted?'Correct':'Try again',
      result:result.continue_prompt?'Read the rest':result.accepted?'Correct':'Try again',
      transcript:heard, mic:'Inactive · Unmuted', recorder:'inactive', error:'—',
    }})),
  });
  async function say(text) {
    if (busy || paused || !text) return false;
    const token = generation; busy = true;
    const buttons = [...app.querySelectorAll('.actions button, .choices button')];
    const states = buttons.map(button => ({button, disabled:button.disabled, draggable:button.draggable}));
    buttons.forEach(button => {button.disabled=true; button.draggable=false; button.classList.add('is-busy');});
    let source = null, activeAudio = null;
    try {
      const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin',
        headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({target_text:text, language:'English', lesson_tts_key:'lesson-31-gawain-2'})});
      const result = await response.json();
      if (token !== generation || paused) return false;
      if (!response.ok || !result.success || !result.audio_content) throw new Error(result.error || 'Could not play audio.');
      source = URL.createObjectURL(new Blob([Uint8Array.from(atob(result.audio_content), char => char.charCodeAt(0))], {type:result.mime_type || 'audio/mpeg'}));
      activeAudio = new Audio(source); audio = activeAudio;
      const ended = await new Promise((resolve, reject) => {
        activeAudio.onended = () => resolve(true);
        activeAudio.addEventListener('ended', () => resolve(true), {once:true});
        // Native playback pauses at the end before firing "ended".
        activeAudio.addEventListener('pause', () => {if (!activeAudio.ended) resolve(false);}, {once:true});
        activeAudio.addEventListener('error', () => reject(new Error('Audio playback failed.')), {once:true});
        activeAudio.play().catch(reject);
      });
      return ended && token === generation && !paused;
    } finally {
      if (token === generation) {
        busy = false;
        states.forEach(({button, disabled, draggable}) => {if (button.isConnected) {button.disabled=disabled; button.draggable=draggable; button.classList.remove('is-busy');}});
      }
      if (source) URL.revokeObjectURL(source);
      if (audio === activeAudio) audio = null;
    }
  }
  const steps = () => `<div class="progress">${data.items.map((_, index) => `<span class="step ${index<state.current_item?'done':''} ${index===state.current_item?'active':''}">${index+1}</span>`).join('')}</div>`;
  function render(message = '', kind = '') {
    hydrate();
    if (state.phase === 'complete') {window.PrescribedLessonUi.showCompletion(app); return;}
    const item = data.items[state.current_item];
    if (state.phase === 'reading_choices') {
      const word = data.word_choices[state.choice_index], help = state.choice_attempts >= 3;
      app.innerHTML = `<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 2</div><h1 class="title">Fill in the Blank</h1><p class="instruction">Read each word aloud first.</p><div class="word">${escape(word)}</div><p class="status ${kind}">${escape(message || `Read word ${state.choice_index+1} of ${data.word_choices.length}.`)}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read">Read</button><button class="button secondary" id="listen" ${help?'':'disabled'}>🔊 Listen</button></div>${steps()}`;
      window.Basahin.bindActivity(app.querySelector('#read'), () => record(word, 'read_choice', {choice_index:state.choice_index}));
      app.querySelector('#listen').onclick = () => say(word).catch(error => render(error.message, 'bad'));
      return;
    }
    const reading = state.phase === 'reading_sentence', dragging = state.phase === 'dragging';
    const listeningToSentence = state.phase === 'sentence_listen';
    const placed = state.placed_word ? `<span class="blank correct">${escape(state.placed_word)}</span>` : '<span class="blank" id="blank"></span>';
    app.innerHTML = `<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 2</div><h1 class="title">Fill in the Blank</h1><p class="instruction">${listeningToSentence?'Listen to the sentence.':reading?'Read the whole sentence aloud.':'Drag the correct word to the blank.'}</p><div class="sentence ${reading?'prescribed-reading-sentence':''}">${reading?window.PrescribedSentenceReading.markup(item.sentence, Number(state.sentence_word_index || 0)):escape(item.before)+placed+escape(item.after)}</div>${dragging||listeningToSentence?`<div class="choices" aria-label="Word choices">${item.choices.map(word => `<button class="choice" type="button" draggable="${dragging}" data-w="${escape(word)}" ${dragging?'':'disabled'}>${escape(word)}</button>`).join('')}</div>`:''}<p class="status ${kind}" role="status">${escape(message || (listeningToSentence?'Listen to the sentence to unlock the word choices.':''))}</p><div class="actions">${listeningToSentence||dragging?'<button class="button secondary" id="retry-sentence">🔊 Listen to the sentence</button>':''}${reading?`<button data-basahin-button data-basahin-language="English" class="button" id="sentence">Read</button><button class="button secondary" id="help" ${state.sentence_attempts>=3?'':'disabled'}>🔊 Listen</button>`:''}</div>${steps()}`;
    if (dragging) {
      const blank = app.querySelector('#blank');
      app.querySelectorAll('[data-w]').forEach(button => {
        button.onclick = () => place(button.dataset.w);
        button.ondragstart = event => event.dataTransfer.setData('text', button.dataset.w);
      });
      blank.ondragover = event => event.preventDefault();
      blank.ondrop = event => {event.preventDefault(); place(event.dataTransfer.getData('text'));};
    }
    window.Basahin.bindActivity(app.querySelector('#sentence'), () => record(item.sentence, 'read_sentence'));
    app.querySelector('#help')?.addEventListener('click', () => say(item.sentence).catch(error => render(error.message, 'bad')));
    app.querySelector('#retry-sentence')?.addEventListener('click', () => replaySentence(item));
  }
  async function listenToSentence(item) {
    if (!started || busy || paused || listening || state.phase !== 'sentence_listen') return;
    const owner = {}, token = generation, index = state.current_item;
    const current = () => token===generation && !paused && state.current_item===index && state.phase==='sentence_listen';
    listening = owner;
    try {
      // Keep a finished playback pending across pause and network failures.
      // Resume/retry shares the in-flight save or repeats its exact receipt.
      if (!pendingPlayback) {
        if (choosingInstructionItem !== index) {
          if (!await say("Now, let's choose the word to fill in the blank.") || !current()) return;
          choosingInstructionItem = index;
        }
        if (!await say(item.sentence) || !current()) return;
        pendingPlayback = {action:'sentence_played', item_index:index, request_id:crypto.randomUUID()};
      }
      await flushPlayback();
    } catch (error) {
      if (current()) render(error.message + ' Choose Listen to the sentence to retry.', 'bad');
    } finally {
      if (listening===owner) listening=null;
      if (current()) {const retry=app.querySelector('#retry-sentence'); if (retry) {retry.disabled=false; retry.classList.remove('is-busy');}}
    }
  }
  async function replaySentence(item) {
    if (!started || busy || paused || disposed || listening) return;
    if (state.phase === 'sentence_listen') return listenToSentence(item);
    if (state.phase !== 'dragging') return;
    try {await say(item.sentence);}
    catch (error) {if (!paused && !disposed) render(error.message, 'bad');}
  }
  async function record(target, action, extra = {}) {
    if (busy || paused || muted) return;
    const token=generation, current=() => token===generation && !paused;
    busy=true;
    const read=app.querySelector('#read') || app.querySelector('#sentence');
    const listen=app.querySelector('#listen') || app.querySelector('#help');
    read?.classList.add('is-busy'); if (listen) listen.disabled=true;
    let feedback='';
    try {
      const sentence=action==='read_sentence';
      const transcript=sentence ? await sentenceReader.read(target, state.current_item, read, current)
        : await window.Basahin.read({target_text:target, language:'English', mode:'reading', prescribed_activity_key:'lesson-31-gawain-2'}, {button:read, url:data.transcribe_url});
      if (!current()) return;
      const result=sentence ? transcript : await save({action, heard:String(transcript.raw_transcript || transcript.transcript || ''), ...extra});
      if (!current()) return;
      if (result.continue_prompt) {
        render("Great! Now let's read the rest of the sentence.", 'good');
        app.querySelectorAll('button').forEach(button => button.disabled=true);
        await sentenceReader.playPrompt();
      } else {
        const correct=Boolean(result.accepted);
        feedback=correct ? (state.phase==='complete'?'Great job! You completed every sentence.':state.phase==='sentence_listen'?'':'Correct!') : 'Hmm, let’s try that again.';
        render(correct?'Correct!':'Please try again.', correct?'good':'bad');
        if (correct && state.phase==='sentence_listen') {
          busy=false; await say('Correct!'); if (!current()) return;
          await listenToSentence(data.items[state.current_item]);
        }
      }
    } catch (error) {
      if (!current() || error?.name==='AbortError') return;
      render(error.message || 'Please try again.', 'bad');
      feedback=state.phase==='sentence_listen'?'':'Hmm, let’s try that again.';
    } finally {
      if (token===generation) {
        busy=false; read?.classList.remove('is-busy');
        const activeRead=app.querySelector('#read') || app.querySelector('#sentence');
        if (activeRead) {activeRead.disabled=false; activeRead.classList.remove('is-busy');}
        const help=app.querySelector('#listen') || app.querySelector('#help');
        if (help) help.disabled=help.id==='listen'?state.choice_attempts<3:state.sentence_attempts<3;
      }
    }
    if (feedback && current()) await say(feedback).catch(error => {if (current()) render(error.message, 'bad');});
  }
  async function place(word) {
    if (busy || paused) return;
    busy=true;
    try {
      const result=await save({action:'place_word', word}), correct=Boolean(result.accepted);
      const feedback=correct?"Correct, now let’s read the whole sentence.":'Hmm, let’s try that again.';
      busy=false; render(correct?'Correct! Now read the whole sentence.':'That word does not fit. Try another word.', correct?'good':'bad');
      await say(feedback);
    } catch (error) {render(error.message, 'bad');} finally {busy=false;}
  }
  async function leave(event) {event.preventDefault(); await save({reset:true}); window.location.reload();}
  document.querySelector('#lesson31a2-later').onclick=leave;
  document.querySelector('#lesson31a2-go').onclick=async () => {
    started=true; const token=generation;
    document.querySelector('#lesson31a2-start').hidden=true;
    document.querySelector('#lesson31a2-stage').classList.remove('waiting');
    try {
      if (!await say('Fill in the blank. Read the words, drag the correct word to the blank, then read the whole sentence.') || token!==generation || paused) return;
      render(); if (state.phase==='sentence_listen') await listenToSentence(data.items[state.current_item]);
    } catch (error) {if (token===generation && !paused) render(error.message, 'bad');}
  };
  function cancel() {
    generation++; sentenceReader.cancel(); window.Basahin?.cancelAll(); audio?.pause(); busy=false; listening=null;
    if (started && !paused && !disposed && state.phase === 'dragging') render();
    const retry=app.querySelector('#retry-sentence'); if (retry) {retry.disabled=false; retry.classList.remove('is-busy');}
  }
  document.getElementById('lesson31a2-help-btn')?.addEventListener('click', cancel);
  window.addEventListener('pagehide', () => {disposed=true; cancel();});
  for (const event of ['cancel','pause','cleanup','restart']) window.addEventListener(`session15-lesson31a2-${event}`, () => {if (event==='pause') paused=true; if (event==='cleanup'||event==='restart') disposed=true; cancel();});
  window.addEventListener('session15-lesson31a2-resume', async () => {
    paused=false; disposed=false; window.__session15SilentCancel=false; const token=generation; busy=true;
    app.querySelectorAll('button').forEach(button => button.disabled=true);
    try {
      const restored=await sentenceReader.restore(() => token===generation && !paused && !disposed);
      if (token!==generation || paused || disposed) return;
      busy=false; render();
      if (restored?.continue_prompt) {busy=true; app.querySelectorAll('button').forEach(button => button.disabled=true); await sentenceReader.playPrompt();}
      else if (state.phase==='sentence_listen') await listenToSentence(data.items[state.current_item]);
    } catch (error) {if (token===generation && !paused && !disposed) render(error.message, 'bad');}
    finally {if (token===generation) {busy=false; const read=app.querySelector('#sentence'); if (read && !paused && !disposed) {read.disabled=false; read.classList.remove('is-busy'); const help=app.querySelector('#help'); if (help) help.disabled=state.sentence_attempts<3;}}}
  });
  window.addEventListener('session15-lesson31a2-mute', event => {muted=Boolean(event.detail?.muted); if (muted) cancel();});
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters.lesson31a2={saveCurrentProgress:async () => {await flushPlayback(); await sentenceReader.flush();}, cleanup:cancel};
  hydrate(); render();
})();
