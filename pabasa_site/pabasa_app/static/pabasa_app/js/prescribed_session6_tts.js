/* Google Filipino narration for Session 6, Lesson 17 at 18, Gawain 6–8. */
window.PrescribedSession6Gawain9Audio = (() => {
  const root = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_9/';
  const prompts = [
    'unang_larawan_pana_tts.mp3', 'ikalawang_larawan_pisara_tts.mp3',
    'ikatlong_larawan_palaka_tts.mp3', 'ika_apat_na_larawan_pito_tts.mp3',
    'ikalimang_larawan_regalo_tts.mp3',
  ];
  const words = {
    pana: 'pana_tts.mp3', pisara: 'pisara_tts.mp3', palaka: 'palaka_tts.mp3',
    pito: 'pito_tts.mp3', regalo: 'regalo_tts.mp3',
  };
  const feedback = {
    'Hindi pa. Subukan muli.': 'hindi_pa_tama_tts.mp3',
    'Subukan muli.': 'hindi_pa_tama_tts.mp3',
    'Pakinggan muna ang salita.': 'pakinggan_ang_salita_bago_basahin_tts.mp3',
    'Pakinggan muli ang salita.': 'pakinggan_ang_salita_bago_basahin_tts.mp3',
    'Subukan mong basahin ang salita.': 'subukan_mong_basahin_salita_tts.mp3',
    'Tama ang pagbasa! Isulat naman ang salita.': 'tama_pagbasa_isulat_salita_tts.mp3',
    'Tama! Magaling ang iyong sagot.': 'tama_magaling_ang_iyong_sagot_tts.mp3',
    'Magaling! Natapos mo ang gawain.': 'mahusay_ang_ginawa_mo_ngayon_natapos_aralin_tts.mp3',
  };
  let active = null;
  const play = async (filename) => {
    if (!filename) return;
    active?.pause();
    const player = new Audio(root + filename);
    active = player;
    await player.play();
    await new Promise((resolve) => {
      player.onended = resolve;
      player.onerror = resolve;
    });
    if (active === player) active = null;
  };
  const fileFor = (message) => {
    const prompt = String(message || '').match(/^Larawan\s+(\d+)\s+sa\s+5\./);
    if (prompt) return prompts[Number(prompt[1]) - 1];
    if (words[String(message || '').trim()]) return words[String(message || '').trim()];
    return feedback[message];
  };
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const body = init.body;
    const canReadFields = body && typeof body.get === 'function';
    const activityKey = canReadFields ? body.get('prescribed_activity_key') : '';
    const targetText = canReadFields ? (body.get('text') || body.get('target_text')) : '';
    const requestPath = new URL(input, window.location.href).pathname;
    if (activityKey === 'lesson-17-18-gawain-9' && requestPath.endsWith('/api/reading/read-aloud/')) {
      const filename = fileFor(targetText);
      if (filename) {
        const asset = await nativeFetch(root + filename);
        const bytes = new Uint8Array(await asset.arrayBuffer());
        let binary = '';
        for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        return new Response(JSON.stringify({success: true, audio_content: btoa(binary), mime_type: 'audio/mpeg', tts_language: 'fil-PH', voice_name: 'fil-PH-Wavenet-A'}), {headers: {'Content-Type': 'application/json'}});
      }
    }
    return nativeFetch(input, init);
  };
  return { play, prompt: (index) => play(prompts[index]), word: (value) => play(words[value]), feedback: (message) => play(feedback[message]) };
})();

