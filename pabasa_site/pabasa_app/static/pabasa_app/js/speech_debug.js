(() => {
  'use strict';

  if (!window.SpeechDebug) {
    const histories = new WeakMap();
    const format = data => {
      if (!data?.transcript) return '';
      const model = {chirp_3: 'Chirp 3', stt_v1: 'STT v1'}[data.stt_model] || data.stt_model || 'Google STT';
      const language = data.language_code ? ` | Language: ${data.language_code}` : '';
      const fallback = data.stt_fallback_reason ? ` | Fallback: ${data.stt_fallback_reason}` : '';
      const raw = data.raw_transcript && data.raw_transcript !== data.transcript ? ` | Raw: ${data.raw_transcript}` : '';
      const stitching = data.syllable_stitching_applied
        ? ` | TASS: ${data.syllable_stitched_transcript}`
        : (data.syllable_context ? ` | TASS Context: ${data.syllable_context}` : '');
      const syllables = Number(data.target_syllable_count || 0) > 0
        ? ` | Syllables: ${Number(data.syllable_context_count || 0)}/${Number(data.target_syllable_count)}` : '';
      return `Model: ${model}${language}${fallback} | Words: ${data.transcript}${raw}${stitching}${syllables}`;
    };
    const publish = data => {
      const line = format(data);
      if (!line) return;
      document.querySelectorAll('[data-speech-debug-output]').forEach(output => {
        const lines = [...(histories.get(output) || []), line].slice(-6);
        histories.set(output, lines);
        output.textContent = lines.join('\n');
      });
    };
    let observing = false;
    const observeTranscriptions = () => {
      if (observing || !window.fetch) return;
      observing = true;
      const fetch = window.fetch.bind(window);
      // Older activities submit their own recordings; observe the response clone
      // so every session reports the same server details without consuming its body.
      window.fetch = async (...args) => {
        const response = await fetch(...args);
        const url = String(args[0]?.url || args[0] || '');
        if (response.ok && /\/transcribe\/(?:[?#]|$)/.test(url)) {
          response.clone().json().then(publish).catch(() => {});
        }
        return response;
      };
    };
    window.SpeechDebug = Object.freeze({format, observeTranscriptions});
  }

  // CRLA uses the formatter directly. Session panels opt into response history.
  if (document.querySelector('[data-speech-debug-output]')) window.SpeechDebug.observeTranscriptions();
})();
