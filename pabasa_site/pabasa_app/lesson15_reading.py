"""L15 G3 evidence and term-scoped item results; no automatic fluency grading."""
import copy
import hashlib
import json
import uuid
from functools import wraps

from django.db import OperationalError, transaction
from django.db.models import Max
from django.http import FileResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import Enrollment, PrescribedReadingAttempt, User

KEY = 'lesson-15-gawain-3'
# These are the existing displayed texts (two catalog entries have old typos).
TEXTS = (
    'tawa', 'sawa', 'lawa', 'wala', 'walis', 'matamis', 'Ang walis may',
    'Sawa sa lawa', 'Yaman sa', 'May kawa', 'Ang yoyo', 'Nasa mesa',
    'Si tatay ay', 'Sina nanay at tatay', 'Matamis ang', 'Yema ni',
    'Si Tala ay may yoyo.', 'Matamis ang yema ni Tim.',
    'May kawa sa mesa nila Tala.', 'Ang walis tambo ay nasa mesa.',
    'Sina nanay at tatay ay mayaman.', 'Sasama sina nanay at tatay kay Tala.',
)


def recoverable_database_error(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except OperationalError:
            return JsonResponse({'success': False, 'retryable': True,
                'error': 'Hindi pa na-save ang pagbabago. Subukan muli.'}, status=503)
    return wrapped


def state_for(progress):
    state = copy.deepcopy(progress.state or {}) if progress else {}
    state.setdefault('current_index', progress.current_index if progress else 0)
    state.setdefault('completed_reading_items', list(range(state['current_index'])))
    for field in ('reading_attempts', 'listening_attempts', 'transcripts', 'reading_matches',
                  'statuses', 'item_results', 'skip_requests'):
        if not isinstance(state.get(field), dict):
            state[field] = {}
    state.setdefault('review_history', [])
    state.setdefault('state_version', 1)
    return state


def progress_data(progress):
    return {field: getattr(progress, field) for field in (
        'current_index', 'completed_items', 'correct_items', 'total_items', 'activity_completed',
    )} | {'state': state_for(progress)}


def item_result(state, index):
    """Single classification authority. A grade belongs to one immutable attempt."""
    row = dict(state.get('item_results', {}).get(str(index), {}))
    if row.get('classification_source') == 'skipped':
        row.update(classification='RED', fluency_classification='RED', status='not_read',
                   classification_source='skipped', review_status='skipped', stt_match=None)
    elif row.get('attempt_id'):
        reviewed = (row.get('reviewed_attempt_id') == row['attempt_id']
                    and row.get('classification') in {'GREEN', 'YELLOW', 'RED'})
        row.update(classification=row['classification'] if reviewed else 'PENDING_REVIEW',
                   classification_source='teacher' if reviewed else 'recorded',
                   review_status='reviewed' if reviewed else 'pending')
        row['fluency_classification'] = row['classification']
    else:
        row.update(classification='', classification_source='', review_status='missing')
    return row


def locked_progress(student, scope):
    from . import views as v
    User.objects.select_for_update().get(pk=student.pk)
    progress, _ = v._current_progress_get_or_create(student, scope, KEY, defaults={
        'total_items': len(TEXTS), 'state': {},
    })
    return v._current_progress_queryset(student, scope).select_for_update().get(pk=progress.pk)


def persist(progress, state):
    state['state_version'] += 1
    progress.current_index = state['current_index']
    progress.completed_items = len(set(state['completed_reading_items']))
    progress.total_items = len(TEXTS)
    progress.activity_completed = progress.activity_completed or progress.completed_items == len(TEXTS)
    progress.state = state
    progress.save()


def conflict(progress):
    return JsonResponse({'success': False, 'error': 'Nagbago ang progreso. Subukan muli.',
                         'progress': progress_data(progress)}, status=409)


@recoverable_database_error
def save_progress(request, student, scope):
    payload = json.loads(request.body or '{}')
    with transaction.atomic():
        progress = locked_progress(student, scope)
        state = state_for(progress)
        incoming = payload.get('state') or {}
        if incoming and incoming.get('state_version') != state['state_version']:
            return conflict(progress)
        if payload.get('reset') is True:
            # Archive reviews/current pointers, never delete attempt files or grades.
            history = state.pop('restart_history', []) + [copy.deepcopy(state)]
            version = state['state_version']
            state = state_for(None)
            state.update(state_version=version, restart_history=history)
            progress.current_index = progress.completed_items = progress.correct_items = 0
            progress.activity_completed = False
        else:
            # Client saves only listening usage, never classifications or progression.
            for key, value in (incoming.get('listening_attempts') or {}).items():
                if key.isdigit() and 0 <= int(key) < len(TEXTS):
                    state['listening_attempts'][key] = max(
                        state['listening_attempts'].get(key, 0), min(3, max(0, int(value))))
        persist(progress, state)
        return JsonResponse({'success': True, 'progress': progress_data(progress)})


def reading_context(request, audio):
    """Validate before contacting the provider; outcomes never come from the client."""
    from . import views as v
    student = v._active_prescribed_student(request)
    if not student:
        raise ValueError('Student authorization required.')
    scope = v._current_learning_context(student)
    if scope['state'] != 'ARAL_ACTIVE' or not v._student_can_open_prescribed_activity(student, KEY):
        raise ValueError('Hindi pinahintulutan ang gawain.')
    index = int(request.POST.get('item_index', -1))
    attempt_id = uuid.UUID(request.POST.get('attempt_id', ''))
    if not 0 <= index < len(TEXTS) or request.POST.get('target_text') != TEXTS[index]:
        raise ValueError('Hindi tugma ang babasahin.')
    if request.POST.get('mode') != 'word' or request.POST.get('language') != 'Filipino':
        raise ValueError('Hindi tugma ang speech configuration.')
    if not audio or not 0 < audio.size <= 12 * 1024 * 1024:
        raise ValueError('Hindi wastong laki ng recording.')
    header = audio.read(16)
    audio.seek(0)
    mime = (audio.content_type or '').split(';')[0]
    if not ((mime == 'audio/webm' and header.startswith(b'\x1aE\xdf\xa3'))
            or (mime == 'audio/ogg' and header.startswith(b'OggS'))
            or (mime in {'audio/wav', 'audio/x-wav'} and header.startswith(b'RIFF') and header[8:12] == b'WAVE')
            or (mime in {'audio/mp4', 'audio/x-m4a'} and header[4:8] == b'ftyp')):
        raise ValueError('Hindi wastong audio format.')
    digest = hashlib.sha256(audio.read()).hexdigest()
    audio.seek(0)
    clip_id = uuid.uuid5(attempt_id, digest)
    duplicate = PrescribedReadingAttempt.objects.filter(
        attempt_id=clip_id, student=student, school_calendar=scope['school_calendar'], term=scope['term'],
        activity_key=KEY, item_index=index).first()
    if duplicate:
        current = v._current_progress_queryset(student, scope).filter(activity_key=KEY).first()
        if item_result(state_for(current), index).get('attempt_id') != str(clip_id):
            raise ValueError('Lumang recording ito. Subukan muli.')
        return None, JsonResponse(dict(duplicate.audio_features['stt_result'], progress=progress_data(current)))
    progress = v._current_progress_queryset(student, scope).filter(activity_key=KEY).first()
    state = state_for(progress)
    if (progress and progress.activity_completed or index != state['current_index']
            or int(request.POST.get('state_version', -1)) != state['state_version']):
        raise ValueError('Nagbago ang progreso. I-refresh ang gawain.')
    return (student, scope, index, clip_id, state['state_version'], str(attempt_id)), None


def retain_reading(context, audio, analysis):
    """One upload: server STT response is sent only after durable evidence/state save."""
    student, scope, index, clip_id, version, reading_id = context
    with transaction.atomic():
        progress = locked_progress(student, scope)
        state = state_for(progress)
        duplicate = PrescribedReadingAttempt.objects.filter(attempt_id=clip_id).first()
        if duplicate:
            return dict(duplicate.audio_features['stt_result'], progress=progress_data(progress))
        if version != state['state_version'] or index != state['current_index']:
            raise ValueError('Nagbago ang progreso. I-refresh ang gawain bago subukan muli.')
        number = (PrescribedReadingAttempt.objects.filter(student=student, activity_key=KEY,
                  item_index=index).aggregate(n=Max('attempt_number'))['n'] or 0) + 1
        attempt = PrescribedReadingAttempt(
            student=student, school_calendar=scope['school_calendar'], term=scope['term'],
            activity_key=KEY, item_index=index, attempt_id=clip_id, attempt_number=number,
            expected_text=TEXTS[index], recognized_transcript=analysis.get('raw_transcript') or analysis.get('transcript', ''),
            stt_match=analysis.get('complete') is True, stt_provider=analysis.get('stt_provider', ''),
            stt_model=analysis.get('stt_model', ''), audio_mime_type=audio.content_type,
            classification='PENDING_REVIEW', classification_source='recorded', review_status='pending',
        )
        audio.seek(0)
        attempt.audio_file.save(str(clip_id) + '.recording', audio, save=False)
        try:
            key = str(index)
            previous = item_result(state, index)
            if previous.get('review_status') == 'reviewed':
                state['review_history'].append(previous)
            state['item_results'][key] = {'attempt_id': str(clip_id), 'submission_id': None,
                'reading_attempt_id': reading_id,
                'classification': 'PENDING_REVIEW', 'classification_source': 'recorded',
                'review_status': 'pending', 'review_version': previous.get('review_version', 0) + 1,
                'stt_match': attempt.stt_match, 'status': 'read' if attempt.stt_match else 'retry'}
            state['reading_attempts'][key] = state['reading_attempts'].get(key, 0) + 1
            state['transcripts'][key] = attempt.recognized_transcript
            state['reading_matches'][key] = attempt.stt_match
            state['statuses'][key] = 'read' if attempt.stt_match else 'retry'
            if attempt.stt_match:
                state['completed_reading_items'] = sorted(set(state['completed_reading_items']) | {index})
                state['current_index'] = index + 1
            persist(progress, state)
            analysis = dict(analysis, progress=progress_data(progress), evidence_saved=True)
            attempt.audio_features = {'reading_attempt_id': reading_id,
                'stt_result': {key: value for key, value in analysis.items() if key != 'progress'}}
            attempt.save()
            return analysis
        except Exception:
            attempt.audio_file.delete(save=False)
            raise


@csrf_protect
@require_http_methods(['POST'])
@recoverable_database_error
def skip(request):
    from . import views as v
    student = v._active_prescribed_student(request)
    if not student:
        return JsonResponse({'success': False}, status=403)
    scope = v._current_learning_context(student)
    if scope['state'] != 'ARAL_ACTIVE' or not v._student_can_open_prescribed_activity(student, KEY):
        return JsonResponse({'success': False}, status=403)
    try:
        data = json.loads(request.body)
        index, version = int(data['item_index']), int(data['state_version'])
        request_id = str(uuid.UUID(data['request_id']))
        if data.get('activity_key') != KEY:
            raise ValueError('Invalid activity.')
        with transaction.atomic():
            progress = locked_progress(student, scope)
            state = state_for(progress)
            if state['skip_requests'].get(request_id) == index:
                return JsonResponse({'success': True, 'progress': progress_data(progress)})
            if progress.activity_completed or index != state['current_index'] or version != state['state_version']:
                return conflict(progress)
            key = str(index)
            prior = item_result(state, index)
            if prior.get('attempt_id'):
                state['review_history'].append(prior)
            state['item_results'][key] = dict(prior, classification='RED', fluency_classification='RED',
                classification_source='skipped', status='not_read', stt_match=None, review_status='skipped')
            state['statuses'][key] = 'not_read'
            state['reading_matches'][key] = None
            state['skip_requests'][request_id] = index
            state['completed_reading_items'] = sorted(set(state['completed_reading_items']) | {index})
            state['current_index'] = index + 1
            persist(progress, state)
            return JsonResponse({'success': True, 'progress': progress_data(progress)})
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'success': False, 'error': 'Hindi na-save ang paglaktaw. Subukan muli.'}, status=400)


