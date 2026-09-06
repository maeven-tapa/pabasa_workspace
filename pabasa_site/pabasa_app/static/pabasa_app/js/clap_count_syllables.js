(() => {
  const data = JSON.parse(document.querySelector('#material')?.textContent || '{}');
  const completed = JSON.parse(document.querySelector('#completion')?.textContent || '{}');
  const stage = document.querySelector('#stage');
  const progress = document.querySelector('#progress');
  const fill = document.querySelector('#progressFill');
  const navStepper = document.querySelector('.clap-count-title');
  const items = [...(data.items || [])];

  if (data.randomize_order && !completed.completed) {
    for (let i = items.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [items[i], items[j]] = [items[j], items[i]];
    }
  }

  const sound = new Audio('/static/pabasa_app/audio/clap/clap-sound-effect.mp3');
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';

  let index = 0;
  let phase = 'listen';
  let claps = 0;
  let choice = null;
  let answers = [];
  let lottie = null;
  let speaking = false;
  let started = Date.now();
  let revealedSyllableCount = 0;
  let builtSyllables = [];
  let isCatchingSyllable = false;
  let isBuildReceiving = false;

  const item = () => items[index];
  const word = () => String(item()?.word || '').toUpperCase();
  const parts = () => item()?.syllables || [];
  const mascot = () => `<img class="clap-count-mascot" src="${esc(window.CLAP_MASCOT_URL)}" alt="PABASA mascot">`;
  const card = x => `<article class="clap-count-card game-card-container">${x}${mascot()}</article>`;

  const phaseStyles = `
    .clap-count-clap-scene {
      position: relative;
      display: grid;
      justify-items: center;
      gap: 14px;
      width: min(100%, 720px);
      padding: 6px 0 0;
    }
    .clap-count-word-phase {
      transition: transform 0.22s ease, filter 0.22s ease;
    }
    .clap-count-word-phase.is-catching {
      transform: translateY(-12px) scale(0.95);
      filter: drop-shadow(0 0 10px rgba(255, 246, 180, 0.9)) drop-shadow(0 0 18px rgba(255, 237, 148, 0.75));
    }
    .clap-count-build-area {
      position: relative;
      overflow: hidden;
      width: min(100%, 430px);
      min-height: 82px;
      padding: 13px 15px 15px;
      border: 2px dashed rgba(17, 92, 93, 0.38);
      border-radius: 20px;
      background: linear-gradient(145deg, rgba(255, 255, 249, 0.76), rgba(225, 245, 232, 0.58));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82), inset 0 -8px 18px rgba(38, 107, 85, 0.08), 0 7px 18px rgba(18, 69, 63, 0.18);
      backdrop-filter: blur(5px);
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
    }
    .clap-count-build-area::after {
      position: absolute;
      inset: 0;
      pointer-events: none;
      border: 1px solid rgba(255, 255, 255, 0.48);
      border-radius: inherit;
      content: "";
    }
    .clap-count-build-area.is-receiving {
      border-color: rgba(244, 189, 72, 0.72);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92), inset 0 -8px 18px rgba(38, 107, 85, 0.08), 0 0 0 4px rgba(255, 235, 157, 0.26), 0 9px 22px rgba(18, 69, 63, 0.22);
      transform: translateY(-2px);
    }
    .clap-count-build-label {
      margin-bottom: 8px;
      color: #0d5065;
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      opacity: 0.8;
    }
    .clap-count-build-tiles {
      position: relative;
      z-index: 1;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 8px;
      min-height: 34px;
    }
    .clap-count-built-syllable {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
      max-width: 100%;
      padding: 8px clamp(12px, 3vw, 16px);
      border-radius: 14px;
      border: 2px solid #d9ebde;
      background: linear-gradient(145deg, #fffef9, #effaf0);
      box-shadow: 0 4px 0 #a7d0b5;
      color: #0d5065;
      font-size: clamp(1.1rem, 2vw, 1.7rem);
      font-weight: 900;
      letter-spacing: 0.04em;
      line-height: 1.05;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }
    .clap-count-built-syllable.is-new {
      animation: clap-count-tile-land 280ms cubic-bezier(0.2, 1.35, 0.4, 1) both;
    }
    .clap-count-build-area.is-complete {
      border-style: solid;
      border-color: rgba(113, 168, 116, 0.58);
    }
    .clap-count-build-area.is-complete .clap-count-built-syllable {
      background: linear-gradient(145deg, #f0ffe9, #dff5de);
      box-shadow: 0 4px 0 #8ec298;
    }
    .clap-count-build-empty {
      position: relative;
      z-index: 1;
      display: block;
      width: 100%;
      height: 30px;
      border-radius: 12px;
      background: repeating-linear-gradient(90deg, rgba(23, 106, 91, 0.08) 0 2px, transparent 2px 54px);
      box-shadow: inset 0 1px 5px rgba(21, 86, 76, 0.08);
    }
    @keyframes clap-count-tile-land {
      0% { opacity: 0; transform: translateY(-7px) scale(0.86); }
      68% { opacity: 1; transform: translateY(2px) scale(1.04); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .clap-count-catch-syllable {
      position: absolute;
      left: 50%;
      top: 34%;
      transform: translate(-50%, -50%) scale(0.8);
      padding: 10px 18px;
      border-radius: 14px;
      background: linear-gradient(145deg, #fff7cf, #f9d569);
      border: 2px solid #f4ce58;
      box-shadow: 0 9px 0 #c98d1d, 0 18px 22px rgba(16, 56, 79, 0.2);
      color: #563b00;
      font-size: clamp(1.3rem, 3vw, 2.2rem);
      font-weight: 950;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      animation: clap-count-catch 0.42s ease-out forwards;
    }
    @keyframes clap-count-catch {
      0% { opacity: 0; transform: translate(-50%, -50%) scale(0.62); }
      22% { opacity: 1; transform: translate(-50%, -92%) scale(1.08); }
      55% { opacity: 1; transform: translate(-50%, -135%) scale(1.12); }
      100% { opacity: 0; transform: translate(-50%, -160%) scale(0.9); }
    }
    .clap-count-answer-grid .clap-count-answer {
      position: relative;
      z-index: 0;
      display: grid;
      place-items: center;
      padding: 12px 8px;
      line-height: 1;
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
    }
    .clap-count-answer-grid .clap-count-answer.is-selected {
      z-index: 1;
      transform: translateY(-3px) scale(1.02);
      box-shadow: 0 8px 0 #bd8b28, 0 12px 18px rgba(73, 56, 16, 0.2) !important;
    }
    .clap-count-answer-grid .clap-count-answer:active {
      transform: translateY(1px) scale(0.99);
    }
    .clap-count-answer-grid + .clap-count-actions .clap-count-button {
      border-color: rgba(255, 247, 194, 0.9);
      box-shadow: 0 5px 0 #0e4b50, 0 9px 16px rgba(11, 62, 65, 0.2);
      filter: saturate(1.08);
    }
    .clap-count-answer-grid + .clap-count-actions .clap-count-button:hover {
      transform: translateY(-2px);
      filter: saturate(1.08) brightness(1.05);
    }
    .clap-count-answer-grid + .clap-count-actions .clap-count-button:active {
      transform: translateY(2px);
      box-shadow: 0 2px 0 #0e4b50;
    }
    .clap-count-answer-grid + .clap-count-actions .clap-count-secondary {
      border-color: rgba(255, 255, 255, 0.72);
      background: rgba(255, 253, 245, 0.78);
      box-shadow: 0 3px 0 rgba(117, 157, 147, 0.75);
      color: #0d5065;
    }
    .clap-count-answer-grid + .clap-count-actions .clap-count-secondary:hover {
      transform: translateY(-1px);
    }
    .top-nav-bar .stepper-container {
      gap: clamp(5px, 1vw, 12px);
      width: min(420px, 100%);
    }
    .top-nav-bar .clap-count-step {
      min-width: clamp(48px, 5vw, 58px);
      color: rgba(9, 63, 80, 0.58);
      transition: transform 180ms ease, color 180ms ease;
    }
    .top-nav-bar .stepper-node-icon {
      width: 29px;
      height: 29px;
      border: 2px solid rgba(79, 137, 119, 0.26);
      background: rgba(255, 255, 255, 0.7);
      box-shadow: 0 2px 0 rgba(111, 157, 143, 0.35);
      color: rgba(9, 63, 80, 0.58);
      transition: transform 180ms ease, background 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }
    .top-nav-bar .clap-count-step.is-complete {
      color: rgba(35, 114, 76, 0.76);
    }
    .top-nav-bar .clap-count-step.is-complete .stepper-node-icon {
      border-color: #3b9165;
      background: #3b9165;
      box-shadow: 0 2px 0 #27714c;
      color: #fff;
    }
    .top-nav-bar .clap-count-step.is-active {
      color: #093f50;
      transform: scale(1.04);
    }
    .top-nav-bar .clap-count-step.is-active .stepper-node-icon {
      border-color: #f0b93d;
      background: linear-gradient(145deg, #fff6c9, #f4bd48);
      box-shadow: 0 2px 0 #bd8b28, 0 0 0 4px rgba(255, 232, 145, 0.42);
      color: #704800;
    }
    .top-nav-bar .clap-count-step.is-active .stepper-node-label {
      color: #093f50;
      font-weight: 900;
    }
    .top-nav-bar .clap-count-step-line {
      flex: 1 1 18px;
      min-width: 10px;
      max-width: 38px;
      height: 3px;
      margin-top: 13px;
      border-radius: 999px;
      background: rgba(121, 166, 151, 0.34);
      transition: background 180ms ease;
    }
    .top-nav-bar .clap-count-step-line.is-complete {
      background: #78b68f;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.7);
    }
    .clap-count-progress {
      width: min(180px, 100%);
      padding-inline: 2px;
    }
    .clap-count-progress-text {
      margin-bottom: 6px;
      color: #093f50;
      font-size: clamp(0.76rem, 1.2vw, 0.88rem);
      font-weight: 800;
      letter-spacing: 0.02em;
      line-height: 1;
      white-space: nowrap;
    }
    .clap-count-track {
      height: 8px;
      border: 1px solid rgba(102, 153, 137, 0.24);
      background: rgba(211, 229, 222, 0.74);
      box-shadow: inset 0 1px 2px rgba(31, 86, 70, 0.12), 0 1px 0 rgba(255, 255, 255, 0.72);
    }
    .clap-count-fill {
      background: linear-gradient(90deg, #126d75, #55b590);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.32);
    }
    @media (max-width: 760px) {
      .clap-count-header {
        gap: 6px;
        padding-inline: 9px;
      }
      .clap-count-back {
        padding-inline: 10px;
      }
      .clap-count-title {
        font-size: clamp(0.82rem, 2vw, 1.05rem);
      }
      .top-nav-bar .stepper-container {
        gap: 3px;
      }
      .top-nav-bar .clap-count-step {
        min-width: 39px;
      }
      .top-nav-bar .stepper-node-label {
        font-size: clamp(0.58rem, 1.6vw, 0.7rem);
      }
      .top-nav-bar .stepper-node-icon {
        width: 26px;
        height: 26px;
      }
      .top-nav-bar .clap-count-step-line {
        min-width: 5px;
        margin-top: 12px;
      }
      .clap-count-progress {
        width: min(145px, 100%);
      }
    }
  `;

  if (!document.getElementById('clap-count-phase-2-styles')) {
    const styleTag = document.createElement('style');
    styleTag.id = 'clap-count-phase-2-styles';
    styleTag.textContent = phaseStyles;
    document.head.appendChild(styleTag);
  }

  function resetBuildState() {
    revealedSyllableCount = 0;
    builtSyllables = [];
    claps = 0;
    isCatchingSyllable = false;
    isBuildReceiving = false;
  }

  function steps() {
    const s = [['listen', '👂', 'Listen'], ['clap', '👏', 'Clap'], ['answer', '🔢', 'Count']];
    const p = { listen: 0, clap: 1, answer: 2 }[phase] ?? 2;
    return `<span class="clap-count-stepper stepper-container" aria-label="Learning steps">${s.map(([n, i, l], x) => `<span class="clap-count-step ${x < p ? 'is-complete' : x === p ? 'is-active' : ''}"><span class="clap-count-step-icon stepper-node-icon">${x < p ? '✓' : i}</span><span class="stepper-node-label">${l}</span></span>${x < 2 ? `<span class="clap-count-step-line ${x < p ? 'is-complete' : ''}"></span>` : ''}`).join('')}</span>`;
  }

  function panel(instruction, showWord = true, wordClass = '') {
    const characters = word().replace(/\s/g, '').length;
    const lengthClass = characters > 14 ? 'is-very-long' : characters > 9 ? 'is-long' : characters > 6 ? 'is-medium' : 'is-short';
    return `${showWord ? `<div class="clap-count-word-display ${lengthClass}"><h2 class="clap-count-word ${wordClass}">${esc(word())}</h2></div>` : ''}<p class="clap-count-instruction">${instruction}</p>`;
  }

  function buildArea() {
    const tiles = builtSyllables.length
      ? builtSyllables.map((part, tileIndex) => `<span class="clap-count-built-syllable ${isBuildReceiving && tileIndex === builtSyllables.length - 1 ? 'is-new' : ''}">${esc(part)}</span>`).join('')
      : '<span class="clap-count-build-empty" aria-hidden="true"></span>';
    return `<div class="clap-count-build-area ${builtSyllables.length === parts().length ? 'is-complete' : ''} ${isBuildReceiving ? 'is-receiving' : ''}" aria-live="polite"><div class="clap-count-build-label">Build Area</div><div class="clap-count-build-tiles">${tiles}</div></div>`;
  }

  function update() {
    progress.textContent = `Word ${Math.min(index + 1, items.length)} of ${items.length}`;
    fill.style.width = `${items.length ? ((index + 1) / items.length) * 100 : 100}%`;
    navStepper.classList.add('top-nav-bar');
    navStepper.innerHTML = steps();
  }

  function renderIntro() {
    stage.innerHTML = `<section class="clap-count-intro" aria-labelledby="clapCountIntroTitle"><div class="clap-count-intro-card"><div class="clap-count-intro-icon" aria-hidden="true">👏</div><h2 id="clapCountIntroTitle">Clap &amp; Count!</h2><p class="clap-count-intro-lead">Listen to the word, then clap for each syllable.</p><div class="clap-count-intro-example" aria-label="Banana has three syllables and three claps"><div class="clap-count-intro-word">BANANA</div><div class="clap-count-intro-claps"><span>BA 👏</span><span>NA 👏</span><span>NA 👏</span></div></div><p class="clap-count-intro-key">ONE CLAP = ONE SYLLABLE</p><button class="clap-count-intro-start" id="startClapCountButton" type="button">Let’s Start!</button></div></section>`;
    document.querySelector('#startClapCountButton')?.addEventListener('click', () => {
      render();
    }, { once: true });
  }

  function render() {
    if (!item()) return finish();
    if (phase === 'listen') resetBuildState();

    update();
    let body = '';

    if (phase === 'listen') {
      body += `${panel('Hear the word, then clap its spoken chunks.', true, 'clap-count-word-listen-phase')}<button class="clap-count-button clap-count-listen" id="listen" type="button">🔊 Hear the word</button>`;
    } else if (phase === 'clap') {
      const characters = word().replace(/\s/g, '').length;
      const lengthClass = characters > 14 ? 'is-very-long' : characters > 9 ? 'is-long' : characters > 6 ? 'is-medium' : 'is-short';
      body += `<div class="clap-count-clap-scene"><div class="clap-count-word-display ${lengthClass}"><h2 class="clap-count-word clap-count-word-phase">${esc(word())}</h2></div>${buildArea()}</div><button class="clap-count-clap-button" id="clap" type="button" aria-label="Clap once. ${claps} claps so far"><span class="clap-count-ripple"></span><span id="clapAnimation"></span><span class="clap-count-clap-label">TAP TO CLAP</span></button><p class="clap-count-claps" id="clapCount">${claps} ${claps === 1 ? 'clap' : 'claps'}</p><div class="clap-count-actions"><button class="clap-count-secondary" id="clear" ${(claps || builtSyllables.length) ? '' : 'disabled'}>Start over</button><button class="clap-count-button" id="count" ${builtSyllables.length === parts().length && !isCatchingSyllable ? '' : 'disabled'}>Count my claps →</button></div>`;
    } else {
      const buttons = [1, 2, 3, 4, 5].map(n => `<button class="clap-count-answer ${choice === n ? 'is-selected' : ''}" data-answer="${n}" aria-pressed="${choice === n}">${n}</button>`).join('');
      body += `${panel('How many syllables did you clap?')}<div class="clap-count-answer-grid" aria-label="How many syllables did you hear?">${buttons}</div><div class="clap-count-actions"><button class="clap-count-secondary" id="again">Clap again</button><button class="clap-count-button" id="check" ${choice === null ? 'disabled' : ''}>Check my answer ✓</button></div>`;
    }

    stage.innerHTML = card(`<div class="clap-count-content">${body}</div>`);
    if (phase === 'clap') setup();

    document.querySelector('#listen')?.addEventListener('click', speak);
    document.querySelector('#clap')?.addEventListener('click', clap);
    document.querySelector('#clear')?.addEventListener('click', () => {
      resetBuildState();
      render();
    });
    document.querySelector('#count')?.addEventListener('click', () => {
      phase = 'answer';
      render();
    });
    document.querySelector('#again')?.addEventListener('click', () => {
      phase = 'clap';
      choice = null;
      resetBuildState();
      render();
    });
    document.querySelectorAll('[data-answer]').forEach(button => {
      button.addEventListener('click', () => {
        choice = Number(button.dataset.answer);
        render();
      });
    });
    if (phase === 'answer') {
      document.querySelector('#check')?.addEventListener('click', check);
    }
  }

  function speak() {
    if (speaking) return;
    if (!('speechSynthesis' in window)) {
      phase = 'clap';
      return render();
    }

    speaking = true;
    const button = document.querySelector('#listen');
    if (button) {
      button.disabled = true;
      button.classList.add('is-playing');
      button.textContent = '🔊 Listening…';
    }
    const wordElement = document.querySelector('.clap-count-word');
    wordElement?.classList.add('is-listening');
    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(item().word);
    utterance.lang = data.language === 'Filipino' ? 'fil-PH' : 'en-US';
    const done = () => {
      speaking = false;
      if (phase === 'listen') {
        phase = 'clap';
        render();
      }
    };

    utterance.onend = done;
    utterance.onerror = done;
    speechSynthesis.speak(utterance);
  }

  function setup() {
    const container = document.querySelector('#clapAnimation');
    if (!container || !window.lottie) return;
    lottie?.destroy();
    lottie = window.lottie.loadAnimation({
      container,
      renderer: 'svg',
      loop: false,
      autoplay: false,
      path: window.CLAP_ANIMATION_URL,
    });
  }

  function clap() {
    if (phase !== 'clap' || isCatchingSyllable || builtSyllables.length >= parts().length) return;

    const nextSyllable = parts()[revealedSyllableCount];
    if (!nextSyllable) return;

    isCatchingSyllable = true;
    const button = document.querySelector('#clap');
    const cardElement = stage.querySelector('.clap-count-card');
    const scene = stage.querySelector('.clap-count-clap-scene');
    const wordElement = stage.querySelector('.clap-count-word-phase');

    if (button) {
      button.classList.remove('is-clapping');
      void button.offsetWidth;
      button.classList.add('is-clapping');
    }
    if (cardElement) cardElement.classList.add('is-clapping');

    sound.currentTime = 0;
    sound.play().catch(() => {});
    lottie?.stop();
    lottie?.goToAndPlay(0, true);

    if (wordElement) wordElement.classList.add('is-catching');

    if (scene) {
      const catchTile = document.createElement('div');
      catchTile.className = 'clap-count-catch-syllable';
      catchTile.textContent = nextSyllable;
      catchTile.setAttribute('aria-hidden', 'true');
      scene.appendChild(catchTile);

      setTimeout(() => {
        if (wordElement) wordElement.classList.remove('is-catching');
        catchTile.remove();

        builtSyllables.push(nextSyllable);
        revealedSyllableCount = builtSyllables.length;
        claps = revealedSyllableCount;

        const countElement = document.querySelector('#clapCount');
        if (countElement) countElement.textContent = `${claps} ${claps === 1 ? 'clap' : 'claps'}`;

        const clearButton = document.querySelector('#clear');
        const countButton = document.querySelector('#count');
        if (clearButton) clearButton.disabled = false;
        if (countButton) countButton.disabled = !(builtSyllables.length === parts().length);

        isCatchingSyllable = false;
        isBuildReceiving = true;
        render();

        setTimeout(() => {
          isBuildReceiving = false;
          render();
        }, 280);
        if (cardElement) setTimeout(() => cardElement.classList.remove('is-clapping'), 430);
        if (button) setTimeout(() => button.classList.remove('is-clapping'), 430);
      }, 420);
    }
  }

  function check() {
    if (choice === null) return;
    answers.push({ word_id: item().id, answer: choice, claps });
    if (choice === +item().syllable_count) return success();
    retry();
  }

  function retry() {
    update();
    stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><h2>Let’s clap again</h2><p><strong>${esc(word())}</strong></p>${buildArea()}<button class="clap-count-button" id="retry">👏 Try clapping again</button></section></div>`);
    document.querySelector('#retry').onclick = () => {
      phase = 'clap';
      choice = null;
      resetBuildState();
      render();
    };
  }

  function success() {
    update();
    stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><div class="clap-count-success-banner">✨ GREAT JOB! ✨</div><h2 class="clap-count-success-title">Amazing clapping!</h2><p class="clap-count-success-word">${esc(word())}</p><div class="clap-count-result-syllables" aria-label="Syllable breakdown">${parts().map(part => `<span class="clap-count-result-chip">${esc(part)}</span>`).join('')}</div><p class="clap-count-syllable-total">👏 ${item().syllable_count} ${+item().syllable_count === 1 ? 'syllable' : 'syllables'} 👏</p><p class="clap-count-mascot-cheer">🐧 You crushed it!</p><button class="clap-count-button clap-count-success-next" id="next">${index === items.length - 1 ? 'Finish' : 'Next word →'}</button></section></div>`);
    document.querySelector('#next').onclick = () => {
      index += 1;
      phase = 'listen';
      claps = 0;
      choice = null;
      resetBuildState();
      render();
    };
  }

  async function finish() {
    progress.textContent = 'Complete ✓';
    fill.style.width = '100%';
    stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><div class="clap-count-phase">Saving result…</div><h2>Great job! 🎉</h2><p>You completed Clap &amp; Count Syllables.</p></section></div>`);

    try {
      const response = await fetch('/record-assessment-completion/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({
          material_id: data.id,
          activity_type: 'assessment',
          assessment_type: 'word',
          items_completed: items.length,
          scores: {
            answers,
            duration_seconds: Math.round((Date.now() - started) / 1000),
          },
        }),
      });

      const result = await response.json();
      if (!response.ok || !result.success) throw Error(result.error || 'Unable to save result.');

      stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><div class="clap-count-phase">Activity complete</div><h2>Great job! 🎉</h2><p>${+result.correct_items || 0} of ${+result.items_completed || 0} correct · ${+result.accuracy || 0}%</p><a class="clap-count-button" href="/dashboard/assessment/">Back to Assessments →</a></section></div>`);
    } catch (error) {
      stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><h2>Please try again</h2><p>${esc(error.message)}</p><button class="clap-count-button" id="save">Save again</button></section></div>`);
      document.querySelector('#save').onclick = finish;
    }
  }

  if (completed.completed) {
    progress.textContent = 'Completed ✓';
    fill.style.width = '100%';
    stage.innerHTML = card(`<div class="clap-count-content"><section class="clap-count-success"><div class="clap-count-phase">Completed ✓</div><h2>Activity finished!</h2><p>${+completed.correct_items || 0} of ${+completed.total_items || 0} correct · ${+completed.accuracy || 0}%</p><a class="clap-count-button" href="/dashboard/assessment/">Back to Assessments →</a></section></div>`);
  } else if (items.length) {
    renderIntro();
  }
})();
