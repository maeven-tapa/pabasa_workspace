(function () {
  'use strict';

  const punctuationOnly = value => String(value || '')
    .trim()
    .replace(/[.!?]+\s*$/u, '')
    .replace(/\s+/gu, ' ');

  let activeAudio = null;

  window.playPrescribedReadAloud = function playPrescribedReadAloud(text, fallback, mappings) {
    const key = punctuationOnly(text);
    const source = Object.entries(mappings || {})
      .find(([mappedText]) => punctuationOnly(mappedText) === key)?.[1];
    if (!source) return fallback(text);

    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }
    const audio = new Audio();
    audio.preload = 'auto';
    audio.src = source;
    activeAudio = audio;
    return new Promise(resolve => {
      const finish = () => {
        if (activeAudio === audio) activeAudio = null;
        resolve();
      };
      audio.onended = finish;
      audio.onerror = finish;
      audio.load();
      audio.play().catch(finish);
    });
  };
}());
