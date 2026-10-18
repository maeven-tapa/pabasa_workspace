"""Application-clock API and calendar regressions; browser uses a disposable DB."""
import os
import subprocess
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SchoolCalendar, SystemTimeOverride, User
from .system_clock import invalidate_override_cache


def sign_in_admin(client):
    admin = User.objects.create(custom_id='CLOCK-ADMIN', role='admin', first_name='Clock',
        last_name='Test', sex='male', birth_month=1, birth_day=1, birth_year=1985,
        email='calendar-clock@example.invalid', password_hash='!')
    session = client.session
    session.update({'user_id': admin.pk, 'user_role': 'admin'})
    session.save()
    return admin


class AdminCalendarClockTests(TestCase):
    def setUp(self):
        sign_in_admin(self.client)
        invalidate_override_cache()
        self.addCleanup(invalidate_override_cache)

    def test_real_application_clock_returns_full_manila_timestamp_and_is_not_cached(self):
        instant = datetime(2026, 10, 18, 18, 25, 36, tzinfo=dt_timezone.utc)
        # The endpoint must use the configured server zone, even if a request
        # happens to have activated a different timezone.
        with patch('pabasa_app.system_clock._real_now', return_value=instant), timezone.override('America/Los_Angeles'):
            response = self.client.get(reverse('admin_system_time'))
        self.assertEqual(response.json(), {'success': True,
            'server_time': '2026-10-19T02:25:36+08:00', 'time_zone': 'Asia/Manila'})
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_persisted_override_advances_and_changes_reach_the_endpoint(self):
        real = datetime(2026, 10, 18, tzinfo=dt_timezone.utc)
        simulated = datetime(2040, 1, 2, 23, 59, 50, tzinfo=ZoneInfo('Asia/Manila'))
        override = SystemTimeOverride.objects.create(enabled=True,
            reference_time=simulated, configured_at=real)
        with patch('pabasa_app.system_clock._real_now', return_value=real + timedelta(seconds=20)):
            self.assertEqual(self.client.get(reverse('admin_system_time')).json()['server_time'],
                '2040-01-03T00:00:10+08:00')
            override.reference_time = simulated + timedelta(days=7)
            override.save()
            invalidate_override_cache()
            self.assertEqual(self.client.get(reverse('admin_system_time')).json()['server_time'],
                '2040-01-10T00:00:10+08:00')
            override.enabled = False
            override.save()
            invalidate_override_cache()
            self.assertEqual(self.client.get(reverse('admin_system_time')).json()['server_time'],
                '2026-10-18T08:00:20+08:00')

    def test_time_endpoint_remains_admin_only_and_get_only(self):
        url = reverse('admin_system_time')
        for role in (None, 'student', 'teacher', 'principal'):
            with self.subTest(role=role):
                client = Client()
                if role:
                    session = client.session
                    session.update({'user_id': 12345, 'user_role': role})
                    session.save()
                self.assertRedirects(client.get(url), reverse('auth'), fetch_redirect_response=False)
        self.assertEqual(self.client.post(url).status_code, 405)


class AdminCalendarClockBrowserTests(StaticLiveServerTestCase):
    def test_indicator_uses_server_clock_in_a_different_client_timezone(self):
        sign_in_admin(self.client)
        SchoolCalendar.objects.create(school_year='2040-2041', current_term=1, is_active=True)
        SystemTimeOverride.objects.create(enabled=True,
            reference_time=datetime(2040, 1, 2, 15, 20, tzinfo=ZoneInfo('Asia/Manila')),
            configured_at=timezone.now())
        invalidate_override_cache()
        self.addCleanup(invalidate_override_cache)
        environment = dict(os.environ, PABASA_CALENDAR_SERVER=self.live_server_url,
            PABASA_CALENDAR_COOKIE=self.client.cookies['sessionid'].value)
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_admin_calendar_clock.cjs'
        result = subprocess.run(['node', str(script)], env=environment,
            capture_output=True, text=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
