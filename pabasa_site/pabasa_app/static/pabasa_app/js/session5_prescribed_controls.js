(() => {
  'use strict';

  const root = document.querySelector('[data-session5-controls]');
  if (!root || !window.PrescribedControls) return;
  const prefix = root.dataset.prefix;
  if (!prefix || window.__session5ControlsInitialized?.[prefix]) return;
  window.__session5ControlsInitialized = window.__session5ControlsInitialized || {};

  const q = suffix => document.getElementById(`${prefix}${suffix}`);
  let isMuted = false;
  let testStream = null;
  let testContext = null;
  let testAnalyser = null;
  let testFrame = 0;
  let paused = false;
  let requestingTest = false;
  let generation = 0;
  const activityStreams = new Set();
  const activityRecorders = new Set();
  const debugHistory = [];
  const media = () => Array.from(document.querySelectorAll('audio,video'));
  const debug = (patch = {}, message = '') => {
    Object.entries(patch).forEach(([key, value]) => { const field = q(`-debug-${key}`); if (field) field.textContent = value; });
    if (message) {
      debugHistory.push(message);
      while (debugHistory.length > 6) debugHistory.shift();
      const raw = q('-debug-raw');
      if (raw) raw.textContent = debugHistory.join('\n');
    }
    refreshExpectedText();
  };

  const expectedDataIds = {
    'prescribed-s5l13g1': 'lesson13-data',
    'prescribed-s5l13g2': 'lesson13-gawain2-data',
    'prescribed-s5l13g3': 'lesson13-gawain3-data',
    'prescribed-s5l14g1': 'lesson14-data',
    'prescribed-s5l14g2': 'lesson14-gawain2-data',
    'prescribed-s5l14g3': 'lesson14-gawain3-data',
    'prescribed-s5l15g1': 'lesson15-gawain1-data',
    'prescribed-s5l15g2': 'lesson15-gawain2-data',
  };

  const readJsonScript = id => {
    const script = document.getElementById(id);
    if (!script) return null;
    try { return JSON.parse(script.textContent || '{}'); } catch (_) { return null; }
  };

  const currentIndex = data => {
    const state = data?.progress?.state || {};
    return Math.max(0, Number(state.current_index ?? state.current_item ?? data?.progress?.current_index) || 0);
  };

  const domItemIndex = () => {
    const steps = Array.from(document.querySelectorAll('.lesson-13-step, .step'));
    const active = steps.findIndex(step => step.classList.contains('active'));
    return active >= 0 ? active : null;
  };

  const isPartTwo = () => Boolean(
    document.querySelector('#matching, #answer, .choices')
      || Array.from(document.querySelectorAll('.eyebrow, .session-label')).some(node => /PART 2/i.test(node.textContent || ''))
  );

  const expectedFromActivityData = () => {
    const data = readJsonScript(expectedDataIds[prefix]);
    if (!data) return '';
    const index = domItemIndex() ?? currentIndex(data);
    if (prefix === 'prescribed-s5l13g1') return data.items?.[index]?.letter || '';
    if (prefix === 'prescribed-s5l13g2') return (data.columns || []).flat()?.[index] || '';
    if (prefix === 'prescribed-s5l13g3') return data.sentences?.[index] || '';
    if (prefix === 'prescribed-s5l14g1') return data.items?.[index]?.word || '';
    if (prefix === 'prescribed-s5l14g2') return !isPartTwo() ? data.items?.[index]?.word || '' : '';
    if (prefix === 'prescribed-s5l14g3') {
      const item = data.items?.[index];
      return !isPartTwo() ? item?.word || '' : item?.expected_input || '';
    }
    if (prefix === 'prescribed-s5l15g1') return data.items?.[index]?.word || '';
    if (prefix === 'prescribed-s5l15g2') return !isPartTwo() ? data.items?.[index]?.word || '' : '';
    return '';
  };

  const getExpectedText = () => {
    const visible = document.querySelector('.lesson-13-sentence, .lesson-13-word, .item-text');
    if (visible?.textContent.trim()) return visible.textContent.trim();
    const image = document.querySelector('.picture img[alt^="Larawan ng "]');
    if (image) return image.alt.replace(/^Larawan ng /, '').trim();
    return String(expectedFromActivityData() || '').trim();
  };

  const refreshExpectedText = () => {
    const field = q('-debug-expected');
    if (!field) return;
    const next = getExpectedText() || 'Not available';
    if (field.textContent !== next) field.textContent = next;
  };

  const scheduleExpectedTextRefresh = () => {
    refreshExpectedText();
    window.requestAnimationFrame?.(refreshExpectedText);
  };

  const wrapActivityMicrophone = () => {
    const devices = navigator.mediaDevices;
    if (!devices?.getUserMedia || devices.getUserMedia.__session5Wrapped) return;
    const original = devices.getUserMedia.bind(devices);
    const wrapped = async constraints => {
      const stream = await original(constraints);
      if (!requestingTest) activityStreams.add(stream);
      stream.getTracks().forEach(track => { track.enabled = !isMuted; });
      if (!requestingTest) debug({mic: `Active · ${isMuted ? 'Muted' : 'Unmuted'}`, status: isMuted ? 'Muted' : 'Ready'}, 'Activity microphone opened');
      return stream;
    };
    wrapped.__session5Wrapped = true;
    devices.getUserMedia = wrapped;
  };

  const stopActivityMedia = () => media().forEach(element => {
    try { element.pause(); } catch (_) { /* media may already be detached */ }
  });

  const stopActivityRecorders = () => {
    activityRecorders.forEach(recorder => {
      try { if (recorder.state === 'recording') recorder.stop(); } catch (_) { /* recorder may already be inactive */ }
    });
    activityRecorders.clear();
  };

  const wrapAsyncBoundaries = () => {
    const OriginalRecorder = window.MediaRecorder;
    if (OriginalRecorder && !OriginalRecorder.__session5Wrapped) {
      const wrappedRecorder = new Proxy(OriginalRecorder, {
        construct(target, args, newTarget) {
          const recorder = Reflect.construct(target, args, newTarget);
          activityRecorders.add(recorder);
          recorder.addEventListener?.('start', () => debug({status: isMuted ? 'Muted' : 'Listening', recorder: 'Recording'}, 'Recording started'));
          recorder.addEventListener?.('stop', () => debug({status: 'Processing', recorder: 'Inactive'}, 'Recording stopped'));
          recorder.addEventListener?.('stop', () => activityRecorders.delete(recorder), {once: true});
          return recorder;
        },
      });
      wrappedRecorder.__session5Wrapped = true;
      window.MediaRecorder = wrappedRecorder;
    }
    if (window.fetch && !window.fetch.__session5Wrapped) {
      const originalFetch = window.fetch.bind(window);
      const guardedFetch = (input, init) => {
        const captured = generation;
        return originalFetch(input, init).then(response => {
          if (captured !== generation) throw new Error('Session 5 activity operation is stale');
          if (String(input).includes('transcrib')) {
            response.clone().json().then(result => {
              debug({transcript: result.transcript || 'Not available', result: result.success ? 'Processed' : 'Not available'}, 'Transcription response received');
            }).catch(() => {});
          }
          scheduleExpectedTextRefresh();
          return response;
        });
      };
      guardedFetch.__session5Wrapped = true;
      window.fetch = guardedFetch;
    }
  };

  const updateMic = () => {
    const button = q('-mic-toggle');
    const icon = button?.querySelector('i');
    if (!button || !icon) return;
    icon.classList.toggle('bi-mic-fill', !isMuted);
    icon.classList.toggle('bi-mic-mute-fill', isMuted);
    button.classList.toggle('is-muted', isMuted);
    button.setAttribute('aria-pressed', String(isMuted));
    button.setAttribute('aria-label', isMuted ? 'I-unmute ang mikropono' : 'I-mute ang mikropono');
    button.title = isMuted ? 'I-unmute ang mikropono' : 'I-mute ang mikropono';
    const mic = q('-debug-mic');
      if (mic) mic.textContent = `${activityStreams.size ? 'Active' : 'Inactive'} · ${isMuted ? 'Muted' : 'Unmuted'}`;
  };

  const stopTest = () => {
    if (testFrame) cancelAnimationFrame(testFrame);
    testFrame = 0;
    testStream?.getTracks().forEach(track => track.stop());
    testStream = null;
    try { testContext?.close(); } catch (_) { /* context may already be closed */ }
    testContext = null;
    testAnalyser = null;
    const fill = q('-level-fill');
    if (fill) fill.style.width = '0%';
    const status = q('-settings-status');
    if (status) status.innerHTML = '<strong>Microphone Status:</strong> Not tested';
    const button = q('-test-toggle');
    if (button) { button.innerHTML = '<i class="bi bi-mic-fill" aria-hidden="true"></i> Start Test'; button.dataset.testing = 'false'; }
  };

  const renderLevel = () => {
    if (!testAnalyser) return;
    const values = new Uint8Array(testAnalyser.fftSize);
    testAnalyser.getByteTimeDomainData(values);
    let peak = 0;
    values.forEach(value => { peak = Math.max(peak, Math.abs(value - 128)); });
    const level = Math.min(100, Math.round(peak * 100 / 128));
    const fill = q('-level-fill');
    if (fill) fill.style.width = `${level}%`;
    testFrame = requestAnimationFrame(renderLevel);
  };

  const bindAudioTest = () => {
    const button = q('-test-toggle');
    const select = q('-device-select');
    const status = q('-settings-status');
    if (!button || button.dataset.bound) return;
    button.dataset.bound = 'true';
    const populate = async () => {
      if (!navigator.mediaDevices?.enumerateDevices || !select) return;
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const current = select.value;
        select.replaceChildren(new Option('Default microphone', ''));
        devices.filter(device => device.kind === 'audioinput').forEach(device => select.add(new Option(device.label || `Microphone ${select.length}`, device.deviceId)));
        select.value = current;
      } catch (_) { /* device enumeration is optional */ }
    };
    button.addEventListener('click', async () => {
      if (testStream) { stopTest(); return; }
      try {
        const audio = select?.value ? {deviceId: {exact: select.value}} : true;
        requestingTest = true;
        testStream = await navigator.mediaDevices.getUserMedia({audio});
        requestingTest = false;
        testContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = testContext.createMediaStreamSource(testStream);
        testAnalyser = testContext.createAnalyser();
        testAnalyser.fftSize = 256;
        source.connect(testAnalyser);
        if (status) status.innerHTML = '<strong>Microphone Status:</strong> Ready';
        button.dataset.testing = 'true';
        button.innerHTML = '<i class="bi bi-stop-fill" aria-hidden="true"></i> Stop Test';
        renderLevel();
        await populate();
      } catch (error) {
        requestingTest = false;
        stopTest();
        if (status) status.innerHTML = `<strong>Microphone Status:</strong> ${error?.message || 'Microphone unavailable'}`;
      }
    });
    select?.addEventListener('change', () => { if (testStream) { stopTest(); button.click(); } });
    populate();
  };

  const bindDebug = () => {
    const toggle = q('-debug-toggle');
    const panel = q('-debug-panel');
    if (!toggle || !panel || toggle.dataset.bound) return;
    toggle.dataset.bound = 'true';
    const key = 'pabasaShowSpeechDebugPanel';
    let saved = false;
    try { saved = localStorage.getItem(key) === 'true'; } catch (_) { /* storage is optional */ }
    toggle.checked = saved;
    const render = () => { panel.hidden = !toggle.checked; panel.setAttribute('aria-hidden', String(!toggle.checked)); scheduleExpectedTextRefresh(); };
    toggle.addEventListener('change', () => { try { localStorage.setItem(key, String(toggle.checked)); } catch (_) {} render(); });
    render();
  };

  const resetActivity = async () => {
    stopTest();
    stopActivityMedia();
    if (typeof window.__session5ActivityHooks?.restart === 'function') return window.__session5ActivityHooks.restart();
    const dataScript = Array.from(document.scripts).find(script => script.type === 'application/json' && script.textContent.includes('progress_url'));
    try {
      const data = dataScript ? JSON.parse(dataScript.textContent) : null;
      if (data?.progress_url) {
        const csrf = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
        await fetch(data.progress_url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: JSON.stringify({reset: true})});
      }
    } catch (_) { /* reload remains the safe fallback */ }
    window.location.reload();
  };

  const adapter = {
    pause() { paused = true; generation += 1; stopActivityRecorders(); activityStreams.forEach(stream => stream.getTracks().forEach(track => track.stop())); activityStreams.clear(); stopActivityMedia(); window.dispatchEvent(new CustomEvent('session5-prescribed-paused', {detail: {prefix}})); },
    resume() { paused = false; window.dispatchEvent(new CustomEvent('session5-prescribed-resumed', {detail: {prefix}})); },
    restart: async () => { generation += 1; stopActivityRecorders(); return resetActivity(); },
    cleanup() { generation += 1; stopTest(); stopActivityRecorders(); activityStreams.forEach(stream => stream.getTracks().forEach(track => track.stop())); activityStreams.clear(); stopActivityMedia(); window.dispatchEvent(new CustomEvent('session5-prescribed-cleanup', {detail: {prefix}})); },
    setMuted(value) {
      isMuted = Boolean(value);
      activityStreams.forEach(stream => stream.getTracks().forEach(track => { track.enabled = !isMuted; }));
      updateMic();
    },
    bindAudioTest,
    bindDebug,
  };

  wrapActivityMicrophone();
  wrapAsyncBoundaries();
  updateMic();
  window.PrescribedControls.init({prefix, adapter});
  window.__session5ControlsInitialized[prefix] = true;
  scheduleExpectedTextRefresh();
  window.addEventListener('pagehide', () => { stopTest(); stopActivityMedia(); }, {once: true});
})();
