/* Shared workbook presentation for teacher preview and student interaction. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent);
  const a = data.activity, preview = data.preview;
  const qBuilder = a.activity_key === 'aral-l23-g6-q-syllable-builder';
  const l24Builder = a.activity_key === 'aral-l24-g1-v-syllable-builder';
  const cBuilder = (Boolean(a.specialized_builder) && !qBuilder) || a.activity_key === 'aral-l22-g1-c-syllable-builder';
  const specializedBuilder = cBuilder || qBuilder;
  const jReading = a.activity_key === 'aral-l23-g3-j-word-reading';
  const qReading = a.activity_key === 'aral-l23-g7-q-word-reading';
  const prescribedWordReading = jReading || qReading;
  const jSyllables = a.activity_key === 'aral-l23-g4-j-syllabication';
  const pictureReading = a.activity_key === 'aral-l24-g4-x-pictures';
  const l23G1 = a.activity_key === 'aral-l23-g1-n-syllable-builder';
  const localAudio = l23G1 ? (data.local_audio || {}) : {};
  const G1_MAPPED_TEXT = new Set([
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.',
    'Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe',
    'Basahin muna ang lahat ng nasa Big Box.', 'Bumuo muna ng lahat ng wastong salita.',
    'Bumuo ng ibang salita.', 'Hindi available ang mikropono sa browser na ito.',
    'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi mabasa ang recording.',
    'Hindi magamit ang mikropono. Subukan muli.', 'Hindi nakuha ang iyong boses. Subukan muli.',
    'Hindi tumugon ang mikropono.', 'Magaling! Nabasa mo nang tama ang lahat ng pantig.',
    'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.',
    'Pakinggan muna ang tamang pagbigkas.', 'Subukan muli.', 'Tama!',
    'Walang nakuha sa recording. Subukan muli.', 'Magaling! Nabuo mo ang salitang Niño',
    'Magaling! Natapos mo ang Gawain 1.',
  ]);
  let state = data.state, busy = false, selected = [], builder = [], words = [];
  let activeRecorder = null, activeStream = null, activeReadAloud = null, audioController = null;
  let audioRun = 0, instructionSpoken = false, pendingSpeech = '';
  const instructionText = a.instruction;
  const content = document.getElementById('wb-content'), action = document.getElementById('wb-action');
  const status = document.getElementById('wb-status');
  const fil = a.language === 'Filipino';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const token = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const endpoint = data.progress_url;
  const item = () => a.items[state.index];
  const oral = () => state.oral[item()?.id] || {passed:false,attempts:0,listens:0,phase:a.model_first?'model':'read'};
  const message = (text, error=false) => {
    status.textContent=text;status.className=error?'wb-error':'wb-save';status.hidden=specializedBuilder||prescribedWordReading||jSyllables;
    if(specializedBuilder){const primary=content.querySelector('.wb-phase-status');if(primary){primary.textContent=text;primary.classList.toggle('wb-feedback-error',error);}}
  };
  const stopReadAloud = () => {
    audioRun += 1;
    audioController?.abort();
    audioController = null;
    if(activeReadAloud){activeReadAloud.pause();activeReadAloud.currentTime=0;activeReadAloud=null;}
  };
  const localAudioUrl = text => text === instructionText ? localAudio.instruction
    : (localAudio.syllables || {})[text] || (localAudio.feedback || {})[text]
    || (localAudio.completion || {})[text] || null;
  async function playPrescribedAudio(text,allowBusy=false){
    if(!text || (busy&&!allowBusy) || activeStream)return;
    stopReadAloud();
    const run=audioRun, controller=new AbortController();audioController=controller;
    const localUrl=l23G1 ? localAudioUrl(text) : null;
    if(l23G1 && G1_MAPPED_TEXT.has(text)){
      if(!localUrl){if(audioController===controller)audioController=null;throw Error('Hindi available ang nakatalagang audio.');}
      try{
        if(run!==audioRun||(busy&&!allowBusy)||activeStream)return;
        const audio=new Audio(localUrl);activeReadAloud=audio;await audio.play();
        await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(Error('Hindi ma-play ang nakatalagang audio.'));});
      }finally{
        if(audioController===controller)audioController=null;
        if(activeReadAloud&&run===audioRun){activeReadAloud.pause();activeReadAloud=null;}
      }
      return;
    }
    const form=new FormData();form.append('target_text',text);form.append('language','Filipino');form.append('mode','reading');form.append('prescribed_activity_key',a.activity_key);
    try{
      const response=await fetch(data.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':token()},body:form,signal:controller.signal});
      const result=await responseJson(response,'Hindi available ang Filipino audio. Subukan muli.');
      if(!response.ok||!result.success||!result.audio_content)throw Error(result.error||'Hindi available ang Filipino audio.');
      if(!result.local_audio&&(result.tts_language!=='fil-PH'||result.voice_name!=='fil-PH-Wavenet-A'))throw Error('Hindi available ang tamang Filipino voice.');
      if(run!==audioRun||(busy&&!allowBusy)||activeStream)return;
      const audio=new Audio('data:'+(result.mime_type||'audio/mpeg')+';base64,'+result.audio_content);activeReadAloud=audio;
      await audio.play();
      await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(Error('Hindi ma-play ang Filipino audio.'));});
    }finally{
      if(audioController===controller)audioController=null;
      if(activeReadAloud&&run===audioRun){activeReadAloud.pause();activeReadAloud=null;}
    }
  }
  async function responseJson(response, fallback) {
    const contentType = response.headers.get('content-type') || '';
    const body = await response.text();
    if (!contentType.toLowerCase().includes('application/json')) {
      console.error('Workbook request returned a non-JSON response.', {status:response.status,url:response.url,contentType,body:body.slice(0,500)});
      throw Error(fallback);
    }
    try { return JSON.parse(body); }
    catch (error) {
      console.error('Workbook request returned invalid JSON.', {status:response.status,url:response.url,contentType,body:body.slice(0,500),error});
      throw Error(fallback);
    }
  }
  let queue = Promise.resolve();
  function send(event, form=null, announceSaved=true) {
    if(preview) return Promise.resolve();
    const operation = async () => {
      let body;
      if(form) {form.set('revision',state.revision);if(event?.action)form.set('action',event.action);body=form;}
      else body=JSON.stringify({...event,revision:state.revision});
      const response=await fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':token(),...(form?{}:{'Content-Type':'application/json'})},body});
      const result=await responseJson(response,'Hindi na-save. Subukan muli.');
      if(!response.ok||!result.success) throw Error(result.error||'Hindi na-save. Subukan muli.');
      const latestDraft=state.draft;
      state=result.state;
      if(event?.action==='draft')state.draft=latestDraft;
      if(announceSaved)message(fil?'Na-save ang iyong gawain.':'Your work is saved.');
    };
    const pending=queue.then(operation);queue=pending.catch(()=>{});return pending;
  }
  async function perform(event,form=null){if(busy)return;busy=true;lock();try{await send(event,form);render();if(l23G1){if(state.completed){await playPrescribedAudio('Magaling! Natapos mo ang Gawain 1.',true);await playPrescribedAudio('Magaling! Nabuo mo ang salitang Niño',true);}else if(G1_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}}catch(e){const text=e.message||'Hindi na-save. Subukan muli.';message(text,true);if(l23G1&&G1_MAPPED_TEXT.has(text))playPrescribedAudio(text,true).catch(()=>{});}finally{busy=false;lock();}}
  function lock(){action.querySelectorAll('button').forEach(b=>b.disabled=busy||preview);}
  function button(text,fn,primary=false){const b=document.createElement('button');b.type='button';b.textContent=text;b.className=primary?'wb-primary':'';b.onclick=fn;action.appendChild(b);return b;}
  function table(){let n=0;return `<table class="wb-table">${a.column_headers?'<thead><tr>'+a.column_headers.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr></thead>':''}<tbody>${a.rows.map(row=>'<tr>'+row.map(text=>{const i=text?a.items[n++]:null;return `<td class="${!preview&&i?(n-1===state.index?'wb-current':n-1<state.index?'wb-done':''):''}">${i&&a.images?.[i.id]?`<img src="${esc(a.images[i.id])}" alt="${esc(text)}"><br>`:''}${esc(i?(a.cell_display?.[i.id]||text):'')}</td>`;}).join('')+'</tr>').join('')}</tbody></table>`;}
  function render(){
    selected=[];builder=state.draft.builder||[];words=state.draft.words||[];
    const totalProgress=cBuilder?a.items.length:(a.progress_total||a.items.length), progressValue=state.completed?totalProgress:Math.min(totalProgress, qBuilder?Number(state.index||0):cBuilder?Number(state.index||0):Number(state.index||0));
    document.getElementById('wb-progress').textContent=preview?'Preview':(cBuilder?`Nabasa: ${Math.min(a.items.length,Number(state.index||0))} / ${a.items.length}`:(a.activity_key==='aral-l23-g1-n-syllable-builder'||l24Builder?`Nabasa: ${Math.min(12,Number(state.index||0))} / 12`:`${progressValue} / ${totalProgress}`));
    const progressFill=document.getElementById('wb-progress-fill');if(progressFill)progressFill.style.width=`${preview?0:Math.max(0,Math.min(100,progressValue/totalProgress*100))}%`;
    document.getElementById('wb-back').hidden=preview;
    action.replaceChildren();
    if(state.completed){
      const completionWord=a.activity_key==='aral-l23-g1-n-syllable-builder'?'Niño':(state.found_words||[]).join(', ');
      content.innerHTML=`<div class="wb-focus"><h2>${cBuilder?'Magaling! Natapos mo ang Gawain 1.':fil?'Natapos mo ang gawain!':'Activity complete!'}</h2>${cBuilder?`<p>${a.activity_key==='aral-l23-g1-n-syllable-builder'?`Magaling! Nabuo mo ang salitang ${completionWord}`:`Nabuo mo na: ${esc(completionWord)}`}</p>`:a.review_required?'<p>Your written work is saved for teacher review.</p>':''}</div>`;
      if(cBuilder)button('Susunod',()=>{if(data.next_url)location.href=data.next_url;},true).disabled=!data.next_url;
      if((prescribedWordReading||jSyllables||pictureReading)&&data.next_url)button('Susunod',()=>{location.href=data.next_url;},true);
      return;
    }
    if(prescribedWordReading){renderJReading();return;}
    if(pictureReading){renderPictureReading();return;}
    if(jSyllables){renderJSyllables();return;}
    if(specializedBuilder&&!preview){renderCBuilder();lock();return;}
    if(state.index>=a.items.length&&!preview){content.innerHTML='<div class="wb-focus">'+(fil?'Na-save ang lahat ng bahagi ng gawain.':'All required parts are saved.')+'</div>';button(fil?'Tapusin ang gawain':'Finish activity',()=>perform({action:'finish'}),true);return;}
    const kind=a.interaction_type;
    content.innerHTML=preview?'<p class="wb-preview-note">Preview · '+(fil?'Walang sagot na napili.':'No answers selected.')+'</p>':'';
    if(kind==='search')renderSearch();
    else if(kind==='drawing')renderDrawing();
    else if(kind==='fill')renderFill();
    else if(kind==='syllables')renderSyllables();
    else if(a.group_titles){content.innerHTML+=a.rows.map((row,i)=>`<section class="wb-focus"><h2>${esc(a.group_titles[i])}</h2><p class="wb-verse">${esc(row[0])}</p></section>`).join('');}
    else if(kind==='builder'){if(preview)content.innerHTML+=table();}
    else if(kind==='reading'){if(preview)content.innerHTML+=table();}
    else content.innerHTML+=table();
    if(preview){if(kind==='builder')renderBuilder();return;}
    if(a.oral_flow&&!oral().passed){
      const focus=document.createElement('div');focus.className='wb-focus wb-reading-focus';
      const image=a.images?.[item().id]?`<img class="wb-hero-image" src="${esc(a.images[item().id])}" alt="${esc(item().text)}">`:'';
      const verseTitle=a.group_titles?.[state.index]?`<h2>${esc(a.group_titles[state.index])}</h2>`:'';
      focus.innerHTML=`${image}${verseTitle}<strong>${esc(item().text)}</strong>`;action.appendChild(focus);
      const o=oral();
      button(o.phase==='read'?(fil?`Basahin (${o.attempts}/3)`:`Read (${o.attempts}/3)`):o.phase==='model'?'Read Aloud':`Read Aloud (${o.listens}/3)`,o.phase==='read'?record:aloud,true);
    }else if(kind==='reading'||kind==='builder'&&state.index<a.items.length-1){button(fil?'Susunod':'Next',()=>perform({action:'answer',answer:null}),true);}
    else if(kind==='builder')renderBuilder();
    else if(kind==='search'){button(fil?'Piliin ang salita':'Select word',()=>perform({action:'answer',answer:selected}),true);}
    else if(kind==='syllables'){button(fil?'Isumite':'Submit',()=>perform({action:'answer',answer:{text:document.getElementById('wb-written').value}}),true);}
    else if(kind==='fill'){button('Submit',()=>perform({action:'answer',answer:{blanks:[...content.querySelectorAll('[data-blank]')].map(s=>s.value)}}),true);}
    else if(kind==='drawing'){button('Submit drawing and writing',()=>perform({action:'answer',answer:{text:document.getElementById('wb-written').value,strokes:state.draft.strokes||[]}}),true);}
    lock();
  }
  function instructionBanner(){
    return `<div class="wb-instruction-banner"><span>${esc(instructionText)}</span><button type="button" id="wb-instruction-replay" aria-label="Pakinggan muli ang panuto">Pakinggan Muli</button></div>`;
  }
  function speakInstruction(){
    if(preview||instructionSpoken)return;
    instructionSpoken=true;
    setTimeout(()=>playPrescribedAudio(instructionText).catch(e=>console.error('Workbook instruction audio failed',e)),0);
  }
  function renderJReading(){
    const current=Number(state.index||0), done=new Set(state.completed_words||[]);
    content.innerHTML=`${instructionBanner()}<section class="wb-focus wb-j-reading"><h2>Mga salitang may letrang Jj</h2><div class="wb-j-grid">${a.items.map((it,i)=>`<div class="wb-j-word ${done.has(i)?'is-done':''} ${i===current?'is-current':''}" aria-current="${i===current?'step':'false'}">${esc(it.text)}${done.has(i)?'<span aria-label="Tapos na"> ✓</span>':''}</div>`).join('')}</div><p class="wb-j-feedback" id="wb-j-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'Handa ka na.')}</p></section>`;
    const readingHeading=content.querySelector('.wb-j-reading h2');
    if(readingHeading)readingHeading.textContent=a.title;
    const replay=document.getElementById('wb-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>setJFeedback(e.message||'Hindi available ang panuto.',true));};
    if(!preview)speakInstruction();
    if(preview)return;
    if(current<a.items.length){
      const word=a.items[current];
      const card=document.createElement('div');card.className='wb-j-controls';
      const read=button('Basahin',recordJ,true);read.setAttribute('aria-label',`Basahin ang salitang ${word.text}`);
      const help=button('Pakinggan ang Tamang Pagbigkas',()=>playPrescribedAudio(word.text).catch(e=>setJFeedback(e.message||'Hindi available ang audio.',true)),false);help.setAttribute('aria-label',`Pakinggan ang tamang pagbigkas ng ${word.text}`);
      card.append(read,help);action.appendChild(card);
    }
    setJFeedback(state.last_feedback||'Handa ka na.');
  }
  function setJFeedback(text,error=false){const el=document.getElementById('wb-j-feedback');if(el){el.textContent=text;el.classList.toggle('wb-feedback-error',error);}}
  function setPictureFeedback(text,error=false){const el=document.getElementById('wb-picture-feedback');if(el){el.textContent=text;el.classList.toggle('wb-feedback-error',error);}}
  function renderPictureReading(){
    const current=Math.min(Number(state.index||0),a.items.length-1), target=a.items[current];
    const done=new Set(state.completed_words||[]);
    const steps=a.items.map((it,i)=>`<span class="wb-picture-step ${done.has(i)?'is-done':''} ${i===current&&!state.completed?'is-current':''}" aria-label="${i+1} sa ${a.items.length}">${done.has(i)?'✓':i+1}</span>`).join('');
    document.getElementById('wb-progress').innerHTML=steps;
    content.innerHTML=`${instructionBanner()}<section class="wb-picture-reading">${state.completed?`<div class="wb-picture-complete" role="status">Magaling! Natapos mo ang gawain. 🎉</div>`:`<img class="wb-picture-image" src="${esc(a.images?.[target.id]||'')}" alt="Larawan ng ${esc(target.text)}"><strong class="wb-picture-word">${esc(target.text)}</strong><p class="wb-picture-feedback" id="wb-picture-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'Basahin ang salitang nasa larawan.')}</p>`}</section>`;
    const replay=document.getElementById('wb-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>setPictureFeedback(e.message||'Hindi available ang panuto.',true));};
    if(!preview&&!instructionSpoken){instructionSpoken=true;setTimeout(()=>playPrescribedAudio(instructionText).catch(e=>console.error('Picture activity instruction audio failed',e)),0);}
    if(preview||state.completed)return;
    const listen=button('🔊 Pakinggan',()=>playPrescribedAudio(target.text).catch(e=>setPictureFeedback(e.message||'Hindi available ang audio.',true)),false);
    listen.setAttribute('aria-label',`Pakinggan ang ${target.text}`);
    const read=button('🎙 Basahin ang Salita',recordPictureReading,true);
    read.setAttribute('aria-label',`Basahin ang salitang ${target.text}`);
    const controls=document.createElement('div');controls.className='wb-picture-controls';controls.append(read,listen);action.appendChild(controls);
    lock();
  }
  async function recordPictureReading(){
    if(busy||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){setPictureFeedback('Hindi magamit ang mikropono. Subukan muli.',true);return;}
    busy=true;lock();let stream=null,recorder=null,timer=null,requestIndex=Number(state.index||0),requestRevision=Number(state.revision||0);
    try{
      setPictureFeedback('🎙️ Nakikinig... Basahin ang salita.');
      stream=activeStream=await navigator.mediaDevices.getUserMedia({audio:true});
      const chunks=[];recorder=activeRecorder=new MediaRecorder(stream);
      const audioDone=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>e.data.size&&chunks.push(e.data);recorder.onerror=()=>reject(new Error('May problema sa recording.'));recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}));});
      recorder.start();timer=setTimeout(()=>{if(recorder?.state==='recording')recorder.stop();},3500);
      const stop=button('Tapusin ang Pagbasa',()=>{if(recorder?.state==='recording')recorder.stop();},true);stop.setAttribute('aria-label','Tapusin ang pagbasa');action.replaceChildren(stop);
      const audio=await audioDone;clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(requestIndex!==Number(state.index||0)||requestRevision!==Number(state.revision||0))return;
      setPictureFeedback('Pinoproseso ang iyong pagbasa...');
      const form=new FormData();form.append('audio',audio,'reading.webm');
      await send({action:'reading_attempt',item_index:requestIndex},form,false);render();
    }catch(e){
      clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      const denied=e?.name==='NotAllowedError'||e?.name==='SecurityError';setPictureFeedback(denied?'Hindi pinayagan ang mikropono. Subukan muli.':e.message||'Hindi nakuha ang iyong boses. Subukan muli.',true);
    }finally{busy=false;lock();}
  }
  function renderJSyllables(){
    const current=Number(state.index||0), item=a.items[current];
    content.innerHTML=`${instructionBanner()}<section class="wb-focus wb-j-syllables"><h2>Pantigin ang sumusunod na salita.</h2><div class="wb-syllable-rows">${a.items.map((it,i)=>`<div class="wb-syllable-row ${i<current?'is-done':''} ${i===current?'is-current':''}"><span>${i+1}. ${esc(it.text)}</span><span>–</span><span>${i===current?'<input id="wb-j-answer" type="text" inputmode="text" autocomplete="off" aria-label="Sagot para sa '+esc(it.text)+'" value="'+esc(state.draft?.text||'')+'">':i<current?'✓':'—'}</span></div>`).join('')}</div><p class="wb-j-feedback" id="wb-j-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'')}</p></section>`;
    const replay=document.getElementById('wb-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>setJFeedback(e.message||'Hindi available ang panuto.',true));};
    if(!preview)speakInstruction();
    if(preview||!item)return;
    const input=document.getElementById('wb-j-answer');
    input.oninput=()=>draft({text:input.value});
    button('Suriin',()=>perform({action:'answer',answer:{text:input.value}}),true);
    setJFeedback(state.last_feedback||'');
  }
  async function recordJ(){
    if(busy||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){setJFeedback('Hindi magamit ang mikropono. Subukan muli.',true);return;}
    busy=true;lock();let stream=null,recorder=null,timer=null,requestId=Number(state.index||0),requestActivity=a.activity_key;
    try{
      if(!jReading)setJFeedback('Nakikinig...');stream=activeStream=await navigator.mediaDevices.getUserMedia({audio:true});
      const chunks=[];recorder=activeRecorder=new MediaRecorder(stream);
      const audioDone=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>e.data.size&&chunks.push(e.data);recorder.onerror=()=>reject(new Error('May problema sa recording.'));recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}));});
      recorder.start();timer=setTimeout(()=>{if(recorder?.state==='recording')recorder.stop();},3500);
      const stop=button('Tapusin ang Pagbasa',()=>{if(recorder?.state==='recording')recorder.stop();},true);stop.setAttribute('aria-label','Tapusin ang pagbasa');
      action.replaceChildren(stop);
      const audio=await audioDone;clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(requestActivity!==a.activity_key||requestId!==Number(state.index||0))return;
      setJFeedback('Sinusuri...');if(jReading)await playPrescribedAudio('Sinusuri...',true);const form=new FormData();form.append('audio',audio,'reading.webm');
      await send({action:'reading_attempt'},form,false);render();
    }catch(e){
      clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      const denied=e?.name==='NotAllowedError'||e?.name==='SecurityError';setJFeedback(denied?'Hindi pinayagan ang mikropono.':e.message||'Hindi nakuha ang iyong boses. Subukan muli.',true);
    }finally{busy=false;lock();}
  }
  function draft(value){state.draft={...state.draft,...value};if(specializedBuilder&&Object.prototype.hasOwnProperty.call(value,'builder')){state.last_feedback='';const feedback=content.querySelector('.wb-builder-feedback');if(feedback)feedback.textContent='';}const snapshot=structuredClone(state.draft);send({action:'draft',draft:snapshot}).catch(e=>message(e.message,true));}
  function renderCBuilder(){
    const readDone=Boolean(state.read_aloud_completed), piecesById=Object.fromEntries(a.items.map(i=>[i.id,i.text]));
    let fallbackIndex=0;
    const boxCells=a.bigbox_cells||a.rows.map(row=>row.filter(Boolean).map(()=>[`item-${++fallbackIndex}`]));
    builder=state.draft.builder||[];
    content.className=`wb-l22-builder ${qBuilder?'wb-q-builder':''}`;
    const current=Math.min(Number(state.index||0),a.items.length-1), phase=state.reading_phase||'read';
    content.innerHTML=`<div class="wb-l22-banner"><span class="wb-speaker-icon" aria-hidden="true">🔊</span><strong>${instructionText}</strong><button type="button" id="wb-l22-instruction-replay" aria-label="Pakinggan muli ang panuto">Pakinggan muli</button></div><section class="wb-bigbox"><h2>BIG BOX</h2><p class="wb-box-help">Sundan ang dilaw na highlight.</p><div class="wb-bigbox-grid">${boxCells.map(row=>`<div class="wb-bigbox-row">${row.map(()=>'<div class="wb-bigbox-cell"></div>').join('')}</div>`).join('')}</div></section><section class="wb-reading-panel"><h2>BASAHIN</h2><p class="wb-phase-status" role="status">${readDone?'Magaling!':state.last_feedback==='Tama!'?'Tama!':'Handa ka na?'}</p><div id="wb-l22-reading-action"></div><p class="wb-reading-tip"><span aria-hidden="true">💡</span><span> pindutin ang button kapag handa ka nang magbasa.</span></p></section><section class="wb-word-panel ${readDone?'':'is-locked'}" aria-disabled="${!readDone}"><h2>BUMUO NG SALITA</h2>${readDone?`<p>Piliin ang mga pantig sa Big Box.</p><div class="wb-selected-parts" id="wb-selected-parts" aria-live="polite"></div><div class="wb-tools"><button type="button" id="wb-erase">Bura</button><button type="button" id="wb-retry">Ulitin</button></div><p class="wb-builder-feedback" aria-live="polite">${esc(state.last_feedback||'')}</p>${state.found_words?.length?`<div class="wb-builder-words"><strong>Nabuo mo na:</strong><ul>${state.found_words.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:''}`:'<p class="wb-locked-note"><span class="wb-lock-icon" aria-hidden="true">🔒</span><span>Basahin muna ang lahat ng pantig.</span></p>'}</section>`;
    const replay=document.getElementById('wb-l22-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>message(e.message||'Hindi available ang panuto.',true));};
    if(!preview&&!instructionSpoken){instructionSpoken=true;setTimeout(()=>playPrescribedAudio(instructionText).catch(e=>console.error('Lesson 22 instruction audio failed',e)),0);}
    const readingPanel=content.querySelector('.wb-reading-panel');
    const phaseStatus=readingPanel.querySelector('.wb-phase-status');
    phaseStatus.textContent=readDone?'Magaling! Nabasa mo nang tama ang lahat ng pantig.':state.last_feedback||'Basahin muna ang mga pantig sa Big Box.';
    phaseStatus.insertAdjacentHTML('beforebegin',`<p class="wb-reading-target-label">Pantig na babasahin</p><strong class="wb-reading-target">${esc(readDone?'Natapos na ang pagbasa.':a.items[current]?.text||'')}</strong><p class="wb-reading-attempts">Pagsubok: ${readDone?0:Number(state.reading_attempts||0)} / 3</p><div class="wb-transcript" aria-live="polite"><span>NARINIG KO</span><strong>${esc(state.last_transcript||'Hindi ko malinaw na narinig.')}</strong></div>`);
    const itemById=Object.fromEntries(a.items.map(i=>[i.id,i]));
    content.querySelectorAll('.wb-bigbox-row').forEach((row,rowIndex)=>{
      row.querySelectorAll('.wb-bigbox-cell').forEach((cell,cellIndex)=>{
        const itemIds=boxCells[rowIndex][cellIndex]||[];
        cell.replaceChildren(...itemIds.map(id=>{
          const item=itemById[id];if(!item)return null;
          const tile=document.createElement('button');tile.type='button';tile.className='wb-bigbox-tile';tile.dataset.tile=item.id;tile.textContent=item.text;tile.disabled=!readDone||preview;tile.setAttribute('aria-label',`Pantig ${item.text}`);if(builder.includes(item.id))tile.classList.add('is-picked');if(!readDone){const itemIndex=a.items.findIndex(candidate=>candidate.id===item.id);if(itemIndex<current)tile.classList.add('is-complete');if(itemIndex===current){tile.classList.add('is-active');if(current===0)tile.insertAdjacentHTML('afterbegin','<span class="wb-start-cue">Simulan dito</span>');}}tile.onclick=()=>{if(busy)return;builder.push(item.id);paint();tile.classList.add('is-picked');draft({builder});};return tile;
        }).filter(Boolean));
      });
    });
    const paint=()=>{const selected=document.getElementById('wb-selected-parts');if(!selected)return;selected.replaceChildren(...builder.map(id=>{const span=document.createElement('span');span.className='wb-selected-part';span.textContent=piecesById[id]||'';return span;}));};
    paint();
    if(readDone){
      document.getElementById('wb-erase').onclick=()=>{builder.pop();draft({builder});paint();content.querySelectorAll('[data-tile]').forEach(t=>t.classList.toggle('is-picked',builder.includes(t.dataset.tile)));};
      document.getElementById('wb-retry').onclick=()=>{builder=[];draft({builder});paint();content.querySelectorAll('[data-tile]').forEach(t=>t.classList.remove('is-picked'));};
      button('Suriin ang Sagot',()=>perform({action:'build_word',parts:builder}),true).disabled=!builder.length;
      button('Tapusin ang Gawain',()=>perform({action:'finish'}),false).disabled=!(state.found_words||[]).length;
      button('Susunod',()=>{if(data.next_url)location.href=data.next_url;}).disabled=true;
    }else if(!preview){
      const readingButton=(text,fn,primary=true)=>{const b=button(text,fn,primary);if(!primary)b.classList.add('wb-secondary');const target=document.getElementById('wb-l22-reading-action');if(target)target.appendChild(b);return b;};
      if(phase==='help'){
        readingButton('Pakinggan ang Tamang Pagbigkas',readAloudC,true);
        if(state.pronunciation_help_played)readingButton('Subukan Muli',retryCReading,false);
      }else readingButton(state.read_aloud_started?'🎙 Basahin ang Pantig':'🎙 Basahin ang mga Pantig',startCReading);
    }
    if(!preview){
      const restart=button('Ulitin Mula sa Simula',()=>{
        if(window.confirm(`Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa ${qBuilder?'Gawain 6':'Gawain 1'}.`)) perform({action:'restart'});
      },false);
      restart.classList.add('wb-secondary');
    }
  }
  async function startCReading(){
    if(busy)return;stopReadAloud();busy=true;lock();let chunks=[],readTimer,recorder;const requestIndex=Number(state.index||0),requestActivity=a.activity_key;
    try{
      await send({action:'reading_started'},null,false);
      if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw new Error('Hindi available ang mikropono sa browser na ito.');
      activeStream=await Promise.race([navigator.mediaDevices.getUserMedia({audio:true}),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Hindi tumugon ang mikropono.')),8000))]);
      recorder=activeRecorder=new MediaRecorder(activeStream);
      const audioDone=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onerror=()=>reject(new Error('Hindi mabasa ang recording.'));recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}));});
      recorder.start();message('Nakikinig...');
      action.replaceChildren();const stop=button('Tapusin ang Pagbasa',()=>recorder.state==='recording'&&recorder.stop(),true);stop.disabled=false;const readingAction=document.getElementById('wb-l22-reading-action');if(readingAction)readingAction.appendChild(stop);
      readTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},3500);
      const audio=await audioDone;clearTimeout(readTimer);activeStream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(!audio.size)throw new Error('Walang nakuha sa recording. Subukan muli.');
      if(requestActivity!==a.activity_key||requestIndex!==Number(state.index||0))return;
      const form=new FormData();form.append('audio',audio,'reading.webm');message('Sinusuri ang iyong pagbasa...');
      await send({action:'reading_syllable_attempt',item_index:requestIndex},form,false);render();
      pendingSpeech=state.read_aloud_completed?'Magaling! Nabasa mo nang tama ang lahat ng pantig.':state.last_feedback==='Tama!'?'Tama!':'Subukan muli.';
      message(pendingSpeech);
    }catch(error){
      clearTimeout(readTimer);
      activeStream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      const micError=error?.name==='NotAllowedError'||error?.name==='NotFoundError'||error?.name==='NotReadableError'||error?.name==='SecurityError';
      render();
      pendingSpeech=micError?'Hindi magamit ang mikropono. Subukan muli.':(error?.message||'Hindi nakuha ang iyong boses. Subukan muli.');
      message(pendingSpeech,true);
    }finally{clearTimeout(readTimer);busy=false;lock();const speech=pendingSpeech;pendingSpeech='';if(speech)playPrescribedAudio(speech).catch(e=>console.error('Lesson 22 feedback audio failed',e));}
  }
  async function retryCReading(){
    if(busy)return;stopReadAloud();busy=true;lock();
    try{await send({action:'retry_reading'},null,false);render();message('Handa ka na?');pendingSpeech='Handa ka na?';}
    catch(e){const text=e.message||'Hindi maihanda ang pagbasa. Subukan muli.';render();message(text,true);if(l23G1&&G1_MAPPED_TEXT.has(text))pendingSpeech=text;}
    finally{busy=false;lock();const speech=pendingSpeech;pendingSpeech='';if(speech)playPrescribedAudio(speech).catch(e=>console.error('Lesson 22 retry audio failed',e));}
  }
  async function readAloudC(){
    if(busy)return;stopReadAloud();busy=true;lock();const current=Math.min(Number(state.index||0),a.items.length-1);
    try{await playPrescribedAudio(a.items[current].text,true);await send({action:'read_aloud'},null,false);render();}catch(e){const text=e.message||'Hindi available ang audio.';render();message(text,true);if(l23G1&&G1_MAPPED_TEXT.has(text))await playPrescribedAudio(text,true).catch(()=>{});}finally{stopReadAloud();busy=false;lock();}
  }
  function renderSearch(){
    content.innerHTML+=`<div class="wb-search-wrap"><ul class="wb-word-list">${a.items.map((i,n)=>`<li>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(i.text)}${!preview&&state.answers[i.id]?' ✓':''}</li>`).join('')}</ul><label>${fil?'Kulay':'Color'} <input id="wb-color" type="color" value="${esc(state.draft.color||'#b6e6c3')}"></label><div class="wb-search ${a.mark_style}" style="--cols:${a.grid[0].length}">${a.grid.map((row,y)=>Array.from(row).map((letter,x)=>`<button type="button" data-y="${y}" data-x="${x}" aria-label="Row ${y+1}, column ${x+1}: ${esc(letter)}">${esc(letter)}</button>`).join('')).join('')}</div></div>`;
    const found=Object.values(state.answers).flat();
    content.querySelectorAll('.wb-search button').forEach(b=>{
      const y=Number(b.dataset.y),x=Number(b.dataset.x);
      if(!preview&&found.some(p=>p[0]===y&&p[1]===x)){b.classList.add('wb-found');const match=Object.entries(state.answers).find(([,path])=>path.some(p=>p[0]===y&&p[1]===x));b.style.setProperty('--mark',state.mark_colors?.[match?.[0]]||'#b6e6c3');}
      b.disabled=preview||!oral().passed;
      b.onclick=()=>{if(busy)return;if(!selected.length){selected=[[y,x]];}else{const [sy,sx]=selected[0],dy=y-sy,dx=x-sx;if(dx&&dy&&Math.abs(dx)!==Math.abs(dy)){selected=[[y,x]];}else{selected=Array.from({length:Math.max(Math.abs(dx),Math.abs(dy))+1},(_,i)=>[sy+i*Math.sign(dy),sx+i*Math.sign(dx)]);}}content.querySelectorAll('.wb-search button').forEach(cell=>cell.classList.toggle('wb-selected',selected.some(p=>p[0]===+cell.dataset.y&&p[1]===+cell.dataset.x)));draft({selected});};
    });
    if(!preview){selected=state.draft.selected||[];content.querySelectorAll('.wb-search button').forEach(b=>b.classList.toggle('wb-selected',selected.some(p=>p[0]===+b.dataset.y&&p[1]===+b.dataset.x)));}
    document.getElementById('wb-color').oninput=e=>{content.style.setProperty('--mark',e.target.value);draft({color:e.target.value});};
  }
  function renderBuilder(){
    const box=document.createElement('div');box.className='wb-builder';box.innerHTML=`<p>${fil?'Pumili ng mga pantig upang bumuo ng salita.':'Choose syllables to build a word.'}</p><div class="wb-syllable-tiles">${a.items.map(i=>`<button type="button" data-part="${i.id}">${esc(i.text)}</button>`).join('')}</div><div id="wb-building" class="wb-building">${fil?'Pipiliin mong salita ay lalabas dito.':'Your word will appear here.'}</div><div class="wb-tools"><button type="button" id="wb-add">${fil?'Idagdag':'Add word'}</button><button type="button" id="wb-clear">${fil?'Burahin':'Clear'}</button></div><div id="wb-words" class="wb-builder-words"></div>`;content.appendChild(box);
    const wordText=parts=>parts.map(id=>a.items.find(i=>i.id===id)?.text||'').join('');
    const paint=()=>{box.querySelector('#wb-building').textContent=builder.length?wordText(builder):(fil?'Pipiliin mong salita ay lalabas dito.':'Your word will appear here.');box.querySelector('#wb-words').textContent=words.map(wordText).join(', ');};
    box.querySelectorAll('[data-part]').forEach(b=>{b.disabled=preview||!oral().passed;b.onclick=()=>{builder.push(b.dataset.part);b.classList.add('is-picked');paint();draft({builder,words});};});
    box.querySelector('#wb-add').disabled=preview||!oral().passed;box.querySelector('#wb-clear').disabled=preview||!oral().passed;
    box.querySelector('#wb-add').onclick=()=>{if(builder.length){words.push([...builder]);builder=[];box.querySelectorAll('[data-part]').forEach(b=>b.classList.remove('is-picked'));paint();draft({builder,words});}};
    box.querySelector('#wb-clear').onclick=()=>{builder=[];box.querySelectorAll('[data-part]').forEach(b=>b.classList.remove('is-picked'));paint();draft({builder,words});};paint();
    if(!preview)button(fil?'Isumite ang mga salita':'Submit words',()=>perform({action:'answer',answer:words}),true);
    else box.querySelectorAll('button').forEach(b=>b.disabled=true);
  }
  function written(prompt){content.innerHTML+=`<div class="wb-focus"><p>${esc(prompt)}</p><label for="wb-written">${fil?'Sagot':'Answer'}</label><textarea id="wb-written" ${preview||a.oral_flow&&!oral().passed?'disabled':''}>${esc(preview?'':state.draft.text||'')}</textarea></div>`;document.getElementById('wb-written').oninput=e=>draft({text:e.target.value});}
  function renderSyllables(){
    if(a.worked_example)content.innerHTML+=`<p>${esc(a.worked_example)}</p>`;
    if(preview){content.innerHTML+=a.items.map((it,n)=>`<p>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(it.text)} = ________________</p>`).join('');}
    else {const it=item();const n=state.index;content.innerHTML+=`<div class="wb-focus wb-syllable-focus"><p>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(it.text)} = ________________</p></div>`;}
    if(!preview)written(item().text+' = __________');
  }
  function renderFill(){
    content.innerHTML+=`<p>( ${a.options.map(esc).join(', ')} )</p><table class="wb-table"><tr>${a.options.map(x=>`<td>${esc(x)}</td>`).join('')}</tr></table>`;
    if(preview){content.innerHTML+=a.items.map(it=>`<p>${esc(it.text)}</p>`).join('');return;}
    let index=0;
    const sentence=esc(item().text).replace(/_+/g,()=>{const i=index++;return `<select data-blank="${i}" aria-label="Blank ${i+1}"><option value="">_____</option>${a.options.map(o=>`<option value="${esc(o)}" ${state.draft.blanks?.[i]===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;});
    content.innerHTML+=`<div class="wb-focus">${sentence}</div>`;
    content.querySelectorAll('[data-blank]').forEach(select=>select.onchange=()=>draft({blanks:[...content.querySelectorAll('[data-blank]')].map(s=>s.value)}));
  }
  function renderDrawing(){
    content.innerHTML+='<div class="wb-drawing-card"><div class="wb-tools"><label>Color <input type="color" id="wb-pen" value="#24576b"></label><button type="button" id="wb-undo">Undo stroke</button></div><canvas id="wb-canvas" width="900" height="500" aria-label="Draw your picture"></canvas></div>';
    written('Write under your drawing.');
    const canvas=document.getElementById('wb-canvas'),ctx=canvas.getContext('2d');let strokes=structuredClone(state.draft.strokes||[]),stroke=null;
    const redraw=()=>{ctx.clearRect(0,0,900,500);for(const s of strokes){ctx.strokeStyle=s.color;ctx.lineWidth=5;ctx.lineCap='round';ctx.beginPath();s.points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();}};
    const point=e=>{const r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(900,(e.clientX-r.left)*900/r.width)),Math.max(0,Math.min(500,(e.clientY-r.top)*500/r.height))];};
    canvas.onpointerdown=e=>{if(preview||busy)return;canvas.setPointerCapture(e.pointerId);stroke={color:document.getElementById('wb-pen').value,points:[point(e)]};strokes.push(stroke);};
    canvas.onpointermove=e=>{if(!stroke)return;if(stroke.points.length<3000)stroke.points.push(point(e));redraw();};
    const end=()=>{if(stroke){if(stroke.points.length===1)stroke.points.push([...stroke.points[0]]);stroke=null;draft({strokes});}};canvas.onpointerup=end;canvas.onpointercancel=end;
    document.getElementById('wb-undo').onclick=()=>{strokes.pop();redraw();draft({strokes});};redraw();
  }
  async function record(){
    if(busy)return;busy=true;lock();let stream;
    try{
      stream=await navigator.mediaDevices.getUserMedia({audio:true});const chunks=[];const recorder=new MediaRecorder(stream);
      const audio=await new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onerror=reject;recorder.onstop=()=>resolve(new Blob(chunks,{type:recorder.mimeType}));recorder.start();message(fil?'Nagbabasa…':'Recording…');const stop=button(fil?'Tapos nang basahin':'Done reading',()=>recorder.stop());stop.disabled=false;const timer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},60000);recorder.addEventListener('stop',()=>{clearTimeout(timer);stop.remove();});});
      stream.getTracks().forEach(t=>t.stop());message(fil?'Pinakikinggan ang iyong pagbasa…':'Checking your reading…');const form=new FormData();form.append('audio',audio,'reading.webm');await send(null,form);render();
    }catch(e){message(e.message||'Microphone unavailable. Please try again.',true);}finally{stream?.getTracks().forEach(t=>t.stop());busy=false;lock();}
  }
  async function aloud(){
    if(busy)return;busy=true;lock();
    await window.PabasaTemplateTts.speak({text:item().text,profile:'word',onEnd:async()=>{try{await send({action:oral().phase==='model'?'model_listened':'listened'});render();}catch(e){message(e.message,true);}finally{busy=false;lock();}},onError:e=>{message(e.message,true);busy=false;lock();}});
  }
  window.addEventListener('beforeunload',e=>{activeRecorder?.stop();activeStream?.getTracks().forEach(t=>t.stop());stopReadAloud();if(!specializedBuilder&&busy){e.preventDefault();e.returnValue='';}});
  render();
})();
