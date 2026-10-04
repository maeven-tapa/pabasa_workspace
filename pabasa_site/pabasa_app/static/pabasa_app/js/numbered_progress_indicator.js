(function () {
  'use strict';

  const path = window.location.pathname.replace(/\/+$/, '');
  const target = path.endsWith('/lesson-4/gawain-1') || path.endsWith('/lesson-4-gawain-1') || path.endsWith('/prescribed/lesson4-gawain1')
    ? { card: '#app', source: '.progress' }
    : path.endsWith('/session-2-lesson-4-gawain-2') || path.endsWith('/prescribed/session-2-lesson-4-gawain-2')
      ? { card: '.card', source: '#progress' }
      : path.includes('/lesson-5-gawain-1') || path.includes('/lesson-5/gawain-1') || path.includes('/prescribed/lesson5-gawain1')
        ? { card: '#app', source: '#progress' }
        : path.endsWith('/lesson-6-gawain-1') || path.endsWith('/lesson-6/gawain-1') || path.endsWith('/prescribed/lesson6-gawain1')
          ? { card: '#app', source: '.head > b' }
          : null;
  const session3Key = path.includes('/lesson-7/gawain-1') || path.includes('/lesson-7-gawain-1')
    ? 'g1'
    : path.includes('lesson7-gawain2a') ? 'g2a'
      : path.includes('lesson7-gawain2b') ? 'g2b'
        : path.includes('lesson7-gawain2c') ? 'g2c'
          : path.includes('lesson7-gawain3') ? 'g3'
              : path.includes('lesson7-gawain4b') ? 'g4b'
                : path.includes('lesson7-gawain4') ? 'g4'
                  : path.includes('lesson8-gawain1a') ? 'l8g1a'
                    : path.includes('lesson8-gawain1') ? 'l8g1'
                      : path.includes('lesson9-gawain1') ? 'l9g1'
                        : path.includes('lesson9-gawain2') ? 'l9g2'
                          : path.includes('lesson9-gawain3') ? 'l9g3' : null;
  const session3Target = session3Key ? { card: '#app', source: session3Key === 'g1' ? '.head > b' : session3Key === 'l8g1a' ? '#status' : '.progress' } : null;
  const effectiveTarget = session3Target || target;
  if (!effectiveTarget) return;
  const isLesson5 = path.includes('/lesson-5/gawain-1') || path.includes('/lesson-5-gawain-1') || path.includes('/prescribed/lesson5-gawain1');

  const findCard = () => document.querySelector(effectiveTarget.card);
  const parseProgress = source => {
    if (source?.dataset?.state) {
      const saved = source.dataset.state.split('/').map(Number);
      if (saved.length === 2 && saved.every(Number.isFinite)) return { current: saved[0], total: saved[1] };
    }
    const text = source?.textContent || '';
    const match = text.match(/(\d+)\s*\/\s*(\d+)/);
    return match ? { current: Number(match[1]), total: Number(match[2]) } : null;
  };
  const update = () => {
    const card = findCard();
    if (!card) return;
    const source = card.querySelector(effectiveTarget.source);
    if (session3Key === 'l8g1') card.querySelector('.lesson8-g1-progress')?.remove();
    if (session3Key === 'l8g1a') {
      card.querySelectorAll('.lesson8-g1-progress, .lesson8-g1a-progress').forEach(node => node.remove());
    }
    if (isLesson5) card.querySelector('.lesson5-numbered-progress')?.remove();
    const existing = card.querySelector('.numbered-progress');
    let state = parseProgress(source || existing);
    if (session3Key) {
      const status = card.querySelector('#status, .row-count');
      const text = status?.textContent || '';
      const match = text.match(/(?:Larawan|Aytem|Hanay)\s+(\d+)\s+(?:sa|ng|\/)\s+(\d+)/i);
      if (match) state = { current: Number(match[1]), total: Number(match[2]) };
      if (session3Key === 'g4a') {
        const total = card.querySelectorAll('.cell').length;
        const completed = card.querySelectorAll('.cell .stamp').length;
        if (total) state = { current: Math.min(total, completed + 1), total };
      }
      else if (session3Key === 'g1') state = parseProgress(source || existing);
      if (status && (session3Key === 'g2a' || session3Key === 'g2b' || session3Key === 'l9g3')) status.classList.toggle('numbered-progress-count-label', Boolean(match));
    }
    if (!state || !state.total) return;

    // Re-renders can leave a legacy progress node or duplicate indicator in
    // the card. Keep the accessible source long enough to read its state,
    // then retain exactly one compact indicator.
    if (session3Key) {
      card.querySelectorAll('.progress').forEach(node => { if (node !== source) node.remove(); });
    }
    card.querySelectorAll('.numbered-progress').forEach((node, index) => {
      if (index > 0) node.remove();
    });

    if (source && source !== existing) {
      source.setAttribute('aria-label', `Pag-unlad: ${state.current} sa ${state.total}`);
      source.remove();
    }

    const progress = existing || document.createElement('div');
    const stateKey = `${state.current}/${state.total}`;
    const host = card;
    if (existing && progress.dataset.state === stateKey && host.lastElementChild === progress) return;
    progress.className = 'numbered-progress';
    progress.dataset.state = stateKey;
    progress.setAttribute('role', 'progressbar');
    progress.setAttribute('aria-valuemin', '1');
    progress.setAttribute('aria-valuemax', String(state.total));
    progress.setAttribute('aria-valuenow', String(state.current));
    progress.setAttribute('aria-label', `Pag-unlad: ${state.current} sa ${state.total}`);
    progress.innerHTML = '';
    for (let n = 1; n <= state.total; n += 1) {
      const circle = document.createElement('span');
      circle.className = `numbered-progress__circle ${n < state.current ? 'is-completed' : n === state.current ? 'active' : ''}`;
      circle.textContent = String(n);
      circle.setAttribute('aria-hidden', 'true');
      progress.appendChild(circle);
    }
    if (host.lastElementChild !== progress) host.appendChild(progress);
  };

  const style = document.createElement('style');
  style.textContent = `
    .numbered-progress { display:flex; align-items:center; justify-content:center; gap:8px; width:100%; flex:0 0 auto; margin:12px auto 0; order:999; font-family:BasahinFredoka, Fredoka, Nunito, sans-serif; }
    .numbered-progress__circle { display:grid; place-items:center; width:32px; height:32px; border:2px solid #dce9e9; border-radius:50%; background:#f5faf9; color:#54727a; font:400 15px/1 BasahinFredoka, Fredoka, Nunito, sans-serif; }
    .numbered-progress__circle.active { border-color:#e9ad38; background:#f6bf4c; color:#77531d; }
    .numbered-progress__circle.is-completed { border-color:#299e9a; background:#299e9a; color:#fff; }
    body.numbered-progress-lesson5 .focus { gap:6px; }
    body.numbered-progress-lesson5 .focus > .status { display:none; }
    body.numbered-progress-lesson5 > .numbered-progress { margin-top:8px; }
    .numbered-progress-count-label { display:none !important; }
    @media (max-width:600px) { .numbered-progress { gap:5px; margin-top:8px; } .numbered-progress__circle { width:28px; height:28px; font-size:13px; } }
  `;
  document.head.appendChild(style);

  const prepare = () => {
    const card = findCard();
    if (!card) return;
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.alignItems = card.style.alignItems || 'center';
    if (isLesson5) document.body.classList.add('numbered-progress-lesson5');
    update();
  };
  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; prepare(); });
  };
  const observer = new MutationObserver(schedule);
  // Lesson 5 still contains an older inline fallback observer. Disable that
  // fallback before it runs, while retaining this already-created native observer.
  if (isLesson5) {
    const NativeObserver = window.MutationObserver;
    const nativeInterval = window.setInterval;
    window.MutationObserver = class { observe() {} disconnect() {} takeRecords() { return []; } };
    window.setInterval = (callback, delay, ...args) => delay === 200 ? 0 : nativeInterval(callback, delay, ...args);
    document.addEventListener('DOMContentLoaded', () => { window.MutationObserver = NativeObserver; window.setInterval = nativeInterval; }, { once: true });
  }
  const start = () => {
    prepare();
    const card = findCard();
    if (card) observer.observe(card, { childList: true, subtree: true });
    else requestAnimationFrame(start);
    if (isLesson5) {
      const retry = window.setInterval(() => {
        prepare();
        const currentCard = findCard();
        if (currentCard?.querySelector('.numbered-progress') && !currentCard.querySelector('#progress')) window.clearInterval(retry);
      }, 150);
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
}());
