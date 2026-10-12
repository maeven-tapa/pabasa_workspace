(() => {
    'use strict';
    let nextId = 0;
    const compactActivities = {
        'prescribed-lesson-15-gawain-3': ['SESSION 5', 'Lesson 15 · Gawain 3'],
        'prescribed-session-5-lesson-14-gawain-4': ['SESSION 5', 'Lesson 14 · Gawain 4'],
        'prescribed-lesson-13-gawain-1': ['SESSION 5', 'Lesson 13 · Gawain 1'],
        'prescribed-session-4-gawain-2': ['SESSION 4', 'Lessons 10, 11, at 12 · Gawain 2'],
        'prescribed-session-4-gawain-1': ['SESSION 4', 'Lessons 10, 11, at 12 · Gawain 1'],
        'prescribed-lesson-29-gawain-3': ['SESSION 13', 'Lesson 29 Activity 3 · Trace & Say'],
        'prescribed-lesson-1-gawain-1': ['SESSION 1', 'Lesson 1 · Gawain 1'],
    };
    // Retain references to the course's cached records, so reopening stays in sync.
    const reviewRecords = new Map();
    const fluencyLabels = {GREEN: '🟢 Nabasa nang maayos', YELLOW: '🟡 Nabasa pero medyo putol-putol', RED: '🔴 Hindi Nabasa'};

    function summary(reviewed, total, pending, skipped) {
        return `<div class="session5-evaluation-summary" aria-live="polite"><strong>Reading Evaluation — ${reviewed} / ${total} Reviewed</strong><span>Pending: ${pending} · Skipped: ${skipped}</span></div>`;
    }

    const tableHeader = (control = 'Classification') => `<div class="session5-fluency-header"><span>Reading Item</span><span>Student Recording</span><span>${control}</span></div>`;

    function renderFluency(items, escapeHtml) {
        const rows = items.map(item => {
            const skipped = item.classification_source === 'skipped';
            const reviewable = Boolean(item.submission_id && item.recording_url && !skipped);
            const reviewed = !skipped && item.review_status === 'reviewed';
            const value = fluencyLabels[item.classification] ? item.classification : '';
            if (item.submission_id) reviewRecords.set(String(item.submission_id), item);
            return `<div class="session5-fluency-row" data-submission-id="${escapeHtml(item.submission_id || '')}" data-review-state="${skipped ? 'skipped' : reviewed ? 'reviewed' : reviewable ? 'pending' : 'missing'}"><span class="session5-fluency-text"><strong><span class="session5-fluency-number">${Number(item.item_index) + 1}.</span> ${escapeHtml(item.expected_text || '')}</strong>${item.transcript ? `<small>${escapeHtml(item.transcript)}</small>` : ''}</span><span class="session5-fluency-audio">${item.recording_url ? `<audio controls preload="metadata" src="${escapeHtml(item.recording_url)}" aria-label="Student recording: ${escapeHtml(item.expected_text || '')}"></audio>` : '<span class="text-muted">No recording</span>'}</span><span class="reading-review-classification">${skipped ? '<strong class="reading-review-red">🔴 Hindi Nabasa</strong><small class="session5-review-state">Nilaktawan · Awtomatiko</small>' : reviewable ? `<select class="form-select form-select-sm session5-fluency-select" aria-label="Classification: ${escapeHtml(item.expected_text || '')}" data-previous-value="${value}"><option value="" ${!value ? 'selected' : ''}>Naghihintay ng pagsusuri</option>${Object.entries(fluencyLabels).map(([code, label]) => `<option value="${code}" ${value === code ? 'selected' : ''}>${label}</option>`).join('')}</select><small class="session5-review-state">${reviewed ? 'reviewed' : 'pending'}</small>` : '<span class="reading-review-neutral">Wala pang pagbasa</span>'}</span></div>`;
        }).join('');
        return `<div class="compact-reading-review">${summary(0, items.length, 0, 0)}<div class="session5-fluency-table reading-review-list">${tableHeader()}${rows}</div></div>`;
    }

    function renderLetterScores(items, activityId, studentId, escapeHtml) {
        const rows = items.map((item, index) => {
            const reviewable = Boolean(item.submission_id && item.recording_available && item.audio_url);
            const reviewed = item.teacher_score === 0 || item.teacher_score === 1;
            if (item.submission_id) reviewRecords.set(String(item.submission_id), item);
            return `<div class="session4-letter-recording" data-submission-id="${escapeHtml(item.submission_id || '')}" data-session4-activity="${escapeHtml(activityId)}" data-session4-student-id="${escapeHtml(studentId)}" data-review-state="${reviewed ? 'reviewed' : reviewable ? 'pending' : 'missing'}"><span class="session5-fluency-text"><strong><span class="session5-fluency-number">${index + 1}.</span> ${escapeHtml(item.item_label || '')}</strong></span><span class="session5-fluency-audio">${reviewable ? `<audio class="session4-native-audio" controls preload="metadata" src="${escapeHtml(item.audio_url)}" aria-label="Student recording: ${escapeHtml(item.item_label || '')}"></audio>` : '<span class="session4-no-recording">No recording</span>'}</span><span class="reading-review-classification">${reviewable ? `<span class="session4-score-controls" role="group" aria-label="Teacher score for ${escapeHtml(item.item_label || '')}"><button type="button" class="session4-score-button${item.teacher_score === 0 ? ' selected' : ''}" data-score="0">Incorrect — 0</button><button type="button" class="session4-score-button${item.teacher_score === 1 ? ' selected' : ''}" data-score="1">Correct — 1</button></span><span class="session4-score-feedback" aria-live="polite"></span>` : '<span class="reading-review-neutral">Wala pang pagbasa</span>'}</span></div>`;
        }).join('');
        return `<div class="compact-reading-review">${summary(0, items.length, 0, 0)}<div class="session4-recording-list reading-review-list">${tableHeader('Teacher Score')}${rows}</div></div>`;
    }

    function renderSingleRecording(attempt, audioControls, escapeHtml) {
        const available = Boolean(attempt?.recording_available && attempt?.recording_url);
        const reviewed = attempt?.status === 'checked';
        const status = reviewed ? 'Reviewed' : attempt?.status === 'retry' ? 'Retry requested' : available ? 'Pending review' : 'No recording';
        return `<div class="compact-reading-review">${summary(reviewed ? 1 : 0, 1, available && !reviewed ? 1 : 0, 0)}<div class="reading-review-list">${tableHeader('Review Status')}<div class="session5-fluency-row single-recording-review-row" data-review-state="${reviewed ? 'reviewed' : available ? 'pending' : 'missing'}"><span class="session5-fluency-text"><strong><span class="session5-fluency-number">1.</span> Reading recording</strong></span><span class="session5-fluency-audio">${audioControls}</span><span class="reading-review-classification"><span class="single-recording-review-status">${escapeHtml(status)}</span></span></div></div></div>`;
    }

    function updateSingleReview(recording, status) {
        const row = recording?.querySelector('.single-recording-review-row');
        if (!row) return;
        row.dataset.reviewState = status === 'checked' ? 'reviewed' : 'pending';
        row.querySelector('.single-recording-review-status').textContent = status === 'checked' ? 'Reviewed' : 'Retry requested';
        refreshSummary(recording);
    }

    function refreshSummary(root) {
        const review = root?.matches('.compact-reading-review') ? root : root?.querySelector('.compact-reading-review');
        if (!review) return;
        const rows = [...review.querySelectorAll('[data-review-state]')];
        const count = state => rows.filter(row => row.dataset.reviewState === state).length;
        const old = review.querySelector('.session5-evaluation-summary');
        old.outerHTML = summary(count('reviewed'), rows.length, count('pending'), count('skipped'));
    }

    function markReviewed(row, values) {
        if (!row?.closest('.compact-reading-review') || row.dataset.reviewState === 'skipped') return;
        const item = reviewRecords.get(row.dataset.submissionId);
        if (item) Object.assign(item, values);
        row.dataset.reviewState = 'reviewed';
        refreshSummary(row.closest('.compact-reading-review'));
    }

    function order(task) {
        const title = String(task.title || '');
        const label = String(task.activityLabel || '');
        const number = (value, pattern) => Number(String(value).match(pattern)?.[1] || Infinity);
        return [number(label, /session\s*(\d+)/i), number(title, /lessons?\s*(\d+)/i),
            number(title, /(?:activity|gawain)\s*(\d+)/i)];
    }

    function compareTasks(a, b) {
        const left = order(a), right = order(b);
        for (let index = 0; index < left.length; index++) {
            if (left[index] !== right[index]) return left[index] < right[index] ? -1 : 1;
        }
        return String(a.title || '').localeCompare(String(b.title || ''), undefined,
            {numeric: true, sensitivity: 'base'});
    }

    function stopAudio(dialog) {
        dialog.querySelectorAll('audio').forEach(audio => audio.pause());
        document.dispatchEvent(new Event('pabasa:stop-student-progress-audio'));
    }

    function closeAll(root) {
        root.querySelectorAll('.student-progress-review-dialog[open]').forEach(dialog => dialog.close());
    }

    function removeRecording(recording) {
        if (!recording) return;
        const dialog = recording.closest('.student-progress-review-dialog');
        if (!dialog) { recording.remove(); return; }
        const card = dialog.closest('.student-progress-card');
        const wasOpen = dialog.open;
        stopAudio(dialog);
        if (wasOpen) dialog.close();
        card?.querySelector(`[aria-controls="${dialog.id}"]`)?.remove();
        dialog.remove();
        if (wasOpen && card?.isConnected) {
            card.tabIndex = -1;
            card.focus({preventScroll: true});
        }
    }

    async function availability(url, studentId, activityId) {
        if (!url || !studentId) throw new Error('Review availability could not be checked. Refresh student progress and try again.');
        const endpoint = new URL(url, window.location.href);
        endpoint.searchParams.set('student_id', studentId);
        if (activityId !== undefined) endpoint.searchParams.set('activity_id', activityId);
        const response = await fetch(endpoint, {credentials: 'same-origin', cache: 'no-store',
            headers: {'X-Requested-With': 'XMLHttpRequest'}});
        const data = await response.json();
        if (!response.ok || !data.success || !data.completed || typeof data.completed !== 'object') {
            throw new Error('Review availability could not be checked. Refresh student progress and try again.');
        }
        return data.reviewable || data.completed;
    }

    function mount(root, options = {}) {
        root.querySelectorAll('.student-progress-card').forEach(card => {
            const recording = card.querySelector('.student-progress-recording');
            if (!recording || card.querySelector('.student-progress-review-dialog')) return;
            const dialog = document.createElement('dialog');
            dialog.className = 'student-progress-review-dialog';
            const compactIdentity = compactActivities[card.dataset.reviewActivity];
            if (compactIdentity) dialog.classList.add('student-progress-review-dialog--compact-reading');
            dialog.id = `student-progress-review-${++nextId}`;
            dialog.setAttribute('aria-labelledby', `${dialog.id}-title`);
            dialog.setAttribute('closedby', 'none');
            const header = document.createElement('header');
            header.className = 'student-progress-review-header';
            const identity = document.createElement('div');
            const label = document.createElement('small');
            label.textContent = compactIdentity?.[0] || card.querySelector('.student-progress-type')?.textContent || '';
            const title = document.createElement('h2');
            title.id = `${dialog.id}-title`;
            title.textContent = compactIdentity?.[1] || card.querySelector('.student-progress-title')?.textContent || 'Activity recordings';
            identity.append(label, title);
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'student-progress-review-close';
            close.textContent = '×';
            close.setAttribute('aria-label', 'Close recording review');
            close.addEventListener('click', () => dialog.close());
            header.append(identity, close);
            const body = document.createElement('div');
            body.className = 'student-progress-review-body';
            const trigger = document.createElement('button');
            trigger.type = 'button';
            trigger.className = 'student-progress-review-trigger';
            trigger.setAttribute('aria-haspopup', 'dialog');
            trigger.setAttribute('aria-controls', dialog.id);
            const itemCount = recording.querySelectorAll('.session4-letter-recording, .session5-fluency-row').length;
            trigger.innerHTML = '<span><strong>Review recordings</strong><small></small></span><span aria-hidden="true">→</span>';
            trigger.querySelector('small').textContent = itemCount
                ? `${itemCount} items · Open to listen and review`
                : 'Open to listen and review';
            // Capture identity and server snapshot in the closure, not mutable DOM attributes.
            const activityId = card.dataset.reviewActivity;
            const prescribed = card.dataset.reviewPrescribed === 'true';
            let completed = !prescribed || options.completed?.[activityId] === true;
            let checking = false;
            const enabledDescription = trigger.querySelector('small').textContent;
            const updateAvailability = () => {
                trigger.disabled = !completed || checking;
                trigger.setAttribute('aria-disabled', String(trigger.disabled));
                trigger.querySelector('small').textContent = completed
                    ? enabledDescription : 'Available after activity completion';
            };
            updateAvailability();
            recording.before(trigger);
            body.append(recording);
            if (compactIdentity) refreshSummary(recording);
            dialog.append(header, body);
            card.append(dialog);
            trigger.addEventListener('click', async () => {
                if (!completed || checking) { updateAvailability(); return; }
                checking = true;
                updateAvailability();
                trigger.setAttribute('aria-busy', 'true');
                try {
                    if (prescribed) {
                        const latest = await availability(options.url, options.studentId, activityId);
                        completed = latest[activityId] === true;
                    }
                    if (!completed || !trigger.isConnected) return;
                    stopAudio(dialog);
                    dialog.showModal();
                    close.focus();
                } catch (error) {
                    options.onError?.(error.message);
                } finally {
                    checking = false;
                    trigger.removeAttribute('aria-busy');
                    updateAvailability();
                }
            });
            dialog.addEventListener('close', () => {
                stopAudio(dialog);
                if (trigger.isConnected) trigger.focus({preventScroll: true});
            });
            dialog.addEventListener('keydown', event => {
                // Keep Escape from dismissing the course parent.
                if (event.key === 'Escape') event.stopPropagation();
            });
            dialog.addEventListener('cancel', event => {
                // Also prevent native dismissal in browsers without closedby support.
                event.preventDefault();
                event.stopPropagation();
            });
        });
    }

    window.StudentActivityReview = {compareTasks, mount, availability, closeAll, removeRecording,
        renderFluency, renderLetterScores, renderSingleRecording, updateSingleReview, refreshSummary, markReviewed};
})();
