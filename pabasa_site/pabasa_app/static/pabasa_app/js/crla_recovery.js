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
    const recoveryDebug = (event, details = {}) => console.warn('LIVE_CRLA_RECOVERY_DEBUG', event, details);
    const recoveryModalDebug = (event, details = {}) => console.warn('LIVE_CRLA_RECOVERY_MODAL_DEBUG', event, details);
    const recoveryCompleteDebug = (event, details = {}) => console.warn('LIVE_CRLA_RECOVERY_COMPLETE_DEBUG', event, details);
    recoveryDebug('script_loaded', { database: DB_NAME, store: STORE });

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
    function discardMarker(sessionId) { return `pabasa-crla-recovery-discarded:${clean(sessionId)}`; }
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
        recoveryDebug('indexeddb_delete_start', { contextKey: contextKey(context), sessionKey: key, session_id: clean(context.sessionId) });
        clearTimeout(saveTimers.get(key));
        saveTimers.delete(key);
        // Invalidate any queued completion/status callback before deleting.
        writeRevisions.set(key, (writeRevisions.get(key) || 0) + 1);
        lastFingerprints.delete(key);
        return transaction('readwrite', store => store.delete(key)).then(result => {
            recoveryDebug('indexeddb_delete_complete', { contextKey: contextKey(context), sessionKey: key, session_id: clean(context.sessionId) });
            return result;
        }).catch(error => {
            recoveryDebug('indexeddb_delete_failed', { contextKey: contextKey(context), sessionKey: key, session_id: clean(context.sessionId), message: String(error?.message || error) });
            throw error;
        });
    }
    function draftsFor(context) {
        const key = contextKey(context);
        return transaction('readonly', store => store.index('contextKey').getAll(key)).then(rows => {
            const drafts = (rows || []).filter(row => row && row.schemaVersion === SCHEMA_VERSION && row.teacherId === clean(context.teacherId));
            recoveryDebug('indexeddb_lookup_complete', {
                contextKey: key,
                teacherId: clean(context.teacherId),
                draft_count: drafts.length,
                drafts: drafts.map(row => ({ sessionKey: row.sessionKey, session_id: row.sessionId, lastUpdatedAt: row.lastUpdatedAt })),
            });
            return drafts;
        });
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
        recoveryModalDebug('modal_created', { session_id: draft.sessionId, sessionKey: draft.sessionKey });
        recoveryCompleteDebug('modal_displayed', { session_id: draft.sessionId, draft_status: draft.sessionState?.status });
        recoveryDebug('recovery_modal_display', { session_id: draft.sessionId, sessionKey: draft.sessionKey, contextKey: draft.contextKey });
        const root = document.createElement('div');
        root.className = 'assessment-confirm-modal is-visible';
        root.setAttribute('role', 'presentation');
        root.setAttribute('aria-hidden', 'false');
        root.style.cssText = 'display:flex;position:fixed;inset:0;z-index:25000;align-items:center;justify-content:center;padding:1rem;background:rgba(15,23,42,.28)';
        const style = document.createElement('style');
        style.textContent = '.assessment-confirm-dialog{width:min(100%,30rem);max-width:30rem;border:1px solid #dbe8f5;border-radius:22px;background:#fff;color:#17324d;box-shadow:0 24px 70px rgba(28,73,110,.2)}.assessment-confirm-body{position:relative;padding:1.6rem}.assessment-confirm-icon{display:inline-flex;align-items:center;justify-content:center;width:2.8rem;height:2.8rem;margin-bottom:1rem;border-radius:14px;background:#e8f4ff;color:#2875b8;font-size:1.25rem}.assessment-confirm-title{margin:0 0 .55rem;font-size:1.35rem;font-weight:800;color:#17324d}.assessment-confirm-copy{margin:0;color:#526b82;line-height:1.55}.assessment-confirm-actions{display:flex;justify-content:flex-end;gap:.65rem;margin-top:1.4rem}.assessment-confirm-actions button{min-width:6.5rem;border-radius:10px;font-weight:700}.assessment-confirm-cancel{border:1px solid #b8c9d8;color:#38546d;background:#fff}.assessment-confirm-submit{border:0;background:#2875b8;color:#fff}.assessment-confirm-close{position:absolute;top:.75rem;right:.8rem;width:2rem;height:2rem;padding:0;border:0;border-radius:8px;color:#526b82;background:transparent;font-size:1.35rem;line-height:1}.assessment-confirm-close:hover,.assessment-confirm-close:focus-visible{color:#17324d;background:#eef6fc}';
        root.innerHTML = `<div class="assessment-confirm-dialog" style="position:relative;z-index:25001"><div class="assessment-confirm-body"><button class="assessment-confirm-close" type="button" aria-label="Close" data-close>&times;</button><span class="assessment-confirm-icon" aria-hidden="true"><i class="bi bi-book-half"></i></span><h2 class="assessment-confirm-title">Saved Reading Session</h2><p class="assessment-confirm-copy">Your student has saved reading progress from an earlier session.</p><p class="assessment-confirm-copy" style="margin-top:.75rem">Would you like to continue where they stopped?</p><div class="assessment-confirm-actions"><button class="btn assessment-confirm-cancel" data-discard>Discard</button><button class="btn assessment-confirm-submit" data-resume>Continue</button></div></div></div>`;
        document.head.appendChild(style);
        root.querySelector('[data-close]').onclick = () => root.remove();
        const continueButton = root.querySelector('[data-resume]');
        const discardButton = root.querySelector('[data-discard]');
        recoveryModalDebug('buttons_created', {
            session_id: draft.sessionId,
            continue_found: Boolean(continueButton),
            discard_found: Boolean(discardButton),
        });
        continueButton.onclick = async () => {
            recoveryModalDebug('continue_listener_attached_and_clicked', { session_id: draft.sessionId });
            recoveryDebug('continue_clicked', { session_id: draft.sessionId });
            root.remove();
            recoveryModalDebug('modal_removed_before_continue', { session_id: draft.sessionId });
            await onResume();
        };
        discardButton.onclick = async () => { recoveryDebug('discard_clicked', { session_id: draft.sessionId }); root.remove(); await onDiscard(); };
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

    async function offerRecovery(context, existingSession = null) {
        recoveryCompleteDebug('offer_recovery_start', {
            contextKey: contextKey(context), sessionKey: sessionKey(context),
            session_id: clean(context.sessionId), current_url: window.location.href,
        });
        recoveryDebug('offerRecovery_start', {
            contextKey: contextKey(context),
            sessionKey: sessionKey(context),
            teacherId: clean(context.teacherId),
            sectionId: clean(context.sectionId),
            schoolCalendarId: clean(context.schoolCalendarId),
            term: clean(context.term),
            assessmentWeek: clean(context.assessmentWeek),
            assessmentPhase: clean(context.assessmentPhase),
            materialId: clean(context.materialId),
            session_id: clean(context.sessionId),
        });
        // A successful resume redirects back to this page.  Do not immediately
        // re-open the same prompt on that one redirect; an actual refresh will
        // still offer recovery again if the session remains unfinished.
        const resumeMarker = `pabasa-crla-recovery-resumed:${clean(context.sessionId)}`;
        if (sessionStorage.getItem(resumeMarker)) {
            recoveryDebug('offerRecovery_early_return', { reason: 'resume_marker', session_id: clean(context.sessionId) });
            sessionStorage.removeItem(resumeMarker);
            return false;
        }
        const existingSessionId = clean(existingSession?.id);
        if (sessionStorage.getItem(discardMarker(existingSessionId || context.sessionId))) {
            recoveryDebug('offerRecovery_early_return', { reason: 'discard_marker', session_id: existingSessionId || clean(context.sessionId) });
            sessionStorage.removeItem(discardMarker(existingSessionId || context.sessionId));
            return false;
        }
        if (existingSession?.url) {
            const serverDraft = {
                sessionId: clean(existingSession.id),
                sessionKey: `server:${clean(existingSession.id)}`,
                sessionState: {status: clean(existingSession.status)},
                controlUrl: existingSession.url,
            };
            recoveryCompleteDebug('server_session_modal_eligible', {
                session_id: serverDraft.sessionId,
                session_status: existingSession.status,
                modal_will_display: true,
            });
            recoveryModal(serverDraft,
                async () => { window.location.assign(serverDraft.controlUrl); },
                async () => {
                    const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1] || '';
                    const response = await fetch(`/api/live-assessment/session/${encodeURIComponent(serverDraft.sessionId)}/action/`, {
                        method: 'POST', credentials: 'same-origin',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                        body: JSON.stringify({action: 'abandon'}),
                    });
                    const payload = await response.json().catch(() => ({}));
                    recoveryDebug('server_discard_response', { session_id: serverDraft.sessionId, status: response.status, payload });
                    if (response.ok && payload.success) sessionStorage.setItem(discardMarker(serverDraft.sessionId), '1');
                }
            );
            return true;
        }
        let drafts;
        try { drafts = await draftsFor(context); } catch (error) { recoveryDebug('offerRecovery_early_return', { reason: 'indexeddb_lookup_failed', message: String(error?.message || error) }); console.warn('PABASA CRLA recovery unavailable', error); return false; }
        const draft = drafts.sort((a, b) => String(b.lastUpdatedAt).localeCompare(String(a.lastUpdatedAt)))[0];
        if (!draft) { recoveryDebug('offerRecovery_early_return', { reason: 'no_draft' }); return false; }
        recoveryCompleteDebug('draft_selected', {
            session_id: draft.sessionId, draft_status: draft.sessionState?.status,
            student_ids: draft.studentIds, contextKey: draft.contextKey,
        });
        recoveryDebug('draft_selected', { contextKey: draft.contextKey, sessionKey: draft.sessionKey, session_id: draft.sessionId, draft_status: draft.sessionState?.status });
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
            const validationPath = `/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/recovery-validation/?${query}`;
            recoveryDebug('validation_request_start', { path: validationPath, session_id: draft.sessionId });
            const response = await fetch(validationPath, { credentials: 'same-origin', cache: 'no-store' });
            recoveryCompleteDebug('validation_response_received', { session_id: draft.sessionId, status: response.status });
            recoveryDebug('validation_http_response', { path: validationPath, status: response.status, ok: response.ok, session_id: draft.sessionId });
            const payload = await response.json().catch(error => {
                recoveryDebug('validation_json_parse_failed', { path: validationPath, status: response.status, session_id: draft.sessionId, message: String(error?.message || error) });
                throw error;
            });
            validation = payload;
            recoveryCompleteDebug('validation_decision_input', {
                session_id: draft.sessionId, status: response.status,
                session_missing: payload.session_missing === true,
                conclusively_invalid: payload.conclusively_invalid === true,
                session_status: payload.session_status,
                requires_reactivation: payload.requires_reactivation,
                payload,
            });
            recoveryDebug('validation_response', {
                path: `/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/recovery-validation/`,
                status: response.status,
                session_missing: payload.session_missing === true,
                conclusively_invalid: payload.conclusively_invalid === true,
                session_status: payload.session_status,
                requires_reactivation: payload.requires_reactivation,
                payload,
            });
            // A 404 with the explicit session_missing marker means this draft
            // points to a deleted/reset backend transport. Remove only this
            // orphaned browser draft; preserve it for every other failure or
            // inconclusive response so a valid recovery is never lost.
            if (response.status === 404 && payload.session_missing === true) {
                recoveryDebug('orphan_cleanup_condition', { http_404: true, session_missing: true, session_id: draft.sessionId });
                await deleteDraft({ ...context, sessionId: draft.sessionId });
                recoveryDebug('orphan_cleanup_complete', { session_id: draft.sessionId });
                return false;
            }
            if (response.ok && payload.conclusively_invalid) {
                recoveryDebug('validation_conclusive_invalid', { session_id: draft.sessionId, payload });
                await transaction('readwrite', store => store.delete(draft.sessionKey));
                return false;
            }
        } catch (_) {
            recoveryDebug('validation_error_preserve_draft', { session_id: draft.sessionId });
            recoveryCompleteDebug('validation_inconclusive_preserve_draft', { session_id: draft.sessionId });
            // Network loss must not delete a recovery draft. It can be resumed when the server is reachable.
        }
        recoveryCompleteDebug('recovery_modal_eligible', {
            session_id: draft.sessionId,
            validation,
            draft_status: draft.sessionState?.status,
            modal_will_display: true,
        });
        // Recovery has now been detected. Freeze the existing transport before
        // displaying the modal so its decision time is never charged to a
        // student's active elapsed_seconds.
        try {
            recoveryDebug('interrupt_request_start', { session_id: draft.sessionId });
            const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1] || '';
            const interruptResponse = await fetch(`/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/action/`, {
                method: 'POST', credentials: 'same-origin', keepalive: true,
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                body: JSON.stringify({action: 'interrupt'}),
            });
            recoveryDebug('interrupt_request_complete', { session_id: draft.sessionId, status: interruptResponse.status });
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
                    const recoverPath = `/api/live-assessment/session/${encodeURIComponent(draft.sessionId)}/action/`;
                    recoveryModalDebug('continue_request_start', { session_id: draft.sessionId, url: recoverPath, action: 'recover' });
                    const response = await fetch(recoverPath, {
                        method: 'POST', credentials: 'same-origin',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': token, 'Accept': 'application/json'},
                        body: JSON.stringify({action: 'recover'}),
                    });
                    const payload = await response.json().catch(() => ({}));
                    recoveryModalDebug('continue_request_response', { session_id: draft.sessionId, url: recoverPath, status: response.status, payload });
                    recoveryDebug('continue_response', { session_id: draft.sessionId, status: response.status, payload });
                    if (!response.ok || !payload.success) return;
                }
                sessionStorage.setItem(`pabasa-crla-recovery-resumed:${clean(draft.sessionId)}`, '1');
                recoveryModalDebug('continue_navigation', { session_id: draft.sessionId, url: draft.controlUrl || `/dashboard/live-assessment/${encodeURIComponent(draft.sessionId)}/control/` });
                recoveryDebug('continue_navigation', { session_id: draft.sessionId, url: draft.controlUrl || `/dashboard/live-assessment/${encodeURIComponent(draft.sessionId)}/control/` });
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
                recoveryDebug('discard_response', { session_id: draft.sessionId, status: response.status, payload });
                if (response.ok && payload.success) {
                    await deleteDraft({ ...context, sessionId: draft.sessionId });
                    sessionStorage.setItem(discardMarker(draft.sessionId), '1');
                    const remaining = await draftsFor(context).catch(error => ({ error: String(error?.message || error) }));
                    recoveryDebug('discard_remaining_drafts', { contextKey: contextKey(context), remaining });
                }
            });
        return true;
    }

    window.PabasaCrlaRecovery = { putDraft, deleteDraft, scheduleSave, offerRecovery, isActive };
}());
