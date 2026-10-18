/* Retry safe navigation only. A busy POST must never be replayed by this page. */
(() => {
    const key = 'pabasa-page-retry:' + window.location.pathname;
    let attempts = 0;
    try {
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (saved && Date.now() - saved.at < 60000) attempts = saved.attempts || 0;
        sessionStorage.setItem(key, JSON.stringify({attempts: attempts + 1, at: Date.now()}));
    } catch (_) {
        // Without storage, a single page must not create an endless reload loop.
        return;
    }
    if (attempts >= 5) {
        document.getElementById('retry-message').textContent =
            'The service is still busy. Please wait a little, then choose Try again.';
        return;
    }
    window.setTimeout(() => window.location.reload(), 1000 + Math.floor(Math.random() * 1000));
})();
