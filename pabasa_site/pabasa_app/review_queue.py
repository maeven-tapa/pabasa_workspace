"""Teacher inbox projected from current submissions, never from notification state.

One task represents a learner/activity/period. Audio items and reading attempts
stay in their established tables; existing evaluators remain authoritative.
"""
import hashlib
import json
from collections import defaultdict
from functools import wraps
from urllib.parse import urlencode

from django.db import OperationalError, transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .models import (Enrollment, Notification, PrescribedReadingAttempt, StoryResponseSubmission,
    StudentActivityProgress, StudentActivityRecordingSubmission, SupplementaryMaterialPublication,
    SupplementaryStudentAssignment, TeacherReviewInbox, User)
from .prescribed_activity_catalog import prescribed_activity

# Explicit registration prevents catalog preview flags from inventing tasks.
ACTIVITIES = {
    'lesson-1-gawain-1': ('Session 1 · Lesson 1 · Gawain 1', 'Reading recording', 'single'),
    'session-4-gawain-1': ('Session 4 · Lessons 10–12 · Gawain 1', 'Tunog ng mga Letra', 'binary'),
    'session-4-gawain-2': ('Session 4 · Lessons 10–12 · Gawain 2', 'Pagsamahin ang mga Tunog', 'binary'),
    'lesson-13-gawain-1': ('Session 5 · Lesson 13 · Gawain 1', 'Sabihin ang tunog ng mga letra', 'binary'),
    'session-5-lesson-14-gawain-4': ('Session 5 · Lesson 14 · Gawain 4', 'Reading fluency', 'fluency'),
    'lesson-15-gawain-3': ('Session 5 · Lesson 15 · Gawain 3', 'Reading fluency', 'lesson15'),
    'aral-s9-a1-family-drawing': ('Session 9 · Activity 1', 'My family', 'drawing'),
    'aral-s9-a2-helping-drawing': ('Session 9 · Activity 2', 'Helping at home', 'drawing'),
    'lesson-29-gawain-3': ('Session 13 · Lesson 29 · Activity 3', 'Trace & Say', 'trace'),
}
AUDIO_VIEWS = {
    'lesson-1-gawain-1': 'teacher_lesson_1_gawain_1_audio',
    'session-4-gawain-1': 'teacher_session_4_gawain_1_audio',
    'session-4-gawain-2': 'teacher_session_4_gawain_2_audio',
    'lesson-13-gawain-1': 'teacher_lesson_13_gawain_1_audio',
    'session-5-lesson-14-gawain-4': 'teacher_session_5_lesson_14_gawain_4_audio',
    'lesson-29-gawain-3': 'teacher_lesson29_trace_say_audio',
}
SCORE_VIEWS = {
    'session-4-gawain-1': 'teacher_session_4_gawain_1_score',
    'session-4-gawain-2': 'teacher_session_4_gawain_2_score',
    'lesson-13-gawain-1': 'teacher_lesson_13_gawain_1_score',
    'session-5-lesson-14-gawain-4': 'teacher_session_5_lesson_14_gawain_4_classify',
    'lesson-29-gawain-3': 'teacher_lesson29_trace_say_score',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:24]


