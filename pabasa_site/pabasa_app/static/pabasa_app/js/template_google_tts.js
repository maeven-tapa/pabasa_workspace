/* Shared Google TTS client for the 15 teacher-created template activities. */
(() => {
  'use strict';

  let activeAudio = null;
  let activeUrl = '';
  let activeController = null;

  const csrfToken = () => document.cookie.split('; ')
    .find((value) => value.startsWith('csrftoken='))
    ?.split('=').slice(1).join('=') || '';

  const releaseAudio = () => {
    activeController?.abort();
    activeController = null;
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }
    activeAudio = null;
    if (activeUrl) URL.revokeObjectURL(activeUrl);
    activeUrl = '';
  };

  const blobFromBase64 = (value, type) => {
    const binary = atob(value || '');
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return new Blob([bytes], { type: type || 'audio/mpeg' });
  };

  async function speak({ materialId, text, profile = 'instruction', onStart, onEnd, onError } = {}) {
    const targetText = String(text || '').trim();
    if (!materialId || !targetText) return false;
    releaseAudio();
    const controller = new AbortController();
    activeController = controller;
    const form = new FormData();
    form.append('material_id', String(materialId));
    form.append('target_text', targetText);
    form.append('profile', profile);
    try {
      const response = await fetch('/api/template-activities/read-aloud/', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
        body: form, signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Audio is unavailable right now.');
      if (controller.signal.aborted) return false;
      activeUrl = URL.createObjectURL(blobFromBase64(result.audio_content, result.mime_type));
      const audio = new Audio(activeUrl);
      activeAudio = audio;
      const complete = () => {
        if (audio !== activeAudio) return;
        releaseAudio();
        onEnd?.();
      };
      audio.addEventListener('ended', complete, { once: true });
      audio.addEventListener('error', () => {
        if (audio !== activeAudio) return;
        releaseAudio();
        onError?.(new Error('Audio playback failed.'));
      }, { once: true });
      onStart?.();
      await audio.play();
      return true;
    } catch (error) {
      if (error.name !== 'AbortError') {
        releaseAudio();
        onError?.(error);
      }
      return false;
    } finally {
      if (activeController === controller) activeController = null;
    }
  }

  window.PabasaTemplateTts = Object.freeze({ speak, stop: releaseAudio });
})();
