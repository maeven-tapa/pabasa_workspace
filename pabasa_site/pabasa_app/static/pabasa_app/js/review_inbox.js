(() => {
    'use strict';
    const config = document.querySelector('[data-review-inbox-url]');
    if (!config) return;
    let busy = false;
    let lastGood = null;
    async function refresh() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            const response = await fetch(config.dataset.reviewInboxUrl + '?summary=1', {
                credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error('Review inbox unavailable');
            lastGood = data;
            document.querySelectorAll('[data-nc-stat]').forEach(node => {
                const value = data.summary[node.dataset.ncStat];
                if (value !== undefined && node.textContent !== value.toLocaleString()) node.textContent = value.toLocaleString();
                node.classList.remove('nc-loading');
            });
            document.querySelectorAll('[data-nc-badge]').forEach(node => {
                node.hidden = !data.summary.pending;
                node.textContent = data.summary.pending > 99 ? '99+' : data.summary.pending;
            });
            document.querySelectorAll('[data-nc-sync]').forEach(node => {
                node.textContent = 'Updated ' + new Date(data.updated_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
            });
            window.dispatchEvent(new CustomEvent('pabasa:review-inbox', {detail: data}));
            if (data.notification_changed) window.dispatchEvent(new Event('pabasa:notifications-updated'));
        } catch (error) {
            document.querySelectorAll('[data-nc-sync]').forEach(node => {
                node.textContent = lastGood ? 'Connection paused · showing last update' : 'Unable to connect · try refreshing';
            });
        } finally { busy = false; }
    }
    window.PabasaReviewInbox = {refresh, get snapshot() { return lastGood; }};
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    window.addEventListener('pabasa:review-saved', refresh);
    window.addEventListener('focus', refresh);
    window.setInterval(refresh, 30000);
    if (document.getElementById('nc-workspace')) window.addEventListener('pabasa:review-list-loaded', refresh, {once: true});
    else refresh();
})();
