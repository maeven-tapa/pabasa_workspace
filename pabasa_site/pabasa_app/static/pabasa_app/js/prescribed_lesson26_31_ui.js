(() => {
  'use strict';

  const dataNode = document.getElementById('prescribed-activity-data');
  if (!dataNode) return;

  const data = JSON.parse(dataNode.textContent || '{}');
  const progress = data.progress || {};
  const state = progress.state || {};
  const modal = document.querySelector('body > div[id$="-start"]');
  const back = document.querySelector('a[id$="-back"]');
  const app = document.getElementById('app');

  function isMeaningful(value, key = '') {
    if (['activity_key', 'title', 'description', 'instruction', 'total_items', 'phase'].includes(key)) return false;
    if (value === true) return true;
    if (typeof value === 'number') return value > 0;
    if (typeof value === 'string') return Boolean(value.trim() && value !== 'initial' && value !== 'idle');
    if (Array.isArray(value)) return value.some(item => isMeaningful(item));
    if (value && typeof value === 'object') {
      return Object.entries(value).some(([childKey, childValue]) => isMeaningful(childValue, childKey));
    }
    return false;
  }

  function completed() {
    return progress.activity_completed === true || state.phase === 'complete';
  }

  function installStyles() {
    if (document.getElementById('prescribed-lesson26-31-ui-styles')) return;
    const style = document.createElement('style');
    style.id = 'prescribed-lesson26-31-ui-styles';
    style.textContent = `
      .pabasa-resume-backdrop{position:fixed!important;inset:0!important;z-index:1000!important;display:grid!important;place-items:center!important;padding:20px!important;background:#e7f7f7d9!important;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px)}
      .pabasa-resume-backdrop[hidden]{display:none!important}
      .pabasa-resume-card{box-sizing:border-box!important;width:min(500px,calc(100vw - 40px))!important;max-width:100%!important;padding:32px 34px 30px!important;border:2px solid #ffffffd9!important;border-radius:30px!important;background:#fffffff5!important;box-shadow:0 22px 60px #173f6335!important;text-align:center!important}
      .pabasa-resume-label{margin:0 0 16px!important;color:#277f82!important;font-size:1rem!important;font-weight:900!important;letter-spacing:.08em!important}
      .pabasa-resume-message{margin:0 0 22px!important;color:#183e63!important;font-size:clamp(1.65rem,4vw,2.25rem)!important;font-weight:900!important;line-height:1.2!important}
      .pabasa-resume-actions{display:grid!important;gap:14px!important}
      .pabasa-resume-actions button{box-sizing:border-box!important;width:100%!important;min-height:62px!important;padding:13px 20px!important;border-radius:999px!important;font:inherit!important;font-size:1.15rem!important;font-weight:900!important;cursor:pointer!important}
      .pabasa-resume-actions .pabasa-resume-continue{border:0!important;background:#299e9a!important;color:#fff!important;box-shadow:0 5px 0 #187b7a,0 8px 18px #187b7a26!important}
      .pabasa-resume-actions .pabasa-resume-restart{border:3px solid #94d9d6!important;background:#fff!important;color:#187b7a!important;box-shadow:0 4px 0 #b7d6dc!important}
      body.pabasa-completion-active{min-height:100vh!important;overflow:hidden!important}
      body.pabasa-completion-active> :not(#app){display:none!important}
      #app.pabasa-completion-root{position:fixed!important;inset:0!important;z-index:1001!important;display:grid!important;place-items:center!important;width:100vw!important;height:100vh!important;height:100dvh!important;min-height:100dvh!important;margin:0!important;padding:24px!important;overflow:auto!important;box-sizing:border-box!important;background:transparent!important;filter:none!important;opacity:1!important}
      .pabasa-completion-card{box-sizing:border-box!important;width:min(550px,calc(100vw - 40px))!important;margin:auto!important;padding:38px 34px 34px!important;border:2px solid #ffffffd9!important;border-radius:30px!important;background:#fff!important;box-shadow:0 22px 60px #173f6340!important;text-align:center!important}
      .pabasa-completion-card h1{margin:0!important;color:#183e63!important;font-size:clamp(28px,3vw,32px)!important;font-weight:900!important;line-height:1.2!important}
      .pabasa-completion-card p{margin:18px 0 0!important;color:#183e63!important;font-size:clamp(18px,2vw,20px)!important;font-weight:800!important;line-height:1.4!important}
      .pabasa-completion-actions{display:flex!important;justify-content:center!important;width:100%!important;margin-top:26px!important}
      a.pabasa-completion-button{display:inline-flex!important;align-items:center!important;justify-content:center!important;width:min(100%,390px)!important;min-height:68px!important;padding:14px 24px!important;border:0!important;border-radius:999px!important;background:#299e9a!important;box-shadow:0 5px 0 #187b7a,0 8px 18px #187b7a26!important;color:#fff!important;font:inherit!important;font-size:clamp(18px,2vw,20px)!important;font-weight:900!important;text-align:center!important;text-decoration:none!important}
      @media(max-width:480px){.pabasa-resume-card{padding:28px 22px 26px!important}.pabasa-completion-card{padding:30px 22px 26px!important}}
    `;
    document.head.append(style);
  }

  function configureResume() {
    if (!modal || completed()) return;
    const meaningful = Number(progress.completed_items || 0) > 0
      || Number(progress.current_index || 0) > 0
      || isMeaningful(state);
    const laterButton = modal.querySelector('button[id$="-later"],button[id$="-later-button"]');
    if (laterButton && !meaningful) {
      laterButton.textContent = 'MAYBE LATER';
      modal.addEventListener('click', event => {
        if (event.target !== laterButton && !laterButton.contains(event.target)) return;
        event.preventDefault();
        event.stopPropagation();
        if (back?.href) window.location.assign(back.href);
      }, true);
    }
    if (!meaningful) return;

    const card = modal.querySelector('.modal, .lesson26-start-modal, .lesson27-start-modal') || modal.firstElementChild;
    const paragraphs = [...modal.querySelectorAll('p')];
    const label = paragraphs[0];
    const message = modal.querySelector('h2');
    const continueButton = modal.querySelector('button[id$="-go"],button[id$="-start-button"]');
    const restartButton = modal.querySelector('button[id$="-later"],button[id$="-later-button"]');
    if (!card || !label || !message || !continueButton || !restartButton) return;

    installStyles();
    modal.classList.add('pabasa-resume-backdrop');
    card.classList.add('pabasa-resume-card');
    label.classList.add('pabasa-resume-label');
    label.textContent = 'PROGRESS SAVED!';
    message.classList.add('pabasa-resume-message');
    message.textContent = 'You’ve already started this activity. Would you like to continue where you left off?';
    if (!message.id) message.id = `${modal.id}-resume-message`;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', message.id);
    paragraphs.slice(1).forEach(paragraph => { paragraph.hidden = true; });
    const actions = continueButton.parentElement;
    actions?.classList.add('pabasa-resume-actions');
    continueButton.classList.add('pabasa-resume-continue');
    continueButton.textContent = 'CONTINUE';
    restartButton.classList.add('pabasa-resume-restart');
    restartButton.textContent = 'START OVER';
  }

  function showCompletion(target = app) {
    if (!target || !back) return;
    installStyles();
    if (modal) {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      modal.style.display = 'none';
    }

    const card = document.createElement('section');
    card.className = 'pabasa-completion-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.innerHTML = '<h1>Activity complete! 🎉</h1><p>Great job! You have completed the activity.</p><div class="pabasa-completion-actions"></div>';
    back.classList.add('pabasa-completion-button');
    back.replaceChildren(document.createTextNode('BACK TO MY LESSONS'));
    card.querySelector('.pabasa-completion-actions').append(back);
    target.replaceChildren(card);
    target.classList.add('pabasa-completion-root');
    document.body.append(target);
    [...document.body.children].forEach(child => { if (child !== target) child.hidden = true; });
    document.body.classList.add('pabasa-completion-active');
  }

  window.PrescribedLessonUi = {showCompletion};
  configureResume();

  document.addEventListener('DOMContentLoaded', () => {
    if (!completed() || !app) return;
    showCompletion(app);
  }, {once: true});
})();
