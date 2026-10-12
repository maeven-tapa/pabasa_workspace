// Both term selectors follow the calendar until that selector is changed by the teacher.
let studentDirectoryActionsAvailable = false;
let studentDirectorySyncBusy = false;
let studentDirectorySyncQueued = false;
let studentDirectoryCalendar = null;
let studentAralRenderedScope = '';
const studentAralModalIds = ['aralStoryPerformanceModal', 'aralExitStudentsModal', 'aralReviewStudentsModal', 'aralExitHistoryModal'];

function selectStudentReviewTerm(wrap, term, manual = false) {
    if (!wrap) return;
    const value = String(term || '');
    if (!manual && wrap.dataset.value === value) return;
    const option = wrap.querySelector(`.student-filter-option[data-value="${value}"]`);
    wrap.dataset.value = option ? value : '';
    wrap.dataset.assessment = option?.dataset.assessment || '';
    wrap.querySelector('.student-filter-value').textContent = option?.querySelector('.student-filter-option-title').textContent.trim() || 'No Active Term';
    wrap.querySelectorAll('.student-filter-option').forEach(item => {
        item.classList.toggle('is-selected', item === option);
        item.setAttribute('aria-selected', item === option ? 'true' : 'false');
    });
    const input = wrap.querySelector('input[name="aral_term"]');
    if (input) input.value = wrap.dataset.value;
    wrap.classList.remove('is-open');
    wrap.querySelector('.student-filter-trigger').setAttribute('aria-expanded', 'false');
    if (manual) {
        wrap.dataset.manual = 'true';
        ++studentDirectoryRequestId; // Ignore a response for the previous selection.
        if (wrap.id === 'assessmentPeriodFilterWrap') {
            studentDirectoryActionsAvailable = false;
            updateCrlaFinalizationUi(null);
            document.querySelectorAll('.student-crla-observation-level').forEach(select => { select.disabled = true; });
        }
        const actionModal = document.getElementById('teacherAralActionModal');
        if (actionModal && window.bootstrap?.Modal) bootstrap.Modal.getInstance(actionModal)?.hide();
    }
}

function studentAralActionAllowed(button) {
    if (button.dataset.aralAction === 'move') return studentDirectoryActionsAvailable;
    const wrap = document.getElementById('aralTermSelect');
    return Boolean(wrap && !wrap.dataset.stale && wrap.dataset.value && Number(wrap.dataset.value) === studentDirectoryCalendar?.term);
}

function studentAralScope(calendar, term, sectionId) {
    return `${calendar?.scope || ''}:${term || ''}:${sectionId || ''}`;
}

