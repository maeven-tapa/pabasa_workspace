(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent || '{}');
  const activity = data.activity, app = document.getElementById('l22g5-app');
  const instruction = 'Hanapin at bilugan sa loob ng Big Box ang mga salita sa ibaba.';
  const paths = {Fina:[[0,3],[0,4],[0,5],[0,6]],fries:[[2,1],[2,2],[2,3],[2,4],[2,5]],Filipino:[[3,0],[3,1],[3,2],[3,3],[3,4],[3,5],[3,6]],freezer:[[4,0],[4,1],[4,2],[4,3],[4,4],[4,5],[4,6]],Felix:[[5,3],[5,4],[5,5],[5,6],[5,7]]};
  let state = {...(data.state || {})}, phase = 'READY', active = null, busy = false, audio = null, audioBusy = false;
  const words = activity.items.map(item => item.text), found = () => state.found_words && typeof state.found_words === 'object' ? state.found_words : {};
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pathBetween = (start, end) => start && end && start[0] === end[0] && end[1] >= start[1] ? Array.from({length:end[1]-start[1]+1},(_,i)=>[start[0],start[1]+i]) : [];
  const paint = path => document.querySelectorAll('.cell').forEach(cell => cell.classList.toggle('selected', path.some(([r,c]) => r === +cell.dataset.row && c === +cell.dataset.col)));
  const setFeedback = (text, error=false) => { const node=document.getElementById('feedback'); if(node){node.textContent=text||'';node.className=`feedback${error?' error':''}`;} };
  async function playInstruction(){
    if (audioBusy || data.preview) return;
    audioBusy = true; const form = new FormData(); form.append('target_text', instruction); form.append('language','Filipino'); form.append('mode','reading'); form.append('prescribed_activity_key', activity.activity_key);
    try { const r=await fetch(data.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':csrf()},body:form}); const j=await r.json(); if(!r.ok||!j.success||!j.audio_content) throw Error('Hindi available ang audio. Subukan muli.'); audio=new Audio(`data:${j.mime_type||'audio/mpeg'};base64,${j.audio_content}`); await audio.play(); await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=reject;}); }
    catch(e){setFeedback(e.message||'Hindi available ang audio. Subukan muli.',true);} finally {audio?.pause();audio=null;audioBusy=false;}
  }
  async function send(event){
    if(data.preview) return {success:true,state};
    const r=await fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({...event,revision:Number(state.revision||0)})});
    const j=await r.json().catch(()=>({})); if(!r.ok||!j.success) throw Error(j.error||'Hindi na-save ang gawain.'); state=j.state; return j;
  }
  function render(){
    const done=found(), count=Object.keys(done).length;
    if(state.completed){app.innerHTML=`<div class="shell"><header class="header"><a class="back" href="${esc(data.back_url)}">Aking Aralin</a><p class="eyebrow">SESSION 8 · LESSON 22 · GAWAIN 5</p><h1>Hanapin ang mga salita: F</h1></header><section class="complete"><h2>Magaling! Nahanap mo ang lahat ng salita!</h2><p class="progress">Nahanap: 5 / 5</p><div class="controls"><a class="button" href="${esc(data.next_url||data.back_url)}">Magpatuloy sa Gawain 6</a><a class="button secondary" href="${esc(data.back_url)}">Bumalik sa Aking Aralin</a></div></section></div>`; return;}
    app.innerHTML=`<div class="shell"><header class="header"><a class="back" href="${esc(data.back_url)}">Aking Aralin</a><p class="eyebrow">SESSION 8 · LESSON 22 · GAWAIN 5</p><h1>Hanapin ang mga salita: F</h1><p class="instruction">${esc(instruction)}</p><button id="tts" class="tts" type="button">🔊 Pakinggan ang Panuto</button><p class="progress">Nahanap: ${count} / 5</p></header><section class="activity-card"><div class="grid-wrap"><div id="grid" class="grid" aria-label="6 by 8 na Big Box" role="grid">${activity.grid.map((row,r)=>Array.from(row).map((letter,c)=>`<button class="cell" type="button" role="gridcell" data-row="${r}" data-col="${c}" aria-label="Hanay ${r+1}, kolum ${c+1}: ${esc(letter)}">${esc(letter)}</button>`).join('')).join('')}</div><p class="helper">Pindutin ang unang letra at i-drag pakaliwa pakanan sa iisang hanay.</p></div><aside class="word-list"><h2>MGA SALITANG HAHANAPIN</h2><ul>${words.map(word=>`<li class="${done[word]?'found':''}"><span aria-hidden="true">${done[word]?'✓':'○'}</span><span>${esc(word)}</span></li>`).join('')}</ul><p id="feedback" class="feedback" role="status" aria-live="polite">${esc(state.last_feedback||'')}</p><button id="restart" class="restart" type="button">Ulitin Mula sa Simula</button></aside></section><div id="confirm" class="confirm" hidden><div class="confirm-card"><p>Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa Gawain 5.</p><div class="confirm-actions"><button id="cancel" type="button">Kanselahin</button><button id="confirm-restart" class="primary" type="button">Magsimula Muli</button></div></div></div></div>`;
    const grid=document.getElementById('grid'); Object.values(done).forEach(entry=>entry.path.forEach(([r,c])=>grid.querySelector(`[data-row="${r}"][data-col="${c}"]`)?.classList.add('found')));
    document.getElementById('tts').onclick=playInstruction;
    document.getElementById('restart').onclick=()=>document.getElementById('confirm').hidden=false;
    document.getElementById('cancel').onclick=()=>document.getElementById('confirm').hidden=true;
    document.getElementById('confirm-restart').onclick=async()=>{if(busy)return;busy=true;try{await send({action:'restart'});document.getElementById('confirm').hidden=true;render();}catch(e){setFeedback(e.message,true);}finally{busy=false;}};
    grid.addEventListener('pointerdown',e=>{const cell=e.target.closest('.cell');if(!cell||busy||data.preview||phase!=='READY')return;phase='SELECTING';active={id:e.pointerId,start:[+cell.dataset.row,+cell.dataset.col],path:[[+cell.dataset.row,+cell.dataset.col]]};grid.setPointerCapture(e.pointerId);e.preventDefault();paint(active.path);});
    grid.addEventListener('pointermove',e=>{if(phase!=='SELECTING'||!active||e.pointerId!==active.id)return;const cell=document.elementFromPoint(e.clientX,e.clientY)?.closest('.cell');if(!cell||!grid.contains(cell))return;active.path=pathBetween(active.start,[+cell.dataset.row,+cell.dataset.col]);paint(active.path);e.preventDefault();});
    const finish=async e=>{if(phase!=='SELECTING'||!active||e.pointerId!==active.id)return;const gesture=active;active=null;paint([]);phase='VALIDATING';try{const cell=document.elementFromPoint(e.clientX,e.clientY)?.closest('.cell');const path=cell?pathBetween(gesture.start,[+cell.dataset.row,+cell.dataset.col]):gesture.path;if(path.length<2){phase='READY';return;}busy=true;const word=words.find(w=>JSON.stringify(paths[w])===JSON.stringify(path))||'';const result=await send({action:'select_word',word,path,color:'#b6e6c3'});render();setFeedback(result.state.last_feedback||'');}catch(err){setFeedback(err.message,true);}finally{busy=false;if(!state.completed)phase='READY';}};
    grid.addEventListener('pointerup',finish);grid.addEventListener('pointercancel',()=>{active=null;paint([]);phase='READY';});grid.addEventListener('lostpointercapture',()=>{if(phase==='SELECTING'){active=null;paint([]);phase='READY';}});
  }
  window.addEventListener('pagehide',()=>audio?.pause()); render();
})();
