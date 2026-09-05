(() => {
  'use strict';

  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance) return;

  const browserSpeak = speech.speak.bind(speech);
  const browserCancel = speech.cancel.bind(speech);
  let activeAudio = null;

  const filipinoStatusMessages = {
    'Correct! Next letter…': 'Tama! Susunod na letra…',
    'Try one of the remaining bubbles.': 'Subukan ang isa sa mga natitirang bula.',
    'Two tries used. The next word is ready.': 'Nagamit na ang dalawang pagkakataon. Handa na ang susunod na salita.',
    'Unable to play that sound. Please try again.': 'Hindi ma-play ang tunog na iyon. Pakisubukan muli.',
    'Speech recording is not available in this browser.': 'Hindi available ang pag-record ng boses sa browser na ito.',
    'Your recording could not be captured.': 'Hindi na-record ang iyong boses. Pakisubukan muli.',
    'No speech was captured. Please try again.': 'Walang boses na na-record. Pakisubukan muli.',
    'Listening with Google Speech… Read the whole word.': 'Nakikinig ang Google Speech… Basahin ang buong salita.',
    'Checking your word with Google Speech…': 'Sinusuri ng Google Speech ang iyong salita…',
    'Great reading! Next word…': 'Magaling magbasa! Susunod na salita…',
    'Try reading the whole word again.': 'Subukang basahin muli ang buong salita.',
    'Google Speech could not check your word.': 'Hindi masuri ng Google Speech ang iyong salita.',
    'Google Speech could not hear that. Please try again.': 'Hindi narinig ng Google Speech ang iyong boses. Pakisubukan muli.',
    'Your result could not be saved. Please try again.': 'Hindi nai-save ang iyong resulta. Pakisubukan muli.',
  };

  const isFilipinoMaterial = () => String(document.body?.dataset.wordDecodingLanguage || '')
    .toLowerCase()
    .startsWith('fil');

  const updateCurrentLetter = () => {
    const letters = document.querySelectorAll('#word > span:not(.plus)');
    const checks = document.querySelectorAll('#checks .check');
    const currentIndex = [...checks].findIndex((check) => !check.classList.contains('correct')
      && !check.classList.contains('wrong'));
    letters.forEach((letter, index) => letter.classList.toggle('current-letter', index === currentIndex));
  };

  const translateStatus = () => {
    if (!isFilipinoMaterial()) return;
    const status = document.getElementById('status');
    if (!status) return;
    const translated = filipinoStatusMessages[status.textContent.trim()];
    if (translated) status.textContent = translated;
  };

  const installWordDecodingEnhancements = () => {
    const style = document.createElement('style');
    style.textContent = '.word > span.current-letter{color:#f36e83;text-shadow:0 3px #fff,0 0 0.18em #f36e83;transform:scale(1.16);transition:color .18s ease,transform .18s ease}';
    document.head.appendChild(style);

    const board = document.querySelector('.board');
    if (!board) return;
    new MutationObserver(() => {
      updateCurrentLetter();
      translateStatus();
    }).observe(board, { childList: true, subtree: true, characterData: true });
    updateCurrentLetter();
    translateStatus();
  };

  const csrfToken = () => document.cookie
    .split('; ')
    .find((value) => value.startsWith('csrftoken='))
    ?.split('=')
    .slice(1)
    .join('=') || '';

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
    formData.append('mode', 'word');

    try {
      const response = await fetch('/api/reading/read-aloud/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Google TTS failed.');

      activeAudio = new Audio(`data:${data.mime_type || 'audio/mpeg'};base64,${data.audio_content}`);
      activeAudio.addEventListener('ended', () => { activeAudio = null; }, { once: true });
      await activeAudio.play();
    } catch (error) {
      console.warn('Google Word Decoding TTS unavailable; using the browser voice.', error);
      browserSpeak(utterance);
    }
  };

  document.addEventListener('DOMContentLoaded', installWordDecodingEnhancements, { once: true });
})();
