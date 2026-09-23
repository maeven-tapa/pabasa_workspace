(() => {
  'use strict';
  const root = document.querySelector('[data-session1-controls]');
  if (!root || !window.PrescribedControls) return;
  const prefix = root.dataset.prefix;
  window.__session1ControlsInitialized ||= {};
  if (!prefix || window.__session1ControlsInitialized[prefix]) return;
  let muted = false, paused = false, requestingTest = false, testStream = null, testContext = null, analyser = null, frame = 0, generation = 0;
  const streams = new Set(), recorders = new Set(), q = suffix => document.getElementById(`${prefix}${suffix}`);
  const history = [];
  const setDebug = (patch = {}, entry = '') => {
    Object.entries(patch).forEach(([key, value]) => { const field = q(`-debug-${key}`); if (field && field.textContent !== String(value)) field.textContent = String(value); });
    if (entry) { history.push(entry); while (history.length > 6) history.shift(); const raw = q('-debug-raw'); if (raw) raw.textContent = history.join('\n'); }
  };
  window.__session1SpeechDebugReport = report => {
    if (!report || (report.prefix && report.prefix !== prefix)) return;
    const result = report.result || 'Not available';
    setDebug({
      transcript: report.transcript ?? q('-debug-transcript')?.textContent ?? 'Not available',
      normalized: report.normalized ?? q('-debug-normalized')?.textContent ?? 'Not available',
      result,
      status: result === 'Correct' ? 'Correct' : result === 'Retry' ? 'Try again' : result === 'Incorrect' ? 'Try again' : 'Processing',
      error: report.error || q('-debug-error')?.textContent || 'Not available',
    }, `Result: ${String(result).toLowerCase()}`);
  };
  const normalizeSpeech = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim();
  const expectedText = () => {
    const active = document.querySelector('.word.active img, .word.active strong, .tile.active .tile-word');
    if (active?.textContent?.trim()) return active.textContent.trim();
    if (active?.alt?.trim()) return active.alt.trim();
    const status = document.querySelector('#status');
    const match = status?.textContent?.match(/(?:Basahin ang|Sabihin ang pangalan ng larawan\.)\s*([^.!?]+)/i);
    return match?.[1]?.trim() || (document.body.classList.contains('lesson-one-page') ? 'Alpabetong Pilipino' : 'Not available');
  };
  const refreshDebug = () => { const field=q('-debug-expected'); if(field){const next=expectedText()||'Not available';if(field.textContent!==next)field.textContent=next;} };
  const stopAudio = () => document.querySelectorAll('audio,video').forEach(x => { try { x.pause(); } catch (_) {} });
  const stopResources = () => { generation += 1; recorders.forEach(r => { try { if (r.state === 'recording') r.stop(); } catch (_) {} }); recorders.clear(); streams.forEach(s => s.getTracks().forEach(t => t.stop())); streams.clear(); stopAudio(); window.speechSynthesis?.cancel(); };
  const updateMic = () => { const b=q('-mic-toggle'), i=b?.querySelector('i'); if (!b||!i) return; i.className=`bi ${muted?'bi-mic-mute-fill':'bi-mic-fill'}`; b.classList.toggle('is-muted',muted); b.title=muted?'I-unmute ang mikropono':'I-mute ang mikropono'; b.setAttribute('aria-label',b.title); b.setAttribute('aria-pressed',String(muted)); setDebug({mic:`${streams.size?'Active':'Inactive'} · ${muted?'Muted':'Unmuted'}`}); };
  const stopTest = () => { if(frame)cancelAnimationFrame(frame); frame=0; testStream?.getTracks().forEach(t=>t.stop()); testStream=null; try{testContext?.close()}catch(_){} testContext=null; analyser=null; const f=q('-level-fill');if(f)f.style.width='0%'; const s=q('-settings-status');if(s)s.innerHTML='<strong>Microphone Status:</strong> Not tested'; const b=q('-test-toggle');if(b){b.innerHTML='<i class="bi bi-mic-fill"></i> Start Test';b.dataset.testing='false';} };
  const meter=()=>{if(!analyser)return;const a=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(a);let p=0;a.forEach(v=>p=Math.max(p,Math.abs(v-128)));const f=q('-level-fill');if(f)f.style.width=`${Math.min(100,Math.round(p*100/128))}%`;frame=requestAnimationFrame(meter)};
  const bindAudioTest=()=>{const b=q('-test-toggle'),s=q('-device-select');if(!b||b.dataset.bound)return;b.dataset.bound='true';b.onclick=async()=>{if(testStream){stopTest();return}try{requestingTest=true;testStream=await navigator.mediaDevices.getUserMedia({audio:s?.value?{deviceId:{exact:s.value}}:true});requestingTest=false;testContext=new(window.AudioContext||window.webkitAudioContext)();const source=testContext.createMediaStreamSource(testStream);analyser=testContext.createAnalyser();source.connect(analyser);b.dataset.testing='true';b.innerHTML='<i class="bi bi-stop-fill"></i> Stop Test';q('-settings-status').innerHTML='<strong>Microphone Status:</strong> Ready';meter()}catch(e){requestingTest=false;stopTest();q('-settings-status').innerHTML=`<strong>Microphone Status:</strong> ${e.message||'Microphone unavailable'}`}};s?.addEventListener('change',()=>{if(testStream){stopTest();b.click()}})};
  const bindDebug=()=>{const t=q('-debug-toggle'),p=q('-debug-panel');if(!t||!p||t.dataset.bound)return;t.dataset.bound='true';let saved=false;try{saved=localStorage.getItem('pabasaShowSpeechDebugPanel')==='true'}catch(_){}t.checked=saved;const render=()=>{p.hidden=!t.checked;p.setAttribute('aria-hidden',String(!t.checked));refreshDebug()};t.onchange=()=>{try{localStorage.setItem('pabasaShowSpeechDebugPanel',String(t.checked))}catch(_){}render()};render()};
  const resetActivity=async()=>{stopResources();const config=window.__lessonStartProgress;let url=config?.progressUrl;let activityKey=config?.activityKey;let totalItems=config?.totalItems;if(!url){try{const data=JSON.parse(document.getElementById('lesson-one-data')?.textContent||'{}');url=data.progress_url;activityKey='lesson-1-gawain-1';totalItems=11}catch(_){} }if(url){try{const csrf=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||'';await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({activity_key:activityKey,reset:true,total_items:totalItems})});}catch(_){} }try{config?.storageKeys?.forEach(key=>localStorage.removeItem(key))}catch(_){}window.location.reload()};
  const adapter={pause(){paused=true;setDebug({status:'Paused'},'Activity paused');stopResources()},resume(){paused=false;setDebug({status:'Ready'},'Activity resumed')},restart:resetActivity,cleanup(){stopTest();stopResources()},setMuted(v){muted=Boolean(v);streams.forEach(s=>s.getTracks().forEach(t=>t.enabled=!muted));updateMic();setDebug({status:muted?'Muted':'Ready'},muted?'Microphone muted':'Microphone unmuted')},bindAudioTest,bindDebug};
  const wrapRecorder=()=>{const Native=window.MediaRecorder;if(!Native||Native.__session1Wrapped)return;const Wrapped=new Proxy(Native,{construct(target,args,newTarget){const recorder=Reflect.construct(target,args,newTarget);recorders.add(recorder);setDebug({status:muted?'Muted':'Listening',recorder:'Recording'},'Recording started');recorder.addEventListener?.('stop',()=>{recorders.delete(recorder);setDebug({recorder:'Inactive',status:'Processing'},'Recording stopped')},{once:true});recorder.addEventListener?.('error',event=>setDebug({error:event.error?.message||'Recorder error',recorder:'Inactive'},'Recorder error'));return recorder}});Wrapped.__session1Wrapped=true;window.MediaRecorder=Wrapped;};
  const reportVisibleFeedback=()=>{const text=document.querySelector('#status,.status')?.textContent?.trim()||'';if(/Hindi pa ito tama|Subukan muli|Hindi ito ang tamang sagot/i.test(text))window.__session1SpeechDebugReport?.({result:'Incorrect'});};
  const bindActivityReports=()=>{const logger=window.salitangSpeechDebugLog;if(typeof logger==='function'&&!logger.__session1Wrapped){const wrapped=fields=>{logger(fields);if(fields?.exact_match!==undefined)window.__session1SpeechDebugReport?.({transcript:fields.raw_transcript||fields.final_transcript,normalized:fields.normalized_transcript,result:fields.exact_match?'Correct':'Incorrect'});};wrapped.__session1Wrapped=true;window.salitangSpeechDebugLog=wrapped;}};
  const wrapTranscription=()=>{const native=window.fetch;if(!native||native.__session1Wrapped)return;const wrapped=async(...args)=>{const input=String(args[0]?.url||args[0]||'');const speechRequest=/transcrib|reading\/lesson/i.test(input);if(!speechRequest)return native(...args);const beforeExpected=q('-debug-expected')?.textContent||'';setDebug({status:'Processing',error:'Not available'},'STT request started');try{const response=await native(...args);response.clone().json().then(data=>{const transcript=String(data.raw_transcript||data.transcript||'').trim();setDebug({transcript:transcript||'Not available',status:'Processing'},'Transcript received');window.setTimeout(()=>{reportVisibleFeedback();if(prefix.includes('l3g1')&&beforeExpected&&q('-debug-expected')?.textContent&&q('-debug-expected').textContent!==beforeExpected)window.__session1SpeechDebugReport?.({result:'Correct'});},0)}).catch(()=>{});return response}catch(error){setDebug({error:error.message||'STT request failed',status:'Ready'},'STT request error');throw error}};wrapped.__session1Wrapped=true;window.fetch=wrapped;};
  if(navigator.mediaDevices?.getUserMedia&&!navigator.mediaDevices.getUserMedia.__session1Wrapped){const native=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);const wrapped=async c=>{if(muted&&!requestingTest)throw new DOMException('Microphone is muted','NotAllowedError');const s=await native(c);if(!requestingTest)streams.add(s);s.getTracks().forEach(t=>t.enabled=!muted);updateMic();return s};wrapped.__session1Wrapped=true;navigator.mediaDevices.getUserMedia=wrapped;}
  wrapRecorder();
  wrapTranscription();
  const init=()=>{if(window.__session1ControlsInitialized[prefix])return;window.PrescribedControls.init({prefix,adapter});window.__session1ControlsInitialized[prefix]=true;updateMic();setDebug({status:'Ready',recorder:'Inactive',vad:'Not available',error:'Not available'});refreshDebug();bindActivityReports();document.addEventListener('click',event=>{if(event.target.closest('#read,#listen,.read-btn,.answer,.hand,#ready,#startSing,#retrySing'))window.setTimeout(()=>{refreshDebug();bindActivityReports()},0)});window.addEventListener('lesson-start-ready',()=>{refreshDebug();bindActivityReports()});window.addEventListener('pagehide',()=>adapter.cleanup(),{once:true});};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
