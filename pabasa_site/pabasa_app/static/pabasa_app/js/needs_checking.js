(() => {
    'use strict';
    const root = document.getElementById('nc-workspace');
    if (!root) return;
    document.body.classList.add('nc-workspace-page');
    const $ = id => document.getElementById(id);
    const form = $('nc-filters'), list = $('nc-list');
    const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    const statusLabels = {pending: 'New submission', partial: 'Partially reviewed', reviewed: 'Reviewed', retry: 'Awaiting resubmission'};
    let page = 1, pages = 1, category = '', listRequest = 0, searchTimer;
    let initial = true, optionsStamp = '', listStamp = '';
    const initialParams = new URLSearchParams(location.search);
    for (const field of form.elements) if (field.name && initialParams.has(field.name)) field.value = initialParams.get(field.name);
    category = initialParams.get('category') || '';
    page = Math.max(1, Number(initialParams.get('page')) || 1);
    function relative(value) {
        const date = new Date(value), minutes = Math.max(0, Math.floor((Date.now() - date) / 60000));
        if (!Number.isFinite(minutes)) return 'Submitted';
        return minutes < 1 ? 'Just now' : minutes < 60 ? `${minutes}m ago` : minutes < 1440 ? `${Math.floor(minutes / 60)}h ago` : `${Math.floor(minutes / 1440)}d ago`;
    }
    function params(targetPage = page) {
        const data = new URLSearchParams(new FormData(form));
        if (category) data.set('category', category);
        data.set('page', targetPage);
        return data;
    }
    async function get(url, data, attempt = 0) {
        const response = await fetch(url + '?' + data, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}});
        if (response.status === 503 && attempt < 2) { await new Promise(resolve => setTimeout(resolve, 200 * (attempt + 1))); return get(url, data, attempt + 1); }
        let body;
        try { body = await response.json(); } catch { throw new Error('Your session may have expired. Refresh the page to reconnect.'); }
        if (!response.ok || !body.success) throw new Error(body.error || 'Unable to load submissions. Please try again.');
        return body;
    }
    function updateOptions(options) {
        const stamp = JSON.stringify(options);
        if (stamp === optionsStamp) return;
        optionsStamp = stamp;
        for (const [name, items] of [['section', options.sections], ['calendar', options.periods], ['activity', options.activities], ['term', options.terms.map(term => ({id: term, label: 'Term ' + term}))]]) {
            const select = form.elements.namedItem(name);
            const value = select.value || (initial ? initialParams.get(name) || '' : '');
            while (select.options.length > 1) select.remove(1);
            items.forEach(item => select.add(new Option(item.label, item.id)));
            select.value = value;
        }
    }
    function row(task) {
        const initials = task.student_name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('');
        const total = task.reviewed_items + task.pending_items;
        const progress = total ? Math.round(task.reviewed_items / total * 100) : 0;
        const pendingText = task.final_verdict && !task.pending_items ? 'Final decision needed' : task.status === 'reviewed' ? 'All submitted work checked' : task.status === 'retry' ? 'Student is trying again' : `${task.pending_items} ${task.pending_items === 1 ? 'item' : 'items'} to check`;
        return `<article class="nc-row"><div class="nc-student"><span class="nc-avatar" aria-hidden="true">${esc(initials)}</span><div><strong>${esc(task.student_name)}</strong><small>${esc(task.section)} · Term ${task.term}</small></div></div><div class="nc-activity"><span>${task.category === 'prescribed' ? 'PRESCRIBED WORKBOOK' : 'SUPPLEMENTARY MATERIALS'}</span><strong>${esc(task.title)}</strong><small>${esc(task.label)} · <time datetime="${esc(task.submitted_at)}" title="${esc(new Date(task.submitted_at).toLocaleString())}">${esc(relative(task.submitted_at))}</time></small></div><div class="nc-state"><span class="nc-status ${esc(task.status)}"><i class="bi bi-${task.status === 'reviewed' ? 'check2-circle' : task.status === 'partial' ? 'circle-half' : task.status === 'retry' ? 'arrow-repeat' : 'circle-fill'}" aria-hidden="true"></i>${statusLabels[task.status]}</span><small>${pendingText}</small><div class="nc-progress-track" role="progressbar" aria-label="Reviewed submitted items" aria-valuemin="0" aria-valuemax="${Math.max(total, 1)}" aria-valuenow="${task.reviewed_items}"><span style="width:${progress}%"></span></div></div><button type="button" class="nc-button" data-open-task="${esc(task.id)}" data-review-url="${esc(task.review_url)}" aria-label="${task.status === 'reviewed' ? 'View' : 'Review'} ${esc(task.title)} by ${esc(task.student_name)}">${task.status === 'reviewed' || task.status === 'retry' ? 'View' : task.status === 'partial' ? 'Continue' : 'Review'} <i class="bi bi-arrow-right" aria-hidden="true"></i></button></article>`;
    }
    function empty() {
        const filtered = category || [...new FormData(form)].some(([key, value]) => value && !['sort'].includes(key) && !(key === 'status' && value === 'needs_review'));
        return `<div class="nc-empty"><span class="nc-empty-icon"><i class="bi bi-${filtered ? 'search' : 'check2-all'}" aria-hidden="true"></i></span><h3>${filtered ? 'No matching submissions' : 'A clear inbox. A little breathing room.'}</h3><p>${filtered ? 'Try another class, activity, or status to find the work you’re looking for.' : 'You’re up to date with submitted work in your current classes. New submissions will appear here automatically.'}</p>${filtered ? '<button type="button" class="nc-button nc-button-secondary" data-reset>Clear filters</button>' : ''}</div>`;
    }
    async function load({quiet = false} = {}) {
        const sequence = ++listRequest;
        list.setAttribute('aria-busy', 'true');
        if (!quiet) $('nc-results-count').textContent = 'Updating your inbox…';
        try {
            const data = await get(root.dataset.listUrl, params());
            if (sequence !== listRequest) return;
            updateOptions(data.options);
            page = data.page; pages = data.pages;
            const oldFocus = document.activeElement?.dataset?.openTask;
            const stamp = JSON.stringify([data.items, data.total, data.page, params().toString()]);
            if (!quiet || stamp !== listStamp) list.innerHTML = data.items.length ? data.items.map(row).join('') : empty();
            listStamp = stamp;
            if (oldFocus) [...list.querySelectorAll('[data-open-task]')].find(node => node.dataset.openTask === oldFocus)?.focus({preventScroll: true});
            const resultText = `${data.total} ${data.total === 1 ? 'submission' : 'submissions'}${category ? ' · ' + (category === 'prescribed' ? 'Prescribed workbook' : 'Supplementary materials') : ''}`;
            if ($('nc-results-count').textContent !== resultText) $('nc-results-count').textContent = resultText;
            $('nc-page-label').textContent = `Page ${page} of ${pages}`;
            $('nc-prev').disabled = page <= 1; $('nc-next').disabled = page >= pages;
            root.querySelectorAll('[data-nc-stat]').forEach(node => { const value = data.summary[node.dataset.ncStat]; if (value !== undefined && node.textContent !== String(value)) node.textContent = value; });
            root.querySelectorAll('[data-category]').forEach(button => { button.classList.toggle('is-active', button.dataset.category === category); button.setAttribute('aria-pressed', String(button.dataset.category === category)); });
            const url = params();
            history.replaceState(null, '', location.pathname + '?' + url);
            initial = false;
            window.dispatchEvent(new Event('pabasa:review-list-loaded'));
        } catch (error) {
            if (sequence !== listRequest) return;
            $('nc-results-count').textContent = 'Inbox could not be updated';
            if (!quiet) list.innerHTML = `<div class="nc-empty"><span class="nc-empty-icon"><i class="bi bi-wifi-off" aria-hidden="true"></i></span><h3>Let’s reconnect</h3><p>${esc(error.message)}</p><button type="button" class="nc-button" data-reload>Try again</button></div>`;
        } finally { if (sequence === listRequest) list.setAttribute('aria-busy', 'false'); }
    }
    list.addEventListener('click', event => {
        const button = event.target.closest('[data-open-task]');
        if (button) {
            try { sessionStorage.setItem('pabasaReviewInboxReturn', location.pathname + '?' + params()); } catch (_) {}
            location.assign(button.dataset.reviewUrl);
        }
        if (event.target.closest('[data-reset]')) form.reset();
        if (event.target.closest('[data-reload]')) load();
    });
    form.addEventListener('submit', event => event.preventDefault());
    form.addEventListener('input', event => {
        if (event.target.name !== 'q') return;
        clearTimeout(searchTimer); searchTimer = setTimeout(() => { page = 1; load(); }, 300);
    });
    form.addEventListener('change', event => { if (event.target.name !== 'q') { page = 1; load(); } });
    form.addEventListener('reset', () => { category = ''; page = 1; setTimeout(load, 0); });
    root.querySelectorAll('[data-category]').forEach(button => button.onclick = () => { category = button.dataset.category; page = 1; load(); });
    $('nc-prev').onclick = () => { page--; load(); }; $('nc-next').onclick = () => { page++; load(); };
    $('nc-refresh').onclick = () => { window.PabasaReviewInbox?.refresh(); load(); };
    window.addEventListener('pabasa:review-inbox', () => { if (!initial && !document.hidden) load({quiet: true}); });
    load();
})();
