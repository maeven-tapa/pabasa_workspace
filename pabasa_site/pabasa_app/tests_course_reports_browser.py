"""Exercise report selection, delivery states and layout using disposable data."""
import os
from pathlib import Path
import subprocess
from threading import Lock
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from .models import Enrollment, Note, School, SchoolCalendar, Section, User


class SerializedReportsTestRequests:
    """Avoid concurrent use of Django's shared in-memory SQLite test connection."""
    lock = Lock()

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with self.lock:
            return self.get_response(request)


@override_settings(MIDDLEWARE=[
    'pabasa_app.tests_course_reports_browser.SerializedReportsTestRequests',
    *settings.MIDDLEWARE,
])
class CourseReportsBrowserTests(StaticLiveServerTestCase):
    def test_composer_selection_delivery_and_responsive_layout(self):
        school = School.objects.create(name='Composer Test School', code='COMPOSER')
        calendar = SchoolCalendar.objects.create(
            school_year='2026-2027', current_term=1, is_active=True)
        teacher = User.objects.create(
            custom_id='COMPOSER-TEACHER', role='teacher', first_name='Sample',
            last_name='Teacher', school_record=school, email='teacher@example.com',
            sex='female', birth_month=1, birth_day=1, birth_year=1990)
        section = Section.objects.create(
            school=school, school_calendar=calendar, teacher=teacher,
            class_name='Grade 2 Reading', class_code='COMPOSER-CLASS',
            subject='Reading', grade_level='Grade 2', section='A')
        for index in range(20):
            student = User.objects.create(
                custom_id=f'COMPOSER-{index:02}', role='student',
                first_name='Sample', last_name=f'Student {index:02}',
                email=f'student{index}@example.com' if index < 19 else '',
                school_record=school, grade_level='Grade 2',
                sex='female', birth_month=1, birth_day=1, birth_year=2015)
            Enrollment.objects.create(
                student=student, section=section, assigned_teacher=teacher,
                school_calendar=calendar, is_active=True)
        session = self.client.session
        session.update({'user_id': teacher.pk, 'user_role': 'teacher'})
        session.save()
        script = Path(__file__).resolve().parents[2] / 'tools/test_course_reports_browser.cjs'
        env = dict(os.environ, PABASA_REPORTS_SERVER=self.live_server_url,
                   PABASA_REPORTS_COOKIE=self.client.cookies['sessionid'].value)
        with patch('pabasa_app.views.EmailMultiAlternatives') as email:
            result = subprocess.run(['node', str(script)], env=env, text=True,
                                    capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(email.return_value.send.call_count, 1)
        self.assertTrue(email.return_value.attach.call_args.args[1].startswith(b'%PDF'))
        self.assertEqual(Note.objects.filter(teacher=teacher, note_type='course_update:general').count(), 1)
        print(result.stdout.strip())