async function refreshStudentAralTerm(calendar) {
    const wrap = document.getElementById('aralTermSelect');
    if (!wrap) return;
    const automatic = wrap.dataset.manual !== 'true';
    const selectedTerm = automatic ? ([1, 2, 3].includes(calendar.term) ? calendar.term : '') : wrap.dataset.value;
    const scope = studentAralScope(calendar, selectedTerm, studentDirectorySectionId);
    if (scope === studentAralRenderedScope) return;
    wrap.dataset.stale = 'true';
    document.querySelectorAll('.aral-ready-exit-action, .aral-review-all-action').forEach(button => { button.disabled = true; });
    const revision = studentDirectoryRequestId;
    const params = new URLSearchParams({ partial: 'aral' });
    if (selectedTerm) params.set('aral_term', selectedTerm);
    const response = await fetch(`/dashboard/students/?${params}`, { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error('Could not refresh the selected ARAL term.');
    const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (revision !== studentDirectoryRequestId) return;
    const incoming = parsed.getElementById('aralTermRegion');
    if (!incoming || incoming.dataset.calendarScope !== calendar.scope) {
        studentDirectorySyncQueued = true;
        return;
    }
    // Keep existing modal nodes and their listeners; only their selected-term contents change.
    studentAralModalIds.forEach(id => {
        const existing = document.getElementById(id);
        const replacement = parsed.getElementById(id);
        if (existing && replacement) {
            window.bootstrap?.Modal?.getInstance(existing)?.hide();
            document.body.appendChild(existing);
            if (id === 'aralStoryPerformanceModal') {
                existing.querySelector('.modal-context').textContent = replacement.querySelector('.modal-context').textContent;
                existing.querySelector('.modal-body').replaceChildren();
            } else {
                existing.querySelector('.modal-content').innerHTML = replacement.querySelector('.modal-content').innerHTML;
            }
            replacement.remove();
        }
    });
    incoming.querySelector('#aralTermSelect').dataset.manual = automatic ? 'false' : 'true';
    const region = document.getElementById('aralTermRegion');
    region.replaceChildren(...incoming.childNodes);
    region.dataset.calendarScope = calendar.scope;
    studentAralRenderedScope = scope;
    bindStudentDirectoryFilters();
}

// Reuses the Students page's existing 30-second poll, focus refresh, and visibility refresh.
async function refreshStudentOverview() {
    if (document.hidden) return;
    if (studentDirectorySyncBusy) {
        studentDirectorySyncQueued = true;
        return;
    }
    studentDirectorySyncBusy = true;
    const revision = studentDirectoryRequestId;
    try {
        const wrap = document.getElementById('assessmentPeriodFilterWrap');
        const automatic = wrap?.dataset.manual !== 'true';
        const params = new URLSearchParams({ sync: 'directory', term_mode: automatic ? 'auto' : 'manual' });
        if (wrap?.dataset.value) params.set('term', wrap.dataset.value);
        if (studentDirectorySectionId) params.set('section_id', studentDirectorySectionId);
        const response = await fetch(`/dashboard/teacher/students-api/?${params}`, {
            credentials: 'same-origin', cache: 'no-store', headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.ok) throw new Error('Could not refresh student term data.');
        const data = await response.json();
        if (revision !== studentDirectoryRequestId) return;
        if (!data.success || !data.directory_terms) throw new Error('Student term data is unavailable.');
        const terms = data.directory_terms;
        studentDirectorySectionId = terms.section_id;
        studentDirectoryCalendar = terms.calendar;
        if (automatic) selectStudentReviewTerm(wrap, terms.term);
        await refreshStudentAralTerm(terms.calendar);
        if (revision !== studentDirectoryRequestId) return;
        studentDirectoryActionsAvailable = terms.actions_available;
        const students = normalizeStudentPayload(data.students);
        latestStudentDirectoryTotal = Number(data.total_students);
        latestStudentDirectoryStudents = buildStudentDirectoryProjection(students);
        window.latestDashboardMetrics = data.dashboard_metrics || {};
        updateCrlaFinalizationUi(data.crla || null);
        updateStudentStatistics(latestStudentDirectoryStudents, data.level_counts, data.total_students);
        renderStudentDirectory(latestStudentDirectoryStudents);
        if (!terms.term) document.getElementById('crlaFinalizationStatus').textContent = 'No Active Term';
    } catch (error) {
        if (revision === studentDirectoryRequestId) {
            studentDirectoryActionsAvailable = false;
            updateCrlaFinalizationUi(null);
            document.querySelectorAll('.student-crla-observation-level').forEach(select => { select.disabled = true; });
            document.getElementById('crlaFinalizationStatus').textContent = 'Term data unavailable. Retrying…';
        }
    } finally {
        studentDirectorySyncBusy = false;
        if (studentDirectorySyncQueued) {
            studentDirectorySyncQueued = false;
            if (!document.hidden) queueMicrotask(refreshStudentOverview);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    bindStudentDirectoryFilters();
    studentDirectoryCalendar = JSON.parse(document.getElementById('studentDirectoryCalendar').textContent);
    studentAralRenderedScope = studentAralScope(studentDirectoryCalendar, document.getElementById('aralTermSelect')?.dataset.value, studentDirectorySectionId);
    studentAralModalIds.forEach(id => {
        const modal = document.getElementById(id);
        if (modal) document.body.appendChild(modal);
    });
    refreshStudentOverview();
    setInterval(refreshStudentOverview, 30000);
    window.addEventListener('focus', refreshStudentOverview);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshStudentOverview(); });
    window.addEventListener('studentAdded', refreshStudentOverview);
    window.addEventListener('pabasa:assessment-completed', refreshStudentOverview);
});
