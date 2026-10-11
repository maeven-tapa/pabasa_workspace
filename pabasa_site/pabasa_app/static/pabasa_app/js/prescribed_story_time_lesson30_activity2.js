(() => {
  'use strict';
  const node=document.getElementById('prescribed-activity-data'),app=document.getElementById('app');
  if(!node||!app)return;
  const d=JSON.parse(node.textContent||'{}'),csrf=()=>((document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)||[])[1]||''),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),words=v=>String(v||'').toLowerCase().match(/[a-z]+/g)||[];
  let s={...(d.progress?.state||{})},busy=false,paused=false,muted=false,recordingAttemptActive=false,generation=0,stream=null,recorder=null,recordTimer=null,audioUrl=null,audio=null,feedback={},pendingRetryAudio='',disposed=false;
  const debugState={status:'Ready',transcript:'No transcript yet.',expected:'—',normalized:'—',result:'—',mic:'Inactive · Unmuted',recorder:'inactive',vad:'waiting',error:'—',raw:'Waiting for speech...'};
  const emitDebug=detail=>{Object.assign(debugState,detail);Object.entries(debugState).forEach(([key,value])=>{const field=document.getElementById(`lesson30a2-debug-${key}`);if(field)field.textContent=String(value)});window.dispatchEvent(new CustomEvent('lesson30-lesson30a2-debug',{detail:{...debugState}}));};
  window.Lesson30ActivityDebug={getState:()=>({...debugState}),reset:()=>emitDebug({status:'Ready',transcript:'No transcript yet.',expected:'—',normalized:'—',result:'—',mic:`Inactive · ${muted?'Muted':'Unmuted'}`,recorder:'inactive',vad:'waiting',error:'—',raw:'Waiting for speech...'})};
  const sentenceReader=window.PrescribedSentenceReading.create({key:'lesson-30-gawain-2',getState:()=>s,save:body=>post(d.progress_url,body),url:d.transcribe_url,onRestore:()=>{if(!paused&&!busy&&!disposed)render();}});
  function hydrate(){s.current_line=Number(s.current_line||0);s.completed_items=Number(s.completed_items||0);s.phase||='reading'}
  async function post(url,body){const r=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body)}),x=await r.json();if(!r.ok||!x.success)throw Error(x.error||'Could not save your progress.');if(x.progress?.state)s={...x.progress.state};hydrate();return x}
  function steps(){const current=s.phase==='complete'?d.lines.length:s.current_line;return `<div class="progress">${d.lines.map((_,i)=>`<span class="step ${i<current?'done':''} ${i===current&&s.phase!=='complete'?'active':''}">${i+1}</span>`).join('')}</div>`}
  function sentenceMatches(expected,heard){const targetWords=words(expected),heardWords=words(heard);return targetWords.length===heardWords.length&&targetWords.every((word,index)=>word===heardWords[index]||(word==='mat'&&heardWords[index]==='math'))}
  function marked(line,index){
    if(index>s.current_line)return esc(line);
    return window.PrescribedSentenceReading.markup(line,index<s.current_line?line.trim().split(/\s+/).length:Number(s.sentence_word_index||0));
  }
  function render(message='',kind=''){
    hydrate();
    if(s.phase==='complete'||s.current_line>=d.lines.length){window.PrescribedLessonUi.showCompletion(app);post(d.completion_url,{}).catch(()=>{});return}
    const line=d.lines[s.current_line];
    app.innerHTML=`<div class="eyebrow">SESSION 14 · LESSON 30 · ACTIVITY 2</div><p class="instruction">Listen to each line, then read the same line aloud.</p><section class="story"><h2>“${esc(d.story_title)}”</h2>${d.lines.map((text,i)=>`<p class="line ${i<s.current_line?'done':''} ${i===s.current_line?'current':''}">${marked(text,i)}</p>`).join('')}</section><p class="status ${kind}" id="status">${esc(message||'The teacher will read the highlighted line first.')}</p><div class="actions"><button data-basahin-button data-basahin-language="English" class="button" id="read">Read</button><button class="button secondary" id="listen">🔊 Listen</button></div>${steps()}`;
    document.getElementById('listen').onclick=()=>play(line).catch(e=>render(e.message,'bad'));window.Basahin.bindActivity(document.getElementById('read'), ()=>{emitDebug({transcript:'No transcript yet.',normalized:'—',result:'—',error:'—',raw:'Listening for speech...'});return record()});
    emitDebug({status:paused?'Paused':'Ready',expected:line,mic:`Inactive · ${muted?'Muted':'Unmuted'}`,recorder:'inactive',vad:'waiting'});
  }
  async function play(text){
 if(busy||paused||!text)return;
 const playbackGeneration=generation;busy=true;
 const buttons=[...app.querySelectorAll('.actions button')],states=buttons.map(button=>({button,disabled:button.disabled}));
 buttons.forEach(button=>{button.disabled=true;button.classList.add('is-busy');});
 let source=null,activeAudio=null;
 try{
  const response=await fetch(d.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'X-csrfToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({target_text:text,language:'English',lesson_tts_key:'lesson-30-gawain-2'})});
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
  async function record(){
    if(busy||paused||muted)return;
    const attemptGeneration=generation, index=s.current_line,line=d.lines[index];
    const current=()=>attemptGeneration===generation&&!paused;
    recordingAttemptActive=true;busy=true;
    const button=document.getElementById('read'),listen=document.getElementById('listen');
    button?.classList.add('is-busy');if(listen)listen.disabled=true;
    emitDebug({status:'Listening',expected:line,mic:'Active · Unmuted',recorder:'recording',error:'—'});
    let feedbackText='';
    try{
      const result=await sentenceReader.read(line,index,button,current);
      if(!current())return;
      const heard=result.raw_transcript||'',success=Boolean(result.accepted);
      emitDebug({status:result.continue_prompt?'Continue reading':success?'Correct':'Try again',transcript:heard,
        result:result.continue_prompt?'Read the rest':success?'Correct':'Try again',mic:'Inactive · Unmuted',recorder:'inactive',error:'—'});
      if(result.continue_prompt){
        render("Great! Now let's read the rest of the sentence.",'good');
        app.querySelectorAll('button').forEach(b=>b.disabled=true);
        await sentenceReader.playPrompt();
      }else if(success){
        render(s.phase==='complete'?'Great job! You read the whole story.':'Correct! The next line will be read.','good');
        feedbackText=s.phase==='complete'?'Great job! You read the whole story.':'Correct!';
      }else{
        render(`I heard “${heard}”. Read the highlighted words again.`,'bad');feedbackText='Try again.';
      }
    }catch(error){
      if(!current()||error?.name==='AbortError')return;
      emitDebug({status:'Error',mic:'Inactive · Unmuted',recorder:'inactive',error:error.message});
      render(error.message||'Please try again.','bad');feedbackText='Try again.';
    }finally{
      if(attemptGeneration===generation){
        recordingAttemptActive=false;busy=false;
        app.querySelectorAll('.actions button').forEach(b=>{b.disabled=false;b.classList.remove('is-busy');});
      }
    }
    if(feedbackText&&current()){
      try{await play(feedbackText);if(current()&&feedbackText==='Correct!'&&s.phase!=='complete')await play(d.lines[s.current_line]);}catch(_){}
    }
  }
  function stop(){ window.Basahin?.cancelAll(); if(recorder?.state==='recording'){try{recorder.stop()}catch(_){}}if(recordTimer)clearTimeout(recordTimer);recordTimer=null;recorder=null;stream?.getTracks().forEach(t=>t.stop());stream=null}
  function cancelSpeechAttempt(){ sentenceReader.cancel(); window.Basahin?.cancelAll(); generation++;if(recordTimer){clearTimeout(recordTimer);recordTimer=null}const activeRecorder=recorder;recorder=null;if(activeRecorder&&activeRecorder.state!=='inactive'){try{activeRecorder.stop()}catch(_){}}stop();recordingAttemptActive=false;busy=false;document.getElementById('read')?.classList.remove('is-busy');document.getElementById('listen')?.classList.remove('is-busy');emitDebug({status:paused?'Paused':'Ready',recorder:'inactive'},'Speech attempt cancelled')}
  function cancel(){cancelSpeechAttempt();audio?.pause();audio=null;busy=false}
  document.getElementById('lesson30a2-later').onclick=e=>{e.preventDefault();if(busy)return;post(d.progress_url,{reset:true}).then(()=>window.location.reload()).catch(x=>alert(x.message))};
  document.getElementById('lesson30a2-go').onclick=async()=>{document.getElementById('lesson30a2-start').hidden=true;document.getElementById('lesson30a2-stage').classList.remove('waiting');try{await play('Story Time. Listen to each line, then read the same line aloud.');await play(d.lines[s.current_line])}catch(e){render(e.message,'bad')}};
  window.addEventListener('pagehide',()=>{disposed=true;cancel();});
  window.addEventListener('lesson30-lesson30a2-pause',()=>{paused=true;cancel();emitDebug({status:'Paused',recorder:'inactive',raw:'Activity paused.'})});
  window.addEventListener('lesson30-lesson30a2-resume',async()=>{
    paused=false;disposed=false;const token=generation;busy=true;
    app.querySelectorAll('.actions button').forEach(button=>button.disabled=true);
    try{
      const restored=await sentenceReader.restore(()=>token===generation&&!paused&&!disposed);
      if(token!==generation||paused||disposed)return;
      busy=false;render();
      if(restored?.continue_prompt){busy=true;app.querySelectorAll('.actions button').forEach(button=>button.disabled=true);await sentenceReader.playPrompt();}
      else if(restored?.accepted&&s.phase!=='complete')await play(d.lines[s.current_line]);
    }catch(error){if(token===generation&&!paused&&!disposed)render(error.message,'bad');}
    finally{if(token===generation){busy=false;if(!paused&&!disposed)app.querySelectorAll('.actions button').forEach(button=>{button.disabled=false;button.classList.remove('is-busy');});}}
  });
  window.addEventListener('lesson30-lesson30a2-restart',()=>{disposed=true;cancel();});
  window.addEventListener('lesson30-lesson30a2-cleanup',()=>{disposed=true;cancel();});
  window.addEventListener('lesson30-lesson30a2-mute',e=>{muted=Boolean(e.detail?.muted);if(muted)cancelSpeechAttempt();stream?.getTracks().forEach(t=>{t.enabled=!muted});emitDebug({mic:`${stream?'Active':'Inactive'} · ${muted?'Muted':'Unmuted'}`})});
  document.getElementById('lesson30a2-help-btn')?.addEventListener('click',()=>{if(recordingAttemptActive)cancelSpeechAttempt()});
  window.addEventListener('lesson30-lesson30a2-help',()=>{if(recordingAttemptActive)cancelSpeechAttempt()});
  window.__prescribedLeaveAdapters ||= {};
  window.__prescribedLeaveAdapters.lesson30a2={saveCurrentProgress:()=>sentenceReader.flush(),cleanup:cancel};
  hydrate();render();
})();
