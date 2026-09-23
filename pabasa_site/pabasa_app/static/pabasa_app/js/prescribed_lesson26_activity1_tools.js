(() => {
  'use strict';

  const helpButton = document.getElementById('prescribed-l26a1-help-btn');
  const helpModal = document.getElementById('prescribed-l26a1-help-modal');
  const helpClose = document.getElementById('prescribed-l26a1-help-close');
  const micToggle = document.getElementById('prescribed-l26a1-mic-toggle');
  const audioButton = document.getElementById('prescribed-l26a1-audio-settings-btn');
  const audioModal = document.getElementById('prescribed-l26a1-audio-settings-modal');
  const audioClose = document.getElementById('prescribed-l26a1-audio-close');
  const pauseModal = document.getElementById('prescribed-l26a1-pause-modal');
  const restartModal = document.getElementById('prescribed-l26a1-restart-modal');
  const resumeButton = document.getElementById('prescribed-l26a1-resume');
  const restartButton = document.getElementById('prescribed-l26a1-restart');
  const restartYes = document.getElementById('prescribed-l26a1-restart-yes');
  const restartNo = document.getElementById('prescribed-l26a1-restart-no');
  const backButton = document.getElementById('prescribed-l26a1-back');
  const audioTestButton = document.getElementById('prescribed-l26a1-audio-test');
  const deviceSelect = document.getElementById('prescribed-l26a1-device-select');
  const debugToggle = document.getElementById('prescribed-l26a1-debug-toggle');
  const debugPanel = document.getElementById('prescribed-l26a1-debug-panel');
  const debugFields = Object.fromEntries(['status','transcript','expected','normalized','result','mic','recorder','vad','error','raw'].map(key => [key, document.getElementById(`prescribed-l26a1-debug-${key}`)]));
  const status = document.getElementById('prescribed-l26a1-settings-status');
  const testToggle = document.getElementById('prescribed-l26a1-test-toggle');
  const permissionButton = document.getElementById('prescribed-l26a1-permission');
  const levelFill = document.getElementById('prescribed-l26a1-level-fill');
  const levelTrack = levelFill?.parentElement;
  if (!helpButton || !helpModal || !helpClose || !micToggle || !audioButton || !audioModal) return;

  let sampleStream = null;
  let testAudioContext = null;
  let testAnalyser = null;
  let testSource = null;
  let meterFrame = null;
  let testActive = false;

  let isMuted = false;
  function updateMicToggle() {
    micToggle.setAttribute('aria-pressed', String(isMuted));
    micToggle.setAttribute('aria-label', isMuted ? 'Unmute microphone' : 'Mute microphone');
    micToggle.title = isMuted ? 'Unmute microphone' : 'Mute microphone';
    micToggle.classList.toggle('is-muted', isMuted);
    micToggle.innerHTML = `<i class="bi ${isMuted ? 'bi-mic-mute-fill' : 'bi-mic-fill'}" aria-hidden="true"></i>`;
  }
  updateMicToggle();

  const setHidden = (modal, hidden) => { modal.hidden = hidden; };
  function setDebugVisible(visible, persist = true) {
    const enabled = Boolean(visible);
    debugPanel?.toggleAttribute('hidden', !enabled);
    debugPanel?.setAttribute('aria-hidden', String(!enabled));
    if (debugToggle) debugToggle.checked = enabled;
    if (persist) localStorage.setItem('pabasaShowSpeechDebugPanel', enabled ? 'true' : 'false');
  }
  function renderDebugState(state = {}) { Object.entries(debugFields).forEach(([key, field]) => { if (field && state[key] !== undefined) field.textContent = state[key] || (key === 'error' ? '—' : ''); }); }
  window.addEventListener('prescribed-l26a1-debug-state', event => renderDebugState(event.detail || {}));
  setDebugVisible(localStorage.getItem('pabasaShowSpeechDebugPanel') === 'true', false);
  renderDebugState(window.PrescribedLesson26Debug?.getState?.());
  const closeAll = () => { setHidden(helpModal, true); setHidden(audioModal, true); };
  const showHelp = () => { setHidden(audioModal, true); setHidden(helpModal, false); helpClose.focus(); };
  const showAudio = async () => {
    setHidden(pauseModal, true); setHidden(helpModal, true); setHidden(audioModal, false); audioTestButton?.focus();
    await refreshDevices();
    await updatePermissionStatus();
  };
  const showPause = () => { setHidden(audioModal, true); setHidden(restartModal, true); setHidden(pauseModal, false); audioButton.focus(); };
  const showRestartConfirmation = () => { setHidden(pauseModal, true); setHidden(restartModal, false); restartNo.focus(); };

  async function refreshDevices() {
    if (!navigator.mediaDevices?.enumerateDevices || !deviceSelect) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const microphones = devices.filter(device => device.kind === 'audioinput');
      deviceSelect.replaceChildren(new Option('Default microphone', ''));
      microphones.forEach(device => deviceSelect.add(new Option(device.label || `Microphone ${deviceSelect.options.length}`, device.deviceId)));
    } catch (_) { /* Device labels are optional until permission is granted. */ }
  }

  function resetLevel() {
    if (levelFill) levelFill.style.width = '0%';
    levelTrack?.setAttribute('aria-valuenow', '0');
  }

  function stopSampleStream() {
    if (meterFrame) cancelAnimationFrame(meterFrame);
    meterFrame = null;
    testSource?.disconnect(); testSource = null;
    testAnalyser = null;
    testAudioContext?.close().catch(() => {}); testAudioContext = null;
    sampleStream?.getTracks().forEach(track => track.stop());
    sampleStream = null;
    testActive = false;
    resetLevel();
    if (testToggle) testToggle.innerHTML = '<i class="bi bi-mic-fill" aria-hidden="true"></i> Start Test';
  }

  function setStatus(message) {
    if (status) status.innerHTML = `<strong>Microphone Status:</strong> ${message}`;
  }

  async function updatePermissionStatus() {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('Unavailable in this browser.'); permissionButton.hidden = true; return; }
    try {
      const permission = await navigator.permissions?.query?.({name: 'microphone'});
      const state = permission?.state;
      setStatus(state === 'granted' ? 'Access granted.' : state === 'denied' ? 'Access denied.' : 'Permission not granted.');
      permissionButton.hidden = state === 'granted';
    } catch (_) { setStatus('Permission status unavailable.'); permissionButton.hidden = false; }
  }

  function updateMeter() {
    if (!testAnalyser || !testActive) return;
    const values = new Uint8Array(testAnalyser.fftSize);
    testAnalyser.getByteTimeDomainData(values);
    let sum = 0; for (const value of values) { const sample = (value - 128) / 128; sum += sample * sample; }
    const level = Math.min(100, Math.round(Math.sqrt(sum / values.length) * 260));
    if (levelFill) levelFill.style.width = `${level}%`;
    levelTrack?.setAttribute('aria-valuenow', String(level));
    meterFrame = requestAnimationFrame(updateMeter);
  }

  async function startTest() {
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
      setStatus('Unavailable in this browser.');
      return;
    }
    try {
      const constraints = deviceSelect.value ? {audio: {deviceId: {exact: deviceSelect.value}}} : {audio: true};
      sampleStream = await navigator.mediaDevices.getUserMedia(constraints);
      testAudioContext = new AudioContext(); testAnalyser = testAudioContext.createAnalyser(); testAnalyser.fftSize = 512;
      testSource = testAudioContext.createMediaStreamSource(sampleStream); testSource.connect(testAnalyser);
      testActive = true; setStatus('Access granted. Testing live input.'); permissionButton.hidden = true;
      testToggle.innerHTML = '<i class="bi bi-stop-fill" aria-hidden="true"></i> Stop Test'; updateMeter();
    } catch (_) { stopSampleStream(); setStatus('Access denied or microphone unavailable.'); permissionButton.hidden = false; }
  }

  async function toggleTest() {
    if (testActive) stopSampleStream(); else await startTest();
    if (!testActive && !sampleStream) await updatePermissionStatus();
  }

  async function requestPermission() {
    if (testActive) return;
    await startTest();
    if (testActive) stopSampleStream();
    await updatePermissionStatus();
  }

  async function switchDevice() {
    if (!testActive) return;
    stopSampleStream();
    await startTest();
  }

  helpButton.addEventListener('click', showHelp);
  helpClose.addEventListener('click', () => setHidden(helpModal, true));
  audioButton.addEventListener('click', () => { window.PrescribedLesson26Activity?.pause(); setHidden(pauseModal, false); });
  audioClose.addEventListener('click', () => { stopSampleStream(); showPause(); });
  helpModal.addEventListener('click', event => { if (event.target === helpModal) setHidden(helpModal, true); });
  audioModal.addEventListener('click', event => { if (event.target === audioModal) { stopSampleStream(); showPause(); } });
  micToggle.addEventListener('click', () => {
    isMuted = !isMuted;
    updateMicToggle();
    window.dispatchEvent(new CustomEvent('prescribed-l26a1-mic-state', {detail: {muted: isMuted}}));
  });
  deviceSelect?.addEventListener('change', () => { window.dispatchEvent(new CustomEvent('prescribed-l26a1-device-state', {detail: {deviceId: deviceSelect.value}})); switchDevice(); });
  debugToggle?.addEventListener('change', () => setDebugVisible(debugToggle.checked));
  window.addEventListener('prescribed-l26a1-debug-reset', () => renderDebugState(window.PrescribedLesson26Debug?.getState?.() || {}));
  testToggle?.addEventListener('click', toggleTest);
  permissionButton?.addEventListener('click', requestPermission);
  resumeButton?.addEventListener('click', () => { setHidden(pauseModal, true); window.PrescribedLesson26Activity?.resume(); });
  restartButton?.addEventListener('click', showRestartConfirmation);
  restartNo?.addEventListener('click', showPause);
  restartYes?.addEventListener('click', async () => { restartYes.disabled = true; window.PrescribedLesson26Debug?.reset?.(); try { await window.PrescribedLesson26Activity?.restart(); } catch (error) { restartYes.disabled = false; window.alert(error.message); } });
  backButton?.addEventListener('click', () => { window.PrescribedLesson26Activity?.cleanup(); window.location.href = '/dashboard/assessment/'; });
  audioTestButton?.addEventListener('click', showAudio);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { if (!audioModal.hidden) { stopSampleStream(); showPause(); } else if (!restartModal.hidden) { showPause(); } else if (!pauseModal.hidden) { return; } else { closeAll(); } } });
  window.addEventListener('beforeunload', () => { stopSampleStream(); });
})();
