(function () {
  'use strict';
  window.salitangDedicatedFlow = true;
  const stage = document.getElementById('stage');
  if (!stage) return;
  const phase2Text = 'Magkatunog ba ang dalawang larawan na ito? Pindutin ang nawawastong sagot.';
  const phase2ChoiceText = 'Piliin ang tamang kamay.';
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  let audio = null;
  let runId = 0;
  let lastKey = '';
  let phase2Narrated = '';
  let feedbackNarrationKey = '';
  let busy = false;
  let scheduled = false;

  async function speak(text) {
    const id = ++runId;
    if (audio) { audio.pause(); audio = null; }
    const response = await fetch(window.salitangTtsUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf()},
      body: new URLSearchParams({target_text: text, language: 'Filipino', mode: 'word'})
    });
    const data = await response.json();
    if (id !== runId || !response.ok || !data.success || !data.audio_content) return;
    audio = new Audio('data:' + (data.mime_type || 'audio/mpeg') + ';base64,' + data.audio_content);
    await new Promise((resolve, reject) => { audio.onended = resolve; audio.onerror = reject; audio.play().catch(reject); });
    if (id === runId) audio = null;
  }

  async function sync() {
    const status = stage.querySelector('#status');
    if (status?.classList.contains('warning')) {
      const feedback = 'Hindi pa ito tama. Subukan muli.';
      const rawFeedback = status.textContent.trim();
      const feedbackKey = rawFeedback === feedback
        ? status.dataset.feedbackNarrationKey || feedback
        : rawFeedback;
      status.dataset.feedbackNarrationKey = feedbackKey;
      if (status.textContent !== feedback) status.textContent = feedback;
      const answers = stage.querySelector('#answers:not([hidden])');
      if (!answers) {
        const read = stage.querySelector('#read');
        const listen = stage.querySelector('#listen');
        if (read) read.hidden = false;
        if (listen) listen.hidden = false;
      }
      if (busy) return;
      if (feedbackNarrationKey !== feedbackKey) {
        feedbackNarrationKey = feedbackKey;
        busy = true;
        stage.querySelectorAll('#read,#listen,#answers button').forEach(button => { button.disabled = true; });
        try { await speak(feedback); }
        catch (error) { console.error('Salitang Magkatugma retry feedback TTS failed', error); }
        finally {
          busy = false;
          stage.querySelectorAll('#read,#listen,#answers button').forEach(button => { button.disabled = false; });
          if (stage.querySelector('#status')?.classList.contains('warning')) sync();
        }
      }
      return;
    }
    if (busy) return;
    feedbackNarrationKey = '';
    const answers = stage.querySelector('#answers:not([hidden])');
    const prompt = stage.querySelector('.prompt');
    if (answers) {
      const read = stage.querySelector('#read');
      const listen = stage.querySelector('#listen');
      if (read) read.hidden = true;
      if (listen) { listen.hidden = true; listen.disabled = true; }
      if (prompt && prompt.textContent !== phase2Text) prompt.textContent = phase2Text;
      const phase2Key = document.getElementById('progress')?.textContent || '';
      if (phase2Narrated !== phase2Key) {
        phase2Narrated = phase2Key;
        busy = true;
        answers.querySelectorAll('button').forEach(button => { button.disabled = true; });
        try {
          await speak(phase2Text);
          await speak(phase2ChoiceText);
        }
        catch (error) { console.error('Salitang Magkatugma Phase 2 TTS failed', error); }
        finally {
          busy = false;
          answers.querySelectorAll('button').forEach(button => { button.disabled = false; });
          if (stage.querySelector('#status')?.classList.contains('warning')) sync();
        }
      }
      return;
    }
    phase2Narrated = '';
    const pair = stage.querySelector('.pair');
    const active = stage.querySelector('.word.active');
    const read = stage.querySelector('#read');
    const listen = stage.querySelector('#listen');
    const progress = document.getElementById('progress')?.textContent || '';
    const target = active?.querySelector('img')?.getAttribute('alt') || '';
    const key = progress + '|' + target;
    if (!pair || !prompt || !read || !listen || !target || key === lastKey) return;
    const firstForPair = !lastKey || !lastKey.startsWith(progress + '|');
    lastKey = key;
    busy = true;
    listen.hidden = false;
    listen.textContent = 'Pakinggan';
    pair.classList.add('naming-phase');
    pair.querySelectorAll('.word').forEach(card => card.classList.remove('active'));
    read.disabled = true;
    listen.disabled = true;
    try {
      if (!firstForPair && status) {
        status.textContent = 'Magaling! Susunod na larawan.';
        status.className = 'status correct';
      }
      await speak(firstForPair ? prompt.textContent.trim() : 'Magaling! Susunod na larawan.');
      pair.querySelectorAll('.word').forEach(card => {
        if (card.querySelector('img')?.getAttribute('alt') === target) card.classList.add('active');
      });
      await speak('Basahin ito.');
    } catch (error) {
      console.error('Salitang Magkatugma guided TTS failed', error);
      pair.querySelectorAll('.word').forEach(card => {
        if (card.querySelector('img')?.getAttribute('alt') === target) card.classList.add('active');
      });
    } finally {
      busy = false;
      if (stage.contains(read)) read.disabled = false;
      if (stage.contains(listen)) { listen.hidden = false; listen.disabled = false; listen.textContent = 'Pakinggan'; }
      if (stage.querySelector('#status')?.classList.contains('warning')) sync();
    }
  }

  new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => { scheduled = false; sync(); }, 0);
  }).observe(stage, {childList: true, subtree: true, characterData: true});
  document.addEventListener('click', async event => {
    const listen = event.target.closest('#listen');
    if (!listen) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (listen.dataset.apiBusy === '1') return;
    const word = stage.querySelector('.word.active img')?.getAttribute('alt');
    if (!word) return;
    listen.dataset.apiBusy = '1';
    listen.disabled = true;
    try { await speak(word); }
    catch (error) { console.error('Salitang Magkatugma Pakinggan TTS failed', error); }
    finally {
      listen.disabled = false;
      listen.dataset.apiBusy = '0';
      listen.hidden = Boolean(stage.querySelector('#answers:not([hidden])'));
    }
  }, true);
  setTimeout(sync, 80);
}());
