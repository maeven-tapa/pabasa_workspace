from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.urls import resolve, Resolver404

from .models import User
from .system_clock import real_now as session_now


# Let an active learning screen recover from a short disconnection. The tab
# heartbeats every 30 seconds; an abandoned device is replaceable after the
# dedicated presence lease, while ordinary non-learning sessions retain the
# longer idle window.
STUDENT_SESSION_IDLE_TIMEOUT = timedelta(seconds=settings.STUDENT_SESSION_IDLE_SECONDS)
STUDENT_SESSION_LEASE_TIMEOUT = timedelta(seconds=settings.STUDENT_SESSION_LEASE_SECONDS)


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
        # The presence lease lets a different device reclaim an abandoned
        # login. A delayed heartbeat on the current learning device is not
        # logout evidence; ownership and the auth session are checked below.
        return False
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


def _active_session_is_usable(user, session_key, now=None):
    """Confirm the recorded key still points to this student's auth session."""
    if not user or not session_key:
        return False
    now = now or session_now()
    session = Session.objects.filter(
        session_key=session_key, expire_date__gt=now,
    ).first()
    if not session:
        return False
    try:
        data = session.get_decoded()
    except (TypeError, ValueError, UnicodeDecodeError):
        return False
    return (
        str(data.get('user_id', '')) == str(user.pk)
        and data.get('user_role') == 'student'
    )


def claim_student_session(user_id, session_key):
    """Atomically claim a student session, returning False if another is active."""
    for _attempt in range(3):
        now = session_now()
        user = User.objects.get(pk=user_id, role='student')
        active_key = user.active_session_key
        same_session = active_key == session_key
        session_exists = _active_session_is_usable(user, active_key, now)
        stale = bool(
            active_key and (
                not (user.active_session_last_seen or user.last_activity) or
                (user.active_session_last_seen or user.last_activity) <= now - STUDENT_SESSION_LEASE_TIMEOUT
            )
        )
        if active_key and active_key != session_key and session_exists and not stale and not student_session_timed_out(user, now):
            return False
        # Compare ownership and presence in the write itself. SQLite cannot
        # lock a row with select_for_update(), and upgrading ten concurrent
        # validation reads to writes caused sign-ins to fail with DB locks.
        # Recheck after a competing claim or heartbeat rather than overwriting it.
        claimed = User.objects.filter(
            pk=user.pk, role='student', active_session_key=active_key,
            active_session_last_seen=user.active_session_last_seen, last_activity=user.last_activity,
        ).update(
            active_session_key=session_key,
            active_session_created_at=user.active_session_created_at if same_session else now,
            last_activity=now, active_session_last_seen=now,
            active_session_learning=False, updated_at=now,
        )
        if claimed:
            return True
    return False


def student_session_is_active(user, session_key, now=None):
    now = now or session_now()
    last_seen = (user.active_session_last_seen or user.last_activity) if user else None
    return bool(
        user and session_key and user.active_session_key == session_key and
        _active_session_is_usable(user, session_key, now) and
        not student_session_timed_out(user, now) and last_seen
    )


def release_student_session(user_id, session_key):
    User.objects.filter(
        pk=user_id, role='student', active_session_key=session_key,
    ).update(active_session_key=None, active_session_created_at=None, last_activity=None,
             active_session_last_seen=None, active_session_learning=False)
