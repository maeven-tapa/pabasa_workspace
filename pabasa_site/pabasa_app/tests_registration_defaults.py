"""Optional signup email and default credentials preserve account boundaries."""
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.hashers import check_password, make_password
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .admin import UserAdmin, UserAdminForm
from .models import Enrollment, Notification, OtpDebugSettings, School, SchoolCalendar, Section, User
from .views import _create_principal_account, _principal_temporary_password


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistrationDefaultsTests(TestCase):
    def setUp(self):
        self.existing = self.create_user('ADM-DEFAULTS', role='admin', email='defaults-admin@example.com',
                                         password_hash=make_password('ExistingPrivatePassword123'))
        self.school = School.objects.create(name='Defaults Test School', code='DEFAULTS-TEST')
        SchoolCalendar.objects.update(is_active=False)
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
        self.sections = [Section.objects.create(
            school=self.school, school_calendar=self.calendar,
            class_code=f'DEFAULTS-{i}', class_name=f'Grade 2 Defaults {i}',
            grade_level='Grade 2', section=f'DEFAULTS{i}', is_active=True,
        ) for i in range(3)]
        self.emails = {}
        for name in ('send_teacher_signup_otp_email', 'send_student_signup_otp_email',
                     'send_teacher_confirmation_email', 'send_student_confirmation_email'):
            patcher = patch(f'pabasa_app.views.{name}')
            self.emails[name] = patcher.start()
            self.addCleanup(patcher.stop)

    def create_user(self, custom_id, **kwargs):
        defaults = dict(role='student', first_name='Defaults', last_name='Account', sex='female',
                        birth_month=1, birth_day=1, birth_year=1990)
        defaults.update(kwargs)
        return User.objects.create(custom_id=custom_id, **defaults)

    def payload(self, role='student', number=0, **changes):
        data = dict(first_name='Defaults', last_name='Account', sex='female', birth_month='1',
                    birth_day='5', birth_year='2018' if role == 'student' else '1990',
                    school_id=str(self.school.pk), section=str(self.sections[number].pk),
                    lrn=f'1234567890{number:02d}')
        data.update(email=f'{role}-{number}@example.com', password='StudentPrivatePassword123', confirm_password='StudentPrivatePassword123')
        if role == 'teacher':
            data.update(password='TeacherPrivatePassword123', confirm_password='TeacherPrivatePassword123')
        data.update(changes)
        return data

    def signup(self, role='student', number=0, **changes):
        return self.client.post(reverse(f'register_{role}'), self.payload(role, number, **changes))

    def login(self, user):
        session = self.client.session
        session['user_id'] = user.pk
        session['user_role'] = user.role
        session.save()

    def test_model_does_not_unconditionally_assign_a_default_password(self):
        for role in ('admin', 'principal', 'teacher', 'student'):
            user = self.create_user(f'DEFAULT-{role}', role=role)
            self.assertFalse(check_password('12345678', user.password_hash))
            self.assertNotEqual(user.password_hash, '12345678')
            self.assertIsNone(user.email)

    def test_empty_email_is_null_and_multiple_accounts_can_omit_it(self):
        first = self.create_user('EMAILLESS-1', email='')
        second = self.create_user('EMAILLESS-2', email='')
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(first.email)
        self.assertIsNone(second.email)

    def test_existing_account_password_is_preserved_on_save_and_schema_defaults(self):
        original_hash = self.existing.password_hash
        self.existing.first_name = 'Updated'
        self.existing.save()
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.password_hash, original_hash)
        self.assertTrue(check_password('ExistingPrivatePassword123', self.existing.password_hash))
        self.assertFalse(check_password('12345678', self.existing.password_hash))

    def test_email_is_optional_only_while_otp_is_disabled(self):
        for role in ('student', 'teacher'):
            for number, debug in enumerate((False, True)):
                with self.subTest(role=role, debug=debug):
                    OtpDebugSettings.objects.update_or_create(pk=1, defaults={'disable_otp': debug})
                    response = self.signup(role, number, email='')
                    if not debug:
                        self.assertEqual(response.status_code, 400)
                        self.assertIn('email', response.json()['error'].lower())
                        continue
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.json()['success'])
                    self.assertTrue(response.json()['otp_disabled'])
                    user = User.objects.get(custom_id=response.json()['custom_id'])
                    self.assertIsNone(user.email)
                    password = '12345678' if role == 'student' else 'TeacherPrivatePassword123'
                    self.assertTrue(check_password(password, user.password_hash))
                    self.assertEqual(user.school_record_id, self.school.pk)
                    self.assertEqual(user.school_calendar_id, self.calendar.pk)
                    self.assertNotIn(f'pending_{role}_signup', self.client.session)
                    self.emails[f'send_{role}_signup_otp_email'].assert_not_called()
                    self.emails[f'send_{role}_confirmation_email'].assert_not_called()
                    if role == 'student':
                        self.assertTrue(Enrollment.objects.filter(student=user, section=self.sections[number]).exists())
                    else:
                        self.sections[number].refresh_from_db()
                        self.assertEqual(self.sections[number].teacher_id, user.pk)
        self.assertTrue(Notification.objects.filter(recipient=self.existing, title='New student account').exists())

    def test_empty_and_whitespace_email_are_optional(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        for number, email in enumerate(('', '   ')):
            response = self.signup(number=number, email=email)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(User.objects.get(custom_id=response.json()['custom_id']).email)

    def test_submitted_signup_password_cannot_replace_the_default(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        response = self.signup('student', password='UnexpectedPassword123', confirm_password='different')
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(custom_id=response.json()['custom_id'])
        self.assertTrue(check_password('12345678', user.password_hash))
        self.assertFalse(check_password('UnexpectedPassword123', user.password_hash))

    def test_teacher_must_choose_and_confirm_its_own_password(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        for changes in ({'password': ''}, {'confirm_password': ''}, {'confirm_password': 'different'}):
            self.assertEqual(self.signup('teacher', **changes).status_code, 400)
        response = self.signup('teacher')
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(custom_id=response.json()['custom_id'])
        self.assertTrue(check_password('TeacherPrivatePassword123', user.password_hash))
        self.assertFalse(check_password('12345678', user.password_hash))

    def test_enabled_otp_requires_verification_and_preserves_chosen_password(self):
        for role in ('student', 'teacher'):
            email = f'optional-{role}@example.com'
            response = self.signup(role, email=email)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('otp_disabled', response.json())
            self.assertFalse(User.objects.filter(email=email).exists())
            self.emails[f'send_{role}_signup_otp_email'].assert_called_once()
            response = self.client.post(reverse(f'verify_{role}_otp'), {
                'otp': self.client.session[f'pending_{role}_signup_otp'],
            })
            self.assertEqual(response.status_code, 200)
            user = User.objects.get(email=email)
            password = 'StudentPrivatePassword123' if role == 'student' else 'TeacherPrivatePassword123'
            self.assertTrue(check_password(password, user.password_hash))
            self.emails[f'send_{role}_confirmation_email'].assert_called_once()

    def test_supplied_email_still_follows_debug_switch(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        response = self.signup(email='debug-default@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['otp_disabled'])
        self.emails['send_student_signup_otp_email'].assert_not_called()
        self.emails['send_student_confirmation_email'].assert_called_once()

    def test_invalid_or_duplicate_email_is_rejected_if_supplied(self):
        for role in ('student', 'teacher'):
            for email in ('invalid-email', self.existing.email.upper()):
                response = self.signup(role, email=email)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['success'])

    def test_omitting_email_preserves_lrn_birth_and_assignment_validation(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        self.assertEqual(self.signup(lrn='bad-lrn').status_code, 400)
        self.assertEqual(self.signup(birth_day='32').status_code, 400)
        self.assertEqual(self.signup(section='999999').status_code, 400)
        self.assertEqual(self.signup().status_code, 200)
        self.assertEqual(self.signup(number=1, lrn=self.payload()['lrn']).status_code, 400)
        self.assertEqual(self.signup('teacher').status_code, 200)
        self.assertEqual(self.signup('teacher').status_code, 409)

    def test_email_less_account_can_log_in_change_password_and_edit_profile(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        response = self.signup(email='')
        user = User.objects.get(custom_id=response.json()['custom_id'])
        response = self.client.post(reverse('login_user'), {'custom_id': user.custom_id, 'password': '12345678'})
        self.assertTrue(response.json()['success'])
        response = self.client.post(reverse('profile'), {
            'save_account_details': 'true', 'first_name': 'Edited', 'last_name': 'Account', 'email': '',
        })
        self.assertTrue(response.json()['success'])
        response = self.client.post(reverse('settings'), {
            'settings_action': 'change_password', 'current_password': '12345678',
            'new_password': 'PrivatePassword123', 'confirm_password': 'PrivatePassword123',
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(check_password('PrivatePassword123', user.password_hash))
        self.assertIsNone(user.email)

    def test_email_less_accounts_do_not_enable_email_password_recovery(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        self.signup(email='')
        response = self.client.post(reverse('request_password_reset'), {'email': ''})
        self.assertContains(response, 'Email is required')
        self.assertNotIn('password_reset_verified', self.client.session)

    def test_new_principal_keeps_original_temporary_password_and_first_login_change(self):
        request = RequestFactory().get('/')
        user, initial_password = _create_principal_account(
            request, self.school, 'New', '', 'Principal', '', 'new-principal@example.com', '',
        )
        self.assertEqual(initial_password, 'PRINCIPAL123')
        self.assertTrue(check_password('PRINCIPAL123', user.password_hash))
        self.assertFalse(check_password('12345678', user.password_hash))
        self.assertTrue(user.must_change_password)
        response = self.client.post(reverse('login_user'), {'custom_id': user.custom_id, 'password': initial_password})
        self.assertEqual(response.json()['redirect_url'], reverse('principal_change_temporary_password'))

    def test_existing_principal_reset_password_rule_is_unchanged(self):
        self.assertEqual(_principal_temporary_password('Principal'), 'PRINCIPAL123')

    def test_django_admin_defaults_only_new_students_and_preserves_other_passwords(self):
        OtpDebugSettings.objects.create(disable_otp=True)
        model_admin = UserAdmin(User, admin.site)
        request = RequestFactory().post('/')
        for role in ('admin', 'teacher', 'student', 'principal'):
            user = User(role=role, first_name='Created', last_name='ByAdmin', sex='female',
                        birth_month=1, birth_day=1, birth_year=1990, email=None,
                        password_hash=make_password('SubmittedPassword123'))
            model_admin.save_model(request, user, None, change=False)
            password = '12345678' if role == 'student' else 'SubmittedPassword123'
            self.assertTrue(check_password(password, user.password_hash))
            self.assertEqual(check_password('12345678', user.password_hash), role == 'student')
            self.assertTrue(user.custom_id)
        original_hash = self.existing.password_hash
        model_admin.save_model(request, self.existing, None, change=True)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.password_hash, original_hash)

    def test_signup_pages_explain_optional_email_and_show_fixed_password(self):
        for disabled in (False, True):
            OtpDebugSettings.objects.update_or_create(pk=1, defaults={'disable_otp': disabled})
            for role in ('student', 'teacher'):
                response = self.client.get(reverse(f'{role}_signup'))
                self.assertEqual(response.context['otp_debug_disabled'], disabled)
                if disabled:
                    self.assertContains(response, 'data-signup-email-label>Email address (optional)</label>')
                else:
                    self.assertContains(response, 'data-signup-email-label>Email address</label>')
                self.assertContains(response, 'name="password"')
                self.assertContains(response, 'name="confirm_password"')
                if role == 'student':
                    self.assertContains(response, 'studentChosenPasswordPanel')
                    self.assertContains(response, 'studentDebugPasswordPanel')
                else:
                    self.assertNotContains(response, '12345678')

    def test_admin_form_requires_password_hash_for_new_non_student_accounts(self):
        for disabled in (False, True):
            OtpDebugSettings.objects.update_or_create(pk=1, defaults={'disable_otp': disabled})
            for role in ('admin', 'principal', 'teacher', 'student'):
                form = UserAdminForm(data={
                    'role': role, 'first_name': 'Admin', 'last_name': 'Created', 'sex': 'female',
                    'birth_month': 1, 'birth_day': 1, 'birth_year': 1990,
                })
                form.is_valid()
                self.assertEqual('password_hash' in form.errors, not (role == 'student' and disabled))

    def test_enabled_student_otp_rejects_missing_email_and_password_fields(self):
        for changes in ({'email': ''}, {'email': '   '}, {'password': ''},
                        {'confirm_password': ''}, {'confirm_password': 'different'},
                        {'password': 'short', 'confirm_password': 'short'}):
            response = self.signup(**changes)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(User.objects.filter(email='student-0@example.com').exists())

    def test_client_cannot_disable_otp_to_skip_email_or_chosen_password(self):
        response = self.signup(email='', disable_otp='on')
        self.assertEqual(response.status_code, 400)
        response = self.signup(signup_otp_disabled='true')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['signup_otp_disabled'])

    def test_stale_signup_form_is_rejected_in_both_directions(self):
        for role in ('student', 'teacher'):
            for disabled in (False, True):
                OtpDebugSettings.objects.update_or_create(pk=1, defaults={'disable_otp': disabled})
                response = self.signup(role, signup_otp_disabled=str(not disabled).lower())
                self.assertEqual(response.status_code, 409)
                self.assertTrue(response.json()['policy_changed'])
                self.assertEqual(response.json()['signup_otp_disabled'], disabled)

    def test_pending_student_uses_default_if_otp_is_disabled_before_completion(self):
        self.signup()
        OtpDebugSettings.objects.create(disable_otp=True)
        response = self.client.post(reverse('resend_student_signup_otp'))
        self.assertEqual(response.status_code, 200)
        student = User.objects.get(custom_id=response.json()['custom_id'])
        self.assertTrue(check_password('12345678', student.password_hash))
        self.assertFalse(check_password('StudentPrivatePassword123', student.password_hash))

    def test_admin_student_creation_keeps_chosen_password_when_otp_is_enabled(self):
        user = User(role='student', first_name='New', last_name='Student', email='admin-student@example.com',
                    sex='female', birth_month=1, birth_day=1, birth_year=2018,
                    password_hash=make_password('AdminChosenPassword123'))
        UserAdmin(User, admin.site).save_model(RequestFactory().post('/'), user, None, change=False)
        self.assertTrue(check_password('AdminChosenPassword123', user.password_hash))
        self.assertFalse(check_password('12345678', user.password_hash))
