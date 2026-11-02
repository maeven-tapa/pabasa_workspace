from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
import hashlib

from .models import User


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
            user = User.objects.filter(id=request.session.get('user_id'), role='principal', is_archived=False).first()
            if not user or user.account_status == 'archived':
                request.session.flush()
                return redirect('auth')
            version = hashlib.sha256(user.password_hash.encode()).hexdigest()
            previous = request.session.get('principal_password_version')
            if not previous and user.must_change_password:
                # A session predating credential versioning must not consume
                # a newly issued temporary password without authenticating it.
                request.session.flush()
                return redirect('auth')
            if previous and previous != version:
                request.session.flush()
                return redirect('auth')
            request.session['principal_password_version'] = version
            from .principal_security import temporary_password_expired
            if temporary_password_expired(user) and request.path != reverse('logout'):
                request.session.flush()
                return redirect('auth')
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
