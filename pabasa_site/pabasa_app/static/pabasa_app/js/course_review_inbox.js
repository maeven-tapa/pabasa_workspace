/* Inbox navigation only. Course Students' Progress owns the grading interface. */
(() => {
    'use strict';
    const config = document.querySelector('[data-course-review-inbox]');
    if (!config) return;
    let current = null, opening = false;
    const taskId = new URLSearchParams(location.search).get('review_task');
    const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    function inboxUrl() {
        try {
            const saved = new URL(sessionStorage.getItem('pabasaReviewInboxReturn') || config.dataset.inboxUrl, location.origin);
            if (saved.origin === location.origin && saved.pathname === config.dataset.inboxUrl) return saved.pathname + saved.search;
        } catch (_) {}
        return config.dataset.inboxUrl;
    }
    async function read(url, params) {
        const response = await fetch(url + '?' + params, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'This submission could not be opened.');
        return data;
    }
    function navigation() {
        const nav = document.createElement('div');
        nav.className = 'nc-course-review-nav';
        nav.innerHTML = `<a class="btn btn-outline-secondary btn-sm" href="${esc(inboxUrl())}"><i class="bi bi-arrow-left" aria-hidden="true"></i> Back to inbox</a><span data-review-navigation-status role="status" aria-live="polite">Opened from Needs Checking</span><button type="button" class="btn btn-primary btn-sm" data-next-review>Next pending <i class="bi bi-arrow-right" aria-hidden="true"></i></button>`;
        return nav;
    }
    function message(text) {
        document.querySelectorAll('[data-review-navigation-status]').forEach(node => node.textContent = text);
    }
    async function open(id) {
        if (opening) return;
        opening = true;
        try {
            const data = await read(config.dataset.detailUrl, new URLSearchParams({task: id}));
            current = data.task;
            if (current.mode === 'drawing') {
                if (config.dataset.reviewSurface !== 'drawings') { location.assign(current.review_url); return; }
                const main = document.querySelector('.teacher-review');
                main?.prepend(navigation());
                return;
            }
            window.StudentActivityReview.closeAll(document);
            document.dispatchEvent(new CustomEvent('pabasa:open-student-progress', {detail: {task: current}}));
            const url = new URL(location.href); url.searchParams.set('review_task', id); history.replaceState(null, '', url.pathname + url.search);
        } catch (error) {
            let nav = document.querySelector('.nc-course-review-nav');
            if (!nav) {
                nav = navigation();
                (document.querySelector('.dashboard-content-wrap') || document.body).prepend(nav);
            }
            message(error.message);
        } finally { opening = false; }
    }
    window.addEventListener('pabasa:student-progress-ready', event => {
        if (!current || event.detail.task.id !== current.id) return;
        const list = document.getElementById('studentProgressList');
        const modal = document.getElementById('studentProgressModal');
        const toolbar = modal?.querySelector('.modal-body') || list?.parentElement;
        toolbar?.querySelector('.nc-course-review-nav')?.remove();
        toolbar?.prepend(navigation());
        const card = [...(list?.querySelectorAll('[data-review-activity]') || [])].find(node => node.dataset.reviewActivity === current.progress_task.assessmentId);
        const review = card?.querySelector('.student-progress-review-dialog');
        if (review) {
            review.classList.add('nc-inbox-review');
            review.append(navigation());
        }
        // Supplementary scores live on the existing progress card beside its audio entry.
        if (current.category === 'prescribed') card?.querySelector('.student-progress-review-trigger:not(:disabled)')?.click();
    });
    document.addEventListener('click', async event => {
        const next = event.target.closest('[data-next-review]');
        if (next && current) {
            next.disabled = true;
            try {
                const params = new URLSearchParams(new URL(inboxUrl(), location.origin).search);
                params.set('status', 'needs_review'); params.set('page', '1'); params.delete('task');
                let data = await read(config.dataset.queueUrl, params);
                let task = data.items.find(item => item.id !== current.id);
                if (!task && data.pages > 1) { params.set('page', '2'); data = await read(config.dataset.queueUrl, params); task = data.items[0]; }
                if (!task) { message('No other pending submissions match your inbox filters.'); return; }
                if (current.mode === 'drawing' || task.mode === 'drawing') location.assign(task.review_url);
                else await open(task.id);
            } catch (error) { message(error.message); }
            finally { next.disabled = false; }
        }
        const reviewed = event.target.closest('[data-retell-reviewed]');
        if (!reviewed) return;
        reviewed.disabled = true;
        try {
            const token = decodeURIComponent(document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || '');
            const response = await fetch(config.dataset.actionUrl, {method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': token},
                body: JSON.stringify({task: reviewed.dataset.retellReviewed, version: reviewed.dataset.reviewVersion, action: 'reviewed'})});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || 'Review could not be saved.');
            reviewed.textContent = 'Reviewed · score optional';
            window.dispatchEvent(new Event('pabasa:review-saved'));
        } catch (error) {
            reviewed.disabled = false;
            const status = document.createElement('span'); status.className = 'small text-danger ms-2'; status.setAttribute('role', 'alert'); status.textContent = error.message; reviewed.after(status);
        }
    });
    window.addEventListener('pabasa:review-saved', () => {
        message('Feedback saved. Continue with the next pending submission.');
        document.querySelectorAll('[data-retell-reviewed]').forEach(button => {
            if (button.closest('.student-progress-card')?.querySelector('.student-progress-retell-score')?.dataset.gradeLocked === 'true') {
                button.textContent = 'Reviewed · score saved'; button.disabled = true;
            }
        });
    });
    window.addEventListener('pabasa:student-progress-native', () => {
        current = null;
        const url = new URL(location.href); url.searchParams.delete('review_task');
        history.replaceState(null, '', url.pathname + url.search);
    });
    function start() { if (taskId) open(taskId); }
    if (document.readyState !== 'complete') document.addEventListener('DOMContentLoaded', start, {once: true});
    else start();
})();
