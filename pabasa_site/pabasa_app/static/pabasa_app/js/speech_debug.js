(() => {
  'use strict';

  if (!window.SpeechDebug) {
    const histories = new WeakMap();
    const format = data => {
      if (!data?.transcript) return '';
      const model = {chirp_2: 'Chirp 2', chirp_3: 'Chirp 3', stt_v1: 'STT v1', knowlez_stt: 'Knowlez STT'}[data.stt_model] || data.stt_model || 'Google STT';
      const language = data.language_code ? ` | Language: ${data.language_code}` : '';
      const fallback = data.stt_fallback_reason ? ` | Fallback: ${data.stt_fallback_reason}` : '';
      const raw = data.raw_transcript && data.raw_transcript !== data.transcript ? ` | Raw: ${data.raw_transcript}` : '';
      const stitching = data.syllable_stitching_applied
        ? ` | TASS: ${data.syllable_stitched_transcript}`
        : (data.syllable_context ? ` | TASS Context: ${data.syllable_context}` : '');
      const syllables = Number(data.target_syllable_count || 0) > 0
        ? ` | Syllables: ${Number(data.syllable_context_count || 0)}/${Number(data.target_syllable_count)}` : '';
      const wordValues = data.stt_model === 'chirp_2'
        ? ` | Word values (not true confidence): ${(data.stt_words || []).map(word =>
          `${word.word}: ${typeof word.confidence === 'number' ? word.confidence.toFixed(3) : 'unavailable'}`
        ).join(', ') || 'unavailable'}` : '';
      return `Model: ${model}${language}${fallback} | Words: ${data.transcript}${raw}${stitching}${syllables}${wordValues}`;
    };
    const panelFor = output => output.closest('aside');
    const setPanelValue = (panel, suffix, value) => {
      const node = panel?.querySelector(`[id$="-debug-${suffix}"]`);
      if (node) node.textContent = String(value ?? 'Not available');
    };
    const publish = data => {
      const line = format(data);
      document.querySelectorAll('[data-speech-debug-output]').forEach(output => {
        if (line) {
          const lines = [...(histories.get(output) || []), line].slice(-6);
          histories.set(output, lines);
          output.textContent = lines.join('\n');
        }
        const panel = panelFor(output);
        setPanelValue(panel, 'result', data.transcript ? `Transcript: ${data.transcript}${data.stt_model ? ` · Model: ${data.stt_model}` : ''}${data.language_code ? ` · ${data.language_code}` : ''}` : (data.error || 'No transcript returned'));
        setPanelValue(panel, 'error', data.success === false ? (data.error || 'Transcription failed') : '—');
        setPanelValue(panel, 'status', data.success === false ? 'STT failed' : (data.complete === true ? 'STT complete' : 'STT response received'));
        setPanelValue(panel, 'recorder', 'Inactive');
      });
    };
    window.addEventListener('basahin:state', event => {
      const detail = event.detail || {}, state = detail.state;
      document.querySelectorAll('[data-speech-debug-output]').forEach(output => {
        const panel = panelFor(output);
        if (state === 'interim') {
          setPanelValue(panel, 'status', 'Listening (provisional)');
          setPanelValue(panel, 'result', `Hearing: ${detail.transcript || ''}`);
          return;
        }
        if (state === 'level') {
          setPanelValue(panel, 'vad', detail.speaking ? 'Speaking' : (detail.calibrating ? 'Calibrating' : 'Quiet'));
          setPanelValue(panel, 'mic', 'Active · Unmuted');
          return;
        }
        const labels = {calibrating: 'Calibrating', waiting: 'Waiting for speech', listening: 'Listening', silence: 'Silence detected', processing: 'Processing speech', idle: 'Ready'};
        if (labels[state]) setPanelValue(panel, 'status', labels[state]);
        if (state === 'listening') setPanelValue(panel, 'recorder', 'Recording');
        if (state === 'processing' || state === 'idle') setPanelValue(panel, 'recorder', 'Inactive');
        if (state === 'idle') setPanelValue(panel, 'mic', 'Inactive · Unmuted');
      });
    });
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
        const transcription = /\/transcribe\/(?:[?#]|$)/.test(url);
        const workbook = /\/api\/dashboard\/assessment\/activity\/prescribed\/[^/]+\/progress\/(?:[?#]|$)/.test(url);
        const gawain1 = document.querySelector('[data-prescribed-session-controls]')?.dataset.prefix === 'prescribed-s7-l19-g1';
        if (transcription || (workbook && !gawain1)) response.clone().json().then(publish).catch(error => {
          document.querySelectorAll('[data-speech-debug-output]').forEach(output => {
            const panel = panelFor(output);
            setPanelValue(panel, 'status', 'Malformed STT response');
            setPanelValue(panel, 'error', error?.message || 'Unable to read transcription response');
            setPanelValue(panel, 'result', 'No valid reading result returned');
          });
        });
        return response;
      };
    };
    window.SpeechDebug = Object.freeze({format, observeTranscriptions});
  }

  // CRLA uses the formatter directly. Session panels opt into response history.
  if (document.querySelector('[data-speech-debug-output]')) window.SpeechDebug.observeTranscriptions();
})();
