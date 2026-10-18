"""Focused event-click regressions using Chrome and a disposable Django database.

Run: manage.py test pabasa_app.tests_admin_calendar_events_browser
Requires Node, Chrome and playwright-core (or PABASA_PLAYWRIGHT_PATH).
"""
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from .models import CalendarEvent, SchoolCalendar, User


class AdminCalendarEventBrowserTests(StaticLiveServerTestCase):
    def test_protected_date_details_custom_editing_and_week_only_list(self):
        admin = User.objects.create(custom_id='EVENT-ADMIN', role='admin',
            first_name='Calendar', last_name='Regression', sex='male', birth_month=1,
            birth_day=1, birth_year=1985, email='event-admin@example.invalid', password_hash='!')
        calendar = SchoolCalendar.objects.create(school_year='2026-2027', current_term=1)
        for kind, title, start, end in [
            ('school_opening', 'Opening Block', '2026-10-05', '2026-10-09'),
            ('pre_assessment', 'Pre-Assessment Week', '2026-10-19', '2026-10-23'),
            ('school_closing', 'Closing Block', '2026-11-02', '2026-11-06'),
            ('holiday', 'Holiday <b>literal</b>', '2026-11-01', '2026-11-10'),
            ('midline_assessment', 'Midline Assessment Week', '2026-11-09', '2026-11-13'),
            ('post_assessment', 'Post-Assessment Week', '2026-12-07', '2026-12-11'),
            ('examination', 'Examination Week', '2026-12-14', '2026-12-18'),
            ('other', 'Custom event <b>literal</b>', '2026-11-03', '2026-11-05'),
            ('other', 'Overflow A', '2026-11-18', '2026-11-20'),
            ('other', 'Overflow B', '2026-11-18', '2026-11-20'),
            ('other', 'Overflow C', '2026-11-18', '2026-11-20'),
            ('holiday', 'Overflow Holiday', '2026-11-18', '2026-11-20'),
        ]:
            CalendarEvent.objects.create(school_calendar=calendar, term=1, event_type=kind,
                title=title, start_date=date.fromisoformat(start), end_date=date.fromisoformat(end),
                description='Description <b>literal</b>')
        CalendarEvent.objects.create(school_calendar=calendar, term=3,
            event_type='school_closing', title='Closing Block',
            start_date=date(2027, 5, 3), end_date=date(2027, 5, 7))
        session = self.client.session
        session.update({'user_id': admin.pk, 'user_role': 'admin'})
        session.save()
        before = list(CalendarEvent.objects.order_by('pk').values())
        environment = dict(os.environ, PABASA_CALENDAR_SERVER=self.live_server_url,
            PABASA_CALENDAR_COOKIE=self.client.cookies['sessionid'].value,
            PABASA_CALENDAR_URL=reverse('admin_school_calendar') + f'?calendar_id={calendar.pk}')
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_admin_calendar_events.cjs'
        with patch('pabasa_app.views.system_today', return_value=date(2026, 11, 4)), \
             patch('pabasa_app.views.system_now', return_value=datetime(2026, 11, 4, tzinfo=timezone.utc)):
            result = subprocess.run(['node', str(script)], env=environment,
                capture_output=True, text=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(CalendarEvent.objects.order_by('pk').values()), before)
        print(result.stdout.strip())
