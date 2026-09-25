from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from .models import User
from .student_session_lock import (
    STUDENT_SESSION_IDLE_TIMEOUT, STUDENT_SESSION_LEASE_TIMEOUT,
    claim_student_session, student_session_is_active, is_learning_page,
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

    def test_disconnected_device_can_still_be_replaced(self):
        self.login(self.client)
        User.objects.filter(pk=self.student.pk).update(
            active_session_last_seen=timezone.now() - STUDENT_SESSION_LEASE_TIMEOUT - timedelta(seconds=1),
        )
        self.assertEqual(self.login(self.client_class()).status_code, 200)
        self.assertEqual(self.client.post(reverse('student_session_heartbeat')).status_code, 401)

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
        self.assertTrue(is_learning_page(reverse('practice')))
        self.assertTrue(is_learning_page(reverse('practice_game_progression', args=['word'])))
        self.assertFalse(is_learning_page('/dashboard/assessment/not-a-real-page/'))
        self.assertFalse(is_learning_page(reverse('dashboard')))
        self.assertFalse(is_learning_page(reverse('assessment')))
        self.assertFalse(is_learning_page(reverse('practice_results')))

    def test_session_expiry_uses_real_time_not_admin_debug_clock(self):
        self.login(self.client)
        self.student.refresh_from_db()
        with patch('pabasa_app.system_clock.now', return_value=timezone.now() + timedelta(days=30)):
            self.assertTrue(student_session_is_active(self.student, self.client.session.session_key))
            self.assertTrue(claim_student_session(self.student.pk, self.client.session.session_key))
