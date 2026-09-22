(() => {
  'use strict';

  const helpButton = document.getElementById('prescribed-l26a1-help-btn');
  const helpModal = document.getElementById('prescribed-l26a1-help-modal');
  const helpClose = document.getElementById('prescribed-l26a1-help-close');
  const micToggle = document.getElementById('prescribed-l26a1-mic-toggle');
  const audioButton = document.getElementById('prescribed-l26a1-audio-settings-btn');
  const audioModal = document.getElementById('prescribed-l26a1-audio-settings-modal');
  const audioClose = document.getElementById('prescribed-l26a1-audio-close');
  const deviceSelect = document.getElementById('prescribed-l26a1-device-select');
  const debugToggle = document.getElementById('prescribed-l26a1-debug-toggle');
  const status = document.getElementById('prescribed-l26a1-settings-status');
  const recordButton = document.getElementById('prescribed-l26a1-sample-record');
  const playButton = document.getElementById('prescribed-l26a1-sample-play');
  if (!helpButton || !helpModal || !helpClose || !micToggle || !audioButton || !audioModal) return;

  let sampleBlob = null;
  let sampleStream = null;
  let sampleAudio = null;
  let recording = false;

  const setHidden = (modal, hidden) => { modal.hidden = hidden; };
  const closeAll = () => { setHidden(helpModal, true); setHidden(audioModal, true); };
  const showHelp = () => { setHidden(audioModal, true); setHidden(helpModal, false); helpClose.focus(); };
  const showAudio = async () => {
    setHidden(helpModal, true); setHidden(audioModal, false); audioButton.focus();
    await refreshDevices();
  };

  async function refreshDevices() {
    if (!navigator.mediaDevices?.enumerateDevices || !deviceSelect) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const microphones = devices.filter(device => device.kind === 'audioinput');
      deviceSelect.replaceChildren(new Option('Default microphone', ''));
      microphones.forEach(device => deviceSelect.add(new Option(device.label || `Microphone ${deviceSelect.options.length}`, device.deviceId)));
    } catch (_) { /* Device labels are optional until permission is granted. */ }
  }

  function stopSampleStream() {
    sampleStream?.getTracks().forEach(track => track.stop());
    sampleStream = null;
  }

  async function recordSample() {
    if (recording) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      status.textContent = 'Microphone recording is not available in this browser.';
      return;
    }
    recording = true; recordButton.disabled = true; playButton.disabled = true;
    status.textContent = 'Recording sample…';
    const chunks = [];
    try {
      const constraints = deviceSelect.value ? {audio: {deviceId: {exact: deviceSelect.value}}} : {audio: true};
      sampleStream = await navigator.mediaDevices.getUserMedia(constraints);
      const recorder = new MediaRecorder(sampleStream);
      const finished = new Promise(resolve => { recorder.addEventListener('stop', resolve, {once: true}); });
      recorder.addEventListener('dataavailable', event => { if (event.data.size) chunks.push(event.data); });
      recorder.start();
      window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 3000);
      await finished;
      sampleBlob = new Blob(chunks, {type: recorder.mimeType || 'audio/webm'});
      playButton.disabled = !sampleBlob.size;
      status.textContent = 'Sample recorded. Play it back to check your microphone.';
    } catch (_) {
      status.textContent = 'Microphone permission was not granted or recording failed.';
    } finally {
      stopSampleStream(); recording = false; recordButton.disabled = false;
    }
  }

  function playSample() {
    if (!sampleBlob) return;
    sampleAudio?.pause();
    sampleAudio = new Audio(URL.createObjectURL(sampleBlob));
    sampleAudio.addEventListener('ended', () => { status.textContent = 'Ready for a sample recording.'; }, {once: true});
    status.textContent = 'Playing sample…'; sampleAudio.play().catch(() => { status.textContent = 'Sample playback could not start.'; });
  }

  helpButton.addEventListener('click', showHelp);
  helpClose.addEventListener('click', () => setHidden(helpModal, true));
  audioButton.addEventListener('click', showAudio);
  audioClose.addEventListener('click', () => setHidden(audioModal, true));
  helpModal.addEventListener('click', event => { if (event.target === helpModal) setHidden(helpModal, true); });
  audioModal.addEventListener('click', event => { if (event.target === audioModal) setHidden(audioModal, true); });
  micToggle.addEventListener('click', () => {
    const muted = micToggle.getAttribute('aria-pressed') === 'true';
    micToggle.setAttribute('aria-pressed', String(!muted));
    micToggle.setAttribute('aria-label', muted ? 'Mute microphone' : 'Unmute microphone');
    micToggle.classList.toggle('is-muted', !muted);
    window.dispatchEvent(new CustomEvent('prescribed-l26a1-mic-state', {detail: {muted: !muted}}));
  });
  deviceSelect?.addEventListener('change', () => window.dispatchEvent(new CustomEvent('prescribed-l26a1-device-state', {detail: {deviceId: deviceSelect.value}})));
  debugToggle?.addEventListener('change', () => { status.textContent = debugToggle.checked ? 'Speech debug panel enabled for this activity.' : 'Speech debug panel disabled for this activity.'; });
  recordButton?.addEventListener('click', recordSample);
  playButton?.addEventListener('click', playSample);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeAll(); });
  window.addEventListener('beforeunload', () => { stopSampleStream(); sampleAudio?.pause(); });
})();
