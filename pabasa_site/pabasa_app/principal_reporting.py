"""Read-only school monitoring, using persisted official CRLA evidence.

No score is used to invent a reading profile. Percentages have an explicit
enrollment cohort; raw task scores are never treated as percentages.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
import re
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    Assessment, CalendarEvent, ClassCrlaFinalization, Enrollment, Material,
    Notification, Practice, PrescribedReadingAttempt, SchoolCalendar, Section,
    StoryReadingProgress, StoryResponseSubmission, StudentActivityProgress,
    StudentActivityRecordingSubmission, SupplementaryMaterialPublication,
    SupplementaryStudentAssignment, User,
)
from .prescribed_activity_catalog import active_prescribed_activities, LEGACY_SESSION_PROGRESS_ACTIVITIES, LEGACY_SESSION_PROGRESS_ALIASES
from .scoring import canonical_crla_classification
from .system_clock import now as system_now
from .utils.crla_results import official_crla_result_queryset, VALID_CRLA_CLASSIFICATIONS


PHASES = {'pretest': 'BoSY Pre-Test', 'midtest': 'Midline Mid-Test', 'posttest': 'EoSY Post-Test'}
KEY_PHASES = {'bosy_crla_pretest': 'pretest', 'midline_crla_midtest': 'midtest', 'eosy_crla_posttest': 'posttest'}
RGL = 'Reading At Grade Level'


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else 0


def numeric(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def mean(values):
    values = [number for value in values if (number := numeric(value)) is not None]
    return round(sum(values) / len(values), 1) if values else None


def accuracy_mean(values):
    return mean(value for value in values if (number := numeric(value)) is not None and 0 <= number <= 100)


@dataclass
class PrincipalScope:
    school_id: int | None
    calendar: object = None
    term: int | None = None
    phase: str = ''
    section_id: int | None = None
    calendars: object = ()
    start: object = None
    end: object = None
    term_windows: dict = field(default_factory=dict)

    def term_for_date(self, day):
        matches = [term for term, (start, end) in self.term_windows.items() if day and start <= day <= end]
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def resolve(cls, user, params=None):
        params = params or {}
        school_id = getattr(user, 'school_record_id', None) if user and user.role == 'principal' else None
        # Admin's explicit global compatibility view is retained; all Principal
        # requests, including unassigned accounts, remain school constrained.
        global_admin = bool(user and user.role == 'admin')
        calendars = list(SchoolCalendar.objects.order_by('-is_active', '-school_year', '-pk'))
        raw_calendar = params.get('calendar_id') or params.get('school_calendar_id')
        calendar = None
        if raw_calendar:
            calendar = next((item for item in calendars if str(item.pk) == str(raw_calendar)), None)
            if calendar is None:
                raise ValidationError('Select a valid school year.')
        elif calendars:
            # The established resolver uses configured date bounds, not the
            # stored term alone, and performs no writes.
            from .views import _selected_school_calendar
            selected, _, active = _selected_school_calendar()
            calendar = active or next((item for item in calendars if item.is_active), None) or selected
        term = str(params.get('term') or '')
        phase = str(params.get('phase') or '')
        if term and term not in {'1', '2', '3'}:
            raise ValidationError('Select Term 1, 2, or 3.')
        if phase and phase not in PHASES:
            raise ValidationError('Select a valid CRLA assessment period.')
        section_id = params.get('section_id')
        if section_id:
            if not str(section_id).isdigit():
                raise ValidationError('Select a valid section.')
            sections = Section.objects.filter(pk=section_id, school_calendar=calendar)
            if not global_admin:
                sections = sections.filter(school_id=school_id).exclude(school__isnull=True)
            if not str(section_id).isdigit() or not sections.exists():
                raise ValidationError('Section is not in the selected school and school year.')
        start = end = None
        if calendar:
            configured = list(CalendarEvent.objects.filter(school_calendar=calendar, scope='global').values('event_type', 'start_date', 'end_date', 'term'))
            starts = [e['start_date'] for e in configured if e['event_type'] == 'start_of_classes']
            ends = [e['end_date'] for e in configured if e['event_type'] == 'end_of_classes']
            starts = starts or [e['start_date'] for e in configured if e['event_type'] == 'school_opening']
            ends = ends or [e['end_date'] for e in configured if e['event_type'] == 'school_closing']
            start = min(starts) if starts else None
            end = max(ends) if ends else None
        scope = cls(school_id, calendar, int(term) if term else None, phase,
                    int(section_id) if section_id else None, calendars, start, end)
        if calendar:
            for term_number in (1, 2, 3):
                starts = [e['start_date'] for e in configured if e['term'] == term_number and e['event_type'] == 'school_opening']
                ends = [e['end_date'] for e in configured if e['term'] == term_number and e['event_type'] == 'school_closing']
                if starts and ends:
                    scope.term_windows[term_number] = (min(starts), max(ends))
        scope.global_admin = global_admin
        return scope

    def sections(self):
        qs = Section.objects.filter(school_calendar=self.calendar, grade_level='Grade 2')
        if not self.calendar or self.calendar.is_active:
            qs = qs.filter(is_active=True)
        if not self.global_admin:
            qs = qs.filter(school_id=self.school_id).exclude(school__isnull=True)
        if self.section_id:
            qs = qs.filter(pk=self.section_id)
        return qs.select_related('school', 'teacher').order_by('section', 'class_name', 'pk')

    def awaiting_enrollments(self):
        if not self.school_id:
            return Enrollment.objects.none()
        return Enrollment.objects.filter(school_id=self.school_id, school_calendar=self.calendar,
            status='awaiting_assignment', grade_level='Grade 2', student__role='student', student__is_archived=False,
            student__school_record_id=self.school_id).exclude(student__account_status='archived').select_related('student').order_by('student__last_name', 'student__first_name', 'pk')


def _phase(row):
    aliases = {'pre_test': 'pretest', 'pre-assessment': 'pretest', 'pre_assessment': 'pretest',
               'mid_test': 'midtest', 'midline': 'midtest', 'midline_assessment': 'midtest',
               'post_test': 'posttest', 'post-assessment': 'posttest', 'post_assessment': 'posttest'}
    for prefix in ('', 'source_assessment__', 'material__'):
        phase = str(row[prefix + 'system_assessment_phase'] or '').strip().lower()
        if phase in PHASES:
            return phase
        if phase in aliases:
            return aliases[phase]
        key = row[prefix + 'system_assessment_key']
        if key in KEY_PHASES:
            return KEY_PHASES[key]
    return ''


def build_principal_snapshot(user, params=None, *, include_oversight=True):
    scope = PrincipalScope.resolve(user, params)
    sections = list(scope.sections())
    section_map = {section.pk: section for section in sections}
    enrollments = list(Enrollment.objects.filter(
        section_id__in=section_map, school_calendar=scope.calendar,
        status__in=['active', 'completed'], student__role='student', student__is_archived=False,
    ).exclude(student__account_status='archived').select_related('student'))
    if not scope.global_admin:
        enrollments = [e for e in enrollments if e.school_id == scope.school_id and (
            e.student.school_record_id == scope.school_id or e.status == 'completed')]
    cohort = {e.student_id: e for e in enrollments}
    enrollment_map = {e.pk: e for e in enrollments}
    student_ids = set(cohort)
    teacher_ids = {section.teacher_id for section in sections if section.teacher_id and section.teacher.role == 'teacher'
                   and not section.teacher.is_archived and section.teacher.account_status != 'archived'
                   and (scope.global_admin or section.teacher.school_record_id == scope.school_id)}

    fields = [
        'id', 'student_id', 'source_assessment_id', 'enrollment_id', 'section_id', 'material_id',
        'title', 'code', 'assessment_type', 'attempt_status', 'completed_at', 'started_at', 'updated_at',
        'attempt_number', 'total_score', 'accuracy', 'pronunciation_score', 'wpm', 'crla_classification', 'classification',
        'official_term', 'system_assessment_key', 'system_assessment_phase', 'needs_manual_review',
        'source_assessment__title', 'source_assessment__code', 'source_assessment__section_id',
        'source_assessment__system_assessment_phase', 'source_assessment__system_assessment_key',
        'material__title', 'material__assessment_kind', 'material__system_assessment_phase', 'material__system_assessment_key',
        'supplementary_school_calendar_id', 'supplementary_term',
    ]
    candidates_qs = Assessment.objects.filter(student_id__in=student_ids, is_active=True).filter(
        Q(enrollment_id__in=enrollment_map) | Q(enrollment__isnull=True, section_id__in=section_map)
        | Q(enrollment__isnull=True, section__isnull=True, source_assessment__section_id__in=section_map)
    ).exclude(attempt_status__in=['discarded', 'cancelled', 'abandoned'])
    if scope.start:
        candidates_qs = candidates_qs.filter(Q(completed_at__isnull=True) | Q(completed_at__date__gte=scope.start))
    if scope.end:
        candidates_qs = candidates_qs.filter(Q(completed_at__isnull=True) | Q(completed_at__date__lte=scope.end))
    candidates = list(candidates_qs.order_by('-completed_at', '-updated_at', '-id').values(*fields))
    canonical_ids = set(official_crla_result_queryset().filter(pk__in=candidates_qs.values('pk')).values_list('pk', flat=True))
    scoped = []
    unscoped = 0
    for row in candidates:
        enrollment = cohort[row['student_id']]
        if row['enrollment_id']:
            linked = enrollment_map.get(row['enrollment_id'])
            if not linked or linked.student_id != row['student_id']:
                continue
        else:
            linked_section = row['section_id'] or row['source_assessment__section_id']
            if linked_section != enrollment.section_id:
                unscoped += 1
                continue
        completed_on = timezone.localdate(row['completed_at']) if row['completed_at'] else None
        if completed_on and ((scope.start and completed_on < scope.start) or (scope.end and completed_on > scope.end)):
            continue
        official_identity = row['id'] in canonical_ids or row['material__assessment_kind'] == 'crla' or any(
            row[prefix + 'system_assessment_key'] in KEY_PHASES for prefix in ('', 'source_assessment__', 'material__'))
        row['phase'] = _phase(row) if official_identity else ''
        row['official'] = row['id'] in canonical_ids
        row['classification'] = canonical_crla_classification(row['crla_classification'] or row['classification']) if row['official'] else ''
        row['official'] = row['official'] and bool(row['classification'])
        row['term'] = row['official_term'] or row['supplementary_term']
        if row['official'] and row['term'] is None:
            row['term'] = scope.term_for_date(completed_on)
        if scope.term and row['term'] != scope.term:
            continue
        scoped.append(row)

    latest_by_phase = {}
    for row in scoped:
        if row['official']:
            latest_by_phase.setdefault((row['student_id'], row['phase']), row)
    visible = [row for row in scoped if not scope.phase or row['phase'] == scope.phase]
    latest_official = {}
    latest_tasks = {}
    for row in visible:
        if row['official']:
            latest_official.setdefault(row['student_id'], row)
        # A finalized official profile is required for official task completion.
        is_official_task = bool(row['phase'] or row['material__assessment_kind'] == 'crla')
        if is_official_task and not row['official']:
            continue
        if row['attempt_status'] == 'completed' and row['completed_at'] and not row['needs_manual_review']:
            key = ('crla', row['phase'], row['term']) if row['official'] else ('task', row['source_assessment_id'] or row['id'])
            latest_tasks.setdefault((key, row['student_id']), row)

    definitions = list(Assessment.objects.filter(
        source_assessment__isnull=True, student__isnull=True, is_active=True, section_id__in=section_map,
    ).filter(Q(status='published') | Q(status='scheduled', scheduled_at__lte=system_now())).values(
        'id', 'title', 'code', 'assessment_type', 'section_id', 'updated_at', 'system_assessment_phase', 'system_assessment_key', 'official_term', 'material__assessment_kind',
    ))
    tasks = {}
    # Definitions remain visible without results; official tasks are grouped by
    # persisted period/term instead of by the first creator of a shared parent.
    for definition in definitions:
        official_identity = definition['system_assessment_key'] in KEY_PHASES or definition['material__assessment_kind'] == 'crla'
        phase = (definition['system_assessment_phase'] or KEY_PHASES.get(definition['system_assessment_key'], '')) if official_identity else ''
        term = definition['official_term']
        if (scope.phase and phase != scope.phase) or (scope.term and term != scope.term):
            continue
        key = ('crla', phase, term) if phase else ('task', definition['id'])
        task = tasks.setdefault(key, {'title': definition['title'], 'code': definition['code'], 'assessment_type': definition['assessment_type'],
                                     'expected': set(), 'results': {}, 'updated_at': definition['updated_at'], 'material_ids': set()})
        task['expected'].update(sid for sid, e in cohort.items() if e.section_id == definition['section_id'])
    # A configured, published assessment window is evidence of the expected
    # school-wide period even before a learner result creates its parent.
    # A reusable template on its own is not an assignment to every term.
    event_phases = {'pre_assessment': 'pretest', 'midline_assessment': 'midtest', 'post_assessment': 'posttest'}
    configured_periods = set(CalendarEvent.objects.filter(school_calendar=scope.calendar, scope='global', is_published=True,
        event_type__in=event_phases).values_list('event_type', 'term')) if student_ids else set()
    official_materials = list(Material.objects.filter(
        assessment_kind='crla', is_official_reading=True, is_system_owned=True,
        is_active=True, status='published', system_assessment_key__in=KEY_PHASES,
    ).values('id', 'title', 'code', 'item_type', 'system_assessment_key', 'official_term', 'updated_at'))
    for material in official_materials:
        phase = KEY_PHASES[material['system_assessment_key']]
        if scope.phase and phase != scope.phase:
            continue
        observed_terms = {row['term'] for row in visible if row['official'] and row['phase'] == phase}
        terms = observed_terms | {term for event_type, term in configured_periods if event_phases[event_type] == phase}
        for term in terms:
            if scope.term and term != scope.term:
                continue
            key = ('crla', phase, term)
            task = tasks.setdefault(key, {'title': PHASES[phase], 'code': material['code'], 'assessment_type': material['item_type'],
                                         'expected': set(), 'results': {}, 'updated_at': material['updated_at'], 'material_ids': set()})
            task['expected'].update(student_ids)
            task['material_ids'].add(material['id'])
        if observed_terms and ('crla', phase, None) in tasks and None not in observed_terms:
            tasks.pop(('crla', phase, None))
    for (key, sid), row in latest_tasks.items():
        task = tasks.setdefault(key, {'title': PHASES.get(row['phase']) or row['source_assessment__title'] or row['title'],
                                    'code': row['source_assessment__code'] or row['code'], 'assessment_type': row['assessment_type'],
                                    'expected': set(student_ids) if row['official'] else set(), 'results': {},
                                    'updated_at': row['updated_at'], 'material_ids': set()})
        if not task['expected']:
            task['expected'].update(s for s, e in cohort.items() if e.section_id == cohort[sid].section_id)
        task['results'][sid] = row
        task['updated_at'] = max(task['updated_at'], row['updated_at'])
        if row['material_id']:
            task['material_ids'].add(row['material_id'])

    for task in tasks.values():
        task['participants'] = set()
    for row in visible:
        official_task = bool(row['phase'] or row['material__assessment_kind'] == 'crla')
        key = ('crla', row['phase'], row['term']) if official_task else ('task', row['source_assessment_id'] or row['id'])
        if key in tasks and row['student_id'] in tasks[key]['expected']:
            tasks[key]['participants'].add(row['student_id'])
    assessment_rows = []
    for key, task in tasks.items():
        results = {sid: row for sid, row in task['results'].items() if sid in task['expected']}
        completed = len(results)
        expected = len(task['expected'])
        status = 'Completed' if expected and completed == expected else 'In Progress' if task['participants'] else 'Pending'
        assessment_rows.append({
            'category': 'Official CRLA' if key[0] == 'crla' else 'Other assessment',
            'is_official': key[0] == 'crla',
            'id': str(key), 'title': task['title'], 'code': task['code'], 'assessment_type': task['assessment_type'].title(),
            'status': status, 'status_badge': 'success' if status == 'Completed' else 'warning',
            'participants': len(task['participants']), 'expected_students': expected, 'completed_students': completed,
            'completion_rate': percent(completed, expected), 'avg_score': mean(r['total_score'] for r in results.values()),
            'updated_at': task['updated_at'], 'teacher_name': 'School monitoring',
        })
    assessment_rows.sort(key=lambda row: row['updated_at'], reverse=True)

    attempt_rows = []
    for row in latest_tasks.values():
        student = cohort[row['student_id']].student
        attempt_rows.append({
            'attempt_key': row['id'], 'assessment_title': PHASES.get(row['phase']) or row['material__title'] or row['source_assessment__title'] or row['title'],
            'assessment_code': row['source_assessment__code'] or row['code'], 'assessment_type': row['assessment_type'].title(),
            'student_id': student.pk, 'student_name': f'{student.first_name} {student.last_name}'.strip(),
            'attempt_number': row['attempt_number'], 'status': 'Completed', 'total_score': numeric(row['total_score']),
            'accuracy': row['accuracy'], 'pronunciation_score': row['pronunciation_score'], 'wpm': row['wpm'],
            'completed_at': row['completed_at'], 'classification': row['classification'], 'phase': PHASES.get(row['phase'], ''),
            'is_official': row['official'], 'category': 'Official CRLA' if row['official'] else 'Other assessment',
        })

    def grade_summary(ids):
        results = [latest_official[sid] for sid in ids if sid in latest_official]
        attempted = {r['student_id'] for r in visible if r['student_id'] in ids and (r['phase'] or r['material__assessment_kind'] == 'crla')}
        completed = len(results)
        return {'grade': 'Grade 2', 'total_students': len(ids), 'completed': completed,
                'in_progress': len(attempted - set(latest_official)), 'not_started': len(ids - attempted - set(latest_official)),
                'completion_pct': percent(completed, len(ids)), 'reading_score': accuracy_mean(r['accuracy'] for r in results),
                'speech_score': accuracy_mean(r['pronunciation_score'] for r in results),
                'average_score': accuracy_mean(r['accuracy'] for r in results), 'reading_samples': sum(numeric(r['accuracy']) is not None and 0 <= numeric(r['accuracy']) <= 100 for r in results),
                'speech_samples': sum(numeric(r['pronunciation_score']) is not None and 0 <= numeric(r['pronunciation_score']) <= 100 for r in results)}
    grade_rows = [grade_summary(student_ids)] if student_ids else []
    accuracy = accuracy_mean(row['accuracy'] for row in latest_official.values())
    month = timezone.localdate(system_now()).replace(day=1)
    today = timezone.localdate(system_now())
    monthly = accuracy_mean(row['accuracy'] for row in latest_official.values() if month <= timezone.localdate(row['completed_at']) <= today)
    distribution = Counter(row['classification'] for row in latest_official.values())
    section_rows = []
    for section in sections:
        ids = {sid for sid, e in cohort.items() if e.section_id == section.pk}
        summary = grade_summary(ids)
        section_rows.append({'id': section.pk, 'name': section.section or section.class_name,
                             'is_active': section.is_active,
                             'teacher': f'{section.teacher.first_name} {section.teacher.last_name}'.strip() if section.teacher_id in teacher_ids else 'Unassigned', **summary})
    phase_rows = []
    for phase, label in PHASES.items():
        phase_results = [r for (sid, p), r in latest_by_phase.items() if p == phase]
        counts = Counter(r['classification'] for r in phase_results)
        phase_rows.append({'phase': phase, 'label': label, 'completed': len(phase_results), 'expected': len(cohort),
                           'completion_rate': percent(len(phase_results), len(cohort)),
                           'accuracy': accuracy_mean(r['accuracy'] for r in phase_results),
                           'classifications': [{'label': label, 'count': counts[label]} for label in VALID_CRLA_CLASSIFICATIONS]})
    outcomes = []
    ranks = {label: rank for rank, label in enumerate(VALID_CRLA_CLASSIFICATIONS)}
    for before, after in [('pretest', 'midtest'), ('midtest', 'posttest'), ('pretest', 'posttest')]:
        movement = Counter()
        for sid in cohort:
            first, last = latest_by_phase.get((sid, before)), latest_by_phase.get((sid, after))
            if first and last:
                difference = ranks[last['classification']] - ranks[first['classification']]
                movement['improved' if difference < 0 else 'declined' if difference > 0 else 'unchanged'] += 1
        outcomes.append({'before': PHASES[before], 'after': PHASES[after], 'paired': sum(movement.values()),
                         **{key: movement[key] for key in ['improved', 'unchanged', 'declined']}})
    finalized = list(ClassCrlaFinalization.objects.filter(section_id__in=section_map).values(
        'section_id', 'material__title', 'material__system_assessment_phase', 'material__system_assessment_key', 'material__official_term', 'finalized_at'))
    for row in finalized:
        final_date = timezone.localdate(row['finalized_at'])
        row['term'] = scope.term_for_date(final_date)
        row['phase'] = row['material__system_assessment_phase'] or KEY_PHASES.get(row['material__system_assessment_key'], '')
    finalized = [row for row in finalized if (not scope.term or row['term'] == scope.term)
                 and (not scope.phase or row['phase'] == scope.phase)]
    notices = Notification.objects.filter(recipient=user)
    if not scope.global_admin:
        notices = notices.filter(school_id=scope.school_id).exclude(school__isnull=True)
    recent, seen_notices = [], set()
    for notice in notices.order_by('-created_at', '-pk')[:40]:
        if notice.title == 'Top-performing class of the week' and re.search(r'\bat 0(?:\.0+)?%', notice.message):
            continue  # Legacy zero-score accolades are not useful leadership updates.
        identity = (notice.title, notice.message, timezone.localdate(notice.created_at))
        if identity not in seen_notices:
            seen_notices.add(identity)
            recent.append({'title': notice.title, 'message': notice.message, 'created_at': notice.created_at, 'variant': notice.notification_type})
        if len(recent) == 4:
            break
    context = {
        'scope': scope, 'scope_calendar': scope.calendar, 'school_calendars': scope.calendars,
        'scope_start': scope.start, 'scope_end': scope.end, 'scope_term': str(scope.term or ''), 'scope_phase': scope.phase,
        'scope_section_id': str(scope.section_id or ''), 'scope_sections': sections,
        'scope_phase_label': PHASES.get(scope.phase, 'All CRLA periods'),
        'scope_section_label': next((r['name'] for r in section_rows if r['id'] == scope.section_id), 'All sections'),
        'school_name': user.school_record.name if user.school_record_id else 'All schools' if scope.global_admin else 'School not assigned',
        'school_logo': user.school_record.logo if user.school_record_id else '',
        'total_students': len(cohort), 'total_teachers': len(teacher_ids), 'total_sections': len(sections),
        'awaiting_assignment_students': scope.awaiting_enrollments().count() if scope.school_id else 0,
        'total_assessments': len(tasks), 'completed_assessments': sum(r['status'] == 'Completed' for r in assessment_rows),
        'in_progress_assessments': sum(r['status'] == 'In Progress' for r in assessment_rows),
        'pending_assessments': sum(r['status'] == 'Pending' for r in assessment_rows),
        'completion_rate': percent(len(latest_official), len(cohort)), 'official_completed_students': len(latest_official),
        'average_score': accuracy, 'current_month_performance': monthly,
        'accuracy_samples': sum(numeric(r['accuracy']) is not None and 0 <= numeric(r['accuracy']) <= 100 for r in latest_official.values()),
        'grade_rows': grade_rows, 'section_rows': section_rows, 'assessment_rows': assessment_rows,
        'assessment_attempt_rows': attempt_rows, 'assessment_type_cards': [], 'recent_activity': recent,
        'report_rows': [], 'top_grades': sorted(grade_rows, key=lambda r: r['average_score'] if r['average_score'] is not None else -1, reverse=True),
        'intervention_grades': [r for r in grade_rows if r['average_score'] is not None and r['average_score'] < 75],
        'classification_rows': [{'label': label, 'count': distribution[label], 'percentage': percent(distribution[label], len(cohort))} for label in VALID_CRLA_CLASSIFICATIONS],
        'missing_official_students': len(cohort) - len(latest_official), 'phase_rows': phase_rows,
        'outcome_comparisons': outcomes,
        'finalization_rows': [{'section': section_map[row['section_id']].section or section_map[row['section_id']].class_name,
                               'assessment': row['material__title'], 'finalized_at': row['finalized_at']} for row in finalized],
        'unscoped_result_count': unscoped, 'snapshot_at': system_now(),
        'metric_definition': 'Active/completed Grade 2 enrollments in the selected school year; latest finalized official CRLA result per learner. Accuracy includes recorded zero values; missing values are not zero.',
    }
    filters = {'calendar_id': scope.calendar.pk if scope.calendar else '', 'term': scope.term or '',
               'phase': scope.phase, 'section_id': scope.section_id or ''}
    if params and params.get('report_type'):
        filters['report_type'] = params['report_type']
    context['filter_query'] = urlencode(filters)
    filter_scope = PrincipalScope(scope.school_id, scope.calendar)
    filter_scope.global_admin = scope.global_admin
    context['filter_sections'] = list(filter_scope.sections())
    for kind in sorted({r['assessment_type'] for r in assessment_rows}):
        rows = [r for r in assessment_rows if r['assessment_type'] == kind]
        context['assessment_type_cards'].append({'label': kind, 'total': len(rows), 'completed': sum(r['status'] == 'Completed' for r in rows), 'avg_score': None})
    if include_oversight:
        context.update(_oversight(scope, cohort, latest_official, section_rows))
    return context


def _oversight(scope, cohort, official, section_rows):
    """Batch actual progress/assignment/review records; never fabricate work."""
    students = set(cohort)
    enrollment_ids = {e.pk for e in cohort.values()}
    eligible = {sid for sid, row in official.items() if row['classification'] != RGL}
    progress = StudentActivityProgress.objects.filter(student_id__in=students, school_calendar=scope.calendar)
    recordings = StudentActivityRecordingSubmission.objects.filter(student_id__in=students, school_calendar=scope.calendar)
    reading_attempts = PrescribedReadingAttempt.objects.filter(student_id__in=students, school_calendar=scope.calendar)
    publications = SupplementaryMaterialPublication.objects.filter(
        section_id__in={e.section_id for e in cohort.values()}, school_calendar=scope.calendar, is_active=True,
        material__is_active=True, material__status='published',
    ).select_related('material')
    if scope.term:
        progress = progress.filter(term=scope.term)
        recordings = recordings.filter(term=scope.term)
        reading_attempts = reading_attempts.filter(term=scope.term)
        publications = publications.filter(term=scope.term)
    activity_keys = {a['activity_key'] for a in active_prescribed_activities()} | {a['activity_key'] for a in LEGACY_SESSION_PROGRESS_ACTIVITIES}
    activity_keys.update(LEGACY_SESSION_PROGRESS_ALIASES.values())
    catalog_keys = {LEGACY_SESSION_PROGRESS_ALIASES.get(key, key) for key in activity_keys}
    tracking = {}
    for row in progress.filter(activity_key__in=activity_keys | set(LEGACY_SESSION_PROGRESS_ALIASES)).order_by('-updated_at', '-pk').values('student_id', 'activity_key', 'term', 'activity_completed', 'state', 'updated_at'):
        key = (row['student_id'], row['term'], LEGACY_SESSION_PROGRESS_ALIASES.get(row['activity_key'], row['activity_key']))
        tracking.setdefault(key, row)
    tracked = list(tracking.values())
    activity_counts = Counter()
    learner_progress = Counter()
    pending_students = set()
    for row in tracked:
        state = row['state'] if isinstance(row['state'], dict) else {}
        pending = bool(state.get('pending_review') or state.get('awaiting_teacher_verdict'))
        status = 'pending' if pending else 'completed' if row['activity_completed'] else 'started'
        activity_counts[status] += 1
        learner_progress[row['student_id']] += 1
        if pending:
            pending_students.add(row['student_id'])
    pending_recordings = list(recordings.filter(
        Q(review_status__in=['pending', 'pending_review']) | Q(status='submitted', review_status='not_required')
    ).values('student_id', 'pk'))
    latest_readings = {}
    for row in reading_attempts.order_by('-created_at', '-pk').values('student_id', 'activity_key', 'item_index', 'term', 'pk', 'review_status'):
        latest_readings.setdefault((row['student_id'], row['activity_key'], row['item_index'], row['term']), row)
    pending_readings = [row for row in latest_readings.values() if row['review_status'] in {'pending', 'pending_review'}]
    pending_students.update(row['student_id'] for row in pending_recordings + pending_readings)

    publications = list(publications)
    allowed = set(SupplementaryStudentAssignment.objects.filter(
        publication_id__in=[p.pk for p in publications], enrollment_id__in=enrollment_ids,
    ).values_list('publication_id', 'student_id'))
    pairs = {}
    for publication in publications:
        for sid, enrollment in cohort.items():
            if enrollment.section_id != publication.section_id:
                continue
            if publication.material.publication_scope == 'selected_students' and (publication.pk, sid) not in allowed:
                continue
            pairs[(sid, publication.material_id, publication.term)] = 'not_started'
    material_ids = {key[1] for key in pairs}
    supplementary_rows = list(Assessment.objects.filter(
        student_id__in=students, material_id__in=material_ids, is_active=True,
        supplementary_school_calendar=scope.calendar, enrollment_id__in=enrollment_ids,
    ).values('student_id', 'material_id', 'supplementary_term', 'attempt_status', 'completed_at', 'needs_manual_review'))
    for row in supplementary_rows:
        key = (row['student_id'], row['material_id'], row['supplementary_term'])
        if key in pairs and row['attempt_status'] not in ['discarded', 'cancelled', 'abandoned']:
            status = 'completed' if row['attempt_status'] == 'completed' and row['completed_at'] and not row['needs_manual_review'] else 'started'
            if pairs[key] != 'completed':
                pairs[key] = status
    for row in StoryReadingProgress.objects.filter(student_id__in=students, material_id__in=material_ids, school_calendar=scope.calendar, enrollment_id__in=enrollment_ids).values('student_id', 'material_id', 'term', 'completed', 'completed_at'):
        key = (row['student_id'], row['material_id'], row['term'])
        if key in pairs:
            pairs[key] = 'completed' if row['completed'] and row['completed_at'] else 'started'
    for row in StoryResponseSubmission.objects.filter(student_id__in=students, material_id__in=material_ids, school_calendar=scope.calendar, enrollment_id__in=enrollment_ids).values('student_id', 'material_id', 'term', 'status'):
        key = (row['student_id'], row['material_id'], row['term'])
        if key in pairs:
            pairs[key] = 'completed' if row['status'] == 'graded' else 'pending'
            if row['status'] != 'graded':
                pending_students.add(row['student_id'])
    supplementary_counts = Counter(pairs.values())
    supplementary_students = {sid for (sid, mid, term), status in pairs.items() if status != 'not_started'}
    exits = set()
    follow_up = []
    for sid, enrollment in cohort.items():
        preferences = enrollment.student.preference if isinstance(enrollment.student.preference, dict) else {}
        state = preferences.get('reading_assessment_state', {})
        state = state if isinstance(state, dict) else {}
        exit_scope = state.get('aral_exit_scope') or {}
        exit_scope = exit_scope if isinstance(exit_scope, dict) else {}
        latest = official.get(sid)
        try:
            exit_at = parse_datetime(str(state.get('aral_exit_at') or ''))
        except ValueError:
            exit_at = None
        proven_exit = bool(latest and (
            (exit_scope.get('assessment_id') == latest['id'] and exit_scope.get('school_calendar_id') == getattr(scope.calendar, 'pk', None))
            or (exit_at and timezone.is_aware(exit_at) and latest['completed_at'] <= exit_at
                and (not scope.start or timezone.localdate(exit_at) >= scope.start)
                and (not scope.end or timezone.localdate(exit_at) <= scope.end))
        ))
        if latest and proven_exit and state.get('aral_exit_override') and exit_scope.get('term') == latest['term'] and exit_scope.get('phase') == latest['phase']:
            exits.add(sid)
        reason = 'Official CRLA result missing' if not latest else 'Pending Teacher review' if sid in pending_students else 'No intervention progress recorded' if sid in eligible and sid not in exits and not learner_progress[sid] and sid not in supplementary_students else ''
        if reason:
            section = next((row for row in section_rows if row['id'] == enrollment.section_id), {})
            follow_up.append({'student_id': sid, 'name': f'{enrollment.student.first_name} {enrollment.student.last_name}'.strip(),
                              'section': section.get('name', ''), 'teacher': section.get('teacher', ''), 'reason': reason})
    for section in section_rows:
        ids = {sid for sid, e in cohort.items() if e.section_id == section['id']}
        section.update(eligible=len(ids & eligible), progress_recorded=len(ids & (set(learner_progress) | supplementary_students)),
                       pending_review=len(ids & pending_students), follow_up=sum(r['student_id'] in ids for r in follow_up))
    practice_students = set()
    for practice in Practice.objects.filter(section_id__in={e.section_id for e in cohort.values()}, is_active=True).only('attempts'):
        for attempt in practice.attempts if isinstance(practice.attempts, list) else []:
            if isinstance(attempt, dict) and str(attempt.get('enrollment_id')) in {str(e) for e in enrollment_ids} and attempt.get('student_id') in students:
                practice_students.add(attempt['student_id'])
    return {
        'aral_eligible_students': len(eligible), 'aral_recorded_exits': len(exits),
        'aral_progress_students': len((eligible - exits) & (set(learner_progress) | supplementary_students)),
        'prescribed_counts': {'recorded': len(tracked), 'started': activity_counts['started'], 'completed': activity_counts['completed'], 'pending': activity_counts['pending']},
        'prescribed_catalog_count': len(catalog_keys), 'supplementary_counts': {'assigned': len(pairs), **{key: supplementary_counts[key] for key in ['not_started', 'started', 'completed', 'pending']}},
        'pending_review_students': len(pending_students), 'pending_recording_count': len(pending_recordings), 'pending_reading_count': len(pending_readings),
        'reading_analysis_issues': reading_attempts.exclude(audio_analysis_error='').count(),
        'follow_up_rows': follow_up, 'practice_students': len(practice_students),
    }


def weekly_official_accuracy(school_id, calendar_id, start, end):
    """Latest canonical result per enrolled learner in the given week.

    Returns only numeric summaries. Used by Principal notifications so a
    shared parent or a retry cannot create a second performance definition.
    """
    enrollments = Enrollment.objects.filter(school_id=school_id, school_calendar_id=calendar_id,
        status__in=['active', 'completed'], section__is_active=True, grade_level='Grade 2',
        student__is_archived=False, student__school_record_id=school_id).values('id', 'student_id', 'section_id')
    by_student = {row['student_id']: row for row in enrollments}
    latest = {}
    for row in official_crla_result_queryset().filter(student_id__in=by_student, completed_at__gte=start,
        completed_at__lt=end).order_by('-completed_at', '-updated_at', '-pk').values(
            'student_id', 'enrollment_id', 'section_id', 'accuracy', 'crla_classification', 'classification'):
        enrollment = by_student[row['student_id']]
        if row['enrollment_id'] != enrollment['id'] and not (row['enrollment_id'] is None and row['section_id'] == enrollment['section_id']):
            continue
        if canonical_crla_classification(row['crla_classification'] or row['classification']):
            latest.setdefault(row['student_id'], row)
    sections = defaultdict(list)
    for sid, row in latest.items():
        sections[by_student[sid]['section_id']].append(row['accuracy'])
    return {'school': accuracy_mean(row['accuracy'] for row in latest.values()),
            'sections': {section_id: accuracy_mean(values) for section_id, values in sections.items()}}
