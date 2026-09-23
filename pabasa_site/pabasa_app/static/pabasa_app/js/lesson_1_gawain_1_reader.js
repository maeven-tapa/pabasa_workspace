(() => {
  'use strict';

  const TARGETS = [
    'Ang ating alpabeto, ating pag-aralan',
    'Umpisahan ngayon',
    'Aso, bola, cactus, daga, eroplano',
    'French fries, gatas, hipon, ilaw, jeepney',
    'Keso, lamok, medyas, noo, okra',
    'Pato, Quezon, rosas, sisiw, tigre',
    'Ubas, Venus, watawat, xylophone',
    'Yoyo, zebra, ngipin niya, enye',
    'Ating alpabeto, madaling pag-aralan',
    'At ’wag mong kakalimutan',
    'Laging tatandaan',
  ];
  const TOTAL = TARGETS.length;
  const ACTIVITY_KEY = 'lesson-1-gawain-1';
  const CHUNK_MS = 40000;
  const REQUEST_TIMEOUT_MS = 35000;
  const MAX_CHUNK_RETRIES = 2;
  const MIN_MATCHED = 8;
  const MIN_RATIO = 0.65;
  const SONG_URL = 'https://www.youtube.com/watch?v=OxAsjUK6aB4';
  const WELCOME_AUDIO_URL = '/static/pabasa_app/prescribed/audio/SESSION%201/LESSON%201/GAWAIN%201/hello_ka-basa.mp3';
  const SONG_PANEL_NARRATION_URL = '/static/pabasa_app/prescribed/audio/SESSION%201/LESSON%201/GAWAIN%201/makinig_at_awitin.mp3';
  const CARD_DATA = [
    ['Aa', 'apa', 'apa.png'], ['Bb', 'bahay', 'bahay.png'],
    ['Cc', 'computer', '../picture_word/custom/Computer-Kompyuter.png'],
    ['Dd', 'dentista', 'dentista.png'], ['Ee', 'elepante', 'elepante.png'],
    ['Ff', 'futbol', 'futball.png'], ['Gg', 'gitara', 'gitara.png'],
    ['Hh', 'helikopter', 'helikopter.png'], ['Ii', 'itlog', 'itlog.png'],
    ['Jj', 'jeepney', 'jeepney.png'], ['Kk', 'keso', 'cheese.png'],
    ['Ll', 'liyon', 'liyon.png'], ['Mm', 'mais', 'mais.png'],
    ['Nn', 'narra', 'narra.png'], ['Ññ', 'Malacañang', 'malacanang.jpg'],
    ['Ng', 'ngipin', 'ngipin.png'], ['Oo', 'orasan', 'orasan.png'],
    ['Pp', 'piso', 'piso.jpg'], ['Qq', 'Quezon', 'quezon.png'],
    ['Rr', 'radyo', 'radyo.png'], ['Ss', 'saging', 'saging.png'],
    ['Tt', 'tarsier', 'tarsier.png'], ['Uu', 'ulan', 'ulan.png'],
    ['Vv', 'vinta', 'vinta.png'], ['Ww', 'walo', 'walo.png'],
    ['Xx', 'x-ray', 'x-ray.png'], ['Yy', 'yoyo', 'yoyo.png'],
    ['Zz', 'zebra', 'zebra.png'],
  ];
  const CANONICAL_TEXT = [
    'Ang ating alpabeto, ating pag-aralan', 'Umpisahan ngayon', '',
    'Aso, bola, cactus, daga, eroplano',
    'French fries, gatas, hipon, ilaw, jeepney',
    'Keso, lamok, medyas, noo, okra',
    'Pato, Quezon, rosas, sisiw, tigre',
    'Ubas, Venus, watawat, xylophone',
    'Yoyo, zebra, ngipin niya, enye', '',
    'Ating alpabeto, madaling pag-aralan', "At ’wag mong kakalimutan",
    'Laging tatandaan',
  ].join('\n');
  const TOKEN_VARIANTS = {
    cactus: ['cactus', 'kaktus', 'cacts'],
    quezon: ['quezon', 'kewzon', 'qezon'],
    venus: ['venus', 'venous', 'benus'],
    xylophone: ['xylophone', 'silophone', 'sailophone', 'zylophone'],
    enye: ['enye', 'enyeh', 'enyee'],
    ngipin: ['ngipin', 'ngipeen', 'ngipen'],
  };
  const state = {
    panel: null, stream: null, recorder: null, rotationTimer: null,
    finalizing: false, cancelled: false, failedChunk: null, attempt: 0,
    chunkSequence: 0, chunks: [], pendingRequests: [], requestRunning: false,
    activeRequestController: null, requestTimer: null, retryTimers: new Set(),
    mimeType: '', currentSegment: null, transcripts: new Map(), finalizedSequences: new Set(),
    transcriptionFailed: null, recordingParts: [], recordingUrl: '', recordingBlob: null,
    welcomeModal: null, welcomeAudio: null, welcomeAudioUrl: null,
    songPanelNarration: null, songPanelNarrationFinished: false,
    youtubeOpened: false, youtubePageHidden: false, youtubeReturned: false, statusPollTimer: null,
  };

  const data = () => JSON.parse(document.getElementById('lesson-one-data')?.textContent || '{}');
  const saved = () => data().progress?.state || {};
  const progressUrl = () => data().progress_url || document.querySelector('[data-progress-url]')?.dataset.progressUrl || '';
  function installRecordingStyles() {
    document.body.classList.add('lesson-one-page');
    if (document.getElementById('lesson-one-recording-styles')) return;
    const style = document.createElement('style');
    style.id = 'lesson-one-recording-styles';
    style.textContent = `
      .song-panel.is-recording {
        border-color: #d94e43;
        box-shadow: 0 0 0 3px #d94e4330, 0 0 24px #d94e4380, 0 8px 20px #a779251c;
      }
      .song-panel.is-recording .song-kicker {
        color: #b52f2f;
        text-shadow: 0 0 10px #d94e4366;
        animation: lessonOneRecordingGlow 1.4s ease-in-out infinite;
      }
      @keyframes lessonOneRecordingGlow {
        0%, 100% { opacity: .78; transform: scale(.98); }
        50% { opacity: 1; transform: scale(1.04); }
      }
      @media (prefers-reduced-motion: reduce) {
        .song-panel.is-recording .song-kicker { animation: none; opacity: 1; transform: none; }
      }
      .lesson-one-welcome-modal {
        position: fixed; inset: 0; z-index: 20; display: grid; place-items: center;
        padding: 20px; background: #123f4dcc;
      }
      .lesson-one-welcome-card {
        width: min(560px, 100%); padding: 30px 26px; border-radius: 24px;
        background: #fffdf7; color: #164b62; text-align: center;
        box-shadow: 0 20px 50px #0005;
      }
      .lesson-one-welcome-card h2 { margin: 0 0 14px; font-size: clamp(1.35rem, 3vw, 2rem); }
      .lesson-one-welcome-card p { margin: 10px 0; color: #627b84; font-weight: 700; line-height: 1.5; white-space: pre-line; }
      .lesson-one-welcome-actions { display: flex; gap: 12px; justify-content: center; margin-top: 22px; }
      .lesson-one-welcome-actions button, .lesson-one-welcome-retry {
        min-width: 120px; padding: 12px 20px; border: 0; border-radius: 13px;
        background: #299e9a; color: #fff; font-weight: 900; cursor: pointer;
      }
      .lesson-one-welcome-actions button:last-child { background: #d94e43; }
      .lesson-one-welcome-actions button:disabled { opacity: .45; cursor: wait; }
      .lesson-one-welcome-retry { margin-top: 14px; background: #627b84; }
      .lesson-one-welcome-status { min-height: 1.5em; font-size: .9rem; }
      @font-face {
        font-family: LessonOneFredoka;
        src: url('/static/pabasa_app/font/fredoka-one.one-regular.ttf') format('truetype');
        font-display: swap;
      }
      .lesson-one-page {
        --lesson-one-ink: #183e63;
        --lesson-one-teal: #299e9a;
        --lesson-one-teal-dark: #187b7a;
        --lesson-one-accent: #e7af45;
        min-height: 100vh;
        padding: 16px clamp(16px, 4vw, 42px) 22px;
        color: var(--lesson-one-ink);
        font-family: LessonOneFredoka, Nunito, "Segoe UI", sans-serif;
        background: #e1f5f7 url('/static/pabasa_app/prescribed/PRESCRIBED-BG.jpg') center/cover no-repeat;
        overflow: hidden;
      }
      .lesson-one-page .page {
        width: min(1250px, 100%);
        height: 100vh;
        margin: auto;
        padding: 0;
        position: relative;
      }
      .lesson-one-page .back {
        position: absolute;
        top: 0;
        left: 0;
        z-index: 2;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 13px;
        width: 280px;
        min-height: 64px;
        padding: 10px 18px;
        border: 0;
        border-radius: 999px;
        background: #fff;
        color: var(--lesson-one-ink);
        font-size: 1.2rem;
        line-height: 1.15;
        text-align: center;
        text-decoration: none;
        box-shadow: 0 8px 17px #145ca744;
        transition: .16s;
      }
      .lesson-one-page .back:hover { transform: translateY(-2px); box-shadow: 0 10px 22px #145ca755; }
      .lesson-one-page .back:active { transform: translateY(2px); box-shadow: 0 3px 8px #145ca744; }
      .lesson-one-page .back:focus-visible,
      .lesson-one-page button:focus-visible { outline: 4px solid #f5d47c; outline-offset: 4px; }
      .lesson-one-page .shell {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: min(1250px, 100%);
        height: auto;
        min-height: 0;
        margin: 0;
        padding: clamp(24px, 3.3vh, 42px) clamp(20px, 6vw, 80px) 20px;
        border: 2px solid #ffffffaa;
        border-radius: 42px;
        background: #ffffff63;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 18px 45px #1e5b7a35;
      }
      .lesson-one-page .eyebrow {
        margin: -8px auto 16px;
        padding: 10px 30px;
        border-radius: 999px;
        background: #277f82;
        color: #fff;
        font-size: clamp(.85rem, 1.4vw, 1.15rem);
        letter-spacing: .02em;
      }
      .lesson-one-page .title { margin: 0; font-size: clamp(2rem, 4vw, 3.7rem); line-height: 1.08; font-weight: 900; text-align: center; }
      .lesson-one-page .instruction { text-align: center; font-size: clamp(.95rem, 1.5vw, 1.15rem); line-height: 1.3; }
      .lesson-one-page .song-panel {
        border: 5px solid #94d9d6;
        border-radius: 34px;
        background: #ffffffe8;
        box-shadow: 0 10px 24px #187b7a20;
        padding: clamp(20px, 3vh, 32px);
      }
      .lesson-one-page .song-panel h2 { font-size: clamp(1.35rem, 2.5vw, 2.1rem); }
      .lesson-one-page .song-panel p { font-size: clamp(.9rem, 1.5vw, 1.05rem); }
      .lesson-one-page .review-audio { display: block; margin: 18px auto 0; }
      .lesson-one-page .review-actions { display: flex; flex-direction: column; align-items: center; gap: 14px; width: 100%; margin-top: 18px; }
      .lesson-one-page .review-actions .sing-again,
      .lesson-one-page .review-actions .sing-done { margin: 0; }
      .lesson-one-page .youtube-link,
      .lesson-one-page .sing-done,
      .lesson-one-page .sing-stop,
      .lesson-one-page .sing-again {
        min-height: 64px;
        margin: 14px auto 4px;
        border-radius: 999px;
        font-size: clamp(1rem, 1.8vw, 1.35rem);
        box-shadow: 0 7px 0 var(--lesson-one-teal-dark), 0 10px 20px #187b7a26;
      }
      .lesson-one-page .youtube-link { border: 4px solid #94d9d6; background: #fffffff0; color: var(--lesson-one-teal-dark); box-shadow: 0 5px 0 #b7d6dc, 0 8px 16px #187b7a20; }
      .lesson-one-page .sing-done { background: var(--lesson-one-teal); }
      .lesson-one-page .sing-stop { background: #d94e43; box-shadow: 0 7px 0 #9f302a, 0 10px 20px #9f302a26; }
      .lesson-one-page .sing-again { background: #627b84; box-shadow: 0 7px 0 #43575d, 0 10px 20px #43575d26; }
      .lesson-one-page .youtube-link:hover,
      .lesson-one-page .sing-done:hover,
      .lesson-one-page .sing-stop:hover,
      .lesson-one-page .sing-again:hover { filter: brightness(1.05); transform: translateY(-2px); }
      .lesson-one-page .board { gap: 12px; padding: 8px 4px; }
      .lesson-one-page .tile { border: 3px solid #94d9d6; border-radius: 22px; background: #ffffffe8; box-shadow: 0 7px 14px #164b6218; }
      .lesson-one-page .tile.active { border-color: var(--lesson-one-accent); background: #fff4bd; }
      @media (max-width: 800px) {
        .lesson-one-page { overflow: auto; }
        .lesson-one-page .page { height: auto; min-height: 100vh; }
        .lesson-one-page .shell { position: relative; top: auto; left: auto; transform: none; width: 100%; margin: 82px auto 0; padding: 28px 16px 20px; border-radius: 30px; }
        .lesson-one-page .back { width: 230px; min-height: 58px; font-size: 1rem; }
        .lesson-one-page .board { height: auto; grid-template-columns: repeat(3, minmax(108px, 1fr)); grid-template-rows: none; grid-auto-rows: minmax(112px, auto); gap: 10px; }
        .lesson-one-page .tile { min-height: 112px; padding: 10px 7px; }
        .lesson-one-page .tile img { height: 76px; }
        .lesson-one-page .youtube-link,
        .lesson-one-page .sing-done,
        .lesson-one-page .sing-stop,
        .lesson-one-page .sing-again { width: 100%; max-width: 100%; }
      }
    `;
    document.head.appendChild(style);
  }
  const csrf = () => document.cookie.split(';').map(x => x.trim())
    .find(x => x.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const normalize = (value) => String(value || '').normalize('NFKD')
    .replace(/[’‘ʼ\u0060]/g, "'").toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}']+/gu, ' ').replace(/\s+/g, ' ').trim();
  const tokens = (value) => normalize(value).replace(/'/g, '').split(' ').filter(Boolean);
  const tokenMatches = (expected, actual) => (TOKEN_VARIANTS[expected] || [expected]).includes(actual);

  function clearWelcomeAudio() {
    state.welcomeAudio?.pause();
    state.welcomeAudio = null;
    if (state.welcomeAudioUrl) URL.revokeObjectURL(state.welcomeAudioUrl);
    state.welcomeAudioUrl = null;
  }

  function setWelcomeButtons(enabled) {
    state.welcomeModal?.querySelectorAll('[data-welcome-choice]').forEach(button => {
      button.disabled = !enabled;
    });
  }

  async function narrateWelcome() {
    const modal = state.welcomeModal;
    if (!modal) return;
    const status = modal.querySelector('[data-welcome-status]');
    const retry = modal.querySelector('[data-welcome-retry]');
    setWelcomeButtons(false);
    if (retry) retry.hidden = true;
    if (status) status.textContent = 'Inihahanda ang pagsasalaysay…';
    clearWelcomeAudio();
    try {
      state.welcomeAudio = new Audio(WELCOME_AUDIO_URL);
      await new Promise((resolve, reject) => {
        state.welcomeAudio.onended = resolve;
        state.welcomeAudio.onerror = () => reject(new Error('Hindi mapatugtog ang pagsasalaysay.'));
        state.welcomeAudio.play().catch(reject);
      });
      if (status) status.textContent = 'Handa ka na bang magsimula?';
      setWelcomeButtons(true);
    } catch (error) {
      if (status) status.textContent = error.message || 'Hindi natapos ang pagsasalaysay.';
      if (retry) retry.hidden = false;
    } finally {
      clearWelcomeAudio();
    }
  }

  function showWelcomeModal() {
    const modal = document.createElement('section');
    modal.className = 'lesson-one-welcome-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'lesson-one-welcome-title');
    modal.innerHTML = '<div class="lesson-one-welcome-card"><h2 id="lesson-one-welcome-title">Hello, Ka-BASA.</h2><p>Sabay nating panuorin at pakinggan ang Awiting Alpabeto ng Filipino.\n\nHanda ka na ba?</p><div class="lesson-one-welcome-actions"><button type="button" data-welcome-choice="yes" disabled>Oo</button><button type="button" data-welcome-choice="no" disabled>Hindi</button></div><button type="button" class="lesson-one-welcome-retry" data-welcome-retry hidden>Ulitin ang pagsasalaysay</button></div>';
    document.body.appendChild(modal);
    state.welcomeModal = modal;
    modal.querySelector('[data-welcome-choice="yes"]').onclick = () => {
      modal.remove();
      state.welcomeModal = null;
      narrateSongPanel();
    };
    modal.querySelector('[data-welcome-choice="no"]').onclick = () => {
      clearWelcomeAudio();
      window.location.assign(document.querySelector('.back')?.href || '/');
    };
    modal.querySelector('[data-welcome-retry]').onclick = narrateWelcome;
    narrateWelcome();
  }

  function setSongPanelControlsEnabled(panel, enabled) {
    const youtubeLink = panel?.querySelector('.youtube-link');
    const readyButton = panel?.querySelector('#ready');
    if (!youtubeLink || !readyButton) return;
    const youtubeEnabled = enabled && state.songPanelNarrationFinished;
    const readyEnabled = enabled && state.songPanelNarrationFinished && state.youtubeReturned;
    readyButton.disabled = !readyEnabled;
    youtubeLink.setAttribute('aria-disabled', String(!youtubeEnabled));
    youtubeLink.style.opacity = youtubeEnabled ? '' : '.45';
    youtubeLink.style.pointerEvents = youtubeEnabled ? '' : 'none';
    youtubeLink.style.cursor = youtubeEnabled ? '' : 'wait';
    if (youtubeEnabled) youtubeLink.removeAttribute('tabindex');
    else youtubeLink.setAttribute('tabindex', '-1');
  }

  function updateSongPanelGate() {
    setSongPanelControlsEnabled(state.panel, true);
  }

  function showSongGateFeedback() {
    const status = state.panel?.querySelector('.song-note');
    if (!status) return;
    status.textContent = 'Panoorin muna ang awit bago tayo umawit.';
    status.setAttribute('aria-live', 'assertive');
  }

  async function narrateSongPanel() {
    if (state.songPanelNarration || !state.panel) return;
    setSongPanelControlsEnabled(state.panel, false);
    const audio = new Audio(SONG_PANEL_NARRATION_URL);
    state.songPanelNarration = audio;
    try {
      await new Promise((resolve, reject) => {
        audio.onended = resolve;
        audio.onerror = () => reject(new Error('Hindi mapatugtog ang pagsasalaysay.'));
        audio.play().catch(reject);
      });
    } catch (error) {
      console.error(error);
    } finally {
      if (state.songPanelNarration === audio) state.songPanelNarration = null;
      state.songPanelNarrationFinished = true;
      updateSongPanelGate();
    }
  }

  function handleSongPanelReturn() {
    if (!state.youtubeOpened || !state.youtubePageHidden || document.visibilityState !== 'visible') return;
    state.youtubeReturned = true;
    updateSongPanelGate();
  }

  function markSongPanelHidden() {
    if (state.youtubeOpened) state.youtubePageHidden = true;
  }
  const mimeType = () => ['audio/webm;codecs=opus', 'audio/webm',
    'audio/ogg;codecs=opus', 'audio/ogg']
    .find(x => window.MediaRecorder?.isTypeSupported?.(x)) || '';

  function renderBoard() {
    const board = document.getElementById('board');
    const base = '/static/pabasa_app/images/alpabetong_pilipino/';
    if (!board) return;
    board.innerHTML = CARD_DATA.map((x, i) =>
      '<article class="tile" data-card-index="' + i + '"><strong class="tile-letter">' +
      x[0] + '</strong><img src="' + base + x[2] + '" alt="' + x[1] +
      '"><span class="tile-word">' + x[1] + '</span></article>').join('');
  }

  function renderPanel() {
    const video = document.querySelector('.video-wrap');
    if (!video) return null;
    const panel = document.createElement('section');
    panel.className = 'song-panel';
    video.replaceWith(panel);
    state.panel = panel;
    return panel;
  }

  function clearTimers() {
    if (state.rotationTimer) clearTimeout(state.rotationTimer);
    state.rotationTimer = null;
    if (state.requestTimer) clearTimeout(state.requestTimer);
    state.requestTimer = null;
    state.retryTimers.forEach(x => clearTimeout(x));
    state.retryTimers.clear();
  }

  function stopTracks() {
    state.stream?.getTracks().forEach(track => track.stop());
    state.stream = null;
  }

  function cleanup() {
    clearTimers();
    state.activeRequestController?.abort();
    state.activeRequestController = null;
    if (state.recorder && state.recorder.state !== 'inactive') {
      try { state.recorder.stop(); } catch (_) {}
    }
    state.recorder = null;
    state.currentSegment = null;
    state.pendingRequests = [];
    state.chunks = [];
    state.requestRunning = false;
    stopTracks();
  }

  function showRetry(message) {
    state.panel.classList.remove('is-recording');
    state.panel.innerHTML = '<p class="song-result">' + message + '</p><button id="retrySing" class="sing-again" type="button">Subukan muli</button>';
    state.panel.querySelector('#retrySing').onclick = () => reference(state.panel);
  }

  function failAttempt(message) {
    state.cancelled = true;
    state.transcriptionFailed = state.transcriptionFailed || new Error(message);
    clearTimers();
    const recorder = state.recorder;
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== 'inactive') {
        try { recorder.stop(); } catch (_) {}
      }
    }
    cleanup();
    state.finalizing = false;
    showRetry(message);
  }

  function fatalRecorderError() {
    if (state.finalizing) return;
    failAttempt('Hindi maipagpatuloy ang pag-record. Subukan muli.');
  }

  function isOversizedAudioError(error) {
    const message = String(error?.message || error || '').toLowerCase();
    return /sync input too long|input too long|audio longer than\s*1\s*min|too long.*audio|http\s*400.*(?:sync|audio|input)/i.test(message);
  }

  function enqueue(blob, sequence) {
    console.log('[Lesson1] segment enqueued', {
      sequence, size: blob.size, type: blob.type,
    });
    // Lesson 1 Gawain 1 stores the segment locally for review; it is not transcribed.
  }

  function diagnoseBlobDuration(blob, segment) {
    return new Promise(resolve => {
      let objectUrl = '';
      let settled = false;
      let timeoutId = null;
      let audio = null;
      const finish = () => {
        if (settled) return;
        settled = true;
        if (timeoutId) clearTimeout(timeoutId);
        if (audio) {
          audio.onloadedmetadata = null;
          audio.onerror = null;
        }
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        resolve();
      };
      try {
        audio = document.createElement('audio');
        objectUrl = URL.createObjectURL(blob);
        audio.preload = 'metadata';
        audio.onloadedmetadata = () => {
          console.log('[Lesson1] blob media metadata', {
            sequence: segment.sequence,
            recorderDurationSec: ((segment.endedAt - segment.startedAt) / 1000).toFixed(2),
            mediaDurationSec: audio.duration,
            blobSize: blob.size,
            mimeType: blob.type,
          });
          finish();
        };
        audio.onerror = () => {
          console.warn('[Lesson1] blob media metadata unavailable', {
            sequence: segment.sequence, blobSize: blob.size, mimeType: blob.type,
          });
          finish();
        };
        timeoutId = setTimeout(() => {
          console.warn('[Lesson1] blob media metadata timed out', {
            sequence: segment.sequence, blobSize: blob.size, mimeType: blob.type,
          });
          finish();
        }, 2000);
        audio.src = objectUrl;
        audio.load();
      } catch (error) {
        console.warn('[Lesson1] blob media metadata diagnostic failed', {
          sequence: segment.sequence, error,
        });
        finish();
      }
    });
  }

  function finalizeSegment(segment) {
    if (segment.finalized) {
      console.warn('[Lesson1] duplicate segment finalization ignored', segment.sequence);
      return;
    }
    segment.finalized = true;
    segment.endedAt = Date.now();
    const duration = segment.endedAt - segment.startedAt;
    let blob;
    try {
      blob = new Blob(segment.parts, { type: segment.mimeType });
      if (!blob.size) throw new Error('Empty recording segment');
    } catch (error) {
      console.error('[Lesson1] segment rejected', {
        reason: 'blob_creation_failed', duration, parts: segment.parts.length,
        mimeType: segment.mimeType, error,
      });
      state.failedChunk = error;
      failAttempt('Hindi maipagpatuloy ang pag-record. Subukan muli.');
      return;
    }
    segment.sequence = state.chunkSequence++;
    segment.enqueued = true;
    state.recordingParts.push(blob);
    state.finalizedSequences.add(segment.sequence);
    console.log('[Lesson1] segment finalized', {
      sequence: segment.sequence,
      durationMs: segment.endedAt - segment.startedAt,
      durationSec: ((segment.endedAt - segment.startedAt) / 1000).toFixed(2),
      blobSize: blob.size,
      mimeType: blob.type,
    });
    enqueue(blob, segment.sequence);
    diagnoseBlobDuration(blob, segment);
  }

  function stopSegment(segment, reason) {
    if (!segment) return Promise.resolve();
    if (segment.stopPromise) return segment.stopPromise;
    segment.stopPromise = new Promise(resolve => { segment.resolveStop = resolve; });
    segment.stopReason = reason;
    if (state.rotationTimer) clearTimeout(state.rotationTimer);
    state.rotationTimer = null;
    if (segment.recorder.state === 'inactive') {
      if (segment.finalized) {
        segment.resolveStop?.();
        segment.resolveStop = null;
      }
      return segment.stopPromise;
    }
    segment.stopRequested = true;
    console.log('[Lesson1] segment explicitly stopped', {
      reason, sequence: segment.sequence, startedAt: segment.startedAt,
    });
    try {
      segment.recorder.stop();
    } catch (error) {
      state.failedChunk = error;
      console.error('[Lesson1] segment rejected', { reason: 'recorder_stop_failed', error });
      failAttempt('Hindi maipagpatuloy ang pag-record. Subukan muli.');
      segment.resolveStop?.();
      segment.resolveStop = null;
    }
    return segment.stopPromise;
  }

  function rotateRecorder() {
    if (state.cancelled || state.finalizing || !state.stream) return;
    const selectedMime = state.mimeType || mimeType();
    let recorder;
    try {
      recorder = new MediaRecorder(state.stream, selectedMime ? { mimeType: selectedMime } : undefined);
    } catch (error) {
      state.failedChunk = error;
      fatalRecorderError();
      return;
    }
    const segment = {
      recorder, parts: [], mimeType: recorder.mimeType || selectedMime || 'audio/webm',
      startedAt: 0, endedAt: 0, sequence: null, finalized: false, enqueued: false,
      stopRequested: false, stopPromise: null, resolveStop: null, stopReason: '',
    };
    state.recorder = recorder;
    state.currentSegment = segment;
    state.mimeType = segment.mimeType;
    console.log('[Lesson1] segment created', { mimeType: segment.mimeType });
    recorder.ondataavailable = event => {
      if (event.data?.size) {
        segment.parts.push(event.data);
        console.log('[Lesson1] segment dataavailable', {
          sequence: segment.sequence, dataChunks: segment.parts.length, size: event.data.size,
        });
      }
    };
    recorder.onstop = () => {
      if (state.recorder === recorder) state.recorder = null;
      console.log('[Lesson1] segment stop event', {
        sequence: segment.sequence, dataChunks: segment.parts.length,
        stopReason: segment.stopReason,
      });
      console.log('[Lesson1] segment final dataavailable received', {
        sequence: segment.sequence, dataChunks: segment.parts.length,
      });
      finalizeSegment(segment);
      if (state.currentSegment === segment) state.currentSegment = null;
      segment.resolveStop?.();
      segment.resolveStop = null;
      if (segment.enqueued) console.log('[Lesson1] segment finalized/enqueued once', { sequence: segment.sequence });
      if (!state.cancelled && !state.finalizing) rotateRecorder();
    };
    recorder.onerror = event => {
      if (!state.finalizing) {
        state.failedChunk = event.error || new Error('Recorder error');
        console.error('[Lesson1] segment rejected', { reason: 'recorder_error', error: state.failedChunk });
        fatalRecorderError();
      }
    };
    try {
      recorder.start();
      segment.startedAt = Date.now();
      console.log('[Lesson1] segment started', {
        startedAt: segment.startedAt, mimeType: segment.mimeType,
      });
    } catch (error) {
      state.failedChunk = error;
      console.error('[Lesson1] segment rejected', { reason: 'recorder_start_failed', error });
      fatalRecorderError();
      return;
    }
    state.rotationTimer = setTimeout(() => {
      if (state.recorder !== recorder || recorder.state !== 'recording') return;
      console.log('[Lesson1] segment reached rotation point', {
        startedAt: segment.startedAt, requestedAt: Date.now(),
      });
      stopSegment(segment, 'rotation');
    }, CHUNK_MS);
  }

  /* Legacy chunk transcription/evaluation helpers are disabled for this activity.
  function retryChunk(item) {
    console.warn('[Lesson1] segment retried', {
      sequence: item.sequence, retry: item.retries + 1, size: item.blob.size,
    });
    const timer = setTimeout(() => {
      state.retryTimers.delete(timer);
      state.pendingRequests.unshift(item);
      drainQueue();
    }, Math.min(4000, 800 * (item.retries + 1)));
    state.retryTimers.add(timer);
  }

  async function transcribe(item) {
    console.log('[Lesson1] transcription started', {
      sequence: item.sequence, size: item.blob.size, type: item.blob.type,
    });
    const form = new FormData();
    form.append('audio', item.blob, 'lesson1-singalong-' + item.sequence + '.webm');
    form.append('target_text', CANONICAL_TEXT);
    form.append('language', 'Filipino');
    form.append('mode', 'sentence');
    form.append('activity_key', 'lesson-1-gawain-1');
    const controller = new AbortController();
    state.activeRequestController = controller;
    state.requestTimer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch('/api/reading/lesson-1-gawain-1/transcribe/', {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf() },
        body: form, signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok || !result.success) {
        const error = new Error(result.error || 'Hindi naproseso ang audio.');
        error.status = response.status;
        throw error;
      }
      const transcript = String(result.raw_transcript || result.transcript || '').trim();
      if (!transcript) throw new Error('Hindi naproseso ang audio.');
      state.transcripts.set(item.sequence, transcript);
      console.log('[Lesson1] segment transcribed', { sequence: item.sequence });
    } finally {
      clearTimeout(state.requestTimer);
      state.requestTimer = null;
      if (state.activeRequestController === controller) state.activeRequestController = null;
    }
  }

  async function drainQueue() {
    if (state.requestRunning || state.cancelled) return;
    const item = state.pendingRequests.shift() || state.chunks.shift();
    if (!item) return;
    state.requestRunning = true;
    try {
      await transcribe(item);
    } catch (error) {
      console.error('[Lesson1] transcription failed', { sequence: item.sequence, error });
      if (isOversizedAudioError(error)) {
        state.failedChunk = error;
        state.transcriptionFailed = error;
        console.error('[Lesson1] segment rejected', {
          reason: 'oversized_audio', sequence: item.sequence, size: item.blob.size, error,
        });
        failAttempt('Hindi naproseso ang audio. Subukan muli.');
      } else if (!state.cancelled && item.retries < MAX_CHUNK_RETRIES) {
        item.retries += 1;
        retryChunk(item);
      } else {
        state.failedChunk = error;
        state.transcriptionFailed = error;
        if (!state.finalizing && !state.cancelled) fatalRecorderError();
      }
    } finally {
      state.requestRunning = false;
      drainQueue();
      maybeFinish();
    }
  }

  */
  function flushRecorder() {
    return stopSegment(state.currentSegment, 'finalization');
  }

  function variants(target) { return VARIANTS[target] || [tokens(target)]; }

  function mergedTokens() {
    const all = [...state.transcripts.entries()].sort((a, b) => a[0] - b[0]).map(x => tokens(x[1]));
    const result = [];
    all.forEach(chunk => {
      let overlap = 0;
      for (let size = Math.min(3, result.length, chunk.length); size > 0; size -= 1) {
        if (result.slice(-size).join(' ') === chunk.slice(0, size).join(' ')) { overlap = size; break; }
      }
      result.push(...chunk.slice(overlap));
    });
    return result;
  }

  function findLyricLine(expected, spoken, start) {
    const expectedTokens = tokens(expected);
    for (let lineStart = start; lineStart < spoken.length; lineStart += 1) {
      if (!tokenMatches(expectedTokens[0], spoken[lineStart])) continue;
      let spokenIndex = lineStart + 1;
      let matched = true;
      for (const expectedToken of expectedTokens.slice(1)) {
        while (spokenIndex < spoken.length && !tokenMatches(expectedToken, spoken[spokenIndex])) {
          spokenIndex += 1;
        }
        if (spokenIndex >= spoken.length) {
          matched = false;
          break;
        }
        spokenIndex += 1;
      }
      if (matched) return spokenIndex;
    }
    return -1;
  }

  function match() {
    const spoken = mergedTokens();
    let cursor = 0;
    const detected = [];
    TARGETS.forEach(target => {
      const nextCursor = findLyricLine(target, spoken, cursor);
      if (nextCursor >= 0) {
        detected.push(target);
        cursor = nextCursor;
      }
    });
    const undetected = TARGETS.filter(target => !detected.includes(target));
    return {
      detected, undetected, matched: detected.length, total: TOTAL,
      passed: detected.length >= MIN_MATCHED && detected.length / TOTAL >= MIN_RATIO,
      transcript: mergedTokens().join(' '),
    };
  }

  function saveFinal(result) {
    return fetch(progressUrl(), {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({
        activity_key: ACTIVITY_KEY, total_items: TOTAL,
        current_index: result.passed ? TOTAL : 1,
        completed_items: result.passed ? TOTAL : 1,
        correct_items: result.passed ? TOTAL : result.matched, activity_completed: result.passed,
        state: {
          singing_attempts: state.attempt, canonical_text: CANONICAL_TEXT,
          transcript: result.transcript, detected_targets: result.detected,
          undetected_targets: result.undetected, matched: result.matched, total: result.total,
        },
      }),
    }).then(async response => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) throw new Error('save');
      return payload;
    });
  }

  /* Legacy transcription/scoring completion is intentionally unreachable for this recording activity. */
  function maybeFinish() {
    return;
    /*
    if (!state.finalizing || state.requestRunning || state.pendingRequests.length ||
        state.chunks.length || state.retryTimers.size) return;
    if (state.failedChunk || state.transcriptionFailed || !state.finalizedSequences.size ||
        state.transcripts.size !== state.finalizedSequences.size ||
        [...state.finalizedSequences].some(sequence => !state.transcripts.has(sequence))) {
      console.warn('[Lesson1] scoring skipped because transcription failed');
      state.finalizing = false;
      showRetry('Hindi naproseso ang isang audio chunk. Subukan muli.');
      return;
    }
    console.log('[Lesson1] scoring started', {
      transcriptCount: state.transcripts.size,
      transcriptSequences: [...state.transcripts.keys()].sort((a, b) => a - b),
    });
    const result = match();
    saveFinal(result).then(() => {
      cleanup();
      state.finalizing = false;
      if (result.passed) {
        state.panel.innerHTML = '<p class="song-kicker">Mahusay!</p><h2>Natapos ang pag-awit.</h2><p class="song-result">Nakita ang ' + result.matched + ' sa ' + result.total + ' target.</p>';
        document.getElementById('completion')?.classList.add('show');
      } else {
        state.panel.innerHTML = '<p class="song-kicker">Handa na ang resulta.</p><p class="song-result">Nakita ang ' + result.matched + ' sa ' + result.total + ' target.</p><p class="song-note">Subukan muli ang pag-awit upang makumpleto ang gawain.</p><button id="retrySing" class="sing-again" type="button">Ulitin ang Pag-record</button>';
        state.panel.querySelector('#retrySing').onclick = () => reference(state.panel);
      }
    }).catch(() => {
      cleanup();
      state.finalizing = false;
      showRetry('Hindi na-save ang resulta. Subukan muli.');
    });
    */
  }

  async function finalize() {
    if (state.finalizing || state.cancelled) return;
    state.finalizing = true;
    state.panel.classList.remove('is-recording');
    state.panel.innerHTML = '<p class="song-kicker">Inaayos ang iyong recording…</p><p class="song-note">Sandali lamang.</p><button id="stopSing" class="sing-stop" type="button" disabled>Inaayos ang recording…</button>';
    clearTimers();
    try {
      await flushRecorder();
    } catch (error) {
      state.failedChunk = error;
      cleanup();
      state.finalizing = false;
      showRetry('Hindi natapos ang pag-record. Subukan muli.');
      return;
    }
    stopTracks();
    cleanup();
    state.finalizing = false;
    if (!state.recordingParts.length) { showRetry('Walang na-record na audio. Subukan muli.'); return; }
    state.recordingBlob = new Blob(state.recordingParts, { type: state.recordingParts[0].type || 'audio/webm' });
    if (state.recordingUrl) URL.revokeObjectURL(state.recordingUrl);
    state.recordingUrl = URL.createObjectURL(state.recordingBlob);
    state.panel.innerHTML = '<p class="song-kicker">Pakinggan muna</p><h2>Na-record na ang iyong pag-awit.</h2><audio class="review-audio" controls preload="metadata" src="' + state.recordingUrl + '" style="width:100%;max-width:300px"></audio><div class="review-actions"><button id="retrySing" class="sing-again" type="button">ULITIN ANG PAG-RECORD</button><button id="submitSing" class="sing-done" type="button">ISUMITE ANG PAG-AWIT</button></div><p class="song-note" data-submit-error hidden></p>';
    state.panel.querySelector('audio').onerror = () => { const error = state.panel.querySelector('[data-submit-error]'); error.hidden = false; error.textContent = 'Hindi mabuksan ang recording. Maaari kang mag-record muli.'; };
    state.panel.querySelector('#retrySing').onclick = () => { URL.revokeObjectURL(state.recordingUrl); state.recordingUrl = ''; state.recordingBlob = null; reference(state.panel); };
    state.panel.querySelector('#submitSing').onclick = submitRecording;
  }

  async function submitRecording() {
    const button = state.panel.querySelector('#submitSing');
    const error = state.panel.querySelector('[data-submit-error]');
    if (!state.recordingBlob || button.disabled) return;
    button.disabled = true;
    const form = new FormData(); form.append('audio', state.recordingBlob, 'lesson-1-gawain-1.webm');
    try {
      const response = await fetch(data().submission_url, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf() }, body: form });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success) throw new Error(result.error || 'Hindi naisumite ang recording.');
      state.panel.innerHTML = '<p class="song-kicker">Tapos na</p><h2>Naipasa na ang iyong pag-awit.</h2><p class="song-note">Makikinig ang iyong guro sa iyong recording.</p>';
    } catch (submissionError) { button.disabled = false; error.hidden = false; error.textContent = 'Hindi naisumite ang recording. Subukan muli.'; }
  }

  async function startRecording() {
    state.attempt += 1;
    state.cancelled = false; state.finalizing = false; state.failedChunk = null;
    state.chunkSequence = 0; state.chunks = []; state.pendingRequests = []; state.transcripts = new Map(); state.recordingParts = [];
    state.finalizedSequences = new Set(); state.transcriptionFailed = null;
    state.panel.innerHTML = '<p class="song-kicker">● Nagre-record...</p><p class="song-note">Umawit ayon sa awit. Maaari mong tapusin kapag handa ka na.</p><button id="stopSing" class="sing-stop" type="button">TAPUSIN ANG PAG-AWIT</button>';
    state.panel.classList.add('is-recording');
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Hindi available ang mikropono sa browser na ito.');
      state.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      rotateRecorder();
      if (state.cancelled || !state.recorder) return;
      state.panel.querySelector('#stopSing').onclick = finalize;
    } catch (error) {
      cleanup();
      state.panel.innerHTML = '<p class="song-result">' + (error.message || 'Hindi nakuha ang iyong boses.') + '</p><button id="retrySing" class="sing-again" type="button">Subukan muli</button>';
      state.panel.querySelector('#retrySing').onclick = () => reference(state.panel);
    }
  }

  function showPersistedActivityState(panel, payload = data()) {
    const progress = payload.progress || {};
    if (progress.activity_completed) {
      panel.innerHTML = '<p class="song-kicker">Tapos na</p><h2>Naipasa na ang iyong pag-awit.</h2><p class="song-note">Nasuri na ito ng iyong guro.</p>';
      document.getElementById('completion')?.classList.add('show');
      return true;
    }
    if (payload.submitted) {
      panel.innerHTML = '<p class="song-kicker">Naghihintay ng pagsusuri</p><h2>Naipasa na ang iyong pag-awit.</h2><p class="song-note">Hihintayin ang pagsusuri ng iyong guro.</p>';
      return true;
    }
    return false;
  }

  async function pollCompletionStatus() {
    if (!state.statusPollTimer || state.recorder?.state === 'recording' || state.finalizing) return;
    try {
      const response = await fetch(window.location.href, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'text/html' } });
      if (!response.ok) return;
      const html = await response.text();
      const documentCopy = new DOMParser().parseFromString(html, 'text/html');
      const payload = JSON.parse(documentCopy.getElementById('lesson-one-data')?.textContent || '{}');
      if (payload.progress?.activity_completed) {
        clearInterval(state.statusPollTimer);
        state.statusPollTimer = null;
        clearWelcomeAudio();
        cleanup();
        showPersistedActivityState(state.panel, payload);
      }
    } catch (_) {
      // A temporary status-request failure is non-disruptive; the next poll retries.
    }
  }

  function startCompletionStatusPolling() {
    if (state.statusPollTimer) return;
    state.statusPollTimer = setInterval(pollCompletionStatus, 4000);
  }

  function reference(panel) {
    state.panel = panel;
    panel.classList.remove('is-recording');
    panel.innerHTML = '<p class="song-kicker">AWIT NG ALPABETO</p><h2>Makinig at awitin ang Alpabeto ng Filipino</h2><a class="youtube-link" href="' + SONG_URL + '" target="_blank" rel="noopener noreferrer">▶ Panonoorin ang Awit sa YouTube ↗</a><p class="song-note">Magbubukas ang opisyal na video sa bagong tab.</p><div class="song-divider"></div><button id="ready" class="sing-done" type="button">Handa na akong umawit</button>';
    panel.querySelector('.youtube-link').addEventListener('click', () => {
      state.youtubeOpened = true;
    }, { once: true });
    setSongPanelControlsEnabled(panel, true);
    panel.querySelector('#ready').onclick = () => {
      if (!state.songPanelNarrationFinished || !state.youtubeReturned) {
        showSongGateFeedback();
        return;
      }
      panel.innerHTML = '<p class="song-kicker">AWITIN ANG ALPABETO</p><h2>Sabayan ang awit at awitin ang Alpabetong Pilipino.</h2><p class="song-note">Handa ka na ba?</p><button id="startSing" class="sing-done" type="button">MAGSIMULA</button>';
      panel.querySelector('#startSing').onclick = startRecording;
    };
  }

  function init() {
    const shell = document.querySelector('.shell');
    const backLink = document.querySelector('.back');
    if (shell && backLink) shell.prepend(backLink);
    document.querySelectorAll('.shell > .instruction').forEach(element => element.remove());
    installRecordingStyles();
    const layoutStyle = document.createElement('style');
    layoutStyle.textContent = '@media (min-width:761px) { .page { height:100dvh; overflow:hidden; } .shell { height:calc(100dvh - 70px); padding:7px; gap:3px 14px; overflow:hidden; grid-template-rows:auto auto auto minmax(0,1fr); } .shell > .back { grid-column:1/-1; grid-row:1; justify-self:start; margin:0; } .title { font-size:clamp(1.1rem,2.2vh,1.55rem); } .song-panel,.board { grid-row:4; min-height:0; } .song-panel { padding:9px; } .song-panel h2 { font-size:clamp(.9rem,2vh,1.2rem); } .song-panel p { font-size:clamp(.6rem,1.1vh,.7rem); } .lesson-one-page .youtube-link,.lesson-one-page .sing-done { width:fit-content; min-height:42px; max-width:240px; margin-top:8px; padding:8px 12px; font-family:inherit; font-size:.75rem; font-weight:1000; line-height:1.15; } .lesson-one-page .sing-stop,.lesson-one-page .sing-again { width:fit-content; max-width:190px; margin-top:6px; padding:6px 9px; font-family:inherit; font-size:.56rem; font-weight:1000; line-height:1.1; } .board { height:auto; gap:6px; padding:3px 1px; overflow:auto; } .tile { min-height:76px; padding:6px 4px; border-radius:12px; } .tile-letter { font-size:clamp(1.15rem,2.2vw,1.7rem); } .tile img { width:min(78%,54px); height:50px; margin:1px auto 0; } }';
    document.head.appendChild(layoutStyle);
    renderBoard();
    const panel = renderPanel();
    if (!panel) return;
    state.attempt = Number(saved().singing_attempts || 0);
    const persisted = showPersistedActivityState(panel);
    if (!persisted) {
      reference(panel);
      showWelcomeModal();
    }
    if (!data().progress?.activity_completed) startCompletionStatusPolling();
    document.getElementById('done')?.addEventListener('click', () => {
      window.location.href = document.querySelector('.back')?.href || '/';
    });
    window.addEventListener('beforeunload', () => {
      clearWelcomeAudio();
      if (state.statusPollTimer) clearInterval(state.statusPollTimer);
      state.statusPollTimer = null;
      cleanup();
    }, { once: true });
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') markSongPanelHidden();
      else handleSongPanelReturn();
    });
    window.addEventListener('blur', markSongPanelHidden);
    window.addEventListener('focus', handleSongPanelReturn);
  }

  document.addEventListener('DOMContentLoaded', init, { once: true });
})();
