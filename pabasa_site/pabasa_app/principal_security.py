"""Principal credential policy. Never store or log the clear-text secret."""
import secrets
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .system_clock import real_now


def temporary_password():
    return secrets.token_urlsafe(24) + "aA1!"


def issue_temporary_password(user):
    secret = temporary_password()
    user.set_password(secret)
    user.must_change_password = True
    user.principal_password_expires_at = real_now() + timedelta(hours=24)
    return secret


def temporary_password_expired(user):
    return bool(user.role == 'principal' and user.must_change_password and (
        not user.principal_password_expires_at or user.principal_password_expires_at <= real_now()
    ))


def validate_principal_password(password, user):
    validate_password(password, user=user)
    if not (any(c.isupper() for c in password) and any(c.islower() for c in password)
            and any(c.isdigit() for c in password) and any(not c.isalnum() for c in password)):
        raise ValidationError('Use uppercase and lowercase letters, a number, and a special character.')
