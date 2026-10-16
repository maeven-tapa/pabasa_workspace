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
              // A later clip may depend on a progress request made while the
              // intro is playing. Keep its result on the same media element.
              const url = typeof source === 'function'
                ? await Promise.race([Promise.resolve().then(() => source(current.controller.signal)), cancellation])
                : source;
              if (token !== generation) throw cancelled();
              if (!url) throw new Error('Could not find the audio for this activity.');
              audio.src = url;
              audio.load?.();
              await Promise.race([
                new Promise((resolve, reject) => {
                  let settled = false;
                  const finish = error => {
                    if (settled) return;
                    settled = true;
                    clearTimeout(timeout);
                    audio.onended = audio.onerror = null;
                    audio.removeEventListener('pause', onPause);
                    current.controller.signal.removeEventListener('abort', onAbort);
                    error ? reject(error) : resolve();
                  };
                  const onPause = () => {
                    // Native audio can emit pause just before ended when it
                    // naturally reaches the end. That completes this clip.
                    if (!audio.ended) finish(cancelled());
                  };
                  const onAbort = () => finish(cancelled());
                  // A timeout is an error; it must never skip the rest of an
                  // introduction and play the target word over it.
                  const timeout = setTimeout(() => finish(new Error('Audio playback timed out. Try again.')), 30000);
                  audio.onended = () => finish();
                  audio.onerror = () => finish(new Error('Audio playback failed. Try again.'));
                  audio.addEventListener('pause', onPause, {once:true});
                  current.controller.signal.addEventListener('abort', onAbort, {once:true});
                  audio.play().catch(finish);
                }),
                cancellation,
              ]);
            }
            if (token !== generation) throw cancelled();
          } finally {
            current.audio?.pause();
            if (operation === current) operation = null;
          }
        },
      };
    },
  };
})();
