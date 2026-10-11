(() => {
  'use strict';
  const promptUrl = new URL('../prescribed/audio/SESSION_10/LESSON_26/GAWAIN_2/Great! now let\'s read the rest of the sentence..mp3', document.currentScript.src).href;
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function markup(text, readWords = 0) {
    const words = String(text).trim().split(/\s+/);
    const spans = words.map((word, i) => `<span class="prescribed-reading-word ${i < readWords ? 'is-read' : 'is-unread'}" data-reading-word="${i}">${escape(word)}</span>`);
    return spans.slice(0, readWords).join(' ') + (readWords && readWords < words.length ? ' ' : '')
      + (readWords < words.length ? `<span class="prescribed-reading-unread">${spans.slice(readWords).join(' ')}</span>` : '');
  }
  function create({key, getState, save, url, onFeedback = () => {}, onRestore = () => {}}) {
    let reader = null, prompt = null, pending = null, saving = null, pendingCurrent = null, recovery = null;
    async function flush() {
      if (saving) return saving;
      if (!pending) return null;
      const payload = pending;
      saving = save(payload).then(result => {
        if (pending === payload) {
          pending = null;
          // The recording may have been canceled after its result was sent.
          // Preserve the saved result for resume rather than reviving that attempt.
          if (!pendingCurrent()) {recovery = result; onRestore(result);}
        }
        return result;
      });
      try { return await saving; } finally { saving = null; }
    }
    async function read(text, index, button, isCurrent) {
      const recovered = await flush();
      if (isCurrent()) recovery = null;
      // A previous clip may have completed the sentence despite a failed response.
      if (recovered?.accepted || !isCurrent()) return recovered;
      let result, failure;
      reader = window.Basahin.create({visualButton:button, url, continuous:true, silenceMs:3000,
        getFields:() => ({target_text:text, language:'English', mode:'sentence',
          prescribed_activity_key:key, current_syllable_index:Number(getState().sentence_syllable_index || 0)}),
        onResult(value) { if (!isCurrent()) return true; result = value; return true; },
        onError(error) { failure = error; },
      });
      const active = reader;
      try { await active.start(); } finally { active.destroy(); if (reader === active) reader = null; }
      if (!isCurrent()) return null;
      if (failure) throw failure;
      if (result?.success === false) throw new Error(result.error || 'Speech recognition failed. Please try again.');
      const heard = String(result?.raw_transcript || result?.transcript || '').trim();
      if (!heard) throw new Error('No speech detected. Please try again.');
      pending = {action:'sentence_continuation', item_index:index, heard, request_id:crypto.randomUUID()};
      pendingCurrent = isCurrent;
      const saved = await flush();
      if (isCurrent()) onFeedback(saved, heard);
      return {...saved, raw_transcript:heard};
    }
    async function playPrompt() {
      const audio = new Audio(promptUrl); prompt = audio;
      try {
        await new Promise((resolve, reject) => {
          audio.onended = resolve;
          audio.addEventListener('ended', resolve, {once:true});
          audio.addEventListener('pause', resolve, {once:true});
          audio.addEventListener('error', () => reject(new Error('Audio playback failed.')), {once:true});
          audio.play().catch(reject);
        });
      } finally { if (prompt === audio) prompt = null; }
    }
    async function restore(isCurrent = () => true) {
      await flush();
      if (!isCurrent()) return null;
      const result = recovery; recovery = null;
      return result;
    }
    return {read, flush, restore, playPrompt, cancel() { reader?.stop(); prompt?.pause(); }};
  }
  window.PrescribedSentenceReading = {markup, create};
})();
