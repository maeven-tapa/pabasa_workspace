/*
 * Compatibility bridge for template pages that still call Web Speech directly.
 * It is injected only into those template activity responses, never globally.
 */
(() => {
  'use strict';
  const speech = window.speechSynthesis || {};
  if (!window.PabasaTemplateTts) return;
  // A few template pages check the Web Speech globals before calling speak.
  // Supply a tiny compatibility shape so Google TTS still works on browsers
  // that omit the local Web Speech implementation entirely.
  if (!window.speechSynthesis) window.speechSynthesis = speech;
  if (!window.SpeechSynthesisUtterance) {
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = String(text || '');
    };
  }
  const materialId = document.body?.dataset.templateMaterialId || window.__PABASA_TEMPLATE_TTS__?.materialId;
  if (!materialId) return;
  const profile = document.body?.dataset.templateTtsProfile || window.__PABASA_TEMPLATE_TTS__?.profile || 'instruction';
  speech.cancel = () => window.PabasaTemplateTts.stop();
  speech.speak = async (utterance) => {
    const text = String(utterance?.text || '').trim();
    if (!text) return;
    await window.PabasaTemplateTts.speak({
      materialId, text, profile,
      onStart: () => utterance.onstart?.(),
      onEnd: () => utterance.onend?.(),
      onError: (error) => utterance.onerror?.(error),
    });
  };
})();
