"""Actual teacher pages and review endpoints, using isolated synthetic data."""
import io
import os
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.urls import reverse
from django.core.signals import got_request_exception

from . import tests_review_queue as fixtures
from .models import StudentActivityRecordingSubmission, PrescribedReadingAttempt


class ReviewQueueBrowserTests(StaticLiveServerTestCase):
    setUp = fixtures.ReviewQueueTests.setUp
    client_for = fixtures.ReviewQueueTests.client_for
    setup_scope = fixtures.ReviewQueueTests.setup_scope
    progress = fixtures.ReviewQueueTests.progress
    recording = fixtures.ReviewQueueTests.recording
    supplementary = fixtures.ReviewQueueTests.supplementary

    def test_responsive_workspace_and_real_review_actions(self):
        self.setup_scope()
        self.progress()
        first = self.recording(index=0)
        self.recording(index=1, teacher_score=0, status='checked')
        self.progress('session-4-gawain-2')
        self.recording('session-4-gawain-2', substep=0)
        self.progress('session-5-lesson-14-gawain-4')
        self.recording('session-5-lesson-14-gawain-4', review_status='pending')
        self.progress('aral-s9-a1-family-drawing', activity_completed=False, state={
            'submitted': True, 'awaiting_teacher_verdict': True,
            'answers': {'item-1': {'text': 'This is my family.', 'strokes': [
                {'color': '#183e63', 'width': 5, 'points': [[200, 200], [300, 100], [400, 200], [400, 350], [200, 350], [200, 200]]}]}}})
        self.progress('aral-s9-a2-helping-drawing', activity_completed=False,
            state={'submitted': True, 'awaiting_teacher_verdict': True, 'draft': {'text': 'Thank you', 'strokes': []}})
        self.progress('lesson-13-gawain-1'); self.recording('lesson-13-gawain-1')
        single = self.recording('lesson-1-gawain-1', index=None)
        self.progress('lesson-1-gawain-1', activity_completed=False,
            state={'submitted': True, 'submission_id': single.pk})
        reading = PrescribedReadingAttempt.objects.create(student=self.student, school_calendar=self.calendar,
            term=1, activity_key='lesson-15-gawain-3', item_index=0, audio_file='disposable/reading.wav')
        self.progress('lesson-15-gawain-3', state={'item_results': {
            '0': {'attempt_id': str(reading.attempt_id), 'review_version': 0}}})
        self.progress('lesson-29-gawain-3', activity_completed=False, total_items=11,
            state={'submitted': True, 'awaiting_teacher_verdict': True, 'traces': [
                [[{'x': .2, 'y': .2}, {'x': .35, 'y': .8}], [{'x': .65, 'y': .2}, {'x': .8, 'y': .8}]]] * 33})
        for index in range(11):
            self.recording('lesson-29-gawain-3', index=index,
                teacher_score=1 if index < 10 else None, status='checked' if index < 10 else 'submitted')
        retell, _ = self.supplementary('retell_story')
        response, _ = self.supplementary('story_response')
        retell.response_text = 'We helped our friend find her way home.'
        retell.save(update_fields=['response_text'])
        response.response_text = 'The friends worked together.'
        response.save(update_fields=['response_text'])
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as wav:
            wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x00\x00' * 16000)
        for row in StudentActivityRecordingSubmission.objects.all():
            row.audio_file.save(f'local-review-{row.pk}.wav', ContentFile(audio.getvalue()))
        reading.audio_file.save('local-fluency.wav', ContentFile(audio.getvalue()))
        # Use the complete page shell while avoiding unrelated dashboard data work.
        context = patch('pabasa_app.views._dashboard_context', return_value={
            'nav_role': 'teacher', 'first_name': 'Teacher', 'last_name': 'Demo', 'initials': 'TD',
        })
        context.start(); self.addCleanup(context.stop)
        diagnostics = []
        def request_error(sender, request, **kwargs):
            exc = sys.exc_info()[1]
            diagnostics.append({'path': request.path, 'exception': str(exc), 'exception_type': type(exc).__name__})
        got_request_exception.connect(request_error, weak=False)
        self.addCleanup(got_request_exception.disconnect, request_error)
        queue = self.teacher_client.get(reverse('teacher_review_queue_api'))
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()['total'], 11)
        environment = dict(os.environ,
            PABASA_REVIEW_SERVER=self.live_server_url,
            PABASA_REVIEW_COOKIE=self.teacher_client.cookies['sessionid'].value,
            PABASA_REVIEW_RECORD=str(first.pk),
            PABASA_REVIEW_RETELL=str(retell.material_id),
            PABASA_REVIEW_RESPONSE=str(response.material_id),
        )
        script = Path(__file__).resolve().parents[2] / 'tools/test_needs_checking.cjs'
        result = subprocess.run(['node', str(script)], env=environment, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr + str(diagnostics))
        first.refresh_from_db(); retell.refresh_from_db(); response.refresh_from_db()
        self.assertEqual(first.teacher_score, 1)
        self.assertIsNotNone(retell.reviewed_at)
        self.assertIsNone(retell.grade)
        self.assertEqual(response.grade, 4)
