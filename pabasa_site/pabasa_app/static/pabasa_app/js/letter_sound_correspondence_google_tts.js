(() => {
  'use strict';
  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance) return;

  const browserSpeak = speech.speak.bind(speech);
  const browserCancel = speech.cancel.bind(speech);
  let activeAudio = null;
  const csrfToken = () => document.cookie.split('; ').find((value) => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const isFilipino = () => String(document.body?.dataset.letterCorrespondenceLanguage || '').toLowerCase().startsWith('fil');
  const filipinoText = {
    'Tap a handle to hear its balloon, then pop the balloon that matches the letter.': 'Pindutin ang hawakan upang marinig ang tunog ng lobo, saka piliin ang lobong tumutugma sa letra.',
    'Wonderful! That balloon matches the letter.': 'Magaling! Tumutugma ang lobong iyon sa letra.',
    'Nice try! The next round is ready.': 'Magandang pagsubok! Handa na ang susunod na round.',
    'Unable to play that balloon sound. Please try again.': 'Hindi ma-play ang tunog ng lobong iyon. Pakisubukan muli.',
    'Your score could not be saved. Please try again.': 'Hindi nai-save ang iyong puntos. Pakisubukan muli.',
    'This activity has no available reading sets.': 'Walang available na set ng babasahin para sa aktibidad na ito.',
  };

  const translateFeedback = () => {
    if (!isFilipino()) return;
    const feedback = document.getElementById('feedback');
    const translated = filipinoText[feedback?.textContent.trim()];
    if (translated) feedback.textContent = translated;
  };

  const localizePage = () => {
    if (!isFilipino()) return;
    const instruction = document.querySelector('.instruction');
    if (instruction) instruction.textContent = filipinoText['Tap a handle to hear its balloon, then pop the balloon that matches the letter.'];
    new MutationObserver(translateFeedback).observe(document.getElementById('feedback'), { childList: true, characterData: true, subtree: true });
    translateFeedback();
  };

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
    formData.append('target_text', isFilipino() ? (filipinoText[text] || text) : text);
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
  document.addEventListener('DOMContentLoaded', localizePage, { once: true });
})();
