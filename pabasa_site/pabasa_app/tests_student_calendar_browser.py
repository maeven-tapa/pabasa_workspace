"""Opened student calendar UI in a disposable database, using stored test events."""
import json
import os
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from . import tests_lesson15_reading as fixtures, views
from .models import CalendarEvent


class StudentExpandedCalendarBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def test_opened_modal_navigation_events_and_responsive_layout(self):
        payload = []
        definitions = [
            ('pre_assessment', 'Pre-Assessment', '2026-10-12', '2026-10-16', 'Basahin ang nakatakdang gawain.'),
            ('holiday', 'Holiday "Masayang Araw"', '2026-10-12', '2026-10-12', ''),
            ('other', 'ARAL 1 — After Class', '2026-10-12', '2026-10-16', ''),
            ('school_opening', 'Opening Block', '2026-10-05', '2026-10-09', ''),
            ('school_closing', 'Closing Block', '2026-10-26', '2026-10-30', ''),
            ('holiday', 'Saturday Holiday', '2026-10-17', '2026-10-17', ''),
            ('post_assessment', 'Assessment crosses weekend', '2026-10-16', '2026-10-20', ''),
            ('other', 'Isang mahabang pangalan ng gawain na hindi dapat maputol sa detalye', '2026-10-12', '2026-10-12', '<b>Test description</b>'),
        ]
        for kind, title, start, end, description in definitions:
            event = CalendarEvent.objects.create(school_calendar=self.calendar, event_type=kind,
                title=title, start_date=date.fromisoformat(start), end_date=date.fromisoformat(end),
                description=description, is_published=True)
            item = views._calendar_event_payload(event)
            if title.startswith('ARAL'):
                item['event_type'] = 'aral_1'  # Same derived frontend type as the existing ARAL feed.
            payload.append(item)
        before = list(CalendarEvent.objects.values())
        context = {'nav_role': 'student', 'dashboard_greeting_name': 'Test', 'active_school_calendar': self.calendar,
            'student_session_progress': [{'session': number, 'completed': 0, 'total': 1} for number in range(1, 16)],
            'email': self.student.email, 'student_calendar_events_json': json.dumps(payload),
            'student_calendar_today': '2026-10-12', 'student_calendar_school_year': '2026-2027',
            'student_calendar_current_term': 'Term 1'}
        artifacts = tempfile.mkdtemp(prefix='pabasa-calendar-preview-')
        environment = dict(os.environ, PABASA_CALENDAR_SERVER=self.live_server_url,
            PABASA_CALENDAR_COOKIE=self.student_client.cookies['sessionid'].value,
            PABASA_CALENDAR_URL=reverse('dashboard'), PABASA_CALENDAR_ARTIFACTS=artifacts)
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_student_calendar.cjs'
        with patch('pabasa_app.views._dashboard_context', return_value=context):
            result = subprocess.run(['node', str(script)], env=environment,
                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(CalendarEvent.objects.values()), before)
        print(result.stdout.strip())
