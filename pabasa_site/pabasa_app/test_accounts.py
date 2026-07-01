from django.contrib.auth.hashers import make_password

TEACHER_TEST_CUSTOM_ID = "TCH-9999"
TEACHER_TEST_PASSWORD = "teacher123"
STUDENT_TEST_CUSTOM_ID = "STD-9999"
STUDENT_TEST_PASSWORD = "student123"
PRINCIPAL_DEFAULT_CUSTOM_ID = "PRN-SES"
PRINCIPAL_DEFAULT_PASSWORD = "Principal@123"

LEGACY_TEST_CUSTOM_IDS = ("TCH-TEST", "STD-TEST")

DEFAULT_TEST_ACCOUNTS = (
    {
        "custom_id": TEACHER_TEST_CUSTOM_ID,
        "role": "teacher",
        "first_name": "Testing",
        "last_name": "Teacher",
        "password": TEACHER_TEST_PASSWORD,
        "email": "teacher-test@pabasa.local",
    },
    {
        "custom_id": STUDENT_TEST_CUSTOM_ID,
        "role": "student",
        "first_name": "Testing",
        "last_name": "Student",
        "password": STUDENT_TEST_PASSWORD,
        "email": "student-test@pabasa.local",
    },
)

DEFAULT_PRINCIPAL_ACCOUNT = {
    "custom_id": PRINCIPAL_DEFAULT_CUSTOM_ID,
    "role": "principal",
    "first_name": "Principal",
    "last_name": "Account",
    "password": PRINCIPAL_DEFAULT_PASSWORD,
    "email": "principal@pabasa.local",
}

DEFAULT_SEED_ACCOUNTS = DEFAULT_TEST_ACCOUNTS + (DEFAULT_PRINCIPAL_ACCOUNT,)


def _build_user_defaults(account):
    return {
        "role": account["role"],
        "first_name": account["first_name"],
        "last_name": account["last_name"],
        "middle_initial": "",
        "suffix": "",
        "sex": "N/A",
        "birth_month": 1,
        "birth_day": 1,
        "birth_year": 2026,
        "email": account["email"],
        "contact_no": "",
        "password_hash": make_password(account["password"]),
    }


def _upsert_account(User, account):
    return User.objects.update_or_create(
        custom_id=account["custom_id"],
        defaults=_build_user_defaults(account),
    )


def ensure_default_test_accounts(User=None):
    """
    Create default teacher/student/principal accounts when missing.
    Returns a list of (custom_id, created) tuples.
    """
    if User is None:
        from pabasa_app.models import User

    User.objects.filter(custom_id__in=LEGACY_TEST_CUSTOM_IDS).delete()

    results = []
    for account in DEFAULT_SEED_ACCOUNTS:
        _, created = _upsert_account(User, account)
        results.append((account["custom_id"], created))
    return results


def ensure_default_principal_account(User=None):
    if User is None:
        from pabasa_app.models import User

    _, created = User.objects.get_or_create(
        custom_id=DEFAULT_PRINCIPAL_ACCOUNT["custom_id"],
        defaults=_build_user_defaults(DEFAULT_PRINCIPAL_ACCOUNT),
    )
    return DEFAULT_PRINCIPAL_ACCOUNT["custom_id"], created


def remove_default_test_accounts(User=None):
    if User is None:
        from pabasa_app.models import User

    custom_ids = [account["custom_id"] for account in DEFAULT_SEED_ACCOUNTS]
    custom_ids.extend(LEGACY_TEST_CUSTOM_IDS)
    User.objects.filter(custom_id__in=custom_ids).delete()
