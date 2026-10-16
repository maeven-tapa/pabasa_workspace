"""Student badges derived from saved evidence, never browser completion flags."""
from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    Assessment, Material, PrescribedReadingAttempt, StudentAchievement,
    StudentActivityProgress, StudentActivityRecordingSubmission, StudentLearningDay,
)
from .prescribed_activity_catalog import (
    LEGACY_SESSION_PROGRESS_ACTIVITIES, LEGACY_SESSION_PROGRESS_ALIASES, active_prescribed_activities,
)
from .system_clock import now as system_now


ACHIEVEMENTS = (
    ('first-steps', 'First Steps', 'Complete your first assessment.', 'tree-fill'),
    ('book-explorer', 'Book Explorer', 'Complete 3 different assessments.', 'book-fill'),
    ('reading-streak', 'Reading Streak', 'Read or practise on 7 consecutive days.', 'lightning-charge-fill'),
    ('rising-reader', 'Rising Reader', 'Complete 50% of the required prescribed activities.', 'star-fill'),
    ('practice-star', 'Practice Star', 'Complete all 45 levels across Easy, Medium, and Hard in Free, Color, and Hunt Mode in one language.', 'award-fill'),
    ('reading-champion', 'Reading Champion', 'Complete all required prescribed activities across Sessions 1–15.', 'trophy-fill'),
    ('session-starter', 'Session Starter', 'Complete all required activities in your first session.', 'flag-fill'),
    ('session-explorer', 'Session Explorer', 'Complete all required activities in 5 sessions.', 'compass-fill'),
    ('activity-achiever', 'Activity Achiever', 'Complete 10 different guided activities.', 'check2-circle'),
    ('star-collector', 'Star Collector', 'Earn 100 lifetime stars. Spent stars still count.', 'stars'),
    ('color-champion', 'Color Champion', 'Complete all 5 Easy levels in Color Mode in one language.', 'palette-fill'),
    ('word-hunter', 'Word Hunter', 'Complete all 5 Easy levels in Hunt Mode in one language.', 'search'),
)
FINALIZED_WITHOUT_SUBMISSION = 'Finalized without a submitted CRLA assessment.'


def prescribed_catalog():
    # Share the same legacy keys and aliases as the session folders.
    catalog = {item['activity_key']: item for item in active_prescribed_activities()}
    for item in LEGACY_SESSION_PROGRESS_ACTIVITIES:
        catalog.setdefault(item['activity_key'], item)
    return {key: item for key, item in catalog.items() if 1 <= int(item.get('session_number') or 0) <= 15}


def _award(student_id, keys):
    if not keys:
        return
    keys = set(keys) - set(StudentAchievement.objects.filter(
        student_id=student_id, achievement_key__in=keys,
    ).values_list('achievement_key', flat=True))
    if keys:
        StudentAchievement.objects.bulk_create([
            StudentAchievement(student_id=student_id, achievement_key=key) for key in keys
        ], ignore_conflicts=True)


def prescribed_summary(student, school_calendar=None, term=None):
    catalog = prescribed_catalog()
    completed = set()
    if school_calendar and term in (1, 2, 3):
        rows = {
            row.activity_key: row.activity_completed
            for row in StudentActivityProgress.objects.filter(
                student=student, school_calendar=school_calendar, term=term,
                activity_key__in=set(catalog) | set(LEGACY_SESSION_PROGRESS_ALIASES.values()),
            ).only('activity_key', 'activity_completed')
        }
        for key in catalog:
            # A canonical reset must override an older alias completion.
            done = rows.get(key, rows.get(LEGACY_SESSION_PROGRESS_ALIASES.get(key), False))
            if done:
                completed.add(key)
    sessions = defaultdict(set)
    for key, item in catalog.items():
        sessions[int(item['session_number'])].add(key)
    session_count = sum(bool(keys) and keys <= completed for keys in sessions.values())
    total = len(catalog)
    earned = set()
    if total and len(completed) * 2 >= total:
        earned.add('rising-reader')
    if total and len(completed) == total:
        earned.add('reading-champion')
    if session_count >= 1:
        earned.add('session-starter')
    if session_count >= 5:
        earned.add('session-explorer')
    if len(completed) >= 10:
        earned.add('activity-achiever')
    return {
        'completed_activities': len(completed), 'total_activities': total,
        'completed_sessions': session_count,
        'sessions': [{'session': number, 'total': len(sessions[number]),
                      'completed': len(sessions[number] & completed),
                      'percent': (100 if sessions[number] <= completed else
                                  min(99, round(len(sessions[number] & completed) * 100 / len(sessions[number]))))
                      if sessions[number] else 0} for number in range(1, 16)],
        # Incomplete work must never display as 100% after rounding.
        'prescribed_percent': (100 if len(completed) == total and total else
                               min(99, round(len(completed) * 100 / total)) if total else 0),
        'earned': earned,
    }


def assessment_summary(student):
    results = Assessment.objects.filter(
        student=student, attempt_status='completed', completed_at__isnull=False,
    ).exclude(remarks__contains=FINALIZED_WITHOUT_SUBMISSION).filter(
        Q(material__isnull=True) | Q(material__type__in=('assessment', 'both')),
    ).values_list('material_id', 'source_assessment_id', 'id', 'completed_at', 'material__assessment_id')
    results = list(results)
    material_by_source = {source: material for material, source, _id, _at, _parent in results if material and source}
    material_by_source.update({parent: material for material, _source, _id, _at, parent in results if material and parent})
    identities, dates = set(), set()
    today = timezone.localdate(system_now())
    for material_id, source_id, result_id, completed_at, _parent in results:
        date = _local_date(completed_at)
        if not date or date > today:
            continue
        material_id = material_id or material_by_source.get(source_id)
        identities.add(('material', material_id) if material_id else
                       ('assessment', source_id or result_id))
        dates.add(date)
    count = len(identities)
    earned = set()
    if count >= 1:
        earned.add('first-steps')
    if count >= 3:
        earned.add('book-explorer')
    return count, dates, earned


