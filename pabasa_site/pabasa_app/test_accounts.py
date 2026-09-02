from django.contrib.auth.hashers import make_password

TEACHER_TEST_CUSTOM_ID = "TCH-9999"
TEACHER_TEST_PASSWORD = "Testing123"
STUDENT_TEST_CUSTOM_ID = "G2-9999"
STUDENT_TEST_PASSWORD = "Testing123"
LEGACY_TEST_CUSTOM_IDS = ("TCH-TEST", "STD-TEST")

DEFAULT_TEST_ACCOUNTS = (
    {
        "custom_id": TEACHER_TEST_CUSTOM_ID,
        "role": "teacher",
        "first_name": "Test",
        "last_name": "Teacher",
        "sex": "Female",
        "birth_month": 1,
        "birth_day": 1,
        "birth_year": 2000,
        "section": "Aguinaldo",
        "password": TEACHER_TEST_PASSWORD,
        "email": "nica.flores-test@pabasa.local",
    },
    {
        "custom_id": STUDENT_TEST_CUSTOM_ID,
        "role": "student",
        "first_name": "Test",
        "last_name": "Student",
        "sex": "Female",
        "birth_month": 1,
        "birth_day": 1,
        "birth_year": 2019,
        "section": "Aguinaldo",
        "grade_level": "Grade 2",
        # The application requires a 12-digit LRN; this is intentionally fake.
        "lrn": "999999999999",
        "password": STUDENT_TEST_PASSWORD,
        "email": "nicole.flores-test@pabasa.local",
    },
)

DEFAULT_SEED_ACCOUNTS = DEFAULT_TEST_ACCOUNTS


def _build_user_defaults(account):
    return {
        "role": account["role"],
        "first_name": account["first_name"],
        "last_name": account["last_name"],
        "middle_initial": "",
        "suffix": "",
        "sex": account.get("sex", "N/A"),
        "birth_month": account.get("birth_month", 1),
        "birth_day": account.get("birth_day", 1),
        "birth_year": account.get("birth_year", 2026),
        "email": account["email"],
        "contact_no": "",
        "password_hash": make_password(account["password"]),
        "section": account.get("section"),
        "grade_level": account.get("grade_level"),
        "lrn": account.get("lrn"),
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


def remove_default_test_accounts(User=None):
    if User is None:
        from pabasa_app.models import User

    custom_ids = [account["custom_id"] for account in DEFAULT_SEED_ACCOUNTS]
    custom_ids.extend(LEGACY_TEST_CUSTOM_IDS)
    User.objects.filter(custom_id__in=custom_ids).delete()