def teacher_scope(request, student_id):
    from . import views as v
    teacher = User.objects.filter(pk=request.session.get('user_id'), role='teacher', is_archived=False).first()
    student = User.objects.filter(pk=student_id, role='student', is_archived=False).first()
    if not teacher or not student:
        raise PermissionError
    scope = v._current_learning_context(student)
    if not scope.get('school_calendar') or scope.get('term') not in (1, 2, 3) or not Enrollment.objects.filter(
            student=student, school_calendar=scope['school_calendar'], status='active', is_active=True,
            section__teacher=teacher, section__is_active=True).exists():
        raise PermissionError
    return teacher, student, scope


def review_data(student, scope):
    from . import views as v
    progress = v._current_progress_queryset(student, scope).filter(activity_key=KEY).first()
    state = state_for(progress)
    attempts = {str(row.attempt_id): row for row in PrescribedReadingAttempt.objects.filter(
        student=student, activity_key=KEY, school_calendar=scope['school_calendar'], term=scope['term'])}
    items = []
    for index, text in enumerate(TEXTS):
        row = item_result(state, index)
        attempt = attempts.get(row.get('attempt_id'))
        clips = [clip for clip in attempts.values() if clip.item_index == index
                 and row.get('reading_attempt_id')
                 and (clip.audio_features or {}).get('reading_attempt_id') == row['reading_attempt_id']]
        items.append(dict(row, item_index=index, expected_text=text,
            transcript=' '.join(clip.recognized_transcript for clip in clips) if clips else attempt.recognized_transcript if attempt else '',
            recordings=[{'recording_url': reverse('lesson15_reading_audio', args=[clip.pk]),
                         'transcript': clip.recognized_transcript} for clip in clips if clip.audio_file],
            submission_id=attempt.pk if attempt else None,
            recording_url=reverse('lesson15_reading_audio', args=[attempt.pk]) if attempt and attempt.audio_file else None))
    return {'success': True, 'items': items, 'activity_status': 'Completed' if progress and progress.activity_completed
            else 'In Progress' if progress else 'Not Started',
            'graded': sum(row['review_status'] in {'reviewed', 'skipped'} for row in items),
            'pending': sum(row['review_status'] == 'pending' for row in items), 'total': len(TEXTS)}


