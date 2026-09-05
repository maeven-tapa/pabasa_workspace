(() => {
  'use strict';
  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance) return;

  const browserSpeak = speech.speak.bind(speech);
  const browserCancel = speech.cancel.bind(speech);
  let activeAudio = null;
  const csrfToken = () => document.cookie.split('; ').find((value) => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';

  speech.cancel = () => {
    activeAudio?.pause();
    activeAudio = null;
    browserCancel();
  };
  speech.speak = async (utterance) => {
    const text = String(utterance?.text || '').trim();
    if (!text) return;
    speech.cancel();
    const formData = new FormData();
    formData.append('target_text', text);
    formData.append('language', utterance.lang || 'English');
    formData.append('mode', 'letter');
    formData.append('tts_profile', 'correspondence');
    try {
      const response = await fetch('/api/reading/read-aloud/', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }, body: formData });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Google TTS failed.');
      activeAudio = new Audio(`data:${data.mime_type || 'audio/mpeg'};base64,${data.audio_content}`);
      activeAudio.addEventListener('ended', () => { activeAudio = null; }, { once: true });
      await activeAudio.play();
    } catch (error) {
      console.warn('Google Correspondence TTS unavailable; using the browser voice.', error);
      browserSpeak(utterance);
    }
  };
})();
