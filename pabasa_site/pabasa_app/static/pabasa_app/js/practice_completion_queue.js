(function (root) {
    "use strict";
    function create(options) {
        const key = `pabasa_pending_practice_${options.studentId}`;
        let jobs = [];
        let running = null;
        try { jobs = JSON.parse(options.storage.getItem(key) || "[]"); } catch (_) { /* Keep an in-memory queue if storage is unavailable. */ }
        if (!Array.isArray(jobs)) jobs = [];
        jobs = jobs.filter(job => job && job.id && job.payload && Array.isArray(job.awards));
        function persist() {
            try { options.storage.setItem(key, JSON.stringify(jobs)); } catch (_) { /* The current page can still save online. */ }
        }
        async function post(url, payload) {
            const response = await options.fetch(url, {
                method: "POST", credentials: "same-origin", keepalive: true,
                headers: { "Accept": "application/json", "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": options.csrf() },
                body: JSON.stringify(payload),
            });
            let data;
            try { data = JSON.parse(await response.text()); } catch (_) { data = {}; }
            if (!response.ok || !data.success) {
                const error = new Error(response.status === 401 || response.status === 403
                    ? "Sign in again, then reopen Practice to save your result."
                    : "Your result is waiting to be saved. Check your connection and retry.");
                error.retryable = response.status === 408 || response.status === 429 || response.status >= 500;
                throw error;
            }
            return data;
        }
        function flush() {
            if (running) return running;
            running = (async () => {
                const attempted = new Set();
                let pendingMessage;
                while (true) {
                    const job = jobs.find(item => !attempted.has(item.id));
                    if (!job) break;
                    attempted.add(job.id);
                    let saved = false;
                    for (let attempt = 0; attempt < 3 && !saved; attempt++) {
                        options.onStatus?.("saving");
                        try {
                            // Word deposits use their original attempt/idempotency keys.
                            // Retrying a lost response cannot credit stars twice.
                            for (const award of job.awards) await post("/api/practice/hunt/award-stars/", award);
                            const result = await post("/record-assessment-completion/", job.payload);
                            if (job.huntCompletion) {
                                const totals = await post("/api/practice/hunt/award-stars/", job.huntCompletion);
                                options.onHuntTotals?.(totals, job);
                            }
                            jobs = jobs.filter(item => item.id !== job.id);
                            persist();
                            options.onSaved?.(result, job);
                            saved = true;
                        } catch (error) {
                            const retryable = error.retryable !== false;
                            if (retryable && attempt < 2) await options.delay(1000);
                            else { pendingMessage = error.message; break; }
                        }
                    }
                }
                if (!jobs.length) options.onStatus?.("saved");
                else options.onStatus?.("pending", pendingMessage);
                return jobs.length === 0;
            })().finally(() => { running = null; });
            return running;
        }
        return {
            enqueue(job) {
                if (!jobs.some(item => item.id === job.id)) {
                    // Snapshot before a navigation or restart can alter reader state.
                    const snapshot = JSON.parse(JSON.stringify(job));
                    snapshot.payload.student_id = options.studentId;
                    jobs.push(snapshot);
                    persist();
                }
                return flush();
            },
            flush,
            pending: () => jobs.length,
        };
    }
    if (typeof module === "object" && module.exports) module.exports = { create };
    else root.PracticeCompletionQueue = { create };
})(typeof window === "object" ? window : globalThis);
