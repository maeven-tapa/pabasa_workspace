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
from .student_session_lock import (
    claim_student_session, student_session_is_active,
)


class StudentSessionLockTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id='LOCK-STU', role='student', first_name='Lock', last_name='Student',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1,
            birth_year=2012, email='lock-student@example.com',
            password_hash=make_password('password'),
        )

    def login(self, client):
        return client.post(reverse('login_user'), {'custom_id': 'LOCK-STU', 'password': 'password'})

    def test_first_login_succeeds_and_second_session_is_rejected(self):
        first = self.login(self.client)
        self.assertEqual(first.status_code, 200)
        first_key = self.client.session.session_key

        second_client = self.client_class()
        second = self.login(second_client)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(self.student.refresh_from_db(), None)
        self.assertEqual(self.student.active_session_key, first_key)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_second_session_can_explicitly_take_over_and_invalidates_old_session(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        first_key = self.client.session.session_key
        second_client = self.client_class()
        response = second_client.post(reverse('login_user'), {
            'custom_id': 'LOCK-STU', 'password': 'password', 'takeover': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=first_key).exists())
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, second_client.session.session_key)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)

    def test_logout_clears_claim_and_allows_another_session(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 302)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.active_session_key)
        self.assertEqual(self.login(self.client_class()).status_code, 200)

    def test_mismatched_student_session_is_rejected(self):
        self.student.active_session_key = 'different-session'
        self.student.save(update_fields=['active_session_key'])
        session = self.client.session
        session['user_id'] = self.student.id
        session['user_role'] = 'student'
        session.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_mismatched_session_cannot_reach_assessment(self):
        self.student.active_session_key = 'assessment-session-on-device-a'
        self.student.save(update_fields=['active_session_key'])
        session = self.client.session
        session['user_id'] = self.student.id
        session['user_role'] = 'student'
        session.save()
        response = self.client.get(reverse('assessment'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_sessions_are_not_locked(self):
        teacher = User.objects.create(
            custom_id='LOCK-TCH', role='teacher', first_name='Lock', last_name='Teacher',
            middle_initial='', suffix='', sex='male', birth_month=1, birth_day=1,
            birth_year=1990, email='lock-teacher@example.com', password_hash=make_password('password'),
        )
        for client in (self.client, self.client_class()):
            response = client.post(reverse('login_user'), {'custom_id': teacher.custom_id, 'password': 'password'})
            self.assertEqual(response.status_code, 200)


    def test_expired_server_session_no_longer_blocks_login(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        active_key = self.client.session.session_key
        Session.objects.filter(session_key=active_key).update(expire_date=timezone.now() - timedelta(seconds=1))
        replacement = self.client_class()
        self.assertEqual(self.login(replacement).status_code, 200)

    def test_cleared_auth_session_no_longer_blocks_login(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        active_key = self.client.session.session_key
        session = Session.objects.get(session_key=active_key)
        session.session_data = self.client.session.encode({})
        session.save(update_fields=['session_data'])

        replacement = self.client_class()
        response = self.login(replacement)

        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, replacement.session.session_key)

    def test_reauthentication_after_server_session_is_invalidated_succeeds(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        active_key = self.client.session.session_key
        self.client.session.flush()

        response = self.login(self.client)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.client.session.session_key, active_key)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_reauthentication_logout_flow_releases_current_claim(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        active_key = self.client.session.session_key

        response = self.client.get(reverse('logout') + '?next=' + reverse('auth'))

        self.assertRedirects(response, reverse('auth'))
        self.student.refresh_from_db()
        self.assertIsNone(self.student.active_session_key)
        self.assertEqual(self.login(self.client).status_code, 200)
        self.assertNotEqual(self.client.session.session_key, active_key)

    def test_auth_page_cleans_matching_orphaned_session_claim(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        active_key = self.client.session.session_key
        session = Session.objects.get(session_key=active_key)
        session.session_data = self.client.session.encode({})
        session.save(update_fields=['session_data'])

        self.assertEqual(self.client.get(reverse('auth')).status_code, 200)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.active_session_key)
        self.assertEqual(self.login(self.client).status_code, 200)


    def test_long_inactivity_neither_ends_login_nor_allows_device_takeover(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        key = self.client.session.session_key
        old = timezone.now() - timedelta(days=90)
        User.objects.filter(pk=self.student.pk).update(active_session_created_at=old)
        with patch('django.contrib.sessions.backends.db.timezone.now', return_value=timezone.now() + timedelta(days=90)):
            response = self.client.post(reverse('reading_transcribe_api'))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.login(self.client_class()).status_code, 409)
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, key)
        self.assertEqual(self.student.active_session_created_at, old)

    def test_browsing_does_not_track_activity_or_inject_session_ui(self):
        self.login(self.client)
        self.student.refresh_from_db()
        previous = self.student.updated_at
        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.updated_at, previous)
        for fragment in ('student-session-config', 'student_session.js', 'student_session.css',
                         'student-session-dialog', 'Still there?', 'Stay signed in'):
            self.assertNotContains(dashboard, fragment)

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

    def test_disabling_timeouts_does_not_bypass_student_device_ownership(self):
        client, _ = self.login('student')
        User.objects.filter(pk=self.users['student'].pk).update(active_session_key='different-device')
        self.assertEqual(client.post(reverse('reading_transcribe_api')).status_code, 401)
        self.users['student'].refresh_from_db()
        self.assertEqual(self.users['student'].active_session_key, 'different-device')
