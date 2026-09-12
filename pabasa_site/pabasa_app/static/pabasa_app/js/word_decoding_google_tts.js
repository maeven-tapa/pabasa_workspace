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
    'Checking your word with Google Speech…': 'Sinusuri ang iyong salita.',
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
    const status = document.getElementById('status');
    if (!status) return;
    const currentStatus = status.textContent.trim();
    if (currentStatus === 'Checking your word with Google Speech…') {
      status.textContent = isFilipinoMaterial()
        ? 'Sinusuri ang iyong salita.'
        : 'Checking your word…';
      return;
    }
    if (!isFilipinoMaterial()) return;
    const translated = filipinoStatusMessages[currentStatus];
    if (translated) status.textContent = translated;
  };

  const readingFeedbackCopy = () => isFilipinoMaterial()
    ? { heard: 'Narinig:', listen: 'Pakinggan ang Salita' }
    : { heard: 'Heard:', listen: 'Hear the Word' };

  const localizeCompletionCard = () => {
    const card = document.querySelector('#complete .complete-card');
    if (!card || !isFilipinoMaterial()) return;
    const title = card.querySelector('h1');
    const message = card.querySelector('p');
    const finish = card.querySelector('#finish');
    if (title) title.textContent = 'Tapos na ang Pag-decode!';
    if (message) message.textContent = 'Natapos mo ang set ng salita.';
    if (finish) finish.textContent = 'Bumalik sa mga Pagtatasa';
  };

  const getReadingFeedback = () => document.getElementById('word-decoding-reading-feedback');

  const clearReadingFeedback = () => {
    const feedback = getReadingFeedback();
    if (feedback) feedback.hidden = true;
  };

  const playWholeWord = async () => {
    const wholeWord = [...document.querySelectorAll('#word .letter')]
      .map((letter) => letter.textContent.trim())
      .join('');
    if (!wholeWord) return;
    await window.PabasaTemplateTts.speak({
      materialId: document.body?.dataset.templateMaterialId,
      text: wholeWord,
      profile: 'instruction',
    });
  };

  const showReadingFeedback = (transcript) => {
    const capturedWord = String(transcript || '').trim();
    if (!capturedWord) return;
    const feedback = getReadingFeedback();
    if (!feedback) return;
    const copy = readingFeedbackCopy();
    feedback.querySelector('[data-reading-heard-label]').textContent = copy.heard;
    feedback.querySelector('[data-reading-transcript]').textContent = `“${capturedWord}”`;
    feedback.querySelector('[data-read-whole-word]').innerHTML = `<i class="bi bi-volume-up-fill" aria-hidden="true"></i> ${copy.listen}`;
    feedback.hidden = false;
  };

  const installReadingFeedback = () => {
    const status = document.getElementById('status');
    if (!status || getReadingFeedback()) return;
    const feedback = document.createElement('section');
    feedback.id = 'word-decoding-reading-feedback';
    feedback.className = 'word-decoding-reading-feedback';
    feedback.hidden = true;
    feedback.innerHTML = '<p class="reading-feedback-label" data-reading-heard-label></p><p class="reading-feedback-transcript" data-reading-transcript></p><button class="word-read reading-feedback-listen" type="button" data-read-whole-word></button>';
    feedback.querySelector('[data-read-whole-word]').addEventListener('click', playWholeWord);
    status.insertAdjacentElement('afterend', feedback);

    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await nativeFetch(...args);
      const request = args[0];
      const url = typeof request === 'string' ? request : request?.url;
      if (String(url || '').includes('/word-decoding/transcribe/')) {
        response.clone().json().then((payload) => {
          if (payload?.success) showReadingFeedback(payload.transcript);
        }).catch(() => {});
      }
      return response;
    };
  };

  const installWordDecodingEnhancements = () => {
    const style = document.createElement('style');
    style.textContent = '.word > span.current-letter{color:#f36e83;text-shadow:0 3px #fff,0 0 0.18em #f36e83;transform:scale(1.16);transition:color .18s ease,transform .18s ease}.word-read.show+.status{margin-top:22px}.word-decoding-reading-feedback{margin:14px auto 0;max-width:31rem;color:#12395a;text-align:center}.word-decoding-reading-feedback[hidden]{display:none}.reading-feedback-label{margin:0 0 3px;font-size:.9rem;font-weight:900;letter-spacing:.04em}.reading-feedback-transcript{margin:0 0 10px;font-size:1.05rem;font-weight:1000}.word-read.reading-feedback-listen{display:inline-block;padding:10px 16px;font-size:.9rem}';
    document.head.appendChild(style);

    const board = document.querySelector('.board');
    if (!board) return;
    new MutationObserver(() => {
      updateCurrentLetter();
      translateStatus();
      if (!document.getElementById('wordRead')?.classList.contains('show')) clearReadingFeedback();
    }).observe(board, { childList: true, subtree: true, characterData: true });
    installReadingFeedback();
    updateCurrentLetter();
    translateStatus();
    localizeCompletionCard();
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
