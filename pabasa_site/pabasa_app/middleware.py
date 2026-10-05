from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse

from .models import User
from .student_session_lock import (
    release_student_session, student_session_is_active,
)


class PersistentSessionMiddleware:
    """Normalize existing and new logins to the site's persistent lifetime."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.session.get('user_id') or request.session.get('_auth_user_id'):
            if request.session.get('_session_expiry') != settings.SESSION_COOKIE_AGE:
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return response


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
        session_key = request.session.session_key
        if request.session.get("user_role") == "student":
            user = User.objects.filter(id=request.session.get("user_id"), role="student").first()
            key = session_key
            if not student_session_is_active(user, key):
                if user and key == user.active_session_key:
                    release_student_session(user.id, key)
                request.session.flush()
                accept = request.META.get("HTTP_ACCEPT", "") or ""
                if (request.method != 'GET' or request.path.startswith('/api/')
                        or request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
                        or 'application/json' in accept):
                    return JsonResponse({"success": False, "code": "session_replaced", "error": "Please sign in again."}, status=401)
                return redirect("auth")
        elif session_key:
            # A re-authentication redirect can arrive with a session whose
            # payload was cleared or invalidated before the middleware could
            # identify its user. Release only the matching student's stale
            # claim, using the server-side session key as the ownership proof.
            User.objects.filter(
                role="student", active_session_key=session_key,
            ).update(
                active_session_key=None, active_session_created_at=None,
            )
        return self.get_response(request)
