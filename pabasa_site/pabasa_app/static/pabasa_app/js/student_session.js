/* Shared student login lifetime. Learning activity never needs mouse movement. */
(() => {
  'use strict';
  const configNode = document.getElementById('student-session-config');
  if (!configNode || window.PabasaStudentSession) return;
  const config = JSON.parse(configNode.textContent);
  const tabId = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const storageKey = `pabasa-session-tabs:${config.channel}`;
  let deadline = performance.now() + config.remaining_seconds * 1000;
  let protectedSession = config.protected, pendingActivity = false;
  let pending = null, ended = false, lastRequest = -Infinity, lastActivity = -Infinity;
  let dialog, title, message, countdown, stay, signOut, previousFocus;
  let channel;
  try { channel = new BroadcastChannel(`pabasa-session:${config.channel}`); } catch (_) {}

  function learningPages(remove = false) {
    // Share learning presence, not a client-computed authentication deadline.
    // Stale/closed tabs disappear; another tab's learning keeps this one safe.
    try {
      const now = Date.now(), tabs = JSON.parse(localStorage.getItem(storageKey) || '{}');
      for (const [id, tab] of Object.entries(tabs)) {
        if (!tab || Math.abs(now - tab.seen) > 5 * 60 * 1000) delete tabs[id];
      }
      if (remove) delete tabs[tabId];
      else tabs[tabId] = {seen: now, path: config.learning_page ? location.pathname : ''};
      localStorage.setItem(storageKey, JSON.stringify(tabs));
      return Object.values(tabs).map(tab => tab.path).filter(Boolean);
    } catch (_) { return []; }
  }

  function ensureDialog() {
    if (dialog) return;
    dialog = document.createElement('dialog');
    dialog.className = 'student-session-dialog';
    dialog.setAttribute('aria-labelledby', 'student-session-title');
    dialog.setAttribute('aria-describedby', 'student-session-message');
    dialog.innerHTML = '<h2 id="student-session-title"></h2><p id="student-session-message"></p>' +
      '<p class="student-session-countdown" aria-live="off"></p><div class="student-session-actions">' +
      '<button type="button" class="student-session-stay">Stay signed in</button>' +
      '<button type="button" class="student-session-signout">Sign out</button></div>';
    document.body.append(dialog);
    title = dialog.querySelector('h2'); message = dialog.querySelector('#student-session-message');
    countdown = dialog.querySelector('.student-session-countdown');
    stay = dialog.querySelector('.student-session-stay'); signOut = dialog.querySelector('.student-session-signout');
    stay.addEventListener('click', async () => {
      pendingActivity = true;
      // Do not lose a renewal click while a passive status request is pending.
      if (pending) await pending;
      await heartbeat();
    });
    signOut.addEventListener('click', () => {
      learningPages(true);
      location.assign(ended ? config.login_url : config.logout_url);
    });
    dialog.addEventListener('cancel', event => event.preventDefault());
  }

  function showDialog() {
    ensureDialog();
    if (!dialog.open) { previousFocus = document.activeElement; dialog.showModal(); }
  }

  function closeDialog() {
    if (dialog?.open) {
      dialog.close();
      if (previousFocus?.isConnected) previousFocus.focus();
    }
  }

  function expire(broadcast = true) {
    if (ended) return;
    ended = true;
    window.Basahin?.cancelAll();
    window.dispatchEvent(new CustomEvent('pabasa:session-ended'));
    showDialog();
    title.textContent = 'Your session has ended';
    message.textContent = 'Please sign in again to continue. Your saved progress is kept.';
    countdown.textContent = '';
    stay.hidden = true; signOut.textContent = 'Sign in again'; signOut.focus();
    learningPages(true);
    if (broadcast) channel?.postMessage({type: 'ended'});
  }

  function applyStatus(status, broadcast = true) {
    protectedSession = Boolean(status.protected);
    deadline = performance.now() + Math.max(0, status.remaining_seconds) * 1000;
    config.warning_seconds = status.warning_seconds;
    if (protectedSession || status.remaining_seconds > config.warning_seconds) closeDialog();
    if (broadcast) channel?.postMessage({type: 'status', status});
    render();
  }

  async function heartbeat() {
    if (pending || ended) return pending;
    const activity = pendingActivity;
    pendingActivity = false;
    lastRequest = performance.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    if (stay) stay.disabled = true;
    pending = (async () => {
      try {
        const response = await fetch(config.heartbeat_url, {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: {'X-CSRFToken': config.csrf_token, 'Accept': 'application/json'},
          body: new URLSearchParams({activity: activity ? '1' : '0', page: location.pathname,
            learning_pages: JSON.stringify(learningPages())}),
        });
        if (response.status === 401) { expire(); return; }
        if (!response.ok) throw new Error('Session check failed');
        const status = await response.json();
        if (!status.success || !Number.isFinite(status.remaining_seconds)) throw new Error('Invalid session status');
        applyStatus(status);
      } catch (_) {
        // A network failure is not proof of expiry. Do not redirect or discard work.
        pendingActivity ||= activity;
        if (dialog?.open && !ended) message.textContent = 'We could not check your session. Reconnect and choose Stay signed in.';
      } finally {
        clearTimeout(timer); pending = null;
        if (stay) stay.disabled = false;
      }
    })();
    return pending;
  }

  function render() {
    if (ended || protectedSession || config.learning_page) return;
    const remaining = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
    if (remaining > config.warning_seconds) return;
    showDialog();
    title.textContent = 'Still there?';
    if (remaining > 0) {
      message.textContent = 'You have been inactive for a while. Stay signed in to continue.';
      countdown.textContent = `Signing out in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;
    } else {
      countdown.textContent = 'Checking your session…';
      // The server owns expiry, including activity in another tab. Client clocks
      // or a suspended tab cannot log the account out on their own.
      if (performance.now() - lastRequest > 10000) heartbeat();
    }
  }

  function onActivity(event) {
    if (!event.isTrusted || ended || dialog?.open) return;
    const now = performance.now();
    if (now - lastActivity < 1000) return;
    lastActivity = now; pendingActivity = true;
    if (now - lastRequest >= 15000) heartbeat();
  }
  for (const event of ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'scroll']) {
    document.addEventListener(event, onActivity, {passive: true, capture: true});
  }
  channel?.addEventListener('message', event => {
    if (event.data?.type === 'ended') expire(false);
    if (event.data?.type === 'status' && !ended) applyStatus(event.data.status, false);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') heartbeat();
  });
  window.addEventListener('online', () => heartbeat());
  window.addEventListener('pageshow', () => heartbeat());
  window.addEventListener('pagehide', () => learningPages(true));
  setInterval(() => heartbeat(), 30000);
  setInterval(render, 1000);
  window.PabasaStudentSession = Object.freeze({check: heartbeat});
  heartbeat();
})();
