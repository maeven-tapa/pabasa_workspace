from datetime import timedelta

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from .models import User


STUDENT_SESSION_IDLE_TIMEOUT = timedelta(minutes=30)


def claim_student_session(user_id, session_key):
    """Atomically claim a student session, returning False if another is active."""
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user_id, role='student')
        active_key = user.active_session_key
        same_session = active_key == session_key
        session_exists = bool(active_key and Session.objects.filter(
            session_key=active_key, expire_date__gt=now
        ).exists())
        stale = bool(
            active_key and user.last_activity and
            user.last_activity <= now - STUDENT_SESSION_IDLE_TIMEOUT
        )
        if active_key and active_key != session_key and session_exists and not stale:
            return False
        user.active_session_key = session_key
        user.active_session_created_at = user.active_session_created_at or now
        user.last_activity = now
        user.save(update_fields=['active_session_key', 'active_session_created_at', 'last_activity', 'updated_at'])
        return True


def student_session_is_active(user, session_key, now=None):
    now = now or timezone.now()
    return bool(
        user and session_key and user.active_session_key == session_key and
        (not user.last_activity or user.last_activity > now - STUDENT_SESSION_IDLE_TIMEOUT)
    )


def release_student_session(user_id, session_key):
    User.objects.filter(
        pk=user_id, role='student', active_session_key=session_key,
    ).update(active_session_key=None, active_session_created_at=None, last_activity=None)
