"""Initial credentials for newly created student accounts."""
from django.contrib.auth.hashers import make_password


DEFAULT_NEW_STUDENT_PASSWORD = '12345678'


def default_student_password_hash():
    return make_password(DEFAULT_NEW_STUDENT_PASSWORD)


def default_new_account_password_hash():
    """Compatibility callable for the already-applied 0031 migration."""
    return default_student_password_hash()
