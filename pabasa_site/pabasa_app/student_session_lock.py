from django.contrib.sessions.models import Session
from django.db import transaction

from .models import User
from .system_clock import real_now as session_now


def _active_session_is_usable(user, session_key, now=None):
    """Confirm the recorded key still identifies this student's login."""
    if not user or not session_key:
        return False
    session = Session.objects.filter(session_key=session_key, expire_date__gt=now or session_now()).first()
    if not session:
        return False
    try:
        data = session.get_decoded()
    except (TypeError, ValueError, UnicodeDecodeError):
        return False
    return str(data.get('user_id', '')) == str(user.pk) and data.get('user_role') == 'student'


def claim_student_session(user_id, session_key):
    """Atomically claim a login unless another valid device owns it."""
    for _attempt in range(3):
        user = User.objects.get(pk=user_id, role='student')
        active_key = user.active_session_key
        if active_key and active_key != session_key and _active_session_is_usable(user, active_key):
            return False
        # Compare ownership in the write so concurrent logins cannot overwrite
        # a claim made after validation, including with SQLite.
        now = session_now()
        claimed = User.objects.filter(pk=user.pk, role='student', active_session_key=active_key).update(
            active_session_key=session_key,
            active_session_created_at=user.active_session_created_at if active_key == session_key else now,
            updated_at=now,
        )
        if claimed:
            return True
    return False


def student_session_is_active(user, session_key, now=None):
    return bool(user and session_key and user.active_session_key == session_key
                and _active_session_is_usable(user, session_key, now))


def release_student_session(user_id, session_key):
    User.objects.filter(pk=user_id, role='student', active_session_key=session_key).update(
        active_session_key=None, active_session_created_at=None,
    )


def takeover_student_session(user_id, old_session_key, new_session_key):
    """Atomically end a previously claimed device session after confirmation."""
    if not old_session_key or not new_session_key or old_session_key == new_session_key:
        return False
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=user_id, role='student').first()
        if not user or user.active_session_key != old_session_key:
            return False
        Session.objects.filter(session_key=old_session_key).delete()
        now = session_now()
        updated = User.objects.filter(
            pk=user_id, role='student', active_session_key=old_session_key,
        ).update(
            active_session_key=new_session_key,
            active_session_created_at=now,
            updated_at=now,
        )
        return bool(updated)
