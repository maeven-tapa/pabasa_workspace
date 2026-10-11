"""Actual L15 G2 page and APIs, disposable student; capture/STT/audio simulated."""
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from . import tests_lesson15_reading as fixtures
from .models import StudentActivityProgress

KEY = 'lesson-15-gawain-2-angkop-na-pantig'


class Lesson15Gawain2SpeechBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def test_rejections_retries_reading_matching_and_completion(self):
        environment = dict(os.environ, PABASA_L15G2_SERVER=self.live_server_url,
            PABASA_L15G2_STUDENT_COOKIE=self.student_client.cookies['sessionid'].value,
            PABASA_L15G2_URL=reverse('prescribed_activity_page', args=[KEY]))
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_lesson15_gawain2_stt.cjs'
        transcripts = ['yo-yo 한국', 'yo yo', '마사야', 'masaya', 'ma sa ya',
                       'yun gib', 'o ya y', 'o ya yi', 'hielo']
        calls = []

        def provider(*args, **kwargs):
            index = len(calls)
            calls.append(kwargs)
            kwargs['response_metadata']['response_language_codes'] = ['ko-KR' if index == 3 else 'fil-PH']
            return transcripts[index], 'chirp_3', ''

        with patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=provider):
            result = subprocess.run(['node', str(script)], env=environment,
                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(calls), 9)
        expected = ['yo-yo', 'yo-yo', 'masaya', 'masaya', 'masaya', 'yungib', 'oyayi', 'oyayi', 'yelo']
        for call, word in zip(calls, expected):
            self.assertEqual(call['language_code'], 'fil-PH')
            self.assertEqual(call['recognition_context'], [word])
            self.assertFalse(call['allow_fallback'])
        progress = StudentActivityProgress.objects.get(student=self.student, activity_key=KEY,
            school_calendar=self.calendar, term=1)
        self.assertTrue(progress.activity_completed)
        self.assertEqual(progress.state['part'], 2)
        self.assertEqual(progress.state['connections'],
            {'yo-yo': 'b4', 'masaya': 'b1', 'yungib': 'b5', 'oyayi': 'b3', 'yelo': 'b2'})
        print(result.stdout.strip())
