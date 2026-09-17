(function () {
  'use strict';

  window.mountLesson3RhymeActivity = function (config) {
    const pairs = config.pairs;
    const game = document.getElementById(config.mount || 'game');
    const storageKey = config.storageKey;
    const imageBase = config.imageBase;
    let pairIndex = Math.max(0, Math.min(pairs.length, Number(localStorage.getItem(storageKey) || 0)));
    let wordIndex = 0;
    let readAttempts = [0, 0];
    let listenAttempts = [0, 0];
    let answerAttempts = 0;
    let answerPhase = false;
    let recording = false;
    let generation = 0;
    let audio = null;
    let audioUrl = null;
    let cueBusy = false;

    const normalize = value => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z]/g, '');
    const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';

    function stopAudio() {
      if (audio) audio.pause();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audio = null;
      audioUrl = null;
    }

    async function speak(text) {
      stopAudio();
      const response = await fetch(config.readAloudUrl, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf()},
        body: new URLSearchParams({target_text: text, language: 'Filipino', mode: 'word'})
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.audio_content) throw new Error(data.error || 'TTS unavailable');
      audioUrl = URL.createObjectURL(new Blob([Uint8Array.from(atob(data.audio_content), char => char.charCodeAt(0))], {type: data.mime_type || 'audio/mpeg'}));
      audio = new Audio(audioUrl);
      await new Promise((resolve, reject) => { audio.onended = resolve; audio.onerror = reject; audio.play().catch(reject); });
    }

    async function activateAndCue() {
      if (pairIndex >= pairs.length || answerPhase) return;
      cueBusy = true;
      const currentGeneration = generation;
      const instruction = game.querySelector('.instruction');
      const active = game.querySelector('.word.active');
      if (!active) {
        game.querySelectorAll('.word').forEach(card => card.classList.remove('active'));
        game.querySelectorAll('.word')[wordIndex]?.classList.add('active');
      }
      const cue = game.querySelector('.audio-cue');
      cue?.classList.add('active-audio');
      try {
        if (instruction?.dataset.initialCue === '0') await speak(instruction.textContent.trim());
        if (currentGeneration === generation) await speak('Sabihin ito.');
      } catch (error) { console.error('Lesson 3 Gawain 2 TTS failed', error); }
      cue?.classList.remove('active-audio');
      cueBusy = false;
      const button = document.getElementById('read');
      if (button) button.disabled = false;
    }

    function render(message) {
      generation += 1;
      stopAudio();
      if (pairIndex >= pairs.length) {
        localStorage.removeItem(storageKey);
        game.innerHTML = `<div class="complete"><h2>Magaling! Natapos mo ang gawain!</h2><p>Mahusay! Maaari ka nang magpatuloy.</p><a class="exit" href="${config.exitUrl}">Bumalik</a></div>`;
        return;
      }
      const pair = pairs[pairIndex];
      const words = [pair.a, pair.b];
      const inactive = !answerPhase && wordIndex === 0 && readAttempts[0] === 0 && listenAttempts[0] === 0 && pairIndex === 0;
      game.innerHTML = `<header class="header"><div class="brand"><h1>Salitang Magkatugma</h1><p>Lesson 3 · Gawain 2</p></div><div class="progress">Pares ${pairIndex + 1} / ${pairs.length}<div class="segments">${pairs.map((_, index) => `<i class="${index < pairIndex ? 'done ' : ''}${index === pairIndex ? 'active' : ''}"></i>`).join('')}</div></div></header><div class="instruction">${answerPhase ? 'Magkatugma ba ang dalawang salita?' : 'Basahin ang dalawang salita, pagkatapos ay maging Sound Detective!'}</div><div class="pairs">${words.map((word, index) => `<div class="word ${!inactive && !answerPhase && index === wordIndex ? 'active' : ''}"><img src="${imageBase}${word.toLowerCase()}.png" alt="${word}"><strong>${word}</strong></div>`).join('')}</div><div id="status" class="status">${message || (answerPhase ? 'Piliin ang tamang sagot.' : `Sabihin ang pangalan ng larawan.`)}</div>${answerPhase ? '<div class="answers"><button class="answer" data-v="yes">✓<small>MAGKATUGMA</small></button><button class="answer" data-v="no">✕<small>HINDI MAGKATUGMA</small></button></div>' : '<button id="read" class="read" disabled>🎙 Sabihin ngayon</button><button id="listen" class="listen" hidden>🔊 Pakinggan</button>'}`;
      if (answerPhase) document.querySelectorAll('.answer').forEach(button => button.onclick = () => answer(button.dataset.v));
      else {
        document.getElementById('read').onclick = record;
        document.getElementById('listen').onclick = async () => { if (cueBusy) return; listenAttempts[wordIndex] += 1; await speak(words[wordIndex]); if (listenAttempts[wordIndex] >= 3) document.getElementById('listen').hidden = true; };
        if (inactive) {
          const instruction = game.querySelector('.instruction');
          instruction.dataset.initialCue = '0';
          setTimeout(() => activateAndCue(), 0);
        } else { game.querySelector('.instruction').dataset.initialCue = '1'; setTimeout(() => activateAndCue(), 0); }
      }
    }

    async function record() {
      if (recording || cueBusy) return;
      const currentGeneration = generation;
      const word = pairs[pairIndex][wordIndex ? 'b' : 'a'];
      const read = document.getElementById('read');
      const status = document.getElementById('status');
      recording = true; read.disabled = true; read.textContent = '🎙️ Nakikinig…';
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const chunks = [], recorder = new MediaRecorder(stream);
        recorder.ondataavailable = event => event.data.size && chunks.push(event.data);
        const done = new Promise(resolve => recorder.onstop = () => resolve(new Blob(chunks, {type: recorder.mimeType || 'audio/webm'})));
        recorder.start(); setTimeout(() => recorder.state === 'recording' && recorder.stop(), 3500);
        const form = new FormData(); form.append('audio', await done, 'rhyme.webm'); form.append('target_text', word); form.append('language', 'Filipino'); form.append('mode', 'reading');
        const result = await (await fetch(config.transcribeUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form})).json();
        if (currentGeneration !== generation) return;
        if (result.success && normalize(result.transcript).includes(normalize(word))) {
          if (wordIndex === 0) { await speak('Magaling! Susunod na larawan.'); wordIndex = 1; render(); }
          else { answerPhase = true; render(); }
        } else {
          readAttempts[wordIndex] += 1; status.textContent = 'Hindi ito ang tamang sagot. Subukan natin muli.'; status.classList.add('warning'); read.disabled = false; read.textContent = '🎙 Sabihin ngayon';
          try { await speak('Hindi ito ang tamang sagot. Subukan natin muli.'); } catch (error) { console.error('Lesson 3 Gawain 2 retry TTS failed', error); }
          if (readAttempts[wordIndex] >= 3) document.getElementById('listen').hidden = false;
        }
      } catch (error) { if (currentGeneration === generation) { status.textContent = 'Hindi nakuha ang iyong boses. Subukan muli.'; read.disabled = false; read.textContent = '🎙 Sabihin ngayon'; } }
      finally { stream?.getTracks().forEach(track => track.stop()); recording = false; }
    }

    function answer(value) {
      if (value === (pairs[pairIndex].yes ? 'yes' : 'no')) { const pair = pairs[pairIndex]; pairIndex += 1; localStorage.setItem(storageKey, String(pairIndex)); wordIndex = 0; readAttempts = [0, 0]; listenAttempts = [0, 0]; answerAttempts = 0; answerPhase = false; render(`Tama! Ang ${pair.a} at ${pair.b} ay ${pair.yes ? 'magkatugma' : 'hindi magkatugma'}.`); }
      else { answerAttempts += 1; render(answerAttempts >= 3 ? 'Subukan muli. Basahin ulit ang dalawang salita.' : `Hindi pa. Subukan muli. (${answerAttempts}/3)`); if (answerAttempts >= 3) answerAttempts = 0; }
    }

    render();
  };
}());
