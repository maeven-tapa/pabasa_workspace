(() => {
  'use strict';
  const start = () => {
    const root = document.querySelector('[data-session3-controls]');
    if (!root || !window.PrescribedControls || root.dataset.initialized === 'true') return;
    const prefix = root.dataset.prefix;
    if (!prefix) return;
    const q = suffix => document.getElementById(`${prefix}${suffix}`);
    let isMuted = false, generation = 0, testStream = null, testContext = null, analyser = null, frame = 0;
    const streams = new Set(), recorders = new Set(), recognitions = new Set(), history = [];
    let requestingTestStream = false;
    const media = () => [...document.querySelectorAll('audio,video')];
    const write = (suffix, value) => { const el = q(suffix); if (el && el.textContent !== String(value)) el.textContent = String(value); };
    const debug = (patch, message) => { Object.entries(patch || {}).forEach(([k,v]) => write(`-debug-${k}`, v)); if (message) { history.push(message); while (history.length > 6) history.shift(); write('-debug-raw', history.join('\n')); } };
    const expected = () => {
      const visible = document.querySelector('#app .item, #app .reading img, #app .oral-img, #app .picture, #app .task .item, #app .reading .word, .item-text,.lesson-13-sentence,.lesson-13-word,.wordbox .red-label,.item.active img,.focus .picture img');
      if (!visible) return 'Not available';
      return (visible.alt || visible.textContent || '').replace(/^Larawan:?\s*/i, '').trim() || 'Not available';
    };
    const refresh = () => write('-debug-expected', expected());
    const updateMic = () => { const b=q('-mic-toggle'), i=b?.querySelector('i'); if(!b||!i)return; i.classList.toggle('bi-mic-fill',!isMuted); i.classList.toggle('bi-mic-mute-fill',isMuted); b.classList.toggle('is-muted',isMuted); b.setAttribute('aria-pressed',String(isMuted)); b.setAttribute('aria-label',isMuted?'I-unmute ang mikropono':'I-mute ang mikropono'); b.title=isMuted?'I-unmute ang mikropono':'I-mute ang mikropono'; write('-debug-mic',`${streams.size?'Active':'Inactive'} · ${isMuted?'Muted':'Unmuted'}`); };
    const stopTest = () => { if(frame) cancelAnimationFrame(frame); frame=0; testStream?.getTracks().forEach(t=>t.stop()); testStream=null; try{testContext?.close()}catch(_){} testContext=null; analyser=null; const f=q('-level-fill'); if(f)f.style.width='0%'; const s=q('-settings-status'); if(s)s.innerHTML='<strong>Microphone Status:</strong> Not tested'; const b=q('-test-toggle'); if(b){b.dataset.testing='false';b.innerHTML='<i class="bi bi-mic-fill"></i> Start Test';} };
    const level = () => { if(!analyser)return; const a=new Uint8Array(analyser.fftSize); analyser.getByteTimeDomainData(a); let p=0; a.forEach(v=>p=Math.max(p,Math.abs(v-128))); const f=q('-level-fill'); if(f)f.style.width=`${Math.min(100,Math.round(p*100/128))}%`; frame=requestAnimationFrame(level); };
    const bindTest = () => { const b=q('-test-toggle'), sel=q('-device-select'); if(!b||b.dataset.bound)return; b.dataset.bound='true'; b.onclick=async()=>{if(testStream){stopTest();return} try{const audio=sel?.value?{deviceId:{exact:sel.value}}:true;requestingTestStream=true;testStream=await navigator.mediaDevices.getUserMedia({audio});requestingTestStream=false;testContext=new(window.AudioContext||window.webkitAudioContext)();const source=testContext.createMediaStreamSource(testStream);analyser=testContext.createAnalyser();source.connect(analyser);b.dataset.testing='true';b.innerHTML='<i class="bi bi-stop-fill"></i> Stop Test';q('-settings-status').innerHTML='<strong>Microphone Status:</strong> Ready';level();const devices=await navigator.mediaDevices.enumerateDevices();if(sel){sel.replaceChildren(new Option('Default microphone',''));devices.filter(d=>d.kind==='audioinput').forEach(d=>sel.add(new Option(d.label||`Microphone ${sel.length}`,d.deviceId)));}}catch(e){requestingTestStream=false;stopTest();q('-settings-status').innerHTML=`<strong>Microphone Status:</strong> ${e.message||'Microphone unavailable'}`}}; };
    const cleanup = () => { generation++; stopTest(); recorders.forEach(r=>{try{if(r.state==='recording')r.stop()}catch(_){}}); recorders.clear(); streams.forEach(s=>s.getTracks().forEach(t=>t.stop())); streams.clear(); media().forEach(a=>{try{a.pause()}catch(_){}}); };
    const reportRecognitionResult = (recognition, event) => {
      const transcript = String(event?.results?.[event.results.length - 1]?.[0]?.transcript || '').trim();
      if (!transcript) return;
      debug({status:'Processing', transcript, expected:expected(), recorder:'Not available'}, `Transcript received: ${transcript}`);
      setTimeout(() => {
        const status = document.querySelector('#app #status, #app #feedback, #app .status, #app .feedback')?.textContent || '';
        const result = /magaling|tama|accepted|correct/i.test(status) ? 'Correct' : /hindi|muli|mali|wrong|pakinggan|subukan/i.test(status) ? 'Incorrect' : 'Not available';
        debug({expected:expected(), result}, result === 'Not available' ? '' : `Result: ${result.toLowerCase()}`);
      }, 0);
    };
    const OriginalRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (OriginalRecognition && !OriginalRecognition.__session3Wrapped) {
      const WrappedRecognition = new Proxy(OriginalRecognition, { construct(target, args, newTarget) {
        const recognition = Reflect.construct(target, args, newTarget);
        const observed = new Proxy(recognition, { set(targetObject, property, value) {
          if (property === 'onresult' && typeof value === 'function') {
            const handler = value;
            value = function(event) {
              reportRecognitionResult(observed, event);
              const result = Reflect.apply(handler, this, arguments);
              Promise.resolve(result).then(() => {
                const status = document.querySelector('#app #status, #app #feedback, #app .status, #app .feedback')?.textContent || '';
                const reading = /magaling|tama|accepted|correct/i.test(status) ? 'Correct' : /hindi|muli|mali|wrong|pakinggan|subukan/i.test(status) ? 'Incorrect' : 'Not available';
                debug({expected:expected(), result:reading}, reading === 'Not available' ? '' : `Result: ${reading.toLowerCase()}`);
              });
              return result;
            };
          } else if (property === 'onerror' && typeof value === 'function') {
            const handler = value;
            value = function(event) {
              debug({status:'Error', error:event?.error || 'Speech recognition error'}, `Recognition error: ${event?.error || 'unknown'}`);
              return Reflect.apply(handler, this, arguments);
            };
          }
          return Reflect.set(targetObject, property, value);
        }});
        recognitions.add(observed);
        observed.addEventListener?.('start', () => { debug({status:'Listening', expected:expected(), recorder:'Not available'}, 'Speech recognition started'); });
        observed.addEventListener?.('end', () => { recognitions.delete(observed); debug({status:'Ready', recorder:'Not available'}, 'Speech recognition ended'); });
        return observed;
      }});
      WrappedRecognition.__session3Wrapped = true;
      window.SpeechRecognition = WrappedRecognition;
      window.webkitSpeechRecognition = WrappedRecognition;
    }
    const reset = async () => { cleanup(); const data=[...document.scripts].find(s=>s.type==='application/json'&&s.textContent.includes('progress_url')); try { const d=data&&JSON.parse(data.textContent); const m=document.cookie.match(/(?:^|; )csrftoken=([^;]+)/); if(d&&d.progress_url) await fetch(d.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':m?m[1]:''},body:JSON.stringify({reset:true})}); } catch(_) {} location.reload(); };
    const OriginalGetUserMedia=navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices); if(OriginalGetUserMedia&&!navigator.mediaDevices.getUserMedia.__session3Wrapped){const wrapped=async constraints=>{const stream=await OriginalGetUserMedia(constraints);if(!requestingTestStream){streams.add(stream);stream.getTracks().forEach(t=>t.enabled=!isMuted);stream.addEventListener?.('inactive',()=>streams.delete(stream),{once:true});debug({mic:`Active · ${isMuted?'Muted':'Unmuted'}`},'Activity microphone opened');}return stream;};wrapped.__session3Wrapped=true;navigator.mediaDevices.getUserMedia=wrapped;}
    const OriginalRecorder=window.MediaRecorder; if(OriginalRecorder&&!OriginalRecorder.__session3Wrapped){window.MediaRecorder=new Proxy(OriginalRecorder,{construct(target,args,newTarget){const r=Reflect.construct(target,args,newTarget);recorders.add(r);r.addEventListener?.('start',()=>debug({status:isMuted?'Muted':'Listening',recorder:'Recording'},'Recording started'));r.addEventListener?.('stop',()=>{debug({status:'Processing',recorder:'Inactive'},'Recording stopped');recorders.delete(r)},{once:true});return r;}});window.MediaRecorder.__session3Wrapped=true;}
    const adapter={pause(){recognitions.forEach(r=>{try{r.abort()}catch(_){}});cleanup();debug({status:'Paused'},'Activity paused')},resume(){debug({status:'Ready'},'Activity resumed')},restart:reset,cleanup(){recognitions.forEach(r=>{try{r.abort()}catch(_){}});recognitions.clear();cleanup();},setMuted(v){isMuted=Boolean(v);streams.forEach(s=>s.getTracks().forEach(t=>t.enabled=!isMuted));updateMic();debug({},isMuted?'Microphone muted':'Microphone unmuted');},bindAudioTest:bindTest,bindDebug(){const t=q('-debug-toggle'),p=q('-debug-panel');if(!t||!p||t.dataset.bound)return;t.dataset.bound='true';try{t.checked=localStorage.getItem('pabasaShowSpeechDebugPanel')==='true'}catch(_){};const render=()=>{p.hidden=!t.checked;p.setAttribute('aria-hidden',String(!t.checked));refresh()};t.onchange=()=>{try{localStorage.setItem('pabasaShowSpeechDebugPanel',String(t.checked))}catch(_){}render()};render();}};
    updateMic(); refresh(); window.PrescribedControls.init({prefix,adapter}); root.dataset.initialized='true'; window.addEventListener('pagehide',cleanup,{once:true});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
