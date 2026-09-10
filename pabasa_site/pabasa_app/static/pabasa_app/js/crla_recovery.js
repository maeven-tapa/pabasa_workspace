/* Temporary, browser-only recovery for teacher Live CRLA sessions.
 * This intentionally never writes Assessment records or calls a completion API.
 */
(function () {
    'use strict';
    const DB_NAME = 'pabasa_crla_recovery';
    const DB_VERSION = 1;
    const STORE = 'live_sessions';
    const SCHEMA_VERSION = 1;
    let dbPromise;
    const saveTimers = new Map();
    const lastFingerprints = new Map();
    const writeRevisions = new Map();

    function openDb() {
        if (!('indexedDB' in window)) return Promise.reject(new Error('IndexedDB is unavailable'));
        if (!dbPromise) dbPromise = new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                const store = db.objectStoreNames.contains(STORE)
                    ? request.transaction.objectStore(STORE)
                    : db.createObjectStore(STORE, { keyPath: 'sessionKey' });
                if (!store.indexNames.contains('contextKey')) store.createIndex('contextKey', 'contextKey', { unique: false });
                if (!store.indexNames.contains('teacherId')) store.createIndex('teacherId', 'teacherId', { unique: false });
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error || new Error('Unable to open recovery storage'));
        });
        return dbPromise;
    }

    function transaction(mode, work) {
        return openDb().then(db => new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, mode);
            const request = work(tx.objectStore(STORE));
            tx.onabort = () => reject(tx.error || new Error('Recovery storage transaction failed'));
            tx.onerror = () => reject(tx.error || new Error('Recovery storage transaction failed'));
            if (request) request.onsuccess = () => resolve(request.result);
            else tx.oncomplete = () => resolve();
        }));
    }

    const clean = value => value == null ? '' : String(value);
    function contextKey(context) {
        return [context.teacherId, context.sectionId, context.schoolCalendarId, context.term, context.assessmentWeek, context.assessmentPhase, context.materialId]
            .map(clean).join(':');
    }
    function sessionKey(context) { return `${contextKey(context)}:${clean(context.sessionId)}`; }
    function isActive(status) { return ['countdown', 'started', 'paused', 'batch_loaded'].includes(String(status || '').toLowerCase()); }

    function putDraft(context, session, recoveryRevision) {
        if (!context || !context.sessionId || !isActive(session?.status)) return Promise.resolve();
        const now = new Date().toISOString();
        const draft = {
            schemaVersion: SCHEMA_VERSION,
            sessionKey: sessionKey(context), contextKey: contextKey(context),
            teacherId: clean(context.teacherId), sectionId: clean(context.sectionId),
            schoolCalendarId: clean(context.schoolCalendarId), term: clean(context.term),
            assessmentWeek: clean(context.assessmentWeek), assessmentPhase: clean(context.assessmentPhase),
            materialId: clean(context.materialId), batchId: clean(context.sessionId), batchNumber: session.current_batch || 1,
            sessionId: clean(context.sessionId), controlUrl: clean(context.controlUrl),
            studentIds: Array.isArray(session.student_ids) ? session.student_ids.map(clean) : [],
            studentOrder: Array.isArray(session.student_ids) ? session.student_ids.map(clean) : [],
            currentStudentId: '', currentStudentIndex: 0, currentItem: '', currentStep: '',
            studentProgress: session.student_states || {}, temporaryAnswers: {}, temporaryScores: {}, currentClassificationState: {},
            sessionState: session, sessionStartedAt: session.start_at || now, lastUpdatedAt: now,
            recoveryRevision: Number(recoveryRevision) || 0,
        };
        // Keep an older delayed write from replacing a newer snapshot. This
        // also protects against callbacks completing in an unexpected order.
        return openDb().then(db => new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, 'readwrite');
            const store = tx.objectStore(STORE);
            const existingRequest = store.get(draft.sessionKey);
            existingRequest.onerror = () => reject(existingRequest.error || new Error('Unable to read recovery draft'));
            existingRequest.onsuccess = () => {
                const existing = existingRequest.result;
                if (Number(existing?.recoveryRevision || 0) > draft.recoveryRevision) return;
                store.put(draft);
            };
            tx.oncomplete = () => resolve();
            tx.onabort = () => reject(tx.error || new Error('Recovery storage transaction failed'));
            tx.onerror = () => reject(tx.error || new Error('Recovery storage transaction failed'));
        }));
    }
    function deleteDraft(context) {
        const key = sessionKey(context);
        clearTimeout(saveTimers.get(key));
        saveTimers.delete(key);
        // Invalidate any queued completion/status callback before deleting.
        writeRevisions.set(key, (writeRevisions.get(key) || 0) + 1);
        lastFingerprints.delete(key);
        return transaction('readwrite', store => store.delete(key));
    }
    function draftsFor(context) {
        return transaction('readonly', store => store.index('contextKey').getAll(contextKey(context))).then(rows =>
            (rows || []).filter(row => row && row.schemaVersion === SCHEMA_VERSION && row.teacherId === clean(context.teacherId)));
    }
    function scheduleSave(context, session, status) {
        const key = sessionKey(context);
        const fingerprint = JSON.stringify({
            status: session?.status, batch: session?.current_batch,
            students: session?.student_ids, assignments: session?.batch_assignments,
            states: session?.student_states, startAt: session?.start_at,
        });
        if (lastFingerprints.get(key) === fingerprint) return;
        lastFingerprints.set(key, fingerprint);
        const revision = (writeRevisions.get(key) || 0) + 1;
        writeRevisions.set(key, revision);
        clearTimeout(saveTimers.get(key));
        saveTimers.set(key, setTimeout(() => putDraft(context, session, revision).then(() => {
            // IndexedDB serializes read/write transactions for this store. A
            // completion from an older queued save must never claim that it
            // protected a newer state.
            if (writeRevisions.get(key) === revision) status?.('Recovery saved', false);
        }).catch(error => {
            console.warn('PABASA CRLA recovery could not be saved', error);
            if (writeRevisions.get(key) === revision) status?.('Recovery not saved', true);
        }), 250));
    }

    function recoveryModal(draft, onResume, onDiscard) {
        const root = document.createElement('div');
        root.className = 'assessment-confirm-modal is-visible';
        root.setAttribute('role', 'presentation');
        root.setAttribute('aria-hidden', 'false');
        root.style.cssText = 'display:flex;position:fixed;inset:0;z-index:25000;align-items:center;justify-content:center;padding:1rem;background:rgba(7,18,38,.68);backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px)';
        const style = document.createElement('style');
        style.textContent = '.assessment-confirm-dialog{width:min(100%,30rem);max-width:30rem;border:1px solid rgba(110,168,255,.28);border-radius:22px;background:linear-gradient(145deg,#102746,#0a1930);color:#eaf3ff;box-shadow:0 24px 70px rgba(2,10,24,.45)}.assessment-confirm-body{position:relative;padding:1.6rem}.assessment-confirm-icon{display:inline-flex;align-items:center;justify-content:center;width:2.8rem;height:2.8rem;margin-bottom:1rem;border-radius:14px;background:rgba(74,144,226,.18);color:#8fc5ff;font-size:1.25rem}.assessment-confirm-title{margin:0 0 .55rem;font-size:1.35rem;font-weight:800}.assessment-confirm-copy{margin:0;color:#bfd0e7;line-height:1.55}.assessment-confirm-actions{display:flex;justify-content:flex-end;gap:.65rem;margin-top:1.4rem}.assessment-confirm-actions button{min-width:6.5rem;border-radius:10px;font-weight:700}.assessment-confirm-cancel{border:1px solid rgba(191,208,231,.35);color:#dce9f9;background:transparent}.assessment-confirm-submit{border:0;background:#4d9bff;color:#071226}.assessment-confirm-close{position:absolute;top:.75rem;right:.8rem;width:2rem;height:2rem;padding:0;border:0;border-radius:8px;color:#bfd0e7;background:transparent;font-size:1.35rem;line-height:1}.assessment-confirm-close:hover,.assessment-confirm-close:focus-visible{color:#fff;background:rgba(255,255,255,.1)}';
        root.innerHTML = `<div class="assessment-confirm-dialog" style="position:relative;z-index:25001"><div class="assessment-confirm-body"><button class="assessment-confirm-close" type="button" aria-label="Close" data-close>&times;</button><span class="assessment-confirm-icon" aria-hidden="true"><i class="bi bi-broadcast-pin"></i></span><h2 class="assessment-confirm-title">Live CRLA Session Interrupted</h2><p class="assessment-confirm-copy">An unfinished Live CRLA assessment was found for Batch ${Number(draft.batchNumber) || 1}. The last recorded temporary progress is available for recovery.</p><p class="assessment-confirm-copy" style="margin-top:.75rem">Resume the assessment to return to the Student Monitor with the batch, students, progress, and assessment time restored.</p><div class="assessment-confirm-actions"><button class="btn assessment-confirm-cancel" data-discard>Discard Session</button><button class="btn assessment-confirm-submit" data-resume>Resume Assessment</button></div></div></div>`;
        document.head.appendChild(style);
        root.querySelector('[data-close]').onclick = () => root.remove();
        root.querySelector('[data-resume]').onclick = async () => { root.remove(); await onResume(); };
        root.querySelector('[data-discard]').onclick = async () => { root.remove(); await onDiscard(); };
        document.body.append(root);
    }

    function confirmDiscard() {
        return new Promise(resolve => {
            const root = document.createElement('div');
            root.className = 'modal';
            root.style.cssText = 'display:flex;position:fixed;inset:0;z-index:25010;align-items:center;justify-content:center;padding:1rem;background:rgba(15,23,42,.55)';
            root.innerHTML = '<div class="modal-dialog" style="width:min(100%,460px);margin:0"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Discard Session</h5></div><div class="modal-body">Discard this temporary Live CRLA session? This cannot be undone.</div><div class="modal-footer"><button class="btn btn-outline-secondary" data-cancel>Cancel</button><button class="btn btn-danger" data-confirm>Discard Session</button></div></div></div>';
            root.querySelector('[data-cancel]').onclick = () => { root.remove(); resolve(false); };
            root.querySelector('[data-confirm]').onclick = () => { root.remove(); resolve(true); };
            document.body.append(root);
        });
    }

    async function offerRecovery(context) {
        // A successful resume redirects back to this page.  Do not immediately
        // re-open the same prompt on that one redirect; an actual refresh will
        // still offer recovery again if the session remains unfinished.
        const resumeMarker = `pabasa-crla-recovery-resumed:${clean(context.sessionId)}`;
        if (sessionStorage.getItem(resumeMarker)) {
            sessionStorage.removeItem(resumeMarker);
            return false;
        }
        let drafts;
        try { drafts = await draftsFor(context); } catch (error) { console.warn('PABASA CRLA recovery unavailable', error); return false; }
        const draft = drafts.sort((a, b) => String(b.lastUpdatedAt).localeCompare(String(a.lastUpdatedAt)))[0];
        if (!draft) return false;
        // This endpoint is intentionally read-only. The normal live-state
        // endpoint can auto-end an expired session, so it is unsafe for draft
        // discovery after a brownout or expired login.
        let validation = null;
        try {
            const query = new URLSearchParams({
                section_id: clean(context.sectionId), school_calendar_id: clean(context.schoolCalendarId),
                term: clean(context.term), material_id: clean(context.materialId),
                assessment_week: clean(context.assessmentWeek), assessment_phase: clean(context.assessmentPhase),
                draft_updated_at: clean(draft.lastUpdatedAt),
            });
            const response = await fetch(`/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/recovery-validation/?${query}`, { credentials: 'same-origin', cache: 'no-store' });
            const payload = await response.json();
            validation = payload;
            if (response.ok && payload.conclusively_invalid) {
                await transaction('readwrite', store => store.delete(draft.sessionKey));
                return false;
            }
        } catch (_) {
            // Network loss must not delete a recovery draft. It can be resumed when the server is reachable.
        }
        // Recovery has now been detected. Freeze the existing transport before
        // displaying the modal so its decision time is never charged to a
        // student's active elapsed_seconds.
        try {
            const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1] || '';
            await fetch(`/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/action/`, {
                method: 'POST', credentials: 'same-origin', keepalive: true,
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                body: JSON.stringify({action: 'interrupt'}),
            });
        } catch (_) {
            // Keep the draft available; Resume will revalidate/recover once
            // connectivity returns.
        }
        recoveryModal(draft,
            async () => {
                // Always ask the server to reopen the original transport.
                // Per-student elapsed_seconds remains the saved baseline.
                {
                    const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1] || '';
                    const response = await fetch(`/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/action/`, {
                        method: 'POST', credentials: 'same-origin',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                        body: JSON.stringify({action: 'recover'}),
                    });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok || !payload.success) return;
                }
                sessionStorage.setItem(`pabasa-crla-recovery-resumed:${clean(draft.sessionId)}`, '1');
                window.location.assign(draft.controlUrl || `/dashboard/live-assessment/${encodeURIComponent(draft.sessionId)}/control/`);
            },
            async () => {
                // Use the same modal interaction pattern as the live monitor
                // instead of a browser confirm().
                const confirmed = window.PabasaLiveConfirm
                    ? await window.PabasaLiveConfirm('Discard Session', 'Discard this temporary Live CRLA session? This cannot be undone.')
                    : await confirmDiscard();
                if (!confirmed) return;
                const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1] || '';
                const response = await fetch(`/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/action/`, {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                    body: JSON.stringify({action: 'abandon'}),
                });
                const payload = await response.json().catch(() => ({}));
                if (response.ok && payload.success) await deleteDraft({ ...context, sessionId: draft.sessionId });
            });
        return true;
    }

    window.PabasaCrlaRecovery = { putDraft, deleteDraft, scheduleSave, offerRecovery, isActive };
}());
