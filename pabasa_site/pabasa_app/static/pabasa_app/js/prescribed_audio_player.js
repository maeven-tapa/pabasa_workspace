(() => {
  'use strict';
  // Playback cancellation settles the caller even when loading or audio has
  // not ended. Each operation owns its Audio instance and temporary URL.
  window.PrescribedAudioPlayer = {
    create() {
      let generation = 0, operation = null;
      const cancelled = () => new DOMException('Activity audio cancelled.', 'AbortError');
      return {
        get generation() { return generation; },
        get playing() { return operation !== null; },
        isCurrent(token) { return token === generation; },
        cancel() {
          generation++;
          const previous = operation;
          operation = null;
          if (!previous) return false;
          previous.controller.abort();
          previous.reject(cancelled());
          previous.audio?.pause();
          return true;
        },
        async play(source) {
          if (operation) throw new Error('Activity audio is already playing.');
          const token = generation;
          const current = {controller:new AbortController(), audio:null, reject:null};
          const cancellation = new Promise((_, reject) => { current.reject = reject; });
          operation = current;
          let objectUrl = null;
          try {
            const loaded = await Promise.race([
              Promise.resolve().then(() => typeof source === 'function' ? source(current.controller.signal) : {url:source}),
              cancellation,
            ]);
            if (token !== generation) throw cancelled();
            const url = loaded.blob ? (objectUrl = URL.createObjectURL(loaded.blob)) : loaded.url;
            const audio = current.audio = new Audio(url);
            await Promise.race([
              new Promise((resolve, reject) => {
                audio.onended = resolve;
                audio.onerror = () => reject(new Error('Audio playback failed. Try again.'));
                audio.addEventListener('pause', () => reject(cancelled()), {once:true});
                audio.play().catch(reject);
              }),
              cancellation,
            ]);
            if (token !== generation) throw cancelled();
          } finally {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
            if (operation === current) operation = null;
          }
        },
        // Play a short sequence through one media element. Reusing the same
        // element keeps browser autoplay permission through instructional and
        // target-word prompts started by the same learner action.
        async playSequence(sources) {
          const list = Array.isArray(sources) ? sources.filter(Boolean) : [];
          if (!list.length) throw new Error('Could not find the audio for this activity.');
          if (operation) throw new Error('Activity audio is already playing.');
          const token = generation;
          const current = {controller:new AbortController(), audio:null, reject:null};
          const cancellation = new Promise((_, reject) => { current.reject = reject; });
          operation = current;
          try {
            const audio = current.audio = new Audio();
            for (const source of list) {
              if (token !== generation) throw cancelled();
              audio.src = source;
              audio.load?.();
              await Promise.race([
                new Promise((resolve, reject) => {
                  // A few Chromium builds can miss `ended` after replacing a
                  // media element's source. Do not leave the activity locked
                  // forever; the visible Listen control remains available.
                  const timeout = setTimeout(resolve, 8000);
                  audio.onended = resolve;
                  audio.onerror = () => { clearTimeout(timeout); reject(new Error('Audio playback failed. Try again.')); };
                  audio.addEventListener('pause', () => reject(cancelled()), {once:true});
                  audio.play().catch(reject);
                }),
                cancellation,
              ]);
            }
            if (token !== generation) throw cancelled();
          } finally {
            if (operation === current) operation = null;
          }
        },
      };
    },
  };
})();
