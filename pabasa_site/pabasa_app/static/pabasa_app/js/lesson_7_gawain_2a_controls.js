document.addEventListener('DOMContentLoaded', function () {
  const app = document.getElementById('app');
  if (!app) return;
  const activityData = JSON.parse(document.getElementById('activity-data')?.textContent || '{}');
  const oralState = activityData.progress?.state || {};

  let introKey = '';
  let introPlaying = false;
  let narrationToken = 0;
  let readStarted = false;
  let readingBeforeRead = null;
  let feedbackBusy = false;
  let previousReadingStatus = '';
  let part2InstructionBusy = false;
  let part2InstructionPlayed = false;
  let part2FeedbackBusy = false;
  const part2Instruction = 'Isulat ang i sa kahon ng bagay na nagsisimula sa i.';
  const part2InvalidFeedback = 'May mga larawan na nagsisimula sa /i/. Isulat ang i sa tamang kahon, pagkatapos ay isumite muli.';
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  const wordAudioFiles = {
    ilaw: 'ilaw.mp3', itlog: 'itlog.mp3', isa: 'isa.mp3',
    bahay: 'bahay.mp3', bola: 'bola.mp3', suklay: 'suklay.mp3'
  };
  const wordAudioBase = '/static/pabasa_app/prescribed/audio/SESSION%203/LESSON%207/GAWAIN%202A/';
  let narrationQueue = Promise.resolve();
  const playAudio = text => fetch('/api/reading/read-aloud/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'X-CSRFToken': csrf()},
    body: new URLSearchParams({target_text: text, language: 'Filipino', mode: 'reading', prescribed_activity_key: 'lesson7-gawain2a'})
  }).then(response => response.ok ? response.json() : null).then(result => new Promise(resolve => {
    if (!result?.success || !result.audio_content) { resolve(); return; }
    const audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
    let settled = false;
    const finish = () => { if (settled) return; settled = true; audio.onended = null; audio.onerror = null; audio.onabort = null; resolve(); };
    audio.onended = finish;
    audio.onerror = finish;
    audio.onabort = finish;
    Promise.resolve(audio.play()).catch(finish);
  }));
  const requestAudio = text => {
    const next = narrationQueue.then(() => playAudio(text));
    narrationQueue = next.catch(error => console.error('Lesson 7 Gawain 2A narration failed', error));
    return next.catch(error => console.error('Lesson 7 Gawain 2A narration failed', error));
  };
  const buttons = () => [...app.querySelectorAll('.lesson7-g2a-reading-actions button')];
  const setButtonsDisabled = disabled => buttons().forEach(button => { button.disabled = disabled; });
  window.lesson7G2ARecord = async function (event) {
    const read = this;
    const reading = read.closest('.reading');
    readStarted = true;
    readingBeforeRead = reading;
    const itemIndex = Number(oralState.current_reading_item || 0);
    const item = activityData.items?.[itemIndex];
    if (!item) return;
    const result = await window.Basahin.read({target_text: item.word, language: 'Filipino', mode: 'reading', prescribed_activity_key: 'lesson7-gawain2a'}, {
      button: read,
      onVad: state => {
        const listen = reading?.querySelector('#listen');
        if (listen) listen.disabled = state !== 'idle';
      }
    });
    const listen = reading?.querySelector('#listen');
    if (listen) listen.disabled = false;
    if (!result.success || result.complete === false) {
      const status = reading?.querySelector('#status');
      if (status) {
        status.textContent = 'Subukan muli. Sabihin ang salita nang malinaw.';
        showFeedback(status, 'Subukan Muli', '');
      }
      return;
    }
    oralState.completed_reading_items = [...(oralState.completed_reading_items || []), itemIndex];
    oralState.current_reading_item = itemIndex + 1;
    if (itemIndex >= (activityData.items?.length || 1) - 1) {
      oralState.oral_reading_completed = true;
      oralState.current_phase = 'main_activity';
    }
    oralState.state_version = Number(oralState.state_version || 0) + 1;
    await fetch(activityData.progress_url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify({state: oralState})});
    window.lesson7G2ARender?.(oralState);
  };
  const part2Canvases = () => [...app.querySelectorAll('.grid canvas.canvas')];
  const part2ActionButtons = () => [...app.querySelectorAll('.actions button')];
  const setPart2CanvasDisabled = disabled => part2Canvases().forEach(canvas => {
    canvas.classList.toggle('is-disabled', disabled);
    canvas.setAttribute('aria-disabled', String(disabled));
    if (disabled) canvas.setAttribute('tabindex', '-1');
    else canvas.removeAttribute('tabindex');
  });
  const setPart2ActionButtonsDisabled = disabled => part2ActionButtons().forEach(button => { button.disabled = disabled; });

  const narratePart2 = (text, type) => {
    setPart2CanvasDisabled(true);
    setPart2ActionButtonsDisabled(true);
    if (type === 'instruction') part2InstructionBusy = true;
    else {
      part2FeedbackBusy = true;
    }
    requestAudio(text).finally(() => {
      if (type === 'instruction') {
        part2InstructionBusy = false;
        part2InstructionPlayed = true;
      } else {
        part2FeedbackBusy = false;
      }
      setPart2ActionButtonsDisabled(false);
      setPart2CanvasDisabled(false);
    });
  };

  const syncPart2 = () => {
    const grid = app.querySelector('.grid');
    if (!grid) return;
    const instruction = app.querySelector('.instruction');
    if (instruction && instruction.textContent.trim() !== part2Instruction) instruction.textContent = part2Instruction;
    if (!part2InstructionPlayed && !part2InstructionBusy && !feedbackBusy) narratePart2(part2Instruction, 'instruction');
    const status = app.querySelector('#status');
    if (status && status.textContent.trim() === part2InvalidFeedback && !part2FeedbackBusy) narratePart2(part2InvalidFeedback, 'feedback');
  };

  const bindReading = reading => {
    const read = reading.querySelector('#read');
    if (!read) return;
    const instruction = app.querySelector('.instruction');
    if (instruction && instruction.textContent !== 'Tingnan ang larawang nasa ibaba. Ano ito?') instruction.textContent = 'Tingnan ang larawang nasa ibaba. Ano ito?';
    let actions = reading.querySelector('.lesson7-g2a-reading-actions');
    let listen = reading.querySelector('#listen');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'lesson7-g2a-reading-actions';
      read.parentNode.insertBefore(actions, read);
      actions.append(read);
    }
    if (!listen) {
      listen = document.createElement('button');
      listen.type = 'button';
      listen.id = 'listen';
      listen.textContent = 'Pakinggan';
      actions.append(listen);
      listen.addEventListener('click', async () => {
        if (listen.disabled) return;
        const word = reading.querySelector('img')?.alt?.replace(/^Larawan:\s*/i, '').trim();
        if (!word) return;
        const audioFile = wordAudioFiles[word.toLowerCase()];
        if (!audioFile) return;
        setButtonsDisabled(true);
        listen.classList.add('is-speaking');
        try {
          const audio = new Audio(wordAudioBase + encodeURIComponent(audioFile));
          await new Promise(resolve => {
            audio.onended = resolve;
            audio.onerror = resolve;
            audio.play().catch(resolve);
          });
        }
        finally { listen.classList.remove('is-speaking'); setButtonsDisabled(false); }
      });
    }
    const itemKey = reading.querySelector('img')?.getAttribute('alt') || reading;
    const isCompletedReadingTransition = readStarted && reading !== readingBeforeRead;
    if (introKey !== itemKey && !feedbackBusy && !isCompletedReadingTransition) {
      introKey = itemKey;
      const token = ++narrationToken;
      introPlaying = true;
      setButtonsDisabled(true);
      (async () => {
        await requestAudio('Tukuyin ang larawan');
        if (token !== narrationToken || reading !== app.querySelector('.reading')) return;
        await requestAudio('Tingnan ang larawang nasa ibaba. Ano ito?');
      })().catch(() => {}).finally(() => {
        if (token !== narrationToken || reading !== app.querySelector('.reading')) return;
        introPlaying = false;
        setButtonsDisabled(false);
      });
    }
    if (!feedbackBusy && readStarted && reading !== readingBeforeRead) {
      const status = reading.querySelector('#status');
      const currentStatus = status?.textContent.trim() || '';
      if (currentStatus.startsWith('Larawan ') && currentStatus !== previousReadingStatus) {
        readStarted = false;
        readingBeforeRead = null;
        showFeedback(status, 'Magaling', currentStatus);
      }
      previousReadingStatus = currentStatus;
    }
    const status = reading.querySelector('#status');
    if (status && /^Larawan \d+/.test(status.textContent.trim())) status.style.visibility = '';
    if (status && /^Subukan muli\. Sabihin ang salita nang malinaw\.$/i.test(status.textContent.trim()) && status.dataset.g2aFeedback !== 'wrong') {
      showFeedback(status, 'Subukan Muli', '');
    }
  };

  const showFeedback = (status, text, restoreText) => {
    if (!status || feedbackBusy) return;
    feedbackBusy = true;
    status.dataset.g2aFeedback = text;
    status.textContent = text;
    status.style.visibility = 'hidden';
    setButtonsDisabled(true);
    requestAudio(text).finally(() => {
      if (status.isConnected && status.dataset.g2aFeedback === text && restoreText) status.textContent = restoreText;
      if (status.isConnected) delete status.dataset.g2aFeedback;
      feedbackBusy = false;
      if (!introPlaying) setButtonsDisabled(false);
      sync();
    });
  };

  const sync = () => {
    if (!window.__lessonStartReady) return;
    const reading = app.querySelector('.reading');
    if (reading) {
      bindReading(reading);
    } else if (!feedbackBusy && readStarted) {
      const status = app.querySelector('#status');
      if (status) {
        readStarted = false;
        readingBeforeRead = null;
        showFeedback(status, 'Magaling', status.textContent.trim());
      }
    }
    syncPart2();
  };
  sync();
  new MutationObserver(sync).observe(app, {childList: true, subtree: true, characterData: true});
});