def _nonnegative_int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def practice_summary(student):
    slots, stars, dates = defaultdict(set), defaultdict(dict), set()
    today = timezone.localdate(system_now())
    # One query, without per-level/per-mode calls or another student's results.
    materials = Material.objects.filter(
        type='practice', section__isnull=True, teacher__isnull=True,
        is_system_owned=True, source_type='shared',
    ).only('content_json', 'language', 'difficulty_level')
    for material in materials:
        content = material.content_json if isinstance(material.content_json, dict) else {}
        completions = content.get('student_completions') or {}
        completion = completions.get(str(student.pk)) if isinstance(completions, dict) else None
        if not isinstance(completion, dict) or completion.get('status') != 'completed':
            continue
        slot = (content.get('mode'), content.get('difficulty') or material.difficulty_level, content.get('level'))
        if slot[0] not in ('free', 'color', 'hunt') or slot[1] not in ('easy', 'medium', 'hard') or slot[2] not in {f'level_{i}' for i in range(1, 6)}:
            continue
        date = _local_date(completion.get('completed_at'))
        if date and date > today:
            continue
        language = material.language
        slots[language].add(slot)
        stars[language][slot] = max(stars[language].get(slot, 0), _nonnegative_int(completion.get('stars_earned')))
        if date:
            dates.add(date)
    required = {(mode, difficulty, f'level_{i}') for mode in ('free', 'color', 'hunt')
                for difficulty in ('easy', 'medium', 'hard') for i in range(1, 6)}
    earned = set()
    if any(required <= completed for completed in slots.values()):
        earned.add('practice-star')
    for mode, key in (('color', 'color-champion'), ('hunt', 'word-hunter')):
        easy = {(mode, 'easy', f'level_{i}') for i in range(1, 6)}
        if any(easy <= completed for completed in slots.values()):
            earned.add(key)
    pref = student.preference if isinstance(student.preference, dict) else {}
    # Each language's levels contribute to lifetime earnings. Stored/credited
    # totals already include progression, so retain the greater total.
    lifetime = max(_nonnegative_int(pref.get('total_stars_earned')),
                   _nonnegative_int(student.theme_stars_credited),
                   sum(sum(values.values()) for values in stars.values()))
    if lifetime >= 100:
        earned.add('star-collector')
    return lifetime, dates, earned


def _local_date(value):
    if isinstance(value, str):
        try:
            value = parse_datetime(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())
    return timezone.localdate(value, timezone.get_default_timezone())


def record_learning_dates(student_id, dates):
    today = timezone.localdate(system_now())
    dates = {date for date in dates if date and date <= today}
    if not dates:
        return
    dates -= set(StudentLearningDay.objects.filter(
        student_id=student_id, date__in=dates,
    ).values_list('date', flat=True))
    if not dates:
        return
    StudentLearningDay.objects.bulk_create([
        StudentLearningDay(student_id=student_id, date=date) for date in dates
    ], ignore_conflicts=True)


def _streaks(dates, today):
    dates = sorted({date for date in dates if date <= today})
    best = run = 0
    previous = None
    for date in dates:
        run = run + 1 if previous and date == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = date
    current = run if previous in (today, today - timedelta(days=1)) else 0
    return current, best


def refresh_student_achievements(student, lifecycle=None):
    if not student or student.role != 'student':
        return {'badges': [], 'metrics': {}}
    if lifecycle is None:
        from .views import _current_learning_context
        lifecycle = _current_learning_context(student)
    summary = prescribed_summary(student, lifecycle.get('school_calendar'), lifecycle.get('term'))
    assessment_count, dates, assessment_keys = assessment_summary(student)
    lifetime, practice_dates, practice_keys = practice_summary(student)
    dates |= practice_dates
    # Historical days are reconstructed only from dated saved reading evidence,
    # never from progress counts or mutable teacher-review timestamps.
    for values in (
        PrescribedReadingAttempt.objects.filter(student=student).exclude(audio_file='').values_list('created_at', flat=True),
        StudentActivityRecordingSubmission.objects.filter(student=student).exclude(audio_file='').values_list('submitted_at', flat=True),
    ):
        dates.update(_local_date(value) for value in values)
    record_learning_dates(student.pk, dates)
    days = list(StudentLearningDay.objects.filter(
        student=student, date__lte=timezone.localdate(system_now()),
    ).values_list('date', flat=True))
    streak, best_streak = _streaks(days, timezone.localdate(system_now()))
    earned = summary.pop('earned') | assessment_keys | practice_keys
    if best_streak >= 7:
        earned.add('reading-streak')
    _award(student.pk, earned)
    awards = dict(StudentAchievement.objects.filter(student=student).values_list('achievement_key', 'earned_at'))
    return {
        'badges': [{'id': key, 'name': name, 'description': description, 'icon': icon,
                    'unlocked': key in awards} for key, name, description, icon in ACHIEVEMENTS],
        'metrics': {**summary, 'assessment_count': assessment_count, 'lifetime_stars': lifetime,
                    'reading_days': len(days), 'current_streak': streak, 'best_streak': best_streak},
    }
