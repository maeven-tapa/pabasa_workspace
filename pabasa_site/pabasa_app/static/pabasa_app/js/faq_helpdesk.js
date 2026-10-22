/* FAQ records live in semantic HTML. Search, topics and shortcuts share them. */
(() => {
    'use strict';

    const DEFAULT_PAGE_SIZE = 8;

    function normalizeQuery(value) {
        return String(value ?? '').normalize('NFKD').replace(/\p{M}/gu, '')
            .toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
    }

    function filterRecords(records, query = '', topic = 'all') {
        const terms = normalizeQuery(query).split(' ').filter(Boolean);
        const seen = new Set();
        return records.filter(record => {
            if (seen.has(record.id)) return false;
            seen.add(record.id);
            if (topic !== 'all' && record.topic !== topic) return false;
            const text = normalizeQuery([record.title, record.answer, record.topicLabel, record.keywords].join(' '));
            return terms.every(term => text.includes(term));
        });
    }

    function pageRecords(records, page = 0, pageSize = DEFAULT_PAGE_SIZE) {
        const pages = Math.max(1, Math.ceil(records.length / pageSize));
        const current = Math.max(0, Math.min(pages - 1, page));
        return { items: records.slice(current * pageSize, (current + 1) * pageSize), page: current, pages };
    }

    // The same pure functions are exercised by the dependency-free Node tests.
    if (typeof module !== 'undefined' && module.exports) module.exports = { normalizeQuery, filterRecords, pageRecords, DEFAULT_PAGE_SIZE };
    if (typeof document === 'undefined') return;
    const root = document.querySelector('[data-helpdesk]');
    if (!root) return;

    const input = root.querySelector('#faqSearch');
    const status = root.querySelector('#faqSearchStatus');
    const title = root.querySelector('#hd-results-title');
    const context = root.querySelector('[data-filter-context]');
    const topics = [...root.querySelectorAll('[data-topic-filter]')];
    const labels = new Map(topics.map(button => [button.dataset.topicFilter, button.querySelector('span').textContent]));
    const records = [...root.querySelectorAll('[data-faq-record]')].map(element => ({
        id: element.id,
        topic: element.dataset.topic,
        topicLabel: element.dataset.topicLabel,
        keywords: element.dataset.keywords,
        title: element.querySelector('[data-question-title]').textContent,
        answer: element.querySelector('.hd-answer').textContent,
        element,
        button: element.querySelector('.hd-question-button'),
        answerElement: element.querySelector('.hd-answer'),
    }));
    const pageSize = DEFAULT_PAGE_SIZE;
    const state = { query: input.value, topic: 'all', page: 0 };
    const pagination = root.querySelector('[data-pagination]');
    const previous = root.querySelector('[data-previous-page]');
    const next = root.querySelector('[data-next-page]');
    const empty = root.querySelector('[data-empty-state]');
    const topicNav = root.querySelector('.hd-topics');

    function keepTopicInView() {
        if (topicNav.scrollWidth <= topicNav.clientWidth) return;
        const selected = topics.find(button => button.dataset.topicFilter === state.topic);
        const bounds = selected.getBoundingClientRect();
        const viewport = topicNav.getBoundingClientRect();
        // Move only the horizontal selector, never the page or results viewport.
        if (bounds.left < viewport.left + 8) {
            topicNav.scrollTo({ left: topicNav.scrollLeft + bounds.left - viewport.left - 8, behavior: 'instant' });
        } else if (bounds.right > viewport.right - 8) {
            topicNav.scrollTo({ left: topicNav.scrollLeft + bounds.right - viewport.right + 8, behavior: 'instant' });
        }
    }

    function expand(record, open) {
        record.button.setAttribute('aria-expanded', String(open));
        record.answerElement.hidden = !open;
    }

    function render() {
        const matches = filterRecords(records, state.query, state.topic);
        const allTopicMatches = filterRecords(records, state.query);
        const page = pageRecords(matches, state.page, pageSize);
        state.page = page.page;
        const visible = new Set(page.items.map(record => record.id));
        records.forEach(record => {
            record.element.hidden = !visible.has(record.id);
            record.element.removeAttribute('data-group-start');
            record.element.querySelector('.hd-question-topic').hidden = true;
        });
        // Topic context belongs once per group, not above every question.
        page.items.forEach((record, index) => {
            const startsGroup = state.topic === 'all' && record.topic !== page.items[index - 1]?.topic;
            record.element.toggleAttribute('data-group-start', startsGroup);
            record.element.querySelector('.hd-question-topic').hidden = !startsGroup;
        });
        const hasQuery = Boolean(normalizeQuery(state.query));
        topics.forEach(button => {
            const key = button.dataset.topicFilter;
            const count = key === 'all' ? allTopicMatches.length : allTopicMatches.filter(record => record.topic === key).length;
            button.setAttribute('aria-pressed', String(key === state.topic));
            button.setAttribute('aria-label', `${labels.get(key)}, ${count} ${count === 1 ? 'question' : 'questions'}`);
            button.querySelector('[data-count]').textContent = String(count);
        });
        title.textContent = labels.get(state.topic);
        const searchText = state.query.trim().replace(/\s+/g, ' ');
        context.textContent = hasQuery
            ? `Search “${searchText}” · ${state.topic === 'all' ? 'All topics' : labels.get(state.topic) + ' only'}`
            : state.topic === 'all' ? 'Browsing all topics.' : `Showing ${labels.get(state.topic)} only.`;
        const first = matches.length ? state.page * pageSize + 1 : 0;
        const last = Math.min((state.page + 1) * pageSize, matches.length);
        status.textContent = `${matches.length} ${matches.length === 1 ? 'question' : 'questions'}${hasQuery ? ' matched' : ''}${matches.length ? ` · Showing ${first}–${last}` : ''}.`;
        empty.hidden = matches.length !== 0;
        pagination.hidden = page.pages <= 1;
        previous.disabled = state.page === 0;
        next.disabled = state.page === page.pages - 1;
        root.querySelector('[data-page-label]').textContent = `Page ${state.page + 1} of ${page.pages}`;
        root.querySelector('.hd-search-clear').hidden = input.value.length === 0;
        root.querySelector('.hd-results-header [data-reset-filters]').hidden = !hasQuery && state.topic === 'all';
        keepTopicInView();
    }

    function reveal(id, focus = true) {
        const record = records.find(item => item.id === id);
        if (!record) return;
        state.query = '';
        input.value = '';
        state.topic = record.topic;
        const topicRecords = filterRecords(records, '', record.topic);
        state.page = Math.floor(topicRecords.indexOf(record) / pageSize);
        render();
        expand(record, true);
        if (focus) {
            record.button.focus({ preventScroll: true });
            record.element.scrollIntoView({ block: 'nearest', behavior: 'instant' });
        }
    }

    records.forEach(record => {
        expand(record, false);
        record.button.addEventListener('click', () => expand(record, record.button.getAttribute('aria-expanded') !== 'true'));
    });
    input.addEventListener('input', () => {
        state.query = input.value;
        state.page = 0;
        render();
    });
    root.querySelector('.hd-search').addEventListener('submit', event => {
        event.preventDefault();
        // Enter takes keyboard users from search to the result summary.
        title.focus({ preventScroll: true });
        title.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    });
    topics.forEach(button => button.addEventListener('click', () => {
        state.topic = button.dataset.topicFilter;
        state.page = 0;
        render();
    }));
    root.querySelectorAll('[data-clear-search]').forEach(button => button.addEventListener('click', () => {
        state.query = '';
        input.value = '';
        state.page = 0;
        render();
        (button.closest('.hd-search') ? input : title).focus({ preventScroll: true });
    }));
    root.querySelectorAll('[data-reset-filters]').forEach(button => button.addEventListener('click', () => {
        state.query = '';
        state.topic = 'all';
        state.page = 0;
        input.value = '';
        render();
        title.focus({ preventScroll: true });
    }));
    root.querySelectorAll('[data-quick-answer]').forEach(link => link.addEventListener('click', event => {
        event.preventDefault();
        reveal(link.dataset.quickAnswer);
    }));
    [previous, next].forEach((button, index) => button.addEventListener('click', () => {
        state.page += index ? 1 : -1;
        render();
        title.focus({ preventScroll: true });
        title.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    }));
    function readHash() {
        const id = window.location.hash.slice(1);
        if (records.some(record => record.id === id)) return reveal(id);
        const legacyTopic = { 'faq-getting-started': 'getting-started', 'faq-reading': 'reading', 'faq-accounts': 'accounts' }[id];
        if (legacyTopic) { state.topic = legacyTopic; state.page = 0; render(); }
    }
    // Use the shared header's measured height; short windows keep a normal sidebar.
    const sidebar = root.querySelector('.hd-sidebar');
    const publicHeader = document.querySelector('.modern-nav-wrap');
    function syncStickyTopics() {
        const headerHeight = publicHeader?.getBoundingClientRect().height || 0;
        root.dataset.stickyTopics = String(window.innerHeight > sidebar.offsetHeight + headerHeight + 32);
        keepTopicInView();
    }
    window.addEventListener('resize', syncStickyTopics, { passive: true });
    if ('ResizeObserver' in window) {
        const observer = new ResizeObserver(syncStickyTopics);
        observer.observe(sidebar);
        if (publicHeader) observer.observe(publicHeader);
    }
    syncStickyTopics();
    render();
    readHash();
    window.addEventListener('hashchange', readHash);
    root.dataset.enhanced = '';
})();
