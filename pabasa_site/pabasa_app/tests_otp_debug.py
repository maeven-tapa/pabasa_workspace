"""OTP debugging must skip only verification and preserve completion workflows."""
import time
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import ActivityLog, Enrollment, OtpDebugSettings, School, SchoolCalendar, Section, User
from .views import _otp_debug_disabled


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OtpDebugTests(TestCase):
    def setUp(self):
        self.admin = self.make_user('OTP-ADMIN', 'admin', 'otp-admin@example.com')
        self.teacher = self.make_user('OTP-TEACHER', 'teacher', 'otp-teacher@example.com')
        self.school = School.objects.create(name='OTP Test School', code='OTP-TEST')
        SchoolCalendar.objects.update(is_active=False)
        self.calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
        self.section = Section.objects.create(
            school=self.school, school_calendar=self.calendar, class_code='OTP-CLASS',
            class_name='Grade 2 OTP', grade_level='Grade 2', section='OTP',
            teacher=self.teacher, is_active=True,
        )
        self.empty_section = Section.objects.create(
            school=self.school, school_calendar=self.calendar, class_code='OTP-EMPTY',
            class_name='Grade 2 Empty', grade_level='Grade 2', section='EMPTY', is_active=True,
        )
        self.emails = {}
        for name in (
            'send_teacher_signup_otp_email', 'send_student_signup_otp_email',
            'send_password_reset_otp_email', 'send_teacher_confirmation_email',
            'send_student_confirmation_email', 'send_password_reset_confirmation_email',
        ):
            patcher = patch(f'pabasa_app.views.{name}')
            self.emails[name] = patcher.start()
            self.addCleanup(patcher.stop)

    def make_user(self, custom_id, role, email):
        return User.objects.create(
            custom_id=custom_id, role=role, first_name='Debug', last_name='Account',
            email=email, sex='female', birth_month=1, birth_day=1, birth_year=1990,
            password_hash=make_password('OriginalPassword123'),
        )

    def login_admin(self, client=None):
        client = client or self.client
        session = client.session
        session['user_id'] = self.admin.pk
        session['user_role'] = 'admin'
        session.save()

    def set_debug(self, enabled=True):
        OtpDebugSettings.objects.update_or_create(pk=1, defaults={'disable_otp': enabled})

    def signup_payload(self, role='student'):
        return {
            'first_name': 'Debug', 'last_name': role.title(),
            'email': f'new-{role}@example.com', 'password': 'SignupPassword123',
            'confirm_password': 'SignupPassword123', 'sex': 'female',
            'birth_month': '1', 'birth_day': '5', 'birth_year': '2018' if role == 'student' else '1990',
            'school_id': str(self.school.pk), 'grade_level': 'Grade 2',
            'section': str(self.section.pk if role == 'student' else self.empty_section.pk),
            'lrn': '123456789012',
        }

    def start_signup(self, role='student', **changes):
        payload = self.signup_payload(role)
        payload.update(changes)
        return self.client.post(reverse(f'register_{role}'), payload)

    def start_reset(self):
        return self.client.post(reverse('request_password_reset'), {'email': self.teacher.email})

    def test_default_requires_otp_without_creating_settings(self):
        self.assertFalse(_otp_debug_disabled())
        self.assertFalse(OtpDebugSettings.objects.exists())
        self.login_admin()
        response = self.client.get(reverse('admin_settings'))
        self.assertContains(response, 'Disable OTP')
        self.assertFalse(response.context['otp_debug_disabled'])

    def test_admin_can_save_both_states_and_audit_them(self):
        self.login_admin()
        for enabled in (True, False):
            data = {'settings_action': 'save_otp_debug'}
            if enabled:
                data['disable_otp'] = 'on'
            response = self.client.post(reverse('admin_settings'), data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(_otp_debug_disabled(), enabled)
            self.assertEqual(response.context['otp_debug_disabled'], enabled)
            entry = ActivityLog.objects.filter(event_type='otp_debug').latest('id')
            self.assertEqual(entry.actor_id, self.admin.pk)
            self.assertEqual(entry.metadata, {'disable_otp': enabled})

    def test_anonymous_teacher_student_and_principal_cannot_change_switch(self):
        for role in (None, 'teacher', 'student', 'principal'):
            with self.subTest(role=role):
                client = Client()
                if role:
                    session = client.session
                    session['user_id'] = self.teacher.pk
                    session['user_role'] = role
                    session.save()
                response = client.post(reverse('admin_settings'), {
                    'settings_action': 'save_otp_debug', 'disable_otp': 'on',
                })
                self.assertEqual(response.status_code, 302)
                self.assertFalse(_otp_debug_disabled())

    def test_switch_checks_actual_admin_account_and_csrf(self):
        self.login_admin()
        self.admin.role = 'teacher'
        self.admin.save(update_fields=['role'])
        response = self.client.post(reverse('admin_settings'), {
            'settings_action': 'save_otp_debug', 'disable_otp': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(_otp_debug_disabled())
        self.admin.role = 'admin'
        self.admin.save(update_fields=['role'])
        client = Client(enforce_csrf_checks=True)
        self.login_admin(client)
        response = client.post(reverse('admin_settings'), {
            'settings_action': 'save_otp_debug', 'disable_otp': 'on',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(_otp_debug_disabled())

    def test_other_admin_settings_do_not_change_otp(self):
        self.set_debug()
        self.login_admin()
        self.client.post(reverse('admin_settings'), {'settings_action': 'save_notifications'})
        self.assertTrue(_otp_debug_disabled())

    def test_debug_signups_keep_accounts_ids_enrollment_and_confirmation(self):
        self.set_debug()
        for role in ('student', 'teacher'):
            with self.subTest(role=role):
                response = self.start_signup(role)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['otp_disabled'])
                user = User.objects.get(email=self.signup_payload(role)['email'])
                self.assertEqual(user.custom_id, response.json()['custom_id'])
                self.assertEqual(user.school_record_id, self.school.pk)
                self.assertEqual(user.school_calendar_id, self.calendar.pk)
                password = '12345678' if role == 'student' else 'SignupPassword123'
                self.assertTrue(check_password(password, user.password_hash))
                self.emails[f'send_{role}_signup_otp_email'].assert_not_called()
                self.emails[f'send_{role}_confirmation_email'].assert_called_once()
                self.assertNotIn(f'pending_{role}_signup', self.client.session)
                if role == 'student':
                    self.assertTrue(Enrollment.objects.filter(student=user, section=self.section).exists())
                    self.assertEqual(user.lrn, '123456789012')
                else:
                    self.empty_section.refresh_from_db()
                    self.assertEqual(self.empty_section.teacher_id, user.pk)

    def test_debug_signups_still_reject_invalid_data_and_school(self):
        self.set_debug()
        for role in ('student', 'teacher'):
            for changes in ({'first_name': ''},
                            {'birth_day': '32'}, {'school_id': '999999'}, {'section': '999999'}):
                with self.subTest(role=role, changes=changes):
                    response = self.start_signup(role, **changes)
                    self.assertFalse(response.json()['success'])
                    self.assertFalse(User.objects.filter(email=self.signup_payload(role)['email']).exists())

    def test_debug_signups_still_reject_duplicate_email_and_assigned_teacher(self):
        self.set_debug()
        self.assertEqual(self.start_signup(email=self.teacher.email).status_code, 400)
        self.assertEqual(self.start_signup('teacher', section=str(self.section.pk)).status_code, 409)

    def test_enabled_otp_signups_still_send_verify_and_complete(self):
        for role in ('student', 'teacher'):
            with self.subTest(role=role):
                response = self.start_signup(role, disable_otp='on')
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('otp_disabled', response.json())
                self.assertFalse(User.objects.filter(email=self.signup_payload(role)['email']).exists())
                self.emails[f'send_{role}_signup_otp_email'].assert_called_once()
                key = f'pending_{role}_signup_otp'
                response = self.client.post(reverse(f'verify_{role}_otp'), {'otp': 'incorrect', 'disable_otp': 'on'})
                self.assertEqual(response.status_code, 400)
                response = self.client.post(reverse(f'verify_{role}_otp'), {'otp': self.client.session[key]})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
                self.assertNotIn('otp_disabled', response.json())

    def test_pending_signup_can_finish_without_otp_after_admin_enables_debug(self):
        for role in ('student', 'teacher'):
            self.set_debug(False)
            self.start_signup(role)
            self.set_debug()
            response = self.client.post(reverse(f'verify_{role}_otp'), {})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['otp_disabled'])

    def test_pending_signup_resend_skips_email_during_debug(self):
        for role in ('student', 'teacher'):
            self.set_debug(False)
            self.start_signup(role)
            self.emails[f'send_{role}_signup_otp_email'].reset_mock()
            self.set_debug()
            response = self.client.post(reverse(f'resend_{role}_signup_otp'))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['otp_disabled'])
            self.emails[f'send_{role}_signup_otp_email'].assert_not_called()

    def test_debug_verification_still_requires_pending_signup_and_expiry(self):
        self.set_debug()
        for role in ('student', 'teacher'):
            response = self.client.post(reverse(f'verify_{role}_otp'))
            self.assertEqual(response.status_code, 400)
            self.set_debug(False)
            self.start_signup(role)
            session = self.client.session
            session[f'pending_{role}_signup_otp_created'] = time.time() - 601
            session.save()
            self.set_debug()
            response = self.client.post(reverse(f'verify_{role}_otp'))
            self.assertEqual(response.status_code, 400)
            self.assertIn('expired', response.json()['error'])

    def test_turning_debug_off_restores_signup_otp(self):
        self.set_debug()
        self.set_debug(False)
        self.start_signup()
        response = self.client.post(reverse('verify_student_otp'))
        self.assertEqual(response.status_code, 400)
        self.emails['send_student_signup_otp_email'].assert_called_once()

    def test_debug_password_reset_skips_otp_and_keeps_confirmation_and_cleanup(self):
        self.set_debug()
        response = self.start_reset()
        self.assertRedirects(response, f"{reverse('forgot_password_reset')}?email={self.teacher.email}")
        self.emails['send_password_reset_otp_email'].assert_not_called()
        self.assertTrue(self.client.session['password_reset_otp_bypassed'])
        response = self.client.post(reverse('reset_password'), {
            'email': self.teacher.email, 'password': 'NewPassword123', 'confirm_password': 'NewPassword123',
        })
        self.assertContains(response, 'Your password has been updated.')
        self.teacher.refresh_from_db()
        self.assertTrue(check_password('NewPassword123', self.teacher.password_hash))
        self.emails['send_password_reset_confirmation_email'].assert_called_once()
        for key in ('password_reset_verified', 'password_reset_email', 'password_reset_otp_bypassed',
                    'pending_password_reset', 'pending_password_reset_otp'):
            self.assertNotIn(key, self.client.session)

    def test_debug_password_reset_preserves_email_binding_and_password_match(self):
        self.set_debug()
        self.start_reset()
        response = self.client.post(reverse('reset_password'), {
            'email': self.admin.email, 'password': 'NewPassword123', 'confirm_password': 'NewPassword123',
        })
        self.assertRedirects(response, reverse('forgot_password'))
        response = self.client.post(reverse('reset_password'), {
            'email': self.teacher.email, 'password': 'NewPassword123', 'confirm_password': 'wrong',
        })
        self.assertContains(response, 'Passwords do not match')
        self.teacher.refresh_from_db()
        self.assertTrue(check_password('OriginalPassword123', self.teacher.password_hash))

    def test_debug_password_reset_requires_existing_account_and_started_session(self):
        self.set_debug()
        response = self.client.post(reverse('request_password_reset'), {'email': 'missing@example.com'})
        self.assertContains(response, 'No account found')
        response = self.client.post(reverse('verify_forgot_password_otp'), {'email': self.teacher.email})
        self.assertContains(response, 'No pending password reset')
        response = self.client.post(reverse('reset_password'), {
            'email': self.teacher.email, 'password': 'NewPassword123', 'confirm_password': 'NewPassword123',
        })
        self.assertRedirects(response, reverse('forgot_password'))

    def test_pending_password_reset_verification_can_skip_otp_after_toggle(self):
        self.start_reset()
        self.set_debug()
        response = self.client.post(reverse('verify_forgot_password_otp'), {'email': self.teacher.email})
        self.assertRedirects(response, f"{reverse('forgot_password_reset')}?email={self.teacher.email}")
        self.assertTrue(self.client.session['password_reset_otp_bypassed'])

    def test_pending_password_reset_resend_skips_email_during_debug(self):
        self.start_reset()
        self.emails['send_password_reset_otp_email'].reset_mock()
        self.set_debug()
        response = self.client.get(reverse('resend_password_reset_otp'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session['password_reset_otp_bypassed'])
        self.emails['send_password_reset_otp_email'].assert_not_called()

    def test_debug_password_reset_verification_keeps_email_binding_and_expiry(self):
        self.start_reset()
        self.set_debug()
        response = self.client.post(reverse('verify_forgot_password_otp'), {'email': self.admin.email})
        self.assertContains(response, 'No pending password reset')
        self.set_debug(False)
        self.start_reset()
        session = self.client.session
        session['pending_password_reset_otp_created'] = time.time() - 601
        session.save()
        self.set_debug()
        response = self.client.post(reverse('verify_forgot_password_otp'), {'email': self.teacher.email})
        self.assertContains(response, 'OTP expired')

    def test_turning_debug_off_invalidates_bypassed_password_reset_get_and_post(self):
        for endpoint in ('forgot_password_reset', 'reset_password'):
            self.set_debug()
            self.start_reset()
            self.set_debug(False)
            if endpoint == 'forgot_password_reset':
                response = self.client.get(reverse(endpoint))
            else:
                response = self.client.post(reverse(endpoint), {
                    'email': self.teacher.email, 'password': 'NewPassword123', 'confirm_password': 'NewPassword123',
                })
            self.assertRedirects(response, reverse('forgot_password'))
            self.assertNotIn('password_reset_verified', self.client.session)

    def test_normal_password_reset_otp_still_requires_correct_code_and_can_complete(self):
        self.start_reset()
        self.emails['send_password_reset_otp_email'].assert_called_once()
        response = self.client.post(reverse('verify_forgot_password_otp'), {
            'email': self.teacher.email, 'otp': 'incorrect', 'disable_otp': 'on',
        })
        self.assertContains(response, 'Invalid OTP')
        response = self.client.post(reverse('verify_forgot_password_otp'), {
            'email': self.teacher.email, 'otp': self.client.session['pending_password_reset_otp'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('password_reset_otp_bypassed', self.client.session)
        self.set_debug()
        self.set_debug(False)
        response = self.client.post(reverse('reset_password'), {
            'email': self.teacher.email, 'password': 'NewPassword123', 'confirm_password': 'NewPassword123',
        })
        self.assertEqual(response.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertTrue(check_password('NewPassword123', self.teacher.password_hash))
