(()=>{
  'use strict';

  const dataNode=document.getElementById('prescribed-activity-data');
  const app=document.getElementById('app');
  if(!dataNode||!app)return;
  const d=JSON.parse(dataNode.textContent||'{}');
  const words=d.word_bank||[];
  const items=d.items||[];
  const csrf=()=>((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)||[])[1]||'');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm=v=>String(v||'').toLowerCase().replace(/[^a-z]/g,'');
  const headers=extra=>({'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest',...extra});
  const setBusyButton=(id,busyState)=>document.getElementById(id)?.classList.toggle('is-busy',busyState);
  let s={phase:'intro',current_oral_word_index:0,unlocked_oral_words:[],stt_attempts:{},read_aloud_plays:{},matches:{},picture_attempts:{},needs_reread:false,state_version:0,...(d.progress?.state||{})};
  let busy=false,stream=null,audio=null,audioUrl=null;

  async function jsonResponse(response){
    const body=await response.text();
    try{return JSON.parse(body)}catch(_){
      if(response.status===403)throw Error('The request was rejected. Please refresh the page and try again.');
      throw Error('The server returned an invalid response. Please try again.');
    }
  }
  const index=()=>Math.min(Object.keys(s.matches||{}).length,words.length);
  const current=()=>words[index()];
  const complete=()=>s.phase==='completion'||Object.keys(s.matches||{}).length===words.length;
  const syncListen=()=>{const button=document.getElementById('listen'),target=current();if(button)button.disabled=Number(s.stt_attempts?.[target]||0)<3};

  async function save(){
    const r=await fetch(d.progress_url,{method:'POST',credentials:'same-origin',headers:headers({'Content-Type':'application/json'}),body:JSON.stringify({state:{...s,state_version:(Number(s.state_version)||0)+1}})});
    const j=await jsonResponse(r);
    if(!r.ok||!j.success)throw Error(j.error||'Progress could not be saved.');
    s={...s,...j.progress.state};
    return j;
  }
  async function reset(){
    const r=await fetch(d.progress_url,{method:'POST',credentials:'same-origin',headers:headers({'Content-Type':'application/json'}),body:JSON.stringify({reset:true})});
    const j=await jsonResponse(r);
    if(!r.ok||!j.success)throw Error(j.error||'Could not reset progress.');
  }
  function steps(){
    const i=index();
    return `<div class="progress">${words.map((_,n)=>`<span class="step ${n<i?'done':''} ${n===i&&!complete()?'active':''}">${n+1}</span>`).join('')}</div>`;
  }
  function announce(message){window.setTimeout(()=>play(message).catch(()=>{}),0)}
  function render(message='',kind=''){
    if(complete()){
      app.innerHTML=`<div class="complete">🎉 Great job! You matched every picture.</div>${steps()}`;
      finish();
      announce('Great job! You matched every picture.');
      return;
    }
    const target=current();
    if(s.phase==='matching'){
      app.innerHTML=`<div class="eyebrow">SESSION 14 · LESSON 30 · ACTIVITY 1</div><h1 class="title">Match It!</h1><p class="instruction">Choose the picture that matches the word.</p><div class="word">${esc(target)}</div><div class="pictures">${items.map(item=>`<button class="picture" data-id="${esc(item.id)}" aria-label="${esc(item.alt_text)}"><img src="${esc(item.image_url)}" alt="${esc(item.alt_text)}"></button>`).join('')}</div><p class="status ${kind}">${esc(message||'Choose the matching picture.')}</p>${steps()}</div>`;
      app.querySelectorAll('.picture').forEach(button=>button.onclick=()=>choose(button));
      return;
    }
    app.innerHTML=`<div class="eyebrow">SESSION 14 · LESSON 30 · ACTIVITY 1</div><h1 class="title">Match It!</h1><p class="instruction">Read the word aloud first. Then choose the matching picture.</p><div class="word">${esc(target)}</div><p class="status ${kind}">${esc(message||'Read the word aloud.')}</p><div class="actions"><button class="button" id="read">🎙️ Read the word</button><button class="button secondary" id="listen" ${Number(s.stt_attempts?.[target]||0)<3?'disabled':''}>🔊 Listen</button></div>${steps()}`;
    app.querySelector('#read').onclick=()=>read(target);
    app.querySelector('#listen')?.addEventListener('click',()=>play(target).then(()=>{render('Now read the word aloud.');announce('Now read the word aloud.')} ).catch(e=>render(e.message,'bad')));
  }
  async function play(text){
    if(busy)return;
    busy=true;
    const buttons=[...app.querySelectorAll('button')],buttonStates=buttons.map(button=>({button,disabled:button.disabled})); buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});
    try{
      const r=await fetch(d.read_aloud_url,{method:'POST',credentials:'same-origin',headers:headers({'Content-Type':'application/x-www-form-urlencoded'}),body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-30-gawain-1'})});
      const j=await jsonResponse(r);
      if(!r.ok||!j.success||!j.audio_content)throw Error(j.error||'Audio is unavailable.');
      const bytes=Uint8Array.from(atob(j.audio_content),c=>c.charCodeAt(0));
      audioUrl=URL.createObjectURL(new Blob([bytes],{type:j.mime_type||'audio/mpeg'}));
      audio=new Audio(audioUrl);
      await new Promise((ok,bad)=>{audio.onended=ok;audio.onerror=()=>bad(Error('Audio playback failed.'));audio.play().catch(bad)});
    }finally{
      busy=false;
      if(audioUrl){URL.revokeObjectURL(audioUrl);audioUrl=null}
      audio=null;
      buttonStates.forEach(({button,disabled})=>{if(button.isConnected)button.disabled=disabled;}); syncListen(); buttons.forEach(button=>{if(button.isConnected)button.classList.remove('is-busy');});
    }
  }
  async function read(target){
    if(busy)return;
    busy=true;
    setBusyButton('read',true);
    const listenButton=document.getElementById('listen');
    if(listenButton){listenButton.disabled=true;listenButton.classList.add('is-busy')}
    try{
      if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw Error('Microphone recording is not available in this browser.');
      stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      const recorder=new MediaRecorder(stream),chunks=[];
      recorder.ondataavailable=e=>e.data.size&&chunks.push(e.data);
      const blob=await new Promise((ok,bad)=>{recorder.onerror=()=>bad(Error('Could not record your voice.'));recorder.onstop=()=>ok(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}));recorder.start();setTimeout(()=>recorder.state==='recording'&&recorder.stop(),3500)});
      stop();
      const form=new FormData();form.append('audio',blob,'lesson30-match-it.webm');form.append('target_text',target);form.append('language','English');form.append('mode','reading');
      const r=await fetch(d.transcribe_url,{method:'POST',credentials:'same-origin',headers:headers(),body:form});
      const j=await jsonResponse(r);
      const heard=String(j.raw_transcript||j.transcript||''),ok=Boolean(r.ok&&j.success&&norm(heard).includes(norm(target)));
      if(!ok){
        s.stt_attempts[target]=Math.min(3,Number(s.stt_attempts[target]||0)+1);
        await save();
        render(`I heard “${heard}”. Please try again.`,'bad');
        announce('Try again.');
        return;
      }
      s.unlocked_oral_words=[...new Set([...(s.unlocked_oral_words||[]),target])];s.current_oral_word_index=index();s.stt_attempts[target]=0;s.picture_attempts[target]=0;s.needs_reread=false;s.phase='matching';
      await save();
      render('Correct! Now choose the matching picture.','good');
      announce('Correct! Now choose the matching picture.');
    }catch(e){
      stop();
      s.stt_attempts[target]=Math.min(3,Number(s.stt_attempts[target]||0)+1);
      try{await save()}catch(_){}
      render(e.message||'I could not hear you. Try again.','bad');
    }finally{busy=false;setBusyButton('read',false);if(listenButton?.isConnected){listenButton.disabled=Number(s.stt_attempts?.[target]||0)<3;listenButton.classList.remove('is-busy')}}
  }
  async function choose(button){
    if(busy)return;
    const item=items.find(x=>x.id===button.dataset.id),target=current();
    if(!item)return;
    busy=true;
    try{
      if(item.word!==target){
        const misses=Math.min(3,Number(s.picture_attempts[target]||0)+1);s.picture_attempts[target]=misses;
        if(misses>=3){s.needs_reread=true;s.phase='oral_reading';await save();render('Listen to the word, then read it again.','bad');announce('Listen to the word, then read it again.');setTimeout(()=>play(target).catch(e=>render(e.message,'bad')),350)}
        else{await save();render('That is not the matching picture. Try again.','bad');announce('Try again.')}
        return;
      }
      s.matches[item.id]=target;s.picture_attempts[target]=0;s.needs_reread=false;s.current_oral_word_index=index()+1;s.phase='oral_reading';await save();
      if(index()===words.length){s.phase='completion';await finish();render();return}
      render('Correct! Read the next word.','good');announce('Correct! Read the next word.');
    }catch(e){if(item.word===target)delete s.matches[item.id];render(e.message,'bad')}finally{busy=false}
  }
  async function finish(){
    if(!complete())return;
    try{
      const r=await fetch(d.completion_url,{method:'POST',credentials:'same-origin',headers:headers({'Content-Type':'application/json'}),body:'{}'});
      const j=await jsonResponse(r);
      if(!r.ok||!j.success)throw Error(j.error||'Could not save completion.');
      d.progress.activity_completed=true;
    }catch(e){console.error(e)}
  }
  function stop(){stream?.getTracks().forEach(t=>t.stop());stream=null}
  async function leave(e){e.preventDefault();if(busy)return;busy=true;try{await reset();location.assign(document.getElementById('lesson30a1-back').href)}catch(x){busy=false;alert(x.message)}}
  document.getElementById('lesson30a1-back').onclick=leave;
  document.getElementById('lesson30a1-later').onclick=leave;
  document.getElementById('lesson30a1-go').onclick=async()=>{document.getElementById('lesson30a1-start').hidden=true;document.getElementById('lesson30a1-stage').classList.remove('waiting');try{await play('Match It. Read the word aloud first. Then choose the matching picture.')}catch(e){render(e.message,'bad')}};
  window.addEventListener('pagehide',()=>{stop();audio?.pause()});
  render();
})();