def database_errors(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except OperationalError:
            return JsonResponse({'success': False, 'retryable': True,
                'error': 'The review inbox is temporarily busy. Please try again.'}, status=503)
    return wrapped


def teacher_for(request):
    if request.session.get('user_role') != 'teacher':
        return None
    return User.objects.filter(pk=request.session.get('user_id'), role='teacher', is_archived=False,
        account_status__in=['active', 'pending_archive']).first()


def _recording_belongs(row, progress):
    if row.school_calendar_id is not None or row.term is not None:
        return (row.school_calendar_id, row.term) == (progress.school_calendar_id, progress.term)
    # Older activities stored one mutable recording per learner. Never borrow a
    # previous period's recording. Lesson 1 has an explicit current-attempt link.
    state = progress.state if isinstance(progress.state, dict) else {}
    if progress.activity_key == 'lesson-1-gawain-1':
        return state.get('submission_id') == row.pk
    return row.submitted_at >= progress.created_at


def collect(teacher):
    """Bounded query count: batch roster, progress, recordings, attempts, publications."""
    from . import views as v
    enrollments = Enrollment.objects.filter(status='active', is_active=True,
        student__role='student', student__is_archived=False, section__teacher=teacher,
        section__is_active=True, school_calendar__is_active=True,
    ).select_related('student', 'section', 'school_calendar').order_by('-joined_at', '-pk')
    if teacher.school_record_id:
        enrollments = enrollments.filter(section__school_id=teacher.school_record_id)
    scopes, sections, periods, terms = {}, {}, {}, {}
    enrollments_by_id = {}
    enrollment_ids = set()
    for enrollment in enrollments:
        calendar = enrollment.school_calendar
        if enrollment.section.school_calendar_id != calendar.pk:
            continue
        if enrollment.school_id and enrollment.school_id != enrollment.section.school_id:
            continue
        if enrollment.student.school_record_id and enrollment.student.school_record_id != enrollment.section.school_id:
            continue
        if enrollment.student.school_calendar_id and enrollment.student.school_calendar_id != calendar.pk:
            continue
        if calendar.pk not in terms:
            terms[calendar.pk] = v._calendar_current_term(calendar)
        term = terms[calendar.pk]
        if term not in (1, 2, 3):
            continue
        enrollment._review_term = term
        key = (enrollment.student_id, calendar.pk, term)
        scopes.setdefault(key, enrollment)
        sections[enrollment.section_id] = enrollment.section.class_name
        periods[calendar.pk] = calendar.school_year
        enrollment_ids.add(enrollment.pk)
        enrollments_by_id[enrollment.pk] = enrollment
    if not scopes:
        return [], {'sections': [], 'periods': [], 'terms': [], 'activities': []}
    students = {key[0] for key in scopes}
    calendars = {key[1] for key in scopes}
    progress_rows = list(StudentActivityProgress.objects.filter(student_id__in=students,
        school_calendar_id__in=calendars, activity_key__in=ACTIVITIES).order_by('-updated_at', '-pk'))
    recordings = defaultdict(list)
    for row in StudentActivityRecordingSubmission.objects.filter(student_id__in=students,
            activity_key__in=ACTIVITIES).order_by('-submitted_at', '-pk'):
        recordings[(row.student_id, row.activity_key)].append(row)
    attempts = defaultdict(dict)
    for attempt in PrescribedReadingAttempt.objects.filter(student_id__in=students,
            school_calendar_id__in=calendars, activity_key='lesson-15-gawain-3'):
        attempts[(attempt.student_id, attempt.school_calendar_id, attempt.term)][str(attempt.attempt_id)] = attempt
    tasks, seen = [], set()
    for progress in progress_rows:
        scope_key = (progress.student_id, progress.school_calendar_id, progress.term)
        enrollment = scopes.get(scope_key)
        identity = (*scope_key, progress.activity_key)
        if not enrollment or identity in seen:
            continue
        seen.add(identity)
        state = progress.state if isinstance(progress.state, dict) else {}
        label, title, mode = ACTIVITIES[progress.activity_key]
        retry = bool(state.get('retry_requested') and not state.get('submitted') and not progress.activity_completed)
        submitted = progress.activity_completed
        if mode in {'single', 'trace', 'drawing'}:
            submitted = bool(submitted or state.get('submitted') or state.get('awaiting_teacher_verdict'))
        if not submitted and not retry:
            continue
        task = _base_task(enrollment, progress.activity_key, label, title, mode, 'prescribed')
        task['_progress'] = progress
        items, tokens = [], []
        catalog = prescribed_activity(progress.activity_key) or {}
        catalog_items = catalog.get('items') or []
        task['expected_items'] = len(catalog_items) or 1
        if mode == 'drawing':
            checked = bool(state.get('checked') and progress.activity_completed)
            answer = (state.get('answers') or {}).get('item-1', state.get('draft') or {})
            task['artifact'] = answer if isinstance(answer, dict) else {}
            task['instruction'] = catalog.get('instruction', '')
            task['reviewed_items'] = int(checked)
            task['pending_items'] = int(submitted and not checked)
            tokens = [digest([progress.pk, task['artifact'], state.get('review_history')])]
        elif mode == 'lesson15':
            from .lesson15_reading import item_result, state_for, TEXTS
            reading_state = state_for(progress)
            current_attempts = attempts.get(scope_key, {})
            for index, text in enumerate(TEXTS):
                result = item_result(reading_state, index)
                attempt = current_attempts.get(result.get('attempt_id'))
                if result.get('classification_source') == 'skipped' or not attempt or not attempt.audio_file:
                    continue
                clips = [clip for clip in current_attempts.values() if clip.item_index == index
                    and result.get('reading_attempt_id')
                    and (clip.audio_features or {}).get('reading_attempt_id') == result['reading_attempt_id']]
                item = dict(result, item_index=index, expected_text=text, submission_id=attempt.pk,
                    recording_url=_audio_url(task['id'], attempt.pk),
                    recordings=[{'recording_url': _audio_url(task['id'], clip.pk)} for clip in clips if clip.audio_file])
                item['_audio_ids'] = [clip.pk for clip in clips] + [attempt.pk]
                items.append(item)
                tokens.append(str(attempt.attempt_id))
        else:
            seen_items = set()
            for row in recordings.get((progress.student_id, progress.activity_key), []):
                item_key = (row.item_index, row.substep)
                if not _recording_belongs(row, progress) or item_key in seen_items:
                    continue
                if mode == 'single' and state.get('submission_id') != row.pk:
                    continue
                if mode != 'single' and (row.item_index is None or not 0 <= row.item_index < len(catalog_items)):
                    continue
                if progress.activity_key == 'session-4-gawain-2' and row.substep not in (0, 1):
                    continue
                seen_items.add(item_key)
                if not row.audio_file or row.status == 'retry' or row.classification_source == 'skipped':
                    continue
                source = catalog_items[row.item_index] if row.item_index is not None and row.item_index < len(catalog_items) else {}
                text = (source.get('first' if row.substep == 0 else 'second', '') if row.substep is not None
                    else source.get('text') or source.get('letter') or source.get('word') or 'Reading recording')
                reviewed = row.status == 'checked' if mode == 'single' else (
                    row.review_status == 'reviewed' and row.classification_source == 'teacher'
                    if mode == 'fluency' else row.teacher_score in (0, 1))
                items.append({'submission_id': row.pk, 'item_index': row.item_index, 'substep': row.substep,
                    'expected_text': text, 'item_label': text, 'teacher_score': row.teacher_score,
                    'recording_available': True, 'audio_url': _audio_url(task['id'], row.pk),
                    'recording_url': _audio_url(task['id'], row.pk), 'status': row.status,
                    'classification': row.fluency_classification, 'classification_source': row.classification_source,
                    'review_status': 'reviewed' if reviewed else 'pending', 'transcript': row.recognized_transcript,
                    '_row': row})
                tokens.append(digest([row.pk, row.audio_file.name, row.submitted_at]))
            items.sort(key=lambda item: (item['item_index'] or 0, item['substep'] or 0))
        if mode != 'drawing':
            task['reviewed_items'] = sum(item['review_status'] == 'reviewed' for item in items)
            task['pending_items'] = sum(item['review_status'] != 'reviewed' for item in items)
        if not items and mode != 'drawing' and not retry and mode != 'trace':
            continue
        final_verdict = mode == 'trace' and submitted and not progress.activity_completed
        task['final_verdict'] = final_verdict
        task['status'] = ('retry' if retry else 'partial' if task['reviewed_items'] and
            (task['pending_items'] or final_verdict) else 'pending' if task['pending_items'] or final_verdict else 'reviewed')
        task['submitted_at'] = str(state.get('submitted_at') or state.get('completed_at') or
            min((item['_row'].submitted_at for item in items if '_row' in item), default=progress.created_at).isoformat())
        task['items'] = items
        task['_tokens'] = tokens
        task['version'] = digest([progress.updated_at, tokens,
            [(item['submission_id'], item.get('review_status'), item.get('teacher_score'), item.get('classification')) for item in items]])
        tasks.append(task)

    publications = list(SupplementaryMaterialPublication.objects.filter(section_id__in=sections,
        school_calendar_id__in=calendars, is_active=True, material__is_active=True,
    ).select_related('material'))
    publication_map = {(p.material_id, p.section_id, p.school_calendar_id, p.term): p for p in publications}
    assignments = set(SupplementaryStudentAssignment.objects.filter(publication_id__in=[p.pk for p in publications],
        enrollment_id__in=enrollment_ids).values_list('publication_id', 'student_id', 'enrollment_id'))
    submissions = StoryResponseSubmission.objects.filter(student_id__in=students,
        school_calendar_id__in=calendars, material_id__in=[p.material_id for p in publications],
    ).select_related('material', 'story_material').order_by('-submitted_at', '-pk')
    seen_supplementary = set()
    for submission in submissions:
        enrollment = (enrollments_by_id.get(submission.enrollment_id) if submission.enrollment_id
            else scopes.get((submission.student_id, submission.school_calendar_id, submission.term)))
        if not enrollment or (submission.enrollment_id and submission.enrollment_id not in enrollment_ids):
            continue
        if enrollment.student_id != submission.student_id:
            continue
        if (enrollment.school_calendar_id, enrollment._review_term) != (submission.school_calendar_id, submission.term):
            continue
        publication = publication_map.get((submission.material_id, enrollment.section_id, submission.school_calendar_id, submission.term))
        if not publication:
            continue
        material = submission.material
        if material.publication_scope == 'selected_students' and (publication.pk, submission.student_id, enrollment.pk) not in assignments:
            continue
        content = material.content_json if isinstance(material.content_json, dict) else {}
        mode = content.get('activity_type') or content.get('activity_variant')
        if mode not in {'story_response', 'retell_story'} or not submission.audio_file and not submission.response_text:
            continue
        identity = (submission.student_id, material.pk, submission.school_calendar_id, submission.term)
        if identity in seen_supplementary:
            continue
        seen_supplementary.add(identity)
        task = _base_task(enrollment, f'material-{material.pk}',
            'Retell the Story' if mode == 'retell_story' else 'Response to Story', material.title, mode, 'supplementary')
        reviewed = submission.grade is not None or (mode == 'retell_story' and submission.reviewed_at is not None)
        task.update(status='reviewed' if reviewed else 'pending', reviewed_items=int(reviewed),
            pending_items=int(not reviewed), submitted_at=submission.submitted_at.isoformat(),
            version=digest([submission.pk, submission.updated_at]), submission_id=submission.pk,
            grade=submission.grade, reviewed_at=submission.reviewed_at, prompt=submission.prompt,
            response_text=submission.response_text, recording_available=bool(submission.audio_file),
            recording_url=_audio_url(task['id'], submission.pk) if submission.audio_file else None,
            story_title=(submission.story_material.title if submission.story_material else ''),
            items=[], _submission=submission, _tokens=[digest([submission.pk, submission.audio_file.name, submission.submitted_at])])
        tasks.append(task)
    options = {'sections': [{'id': key, 'label': value} for key, value in sections.items()],
        'periods': [{'id': key, 'label': value} for key, value in periods.items()],
        'terms': sorted(set(term for term in terms.values() if term in (1, 2, 3))),
        'activities': [{'id': key, 'label': f'{value[0]} · {value[1]}'} for key, value in ACTIVITIES.items()]
            + [{'id': 'story_response', 'label': 'Response to Story'}, {'id': 'retell_story', 'label': 'Retell the Story'}]}
    return tasks, options


def _base_task(enrollment, key, label, title, mode, category):
    student = enrollment.student
    task_id = f'{student.pk}:{enrollment.school_calendar_id}:{_term_for(enrollment)}:{key}'
    review_url = (reverse('teacher_prescribed_review_page') + '?' + urlencode({
        'student_id': student.pk, 'session': 9, 'activity': key, 'review_task': task_id})
        if mode == 'drawing' else reverse('courses') + '?' + urlencode({'review_task': task_id}))
    return {'id': task_id, 'review_url': review_url,
        'student_id': student.pk, 'student_name': ' '.join(filter(None, [student.first_name, student.last_name])) or student.custom_id,
        'section_id': enrollment.section_id, 'section': enrollment.section.class_name,
        'school_calendar_id': enrollment.school_calendar_id, 'school_year': enrollment.school_calendar.school_year,
        'term': _term_for(enrollment), 'activity_key': key, 'label': label, 'title': title, 'mode': mode,
        'category': category, 'pending_items': 0, 'reviewed_items': 0, 'final_verdict': False}


def _term_for(enrollment):
    # Set by collect, avoiding a calendar query for each task.
    return enrollment._review_term


def _audio_url(task_id, record_id):
    return reverse('teacher_review_audio') + f'?task={task_id}&record={record_id}'


def public(task, detail=False):
    return {key: value for key, value in task.items() if not key.startswith('_')
        and (detail or key not in {'items', 'artifact', 'response_text', 'prompt', 'recording_url'})}


def summary(tasks):
    pending = [task for task in tasks if task['status'] in {'pending', 'partial'}]
    return {'pending': len(pending), 'students': len({task['student_id'] for task in pending}),
        'prescribed': sum(task['category'] == 'prescribed' for task in pending),
        'supplementary': sum(task['category'] == 'supplementary' for task in pending),
        'partial': sum(task['status'] == 'partial' for task in pending),
        'reviewed': sum(task['status'] == 'reviewed' for task in tasks),
        'retry': sum(task['status'] == 'retry' for task in tasks),
        'oldest': min((task['submitted_at'] for task in pending), default=None)}


def sync_notification(teacher, tasks):
    """One grouped notification. Reading/clearing it never affects the work list."""
    from . import views as v
    pending = [task for task in tasks if task['status'] in {'pending', 'partial'}]
    tokens = sorted({f"{task['id']}:{token}" for task in pending for token in task['_tokens']})
    changed = False
    with transaction.atomic():
        # Serialize first creation and concurrent browser tabs on the same user.
        User.objects.select_for_update().get(pk=teacher.pk)
        inbox, _ = TeacherReviewInbox.objects.select_for_update().get_or_create(teacher=teacher)
        new = set(tokens) - set(inbox.seen_tokens)
        notification = Notification.objects.filter(pk=inbox.notification_id, recipient=teacher).first()
        counts = summary(tasks)
        submission_word = 'submission' if counts['pending'] == 1 else 'submissions'
        student_word = 'student' if counts['students'] == 1 else 'students'
        message = f"{counts['pending']} {submission_word} from {counts['students']} {student_word} ready for your feedback."
        if not pending:
            message = 'All submitted work has been checked. Your review queue is clear.'
        if new and v._notification_settings_for_user(teacher).get('push_enabled') is True:
            if not notification:
                notification = v._create_notification(teacher, 'New work to check', message,
                    'assessment', reverse('teacher_review_queue'), send_email=False)
                inbox.notification = notification
            else:
                notification.title, notification.message, notification.is_read = 'New work to check', message, False
                notification.created_at = timezone.now()
                notification.save(update_fields=['title', 'message', 'is_read', 'created_at', 'updated_at'])
            changed = True
        elif notification and (notification.message != message or not pending and not notification.is_read):
            notification.message = message
            if not pending:
                notification.is_read = True
            notification.save(update_fields=['message', 'is_read', 'updated_at'])
            changed = True
        if inbox.seen_tokens != tokens or inbox.notification_id != getattr(notification, 'pk', None):
            inbox.seen_tokens = tokens
            inbox.save(update_fields=['seen_tokens', 'notification'])
    return changed


@never_cache
@require_GET
def workspace(request):
    from . import views as v
    if not teacher_for(request):
        return HttpResponseForbidden('Teacher access required.')
    return render(request, 'pabasa_app/teacher_review_queue.html', v._dashboard_context(request, 'teacher'))


@never_cache
@require_GET
@database_errors
def queue_api(request):
    teacher = teacher_for(request)
    if not teacher:
        return JsonResponse({'success': False, 'error': 'Teacher access required.'}, status=403)
    tasks, options = collect(teacher)
    result = {'success': True, 'summary': summary(tasks), 'updated_at': timezone.now().isoformat()}
    if request.GET.get('summary') == '1':
        result['notification_changed'] = sync_notification(teacher, tasks)
        return JsonResponse(result)
    selected = tasks
    for param, field in [('section', 'section_id'), ('calendar', 'school_calendar_id'), ('term', 'term'), ('category', 'category')]:
        if request.GET.get(param):
            selected = [task for task in selected if str(task[field]) == request.GET[param]]
    if request.GET.get('activity'):
        selected = [task for task in selected if request.GET['activity'] in {task['activity_key'], task['mode']}]
    status = request.GET.get('status', 'needs_review')
    selected = [task for task in selected if task['status'] in
        ({'pending', 'partial'} if status == 'needs_review' else {'pending', 'partial', 'reviewed', 'retry'} if status == 'all' else {status})]
    search = request.GET.get('q', '').strip().casefold()[:160]
    if search:
        selected = [task for task in selected if search in ' '.join(str(task[field]) for field in ['student_name', 'section', 'label', 'title']).casefold()]
    sort = request.GET.get('sort', 'oldest')
    selected.sort(key=(lambda task: (task['student_name'].casefold(), task['submitted_at'])) if sort == 'student'
        else (lambda task: (task['pending_items'], task['submitted_at'])) if sort == 'remaining'
        else (lambda task: task['submitted_at']), reverse=sort in {'newest', 'remaining'})
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except ValueError:
        page = 1
    pages = max(1, (len(selected) + 11) // 12)
    page = min(page, pages)
    result.update(items=[public(task) for task in selected[(page-1)*12:page*12]], total=len(selected),
        page=page, pages=pages, options=options)
    return JsonResponse(result)


def find_task(teacher, task_id):
    return next((task for task in collect(teacher)[0] if task['id'] == task_id), None)


def detail_payload(task):
    payload = public(task, detail=True)
    payload['items'] = [{key: value for key, value in item.items() if not key.startswith('_')} for item in task['items']]
    if task['mode'] == 'trace':
        payload['traces'] = (task['_progress'].state or {}).get('traces', [])
    if task['mode'] != 'drawing':
        payload['progress_task'], payload['progress_attempt'] = course_progress_context(task, payload['items'])
    return payload


def course_progress_context(task, items):
    """Adapt the scoped submission to the existing Course student-progress renderer."""
    types = {'lesson-1-gawain-1': 'lesson_1_recording',
        'session-4-gawain-1': 'session_4_gawain_1', 'session-4-gawain-2': 'session_4_gawain_2',
        'lesson-13-gawain-1': 'lesson_13_gawain_1', 'lesson-29-gawain-3': 'lesson_29_trace_say'}
    activity_type = ('session_5_fluency' if task['mode'] in {'fluency', 'lesson15'}
        else types.get(task['activity_key'], task['mode']))
    assessment_id = ('prescribed-' + task['activity_key'] if task['category'] == 'prescribed' else task['activity_key'])
    progress_task = {'title': task['title'], 'assessmentId': assessment_id,
        'source_type': task['category'], 'activityType': activity_type, 'activityLabel': task['label']}
    progress = task.get('_progress')
    reviewed = task['status'] == 'reviewed'
    attempt = {'student_id': task['student_id'], 'activity_type': activity_type,
        'status': 'completed' if reviewed else 'submitted', 'submitted_at': task['submitted_at'],
        'completed_at': task['submitted_at'] if progress and progress.activity_completed else None,
        'session4_recordings': items, 'session5_recordings': items,
        'session4_correct_items': progress.correct_items if progress else 0,
        'session4_total_items': progress.total_items if progress else 0,
        'can_retry': task['status'] in {'pending', 'partial'},
        'can_check': task['status'] in {'pending', 'partial'},
        'lesson15_review': task['mode'] == 'lesson15'}
    if task['mode'] == 'single' and items:
        attempt.update(items[0], status=items[0]['status'])
    if '_submission' in task:
        submission = task['_submission']
        attempt.update(story_response_submission_id=submission.pk, retell_grade=submission.grade,
            grade_locked=submission.grade is not None, recording_available=bool(submission.audio_file),
            recording_url=task['recording_url'], recording_duration_seconds=submission.duration_seconds,
            reviewed_at=submission.reviewed_at.isoformat() if submission.reviewed_at else None,
            review_task=task['id'], review_version=task['version'])
    return progress_task, attempt


@never_cache
@require_GET
@database_errors
def detail_api(request):
    teacher = teacher_for(request)
    task = find_task(teacher, request.GET.get('task')) if teacher else None
    if not task:
        return JsonResponse({'success': False, 'error': 'This submission is no longer available in your current classes.'}, status=404)
    return JsonResponse({'success': True, 'task': detail_payload(task)})


@csrf_protect
@require_POST
@database_errors
def action_api(request):
    from . import views as v
    teacher = teacher_for(request)
    if not teacher:
        return JsonResponse({'success': False, 'error': 'Teacher access required.'}, status=403)
    try:
        data = json.loads(request.body)
        task_id = data['task']
        if not isinstance(task_id, str):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'success': False, 'error': 'Invalid review request.'}, status=400)
    with transaction.atomic():
        # Lock evidence before validating its version, matching existing evaluators.
        task = find_task(teacher, task_id)
        if not task:
            return JsonResponse({'success': False, 'error': 'Submission access denied.'}, status=404)
        User.objects.select_for_update().get(pk=task['student_id'])
        if '_submission' in task:
            StoryResponseSubmission.objects.select_for_update().get(pk=task['_submission'].pk)
        else:
            StudentActivityProgress.objects.select_for_update().get(pk=task['_progress'].pk)
            list(StudentActivityRecordingSubmission.objects.select_for_update().filter(
                student_id=task['student_id'], activity_key=task['activity_key']))
        task = find_task(teacher, task_id)
        if not task or data.get('version') != task['version']:
            return JsonResponse({'success': False, 'error': 'This submission changed. Refresh it before checking.'}, status=409)
        if task['status'] == 'retry':
            return JsonResponse({'success': False, 'error': 'Wait for the student to resubmit this activity.'}, status=409)
        action = data.get('action')
        body = {'student_id': task['student_id'], 'activity_key': task['activity_key']}
        mode = task['mode']
        if action == 'item':
            item = next((item for item in task['items'] if str(item['submission_id']) == str(data.get('submission_id'))), None)
            if not item or task['status'] == 'retry':
                return JsonResponse({'success': False, 'error': 'Current recording required.'}, status=409)
            body.update(submission_id=item['submission_id'], score=data.get('score'), classification=data.get('classification'))
            if mode == 'lesson15':
                from . import lesson15_reading
                evaluator = lesson15_reading.classify
                body.update(item_index=item['item_index'], attempt_id=item['attempt_id'], review_version=item['review_version'])
            elif task['activity_key'] in SCORE_VIEWS:
                evaluator = getattr(v, SCORE_VIEWS[task['activity_key']])
            else:
                return JsonResponse({'success': False, 'error': 'Unsupported item review.'}, status=400)
        elif mode in {'story_response', 'retell_story'} and action in {'grade', 'reviewed'}:
            submission = task['_submission']
            if action == 'reviewed' and mode != 'retell_story':
                return JsonResponse({'success': False, 'error': 'A story response requires a score.'}, status=400)
            if action == 'reviewed':
                if submission.reviewed_at is None:
                    submission.reviewed_at, submission.reviewed_by = timezone.now(), teacher
                    submission.save(update_fields=['reviewed_at', 'reviewed_by', 'updated_at'])
                return JsonResponse({'success': True})
            body.update(submission_id=submission.pk, grade=data.get('grade'))
            evaluator = v.teacher_story_response_grade
        elif mode == 'single' and action in {'checked', 'retry'}:
            body.update(submission_id=task['items'][0]['submission_id'], action=action)
            evaluator = v.teacher_lesson_1_gawain_1_review_action
        elif mode == 'trace' and action in {'checked', 'retry'}:
            body['action'] = action
            evaluator = v.teacher_lesson29_trace_say_review_action
        elif mode == 'drawing' and action in {'complete', 'retry'}:
            body['action'] = action
            evaluator = v.teacher_prescribed_review_action
        else:
            return JsonResponse({'success': False, 'error': 'Invalid review action.'}, status=400)
        request._body = json.dumps(body).encode()
        return evaluator(request)


@never_cache
@require_GET
@database_errors
def audio_api(request):
    from . import views as v
    teacher = teacher_for(request)
    task = find_task(teacher, request.GET.get('task')) if teacher else None
    if not task:
        return HttpResponseForbidden('Recording unavailable.')
    try:
        record_id = int(request.GET.get('record', ''))
    except ValueError:
        return HttpResponseForbidden('Recording unavailable.')
    if '_submission' in task and record_id == task['_submission'].pk:
        evaluator = v.teacher_retell_recording if task['mode'] == 'retell_story' else v.teacher_story_response_audio
        return evaluator(request, record_id)
    item = next((item for item in task['items'] if record_id in item.get('_audio_ids', [item['submission_id']])), None)
    if not item:
        return HttpResponseForbidden('Recording unavailable.')
    if task['mode'] == 'lesson15':
        from .lesson15_reading import audio
        return audio(request, record_id)
    return getattr(v, AUDIO_VIEWS[task['activity_key']])(request, record_id)
