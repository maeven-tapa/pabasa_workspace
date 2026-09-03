from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone

from .models import User
from .student_session_lock import release_student_session, student_session_is_active


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
        if request.session.get("user_role") == "student":
            user = User.objects.filter(id=request.session.get("user_id"), role="student").first()
            key = request.session.session_key
            if not student_session_is_active(user, key):
                if user and key == user.active_session_key:
                    release_student_session(user.id, key)
                request.session.flush()
                accept = request.META.get("HTTP_ACCEPT", "") or ""
                if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest" or accept.startswith("application/json"):
                    return JsonResponse({"success": False, "error": "This student session is no longer valid. Please log in again."}, status=401)
                return redirect("auth")
            User.objects.filter(pk=user.pk, active_session_key=key).update(last_activity=timezone.now())
        return self.get_response(request)
