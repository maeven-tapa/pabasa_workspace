import hashlib
from datetime import timedelta

from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.cache import patch_cache_control

from .models import User
from .student_session_lock import (
    is_learning_page, release_student_session, student_session_is_active,
    student_session_status, student_session_timed_out,
)
from .system_clock import real_now as session_now


class PrincipalPasswordChangeMiddleware:
    """Keep temporary-password Principal sessions inside the change flow."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get("user_role") == "principal":
            change_path = reverse("principal_change_temporary_password")
            allowed_paths = {change_path, reverse("logout")}
            if request.path not in allowed_paths and not request.path.startswith(("/static/", "/media/")):
                must_change = User.objects.filter(
                    id=request.session.get("user_id"),
                    role="principal",
                    is_archived=False,
                    must_change_password=True,
                ).exists()
                if must_change:
                    return redirect("principal_change_temporary_password")
        return self.get_response(request)


class StudentSessionLockMiddleware:
    """Reject student requests whose Django session is no longer the active one."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = None
        session_key = request.session.session_key
        if request.session.get("user_role") == "student":
            user = User.objects.filter(id=request.session.get("user_id"), role="student").first()
            key = session_key
            if not student_session_is_active(user, key):
                reason = 'idle_timeout' if user and key == user.active_session_key and student_session_timed_out(user) else 'session_replaced'
                if user and key == user.active_session_key:
                    release_student_session(user.id, key)
                request.session.flush()
                accept = request.META.get("HTTP_ACCEPT", "") or ""
                if (request.method != 'GET' or request.path.startswith('/api/')
                        or request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
                        or 'application/json' in accept):
                    return JsonResponse({"success": False, "code": reason, "error": "Your session has ended. Please sign in again."}, status=401)
                return redirect("auth")
            # Polling proves presence, not user interaction. Device ownership
            # and idle validity are checked above, before any refresh.
            now = session_now()
            # Live readers poll and publish every few seconds. A presence
            # lease needs one refresh per heartbeat interval, not a SQLite
            # write for every student's poll and speech request.
            if not user.active_session_last_seen or user.active_session_last_seen <= now - timedelta(seconds=30):
                User.objects.filter(pk=user.pk, active_session_key=key).update(active_session_last_seen=now)
        elif session_key:
            # A re-authentication redirect can arrive with a session whose
            # payload was cleared or invalidated before the middleware could
            # identify its user. Release only the matching student's stale
            # claim, using the server-side session key as the ownership proof.
            User.objects.filter(
                role="student", active_session_key=session_key,
            ).update(
                active_session_key=None, active_session_created_at=None,
                last_activity=None, active_session_last_seen=None,
                active_session_learning=False,
            )
        response = self.get_response(request)
        if (not user or request.session.get('user_role') != 'student' or response.streaming
                or response.status_code != 200 or 'text/html' not in response.get('Content-Type', '')
                or response.get('Content-Encoding') or response.get('Content-Disposition')):
            return response
        # Standalone learning screens do not inherit the dashboard template.
        # Only full authenticated student documents receive this shared UI.
        content = response.content
        body_end = content.lower().rfind(b'</body>')
        if body_end < 0:
            return response
        learning = is_learning_page(request.path)
        now = session_now()
        updated = User.objects.filter(pk=user.pk, active_session_key=key).update(
            last_activity=now, active_session_last_seen=now, active_session_learning=learning,
        )
        if not updated:
            return response
        user.last_activity, user.active_session_learning = now, learning
        config = {
            **student_session_status(user, now), 'learning_page': learning,
            'heartbeat_url': reverse('student_session_heartbeat'),
            'login_url': reverse('auth'), 'logout_url': reverse('logout'),
            'csrf_token': get_token(request),
            'channel': hashlib.sha256(key.encode()).hexdigest()[:16],
        }
        fragment = render_to_string('pabasa_app/student_session_script.html', {'student_session_config': config}).encode(response.charset)
        response.content = content[:body_end] + fragment + content[body_end:]
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        patch_cache_control(response, private=True, no_store=True)
        return response