@require_http_methods(['GET'])
def reviews(request):
    try:
        _, student, scope = teacher_scope(request, request.GET.get('student_id'))
        return JsonResponse(review_data(student, scope))
    except (PermissionError, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Student access denied.'}, status=403)


@csrf_protect
@require_http_methods(['POST'])
@recoverable_database_error
def classify(request):
    from . import views as v
    try:
        data = json.loads(request.body)
        teacher, student, scope = teacher_scope(request, data['student_id'])
        index = int(data['item_index'])
        if data['classification'] not in {'GREEN', 'YELLOW', 'RED'} or not 0 <= index < len(TEXTS):
            raise ValueError
        with transaction.atomic():
            progress = locked_progress(student, scope)
            state = state_for(progress)
            row = item_result(state, index)
            if row['classification_source'] == 'skipped' or not row.get('attempt_id'):
                return JsonResponse({'success': False, 'error': 'Hindi maaaring baguhin ang item.'}, status=403)
            if row['attempt_id'] != data['attempt_id'] or row['review_version'] != data['review_version']:
                return JsonResponse({'success': False, 'error': 'Nagbago ang ebidensya o grado. I-refresh ang resulta.'}, status=409)
            state['review_history'].append(dict(row))
            row.update(classification=data['classification'], classification_source='teacher',
                       fluency_classification=data['classification'], review_status='reviewed',
                       reviewed_attempt_id=row['attempt_id'], reviewer_id=teacher.pk,
                       reviewed_at=v.system_now().isoformat(), review_version=row['review_version'] + 1)
            state['item_results'][str(index)] = row
            progress.state = state
            progress.save(update_fields=['state', 'updated_at'])
            return JsonResponse(review_data(student, scope))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid review.'}, status=400)
    except PermissionError:
        return JsonResponse({'success': False, 'error': 'Student access denied.'}, status=403)


@require_http_methods(['GET'])
def audio(request, attempt_pk):
    attempt = PrescribedReadingAttempt.objects.filter(pk=attempt_pk, activity_key=KEY).first()
    try:
        if not attempt:
            raise PermissionError
        _, _, scope = teacher_scope(request, attempt.student_id)
        if attempt.school_calendar_id != scope['school_calendar'].pk or attempt.term != scope['term']:
            raise PermissionError
        response = FileResponse(attempt.audio_file.open('rb'), content_type=attempt.audio_mime_type or 'audio/webm')
        response['Cache-Control'] = 'private, no-store'
        return response
    except (PermissionError, FileNotFoundError, OSError, ValueError):
        return JsonResponse({'success': False, 'error': 'Recording unavailable.'}, status=403)
