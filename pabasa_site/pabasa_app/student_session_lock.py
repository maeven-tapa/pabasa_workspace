from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import transaction
from django.urls import resolve, Resolver404

from .models import User
from .system_clock import real_now as session_now


# Let an active learning screen recover from a short disconnection. The tab
# heartbeats every 30 seconds; a device is replaceable after the normal idle
# window, even if it was left on an assessment page.
STUDENT_SESSION_IDLE_TIMEOUT = timedelta(seconds=settings.STUDENT_SESSION_IDLE_SECONDS)
STUDENT_SESSION_LEASE_TIMEOUT = STUDENT_SESSION_IDLE_TIMEOUT


def is_learning_page(path):
    """Only actual learning views qualify, never arbitrary client URL strings."""
    try:
        match = resolve(path)
    except (Resolver404, ValueError):
        return False
    return bool(
        path.startswith('/dashboard/assessment/')
        or path.startswith('/dashboard/practice/') and match.url_name != 'practice_results'
        or match.url_name in {
            'practice_word_page', 'practice_sentence_page', 'practice_para_page',
            'practice', 'practice_mark_tutorial_seen', 'practice_game_progression',
            'assessment', 'courses', 'course_student_view', 'prescribed_activity_page',
            'live_assessment_session', 'live_assessment_session_control',
            'live_assessment_waiting_room',
        }
    )


def student_session_timed_out(user, now=None):
    now = now or session_now()
    if not user:
        return False
    if user.active_session_learning:
        last_seen = user.active_session_last_seen or user.last_activity
        return bool(last_seen and last_seen <= now - STUDENT_SESSION_LEASE_TIMEOUT)
    return bool(user.last_activity and user.last_activity <= now - STUDENT_SESSION_IDLE_TIMEOUT)


def student_session_status(user, now=None):
    now = now or session_now()
    remaining = STUDENT_SESSION_IDLE_TIMEOUT.total_seconds()
    if user.last_activity and not user.active_session_learning:
        remaining -= (now - user.last_activity).total_seconds()
    return {
        'success': True, 'protected': user.active_session_learning,
        'remaining_seconds': max(0, remaining),
        'warning_seconds': settings.STUDENT_SESSION_WARNING_SECONDS,
    }


def claim_student_session(user_id, session_key):
    """Atomically claim a student session, returning False if another is active."""
    now = session_now()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id, role='student')
        active_key = user.active_session_key
        same_session = active_key == session_key
        session_exists = bool(active_key and Session.objects.filter(
            session_key=active_key, expire_date__gt=now
        ).exists())
        stale = bool(
            active_key and (
                not (user.active_session_last_seen or user.last_activity) or
                (user.active_session_last_seen or user.last_activity) <= now - STUDENT_SESSION_LEASE_TIMEOUT
            )
        )
        if active_key and active_key != session_key and session_exists and not stale and not student_session_timed_out(user, now):
            return False
        user.active_session_key = session_key
        user.active_session_created_at = user.active_session_created_at if same_session else now
        user.last_activity = now
        user.active_session_last_seen = now
        user.active_session_learning = False
        user.save(update_fields=['active_session_key', 'active_session_created_at', 'last_activity',
                                 'active_session_last_seen', 'active_session_learning', 'updated_at'])
        return True


def student_session_is_active(user, session_key, now=None):
    now = now or session_now()
    last_seen = (user.active_session_last_seen or user.last_activity) if user else None
    return bool(
        user and session_key and user.active_session_key == session_key and
        not student_session_timed_out(user, now) and last_seen and
        last_seen > now - STUDENT_SESSION_LEASE_TIMEOUT
    )


def release_student_session(user_id, session_key):
    User.objects.filter(
        pk=user_id, role='student', active_session_key=session_key,
    ).update(active_session_key=None, active_session_created_at=None, last_activity=None,
             active_session_last_seen=None, active_session_learning=False)
