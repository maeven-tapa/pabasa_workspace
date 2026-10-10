/* One fresh, authorized listing per section/mode on this page. */
(function () {
    'use strict';
    const entries = new Map();
    const generations = new Map();
    const sections = new Set();
    const queue = [];
    const readingsKey = 'pabasa_section_readings';
    const metadataKey = 'pabasa_section_metadata';
    const requestedSection = new URLSearchParams(window.location.search).get('section_id');
    let active = 0;

    function read(key) {
        try {
            const value = JSON.parse(localStorage.getItem(key) || '{}');
            return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
        } catch (_) { return {}; }
    }
    function write(key, value) {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* Storage is optional. */ }
    }
    function removeSection(sectionId) {
        const readings = read(readingsKey);
        const metadata = read(metadataKey);
        delete readings[sectionId];
        delete metadata[sectionId];
        write(readingsKey, readings);
        write(metadataKey, metadata);
    }
    function store(sectionId, payload) {
        const readings = read(readingsKey);
        readings[sectionId] = payload.materials || {};
        write(readingsKey, readings);
        const metadata = read(metadataKey);
        metadata[sectionId] = {
            code: payload.class_code || '', name: payload.class_name || 'Reading Class',
            subject: payload.subject || 'Reading',
        };
        write(metadataKey, metadata);
    }
    function drain() {
        while (active < 2 && queue.length) {
            const job = queue.shift();
            active += 1;
            Promise.resolve().then(job.run).then(job.resolve, job.reject).finally(() => {
                active -= 1;
                drain();
            });
        }
    }
    function schedule(run, priority) {
        return new Promise((resolve, reject) => {
            const job = { run, resolve, reject };
            if (priority) queue.unshift(job); else queue.push(job);
            drain();
        });
    }
    function invalidate(sectionId) {
        const targets = sectionId == null ? [...sections] : [String(sectionId)];
        targets.forEach(id => {
            generations.set(id, (generations.get(id) || 0) + 1);
            entries.delete(`${id}:summary`);
            entries.delete(`${id}:full`);
            removeSection(id);
        });
    }
    function load(sectionId, options = {}) {
        const id = String(sectionId || '');
        if (!/^\d+$/.test(id)) return Promise.reject(new Error('A section ID is required'));
        const view = options.view === 'full' ? 'full' : 'summary';
        const key = `${id}:${view}`;
        sections.add(id);
        if (options.fresh) invalidate(id);
        if (entries.has(key)) return entries.get(key);
        const generation = generations.get(id) || 0;
        const promise = schedule(async () => {
            if ((generations.get(id) || 0) !== generation) throw new Error('Materials request superseded');
            const params = new URLSearchParams({ section_id: id });
            if (view === 'summary') params.set('view', view);
            const response = await fetch(`/api/class/materials/?${params}`, {
                credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' },
            });
            const payload = await response.json();
            if ((generations.get(id) || 0) !== generation) throw new Error('Materials request superseded');
            if (!response.ok || !payload.success) {
                removeSection(id);
                if ([401, 403, 404].includes(response.status)) invalidate(id);
                const error = new Error(payload.error || 'Unable to load class materials');
                error.status = response.status;
                throw error;
            }
            // Full-mode callers cannot replace the compact listing already
            // shared with badges/cards using a different storage shape.
            if (view === 'summary') store(id, payload);
            return payload;
        }, options.priority || id === requestedSection);
        entries.set(key, promise);
        promise.catch(() => {
            if (entries.get(key) === promise) entries.delete(key);
            if ((generations.get(id) || 0) === generation) removeSection(id);
        });
        return promise;
    }
    function prune(sectionIds) {
        const allowed = new Set(sectionIds.map(String));
        const cached = new Set([...sections, ...Object.keys(read(readingsKey)), ...Object.keys(read(metadataKey))]);
        cached.forEach(id => {
            if (!allowed.has(id)) { invalidate(id); sections.delete(id); }
        });
    }
    function orderedClasses(classes) {
        return [...classes].sort((a, b) =>
            Number(String(b.section_id || b.id) === requestedSection)
            - Number(String(a.section_id || a.id) === requestedSection));
    }
    async function refresh() {
        const ids = [...sections];
        invalidate();
        await Promise.allSettled(ids.map(id => load(id)));
        window.dispatchEvent(new CustomEvent('pabasa:student-class-updated'));
    }
    window.PabasaMaterials = { load, invalidate, prune, orderedClasses, refresh };

    // Persisted data is never the source for a new student's authorized listing.
    if (window.PABASA_USER_ROLE === 'student') write(readingsKey, {});
    window.addEventListener('pabasa:assessment-completed', refresh);
    window.addEventListener('pabasa:practice-completed', refresh);
    window.addEventListener('pageshow', event => { if (event.persisted) refresh(); });
})();
