from django.shortcuts import redirect
from django.urls import reverse

from .models import User


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
