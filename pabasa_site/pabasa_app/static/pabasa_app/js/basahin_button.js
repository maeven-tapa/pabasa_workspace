/* Shared presentation only: activity handlers retain their scoring and locks. */
(() => {
  'use strict';
  if (window.BasahinButton) return;
  const LABEL = 'Basahin';
  const selector = 'button[data-basahin-button]';
  const englishReaderSelector = 'button[data-basahin-button][data-basahin-language="English"]';
  const pakingganSelector = 'button[data-pakinggan-button]';
  // Sessions 10–15 are Lessons 26–31. Keep the shared Listen presentation
  // limited to those activities until it is deliberately rolled out further.
  const isSession10To15Activity = () => /\/lesson-(?:26|27|28|29|30|31)-gawain-/i.test(window.location.pathname);
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

  function decoratePakinggan(button) {
    if (!button) return;
    const source = button.textContent.trim();
    button.setAttribute('data-pakinggan-button', '');
    button.dataset.pakingganState = button.classList.contains('is-busy') ? 'playing' : 'ready';
    let label = button.querySelector('[data-pakinggan-label]');
    let icon = button.querySelector('[data-pakinggan-icon]');
    if (!label || !icon) {
      icon = document.createElement('i');
      icon.setAttribute('data-pakinggan-icon', '');
      icon.setAttribute('aria-hidden', 'true');
      label = document.createElement('span');
      label.setAttribute('data-pakinggan-label', '');
      button.replaceChildren(icon, label);
    }
    const text = source.replace(/^[^\p{L}]+/u, '') || 'Pakinggan';
    if (label.textContent !== text) label.textContent = text;
    return button;
  }

  function pairWithPakinggan(read, listen) {
    if (!read || !listen) return;
    read.setAttribute('data-pakinggan-pair', '');
    listen.setAttribute('data-pakinggan-button', '');
    decoratePakinggan(listen);
    const syncSize = () => {
      if (!read.isConnected || !listen.isConnected) return;
      const rect = listen.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      read.style.setProperty('--pakinggan-paired-width', `${Math.round(rect.width * 100) / 100}px`);
      read.style.setProperty('--pakinggan-paired-height', `${Math.round(rect.height * 100) / 100}px`);
    };
    requestAnimationFrame(syncSize);
    if (!listen._pakingganResizeObserver && 'ResizeObserver' in window) {
      listen._pakingganResizeObserver = new ResizeObserver(syncSize);
      listen._pakingganResizeObserver.observe(listen);
    }
  }

  function mountPakingganPairs(root = document) {
    if (!isSession10To15Activity()) return;
    const readers = [];
    if (root.matches?.(englishReaderSelector)) readers.push(root);
    root.querySelectorAll?.(englishReaderSelector).forEach(button => readers.push(button));
    readers.forEach(read => {
      const listen = [...(read.parentElement?.children || [])]
        .find(button => button !== read && button.matches?.('button') && /listen|pakinggan/i.test(button.textContent));
      if (listen) pairWithPakinggan(read, listen);
    });
    // Some activity phases show a Listen control before, or without, the Read
    // control. Mark those too so their playing state never inherits a local
    // pulse animation.
    const controls = [];
    if (root.matches?.('button') && /listen|pakinggan/i.test(root.textContent)) controls.push(root);
    root.querySelectorAll?.('button').forEach(button => {
      if (/listen|pakinggan/i.test(button.textContent)) controls.push(button);
    });
    controls.forEach(decoratePakinggan);
    if (root.matches?.(pakingganSelector)) decoratePakinggan(root);
    root.querySelectorAll?.(pakingganSelector).forEach(button => decoratePakinggan(button));
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
    mountPakingganPairs(root);
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
      mountPakingganPairs(document);
      changed.forEach(button => { if (button.isConnected) decorate(button); });
    }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class', 'disabled']});
  }
  document.addEventListener('click', handleClick);
  window.BasahinButton = Object.freeze({LABEL, labelsFor, decorate, decoratePakinggan, setState: decorate, setSpeech, mount, bindActivity, getActivity, unbindActivity});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
