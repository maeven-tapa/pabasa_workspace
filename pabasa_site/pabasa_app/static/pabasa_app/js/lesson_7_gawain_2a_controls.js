document.addEventListener('DOMContentLoaded', function () {
  const app = document.getElementById('app');
  if (!app) return;

  let introPlayed = false;
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
  const requestAudio = text => fetch('/api/reading/read-aloud/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'X-CSRFToken': csrf()},
    body: new URLSearchParams({target_text: text, language: 'Filipino', mode: 'reading', prescribed_activity_key: 'lesson7-gawain2a'})
  }).then(response => response.ok ? response.json() : null).then(result => new Promise(resolve => {
    if (!result?.success || !result.audio_content) { resolve(); return; }
    const audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
    audio.onended = resolve;
    audio.onerror = resolve;
    audio.play().catch(resolve);
  })).catch(error => console.error('Lesson 7 Gawain 2A narration failed', error));
  const buttons = () => [...app.querySelectorAll('.lesson7-g2a-reading-actions button')];
  const setButtonsDisabled = disabled => buttons().forEach(button => { button.disabled = disabled; });
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
    if (!part2InstructionPlayed && !part2InstructionBusy) narratePart2(part2Instruction, 'instruction');
    const status = app.querySelector('#status');
    if (status && status.textContent.trim() === part2InvalidFeedback && !part2FeedbackBusy) narratePart2(part2InvalidFeedback, 'feedback');
  };

  const bindReading = reading => {
    const read = reading.querySelector('#read');
    if (!read) return;
    const instruction = app.querySelector('.instruction');
    if (instruction && instruction.textContent !== 'Tingnan ang larawang nasa ibaba. Ano ito?') instruction.textContent = 'Tingnan ang larawang nasa ibaba. Ano ito?';
    if (read.textContent !== 'Simulan ang pagbasa') read.textContent = 'Simulan ang pagbasa';
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
        setButtonsDisabled(true);
        listen.classList.add('is-speaking');
        try { await requestAudio(word); }
        finally { listen.classList.remove('is-speaking'); setButtonsDisabled(false); }
      });
    }
    if (!read.dataset.g2aBound) {
      read.dataset.g2aBound = '1';
      read.addEventListener('click', () => { readStarted = true; readingBeforeRead = reading; }, true);
    }
    if (!introPlayed) {
      introPlayed = true;
      setButtonsDisabled(true);
      (async () => {
        await requestAudio('Tukuyin ang larawan');
        await requestAudio('Tingnan ang larawang nasa ibaba. Ano ito?');
        setButtonsDisabled(false);
      })().catch(() => setButtonsDisabled(false));
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
    if (status && /^Subukan muli\. Sabihin ang salita nang malinaw\.$/i.test(status.textContent.trim()) && status.dataset.g2aFeedback !== 'wrong') {
      showFeedback(status, 'Subukan Muli', '');
    }
  };

  const showFeedback = (status, text, restoreText) => {
    if (!status || feedbackBusy) return;
    feedbackBusy = true;
    status.dataset.g2aFeedback = text;
    status.textContent = text;
    setButtonsDisabled(true);
    requestAudio(text).finally(() => {
      if (status.isConnected && status.dataset.g2aFeedback === text && restoreText) status.textContent = restoreText;
      if (status.isConnected) delete status.dataset.g2aFeedback;
      feedbackBusy = false;
      setButtonsDisabled(false);
    });
  };

  const sync = () => {
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
