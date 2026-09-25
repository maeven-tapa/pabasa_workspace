/* Shared presentation only: activity handlers retain their scoring and locks. */
(() => {
  'use strict';
  if (window.BasahinButton) return;
  const LABEL = 'Basahin';
  const selector = 'button[data-basahin-button]';
  const labels = {idle: LABEL, calibrating: 'Sandali...', waiting: 'Magsalita...', listening: 'Nakikinig...', processing: 'Sinusuri...'};
  const englishLabels = {idle: 'Read', calibrating: 'Please wait...', waiting: 'Speak now...', listening: 'Listening...', processing: 'Checking...'};
  const labelsFor = button => /^en|english/i.test(button?.dataset.basahinLanguage || '') ? englishLabels : labels;
  const activities = new WeakMap(), running = new WeakSet();

  // One click handler for every Basahin button, including buttons re-rendered by
  // an activity. Registered callbacks supply only that activity's workflow.
  function bindActivity(button, action) {
    if (!button) return;
    button.onclick = null;
    activities.set(button, action);
    decorate(button);
    return action;
  }
  const getActivity = button => activities.get(button);
  function unbindActivity(button, action) {
    if (button && (!action || getActivity(button) === action)) activities.delete(button);
  }
  async function handleClick(event) {
    const button = event.target.closest?.(selector);
    const action = button && getActivity(button);
    if (!action || button.disabled || running.has(button)) return;
    running.add(button);
    try { await action.call(button, event); }
    catch (error) {
      button.dispatchEvent(new CustomEvent('basahin:error', {bubbles: true, detail: {error}}));
    } finally {
      running.delete(button);
      if (button.isConnected) decorate(button);
    }
  }

  function stateFromText(text) {
    if (/sandali|please wait/i.test(text)) return 'calibrating';
    if (/magsalita|speak now/i.test(text)) return 'waiting';
    if (/nakikinig|nagbabasa|recording|listening/i.test(text)) return 'listening';
    if (/sinusuri|pinoproseso|processing|checking/i.test(text)) return 'processing';
    if (/pakinggan|read aloud/i.test(text)) return 'model';
    return 'idle';
  }

  function setSpeech(button, speaking) {
    if (!button) return;
    const value = String(Boolean(speaking));
    if (button.dataset.basahinSpeaking !== value) button.dataset.basahinSpeaking = value;
  }

  function decorate(button, state) {
    if (!button) return;
    const source = button.textContent.trim();
    state = state || stateFromText(source);
    if (!button.hasAttribute('data-basahin-button')) button.setAttribute('data-basahin-button', '');
    if (button.dataset.basahinState !== state) button.dataset.basahinState = state;
    if (state !== 'listening') setSpeech(button, false);
    const busy = String(['calibrating', 'waiting', 'listening', 'processing'].includes(state));
    if (button.getAttribute('aria-busy') !== busy) button.setAttribute('aria-busy', busy);
    let label = button.querySelector('[data-basahin-label]');
    let icon = button.querySelector('[data-basahin-icon]');
    if (!label || !icon) {
      // Keep the button itself: existing onclick handlers and focus survive.
      icon = document.createElement('i');
      icon.setAttribute('data-basahin-icon', '');
      icon.setAttribute('aria-hidden', 'true');
      label = document.createElement('span');
      label.setAttribute('data-basahin-label', '');
      button.replaceChildren(icon, label);
    }
    // Some activities reuse their reading button for the teacher's model audio.
    const text = labelsFor(button)[state] || source.replace(/^[^\p{L}]+/u, '') || 'Pakinggan';
    if (label.textContent !== text) label.textContent = text;
    return button;
  }

  function mount(root = document) {
    if (root.matches?.(selector)) decorate(root);
    root.querySelectorAll(selector).forEach(button => decorate(button));
  }

  function start() {
    mount();
    new MutationObserver(records => {
      const changed = new Set();
      for (const record of records) {
        const element = record.target.nodeType === 1 ? record.target : record.target.parentElement;
        const button = element?.closest(selector);
        if (button) changed.add(button);
        for (const node of record.addedNodes || []) {
          if (node.nodeType !== 1) continue;
          if (node.matches(selector)) changed.add(node);
          node.querySelectorAll(selector).forEach(item => changed.add(item));
        }
      }
      changed.forEach(button => { if (button.isConnected) decorate(button); });
    }).observe(document.body, {subtree: true, childList: true, characterData: true});
  }
  document.addEventListener('click', handleClick);
  window.BasahinButton = Object.freeze({LABEL, labelsFor, decorate, setState: decorate, setSpeech, mount, bindActivity, getActivity, unbindActivity});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
