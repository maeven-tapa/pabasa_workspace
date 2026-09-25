(() => {
  if (window.__lesson7RecognitionFeedbackFetch) return;
  window.__lesson7RecognitionFeedbackFetch = true;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const request = nativeFetch(input, init);
    if (!String(input).includes('/api/reading/transcribe/')) return request;
    return request.then(response => {
      const nativeJson = response.json.bind(response);
      response.json = async () => {
        const data = await nativeJson();
        const target = document.querySelector('#app .item.active')?.getAttribute('aria-label') || '';
        const normalize = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
        const correct = data?.success && normalize(data.transcript).includes(normalize(target));
        window.__lesson7RecognitionFeedback = correct ? 'correct' : 'wrong';
        return data;
      };
      return response;
    });
  };
})();

document.addEventListener('DOMContentLoaded', function () {
  const app = document.getElementById('app');
  if (!app) return;

  app.addEventListener('click', event => {
    if (event.target.closest('#lesson7Start')) {
      app.dataset.lesson7IntroComplete = '1';
      transitionToken += 1;
    }
  }, true);

  let narratedStatus = null;
  let transitionToken = 0;
  let feedbackToken = 0;
  const controls = () => [app.querySelector('#read'), app.querySelector('#aloud'), ...app.querySelectorAll('.choice')].filter(Boolean);
  const lockControls = disabled => controls().forEach(button => { button.disabled = disabled; });
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';

  const narrateFeedback = text => {
    const requestToken = ++feedbackToken;
    return fetch('/api/reading/read-aloud/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': csrf(),
      },
      body: new URLSearchParams({
        target_text: text,
        language: 'Filipino',
        mode: 'reading',
        prescribed_activity_key: 'lesson-7-gawain-1',
      }),
    })
      .then(response => response.ok ? response.json() : null)
      .then(result => new Promise(resolve => {
        if (requestToken !== feedbackToken || !result?.success || !result.audio_content) {
          resolve();
          return;
        }
        const audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
        audio.onended = resolve;
        audio.onerror = resolve;
        audio.play().catch(resolve);
      }))
      .catch(error => console.error('Lesson 7 Gawain 1 feedback narration failed', error));
  };

  const setFeedbackDisabled = disabled => app.querySelectorAll('#read,#aloud,.choice').forEach(button => {
    if (disabled) {
      button.dataset.feedbackWasDisabled = button.disabled ? '1' : '0';
      button.disabled = true;
    } else if (button.dataset.feedbackWasDisabled) {
      button.disabled = button.dataset.feedbackWasDisabled === '1';
      delete button.dataset.feedbackWasDisabled;
    }
  });

  const showFeedback = (status, text, restoreText) => {
    if (!status || status.dataset.feedbackText === text) return;
    status.dataset.feedbackText = text;
    status.textContent = text;
    setFeedbackDisabled(true);
    narrateFeedback(text).finally(() => {
      if (status.isConnected && status.dataset.feedbackText === text) {
        if (restoreText) status.textContent = restoreText;
        delete status.dataset.feedbackText;
      }
      setFeedbackDisabled(false);
    });
  };

  const playWordAudio = async listen => {
    const word = app.querySelector('.item.active')?.getAttribute('aria-label');
    if (!word || listen.disabled) return;
    listen.disabled = true;
    const listens = Number(listen.dataset.listens || 0) + 1;
    listen.dataset.listens = String(listens);
    try {
      const audioFilename = {
        aso: 'aso.mp3',
        'ilang-ilang': 'ilang-ilang.mp3',
        ilaw: 'ilaw.mp3',
        ilong: 'ilong.mp3',
        ipis: 'ipis.mp3',
        isa: 'isa.mp3',
        itlog: 'itlog.mp3',
        saging: 'saging.mp3',
      }[String(word).trim().toLowerCase()];
      if (!audioFilename) throw new Error(`No prescribed audio found for ${word}`);
      const audio = new Audio(`/static/pabasa_app/prescribed/audio/SESSION%203/LESSON%207/GAWAIN%201/${encodeURIComponent(audioFilename)}`);
      await new Promise(resolve => {
        audio.onended = resolve;
        audio.onerror = resolve;
        audio.play().catch(resolve);
      });
    } catch (error) {
      console.error('Lesson 7 Gawain 1 word narration failed', error);
    } finally {
      listen.disabled = false;
    }
  };

  const bindListenButton = listen => {
    if (!listen) return;
    if (listen.textContent !== 'Pakinggan') listen.textContent = 'Pakinggan';
    if (listen.dataset.prescribedTts === '1') return;
    listen.dataset.prescribedTts = '1';
    listen.onclick = event => {
      event.preventDefault();
      playWordAudio(listen);
    };
  };

  const startItemTransition = () => {
    if (!app.dataset.lesson7IntroComplete && (app.querySelector('.lesson7-overview') || (app.querySelector('.head h1')?.textContent.trim() === 'Letrang Ii' && app.querySelector('.head>b')?.textContent.trim().startsWith('1 /')))) return;
    const wheel = app.querySelector('.wheel');
    const activeImage = wheel?.querySelector('.item.active img');
    const host = wheel?.parentElement;
    if (!wheel || !activeImage || !host) return;
    const focusOnly = app.querySelector('.choices');
    if (focusOnly) {
      let focusPicture = host.querySelector('.lesson7-focus-picture');
      if (!focusPicture) {
        focusPicture = document.createElement('img');
        focusPicture.className = 'lesson7-focus-picture';
        host.append(focusPicture);
      }
      focusPicture.src = activeImage.src;
      focusPicture.alt = activeImage.alt;
      wheel.classList.add('is-focus-only');
      focusPicture.classList.add('is-visible');
      return;
    }
    const itemKey = wheel.querySelector('.item.active')?.getAttribute('aria-label') || activeImage.src;
    if (host.dataset.transitionItem === itemKey) return;
    host.dataset.transitionItem = itemKey;
    const token = ++transitionToken;
    let focusPicture = host.querySelector('.lesson7-focus-picture');
    if (!focusPicture) {
      focusPicture = document.createElement('img');
      focusPicture.className = 'lesson7-focus-picture';
      focusPicture.alt = activeImage.alt;
      host.append(focusPicture);
    }
    focusPicture.src = activeImage.src;
    focusPicture.alt = activeImage.alt;
    focusPicture.classList.remove('is-visible');
    wheel.classList.remove('is-fading-out');
    window.setTimeout(() => {
      if (token !== transitionToken || !wheel.isConnected) return;
      wheel.classList.add('is-fading-out');
      window.setTimeout(() => {
        if (token !== transitionToken || !wheel.isConnected) return;
        focusPicture.classList.add('is-visible');
      }, 180);
    }, 1400);
  };

  const syncReadControls = () => {
    const status = app.querySelector('#status');
    const listen = app.querySelector('#aloud');
    bindListenButton(listen);
    if (listen && status?.textContent.trim() === 'Ano ang nasa larawan?' && narratedStatus !== status) listen.hidden = false;
  };

  const narrateStatus = () => {
    if (!window.__lessonStartReady) return;
    const progressLabel = app.querySelector('.head>b')?.textContent.trim();
    if (!app.dataset.lesson7IntroComplete && progressLabel && !progressLabel.startsWith('1 /')) {
      app.dataset.lesson7IntroComplete = '1';
    }
    if (!app.dataset.lesson7IntroComplete || app.querySelector('.lesson7-overview')) return;
    const status = app.querySelector('#status');
    const statusText = status?.textContent.trim();
    if (!status || !['Ano ang nasa larawan?', 'Nagsisimula ba ang larawan sa tunog I?'].includes(statusText) || status === narratedStatus) return;

    narratedStatus = status;
    syncReadControls();
    lockControls(true);

    fetch('/api/reading/read-aloud/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': csrf(),
      },
      body: new URLSearchParams({
        target_text: statusText,
        language: 'Filipino',
        mode: 'reading',
        prescribed_activity_key: 'lesson-7-gawain-1',
      }),
    })
      .then(response => response.ok ? response.json() : null)
      .then(result => new Promise(resolve => {
        if (!result?.success || !result.audio_content) {
          resolve();
          return;
        }
        const audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
        audio.onended = resolve;
        audio.onerror = resolve;
        audio.play().catch(resolve);
      }))
      .catch(error => console.error('Lesson 7 Gawain 1 status narration failed', error))
      .finally(() => lockControls(false));
  };

  const sync = () => {
    if (!window.__lessonStartReady) return;
    syncReadControls();
    startItemTransition();
    const status = app.querySelector('#status');
    if (status) {
      if (app.querySelector('.choices') && status.textContent.trim() === 'Nagsisimula ba sa tunog /i/?') {
        status.textContent = 'Nagsisimula ba ang larawan sa tunog I?';
      }
      if (app.querySelector('.choices') && status.textContent.trim() === 'Nagsisimula ba ang larawan sa tunog I?') {
        status.closest('.controls')?.classList.add('lesson7-classify-ready');
      }
      const statusText = status.textContent.trim();
      if (/^Subukan muli\.!?(?: \(\d+\/3\))?$/i.test(statusText)) {
        showFeedback(status, 'Subukan muli!', '');
      } else if (window.__lesson7RecognitionFeedback === 'correct' && statusText !== 'Magaling!') {
        window.__lesson7RecognitionFeedback = null;
        showFeedback(status, 'Magaling!', statusText);
      }
    }
    narrateStatus();
  };

  sync();
  new MutationObserver(sync).observe(app, {childList: true, subtree: true, characterData: true});
});
