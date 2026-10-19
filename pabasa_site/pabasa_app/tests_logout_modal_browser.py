"""Exercise the shared logout overlay in real Chrome using disposable sessions."""
import json
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from .models import Enrollment, School, SchoolCalendar, Section, User


@override_settings(MIDDLEWARE=[
    'pabasa_app.tests_course_reports_browser.SerializedReportsTestRequests',
    *settings.MIDDLEWARE,
])
class LogoutModalBrowserTests(StaticLiveServerTestCase):
    def test_shared_overlay_across_dashboard_course_tabs_and_mobile(self):
        school = School.objects.create(name='Logout Test School', code='LOGOUT')
        calendar = SchoolCalendar.objects.create(
            school_year='2026-2027', current_term=1, is_active=True)
        teacher = User.objects.create(
            custom_id='LOGOUT-TEACHER', role='teacher', first_name='Sample',
            last_name='Teacher', school_record=school, email='teacher@example.com',
            sex='female', birth_month=1, birth_day=1, birth_year=1990)
        section = Section.objects.create(
            school=school, school_calendar=calendar, teacher=teacher,
            class_name='Grade 2 Reading', class_code='LOGOUT-CLASS',
            subject='Reading', grade_level='Grade 2', section='A')
        for index in range(20):
            student = User.objects.create(
                custom_id=f'LOGOUT-{index:02}', role='student', first_name='Sample',
                last_name=f'Student {index:02}', email=f'student{index}@example.com',
                school_record=school, grade_level='Grade 2',
                sex='female', birth_month=1, birth_day=1, birth_year=2015)
            Enrollment.objects.create(student=student, section=section,
                                      assigned_teacher=teacher, school_calendar=calendar)
        sessions = []
        for _ in range(3):
            client = self.client_class()
            session = client.session
            session.update({'user_id': teacher.pk, 'user_role': 'teacher'})
            session.save()
            sessions.append(session.session_key)
        script = Path(__file__).resolve().parents[2] / 'tools/test_logout_modal_browser.cjs'
        env = dict(os.environ, PABASA_LOGOUT_SERVER=self.live_server_url,
                   PABASA_LOGOUT_SESSIONS=json.dumps(sessions))
        result = subprocess.run(['node', str(script)], env=env, text=True,
                                capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(Session.objects.filter(session_key=sessions[0]).exists())
        self.assertFalse(Session.objects.filter(session_key__in=sessions[1:]).exists())
        print(result.stdout.strip())
