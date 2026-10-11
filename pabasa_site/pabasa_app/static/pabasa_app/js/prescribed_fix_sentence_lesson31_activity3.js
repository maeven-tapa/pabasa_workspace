(() => {
  const node = document.querySelector('#prescribed-activity-data'), app = document.querySelector('#app'); if (!node || !app) return;
  const data = JSON.parse(node.textContent || '{}'), csrf = () => ((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '');
  const esc = value => String(value ?? '').replace(/[&<>]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char]));
  let state = {...(data.progress?.state || {})}, busy = false, stream, selected = '', badSlot = -1, paused=false, muted=false, generation=0, audio=null, disposed=false;
  const hydrate = () => { state.current_item = Number(state.current_item || 0); state.word_index = Number(state.word_index || 0); state.placements ||= []; state.phase ||= 'reading_words'; };
  const steps = () => `<div class="progress">${data.items.map((_, index) => `<span class="step ${index < state.current_item ? 'done' : ''} ${index === state.current_item ? 'active' : ''}">${index + 1}</span>`).join('')}</div>`;
  async function save(body) { const response = await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body)}), result = await response.json(); if (!response.ok || !result.success) throw Error(result.error || 'Could not save progress.'); state = {...result.progress.state}; hydrate(); return result; }
  const sentenceReader=window.PrescribedSentenceReading.create({key:'lesson-31-gawain-3',getState:()=>state,save,url:data.transcribe_url,onRestore:()=>{if(!paused&&!busy&&!disposed)render();},onFeedback:(result,heard)=>window.dispatchEvent(new CustomEvent('session15-lesson31a3-debug',{detail:{status:result.continue_prompt?'Continue reading':result.accepted?'Correct':'Try again',result:result.continue_prompt?'Read the rest':result.accepted?'Correct':'Try again',transcript:heard,mic:'Inactive · Unmuted',recorder:'inactive',error:'—'}}))});
  async function speak(text){
 if(busy||paused||!text)return;
 const playbackGeneration=generation;busy=true;
 const buttons=[...app.querySelectorAll('.actions button')],states=buttons.map(button=>({button,disabled:button.disabled}));
 buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});
 let source=null,activeAudio=null;
 try{
  const response=await fetch(data.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'X-csrfToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-31-gawain-3'})});
  const result=await response.json();
  if(playbackGeneration!==generation||paused)return;
  if(!response.ok||!result.success||!result.audio_content)throw new Error(result.error||'Could not play audio.');
  source=URL.createObjectURL(new Blob([Uint8Array.from(atob(result.audio_content),c=>c.charCodeAt(0))],{type:result.mime_type||'audio/mpeg'}));
  activeAudio=new Audio(source);audio=activeAudio;
  await new Promise((resolve,reject)=>{activeAudio.onended=resolve;activeAudio.addEventListener('ended',resolve,{once:true});activeAudio.addEventListener('pause',resolve,{once:true});activeAudio.addEventListener('error',()=>reject(new Error('Audio playback failed.')),{once:true});activeAudio.play().catch(reject);});
 }finally{
  if(playbackGeneration===generation){busy=false;states.forEach(({button,disabled})=>{if(button.isConnected){button.disabled=disabled;button.classList.remove('is-busy');}});}
  if(source)URL.revokeObjectURL(source);if(audio===activeAudio)audio=null;
 }
}
  function render(message='', kind='') {
    hydrate(); if (state.phase === 'complete') { window.PrescribedLessonUi.showCompletion(app); fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'}); return; }
    const item=data.items[state.current_item];
    if (state.phase === 'reading_words') { const word=item.jumbled_words[state.word_index]; app.innerHTML=`<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 3</div><h1 class="title">Fix the Sentence!</h1><p class="instruction">Read each word aloud.</p><div class="word">${esc(word)}</div><p class="status ${kind}">${esc(message || `Read word ${state.word_index + 1} of ${item.jumbled_words.length}.`)}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read-word">Read</button><button class="button secondary" id="listen-word" ${Number(state.attempts||0)<3?'disabled':''}>🔊 Listen</button></div>${steps()}`; window.Basahin.bindActivity(app.querySelector('#read-word'), ()=>record(word,'read_word',{word_index:state.word_index}));app.querySelector('#listen-word').onclick=()=>speak(word).catch(error=>render(error.message,'bad'));return; }
    const placedCounts = state.placements.reduce((counts, word) => {
      counts[word] = (counts[word] || 0) + 1;
      return counts;
    }, {});
    const remaining = item.jumbled_words.filter(word => {
      if (!placedCounts[word]) return true;
      placedCounts[word] -= 1;
      return false;
    });
    app.innerHTML=`<div class="eyebrow">SESSION 15 · LESSON 31 · ACTIVITY 3</div><h1 class="title">Fix the Sentence!</h1><p class="instruction">${state.phase==='reading_sentence'?'Read the complete sentence aloud.':'Drag each word to the next container.'}</p>${state.phase==='reading_sentence'?`<div class="sentence prescribed-reading-sentence">${window.PrescribedSentenceReading.markup(item.sentence,Number(state.sentence_word_index||0))}</div>`:`<div class="slots">${item.ordered_words.map((_, index) => `<div class="slot ${index < state.placements.length ? 'filled' : ''} ${badSlot===index?'bad':''}" data-slot="${index}">${esc(state.placements[index] || '___')}</div>`).join('')}</div>`}${state.phase==='arranging'?`<div class="bank">${remaining.map(word=>`<button class="token" draggable="true" data-word="${esc(word)}">${esc(word)}</button>`).join('')}</div>`:''}<p class="status ${kind}">${esc(message)}</p><div class="actions">${state.phase==='reading_sentence'?`<button data-basahin-button data-basahin-language="English" class="button" id="read-sentence">Read</button><button class="button secondary" id="listen-sentence" ${Number(state.attempts||0)<3?'disabled':''}>🔊 Listen</button>`:''}</div>${steps()}`;
    if (state.phase === 'arranging') { app.querySelectorAll('[data-word]').forEach(button=>{button.onclick=()=>place(button.dataset.word);button.ondragstart=event=>event.dataTransfer.setData('text/plain',button.dataset.word)}); app.querySelector(`[data-slot="${state.placements.length}"]`)?.addEventListener('dragover',event=>event.preventDefault());app.querySelector(`[data-slot="${state.placements.length}"]`)?.addEventListener('drop',event=>{event.preventDefault();place(event.dataTransfer.getData('text/plain'));}); }
    window.Basahin.bindActivity(app.querySelector('#read-sentence'), ()=>record(item.sentence,'read_sentence'));app.querySelector('#listen-sentence')?.addEventListener('click',()=>speak(item.sentence).catch(error=>render(error.message,'bad')));
  }
  async function record(target,action,extra={}){
    if(busy||paused||muted)return;
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)return render('Microphone recording is not available.','bad');
    const attemptGeneration=generation,current=()=>attemptGeneration===generation&&!paused;
    busy=true;const read=app.querySelector('#read-word')||app.querySelector('#read-sentence'),listen=app.querySelector('#listen-word')||app.querySelector('#listen-sentence');
    read?.classList.add('is-busy');if(listen)listen.disabled=true;
    let feedback='',arrange=false;
    try{
      const sentence=action==='read_sentence';
      const transcript=sentence?await sentenceReader.read(target,state.current_item,read,current):await window.Basahin.read({target_text:target,language:'English',mode:'reading',prescribed_activity_key:'lesson-31-gawain-3'},{button:read,url:data.transcribe_url});
      if(!current())return;
      const result=sentence?transcript:await save({action,heard:transcript.raw_transcript||transcript.transcript,...extra});
      if(!current())return;
      if(result.continue_prompt){
        render("Great! Now let's read the rest of the sentence.",'good');
        app.querySelectorAll('button').forEach(b=>b.disabled=true);await sentenceReader.playPrompt();
      }else{
        feedback=result.accepted?(state.phase==='complete'?'Great job! You completed Fix the Sentence.':sentence?'That’s right, now let’s read the next word.':'Correct!'):'Hmm, let’s try that again.';
        arrange=result.accepted&&action==='read_word'&&state.phase==='arranging';
        render(result.accepted?'Correct!':'Please try again.',result.accepted?'good':'bad');
      }
    }catch(error){if(!current()||error?.name==='AbortError')return;render(error.message||'Please try again.','bad');}
    finally{if(attemptGeneration===generation){busy=false;const activeRead=app.querySelector('#read-word')||app.querySelector('#read-sentence');if(activeRead){activeRead.disabled=false;activeRead.classList.remove('is-busy');}const help=app.querySelector('#listen-word')||app.querySelector('#listen-sentence');if(help)help.disabled=Number(state.attempts||0)<3;}}
    if(feedback&&current()){await speak(feedback);if(arrange&&current())await speak("Now, let's arrange the words.");}
  }
  async function place(word) { if(busy||paused)return;busy=true;try { const result=await save({action:'place_word',slot:state.placements.length,word}),feedback=result.accepted?(state.phase==='reading_sentence'?'That’s right, now let’s read the whole sentence.':'Correct!'):'Hmm, let’s try that again.';if(!result.accepted){badSlot=state.placements.length;busy=false;render('That word does not go there. Try another word.','bad');await speak(feedback);setTimeout(()=>{badSlot=-1;render();},650);return;}badSlot=-1;busy=false;render(state.phase==='reading_sentence'?'Correct! Now read the complete sentence.':'Correct! Add the next word.','good');await speak(feedback);}catch(error){render(error.message,'bad');}finally{busy=false;} }
  async function leave(event){event.preventDefault();try{await save({reset:true});window.location.reload()}catch(error){alert(error.message)}}
  document.querySelector('#lesson31a3-later').onclick=leave;document.querySelector('#lesson31a3-go').onclick=async()=>{document.querySelector('#lesson31a3-start').hidden=true;document.querySelector('#lesson31a3-stage').classList.remove('waiting');render();try{await speak('Fix the sentence. Read the words, put them in the correct order, then read the whole sentence.')}catch(error){render(error.message,'bad')}};function cancel(){generation++;sentenceReader.cancel();window.Basahin?.cancelAll();audio?.pause();busy=false;}
  document.getElementById('lesson31a3-help-btn')?.addEventListener('click',cancel);
  window.addEventListener('pagehide',()=>{disposed=true;cancel();});
  for(const event of ['cancel','pause','cleanup','restart'])window.addEventListener(`session15-lesson31a3-${event}`,()=>{if(event==='pause')paused=true;if(event==='cleanup'||event==='restart')disposed=true;cancel();});
  window.addEventListener('session15-lesson31a3-resume',async()=>{
    paused=false;disposed=false;window.__session15SilentCancel=false;const token=generation;busy=true;
    app.querySelectorAll('button').forEach(button=>button.disabled=true);
    try{
      const restored=await sentenceReader.restore(()=>token===generation&&!paused&&!disposed);
      if(token!==generation||paused||disposed)return;
      busy=false;render();
      if(restored?.continue_prompt){busy=true;app.querySelectorAll('button').forEach(button=>button.disabled=true);await sentenceReader.playPrompt();}
    }catch(error){if(token===generation&&!paused&&!disposed)render(error.message,'bad');}
    finally{if(token===generation){busy=false;if(!paused&&!disposed){const read=app.querySelector('#read-word')||app.querySelector('#read-sentence');if(read){read.disabled=false;read.classList.remove('is-busy');}const help=app.querySelector('#listen-word')||app.querySelector('#listen-sentence');if(help)help.disabled=Number(state.attempts||0)<3;}}}
  });
  window.addEventListener('session15-lesson31a3-mute',event=>{muted=Boolean(event.detail?.muted);if(muted)cancel();});
  window.__prescribedLeaveAdapters ||= {};window.__prescribedLeaveAdapters.lesson31a3={saveCurrentProgress:()=>sentenceReader.flush(),cleanup:cancel};
  hydrate();render();
})();
