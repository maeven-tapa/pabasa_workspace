import json
import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from .models import User


class StudentMultiDeviceSessionTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id='MULTI-STU', role='student', first_name='Multi', last_name='Student',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2012, email='multi-student@example.com',
            password_hash=make_password('password'),
        )

    def login(self, client, **extra):
        return client.post(reverse('login_user'), {
            'custom_id': self.student.custom_id, 'password': 'password', **extra,
        })

    def test_multiple_devices_stay_authenticated_without_confirmation(self):
        second = self.client_class()
        for client in (self.client, second):
            response = self.login(client)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertNotIn('can_takeover', response.json())
        self.assertNotEqual(self.client.session.session_key, second.session.session_key)
        for client in (self.client, second):
            self.assertEqual(client.get(reverse('dashboard')).status_code, 200)
            self.assertEqual(client.get(reverse('assessment')).status_code, 200)
            self.assertEqual(client.post(reverse('reading_transcribe_api')).status_code, 400)
            self.assertEqual(client.session.get('user_id'), self.student.pk)

    def test_legacy_takeover_parameter_does_not_end_other_session(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        key = self.client.session.session_key
        self.assertEqual(self.login(self.client_class(), takeover='1').status_code, 200)
        self.assertTrue(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_logout_only_ends_current_device_session(self):
        second = self.client_class()
        self.login(self.client)
        self.login(second)
        key = self.client.session.session_key
        self.assertEqual(self.client.get(reverse('logout')).status_code, 302)
        self.assertNotIn('user_id', self.client.session)
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertEqual(second.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(second.session.get('user_id'), self.student.pk)

    def test_login_still_requires_valid_credentials(self):
        self.login(self.client)
        second = self.client_class()
        self.assertEqual(self.login(second, password='wrong').status_code, 401)
        self.assertNotIn('user_id', second.session)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_unauthenticated_requests_still_require_login(self):
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        self.assertEqual(self.client.post(reverse('reading_transcribe_api')).status_code, 401)

    def test_long_inactivity_allows_another_device_without_ending_first(self):
        self.login(self.client)
        key = self.client.session.session_key
        future = timezone.now() + timedelta(days=90)
        with patch('django.contrib.sessions.backends.db.timezone.now', return_value=future):
            self.assertEqual(self.login(self.client_class()).status_code, 200)
            self.assertEqual(self.client.post(reverse('reading_transcribe_api')).status_code, 400)
        self.assertEqual(self.client.session.session_key, key)

    def test_login_page_has_no_device_takeover_prompt(self):
        response = self.client.get(reverse('auth'))
        self.assertEqual(response.status_code, 200)
        for fragment in ('takeoverBtn', 'takeoverRequested', 'student_session_conflict',
                         'Continue here and end other session'):
            self.assertNotContains(response, fragment)

    def test_obsolete_heartbeat_route_is_removed(self):
        self.login(self.client)
        self.assertEqual(self.client.post('/api/student-session/heartbeat/').status_code, 404)


class PersistentSessionConfigurationTests(SimpleTestCase):
    def test_deployment_environment_cannot_reenable_automatic_timeouts(self):
        result = subprocess.run([sys.executable, '-c',
            'import json; from django.conf import settings; '
            "print(json.dumps([hasattr(settings, 'SESSION_TIMEOUTS_ENABLED'), settings.SESSION_COOKIE_AGE, "
            'settings.SESSION_EXPIRE_AT_BROWSER_CLOSE]))'],
            env={**os.environ, 'SESSION_TIMEOUTS_ENABLED': 'true'},
            capture_output=True, text=True, check=True, timeout=30)
        enabled, lifetime, browser_close = json.loads(result.stdout)
        self.assertFalse(enabled)
        self.assertGreaterEqual(lifetime, 99 * 365 * 24 * 60 * 60)
        self.assertFalse(browser_close)


class PersistentAccountSessionTests(TestCase):
    def setUp(self):
        password = make_password('password')
        self.users = {}
        for role in ('student', 'teacher', 'admin', 'principal'):
            self.users[role] = User.objects.create(
                custom_id=f'NO-TIMEOUT-{role}', role=role, first_name='Session', last_name=role,
                middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
                birth_year=1990, email=f'no-timeout-{role}@example.com', password_hash=password,
            )

    def login(self, role):
        client = self.client_class()
        response = client.post(reverse('login_user'), {
            'custom_id': self.users[role].custom_id, 'password': 'password',
        })
        self.assertEqual(response.status_code, 200, response.content)
        return client, response

    def test_every_role_gets_a_long_lived_cookie_and_server_session(self):
        for role in self.users:
            with self.subTest(role=role):
                client, response = self.login(role)
                self.assertEqual(int(response.cookies[settings.SESSION_COOKIE_NAME]['max-age']), settings.SESSION_COOKIE_AGE)
                stored = Session.objects.get(session_key=client.session.session_key)
                self.assertGreater(stored.expire_date, timezone.now() + timedelta(days=99 * 365))

    def test_every_role_remains_authenticated_past_the_old_django_expiry(self):
        for role in self.users:
            with self.subTest(role=role):
                client, _ = self.login(role)
                original_key = client.session.session_key
                future = timezone.now() + timedelta(days=30)
                with patch('django.contrib.sessions.backends.db.timezone.now', return_value=future):
                    self.assertEqual(client.get(reverse('home')).status_code, 200)
                    self.assertEqual(client.session.get('user_id'), self.users[role].pk)
                    self.assertEqual(client.session.session_key, original_key)

    def test_existing_short_and_browser_close_sessions_are_extended_for_every_role(self):
        for role in self.users:
            client, _ = self.login(role)
            for expiry in (60, 0):
                with self.subTest(role=role, expiry=expiry):
                    session = client.session
                    session.set_expiry(expiry)
                    session.save()
                    response = client.get(reverse('home'))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(client.session.get('user_id'), self.users[role].pk)
                    self.assertEqual(client.session.get('_session_expiry'), settings.SESSION_COOKIE_AGE)
                    stored = Session.objects.get(session_key=client.session.session_key)
                    self.assertGreater(stored.expire_date, timezone.now() + timedelta(days=99 * 365))


    def test_existing_django_admin_sessions_are_extended(self):
        user = get_user_model().objects.create_user(username='django-admin', is_staff=True, is_superuser=True)
        self.client.force_login(user)
        for expiry in (60, 0):
            with self.subTest(expiry=expiry):
                session = self.client.session
                session.set_expiry(expiry)
                session.save()
                response = self.client.get(reverse('admin:index'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.session.get('_auth_user_id'), str(user.pk))
                stored = Session.objects.get(session_key=self.client.session.session_key)
                self.assertGreater(stored.expire_date, timezone.now() + timedelta(days=99 * 365))

    def test_manual_logout_still_invalidates_every_role(self):
        for role in self.users:
            with self.subTest(role=role):
                client, _ = self.login(role)
                original_key = client.session.session_key
                self.assertEqual(client.get(reverse('logout')).status_code, 302)
                self.assertNotIn('user_id', client.session)
                self.assertFalse(Session.objects.filter(session_key=original_key).exists())

    def test_student_sessions_on_multiple_devices_remain_persistent(self):
        first, _ = self.login('student')
        second, _ = self.login('student')
        future = timezone.now() + timedelta(days=90)
        with patch('django.contrib.sessions.backends.db.timezone.now', return_value=future):
            for client in (first, second):
                self.assertEqual(client.post(reverse('reading_transcribe_api')).status_code, 400)
                self.assertEqual(client.session.get('user_id'), self.users['student'].pk)
