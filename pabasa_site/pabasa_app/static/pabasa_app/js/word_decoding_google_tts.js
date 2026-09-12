(() => {
  'use strict';

  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance || !window.PabasaTemplateTts) return;

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

  const naturalInstruction = (text) => {
    if (text === 'Listen to each bubble. Choose the sound for.') {
      return isFilipinoMaterial()
        ? 'Makinig sa bawat bula. Piliin ang tamang tunog.'
        : 'Listen to each bubble. Choose the matching sound.';
    }
    return text;
  };

  const updateCurrentLetter = () => {
    const letters = document.querySelectorAll('#word > span:not(.plus)');
    const checks = document.querySelectorAll('#checks .check');
    // A wrong check is still the active letter until the student gets the
    // second attempt right or the round advances after two wrong attempts.
    const currentIndex = [...checks].findIndex((check) => !check.classList.contains('correct'));
    letters.forEach((letter) => {
      letter.classList.remove('current-letter', 'active');
      letter.style.color = '';
    });
    if (letters[currentIndex]) {
      letters[currentIndex].classList.add('current-letter');
      letters[currentIndex].style.color = '#f36e83';
    }
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

  speech.cancel = () => {
    window.PabasaTemplateTts.stop();
  };

  speech.speak = async (utterance) => {
    const text = String(utterance?.text || '').trim();
    if (!text) return;

    await window.PabasaTemplateTts.speak({
      materialId: document.body?.dataset.templateMaterialId,
      text: naturalInstruction(text),
      profile: 'instruction',
    });
  };

  document.addEventListener('DOMContentLoaded', installWordDecodingEnhancements, { once: true });
})();
