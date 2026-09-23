(function () {
  'use strict';

  function runScripts(scripts) {
    return scripts.reduce((chain, source) => chain.then(() => new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const src = source.getAttribute('src');
      if (src) {
        script.src = src;
        script.async = false;
        script.onload = resolve;
        script.onerror = reject;
      } else script.text = source.textContent;
      source.replaceWith(script);
      if (!src) resolve();
    })), Promise.resolve());
  }

  window.deferActivityBootstrap = function deferActivityBootstrap(name) {
    let started = false;
    window.addEventListener('lesson-start-ready', function () {
      if (started) return;
      started = true;
      runScripts([...document.querySelectorAll(`script[data-activity-bootstrap="${name}"]`)])
        .then(() => window.dispatchEvent(new Event('lesson-start-ready')))
        .catch(error => console.error('Activity bootstrap failed', error));
    }, { once: true });
  };
}());
