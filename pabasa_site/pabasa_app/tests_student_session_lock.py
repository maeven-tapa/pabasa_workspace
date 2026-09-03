from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import User
from .student_session_lock import STUDENT_SESSION_IDLE_TIMEOUT


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
