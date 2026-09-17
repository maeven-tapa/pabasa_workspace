(function () {
  'use strict';
  window.salitangDedicatedFlow = true;
  const stage = document.getElementById('stage');
  if (!stage) return;
  const phase2Text = 'Magkatunog ba ang dalawang larawan na ito? Pindutin ang nawawastong sagot.';
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  let audio = null;
  let runId = 0;
  let lastKey = '';
  let phase2Narrated = '';
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
    if (busy) return;
    const answers = stage.querySelector('#answers:not([hidden])');
    const prompt = stage.querySelector('.prompt');
    if (answers) {
      if (prompt) prompt.textContent = phase2Text;
      const phase2Key = stage.querySelector('.progress')?.textContent || '';
      if (phase2Narrated !== phase2Key) {
        phase2Narrated = phase2Key;
        busy = true;
        answers.querySelectorAll('button').forEach(button => { button.disabled = true; });
        try { await speak(phase2Text); }
        catch (error) { console.error('Salitang Magkatugma Phase 2 TTS failed', error); }
        finally {
          busy = false;
          answers.querySelectorAll('button').forEach(button => { button.disabled = false; });
        }
      }
      return;
    }
    phase2Narrated = '';
    const pair = stage.querySelector('.pair');
    const active = stage.querySelector('.word.active');
    const read = stage.querySelector('#read');
    const progress = stage.querySelector('.progress')?.textContent || '';
    const target = active?.querySelector('img')?.getAttribute('alt') || '';
    const key = progress + '|' + target;
    if (!pair || !prompt || !read || !target || key === lastKey) return;
    const firstForPair = !lastKey || !lastKey.startsWith(progress + '|');
    lastKey = key;
    busy = true;
    pair.classList.add('naming-phase');
    pair.querySelectorAll('.word').forEach(card => card.classList.remove('active'));
    read.disabled = true;
    try {
      await speak(firstForPair ? prompt.textContent.trim() : 'Magaling! Susunod na larawan.');
      pair.querySelectorAll('.word').forEach(card => {
        if (card.querySelector('img')?.getAttribute('alt') === target) card.classList.add('active');
      });
      await speak('Sabihin ito.');
    } catch (error) {
      console.error('Salitang Magkatugma guided TTS failed', error);
      pair.querySelectorAll('.word').forEach(card => {
        if (card.querySelector('img')?.getAttribute('alt') === target) card.classList.add('active');
      });
    } finally {
      busy = false;
      if (stage.contains(read)) read.disabled = false;
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
    listen.dataset.listenCount = String(Number(listen.dataset.listenCount || 0) + 1);
    listen.disabled = true;
    try { await speak(word); }
    catch (error) { console.error('Salitang Magkatugma Pakinggan TTS failed', error); }
    finally {
      listen.disabled = false;
      listen.dataset.apiBusy = '0';
      if (Number(listen.dataset.listenCount) >= 3) {
        listen.hidden = true;
        const read = stage.querySelector('#read');
        if (read) { read.hidden = false; read.disabled = false; read.textContent = 'Basahin ngayon'; }
      }
    }
  }, true);
  setTimeout(sync, 80);
}());
