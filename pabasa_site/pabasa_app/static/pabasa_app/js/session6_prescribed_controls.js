(() => {
  'use strict';
  const root = document.querySelector('[data-session6-controls]');
  if (!root || !window.PrescribedControls) return;
  const prefix = root.dataset.prefix;
  if (!prefix || window.__session6ControlsInitialized?.[prefix]) return;

  // All Session 6 activity renderers use independent Audio instances. Keep
  // their playback serialized at the page boundary so a delayed narration or
  // word response cannot play over a newer instruction/feedback clip.
  if (!window.__session6AudioPlaybackGuard) {
    const NativeAudio = window.Audio;
    let activeAudio = null;
    let activeReadAloudController = null;
    const clear = player => {
      if (activeAudio === player) activeAudio = null;
    };
    const Session6Audio = function (...args) {
      activeAudio?.pause();
      const player = new NativeAudio(...args);
      activeAudio = player;
      player.addEventListener('ended', () => clear(player), {once: true});
      player.addEventListener('error', () => clear(player), {once: true});
      return player;
    };
    Session6Audio.prototype = NativeAudio.prototype;
    window.Audio = Session6Audio;
    window.__session6AudioPlaybackGuard = {
      cancel() {
        activeReadAloudController?.abort();
        activeReadAloudController = null;
        activeAudio?.pause();
        activeAudio = null;
      },
    };
    const NativeFetch = window.fetch?.bind(window);
    if (NativeFetch && !window.__session6ReadAloudGuard) {
      const guardedFetch = (input, init = {}) => {
        const target = String(input?.url || input || '');
        if (!target.includes('/api/reading/read-aloud/')) return NativeFetch(input, init);
        activeReadAloudController?.abort();
        const controller = new AbortController();
        activeReadAloudController = controller;
        return NativeFetch(input, {...init, signal: controller.signal}).finally(() => {
          if (activeReadAloudController === controller) activeReadAloudController = null;
        });
      };
      guardedFetch.__session6ReadAloudGuard = true;
      window.fetch = guardedFetch;
      window.__session6ReadAloudGuard = true;
    }
    window.addEventListener('session6-prescribed-cancel', () => window.__session6AudioPlaybackGuard.cancel());
    window.addEventListener('pagehide', () => window.__session6AudioPlaybackGuard.cancel(), {once: true});
  }
  const q = suffix => document.getElementById(`${prefix}${suffix}`);
  let isMuted = false, paused = false, generation = 0, testing = false;
  let testStream = null, testContext = null, testSource = null, testAnalyser = null, testFrame = 0;
  const streams = new Set(), recorders = new Set(), history = [];
  const setField = (name, value) => { const node = q(`-debug-${name}`); const next = String(value ?? 'Not available'); if (node && node.textContent !== next) node.textContent = next; };
  const debugState = patch => Object.entries(patch || {}).forEach(([name, value]) => setField(name, value));
  const note = message => { history.push(message); while (history.length > 6) history.shift(); setField('output', history.join('\n')); };
  const ensureDebugFields = () => { const panel = q('-debug-panel'); if (!panel) return; [['result', 'Reading Result'], ['error', 'Error']].forEach(([name, label]) => { if (q(`-debug-${name}`)) return; const row = document.createElement('div'); row.className = 'session67-debug-row'; row.innerHTML = `<span class="session67-debug-key">${label}</span><span class="session67-debug-value" id="${prefix}-debug-${name}">Not available</span>`; const output = q('-debug-output'); panel.insertBefore(row, output?.parentElement || null); }); };
  const stopAudio = () => document.querySelectorAll('audio,video').forEach(media => { try { media.pause(); } catch (_) {} });
  const expected = () => { const activeOral = document.querySelector('#oral,#oral-action,#oralAction,#read-word,#read-current'); const explicitTarget = activeOral && document.querySelector('[data-expected-text]'); if (explicitTarget?.dataset.expectedText?.trim()) return explicitTarget.dataset.expectedText.trim(); const node = document.querySelector('.oral-word,.word.active,.oral-card .word,.oral-reading .word,.word'); if (node?.textContent.trim()) return node.textContent.trim(); const partial = document.querySelector('.partial,.prompt .blank'); if (partial?.textContent.trim()) return partial.textContent.trim(); if (!activeOral) return 'Not available'; const image = document.querySelector('#app img[alt^="Larawan ng "]'); return image ? image.alt.replace(/^Larawan ng\s*/i, '').trim() || 'Not available' : 'Not available'; };
  const refreshDebug = () => { setField('expected', expected()); setField('mic', `${streams.size ? 'Active' : 'Inactive'} · ${isMuted ? 'Muted' : 'Unmuted'}`); };
  const updateMic = () => { const button = q('-mic-toggle'), icon = button?.querySelector('i'); if (!button || !icon) return; icon.classList.toggle('bi-mic-fill', !isMuted); icon.classList.toggle('bi-mic-mute-fill', isMuted); button.classList.toggle('is-muted', isMuted); button.setAttribute('aria-pressed', String(isMuted)); button.setAttribute('aria-label', isMuted ? 'I-unmute ang mikropono' : 'I-mute ang mikropono'); button.title = isMuted ? 'I-unmute ang mikropono' : 'I-mute ang mikropono'; refreshDebug(); };
  const stopTest = () => { if (testFrame) cancelAnimationFrame(testFrame); testFrame = 0; testStream?.getTracks().forEach(track => track.stop()); testStream = null; try { testSource?.disconnect(); testAnalyser?.disconnect(); testContext?.close(); } catch (_) {} testSource = testAnalyser = testContext = null; const level = q('-level-fill'); if (level) level.style.width = '0%'; const button = q('-test-toggle'); if (button) button.innerHTML = '<i class="bi bi-mic-fill" aria-hidden="true"></i> Start Test'; };
  const drawLevel = () => { if (!testAnalyser) return; const values = new Uint8Array(testAnalyser.fftSize); testAnalyser.getByteTimeDomainData(values); let peak = 0; values.forEach(value => { peak = Math.max(peak, Math.abs(value - 128)); }); const level = q('-level-fill'); if (level) level.style.width = `${Math.min(100, Math.round(peak * 100 / 128))}%`; testFrame = requestAnimationFrame(drawLevel); };
  const bindAudioTest = () => { const button = q('-test-toggle'), select = q('-device-select'), status = q('-settings-status'); if (!button || button.dataset.bound) return; button.dataset.bound = 'true'; const populate = async () => { try { const devices = await navigator.mediaDevices?.enumerateDevices?.() || []; const prior = select.value; select.replaceChildren(new Option('Default microphone', '')); devices.filter(device => device.kind === 'audioinput').forEach(device => select.add(new Option(device.label || `Microphone ${select.length}`, device.deviceId))); select.value = prior; } catch (_) {} }; button.addEventListener('click', async () => { if (testStream) { stopTest(); return; } try { testing = true; testStream = await navigator.mediaDevices.getUserMedia({audio: select?.value ? {deviceId: {exact: select.value}} : true}); testing = false; testContext = new (window.AudioContext || window.webkitAudioContext)(); testSource = testContext.createMediaStreamSource(testStream); testAnalyser = testContext.createAnalyser(); testAnalyser.fftSize = 256; testSource.connect(testAnalyser); if (status) status.innerHTML = '<strong>Microphone Status:</strong> Ready'; button.innerHTML = '<i class="bi bi-stop-fill" aria-hidden="true"></i> Stop Test'; drawLevel(); await populate(); } catch (error) { testing = false; stopTest(); if (status) status.textContent = `Microphone Status: ${error?.message || 'Microphone unavailable'}`; } }); select?.addEventListener('change', () => { if (testStream) { stopTest(); button.click(); } }); populate(); };
  const bindDebug = () => { const toggle = q('-debug-toggle'), panel = q('-debug-panel'); if (!toggle || !panel || toggle.dataset.bound) return; toggle.dataset.bound = 'true'; let stored = false; try { stored = localStorage.getItem('pabasaShowSpeechDebugPanel') === 'true'; } catch (_) {} toggle.checked = stored; const render = () => { panel.hidden = !toggle.checked; panel.setAttribute('aria-hidden', String(!toggle.checked)); refreshDebug(); }; toggle.addEventListener('change', () => { try { localStorage.setItem('pabasaShowSpeechDebugPanel', String(toggle.checked)); } catch (_) {} render(); }); render(); };
  const cancelAttempt = (reason = 'cancel') => { generation += 1; window.__session6CanceledGeneration = generation; window.dispatchEvent(new CustomEvent('session6-prescribed-cancel', {detail: {prefix, generation, reason}})); recorders.forEach(recorder => { try { if (recorder.state !== 'inactive') recorder.stop(); } catch (_) {} }); streams.forEach(stream => stream.getTracks().forEach(track => track.stop())); streams.clear(); stopAudio(); debugState({status: reason === 'pause' ? 'Paused' : 'Canceled', recorder: 'Inactive', vad: 'Canceled'}); note(`Active attempt ${reason}`); refreshDebug(); };
  const readTranscriptionResponse = async response => { try { const payload = await response.clone().json(); const transcript = payload.raw_transcript || payload.transcript || ''; const accepted = Boolean(response.ok && payload.success && payload.complete === true); debugState({status: 'STT complete', result: `${transcript || 'No transcript returned'} · ${accepted ? 'Correct' : (payload.success ? 'Incorrect / incomplete' : 'Failed')}`, error: response.ok && !payload.error ? '—' : (payload.error || `HTTP ${response.status}`), recorder: 'Inactive'}); note(`Transcription response · ${accepted ? 'accepted' : 'rejected'}`); } catch (error) { debugState({status: 'Error', result: 'Malformed STT response', error: `Invalid speech response: ${error.message || 'unknown error'}`}); note('Unable to read transcription response'); } };
  const wrapMedia = () => { const devices = navigator.mediaDevices; if (devices?.getUserMedia && !devices.getUserMedia.__session6Controls) { const original = devices.getUserMedia.bind(devices); const wrapped = async constraints => { const stream = await original(constraints); if (!testing) { streams.add(stream); stream.getTracks().forEach(track => { track.enabled = !isMuted; }); debugState({status: isMuted ? 'Muted' : 'Listening', error: '—', vad: 'Microphone open; waiting for speech'}); note('Activity microphone opened'); refreshDebug(); } return stream; }; wrapped.__session6Controls = true; devices.getUserMedia = wrapped; } const Native = window.MediaRecorder; if (Native && !Native.__session6Controls) { const Wrapped = new Proxy(Native, {construct(target, args, newTarget) { const recorder = Reflect.construct(target, args, newTarget); recorders.add(recorder); recorder.addEventListener('start', () => { window.__session6CanceledGeneration = 0; debugState({recorder: 'Recording', status: 'Listening', vad: 'Recording', error: '—', result: 'Processing'}); note('Recording started'); }); recorder.addEventListener('stop', () => { recorders.delete(recorder); debugState({recorder: 'Inactive', status: 'Processing'}); note('Recording stopped'); }); return recorder; }}); Wrapped.__session6Controls = true; window.MediaRecorder = Wrapped; } if (window.fetch && !window.fetch.__session6Controls) { const originalFetch = window.fetch.bind(window); const guardedFetch = (...args) => { const target = String(args[0]?.url || args[0] || ''); const transcription = /transcrib/i.test(target); if (window.__session6CanceledGeneration && transcription) return Promise.reject(Error('Canceled Session 6 speech attempt')); const captured = generation; return originalFetch(...args).then(async response => { if (captured !== generation) throw Error('Canceled Session 6 activity operation'); if (transcription) await readTranscriptionResponse(response); requestAnimationFrame(refreshDebug); return response; }).catch(error => { if (transcription) { debugState({status: 'Error', result: 'Failed', error: error.message || 'Speech request failed'}); note(`Speech request error · ${error.message || 'unknown error'}`); } throw error; }); }; guardedFetch.__session6Controls = true; window.fetch = guardedFetch; } };
  const directVads = new Map();
  const startDirectVad = (recorder, suppliedStream = null) => {
    if (directVads.has(recorder) || !window.Basahin?.createVad) return;
    const stream = suppliedStream || Array.from(streams).pop(), AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!stream || !AudioContext) return;
    try {
      const context = new AudioContext(), source = context.createMediaStreamSource(stream), analyser = context.createAnalyser();
      context.resume?.().catch(() => {});
      analyser.fftSize = 1024;
      source.connect(analyser);
      const samples = new Uint8Array(analyser.fftSize), vad = window.Basahin.createVad(), started = performance.now();
      vad.takeSpeech();
      const state = {context, source, analyser, samples, vad, started, frame: 0};
      const tick = () => {
        if (recorder.state === 'inactive') return;
        analyser.getByteTimeDomainData(samples);
        let sum = 0;
        for (const sample of samples) sum += ((sample - 128) / 128) ** 2;
        const level = vad.sample(Math.sqrt(sum / samples.length), performance.now() - started);
        debugState({vad: level.calibrating ? 'Calibrating' : (level.speaking ? 'Speaking' : 'Quiet'), status: level.speaking ? 'Listening' : 'Waiting'});
        state.frame = requestAnimationFrame(tick);
      };
      directVads.set(recorder, state);
      tick();
    } catch (_) {}
  };
  const stopDirectVad = recorder => {
    const state = directVads.get(recorder);
    if (!state) return;
    cancelAnimationFrame(state.frame);
    try { state.source.disconnect(); state.analyser.disconnect(); state.context.close(); } catch (_) {}
    directVads.delete(recorder);
  };
  const directVadTimer = window.setInterval(() => {
    recorders.forEach(recorder => { if (recorder.state === 'recording') startDirectVad(recorder); });
    directVads.forEach((_, recorder) => { if (recorder.state === 'inactive') stopDirectVad(recorder); });
  }, 60);
  window.addEventListener('pagehide', () => { window.clearInterval(directVadTimer); directVads.forEach((_, recorder) => stopDirectVad(recorder)); }, {once: true});
  const reset = async () => { cancelAttempt(); const data = [...document.querySelectorAll('script[type="application/json"]')].map(script => { try { return JSON.parse(script.textContent || '{}'); } catch (_) { return null; } }).find(value => value?.progress_url); if (!data?.progress_url) throw Error('Restart is unavailable for this activity.'); const csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || ''; const response = await fetch(data.progress_url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: JSON.stringify({reset: true})}); const result = await response.json().catch(() => ({})); if (!response.ok || !result.success) throw Error(result.error || 'Hindi na-reset ang gawain.'); window.location.replace(`${window.location.pathname}?restart=${Date.now()}`); };
  const adapter = { pause() { paused = true; cancelAttempt('pause'); }, resume() { paused = false; window.dispatchEvent(new CustomEvent('session6-prescribed-resume', {detail: {prefix}})); debugState({status: 'Ready', error: '—'}); refreshDebug(); }, restart: reset, cleanup() { cancelAttempt('cleanup'); stopTest(); window.dispatchEvent(new CustomEvent('session6-prescribed-cleanup', {detail: {prefix}})); }, cancelAttempt, stopAudioTest: stopTest, setMuted(value) { isMuted = Boolean(value); if (isMuted) cancelAttempt('mute'); else streams.forEach(stream => stream.getTracks().forEach(track => { track.enabled = true; })); updateMic(); note(isMuted ? 'Microphone muted' : 'Microphone unmuted'); }, bindAudioTest, bindDebug };
  document.addEventListener('click', event => { const button = event.target.closest('button'); if (isMuted && button && (button.id === 'oral' || /🎙|Basahin|Pagbasa|SIMULAN ANG PAGBASA/u.test(button.textContent || ''))) { event.preventDefault(); event.stopImmediatePropagation(); debugState({status: 'Muted', vad: 'Muted'}); note('Muted speech attempt blocked'); } }, true);
  const init = () => { if (window.__session6ControlsInitialized?.[prefix]) return; ensureDebugFields(); wrapMedia(); window.addEventListener('basahin:state', event => { const detail = event.detail || {}; if (detail.state === 'level') { debugState({vad: detail.speaking ? 'Speaking' : (detail.calibrating ? 'Calibrating' : 'Quiet')}); return; } const labels = {calibrating: 'Calibrating', waiting: 'Waiting for speech', listening: 'Speaking detected', silence: 'Silence / no speech', processing: 'Processing speech', idle: 'Ready'}; if (labels[detail.state]) { debugState({status: labels[detail.state], vad: labels[detail.state]}); note(`Speech · ${labels[detail.state]}`); } }); updateMic(); window.PrescribedControls.init({prefix, adapter}); try { bindAudioTest(); bindDebug(); } catch (_) {} window.__session6ControlsInitialized = window.__session6ControlsInitialized || {}; window.__session6ControlsInitialized[prefix] = true; refreshDebug(); window.addEventListener('session6-prescribed-render', refreshDebug); document.addEventListener('click', () => requestAnimationFrame(refreshDebug)); window.addEventListener('pagehide', () => { cancelAttempt(); stopTest(); }, {once: true}); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true}); else init();
  window.PrescribedSession6Controls = {refreshDebug, isMuted: () => isMuted, generation: () => generation};
})();
