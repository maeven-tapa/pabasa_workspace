"""Actual L14 G2 page/API, disposable student; microphone/provider simulated."""
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from . import tests_lesson15_reading as fixtures
from .models import StudentActivityProgress


class Lesson14Gawain2SpeechBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.Lesson15ReadingTests.setUp
    client_for = fixtures.Lesson15ReadingTests.client_for

    def test_non_filipino_retry_and_refresh_preserve_progress(self):
        environment = dict(os.environ, PABASA_L14_SERVER=self.live_server_url,
            PABASA_L14_STUDENT_COOKIE=self.student_client.cookies['sessionid'].value,
            PABASA_L14_URL=reverse('prescribed_activity_page', args=['lesson-14-gawain-2']))
        script = Path(__file__).resolve().parents[2] / 'tools' / 'test_lesson14_gawain2_stt.cjs'
        with patch('pabasa_app.views.transcribe_audio_bytes_with_model', side_effect=[
                ('mata 한국', 'chirp_3', ''), ('ma ta', 'chirp_3', ''),
                ('오 야 이', 'chirp_3', ''), ('buto', 'chirp_3', '')]) as provider:
            result = subprocess.run(['node', str(script)], env=environment,
                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(provider.call_count, 4)
        for call in provider.call_args_list:
            self.assertEqual(call.kwargs['language_code'], 'fil-PH')
            self.assertEqual(call.kwargs['recognition_context'],
                ['mata'] if call == provider.call_args_list[0] or call == provider.call_args_list[1] else ['buto'])
            self.assertFalse(call.kwargs['allow_fallback'])
        progress = StudentActivityProgress.objects.get(student=self.student,
            activity_key='lesson-14-gawain-2', school_calendar=self.calendar, term=1)
        self.assertEqual(progress.state['current_index'], 2)
        self.assertEqual(progress.state['part'], 1)
        self.assertFalse(progress.activity_completed)
        self.assertEqual(progress.state.get('connections', {}), {})
        print(result.stdout.strip())
