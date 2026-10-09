(() => {
  'use strict';
  const root = document.querySelector('[data-prescribed-session-controls]');
  if (!root || !window.PrescribedControls) return;
  const prefix = root.dataset.prefix;
  const q = suffix => document.getElementById(`${prefix}${suffix}`);
  let isMuted = false, paused = false, testStream = null, testContext = null;
  let testAnalyser = null, testSource = null, frame = 0, testing = false, testRequest = false;
  const streams = new Set(), recorders = new Set(), requests = new Set();
  const media = () => [...document.querySelectorAll('audio,video')];
  const history = [];
  const data = () => { const node = [...document.scripts].find(item => item.type === 'application/json' && item.textContent.includes('progress_url')); try { return JSON.parse(node?.textContent || '{}'); } catch (_) { return {}; } };
  const csrfToken = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const refreshExpected = () => { const field = q('-debug-expected'); if (!field) return; if (prefix === 'prescribed-s7-l19-g1') { const exact = window.__session7L19G1ExpectedText || 'Not reading'; if (field.textContent !== exact) field.textContent = exact; return; } if (prefix === 'prescribed-s7-l19-g3') { const exact = window.__session7L19G3ExpectedText || 'Not reading'; if (field.textContent !== exact) field.textContent = exact; return; } const node = document.querySelector('[data-expected-text], .target, .item-text, .wb-reading-target, .wb-picture-word, .wb-j-word.is-current, .wb-syllable-row.is-current, .wb-syllable-focus, .wb-builder-words, .word-list .current, .word.active, .word.current, .word, .lesson27-verse.active'); const domText = node?.getAttribute('data-expected-text') || node?.textContent?.trim(); const payload = data(); const state = payload.progress?.state || {}; const items = Array.isArray(payload.items) ? payload.items : []; const index = Math.max(0, Number(state.current_item_index ?? state.current_index ?? state.current_scored_index ?? 0) || 0); const item = items[index] || {}; const completed = state.orally_completed_words?.[String(index)] || state.completed_oral_reads?.[String(index)] || state.completed_oral_words?.[String(index)] || []; const readingIndex = Math.max(0, Number(state.current_oral_word_index ?? state.current_reading_index ?? state.current_word_index ?? completed.length) || 0); const dataText = item.word || item.words?.[readingIndex] || item.choices?.[readingIndex] || ''; const next = domText || dataText || 'Not available'; if (field.textContent !== next) field.textContent = next; };
  if (prefix === 'prescribed-s7-l19-g1') window.addEventListener('session7-l19-g1-expected-changed', refreshExpected);
  const debug = (patch = {}, message = '') => { Object.entries(patch).forEach(([key, value]) => { const field = q(`-debug-${key}`); if (field && field.textContent !== String(value ?? 'Not available')) field.textContent = String(value ?? 'Not available'); }); if (message) { history.push(message); while (history.length > 6) history.shift(); const raw = q('-debug-output') || q('-debug-raw'); if (raw) raw.textContent = history.join('\n'); } refreshExpected(); };
  const isSpeechRequest = input => /reading_transcribe_api|\/api\/reading\/transcribe\//.test(String(input?.url || input || ''));
  const bindSpeechDebug = () => {
    window.addEventListener('basahin:state', event => {
      const detail = event.detail || {}, state = detail.state;
      if (state === 'level') {
        debug({vad:detail.speaking ? 'Speaking' : (detail.calibrating ? 'Calibrating' : 'Quiet'), status:detail.speaking ? 'Listening' : 'Waiting'});
        return;
      }
      const labels = {calibrating:'Calibrating', waiting:'Waiting for speech', listening:'Speaking detected', silence:'Silence / no speech', processing:'Processing', idle:'Ready'};
      if (labels[state]) debug({vad:labels[state], status:state === 'processing' ? 'Processing' : (state === 'idle' ? 'Ready' : 'Listening')}, `VAD · ${labels[state]}`);
    });
    const monitor = window.setInterval(() => {
      recorders.forEach(recorder => {
        if (!recorder.__prescribedSessionDebugBound) {
          recorder.__prescribedSessionDebugBound = true;
          recorder.addEventListener?.('error', event => debug({recorder:'Error', status:'Error', error:event.error?.message || 'Recorder error'}, 'Recorder error'));
        }
        const state = recorder.state === 'recording' ? 'Recording' : (recorder.state === 'paused' ? 'Paused' : 'Inactive');
        if (recorder.__prescribedSessionDebugState !== state) {
          recorder.__prescribedSessionDebugState = state;
          debug({recorder:state, status:state === 'Recording' ? 'Listening' : (state === 'Paused' ? 'Paused' : 'Processing')}, `Recorder · ${state}`);
        }
      });
    }, 50);
    window.addEventListener('pagehide', () => window.clearInterval(monitor), {once:true});
    const originalFetch = window.fetch.bind(window);
    const wrappedFetch = (input, init) => {
      if (prefix === 'prescribed-s7-l19-g3' && isSpeechRequest(input)) debug({status:'Processing',transcript:'Awaiting transcription response',result:'Processing',acceptance:'Pending',error:'Not available'}, 'STT request started');
      return originalFetch(input, init).then(response => {
      if (!isSpeechRequest(input)) return response;
      response.clone().json().then(result => {
        const transcript = result?.transcript || result?.raw_transcript || result?.text || result?.recognized_text;
        const correct = result?.complete === true || result?.correct === true;
        const failed = result?.success === false || result?.complete === false;
        if (prefix === 'prescribed-s7-l19-g3') {
          const serverTranscript = result?.transcript || result?.normalized_transcript || result?.normalized_value || result?.value || 'Not returned';
          const accepted = result?.complete === true ? 'Accepted by server' : result?.complete === false ? 'Rejected by server' : 'Not returned';
          debug({transcript:serverTranscript, result:result?.complete === true ? 'Correct' : result?.complete === false ? 'Incorrect' : 'Not returned', acceptance:accepted, recorder:'Inactive', error:result?.error || (!response.ok || result?.success !== true ? 'Speech API failure' : 'None')}, `STT response · ${accepted}`);
        } else {
          debug({transcript:transcript || 'No transcript returned', result:correct ? 'Correct' : (failed ? 'Incorrect' : 'Processed'), error:result?.error || 'Not available'}, `STT response · ${correct ? 'accepted' : (failed ? 'rejected' : 'processed')}`);
        }
      }).catch(() => prefix === 'prescribed-s7-l19-g3'
        ? debug({transcript:'Not returned',result:'Failed',acceptance:'Not returned',recorder:'Inactive',error:'Invalid STT response'}, 'STT response could not be read')
        : debug({result:'Failed', error:'Invalid STT response'}, 'STT response could not be read'));
      return response;
    }).catch(error => {
      if (isSpeechRequest(input)) {
        if (prefix === 'prescribed-s7-l19-g3') debug({transcript:'Not returned',result:'Failed',acceptance:'Not returned',recorder:'Inactive',error:error.message || 'Speech request failed'}, 'STT request failed');
        else debug({result:'Failed', error:error.message || 'Speech request failed'}, 'STT request failed');
      }
      throw error;
      });
    };
    wrappedFetch.__prescribedSessionSttWrapped = true;
    window.fetch = wrappedFetch;
  };
  const stopTest = () => { if (frame) cancelAnimationFrame(frame); frame = 0; testSource?.disconnect(); testSource = null; testAnalyser = null; testContext?.close?.().catch?.(() => {}); testContext = null; testStream?.getTracks().forEach(track => track.stop()); testStream = null; testing = false; const fill = q('-level-fill'); if (fill) fill.style.width = '0%'; const button = q('-test-toggle'); if (button) button.innerHTML = '<i class="bi bi-mic-fill" aria-hidden="true"></i> Start Test'; };
  const meter = () => { if (!testAnalyser || !testing) return; const values = new Uint8Array(testAnalyser.fftSize); testAnalyser.getByteTimeDomainData(values); let sum = 0; for (const value of values) { const sample = (value - 128) / 128; sum += sample * sample; } const level = Math.min(100, Math.round(Math.sqrt(sum / values.length) * 260)); q('-level-fill')?.style.setProperty('width', `${level}%`); q('-level-fill')?.parentElement?.setAttribute('aria-valuenow', String(level)); frame = requestAnimationFrame(meter); };
  const startTest = async () => { if (testing || !navigator.mediaDevices?.getUserMedia || !window.AudioContext) return; try { testRequest = true; const select = q('-device-select'); testStream = await navigator.mediaDevices.getUserMedia(select?.value ? {audio:{deviceId:{exact:select.value}}} : {audio:true}); testRequest = false; testContext = new AudioContext(); testAnalyser = testContext.createAnalyser(); testAnalyser.fftSize = 512; testSource = testContext.createMediaStreamSource(testStream); testSource.connect(testAnalyser); testing = true; q('-settings-status').innerHTML = '<strong>Microphone Status:</strong> Access granted. Testing live input.'; q('-test-toggle').innerHTML = '<i class="bi bi-stop-fill" aria-hidden="true"></i> Stop Test'; meter(); } catch (_) { testRequest = false; stopTest(); q('-settings-status').innerHTML = '<strong>Microphone Status:</strong> Access denied or unavailable.'; } };
  const stopActivity = () => { recorders.forEach(recorder => { try { if (recorder.state === 'recording' || recorder.state === 'paused') recorder.stop(); } catch (_) {} }); recorders.clear(); streams.forEach(stream => stream.getTracks().forEach(track => track.stop())); streams.clear(); media().forEach(element => { try { element.pause(); } catch (_) {} }); requests.forEach(controller => controller.abort()); requests.clear(); };
  const setMic = value => { isMuted = Boolean(value); streams.forEach(stream => stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; })); const button = q('-mic-toggle'); if (button) { button.setAttribute('aria-pressed', String(isMuted)); button.setAttribute('aria-label', isMuted ? 'Unmute microphone' : 'Mute microphone'); button.title = isMuted ? 'Unmute microphone' : 'Mute microphone'; button.classList.toggle('is-muted', isMuted); button.innerHTML = `<i class="bi ${isMuted ? 'bi-mic-mute-fill' : 'bi-mic-fill'}" aria-hidden="true"></i>`; } debug({mic:`${streams.size ? 'Active' : 'Inactive'} · ${isMuted ? 'Muted' : 'Unmuted'}`, status:isMuted ? 'Muted' : (paused ? 'Paused' : 'Ready')}, isMuted ? 'Microphone muted' : 'Microphone unmuted'); };
  const patchMedia = () => { const devices = navigator.mediaDevices; if (devices?.getUserMedia && !devices.getUserMedia.__prescribedSessionWrapped) { const original = devices.getUserMedia.bind(devices); const wrapped = async constraints => { if (isMuted && !testRequest) throw new DOMException('Microphone is muted.', 'NotAllowedError'); const stream = await original(constraints); if (!testRequest) { streams.add(stream); stream.getAudioTracks().forEach(track => { track.enabled = !isMuted; }); } return stream; }; wrapped.__prescribedSessionWrapped = true; devices.getUserMedia = wrapped; } const OriginalRecorder = window.MediaRecorder; if (OriginalRecorder && !OriginalRecorder.__prescribedSessionWrapped) { const Wrapped = new Proxy(OriginalRecorder, {construct(target, args, newTarget) { const recorder = Reflect.construct(target, args, newTarget); recorders.add(recorder); recorder.addEventListener?.('stop', () => recorders.delete(recorder), {once:true}); return recorder; }}); Wrapped.__prescribedSessionWrapped = true; window.MediaRecorder = Wrapped; } };
  const patchFetch = () => { if (prefix === 'prescribed-s7-l19-g3' || !window.fetch || window.fetch.__prescribedSessionWrapped) return; const original = window.fetch.bind(window); const wrapped = (input, init = {}) => { const controller = new AbortController(); requests.add(controller); const options = {...init, signal: init.signal || controller.signal}; return original(input, options).finally(() => requests.delete(controller)).then(response => { window.requestAnimationFrame(refreshExpected); return response; }); }; wrapped.__prescribedSessionWrapped = true; window.fetch = wrapped; };
  const addGawain3DebugFields = panel => { if (prefix !== 'prescribed-s7-l19-g3' || !panel) return; const insert = (id,label,after) => { if (q(`-debug-${id}`)) return; const row=document.createElement('div'); row.className='prescribed-session-row'; row.innerHTML=`<span class="prescribed-session-key">${label}</span><span class="prescribed-session-value" id="${prefix}-debug-${id}">Not returned</span>`; const anchor=q(`-debug-${after}`)?.closest('.prescribed-session-row, .session67-debug-row'); panel.insertBefore(row,anchor?.nextSibling||null); }; insert('transcript','Transcript','result'); insert('acceptance','Server Acceptance','transcript'); };
  const adapter = { pause() { paused = true; stopActivity(); window.dispatchEvent(new CustomEvent('prescribed-session-paused', {detail:{prefix}})); debug({status:'Paused',recorder:'Inactive'}); }, resume() { paused = false; window.dispatchEvent(new CustomEvent('prescribed-session-resumed', {detail:{prefix}})); debug({status:isMuted ? 'Muted' : 'Ready'}); }, async restart() { stopActivity(); stopTest(); const payload = data(); if (payload.progress_url) await fetch(payload.progress_url, {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},body:JSON.stringify({reset:true})}); window.location.reload(); }, cleanup() { stopActivity(); stopTest(); paused = true; }, cleanupForLeave() { stopTest(); paused = true; }, setMuted: setMic, bindAudioTest() { q('-test-toggle')?.addEventListener('click', () => testing ? stopTest() : startTest()); q('-device-select')?.addEventListener('change', () => { if (testing) { stopTest(); startTest(); } }); navigator.mediaDevices?.enumerateDevices?.().then(devices => { const select=q('-device-select'); if (!select) return; select.replaceChildren(new Option('Default microphone','')); devices.filter(device => device.kind === 'audioinput').forEach(device => select.add(new Option(device.label || `Microphone ${select.options.length}`, device.deviceId))); }).catch(() => {}); }, bindDebug() { const toggle=q('-debug-toggle'), panel=q('-debug-panel'); if (!toggle || !panel) return; addGawain3DebugFields(panel); let saved=false; if (prefix !== 'prescribed-s7-l19-g3') { try { saved=localStorage.getItem('pabasaShowSpeechDebugPanel') === 'true'; } catch (_) {} } toggle.checked=saved; const render=()=>{panel.hidden=!toggle.checked; panel.setAttribute('aria-hidden',String(!toggle.checked)); document.body.classList.toggle('session7-l19-g3-debug-open',prefix === 'prescribed-s7-l19-g3' && toggle.checked); refreshExpected();}; toggle.addEventListener('change',()=>{try { if (prefix !== 'prescribed-s7-l19-g3') localStorage.setItem('pabasaShowSpeechDebugPanel',String(toggle.checked)); } catch(_){} render();}); render(); if (prefix === 'prescribed-s7-l19-g3') debug({result:'Waiting',recorder:'Inactive',vad:'Waiting',error:'None'}); else debug({}); } };
  patchMedia(); patchFetch(); bindSpeechDebug(); window.PrescribedControls.init({prefix, adapter}); q('-help-btn')?.addEventListener('click', () => stopActivity()); window.requestAnimationFrame(refreshExpected); window.addEventListener('pagehide', () => { stopActivity(); stopTest(); }, {once:true});
})();
