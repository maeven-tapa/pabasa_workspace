import json
import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from .models import User
from .student_session_lock import (
    STUDENT_SESSION_IDLE_TIMEOUT, STUDENT_SESSION_LEASE_TIMEOUT,
    claim_student_session, student_session_is_active, is_learning_page,
)


@override_settings(SESSION_TIMEOUTS_ENABLED=True)
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

    def test_student_session_cookie_has_no_client_clock_expiry(self):
        response = self.login(self.client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies['sessionid']['max-age'], '')

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

    def test_idle_server_activity_no_longer_blocks_login(self):
        self.assertEqual(self.login(self.client).status_code, 200)
        self.student.refresh_from_db()
        self.student.last_activity = timezone.now() - STUDENT_SESSION_IDLE_TIMEOUT - timedelta(seconds=1)
        self.student.save(update_fields=['last_activity'])
        replacement = self.client_class()
        self.assertEqual(self.login(replacement).status_code, 200)

    def test_device_lease_gap_does_not_expire_current_login(self):
        self.login(self.client)
        self.student.refresh_from_db()
        self.student.last_activity = timezone.now() - timedelta(minutes=5)
        self.student.active_session_last_seen = self.student.last_activity
        self.student.save()
        self.assertTrue(student_session_is_active(self.student, self.client.session.session_key))

    def test_learning_login_survives_delayed_presence_after_lease(self):
        self.login(self.client)
        earlier = timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(minutes=1)
        User.objects.filter(pk=self.student.pk).update(
            active_session_learning=True, last_activity=earlier,
            active_session_last_seen=earlier,
        )
        response = self.client.post(reverse('student_session_heartbeat'), {'page': reverse('assessment')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['protected'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, self.client.session.session_key)

    def test_dashboard_login_uses_idle_timeout_not_presence_lease(self):
        self.login(self.client)
        earlier = timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(minutes=1)
        User.objects.filter(pk=self.student.pk).update(
            active_session_learning=False, last_activity=earlier,
            active_session_last_seen=earlier,
        )
        response = self.client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['protected'])

    def test_ten_learning_accounts_survive_a_delayed_heartbeat_together(self):
        clients = []
        for index in range(10):
            student = self.student if index == 0 else User.objects.create(
                custom_id=f'LIVE-LOCK-{index}', role='student', first_name=f'Learner{index}',
                last_name='Live', middle_initial='', suffix='', sex='female',
                birth_month=1, birth_day=1, birth_year=2012,
                email=f'live-lock-{index}@example.com', password_hash=self.student.password_hash,
            )
            client = self.client_class()
            response = client.post(reverse('login_user'), {'custom_id': student.custom_id, 'password': 'password'})
            self.assertEqual(response.status_code, 200)
            clients.append((student, client, client.session.session_key))
        earlier = timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(minutes=1)
        User.objects.filter(pk__in=[student.pk for student, _, _ in clients]).update(
            active_session_learning=True, last_activity=earlier, active_session_last_seen=earlier,
        )
        responses = [client.post(reverse('student_session_heartbeat'), {'page': reverse('assessment')})
            for _, client, _ in clients]
        self.assertEqual([response.status_code for response in responses], [200] * 10)
        for student, client, original_key in clients:
            student.refresh_from_db()
            self.assertEqual(student.active_session_key, original_key)
            self.assertEqual(client.session.get('user_id'), student.pk)

    def test_disconnected_device_can_still_be_replaced(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(
            active_session_last_seen=timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(seconds=1),
        )
        self.assertEqual(self.login(self.client_class()).status_code, 200)
        self.assertEqual(self.client.post(reverse('student_session_heartbeat')).status_code, 401)

    def test_fresh_learning_presence_still_blocks_second_login(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(
            active_session_learning=True,
            last_activity=timezone.now() - STUDENT_SESSION_IDLE_TIMEOUT,
            active_session_last_seen=timezone.now(),
        )
        replacement = self.client_class()
        response = self.login(replacement)
        self.assertEqual(response.status_code, 409)

    def test_claim_cannot_replace_a_device_that_refreshed_during_validation(self):
        from .student_session_lock import _active_session_is_usable

        self.login(self.client)
        original_key = self.client.session.session_key
        earlier = timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(seconds=1)
        User.objects.filter(pk=self.student.pk).update(active_session_last_seen=earlier)
        calls = []

        def refresh_device(user, key, now):
            if not calls:
                User.objects.filter(pk=self.student.pk).update(active_session_last_seen=now)
            calls.append(key)
            return _active_session_is_usable(user, key, now)

        replacement = SessionStore()
        replacement.update({'user_id': self.student.pk, 'user_role': 'student'})
        replacement.create()
        with patch('pabasa_app.student_session_lock._active_session_is_usable', side_effect=refresh_device):
            self.assertFalse(claim_student_session(self.student.pk, replacement.session_key))
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, original_key)

    def test_heartbeat_refreshes_presence_timestamp(self):
        self.login(self.client)
        old_seen = timezone.now() - timedelta(minutes=1)
        User.objects.filter(pk=self.student.pk).update(active_session_last_seen=old_seen)
        response = self.client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertGreater(self.student.active_session_last_seen, old_seen)

    def test_delayed_heartbeat_from_replaced_session_cannot_refresh_new_owner(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(
            active_session_last_seen=timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(seconds=1),
        )
        replacement = self.client_class()
        self.assertEqual(self.login(replacement).status_code, 200)
        self.student.refresh_from_db()
        replacement_key = self.student.active_session_key
        replacement_seen = self.student.active_session_last_seen

        response = self.client.post(reverse('student_session_heartbeat'))

        self.assertEqual(response.status_code, 401)
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, replacement_key)
        self.assertEqual(self.student.active_session_last_seen, replacement_seen)

    def test_device_replacement_during_heartbeat_validation_keeps_new_owner(self):
        self.login(self.client)
        replacement_seen = timezone.now()

        def replace_while_validating(*args):
            User.objects.filter(pk=self.student.pk).update(
                active_session_key='replacement-during-heartbeat',
                active_session_last_seen=replacement_seen,
            )
            return True

        with patch('pabasa_app.views.student_session_is_active', side_effect=replace_while_validating):
            response = self.client.post(reverse('student_session_heartbeat'), {'activity': '1'})
        self.assertEqual(response.status_code, 401)
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, 'replacement-during-heartbeat')
        self.assertEqual(self.student.active_session_last_seen, replacement_seen)

    def test_learning_login_survives_long_reading_without_requests(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(
            active_session_learning=True, last_activity=timezone.now() - timedelta(hours=2),
        )
        self.student.refresh_from_db()
        self.assertTrue(student_session_is_active(self.student, self.client.session.session_key))
        response = self.client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['protected'])

    def test_idle_timeout_returns_json_and_releases_only_current_claim(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(last_activity=timezone.now() - STUDENT_SESSION_IDLE_TIMEOUT)
        response = self.client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'idle_timeout')
        self.student.refresh_from_db()
        self.assertIsNone(self.student.active_session_key)

    def test_passive_heartbeat_does_not_extend_idle_deadline(self):
        self.login(self.client)
        previous = timezone.now() - timedelta(minutes=29)
        User.objects.filter(pk=self.student.pk).update(last_activity=previous)
        response = self.client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.json()['remaining_seconds'], 61)
        self.student.refresh_from_db()
        self.assertEqual(self.student.last_activity, previous)

    def test_stay_signed_in_renews_before_expiry(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(last_activity=timezone.now() - timedelta(minutes=29))
        response = self.client.post(reverse('student_session_heartbeat'), {'activity': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['remaining_seconds'], 1790)

    def test_expired_login_cannot_be_revived_by_activity_or_learning_claim(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(last_activity=timezone.now() - timedelta(minutes=31))
        response = self.client.post(reverse('student_session_heartbeat'), {
            'activity': '1', 'page': reverse('practice_word_page'),
        })
        self.assertEqual(response.status_code, 401)

    def test_learning_protection_never_bypasses_device_ownership(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(active_session_learning=True, active_session_key='another-device')
        response = self.client.post(reverse('student_session_heartbeat'), {'page': reverse('practice_word_page')})
        self.assertEqual(response.status_code, 401)
        self.student.refresh_from_db()
        self.assertEqual(self.student.active_session_key, 'another-device')

    def test_learning_routes_are_resolved_not_arbitrary_prefixes(self):
        for name in ('practice_word_page', 'practice_sentence_page', 'practice_para_page', 'reading_word_page', 'reading_sentence_page'):
            self.assertTrue(is_learning_page(reverse(name)), name)
        self.assertTrue(is_learning_page(reverse('prescribed_activity_page', args=['lesson27-gawain1'])))
        self.assertTrue(is_learning_page(reverse('assessment')))
        self.assertTrue(is_learning_page(reverse('session_4_gawain_1_page')))
        self.assertTrue(is_learning_page(reverse('courses')))
        self.assertTrue(is_learning_page(reverse('course_student_view')))
        self.assertTrue(is_learning_page(reverse('practice')))
        self.assertTrue(is_learning_page(reverse('practice_game_progression', args=['word'])))
        self.assertFalse(is_learning_page('/dashboard/assessment/not-a-real-page/'))
        self.assertFalse(is_learning_page(reverse('dashboard')))
        self.assertFalse(is_learning_page(reverse('practice_results')))

    def test_session_expiry_uses_real_time_not_admin_debug_clock(self):
        self.login(self.client)
        self.student.refresh_from_db()
        with patch('pabasa_app.system_clock.now', return_value=timezone.now() + timedelta(days=30)):
            self.assertTrue(student_session_is_active(self.student, self.client.session.session_key))
            self.assertTrue(claim_student_session(self.student.pk, self.client.session.session_key))


class SessionTimeoutConfigurationTests(SimpleTestCase):
    def test_deployment_environment_cannot_reenable_automatic_timeouts(self):
        result = subprocess.run([sys.executable, '-c',
            'import json; from django.conf import settings; '
            'print(json.dumps([settings.SESSION_TIMEOUTS_ENABLED, settings.SESSION_COOKIE_AGE, '
            'settings.SESSION_EXPIRE_AT_BROWSER_CLOSE]))'],
            env={**os.environ, 'SESSION_TIMEOUTS_ENABLED': 'true'},
            capture_output=True, text=True, check=True, timeout=30)
        enabled, lifetime, browser_close = json.loads(result.stdout)
        self.assertFalse(enabled)
        self.assertGreaterEqual(lifetime, 99 * 365 * 24 * 60 * 60)
        self.assertFalse(browser_close)


@override_settings(SESSION_TIMEOUTS_ENABLED=False, SESSION_COOKIE_AGE=100 * 365 * 24 * 60 * 60)
class SessionTimeoutDisabledTests(TestCase):
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

    def test_dashboard_and_passive_heartbeat_survive_long_inactivity_without_warning(self):
        client, _ = self.login('student')
        old = timezone.now() - timedelta(days=30)
        User.objects.filter(pk=self.users['student'].pk).update(
            active_session_learning=False, last_activity=old, active_session_last_seen=old,
        )
        response = client.post(reverse('student_session_heartbeat'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['timeouts_enabled'])
        self.assertTrue(response.json()['protected'])
        self.users['student'].refresh_from_db()
        self.assertEqual(self.users['student'].last_activity, old)
        self.assertEqual(client.get(reverse('dashboard')).status_code, 200)
        self.assertContains(client.get(reverse('dashboard')), '"timeouts_enabled": false')

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
        self.assertEqual(client.post(reverse('student_session_heartbeat')).status_code, 401)
        self.users['student'].refresh_from_db()
        self.assertEqual(self.users['student'].active_session_key, 'different-device')

    def test_reenabling_policy_restores_normal_cookie_lifetimes_for_existing_accounts(self):
        for role in self.users:
            with self.subTest(role=role):
                client, _ = self.login(role)
                with override_settings(SESSION_TIMEOUTS_ENABLED=True, SESSION_COOKIE_AGE=14 * 24 * 60 * 60):
                    self.assertEqual(client.get(reverse('home')).status_code, 200)
                    self.assertFalse(client.session.get('session_timeouts_disabled'))
                    self.assertEqual(client.session.get_expire_at_browser_close(), role == 'student')
                    stored = Session.objects.get(session_key=client.session.session_key)
                    self.assertLess(stored.expire_date, timezone.now() + timedelta(days=15))