(() => {
  'use strict';

  const boot = () => {
    const app = document.getElementById('app');
    const dataNode = document.getElementById('prescribed-activity-data');
    if (!app || !dataNode) return;

    let activity;
    try { activity = JSON.parse(dataNode.textContent || '{}'); } catch (_) { return; }
    const supported = new Set([
      'lesson-17-18-gawain-6', 'lesson-17-18-gawain-7', 'lesson-17-18-gawain-8',
      'lesson-17-18-gawain-9',
    ]);
    if (!supported.has(activity.activity_key)) return;

    const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
    const text = (selector) => app.querySelector(selector)?.textContent.trim() || '';
    const isGawain7 = activity.activity_key === 'lesson-17-18-gawain-7';
    const isGawain8 = activity.activity_key === 'lesson-17-18-gawain-8';
    const isGawain9 = activity.activity_key === 'lesson-17-18-gawain-9';
    if (isGawain9) return;
    const gawain7Root = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_7/';
    const gawain8Root = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_8/';
    const gawain7PromptParts = [
      ['basahin_muna_ang_mga_ngalan_tts.mp3', 'unang_salita_sa_lima.mp3', 'basahin_riles.mp3'],
      ['basahin_muna_ang_mga_ngalan_tts.mp3', 'ikalawang_salita_sa_lima.mp3', 'basahin_puso.mp3'],
      ['basahin_muna_ang_mga_ngalan_tts.mp3', 'ikatlong_salita_sa_lima.mp3', 'basahin_robot.mp3'],
      ['basahin_muna_ang_mga_ngalan_tts.mp3', 'ika_apat_na_salita_sa_lima.mp3', 'basahin_payong.mp3'],
      ['basahin_muna_ang_mga_ngalan_tts.mp3', 'ikalimang_salita_sa_lima.mp3', 'basahin_pitaka.mp3'],
    ];
    const gawain8Words = {
      palaka: 'salitang_babasahin_palaka_tts.mp3', peluka: 'salitang_babasahin_peluka_tts.mp3',
      palaro: 'salitang_babasahin_palaro_tts.mp3', palara: 'salitang_babasahin_palara_tts.mp3',
      resibo: 'salitang_babasahin_resibo_tts.mp3', resita: 'salitang_babasahin_resita_tts.mp3',
      pilay: 'salitang_babasahin_pilay_tts.mp3', palay: 'salitang_babasahin_palay_tts.mp3',
      bareta: 'salitang_babasahin_bareta_tts.mp3', balita: 'salitang_babasahin_balita_tts.mp3',
    };
    const gawain8Groups = [
      'unang_pangkat_sa_lima.mp3', 'ikalawang_pangkat_sa_lima.mp3',
      'ikatlong_pangkat_sa_lima.mp3', 'ika_apat_na_pangkat_sa_lima.mp3',
      'ikalimang_pangkat_sa_lima.mp3',
    ];
    const gawain8WordNumbers = [
      'unang_salit_sa_tatlo.mp3', 'ikalawang_salita_sa_tatlo.mp3',
      'ikatlong_salita_sa_tatlo.mp3',
    ];
    const gawain8Feedback = {
      'Tama ang pagbasa!': 'magaling_tama_ang_nabasa_mo_tts.mp3',
      'Hindi pa. Subukan muli.': 'hindi_pa_tama_tts.mp3',
      'Pakinggan muna ang salita.': 'pakinggan_muna_ang_salita_tts.mp3',
      'Subukan mong basahin ang salita.': 'subukan_mong_basahin_salita_tts.mp3',
      'Subukan muli.': 'hindi_pa_tama_tts.mp3',
      'Tama! Bilog ang salitang naiiba.': 'tama_nabilugan_mo_ang_salitang_naiiba_tts.mp3',
    };
    let audio = null;
    let lastStep = '';
    let lastFeedback = '';
    let queue = Promise.resolve();
    let firstOralStep = isGawain7;

    const showError = (message) => {
      const status = app.querySelector('#status');
      if (status) {
        status.textContent = message;
        status.className = 'status bad';
      }
      console.error('Prescribed Filipino TTS:', message);
    };

    const play = async (message) => {
      if (!message) return;
      if (!activity.read_aloud_url) {
        showError('Walang TTS address para sa gawaing ito.');
        return;
      }
      audio?.pause();
      const form = new URLSearchParams({
        target_text: message,
        language: 'Filipino',
        mode: 'reading',
        prescribed_activity_key: activity.activity_key,
      });
      const response = await fetch(activity.read_aloud_url, {
        method: 'POST', credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrf(),
        },
        body: form,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success || !result.audio_content) {
        throw new Error(result.error || 'Hindi available ang Filipino audio.');
      }
      const player = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`);
      audio = player;
      await player.play();
      await new Promise((resolve) => {
        player.onended = resolve;
        player.onerror = () => resolve();
      });
      if (audio === player) audio = null;
    };

    const playFile = async (filename, root = gawain8Root) => {
      if (!filename) return;
      audio?.pause();
      const player = new Audio(root + filename);
      audio = player;
      await player.play();
      await new Promise((resolve) => {
        player.onended = resolve;
        player.onerror = () => resolve();
      });
      if (audio === player) audio = null;
    };

    const enqueue = (message, delay = 0) => {
      queue = queue.then(async () => {
        if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
        await play(message);
      }).catch((error) => showError(error.message || 'Hindi available ang Filipino audio.'));
    };

    const enqueueFiles = (filenames, delay = 0, root = gawain8Root) => {
      queue = queue.then(async () => {
        if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
        for (const filename of filenames) await playFile(filename, root);
      }).catch((error) => showError(error.message || 'Hindi available ang Filipino audio.'));
    };

    const currentStep = () => {
      const instruction = text('.instruction');
      const hints = [...app.querySelectorAll('.hint')].map((node) => node.textContent.trim()).filter(Boolean);
      if (app.querySelector('#oral')) {
        const word = text('.word.active') || text('.word');
        return {
          key: `${isGawain8 ? text('.hint') : 'oral'}:${word}`,
          message: [instruction, ...hints, word && `Ang salitang babasahin ay ${word}.`].filter(Boolean).join(' '),
        };
      }
      if (app.querySelector('#answer')) {
        return {
          key: `written:${text('.partial')}`,
          message: [instruction, ...hints].filter(Boolean).join(' '),
        };
      }
      if (app.querySelector('.board')) {
        return { key: 'matching', message: [instruction, ...hints].filter(Boolean).join(' ') };
      }
      if (app.querySelector('[data-answer]')) {
        const choices = [...app.querySelectorAll('[data-answer]')].map((node) => node.textContent.trim()).join('|');
        return { key: `selection:${choices}`, message: [instruction, ...hints].filter(Boolean).join(' ') };
      }
      if (app.querySelector('#start')) return { key: 'intro', message: '' };
      return null;
    };

    const inspect = () => {
      const feedback = text('#status');
      const step = currentStep();
      const stepChanged = Boolean(step && step.key !== lastStep);
      const feedbackChanged = Boolean(feedback && feedback !== lastFeedback);
      if (feedbackChanged) lastFeedback = feedback;
      if (stepChanged) lastStep = step.key;

      if (isGawain7) {
        // The activity page already announces Gawain 7 feedback through the
        // read-aloud endpoint. Its local aliases cover those lines; this
        // mapping supplies only the ordered prompt clips and matching prompt.
        if (stepChanged && step) {
          const oralMatch = text('.hint').match(/Salita (\d+) sa 5/);
          if (oralMatch && app.querySelector('#oral')) {
            const prompt = gawain7PromptParts[Number(oralMatch[1]) - 1];
            if (prompt) enqueueFiles(prompt, 3000, gawain7Root);
          } else if (app.querySelector('.board')) {
            enqueueFiles(['ngayon_ikabit_ang_bawat_larawan_sa_tamang_ngalan_tts.mp3'], 3000, gawain7Root);
          }
        }
        return;
      }

      if (isGawain8) {
        if (feedbackChanged) {
          const feedbackFile = gawain8Feedback[feedback]
            || (feedback === 'Pakinggan muli ang salita.' ? gawain8Feedback['Pakinggan muna ang salita.'] : '');
          if (feedbackFile) enqueueFiles([feedbackFile]);
        }
        if (stepChanged && step) {
          const hints = [...app.querySelectorAll('.hint')].map((node) => node.textContent.trim());
          const oralMatch = hints[0]?.match(/Pangkat (\d+) sa 5 · Salita (\d+) sa 3/);
          if (oralMatch && app.querySelector('#oral')) {
            const groupIndex = Number(oralMatch[1]) - 1;
            const wordIndex = Number(oralMatch[2]) - 1;
            const word = text('.word.active') || text('.word');
            enqueueFiles([
              'basahin_bilugan_naiiba_sa_pangkat_tts.mp3',
              gawain8Groups[groupIndex], gawain8WordNumbers[wordIndex], gawain8Words[word],
            ]);
          } else if (app.querySelector('[data-answer]')) {
            enqueueFiles(['basahin_bilugan_naiiba_sa_pangkat_tts.mp3']);
          }
        }
        return;
      }

      // Gawain 7 already narrates its own feedback in its existing activity flow.
      if (feedbackChanged && !isGawain7) enqueue(feedback);
      if (!stepChanged || !step?.message) return;

      // Gawain 7 still uses its established click-driven announcement for the
      // opening instruction.  Follow it with the actual first word instead of
      // silently skipping that item as the prior implementation did.
      const delay = isGawain7 && (feedbackChanged || firstOralStep) ? 3000 : 0;
      if (firstOralStep && step.key.startsWith('oral:')) firstOralStep = false;
      // Avoid overlapping Gawain 7's existing feedback audio with its next prompt.
      enqueue(step.message, delay);
    };

    new MutationObserver(inspect).observe(app, {
      childList: true, subtree: true, characterData: true,
    });
    inspect();
    addEventListener('pagehide', () => audio?.pause(), { once: true });
  };

  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
