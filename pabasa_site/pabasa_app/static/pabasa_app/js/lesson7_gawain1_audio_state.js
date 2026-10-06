(() => {
  'use strict';
  let activeAudio = null;
  const release = audio => {
    if (activeAudio !== audio) return;
    activeAudio = null;
    const read = document.getElementById('read');
    if (read?.isConnected) { read.disabled = false; read.removeAttribute('aria-busy'); }
  };
  const bind = () => {
    const listen = document.getElementById('aloud');
    if (!listen || listen.__lesson7PlaybackBound) return;
    listen.__lesson7PlaybackBound = true;
    listen.addEventListener('click', event => {
      if (activeAudio) return;
      event.stopImmediatePropagation();
      const read = document.getElementById('read');
      const word = (document.querySelector('.item.active img')?.alt || '').toLocaleLowerCase();
      const file = word === 'ilang ilang' ? 'ilang-ilang.mp3' : `${word}.mp3`;
      const audio = new Audio(`/static/pabasa_app/prescribed/audio/SESSION%203/LESSON%207/GAWAIN%201/${encodeURIComponent(file)}`);
      audio.__lesson7Word = word;
      activeAudio = audio;
      if (read) { read.disabled = true; read.setAttribute('aria-busy', 'true'); }
      audio.onended = () => release(audio);
      audio.onerror = () => release(audio);
      audio.play().catch(() => release(audio));
    }, {capture: true});
  };
  new MutationObserver(() => {
    bind();
    if (activeAudio) {
      const currentWord = (document.querySelector('.item.active img')?.alt || '').toLocaleLowerCase();
      if (currentWord !== activeAudio.__lesson7Word) { activeAudio.pause(); release(activeAudio); }
    }
  }).observe(document.body, {childList: true, subtree: true});
  bind();
  window.addEventListener('pagehide', () => { if (activeAudio) { activeAudio.pause(); release(activeAudio); } });
})();
