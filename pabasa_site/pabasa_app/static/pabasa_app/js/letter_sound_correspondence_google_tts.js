(() => {
  'use strict';
  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance || !window.PabasaTemplateTts) return;
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
    window.PabasaTemplateTts.stop();
  };
  speech.speak = async (utterance) => {
    const text = String(utterance?.text || '').trim();
    if (!text) return;
    await window.PabasaTemplateTts.speak({
      materialId: document.body?.dataset.templateMaterialId,
      text: isFilipino() ? (filipinoText[text] || text) : text,
      profile: 'instruction',
    });
  };
  document.addEventListener('DOMContentLoaded', localizePage, { once: true });
})();
