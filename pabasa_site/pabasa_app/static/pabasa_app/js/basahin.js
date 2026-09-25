/* Shared microphone capture and STT button. See docs/BASAHIN.md. */
(() => {
  'use strict';
  if (window.Basahin) return;

  const CHUNK_MS = 2400;
  const activeCaptures = new Set();
  const readers = new Set();
  const abortError = () => new DOMException('Reading cancelled.', 'AbortError');
  const emit = (state, detail = {}) => window.dispatchEvent(new CustomEvent('basahin:state', {detail: {state, ...detail}}));
  const noSpeechError = () => Object.assign(new Error('Walang narinig na boses. Pindutin ang Basahin upang subukan muli.'), {name: 'NoSpeechError'});

  // Same adaptive RMS threshold as the CRLA reader. Frame counting deliberately
  // uses hysteresis: quiet frames decrease evidence instead of resetting it.
  function createVad() {
    let floor = 0, frames = 0, heard = false, initialized = false;
    return {
      sample(rms, elapsedMs) {
        const calibrating = elapsedMs < 800;
        if (!initialized) { floor = rms; initialized = true; }
        else if (calibrating || rms < floor * 1.8) floor = floor * 0.94 + rms * 0.06;
        const threshold = Math.max(0.014, floor * 3.2 + 0.004);
        frames = !calibrating && rms > threshold ? Math.min(3, frames + 1) : Math.max(0, frames - 1);
        if (frames >= 3) heard = true;
        return {rms, threshold, calibrating, speaking: frames >= 3, heard};
      },
      takeSpeech() { const value = heard; heard = false; frames = 0; return value; },
    };
  }

  function mimeType() {
    return ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
      .find(type => window.MediaRecorder?.isTypeSupported?.(type)) || '';
  }

  async function openMicrophone(constraints = {audio: true}, {signal, timeoutMs = 15000} = {}) {
    let cancelled = false, rejectPending, timer;
    const pending = new Promise((_, reject) => { rejectPending = reject; });
    const cancel = () => { cancelled = true; rejectPending(abortError()); };
    activeCaptures.add(cancel);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Hindi available ang mikropono sa browser na ito.');
      if (signal?.aborted) throw abortError();
      signal?.addEventListener('abort', cancel, {once: true});
      timer = window.setTimeout(() => {
        cancelled = true;
        rejectPending(new Error('Hindi tumugon ang mikropono. Subukan muli.'));
      }, timeoutMs);
      const granted = navigator.mediaDevices.getUserMedia(constraints).then(stream => {
        if (cancelled) { stream.getTracks().forEach(track => track.stop()); throw abortError(); }
        return stream;
      });
      return await Promise.race([granted, pending]);
    } catch (error) {
      error.basahinCapture = true;
      throw error;
    } finally {
      window.clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
      activeCaptures.delete(cancel);
    }
  }

  /** Wait for voice activity, then record one independently decodable clip.
   * Capture releases tracks by default, including a supplied stream. Use
   * keepStream for a controller that reuses its stream across several clips.
   * No network, scoring, attempt counting, or DOM replacement happens here.
   */
  async function capture(options = {}) {
    const {signal, onRecorder, onState, stream: suppliedStream} = options;
    if (signal?.aborted) throw abortError();
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw Object.assign(new Error('Hindi available ang mikropono sa browser na ito.'), {basahinCapture: true});
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) throw Object.assign(new Error('Hindi available ang voice detection sa browser na ito.'), {basahinCapture: true});
    const controller = new AbortController();
    const cancel = () => controller.abort();
    signal?.addEventListener('abort', cancel, {once: true});
    activeCaptures.add(cancel);
    let stream, context, source, analyser, recorder, frame, timer;
    let ended = false, captured = false;
    const owned = !suppliedStream || !options.keepStream;
    let visualState;
    const setState = (state, detail) => {
      if (visualState === state) return;
      visualState = state;
      window.BasahinButton?.setState(options.button, state);
      onState?.(state, detail); emit(state, detail);
    };
    try {
      setState('calibrating');
      stream = suppliedStream || await openMicrophone({audio: {
        echoCancellation: true, noiseSuppression: false, autoGainControl: true,
        ...(options.deviceId ? {deviceId: {exact: options.deviceId}} : {}),
      }}, {signal: controller.signal});
      if (controller.signal.aborted) throw abortError();
      context = new AudioContext();
      if (context.state === 'suspended') await context.resume();
      if (controller.signal.aborted) throw abortError();
      source = context.createMediaStreamSource(stream);
      analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      const samples = new Uint8Array(analyser.fftSize), vad = options.vad || createVad();
      const started = options.startedAt ?? performance.now();
      vad.takeSpeech();
      const audio = await new Promise((resolve, reject) => {
        let settled = false, lastSpeechAt = -Infinity;
        const finish = (error, blob) => {
          if (settled) return;
          settled = true;
          controller.signal.removeEventListener('abort', abort);
          stream.getTracks().forEach(track => track.removeEventListener('ended', abort));
          error ? reject(error) : resolve(blob);
        };
        const abort = () => finish(abortError());
        controller.signal.addEventListener('abort', abort, {once: true});
        stream.getTracks().forEach(track => track.addEventListener('ended', abort, {once: true}));
        const recordChunk = () => {
          if (settled || recorder) return;
          window.clearTimeout(timer);
          try {
            const type = mimeType(), chunks = [];
            recorder = new window.MediaRecorder(stream, type ? {mimeType: type} : undefined);
            recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
            recorder.onerror = event => finish(event.error || new Error('Hindi naitala ang boses.'));
            recorder.onstop = () => {
              window.clearTimeout(timer);
              if (settled) return;
              const blob = new Blob(chunks, {type: recorder.mimeType || type || 'audio/webm'});
              vad.takeSpeech();
              finish(blob.size ? null : noSpeechError(), blob);
            };
            onRecorder?.(recorder);
            recorder.start();
            setState('listening');
            timer = window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, CHUNK_MS);
          } catch (error) { finish(error); }
        };
        const meter = () => {
          if (ended || settled) return;
          try {
            analyser.getByteTimeDomainData(samples);
            let sum = 0;
            for (const sample of samples) sum += ((sample - 128) / 128) ** 2;
            const now = performance.now();
            const level = vad.sample(Math.sqrt(sum / samples.length), now - started);
            if (level.speaking) {
              lastSpeechAt = now;
              recordChunk();
            }
            if (!recorder) setState(level.calibrating ? 'calibrating' : 'waiting');
            // CRLA holds its hearing indicator briefly between syllables.
            window.BasahinButton?.setSpeech(options.button, Boolean(recorder && now - lastSpeechAt < 240));
            onState?.('level', level); emit('level', level);
            if (!settled) frame = window.requestAnimationFrame(meter);
          } catch (error) { finish(error); }
        };
        if (controller.signal.aborted) abort();
        else {
          // Keep the microphone meter open, but create no recorder in silence.
          const waitMs = options.maxWaitMs ?? CHUNK_MS * (options.maxSilentChunks ?? 5);
          timer = window.setTimeout(() => {
            setState('silence', {waitMs});
            finish(noSpeechError());
          }, waitMs);
          meter();
        }
      });
      captured = true;
      return audio;
    } catch (error) {
      error.basahinCapture = true;
      throw error;
    } finally {
      ended = true;
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
      if (recorder) {
        recorder.ondataavailable = recorder.onstop = recorder.onerror = null;
        if (recorder.state !== 'inactive') { try { recorder.stop(); } catch (_) {} }
      }
      source?.disconnect();
      if (context) await context.close().catch(() => {});
      if (owned) stream?.getTracks().forEach(track => track.stop());
      signal?.removeEventListener('abort', cancel);
      activeCaptures.delete(cancel);
      window.BasahinButton?.setState(options.button, captured ? 'processing' : 'idle');
    }
  }

  async function transcribe(audio, fields, {url = '/api/reading/transcribe/', signal} = {}) {
    const form = new FormData();
    for (const [key, value] of Object.entries(fields)) {
      if (value !== undefined && value !== null) form.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
    }
    form.append('audio', audio, audio.type.includes('ogg') ? 'reading.ogg' : 'reading.webm');
    const csrf = decodeURIComponent(document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || '');
    let timedOut = false;
    const request = new AbortController(), cancel = () => request.abort();
    signal?.addEventListener('abort', cancel, {once: true});
    if (signal?.aborted) cancel();
    const timeout = window.setTimeout(() => { timedOut = true; cancel(); }, 35000);
    try {
      const response = await fetch(url, {method: 'POST', credentials: 'same-origin',
        headers: {'X-CSRFToken': csrf, Accept: 'application/json'}, body: form, signal: request.signal});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Hindi naproseso ang pagbasa.');
      return result;
    } catch (error) {
      if (timedOut && !signal?.aborted) throw Object.assign(new Error('Nagtagal ang pagproseso. Pindutin ang Basahin upang subukan muli.'), {name: 'TimeoutError'});
      throw error;
    } finally {
      window.clearTimeout(timeout);
      signal?.removeEventListener('abort', cancel);
    }
  }

  /** New UI binding: capture -> await STT -> callback -> next clip.
   * Return true from onResult to finish; otherwise result.complete controls it.
   * getFields is evaluated each clip to preserve the UI's reading cursor.
   */
  function create(options) {
    const {button, getFields, onResult, onError, onState} = options;
    const visualButton = options.visualButton || button;
    let current = null, destroyed = false;
    function state(name) {
      window.BasahinButton?.setState(visualButton, name);
      if (button) {
        const label = button.querySelector('[data-basahin-label]') || button;
        const text = (window.BasahinButton?.labelsFor?.(button) || {idle: 'Basahin', calibrating: 'Sandali...', waiting: 'Magsalita...', processing: 'Sinusuri...', listening: 'Nakikinig...'})[name];
        if (label.textContent !== text) label.textContent = text;
        button.disabled = name !== 'idle';
        button.setAttribute('aria-busy', String(name !== 'idle'));
      }
      onState?.(name);
    }
    async function start() {
      if (current || destroyed) return;
      const controller = new AbortController();
      let stream;
      current = controller;
      state('calibrating');
      try {
        stream = await openMicrophone({audio: {
          echoCancellation: true, noiseSuppression: false, autoGainControl: true,
          ...(options.deviceId ? {deviceId: {exact: options.deviceId}} : {}),
        }}, {signal: controller.signal});
        if (controller.signal.aborted) return;
        const vad = createVad(), startedAt = performance.now();
        for (let count = 0; count < (options.maxChunks ?? 25); count += 1) {
          const fields = {...getFields()};
          const blob = await capture({stream, button: visualButton, keepStream: true, signal: controller.signal, vad, startedAt,
            onState: (name, detail) => {
              options.onVad?.(name, detail);
              if (['calibrating', 'waiting', 'listening'].includes(name)) state(name);
            },
          });
          if (controller.signal.aborted) return;
          state('processing');
          const result = await (options.transcribe || transcribe)(blob, fields, {signal: controller.signal, url: options.url});
          if (controller.signal.aborted || current !== controller) return;
          const done = await onResult?.(result);
          if (controller.signal.aborted || (done ?? result.complete) || options.continuous === false) return;
          state('waiting');
        }
        throw new Error('Natapos ang oras ng pagbasa. Pindutin ang Basahin upang magpatuloy.');
      } catch (error) {
        if (!controller.signal.aborted && error.name !== 'AbortError') onError?.(error);
      } finally {
        stream?.getTracks().forEach(track => track.stop());
        if (current === controller) { current = null; if (!destroyed) state('idle'); }
      }
    }
    const reader = {
      start,
      stop() { current?.abort(); },
      destroy() { destroyed = true; current?.abort(); if (window.BasahinButton) window.BasahinButton.unbindActivity(button, start); else button?.removeEventListener('click', start); readers.delete(reader); },
    };
    if (window.BasahinButton) window.BasahinButton.bindActivity(button, start);
    else button?.addEventListener('click', start);
    state('idle');
    readers.add(reader);
    return reader;
  }

  // One scored attempt can span multiple clips (e.g. a sentence). Carry the
  // server's cursor/stitching context forward; never submit partial clips as
  // separate activity attempts. A real mismatch finishes the attempt.
  async function read(fields, options = {}) {
    if (options.button && fields.language) options.button.dataset.basahinLanguage = fields.language;
    let finalResult, failure;
    const nextFields = {...fields}, transcripts = [], rawTranscripts = [];
    const reader = create({
      ...options, button: undefined, visualButton: options.button, continuous: true,
      getFields: () => nextFields,
      onError: error => { failure = error; },
      onResult(result) {
        if (!String(result.transcript || '').trim()) throw noSpeechError();
        transcripts.push(result.transcript);
        rawTranscripts.push(result.raw_transcript ?? result.transcript);
        const previousCursor = Number(nextFields.current_syllable_index || 0);
        const progressed = Number(result.current_syllable_index || 0) > previousCursor;
        const stitching = result.syllable_context && result.syllable_context !== nextFields.syllable_context;
        nextFields.current_syllable_index = result.current_syllable_index || previousCursor;
        nextFields.syllable_context = result.syllable_context || '';
        if (result.word_results && nextFields.crla_sentence_word_scoring) nextFields.sentence_word_results = result.word_results;
        options.onProgress?.(result);
        if (options.continuous === false || result.complete || (!progressed && !stitching)) {
          finalResult = {...result, transcript: transcripts.join(' '), raw_transcript: rawTranscripts.join(' ')};
          return true;
        }
        return false;
      },
    });
    const cancel = () => reader.stop();
    options.signal?.addEventListener('abort', cancel, {once: true});
    try {
      if (options.signal?.aborted) throw abortError();
      await reader.start();
      if (failure) {
        if (/^en|english/i.test(fields.language || '')) {
          if (failure.name === 'NoSpeechError') failure.message = 'No speech detected. Press Read to try again.';
          if (failure.name === 'TimeoutError') failure.message = 'Speech processing timed out. Press Read to try again.';
        }
        throw failure;
      }
      if (!finalResult || options.signal?.aborted) throw abortError();
      return finalResult;
    } finally {
      options.signal?.removeEventListener('abort', cancel);
      reader.destroy();
    }
  }

  function cancelAll() { readers.forEach(reader => reader.stop()); activeCaptures.forEach(cancel => cancel()); }
  window.addEventListener('pagehide', cancelAll);
  const isCaptureError = error => Boolean(error?.basahinCapture || ['AbortError', 'NoSpeechError'].includes(error?.name));
  const bindActivity = (button, action) => window.BasahinButton.bindActivity(button, action);
  const getActivity = button => window.BasahinButton.getActivity(button);
  window.Basahin = Object.freeze({CHUNK_MS, createVad, openMicrophone, capture, transcribe, create, read, cancelAll, isCaptureError, bindActivity, getActivity});
})();
