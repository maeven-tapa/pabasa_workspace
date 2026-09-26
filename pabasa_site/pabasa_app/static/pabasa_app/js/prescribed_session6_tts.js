/* Google Filipino narration for Session 6, Lesson 17 at 18, Gawain 6–8. */
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
    ]);
    if (!supported.has(activity.activity_key)) return;

    const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
    const text = (selector) => app.querySelector(selector)?.textContent.trim() || '';
    const isGawain7 = activity.activity_key === 'lesson-17-18-gawain-7';
    const isGawain8 = activity.activity_key === 'lesson-17-18-gawain-8';
    const gawain8Root = '/static/pabasa_app/prescribed/audio/SESSION_6/LESSON_17_18/GAWAIN_8/';
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

    const playFile = async (filename) => {
      if (!filename) return;
      audio?.pause();
      const player = new Audio(gawain8Root + filename);
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

    const enqueueFiles = (filenames) => {
      queue = queue.then(async () => {
        for (const filename of filenames) await playFile(filename);
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
