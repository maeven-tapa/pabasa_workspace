/* Extend the section's existing one-second roster poll; no other feed is needed. */
document.addEventListener('DOMContentLoaded', function () {
    const section = document.querySelector('.section-information-students[data-section-id]');
    const body = section?.querySelector('.student-table tbody');
    const cards = section?.querySelector('.student-cards');
    if (!body || !cards) return;
    const sectionId = section.dataset.sectionId;
    const count = document.getElementById('enrolledStudentCount');
    const calendar = document.getElementById('sectionCalendar');
    const error = document.getElementById('studentSyncError');
    const retry = document.getElementById('studentSyncRetry');
    const levelClasses = {
        'Low Emerging Readers': 'level-low', 'High Emerging Readers': 'level-high',
        'Developing Readers': 'level-developing', 'Transitioning Readers': 'level-transitioning',
        'Readers at Grade Level': 'level-grade', 'Reading At Grade Level': 'level-grade',
        'Low Emerging Reader': 'level-low', 'High Emerging Reader': 'level-high',
        'Developing Reader': 'level-developing', 'Transitioning Reader': 'level-transitioning',
    };
    let rosterVersion = section.dataset.rosterVersion || '';
    let calendarScope = section.dataset.calendarScope || '';
    let lastCalendarCheck = 0;
    let controller = null;
    let generation = 0;
    let pending = false;
    let rosterFailed = false;
    let calendarFailed = false;

    function showSyncState() {
        error.textContent = rosterFailed || calendarFailed ? 'Updates unavailable. Displayed data may be out of date.' : '';
        retry.hidden = !(rosterFailed || calendarFailed);
    }
    function styleLevels() {
        section.querySelectorAll('.reading-level-chip').forEach(chip => {
            const next = `status-chip reading-level-chip ${levelClasses[chip.dataset.readingLevel] || 'level-pending'}`;
            if (chip.className !== next) chip.className = next;
        });
    }
    function reconcile(container, selector, students, field) {
        const existing = new Map();
        let changed = false;
        container.querySelectorAll(selector).forEach(node => {
            const id = node.dataset.studentId;
            if (!students.has(id) || existing.has(id)) { node.remove(); changed = true; }
            else existing.set(id, node);
        });
        students.forEach((student, id) => {
            const old = existing.get(id);
            if (old?.dataset.syncVersion === student.version) return;
            const template = document.createElement('template');
            template.innerHTML = student[field].trim();
            const node = template.content.firstElementChild;
            if (!node || node.dataset.studentId !== id) throw new Error('Invalid student row');
            if (old) old.replaceWith(node);
            else container.appendChild(node);
            changed = true;
        });
        return changed;
    }
    function applyRoster(data) {
        if (data.unchanged) return;
        if (!Array.isArray(data.students)) throw new Error('Invalid roster');
        const students = new Map();
        for (const student of data.students) {
            if (!student.id || !student.version || typeof student.row_html !== 'string' || typeof student.card_html !== 'string') {
                throw new Error('Invalid student');
            }
            students.set(String(student.id), student);
        }
        if (students.size !== data.total_students) throw new Error('Invalid student count');
        let changed = reconcile(body, 'tr[data-student-id]', students, 'row_html');
        changed = reconcile(cards, '.student-card[data-student-id]', students, 'card_html') || changed;
        body.querySelectorAll('tr:not([data-student-id]):not(#studentNoResults)').forEach(node => node.remove());
        cards.querySelectorAll('.student-card:not([data-student-id])').forEach(node => node.remove());
        if (!students.size) {
            body.insertAdjacentHTML('beforeend', '<tr data-enrollment-empty><td colspan="6" class="text-center py-4 text-muted">No students have joined yet.</td></tr>');
            cards.insertAdjacentHTML('beforeend', '<div class="student-card text-muted" data-enrollment-empty>No students have joined yet.</div>');
        }
        styleLevels();
        if (changed) window.refreshStudentDirectory?.();
    }
    async function syncEnrollmentRows() {
        if (document.hidden) return;
        if (controller) { pending = true; return; }
        pending = false;
        const requestGeneration = generation;
        const includeCalendar = !lastCalendarCheck || Date.now() - lastCalendarCheck >= 15000;
        const url = new URL(section.dataset.syncUrl, window.location.origin);
        url.search = new URLSearchParams({section_id: sectionId, sync: 'management', roster_version: rosterVersion, calendar_scope: calendarScope,
            ...(includeCalendar ? {include_calendar: '1'} : {})});
        controller = new AbortController();
        const timeout = setTimeout(() => controller?.abort(), 8000);
        try {
            const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
                headers: {'Accept': 'application/json'}});
            const data = await response.json();
            if (requestGeneration !== generation || document.hidden) return;
            if (!response.ok || !data.success || String(data.section_id) !== sectionId ||
                typeof data.roster_version !== 'string' || !Number.isInteger(data.total_students)) {
                throw new Error('Invalid section response');
            }
            if (includeCalendar && (!data.calendar || typeof data.calendar.label !== 'string')) throw new Error('Missing calendar');
            if (data.calendar && (typeof data.calendar.scope !== 'string' || typeof data.calendar.label !== 'string')) throw new Error('Invalid calendar');
            applyRoster(data);
            rosterVersion = data.roster_version;
            const label = `${data.total_students} enrolled`;
            if (count.textContent !== label) count.textContent = label;
            if (data.calendar) {
                if (calendar.textContent !== data.calendar.label) calendar.textContent = data.calendar.label;
                calendarScope = data.calendar.scope;
                lastCalendarCheck = Date.now();
                calendarFailed = false;
            }
            rosterFailed = false;
            showSyncState();
        } catch (failure) {
            if (requestGeneration !== generation || document.hidden) return;
            rosterFailed = true;
            if (includeCalendar) { calendarFailed = true; lastCalendarCheck = Date.now(); }
            showSyncState();
        } finally {
            clearTimeout(timeout);
            controller = null;
            if (pending && !document.hidden) { pending = false; syncEnrollmentRows(); }
        }
    }
    function refreshNow() {
        generation++;
        rosterVersion = '';
        lastCalendarCheck = 0;
        pending = true;
        controller?.abort();
        syncEnrollmentRows();
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { generation++; controller?.abort(); }
        else refreshNow();
    });
    window.addEventListener('pagehide', () => { generation++; controller?.abort(); });
    for (const event of ['studentAdded', 'studentEnrollmentChanged', 'pabasa:assessment-completed']) {
        window.addEventListener(event, refreshNow);
    }
    retry.addEventListener('click', refreshNow);
    styleLevels();
    syncEnrollmentRows();
    window.setInterval(syncEnrollmentRows, 1000);
});
