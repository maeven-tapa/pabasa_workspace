"""Admin calendar UI regression checks against a disposable Django database.

Requires Node, playwright-core (or PABASA_PLAYWRIGHT_PATH), and Chrome.
Run explicitly: manage.py test pabasa_app.tests_admin_calendar_browser
"""
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase
from django.urls import reverse

from .models import CalendarEvent, SchoolCalendar, User


class AdminCalendarAccessTests(TestCase):
    def test_anonymous_and_non_admin_roles_cannot_read_or_change_calendar(self):
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        for role in (None, 'student', 'teacher', 'principal'):
            with self.subTest(role=role):
                client = Client()
                if role:
                    user = User.objects.create(custom_id=f'CAL-{role}', role=role,
                        first_name='Calendar', last_name='Test', sex='male', birth_month=1,
                        birth_day=1, birth_year=1985, email=f'{role}@example.invalid', password_hash='!')
                    session = client.session
                    session.update({'user_id': user.pk, 'user_role': role})
                    session.save()
                url = reverse('admin_school_calendar')
                self.assertRedirects(client.get(url), reverse('auth'), fetch_redirect_response=False)
                response = client.post(url, {'action': 'save_suspensions', 'calendar_id': calendar.pk,
                    'suspension_dates': '2026-10-14'})
                self.assertRedirects(response, reverse('auth'), fetch_redirect_response=False)
        self.assertFalse(CalendarEvent.objects.exists())


class AdminCalendarBrowserTests(StaticLiveServerTestCase):
    def test_calendar_layout_and_interactions(self):
        admin = User.objects.create(custom_id='CAL-ADMIN', role='admin', first_name='Calendar',
            last_name='Test', sex='male', birth_month=1, birth_day=1, birth_year=1985,
            email='calendar-admin@example.invalid', password_hash='!')
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1, is_active=True)
        SchoolCalendar.objects.create(school_year='2025-2026', current_term=1, is_active=False)
        for kind, title, start, end in [
            ('school_opening', 'Opening Block', '2026-07-01', '2026-07-14'),
            ('school_closing', 'Closing Block', '2027-05-03', '2027-05-14'),
            ('pre_assessment', 'Assessment across weekend', '2026-10-09', '2026-10-20'),
            ('other', 'Class Suspension', '2026-10-14', '2026-10-14'),
            ('other', 'Sunday event', '2026-10-11', '2026-10-11'),
            ('other', 'Saturday event', '2026-10-17', '2026-10-17'),
            ('other', 'Long <b>literal</b> event title for testing narrow columns', '2026-10-13', '2026-10-13'),
            ('holiday', 'Holiday', '2026-10-16', '2026-10-16'),
        ]:
            CalendarEvent.objects.create(school_calendar=calendar, term=1, event_type=kind,
                title=title, start_date=date.fromisoformat(start), end_date=date.fromisoformat(end))
        session = self.client.session
        session.update({'user_id': admin.pk, 'user_role': 'admin'})
        session.save()
        before = list(CalendarEvent.objects.order_by('pk').values())
        environment = dict(os.environ, PABASA_CALENDAR_SERVER=self.live_server_url,
            PABASA_CALENDAR_COOKIE=self.client.cookies['sessionid'].value,
            PABASA_CALENDAR_URL=reverse('admin_school_calendar') + f'?calendar_id={calendar.pk}')
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_admin_calendar.cjs'
        # Keep the date fixture and the newly synchronized clock consistent,
        # including when the browser exercises the Today button.
        with patch('pabasa_app.views.system_today', return_value=date(2026, 10, 12)), \
             patch('pabasa_app.views.system_now', return_value=datetime(2026, 10, 12, 7, 20, tzinfo=timezone.utc)):
            result = subprocess.run(['node', str(script)], env=environment,
                capture_output=True, text=True, timeout=360)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(CalendarEvent.objects.order_by('pk').values()), before)
        print(result.stdout.strip())
